"""Authored boundary fixtures only; these never establish Windows behavior."""
import copy
import ctypes
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend import runtime_lock_attribute_probe as module


def snapshot(attributes=128, times=None):
    return {'identity': [7, 'a' * 32], 'attributes': attributes, 'times': times or [10, 20, 30, 40]}


@pytest.mark.parametrize('attributes', [1, 33])
def test_readonly_transition_preserves_identity_other_attributes_and_explicit_time_outcomes(attributes):
    original = snapshot(128 if attributes == 1 else 32)
    observed = snapshot(attributes, [10, 21, 30, 41])
    assert module.transition(original, observed, True) == {
        'creation_equal': True, 'access_equal': False, 'write_equal': True, 'change_equal': False}
    assert module.transition(original, copy.deepcopy(original), False) == dict.fromkeys(
        ('creation_equal', 'access_equal', 'write_equal', 'change_equal'), True)


@pytest.mark.parametrize('mutation', ['volume', 'file', 'hidden', 'missing-readonly', 'creation', 'write', 'normal-combined'])
def test_unexpected_identity_attributes_or_data_timestamps_cannot_become_verified(mutation):
    observed = snapshot(1)
    if mutation == 'volume': observed['identity'][0] += 1
    if mutation == 'file': observed['identity'][1] = 'b' * 32
    if mutation == 'hidden': observed['attributes'] |= 2
    if mutation == 'missing-readonly': observed['attributes'] = 128
    if mutation == 'creation': observed['times'][0] += 1
    if mutation == 'write': observed['times'][2] += 1
    if mutation == 'normal-combined': observed['attributes'] = 129
    with pytest.raises(module.Refused): module.transition(snapshot(), observed, True)


@pytest.mark.parametrize('value', [None, {}, {'identity': 'private-file-id'},
    {'identity': [True, 'a' * 32], 'attributes': 128, 'times': [1, 2, 3, 4]},
    {'identity': [1, 'a' * 32], 'attributes': 128, 'times': [1, 2, 3, 'private-time']},
    {'identity': [1, 'a' * 32], 'attributes': 128, 'times': [1, 2, 3, 4], 'path': 'private-path'}])
def test_private_wire_snapshot_is_closed_and_typed(value):
    with pytest.raises(module.Refused): module.private_snapshot(value)


@pytest.mark.parametrize('raw', [b'[]', b'null', b'{"state":"x","state":"y"}', b'\xff', b'x' * 4097])
def test_private_frames_refuse_duplicates_untyped_nonascii_and_overflow(raw):
    with pytest.raises(module.Refused): module.decode(raw)


@pytest.mark.parametrize('kind', ['false', 'exception'])
def test_unknown_close_is_sticky_and_never_reuses_a_numeric_handle(kind):
    calls = []
    def close(handle):
        calls.append(handle)
        if kind == 'exception': raise OSError('private close sentinel')
        return 0
    handle = module.Handle(SimpleNamespace(k=SimpleNamespace(CloseHandle=close)), 123)
    with pytest.raises((module.Refused, OSError)): handle.close()
    with pytest.raises(module.Refused): handle.close()
    with pytest.raises(module.Refused): _ = handle.value
    assert calls == [123] and handle.poisoned
    assert any(record is handle for record in module._UNCONFIRMED)


def test_successful_close_is_idempotent_and_exposure_stops():
    calls = []
    handle = module.Handle(SimpleNamespace(k=SimpleNamespace(CloseHandle=lambda h: calls.append(h) or 1)), 123)
    handle.close(); handle.close()
    assert calls == [123]
    with pytest.raises(module.Refused): _ = handle.value


def test_native_basic_info_abi_and_attribute_set_do_not_change_other_fields():
    assert ctypes.sizeof(module.Basic) == 40 and module.Basic.attributes.offset == 32
    assert ctypes.sizeof(module.Identity) == ctypes.sizeof(module.Standard) == 24
    calls = []
    def set_information(handle, kind, information, size):
        value = information._obj
        calls.append((handle, kind, size, value.attributes,
            tuple(getattr(value, name) for name in ('creation', 'access', 'write', 'change'))))
        return 1
    api = module.Windows.__new__(module.Windows)
    api.k = SimpleNamespace(SetFileInformationByHandle=set_information)
    handle = module.Handle(api, 123)
    api.attributes(handle, 128, True)
    api.attributes(handle, 128, False)
    api.attributes(handle, 32, True)
    assert calls == [(123, 0, 40, 1, (0, 0, 0, 0)),
                     (123, 0, 40, 128, (0, 0, 0, 0)),
                     (123, 0, 40, 33, (0, 0, 0, 0))]


@pytest.mark.parametrize('mismatch', ['links', 'directory', 'deleting', 'size', 'attribute', 'content'])
def test_native_snapshot_refuses_unexpected_file_before_any_state_is_accepted(mismatch):
    calls = []
    def query(handle, kind, information, size):
        assert handle == 123
        calls.append(kind)
        value = information._obj
        if kind == 0:
            value.attributes = 2 if mismatch == 'attribute' else 128
            value.creation, value.access, value.write, value.change = 10, 20, 30, 40
        elif kind == 18:
            value.volume = 7
        elif kind == 1:
            value.links = 2 if mismatch == 'links' else 1
            value.directory = mismatch == 'directory'
            value.deleting = mismatch == 'deleting'
            value.size = len(module.CONTENT) + (mismatch == 'size')
        return 1
    def read(handle, output, size, count, overlapped):
        calls.append('read')
        data = b'bad' if mismatch == 'content' else module.CONTENT
        ctypes.memmove(output, data, len(data)); count._obj.value = len(data); return 1
    api = module.Windows.__new__(module.Windows)
    api.k = SimpleNamespace(GetFileInformationByHandleEx=query, SetFilePointerEx=lambda *_: 1, ReadFile=read)
    with pytest.raises(module.Refused): api.snapshot(module.Handle(api, 123))
    assert ('read' in calls) is (mismatch == 'content')


@pytest.mark.parametrize('failed', ['child', 'terminate', 'owner-close', 'pipe'])
def test_owned_cleanup_attempts_all_independent_steps_and_keeps_uncertainty(failed):
    calls = []
    def call(label):
        calls.append(label)
        if label == failed: raise OSError('private cleanup sentinel')
    attempt = module.Attempt.__new__(module.Attempt)
    attempt.closed = attempt.poisoned = False
    attempt.checkpoint, attempt.checkpoint_locked = None, False
    attempt.child = SimpleNamespace(stop_and_wait=lambda _: call('child'))
    attempt.owner = SimpleNamespace(terminate=lambda **_: call('terminate'), close=lambda: call('owner-close'))
    attempt.pipe = SimpleNamespace(close=lambda: call('pipe'))
    with pytest.raises(module.Refused, match='owned-cleanup-unconfirmed'): attempt.close()
    assert calls == ['child', 'terminate', 'owner-close', 'pipe']
    assert any(record is attempt for record in module._UNCONFIRMED)
    with pytest.raises(module.Refused): attempt.close()
    assert calls == ['child', 'terminate', 'owner-close', 'pipe']


def test_pipe_client_identity_is_compared_to_creation_handle_without_pid_adoption():
    calls = []
    def client(handle, output): output._obj.value = 222; calls.append('client'); return 1
    pipe = module.Pipe.__new__(module.Pipe)
    pipe.api = SimpleNamespace(check=lambda value: value, k=SimpleNamespace(
        GetProcessId=lambda handle: calls.append(('genuine-handle', handle)) or 111,
        GetNamedPipeClientProcessId=client))
    pipe.handle = module.Handle(pipe.api, 8)
    with pytest.raises(module.Refused): pipe.bind(SimpleNamespace(process_handle=9), float('inf'))
    assert calls == [('genuine-handle', 9), 'client']


@pytest.mark.parametrize('payload', [b'{"state":"held"}\n', b'{"state":"held"}\r\n'])
def test_nonblocking_pipe_receives_only_bounded_private_frames(payload):
    pending = bytearray(payload)
    calls = []
    def peek(handle, data, size, read, available, left): available._obj.value = len(pending); return 1
    def read(handle, output, size, received, overlapped):
        calls.append(size)
        chunk = bytes(pending[:size]); del pending[:size]
        ctypes.memmove(output, chunk, len(chunk)); received._obj.value = len(chunk); return 1
    pipe = module.Pipe.__new__(module.Pipe)
    pipe.api = SimpleNamespace(check=lambda value: value, k=SimpleNamespace(PeekNamedPipe=peek, ReadFile=read))
    pipe.handle, pipe.buffer, pipe.received = module.Handle(pipe.api, 8), bytearray(), 0
    assert pipe.receive(float('inf')) == {'state': 'held'}
    assert calls and max(calls) <= module.LIMIT + 1


def test_pipe_overflow_is_rejected_before_json_decoding():
    def peek(handle, data, size, read, available, left): available._obj.value = 10000; return 1
    def read(handle, output, size, received, overlapped):
        assert size == module.LIMIT + 1
        ctypes.memmove(output, b'x' * size, size); received._obj.value = size; return 1
    pipe = module.Pipe.__new__(module.Pipe)
    pipe.api = SimpleNamespace(check=lambda value: value, k=SimpleNamespace(PeekNamedPipe=peek, ReadFile=read))
    pipe.handle, pipe.buffer, pipe.received = module.Handle(pipe.api, 8), bytearray(), 0
    with pytest.raises(module.Refused): pipe.receive(float('inf'))


def successful_receipt():
    value = module.receipt()
    value.update(status='mechanism-observed', phase='complete', failure='none',
        cleanup='owned-handles-closed-fixture-retained', legacy_source_sha256=next(iter(module.SOURCE_HASHES)),
        observed=list(module.OBSERVATIONS), timestamp_equalities={name: dict.fromkeys(
            ('creation_equal', 'access_equal', 'write_equal', 'change_equal'), True) for name in module.TIME_STATES})
    return value


@pytest.mark.parametrize('mutation', ['raw', 'gate', 'count-bool', 'unknown-event', 'order', 'missing',
    'private-time', 'numeric-time', 'private-hash', 'cleanup', 'failure', 'creation-changed', 'write-changed'])
def test_public_receipt_cannot_publish_private_values_or_promote_incomplete_result(mutation):
    value = successful_receipt()
    if mutation == 'raw': value['path'] = 'private-authored-path'
    if mutation == 'gate': value['r19_complete'] = True
    if mutation == 'count-bool': value['candidate_data_writers'] = False
    if mutation == 'unknown-event': value['observed'][0] = 'private-unknown-event'
    if mutation == 'order': value['observed'][0:2] = reversed(value['observed'][0:2])
    if mutation == 'missing': value['observed'].pop()
    if mutation == 'private-time': value['timestamp_equalities']['arm']['change_equal'] = 'private-time'
    if mutation == 'numeric-time': value['timestamp_equalities']['arm']['change_equal'] = 1
    if mutation == 'private-hash': value['legacy_source_sha256'] = 'b' * 64
    if mutation == 'cleanup': value['cleanup'] = 'private-unverified-cleanup'
    if mutation == 'failure': value['failure'] = 'protocol-refused'
    if mutation == 'creation-changed': value['timestamp_equalities']['arm']['creation_equal'] = False
    if mutation == 'write-changed': value['timestamp_equalities']['arm']['write_equal'] = False
    with pytest.raises(module.Refused): module.public_receipt(value)


def test_public_receipt_copies_nested_booleans_and_keeps_all_acceptance_gates_closed():
    original = successful_receipt()
    result = module.public_receipt(original)
    original['timestamp_equalities']['arm']['change_equal'] = False
    assert result['timestamp_equalities']['arm']['change_equal'] is True
    assert result['candidate_data_writers'] == 0 and result['keeper_loss_acceptance'] is False
    assert result['r19_complete'] is result['rights_approval'] is result['production_allowed'] is False


@pytest.fixture
def authored(monkeypatch, tmp_path):
    """Behavior double: no Windows attribute/open/process call is executed."""
    monkeypatch.setattr(module.tempfile, 'gettempdir', lambda: str(tmp_path.resolve()))
    class API:
        def __init__(self):
            self.events, self.lease, self.armed, self.read_handles = [], False, False, []
        def ntfs(self, root): self.events.append('authored-filesystem-double')
        def image(self): return 'owned-python-placeholder'
        def open(self, path, access):
            assert access == module.RESTORE and access & 0x40000000 == 0
            handle = object(); self.read_handles.append(handle); self.events.append('restore-open'); return handle
        def snapshot(self, handle):
            assert handle in self.read_handles
            return snapshot(1 if self.armed else 128, [10, 20, 30, 41])
        def attributes(self, handle, original, armed):
            assert handle in self.read_handles and not self.lease and original == 128
            self.armed = armed; self.events.append('restore-clear')
        def close(self, handle): self.read_handles.remove(handle); self.events.append('restore-close')
    api = API()
    class Attempt:
        def __init__(self, *_): api.lease = True; self.closed = False; api.events.append('owned-lease-start')
        def exchange(self, value):
            if 'root' in value: return {'state': 'held', 'snapshot': snapshot()}
            phase = value['command']; api.armed = phase != 'live-clear'; api.events.append(phase)
            return {'state': phase, 'snapshot': snapshot(1 if api.armed else 128, [10, 20, 30, 41])}
        def close(self):
            if not self.closed:
                api.lease, self.closed = False, True; api.events.append('owned-lease-stop')
    def legacy(_api, root, source, expected, *, checkpoint_value=None):
        api.events.append(expected)
        if expected == 'open': assert not api.lease and not api.read_handles and not api.armed
        elif expected == 'readonly-refused': assert not api.lease and not api.read_handles and api.armed
        elif expected == 'sharing-refused': assert api.lease or api.read_handles
        else: pytest.fail('Unexpected authored transition.')
    monkeypatch.setattr(module, 'Windows', lambda: api)
    monkeypatch.setattr(module, 'Attempt', Attempt)
    monkeypatch.setattr(module, 'legacy', legacy)
    return api


def test_authored_state_sequence_never_releases_old_open_during_normal_clear_or_test_restore(authored, tmp_path):
    result = module.experiment()
    assert result['status'] == 'mechanism-observed' and tuple(result['observed']) == module.OBSERVATIONS
    assert not authored.lease and not authored.read_handles and not authored.armed
    assert authored.events.index('owned-lease-stop') < authored.events.index('readonly-refused')
    assert authored.events.index('restore-clear') < len(authored.events) - 1
    assert result['timestamp_equalities']['post-loss']['change_equal'] is False
    roots = list(tmp_path.glob('r19-lock-attribute-*'))
    assert len(roots) == 1 and (roots[0] / 'data/companion-operation.lock').read_bytes() == module.CONTENT
    assert 'private' not in json.dumps(result) and str(tmp_path) not in json.dumps(result)


def test_post_loss_refusal_mismatch_retains_readonly_and_never_clears_for_convenience(authored, monkeypatch, tmp_path):
    previous = module.legacy
    def refuse(api, root, source, expected, *, checkpoint_value=None):
        if expected == 'readonly-refused': raise module.Refused('legacy-outcome-differed')
        return previous(api, root, source, expected, checkpoint_value=checkpoint_value)
    monkeypatch.setattr(module, 'legacy', refuse)
    result = module.experiment()
    assert result['status'] == 'failed' and result['failure'] == 'legacy-outcome-differed'
    assert authored.armed and not authored.lease and not authored.read_handles
    assert 'restore-clear' not in authored.events
    assert len(list(tmp_path.glob('r19-lock-attribute-*'))) == 1


def test_unsupported_host_refuses_before_creating_a_fixture(monkeypatch):
    def unavailable(): raise module.Refused('unsupported-host')
    monkeypatch.setattr(module, 'Windows', unavailable)
    monkeypatch.setattr(module.tempfile, 'mkdtemp', lambda **_: pytest.fail('No fixture on unsupported host.'))
    result = module.experiment()
    assert result['status'] == 'failed' and result['failure'] == 'unsupported-host'
    assert not result['observed']


def test_nonlocal_or_non_ntfs_temp_refuses_before_any_fixture_write(monkeypatch):
    def refuse(_root): raise module.Refused('fixture-refused')
    monkeypatch.setattr(module, 'Windows', lambda: SimpleNamespace(ntfs=refuse))
    monkeypatch.setattr(module.tempfile, 'mkdtemp', lambda **_: pytest.fail('No unsupported-volume fixture write.'))
    result = module.experiment()
    assert result['status'] == 'failed' and result['failure'] == 'fixture-refused'


def test_fixture_marker_is_bounded_and_ancestor_link_refused_before_marker_read(tmp_path, monkeypatch):
    monkeypatch.setattr(module.tempfile, 'gettempdir', lambda: str(tmp_path.resolve()))
    root = tmp_path / 'r19-lock-attribute-authored'
    root.mkdir(); (root / 'data').mkdir()
    (root / 'data/companion-operation.lock').write_bytes(module.CONTENT)
    marker = root / module.MARKER
    marker.write_bytes(b'x' * (module.LIMIT + 1))
    with pytest.raises(module.Refused): module.fixture(root, 'a' * 32)
    outside = tmp_path / 'outside'; outside.mkdir()
    marker.unlink(); marker.symlink_to(outside / 'never-read')
    with pytest.raises(module.Refused): module.fixture(root, 'a' * 32)


def progress_attempt(frames=None):
    class Wire:
        def __init__(self):
            self.frames = list(frames if frames is not None else [
                *({'kind': 'checkpoint', 'stage': name} for name in module.SCRIPT_STEPS[1:-1]),
                {'state': 'open'}])
            self.deadlines = []
        def send(self, value, deadline): self.deadlines.append(deadline)
        def receive(self, deadline):
            self.deadlines.append(deadline)
            if not self.frames: raise module.Refused('protocol-refused')
            value = self.frames.pop(0)
            if isinstance(value, BaseException): raise value
            return value
        def finish(self, deadline):
            self.deadlines.append(deadline)
            if self.frames: raise module.Refused('protocol-refused')
    attempt = module.Attempt.__new__(module.Attempt)
    attempt.pipe, attempt.checkpoint, attempt.checkpoint_locked = Wire(), module.checkpoint(), False
    return attempt


def test_complete_progress_keeps_terminal_result_and_one_exchange_deadline(monkeypatch):
    monkeypatch.setattr(module.time, 'monotonic', lambda: 100.)
    attempt = progress_attempt()
    assert attempt.script_exchange({'owned': 'grant'}) == {'state': 'open'}
    assert attempt.checkpoint == {'parent_step': 'receive-result', 'script_step': 'operationresult', 'child_state': 'not-created'}
    assert set(attempt.pipe.deadlines) == {110.}


@pytest.mark.parametrize('mutation', ['duplicate', 'skip', 'unknown', 'private-key', 'wrong-order', 'early-result', 'truncated', 'unknown-result'])
def test_progress_rejects_bad_order_and_keeps_only_the_last_complete_checkpoint(mutation):
    attempt = progress_attempt()
    frames = attempt.pipe.frames
    boundary = next(i for i, frame in enumerate(frames) if frame.get('stage') == 'sourceopened')
    if mutation == 'duplicate': frames[boundary] = dict(frames[boundary-1])
    if mutation == 'skip': frames.pop(boundary)
    if mutation == 'unknown': frames[boundary] = {'kind': 'checkpoint', 'stage': 'private-unknown-stage'}
    if mutation == 'private-key': frames[boundary]['raw'] = 'private-path'
    if mutation == 'wrong-order': frames[boundary], frames[boundary+1] = frames[boundary+1], frames[boundary]
    if mutation == 'early-result': frames[boundary] = {'state': 'open'}
    if mutation == 'truncated': frames[boundary] = module.Refused('protocol-refused')
    if mutation == 'unknown-result': frames[-1] = {'state': 'private-unknown-result'}
    with pytest.raises(module.Refused): attempt.script_exchange({})
    assert attempt.checkpoint['script_step'] == ('operationentered' if mutation == 'unknown-result' else 'grantvalidated')
    assert attempt.checkpoint_locked and 'private-' not in json.dumps(attempt.checkpoint)


@pytest.mark.parametrize(('stages', 'tail', 'last'), [
    (['connected'], [], 'connected'),
    (['connected', 'grantread'], [], 'grantread'),
    (['connected', 'grantread', 'grantparsed'], [], 'grantparsed'),
    (['connected', 'grantparsed'], [], 'connected'),
    (['connected', 'grantread', 'grantread'], [], 'grantread'),
    (['connected', 'grantread', 'grantvalidated'], [], 'grantread'),
    (['connected', 'grantread'], [None], 'grantread'),
    (['connected', 'grantread'], [{'kind': 'checkpoint', 'stage': 'grantparsed', 'raw': 'private-grant'}], 'grantread'),
    (['connected', 'grantread', 'grantparsed'], [None], 'grantparsed'),
    (['connected', 'grantread', 'grantparsed'], [{'kind': 'checkpoint', 'stage': 'grantvalidated', 'raw': 'private-grant'}], 'grantparsed'),
])
def test_grant_return_checkpoints_never_imply_shape_validation_or_operation(stages, tail, last):
    attempt = progress_attempt([*({'kind': 'checkpoint', 'stage': name} for name in stages), *tail])
    with pytest.raises(module.Refused): attempt.script_exchange({'owned': 'grant'})
    assert attempt.checkpoint == {'parent_step': 'receive-script-progress',
        'script_step': last, 'child_state': 'not-created'}
    assert attempt.checkpoint_locked
    value = module.receipt(); value['baseline_checkpoint'] = attempt.checkpoint
    public = module.public_receipt(value)
    assert public['status'] == 'failed' and public['observed'] == []
    assert public['baseline_checkpoint']['script_step'] == last
    assert 'private-grant' not in json.dumps(public)


def test_changed_wire_does_not_relabel_historical_v2_receipts():
    value = module.receipt()
    value['schema'] = 'proxy-r19-legacy-lock-attribute-mechanism-v2'
    with pytest.raises(module.Refused): module.public_receipt(value)


def test_valid_terminal_cannot_hide_trailing_records_or_become_open_evidence():
    attempt = progress_attempt()
    attempt.pipe.frames.append({'kind': 'checkpoint', 'stage': 'connected'})
    with pytest.raises(module.Refused): attempt.script_exchange({})
    assert attempt.checkpoint['script_step'] == 'operationresult' and attempt.checkpoint_locked


def test_progress_deadline_is_not_extended_by_each_short_record(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    attempt = progress_attempt()
    receive = attempt.pipe.receive
    def slow(deadline):
        clock[0] += 3.
        if clock[0] >= deadline: raise module.Refused('protocol-refused')
        return receive(deadline)
    attempt.pipe.receive = slow
    with pytest.raises(module.Refused): attempt.script_exchange({})
    assert attempt.checkpoint['script_step'] == 'grantparsed' and clock[0] == 12.
    assert set(attempt.pipe.deadlines) == {10.}


def test_several_individually_small_frames_share_one_cumulative_receive_cap():
    pending = [bytearray(b'{"padding":"' + b'x' * 2500 + b'"}\n') for _ in range(2)]
    def peek(handle, data, size, read, available, left): available._obj.value = len(pending[0]); return 1
    def read(handle, output, size, received, overlapped):
        chunk = bytes(pending[0][:size]); del pending[0][:size]
        if not pending[0]: pending.pop(0)
        ctypes.memmove(output, chunk, len(chunk)); received._obj.value = len(chunk); return 1
    pipe = module.Pipe.__new__(module.Pipe)
    pipe.api = SimpleNamespace(check=lambda value: value, k=SimpleNamespace(PeekNamedPipe=peek, ReadFile=read))
    pipe.handle, pipe.buffer, pipe.received = module.Handle(pipe.api, 8), bytearray(), 0
    assert pipe.receive(float('inf')) == {'padding': 'x' * 2500}
    with pytest.raises(module.Refused): pipe.receive(float('inf'))
    assert pipe.received == module.LIMIT + 1


@pytest.mark.parametrize('state', ['buffered', 'queued', 'closed', 'other-error', 'deadline'])
def test_terminal_pipe_boundary_rejects_trailing_or_unconfirmed_completion(monkeypatch, state):
    clock = [0.]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(ctypes, 'get_last_error', lambda: 109 if state == 'closed' else 233, raising=False)
    def peek(handle, data, size, read, available, left):
        available._obj.value = 1 if state == 'queued' else 0
        return state not in {'closed', 'other-error'}
    pipe = module.Pipe.__new__(module.Pipe)
    pipe.api = SimpleNamespace(k=SimpleNamespace(PeekNamedPipe=peek))
    pipe.handle, pipe.buffer = module.Handle(pipe.api, 8), bytearray(b'extra' if state == 'buffered' else b'')
    if state == 'closed': pipe.finish(.03)
    else:
        with pytest.raises(module.Refused): pipe.finish(.03)
    assert clock[0] <= .03


@pytest.mark.parametrize('native,expected', [(0, 'signaled'), (258, 'not-signaled'), (0xffffffff, 'unavailable')])
def test_child_state_is_observed_from_genuine_handle_before_close_without_changing_cleanup(native, expected):
    calls = []
    attempt = module.Attempt.__new__(module.Attempt)
    attempt.checkpoint, attempt.checkpoint_locked = module.checkpoint(), False
    attempt.closed = attempt.poisoned = False
    attempt.child = SimpleNamespace(created=True, closed=False, process_handle=111,
        stop_and_wait=lambda _: calls.append('stop'))
    attempt.owner = SimpleNamespace(kernel=SimpleNamespace(WaitForSingleObject=lambda handle, ms: calls.append(('signal', handle, ms)) or native),
        terminate=lambda **_: calls.append('drain'), close=lambda: calls.append('owner-close'))
    attempt.pipe = SimpleNamespace(close=lambda: calls.append('pipe-close'))
    attempt.close(); attempt.close()
    assert calls == [('signal', 111, 0), 'stop', 'drain', 'owner-close', 'pipe-close']
    assert attempt.checkpoint['child_state'] == expected and attempt.closed


def test_checkpoint_failure_stage_survives_cleanup_and_query_failure_is_context_only():
    attempt = module.Attempt.__new__(module.Attempt)
    attempt.checkpoint = module.checkpoint(); attempt.checkpoint['parent_step'] = 'bind-client'
    attempt.checkpoint_locked = True; attempt.closed = attempt.poisoned = False
    def unavailable(*_): raise OSError('private query sentinel')
    attempt.child = SimpleNamespace(created=True, closed=False, process_handle=111, stop_and_wait=lambda _: None)
    attempt.owner = SimpleNamespace(kernel=SimpleNamespace(WaitForSingleObject=unavailable), terminate=lambda **_: None, close=lambda: None)
    attempt.pipe = SimpleNamespace(close=lambda: None)
    attempt.close()
    assert attempt.closed and attempt.checkpoint == {'parent_step': 'bind-client', 'script_step': 'not-started', 'child_state': 'unavailable'}


def test_no_signal_query_uses_an_already_closed_creation_record():
    attempt = module.Attempt.__new__(module.Attempt)
    attempt.checkpoint = module.checkpoint()
    attempt.child = SimpleNamespace(created=True, closed=True)
    attempt.owner = SimpleNamespace(kernel=SimpleNamespace(WaitForSingleObject=lambda *_: pytest.fail('No stale handle query.')))
    attempt.observe_child()
    assert attempt.checkpoint['child_state'] == 'unavailable'


@pytest.mark.parametrize('value', [None, {}, {'parent_step': 'private-path', 'script_step': 'not-started', 'child_state': 'not-created'},
    {'parent_step': 'not-started', 'script_step': 'not-started', 'child_state': 1},
    {'parent_step': 'not-started', 'script_step': 'not-started', 'child_state': 'not-created', 'pid': 123}])
def test_checkpoint_public_projection_has_exact_three_finite_keys(value):
    result = successful_receipt(); result['baseline_checkpoint'] = value
    with pytest.raises(module.Refused): module.public_receipt(result)


def test_diagnostic_child_unavailability_never_grants_or_revokes_native_acceptance():
    value = successful_receipt()
    value['baseline_checkpoint']['child_state'] = 'unavailable'
    assert module.public_receipt(value)['keeper_loss_acceptance'] is False
    assert module.public_receipt(value)['status'] == 'mechanism-observed'


@pytest.mark.parametrize('failure,expected', [('pipe', 'create-pipe'), ('create', 'create-owned-process'),
    ('resume', 'resume-owned-process'), ('bind', 'bind-client')])
def test_baseline_start_boundaries_are_recorded_before_failure_and_survive_cleanup(monkeypatch, tmp_path, failure, expected):
    calls = []
    def refuse(): raise module.Refused('protocol-refused')
    class Child:
        created, closed, process_handle = True, False, 111
        def resume_once(self):
            calls.append('resume')
            if failure == 'resume': refuse()
        def stop_and_wait(self, deadline): calls.append('stop')
    class Owner:
        created_children = ()
        kernel = SimpleNamespace(WaitForSingleObject=lambda *_: 0)
        def create_suspended(self, *_, **__):
            calls.append('create')
            if failure == 'create': refuse()
            return Child()
        def terminate(self, **_): calls.append('drain')
        def close(self): calls.append('owner-close')
    class Wire:
        name = 'owned-fixture-pipe'
        def __init__(self, api):
            if failure == 'pipe': refuse()
        def bind(self, child, deadline):
            calls.append('bind')
            if failure == 'bind': refuse()
        def close(self): calls.append('pipe-close')
    monkeypatch.setattr(module, 'Pipe', Wire)
    monkeypatch.setattr(module, 'process_module', lambda: SimpleNamespace(WindowsPreparationProcess=Owner))
    value = module.checkpoint()
    with pytest.raises(module.Refused):
        module.Attempt(SimpleNamespace(), lambda name: ['owned-fixture'], tmp_path, checkpoint_value=value)
    assert value['parent_step'] == expected and value['script_step'] == 'not-started'
    assert value['child_state'] == ('signaled' if failure in {'resume', 'bind'} else 'not-created')
    assert 'private' not in json.dumps(value)
