"""Authored SQLite/ordering fixtures. Frozen Win32 process proof is separate."""
from contextlib import closing, contextmanager
import io
import gc
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import weakref
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import httpx

from backend import runtime_data_copy_probe as probe
from backend import runtime_probe
from backend.bundle_host import HostProbeError
from backend.lexirise import LexiriseService
from backend.accounts import AccountStore
from backend.lexirise_settings import account_settings
from backend.languages import translation_language
from backend.reading import LexiriseReadingService
from backend.runtime_bundle import RuntimeLayout


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    app, private = tmp_path/'app', tmp_path/'private'
    app.mkdir(); (app/'ProxyTranscriptRuntime.exe').write_bytes(b'authored-placeholder-not-a-native-image')
    layout = RuntimeLayout(mode='bundle', profile='runtime-experiment', application_root=app,
        resource_root=app/'_internal', executable=app/'ProxyTranscriptRuntime.exe', settings_root=private,
        data_root=private/'data-v1', cache_root=private/'cache-v1', work_root=private/'cache-v1/work',
        tool_root=private/'tools-v1', state_root=private/'host-v1', default_export_root=private/'exports',
        source_commit='a'*40, build_id='authored-data-copy-fixture', children=('frontend',))
    monkeypatch.setattr(probe.tempfile, 'gettempdir', lambda: str(tmp_path))
    calls = []
    class FakeHost:
        """Local behavior double; it does not establish Win32 ownership or C2."""
        def __init__(self, layout):
            self.layout = layout
            self.registered = {}
            self.closed = self.recovery_required = False
            self.tree = object()
        def start_registered(self, *, detached_console, wal_probe=False, grammar_probe=False):
            assert detached_console is True
            assert type(wal_probe) is bool
            assert type(grammar_probe) is bool and not (wal_probe and grammar_probe)
            self.wal_probe = wal_probe
            self.grammar_probe = grammar_probe
            self.readers = {}
            calls.append(('create', self))
            self.registered = {role: SimpleNamespace(created=True, resumed=False, exited=False, closed=False)
                               for role in ('frontend', 'api')}
            def initialize():
                connections = []
                try:
                    probe._SetupStore(self.layout.data_root/'transcript-v2.db', connections)
                finally:
                    for connection in connections: connection.close()
                self.exports = LexiriseService(self.layout.data_root/'lexirise')
                self.reading = LexiriseReadingService(self.layout.data_root/'lexirise', self.exports)
            if grammar_probe:
                self.grammar_policy = runtime_probe._AuthoredGrammarService(self.layout, LexiriseService)
                self.exports = self.grammar_policy.create(self.layout.data_root/'lexirise',
                    accounts=AccountStore(self.layout.work_root/'absent-test-account.dpapi'))
                self.reading = LexiriseReadingService(self.layout.data_root/'lexirise', self.exports)
            elif wal_probe:
                with runtime_probe._authored_wal_connections(self.layout) as policy:
                    initialize()
                    policy.require_stores()
                self.wal_policy = policy
            else:
                # Keep the original control's store initialization unchanged.
                self.exports = LexiriseService(self.layout.data_root/'lexirise')
                self.reading = LexiriseReadingService(self.layout.data_root/'lexirise', self.exports)
        def resume_registered(self):
            calls.append(('resume', self))
            for child in self.registered.values(): child.resumed = True
        def wait_services(self): calls.append(('ready', self))
        @contextmanager
        def _registered_listener_scope(self):
            calls.append(('identity-before', self))
            yield True
            calls.append(('identity-after', self))
        def quiesce_registered(self):
            calls.append(('strict-c2-double', self))
            self.reading.quiesce(1)
            for reader in self.readers.values(): reader.quiesce(1)
        def reader(self, line):
            session = self.exports.pin(line.source_language)
            if not hasattr(session, '_settings_payload'): account_settings(session)
            target = translation_language(session._settings_payload, line.source_language)
            key = (session._scope(), line.source_language, target, session._settings_scope)
            if key not in self.readers:
                self.readers[key] = LexiriseReadingService(self.layout.data_root/'lexirise', session,
                    source_language=line.source_language, translation_language=target)
            return self.readers[key]
        def close(self):
            calls.append(('retained-signal-double', self))
            for child in self.registered.values(): child.exited = child.closed = True
            self.closed, self.tree = True, None
    monkeypatch.setattr(probe, 'FrozenProbeHost', FakeHost)
    instances = []
    def make(case=probe.CASE):
        phases = probe.GRAMMAR_PHASES if case == probe.GRAMMAR_CASE else probe.WAL_PHASES if case == probe.WAL_CASE else probe.RESUME_PHASES if case == probe.RESUME_CASE else probe.PHASES
        stream = io.StringIO(''.join('observed '+phase+'\n' for phase in phases[:-1]))
        value = probe._DataCopyProbe(layout, stream, case=case)
        instances.append(value)
        return value
    def response(request, timeout):
        # Use actual store mutation/row parsing, but this is an HTTP double.
        value = instances[-1]
        if value.case == probe.WAL_CASE:
            with patch.object(sqlite3, 'connect', value.adapter.host.wal_policy.connect):
                return actual_response(value, request)
        return actual_response(value, request)
    def actual_response(value, request):
        connections = []
        try:
            store = probe._SetupStore(value.adapter.layout.data_root/'transcript-v2.db', connections)
            if isinstance(request, probe.Request):
                if request.get_method() == 'PATCH':
                    assert request.data == b'{"favorite":true}' and request.full_url.endswith('/1/favorite')
                    result = store.set_favorite(1, True).model_dump(mode='json')
                    calls.append(('favorite-sql', value.adapter.host))
                else:
                    assert value.case == probe.GRAMMAR_CASE
                    assert request.get_header('X-proxy-transcript-account') == 'legacy'
                    line = store.get(1)
                    reader = value.adapter.host.reader(line)
                    if request.get_method() == 'GET':
                        assert request.full_url.endswith('/1/reading')
                        result = reader.analyze(line.source_text)
                    else:
                        assert request.get_method() == 'POST' and request.full_url.endswith('/1/reading/grammar')
                        assert request.get_header('X-proxy-transcript') == 'lexirise'
                        body = json.loads(request.data)
                        assert set(body) == {'slug', 'known'} and body['known'] is True
                        result = reader.set_grammar_known(line.source_text, body['slug'], body['known'])
                        calls.append(('grammar-sql' if result else 'grammar-404', value.adapter.host))
                        if result is None:
                            raise probe.HTTPError(request.full_url, 404, 'authored missing grammar', {},
                                io.BytesIO(b'{"detail":"Grammar rule not found in this line"}'))
            else:
                assert request == 'http://127.0.0.1:8766/api/lines?game=hito'
                result = [row.model_dump(mode='json') for row in store.list()]
            data = json.dumps(result).encode()
        finally:
            for connection in connections: connection.close()
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self, limit): return data[:limit]
        return Response()
    monkeypatch.setattr(probe, 'urlopen', response)
    yield SimpleNamespace(make=make, calls=calls, layout=layout, hosts=FakeHost)
    # All children here are explicit local doubles. Only test teardown may
    # replace stop to dispose its own fixture leases after asserting retention.
    for value in instances:
        if value.coordinator and value.coordinator._opened:
            monkeypatch.setattr(value.adapter, 'stop', lambda: probe.STOPPED)
            value.adapter.active = value.adapter.setup_open = value.adapter.poisoned = False
            value.coordinator.close(value.coordinator.owner)


def test_actual_sql_copy_and_chinese_context_with_fresh_cohort_order(fixture, capsys):
    value = fixture.make()
    assert value.run() == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert tuple(event['phase'] for event in events) == probe.PHASES
    assert events[-1]['generation'] == 2 and events[-1]['writers_signaled'] == 4
    assert events[-1]['old_barrier_refused'] is True
    assert events[-1]['source_bytes'] == 'preserved-before-resume'
    assert events[-1]['source_logical'] == 'passed'
    assert value.adapter.cohorts[0] is not value.adapter.cohorts[1]
    assert value.coordinator.pointer_path.read_bytes() == value.pointer
    assert not value.coordinator._leases_held() and value.released
    calls = [name for name, _host in fixture.calls]
    assert calls.index('favorite-sql') < calls.index('strict-c2-double') < calls.index('retained-signal-double')
    assert calls.count('create') == calls.count('resume') == calls.count('retained-signal-double') == 2
    # Metadata does not disclose authored rows, transient roots, UUIDs or PIDs.
    serialized = json.dumps(events, ensure_ascii=False)
    assert '这是' not in serialized and str(value.source.path) not in serialized
    assert value.source.fixture_id not in serialized and 'job_members' not in serialized
    assert all(event['r19_complete'] is False and event['target_activation'] is False for event in events)
    assert all(event['schema'] == probe.SCHEMA and event['case'] == probe.CASE for event in events)
    assert not ({'scope', 'copy_attempts', 'authored_interruptions', 'partial_revalidations'} & set(events[-1]))


def test_populated_grammar_uses_real_setter_copy_and_fresh_source_readback(fixture, monkeypatch, capsys):
    value = fixture.make(probe.GRAMMAR_CASE)
    choices = []
    verify = probe._verify_store
    def semantic(connection, name, expected, **options):
        verify(connection, name, expected, **options)
        if options.get('grammar_probe') and name == 'data/lexirise/reading-cache-v2.db':
            choices.append([tuple(row) for row in connection.execute('SELECT slug,proficiency FROM grammar_choices')])
    monkeypatch.setattr(probe, '_verify_store', semantic)
    assert value.run() == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert tuple(event['phase'] for event in events) == probe.GRAMMAR_PHASES
    assert choices == [[(runtime_probe.GRAMMAR_CHOICE_KEY, 4)]]
    assert all(event['schema'] == probe.GRAMMAR_SCHEMA and event['case'] == probe.GRAMMAR_CASE for event in events)
    written = next(event for event in events if event['phase'] == 'grammar-written')
    assert written['grammar_baseline'] == 'zero-without-local-override' and written['unknown_grammar_rule'] == 'rejected-404'
    assert written['grammar_written'] == 'four-with-local-override' and written['grammar_snapshot'] == 'not-run'
    assert written['writers_signaled'] == 0 and written['grammar_override_rows'] == 0
    final = events[-1]
    assert final['grammar_snapshot'] == 'one-scoped-choice-four' and final['grammar_override_rows'] == 1
    assert final['grammar_restarted'] == 'four-with-local-override' and final['writers_signaled'] == 4
    assert final['generation'] == 2 and value.copy_attempts == 1 and value.released
    assert final['source_bytes'] == 'preserved-before-resume' and final['source_logical'] == 'passed'
    assert value.coordinator.pointer_path.read_bytes() == value.pointer and not value.verification_ownership
    assert all(host.grammar_probe and not host.wal_probe for host in value.adapter.cohorts)
    calls = [name for name, _ in fixture.calls]
    assert calls.count('grammar-sql') == calls.count('grammar-404') == 1
    assert calls.index('grammar-sql') < calls.index('strict-c2-double') < calls.index('retained-signal-double')
    assert all(0 < host.grammar_policy.calls <= 16 for host in value.adapter.cohorts)
    text = json.dumps(events, ensure_ascii=False)
    assert all(private not in text for private in (runtime_probe.GRAMMAR_KEY, runtime_probe.GRAMMAR_CHOICE_KEY,
        runtime_probe.GRAMMAR_SLUG, probe.GRAMMAR_TEXT, str(value.source.path)))
    assert not ({'sqlite_policy','transcript_wal_bytes','copy_resumed'} & set(final))
    assert final['r19_complete'] is False and final['target_activation'] is False and final['production_activation'] is False


def _grammar_service(value):
    layout = value.adapter.layout
    policy = runtime_probe._AuthoredGrammarService(layout, LexiriseService)
    accounts = AccountStore(layout.work_root/'absent-test-account.dpapi')
    service = policy.create(layout.data_root/'lexirise', accounts=accounts)
    return policy, service, accounts


def test_grammar_constructor_fixture_avoids_account_environment_and_dpapi_fallbacks(fixture, monkeypatch):
    from backend import lexirise
    value = fixture.make(); value.prepare()
    def unavailable(*_a, **_k): pytest.fail('A real credential fallback must never be reached.')
    monkeypatch.setattr(AccountStore, 'active_key', unavailable)
    monkeypatch.setattr(lexirise, '_protect', unavailable)
    environment = lexirise.os.environ.get
    def forbidden(name, *args):
        if name in {'LEXIRISE_API_KEY','LOCALAPPDATA'}: unavailable()
        return environment(name, *args)
    monkeypatch.setattr(lexirise.os.environ, 'get', forbidden)
    policy, service, accounts = _grammar_service(value)
    assert type(service) is LexiriseService and service._key() == runtime_probe.GRAMMAR_KEY
    assert not accounts.path.exists()
    session = service.pin('zh')
    settings = account_settings(session)
    assert translation_language(settings, 'zh') == 'en'
    reader = LexiriseReadingService(value.adapter.layout.data_root/'lexirise', session)
    try:
        assert reader.set_grammar_known(probe.GRAMMAR_TEXT, runtime_probe.GRAMMAR_SLUG, True) == {
            'slug': runtime_probe.GRAMMAR_SLUG, 'proficiency': 4, 'localOverride': True}
        assert reader.analyze(probe.GRAMMAR_TEXT)['grammar'][0]['localOverride'] is True
    finally: reader.quiesce(1)
    assert policy.calls == 2  # Settings GET and analysis POST; no remote mutation.


def test_grammar_existing_account_fixture_is_refused_before_any_protected_read(fixture,monkeypatch):
    value = fixture.make(); value.prepare()
    layout = value.adapter.layout
    accounts = AccountStore(layout.work_root/'absent-test-account.dpapi')
    accounts.path.parent.mkdir(parents=True)
    accounts.path.write_bytes(b'authored placeholder, not protected user data')
    policy = runtime_probe._AuthoredGrammarService(layout,LexiriseService)
    opened = Path.open
    def refuse(path,*args,**options):
        assert path != accounts.path, 'Existing account bytes must remain unread.'
        return opened(path,*args,**options)
    monkeypatch.setattr(Path,'open',refuse)
    with pytest.raises(runtime_probe.RuntimeBundleError,match='fixture must be absent'):
        policy.create(layout.data_root/'lexirise',accounts=accounts)
    assert not policy.constructed


@pytest.mark.parametrize('fault', ['key','transport','foreign','relative','uri','positional','account-path'])
def test_grammar_factory_refuses_conflicting_or_foreign_inputs_before_constructor(fixture, monkeypatch, fault):
    value = fixture.make(); value.prepare()
    layout = value.adapter.layout
    def constructor(*_a, **_k): pytest.fail('Unselected service must not be constructed.')
    policy = runtime_probe._AuthoredGrammarService(layout, constructor)
    directory, args = layout.data_root/'lexirise', ()
    options = {'accounts': AccountStore(layout.work_root/'absent-test-account.dpapi')}
    if fault == 'key': options['api_key'] = runtime_probe.GRAMMAR_KEY
    if fault == 'transport': options['transport'] = policy.transport
    if fault == 'foreign': directory = value.fixture/'outside-lexirise'
    if fault == 'relative': directory = 'lexirise'
    if fault == 'uri': directory = directory.as_uri()
    if fault == 'positional': args = ('unexpected',)
    if fault == 'account-path': options['accounts'] = AccountStore(value.fixture/'outside.dpapi')
    monkeypatch.setattr(policy, 'guard', lambda *_a, **_k: pytest.fail('Foreign selection cannot inspect metadata.'))
    with pytest.raises(runtime_probe.RuntimeBundleError): policy.create(directory, *args, **options)
    assert not policy.constructed


@pytest.mark.parametrize('method,path,payload', [
    ('PATCH','/v1/settings',{}), ('POST','/v1/me',{}), ('GET','/v1/decks',None),
    ('POST','/v1/dictionary/lookup',{'text':'这'}),
    ('POST','/v1/analyze/text',{'text':'other','language':'zh','fast':False}),
    ('POST','/v1/analyze/text',{'text':probe.GRAMMAR_TEXT,'language':'en','fast':False}),
    ('POST','/v1/analyze/text',{'text':probe.GRAMMAR_TEXT,'language':'zh','fast':0})])
def test_grammar_transport_has_no_remote_success_fallback(fixture, method, path, payload):
    value = fixture.make(); value.prepare()
    policy, _service, _accounts = _grammar_service(value)
    request = httpx.Request(method, 'https://api.lexirise.app'+path, json=payload,
                            headers={'Authorization': 'Bearer '+runtime_probe.GRAMMAR_KEY})
    with pytest.raises(runtime_probe.RuntimeBundleError): policy.reply(request)


def test_grammar_transport_identity_duplicates_and_bound_are_explicit(fixture):
    value = fixture.make(); value.prepare()
    policy, _service, _accounts = _grammar_service(value)
    for url, key in [('https://foreign.example/v1/settings',runtime_probe.GRAMMAR_KEY),
                     ('https://api.lexirise.app/v1/settings?other=1',runtime_probe.GRAMMAR_KEY),
                     ('https://api.lexirise.app/v1/settings','other-fixture')]:
        with pytest.raises(runtime_probe.RuntimeBundleError):
            policy.reply(httpx.Request('GET',url,headers={'Authorization':'Bearer '+key}))
    headers={'Authorization':'Bearer '+runtime_probe.GRAMMAR_KEY}
    with pytest.raises(runtime_probe.RuntimeBundleError):
        policy.reply(httpx.Request('POST','https://api.lexirise.app/v1/analyze/text',headers=headers,
            content=b'{"text":"a","text":"b","language":"zh","fast":false}'))
    request = httpx.Request('GET','https://api.lexirise.app/v1/settings',headers=headers)
    for _ in range(12): assert policy.reply(request).status_code == 200
    with pytest.raises(runtime_probe.RuntimeBundleError, match='transport bound'): policy.reply(request)


def test_grammar_scope_and_actual_zero_choice_cannot_pass_copy_semantics(fixture):
    value = fixture.make(); value.prepare()
    policy, service, _accounts = _grammar_service(value)
    directory = value.adapter.layout.data_root/'lexirise'
    reader = LexiriseReadingService(directory, service)
    try:
        reader.set_grammar_known(probe.GRAMMAR_TEXT, runtime_probe.GRAMMAR_SLUG, False)
    finally: reader.quiesce(1)
    copy = value.target.path/'private-reading.db'; shutil.copy2(reader.path, copy)
    with closing(sqlite3.connect(copy.as_uri()+'?mode=ro',uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        with pytest.raises(probe.DataCopyFailure, match='grammar-choice-unconfirmed'):
            probe._verify_store(connection,'data/lexirise/reading-cache-v2.db',[],grammar_probe=True)
    selected = LexiriseReadingService(directory, service)
    try: selected.set_grammar_known(probe.GRAMMAR_TEXT, runtime_probe.GRAMMAR_SLUG, True)
    finally: selected.quiesce(1)
    other = LexiriseService(directory, api_key='other-fixture-not-a-credential',
        transport=httpx.MockTransport(lambda _request: httpx.Response(200,json={
            'occurrences':[{'charStart':0,'charEnd':1,'word':'这','isWordLike':False}],
            'grammar':[{'slug':runtime_probe.GRAMMAR_SLUG,'indices':[0]}],
            'grammarStates':{runtime_probe.GRAMMAR_SLUG:0}})))
    scoped = LexiriseReadingService(directory, other)
    try:
        rule = scoped.analyze(probe.GRAMMAR_TEXT)['grammar'][0]
        assert rule['proficiency'] == 0 and rule['localOverride'] is False
    finally: scoped.quiesce(1)


@pytest.mark.parametrize('fault', ['success','wrong-status','wrong-detail'])
def test_grammar_negative_http_must_be_the_fixed_owned_404(fixture, monkeypatch, fault):
    value = fixture.make(probe.GRAMMAR_CASE)
    urlopen = probe.urlopen
    def request(current, **options):
        if isinstance(current, probe.Request) and current.data and runtime_probe.GRAMMAR_ABSENT_SLUG.encode() in current.data:
            if fault == 'success':
                class Response:
                    status = 200
                    def __enter__(self): return self
                    def __exit__(self,*_): pass
                    def read(self,_): return b'{}'
                return Response()
            raise probe.HTTPError(current.full_url, 403 if fault == 'wrong-status' else 404,
                'authored different response', {}, io.BytesIO(b'{"detail":"different fixture"}'))
        return urlopen(current, **options)
    monkeypatch.setattr(probe,'urlopen',request)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    with pytest.raises(HeldRecovery): value.run()
    assert not value.grammar_written and value.copy_attempts == 0


@pytest.mark.parametrize('stage', ['copy-progress','copy-verified'])
@pytest.mark.parametrize('mutation', ['source','generation','barrier'])
def test_grammar_case_rechecks_trusted_authority_before_copy_or_fresh_cohort(fixture, monkeypatch, stage, mutation):
    value = fixture.make(probe.GRAMMAR_CASE)
    observe = value.observe
    def changed(phase):
        observe(phase)
        if phase != stage: return
        if mutation == 'source': (value.source.path/'data/authored-payload.bin').write_bytes(b'changed authored source')
        elif mutation == 'generation': value.adapter.generation += 1
        else: value.coordinator._barrier = None
    monkeypatch.setattr(value,'observe',changed)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.grammar_written and len(value.adapter.cohorts) == 1 and not value.grammar_restarted


@pytest.mark.parametrize('mutation', ['payload','same-size-payload','payload-read','owner','current',
                                    'owned','generation','barrier','lease-replaced','lease-unheld'])
def test_grammar_written_ack_pins_fixture_bytes_and_live_coordinator_identity(fixture,monkeypatch,mutation):
    value = fixture.make(probe.GRAMMAR_CASE)
    observe = value.observe
    retained = []
    original = {}
    payload_open = Path.open
    def checkpoint(phase):
        observe(phase)
        if phase != 'grammar-written': return
        coordinator = value.coordinator
        original.update(owner=coordinator._owner,current=coordinator.current,owned=coordinator._owned,
            barrier=coordinator._barrier,legacy=coordinator._legacy_lease,target=coordinator._target_lease)
        retained.extend((coordinator._legacy_lease,coordinator._target_lease))
        assert coordinator._barrier is None and value.grammar_ack_state['barrier'] is None
        payload = value.source.path/'data/authored-payload.bin'
        if mutation == 'payload': payload.write_bytes(b'changed after grammar ACK')
        elif mutation == 'same-size-payload': payload.write_bytes(b'X'*len(probe.AUTHORED_PAYLOAD))
        elif mutation == 'payload-read':
            def unavailable(path,*args,**options):
                if path == payload: raise OSError('authored immutable fixture read unavailable')
                return payload_open(path,*args,**options)
            monkeypatch.setattr(Path,'open',unavailable)
        elif mutation == 'owner': coordinator._owner = object()
        elif mutation == 'current': coordinator.current = object()
        elif mutation == 'owned': coordinator._owned = []
        elif mutation == 'generation': value.adapter.generation += 1
        elif mutation == 'barrier': coordinator._barrier = object()
        else:
            coordinator._legacy_lease = SimpleNamespace(held=mutation=='lease-replaced')
    monkeypatch.setattr(value,'observe',checkpoint)
    def hold():
        assert value.adapter.poisoned and not value.released and not value.release_attempted
        assert len(retained) == 2 and all(lease.held for lease in retained)
        assert value.grammar_ack_state['leases'] == tuple(retained)
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    try:
        with pytest.raises(HeldRecovery): value.run()
        assert value.copy_attempts == value.adapter.drains == 0 and len(value.adapter.cohorts) == 1
        assert not value.grammar_restarted
    finally:
        monkeypatch.setattr(Path,'open',payload_open)
        if original:
            coordinator = value.coordinator
            coordinator._owner,coordinator.current,coordinator._owned = original['owner'],original['current'],original['owned']
            coordinator._barrier = original['barrier']
            coordinator._legacy_lease,coordinator._target_lease = original['legacy'],original['target']


@pytest.mark.parametrize('mutation', ['payload','owner','lease'])
def test_grammar_c2_window_cannot_learn_changed_fixture_or_owner_as_its_first_baseline(fixture,monkeypatch,mutation):
    value = fixture.make(probe.GRAMMAR_CASE)
    observe = value.observe
    original = {}
    def checkpoint(phase):
        observe(phase)
        if phase != 'strict-drain-complete': return
        coordinator = value.coordinator
        original.update(owner=coordinator._owner,legacy=coordinator._legacy_lease,target=coordinator._target_lease)
        if mutation == 'payload': (value.source.path/'data/authored-payload.bin').write_bytes(b'changed during actual drain')
        elif mutation == 'owner': coordinator._owner = object()
        else: coordinator._legacy_lease = SimpleNamespace(held=True)
    monkeypatch.setattr(value,'observe',checkpoint)
    monkeypatch.setattr(probe.migration,'_source_inventory',lambda *_:pytest.fail('Unconfirmed state must not become a source baseline.'))
    def hold():
        assert value.adapter.poisoned and not value.released and not value.release_attempted
        assert original['legacy'].held and original['target'].held
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    try:
        with pytest.raises(HeldRecovery): value.run()
        assert value.copy_attempts == 0 and len(value.adapter.cohorts) == 1
    finally:
        if original:
            value.coordinator._owner = original['owner']
            value.coordinator._legacy_lease,value.coordinator._target_lease = original['legacy'],original['target']


@pytest.mark.parametrize('stage', ['strict-drain-complete','writers-signaled'])
def test_grammar_quiesce_ack_rejects_changed_predrain_barrier_before_stop_proof(fixture,monkeypatch,stage):
    value = fixture.make(probe.GRAMMAR_CASE)
    observe = value.observe
    barrier = object()
    def changed(phase):
        observe(phase)
        if phase == stage: value.coordinator._barrier = barrier
    monkeypatch.setattr(value,'observe',changed)
    monkeypatch.setattr(probe.migration,'_source_inventory',lambda *_:pytest.fail('Changed pre-drain frame cannot reach inventory.'))
    def hold():
        assert value.adapter.poisoned and not value.released and not value.release_attempted
        assert value.coordinator._barrier is barrier and value.coordinator._leases_held()
        assert value.grammar_ack_state['leases'] == (value.coordinator._legacy_lease,value.coordinator._target_lease)
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.copy_attempts == 0 and len(value.adapter.cohorts) == 1 and not value.grammar_restarted
    signaled = stage == 'writers-signaled'
    assert value.adapter.host.closed is signaled and value.adapter.active is not signaled
    assert all(child.exited is signaled for child in value.adapter.host.registered.values())


def test_grammar_fixed_quiesce_checks_accept_signaled_inactive_source_without_affecting_final_drain(fixture,monkeypatch):
    value = fixture.make(probe.GRAMMAR_CASE)
    check = value._grammar_stop_checkpoint
    observed = []
    def checkpoint(phase):
        observed.append((phase,value.adapter.generation,value.adapter.active,value.coordinator._barrier))
        check(phase)
    monkeypatch.setattr(value,'_grammar_stop_checkpoint',checkpoint)
    assert value.run() == 0
    assert observed == [('strict-drain-complete',1,True,None),('writers-signaled',1,False,None)]
    assert value.adapter.generation == value.adapter.drains == 2 and value.released


def test_grammar_immutable_payload_link_refuses_before_outside_content(fixture,monkeypatch):
    value = fixture.make(probe.GRAMMAR_CASE)
    observe = value.observe
    opened = Path.open
    touched = []
    def checkpoint(phase):
        observe(phase)
        if phase != 'grammar-written': return
        payload = value.source.path/'data/authored-payload.bin'
        outside = value.fixture/'outside-authored.bin';outside.write_bytes(probe.AUTHORED_PAYLOAD)
        payload.unlink();payload.symlink_to(outside)
        def forbidden(path,*args,**options):
            if path in {payload,outside}:
                touched.append(True);raise AssertionError('Linked immutable fixture content must remain unobserved.')
            return opened(path,*args,**options)
        monkeypatch.setattr(Path,'open',forbidden)
    monkeypatch.setattr(value,'observe',checkpoint)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    try:
        with pytest.raises(HeldRecovery): value.run()
        assert not touched and value.copy_attempts == 0
    finally: monkeypatch.setattr(Path,'open',opened)


def test_grammar_semantic_close_failure_retains_its_exact_connection_and_root(fixture, monkeypatch):
    value = fixture.make(probe.GRAMMAR_CASE)
    connect = sqlite3.connect
    references, closes = [], []
    class Unclosed(sqlite3.Connection):
        def close(self):
            closes.append(weakref.ref(self))
            raise OSError('private grammar verification close failure')
    def verification(database,*args,**options):
        if options.get('uri') and '/authored-wal-semantic-' in str(database).replace('\\','/'):
            connection = connect(database,*args,factory=Unclosed,**options)
            references.append(weakref.ref(connection)); return connection
        return connect(database,*args,**options)
    monkeypatch.setattr(sqlite3,'connect',verification)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        assert len(value.verification_ownership) == 1
        assert value.verification_ownership[0]['connection'] is references[0]()
        assert value.verification_ownership[0]['root'].is_dir()
        raise HeldRecovery()
    monkeypatch.setattr(probe,'hold_keeper_recovery',hold)
    try:
        with pytest.raises(HeldRecovery): value.run()
        assert len(closes) == 1 and not value.grammar_snapshot and len(value.adapter.cohorts) == 1
    finally:
        for reference in references:
            if reference() is not None: sqlite3.Connection.close(reference())
        for record in value.verification_ownership: shutil.rmtree(record['root'])


def test_grammar_api_policy_is_installed_before_real_service_construction(fixture, monkeypatch):
    value = fixture.make(); value.prepare()
    layout = value.adapter.layout
    monkeypatch.delitem(runtime_probe.sys.modules,'backend.api',raising=False)
    created = []
    class Runtime:
        def __init__(self):
            accounts = service.AccountStore()
            actual = service.LexiriseService(layout.data_root/'lexirise',accounts=accounts)
            assert type(actual) is LexiriseService and actual._api_key == runtime_probe.GRAMMAR_KEY
            reader = LexiriseReadingService(layout.data_root/'lexirise',actual)
            try: probe._DataCopyProbe._check_grammar(reader.analyze(probe.GRAMMAR_TEXT),known=False)
            finally: reader.quiesce(1)
            created.append(actual)
        def start_updates(self): pass
    service = SimpleNamespace(Runtime=Runtime,LexiriseService=LexiriseService,AccountStore=AccountStore,
        CaptureService=SimpleNamespace(warmup=lambda _:None),app=object())
    module = runtime_probe.importlib.import_module
    monkeypatch.setattr(runtime_probe.importlib,'import_module',lambda name,*args: service if name=='backend.api' else module(name,*args))
    monkeypatch.setitem(runtime_probe.sys.modules,'uvicorn',SimpleNamespace(run=lambda *_a,**_k: Runtime()))
    monkeypatch.setattr(runtime_probe,'_authored_wal_connections',lambda *_:pytest.fail('Grammar must not enable WAL policy.'))
    assert runtime_probe.api(layout,grammar_probe=True) == 0
    assert len(created) == 1 and service.LexiriseService is LexiriseService and service.AccountStore is AccountStore
    monkeypatch.setitem(runtime_probe.sys.modules,'backend.api',object())
    with pytest.raises(runtime_probe.RuntimeBundleError,match='import was not isolated'):
        runtime_probe.api(layout,grammar_probe=True)
    for options in ({'grammar_probe':1},{'grammar_probe':None},{'grammar_probe':True,'wal_probe':True}):
        with pytest.raises(runtime_probe.RuntimeBundleError,match='fixed authored API policy'):
            runtime_probe.api(layout,**options)


def test_actual_closed_connections_leave_wal_dependent_favorite_for_plain_copy(fixture, monkeypatch, capsys):
    value = fixture.make(probe.WAL_CASE)
    observed = []
    main_only = probe.verify_main_only_transcript
    verify = probe.verify_authored_snapshot
    sqlite_connect = sqlite3.connect
    def no_source_inspection(database, *args, **options):
        if value.adapter is not None and not value.adapter.active and not value.adapter.setup_open:
            assert str(value.source.path) not in str(database), 'Stopped original source must never be SQLite-opened.'
        return sqlite_connect(database, *args, **options)
    monkeypatch.setattr(sqlite3, 'connect', no_source_inspection)
    def baseline(source, target, expected, retained):
        assert not value.adapter.active and value.coordinator._leases_held()
        assert all(child.exited for child in value.adapter.host.registered.values())
        assert expected[0]['favorite'] is False and expected[0]['source_locale'] == 'zh-Hans'
        main_only(source, target, expected, retained)
        assert not retained
        observed.append('main-only-false')
    def complete(snapshot, target, expected, **options):
        before = probe.migration._inventory(snapshot)
        verify(snapshot, target, expected, **options)
        assert probe.migration._inventory(snapshot) == before and expected[0]['favorite'] is True
        observed.append('full-set-true')
    monkeypatch.setattr(probe, 'verify_main_only_transcript', baseline)
    monkeypatch.setattr(probe, 'verify_authored_snapshot', complete)
    assert value.run() == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert tuple(event['phase'] for event in events) == probe.WAL_PHASES
    assert all(event['schema'] == probe.WAL_SCHEMA and event['case'] == probe.WAL_CASE for event in events)
    assert observed == ['main-only-false', 'full-set-true'] and value.copy_attempts == 1
    wal = next(event for event in events if event['phase'] == 'wal-set-observed')
    assert wal['writers_signaled'] == 2 and wal['generation'] == 1 and wal['copy_verification'] == 'not-run'
    assert wal['wal_set'] == 'nonempty-after-retained-signals' and wal['wal_dependency'] == 'not-run'
    final = events[-1]
    assert final['wal_files'] >= 1 and final['shm_files'] >= 1 and final['writers_signaled'] == 4
    assert 32 < final['transcript_wal_bytes'] <= probe.WAL_FILE_BYTES
    assert 0 < final['transcript_shm_bytes'] <= probe.WAL_FILE_BYTES
    assert final['wal_dependency'] == 'main-only-false-full-set-true'
    assert final['sqlite_version'] == sqlite3.sqlite_version and final['sqlite_version_scope'] == 'frozen-coordinator'
    assert final['sqlite_policy'] == probe.WAL_POLICY and final['scope'] == probe.WAL_SCOPE
    assert not value.verification_ownership and all(host.wal_probe for host in value.adapter.cohorts)
    assert not value.coordinator._leases_held() and value.released and not value.copy_resumed
    assert value.coordinator.pointer_path.read_bytes() == value.pointer
    assert all(event['production_activation'] is False and event['target_activation'] is False
               and event['r19_complete'] is False and event['keeper_loss'] == 'unavailable' for event in events)
    assert not ({'copy_resumed', 'authored_interruptions'} & set(final))


def test_nonempty_wal_that_no_longer_changes_main_database_is_not_dependency_proof(fixture, monkeypatch, capsys):
    value = fixture.make(probe.WAL_CASE)
    favorite = probe._SetupStore.set_favorite
    def checkpointed(store, *args):
        result = favorite(store, *args)
        # An actual SQLite checkpoint in the authored API double's already
        # owned connection; no fabricated WAL or extra holder is introduced.
        assert store._owned_connections[-1].execute('PRAGMA wal_checkpoint(PASSIVE)').fetchone()[0] == 0
        return result
    monkeypatch.setattr(probe._SetupStore, 'set_favorite', checkpointed)
    assert value.run() == 2 and value.copy_attempts == 0 and value.released
    assert not value.wal_dependency and not value.adapter.poisoned
    assert (value.source.path/'data/transcript-v2.db-wal').stat().st_size > 32
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['failure'] == 'wal-dependency-unconfirmed'


def test_complete_set_without_its_real_wal_cannot_pass_semantic_verification(fixture, monkeypatch):
    value = fixture.make(probe.WAL_CASE)
    original = probe.verify_authored_snapshot
    def missing(snapshot, target, expected, **options):
        (snapshot/'data/transcript-v2.db-wal').unlink()
        original(snapshot, target, expected, **options)
    monkeypatch.setattr(probe, 'verify_authored_snapshot', missing)
    assert value.run() == 2 and value.released and not value.wal_dependency
    assert value.wal_set_observed and value.adapter.generation == 1


def test_wal_file_cap_is_enforced_before_a_copy_or_main_only_sqlite_open(fixture, monkeypatch):
    value = fixture.make(probe.WAL_CASE)
    monkeypatch.setattr(probe, 'WAL_FILE_BYTES', 32)
    monkeypatch.setattr(probe, 'verify_main_only_transcript', lambda *_: pytest.fail('Overbound set cannot be SQLite-opened'))
    monkeypatch.setattr(probe.migration, '_source_inventory', lambda *_: pytest.fail('Overbound set cannot be content-hashed'))
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.copy_attempts == 0 and not value.wal_set_observed


@pytest.mark.parametrize('mutation', ['source', 'generation'])
def test_wal_observation_handshake_cannot_outlive_actual_authority(fixture, monkeypatch, mutation):
    value = fixture.make(probe.WAL_CASE)
    observe = value.observe
    def changed(phase):
        observe(phase)
        if phase == 'wal-set-observed':
            if mutation == 'source':
                (value.source.path/'data/authored-payload.bin').write_bytes(b'changed authored source')
            else:
                value.adapter.generation += 1
    monkeypatch.setattr(value, 'observe', changed)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.copy_attempts == 0


def test_wal_verification_close_failure_retains_exact_connection_and_live_lease_owner(fixture, monkeypatch):
    value = fixture.make(probe.WAL_CASE)
    connect = sqlite3.connect
    failures = []
    class Unclosed(sqlite3.Connection):
        def close(self):
            failures.append(self)
            raise OSError('private authored close failure')
    def verification(database, *args, **options):
        if options.get('uri') and str(database).endswith('?mode=ro&immutable=1'):
            return connect(database, *args, factory=Unclosed, **options)
        return connect(database, *args, **options)
    monkeypatch.setattr(sqlite3, 'connect', verification)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        assert len(value.verification_ownership) == 1
        assert value.verification_ownership[0]['connection'] is failures[0]
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    try:
        with pytest.raises(HeldRecovery): value.run()
        assert len(failures) == 1 and value.copy_attempts == 0
    finally:
        for connection in failures: sqlite3.Connection.close(connection)
        for record in value.verification_ownership: shutil.rmtree(record['root'])


@pytest.mark.parametrize('case', [probe.WAL_CASE,probe.GRAMMAR_CASE])
def test_core_integrity_copy_close_failure_keeps_private_exception_connection_and_live_owner(fixture, monkeypatch, capsys, case):
    value = fixture.make(case)
    connect = sqlite3.connect
    references, closes, escaped, held = [], [], [], []
    class Unclosed(sqlite3.Connection):
        def close(self):
            closes.append(weakref.ref(self))
            raise OSError('private core verification close sentinel')
    def verification(database, *args, **options):
        if options.get('uri') and '/r19-sqlite-verify-' in str(database).replace('\\', '/'):
            connection = connect(database, *args, factory=Unclosed, **options)
            references.append(weakref.ref(connection))
            return connection
        return connect(database, *args, **options)
    monkeypatch.setattr(sqlite3, 'connect', verification)
    copy = probe.migration.copy_and_verify_synthetic
    def exact_failure(*args, **options):
        try:
            return copy(*args, **options)
        except BaseException as error:
            # Identity assertion only; drop this extra strong reference before
            # checking post-unwind connection lifetime through the probe owner.
            escaped.append(error)
            raise
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', exact_failure)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        assert value.core_copy_failure is escaped.pop()
        assert not value.verification_ownership  # This is the unchanged core's copy.
        held.append(True)
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    try:
        try:
            value.run()
        except HeldRecovery:
            pass
        else:
            pytest.fail('Core verification close failure cannot release the C5 owner.')
        gc.collect()
        assert held == [True] and not escaped and len(references) == len(closes) == 1
        assert references[0]() is closes[0]() and references[0]() is not None
        assert value.core_copy_failure is not None and value.adapter.generation == 1
        assert not value.release_attempted and value.copy_attempts == 1 and not value.copy_verified
        metadata = capsys.readouterr().out
        assert 'private core verification close sentinel' not in metadata and str(value.source.path) not in metadata
    finally:
        for reference in references:
            if reference() is not None: sqlite3.Connection.close(reference())


@pytest.mark.parametrize('strict_case', [probe.WAL_CASE,probe.GRAMMAR_CASE])
def test_strict_helper_refusals_hold_but_c3_c4_keep_existing_safe_error_policy(fixture, monkeypatch, strict_case):
    failure = HostProbeError('insufficient-space', 'private generic helper refusal')
    def refuse(*_args, **_options): raise failure
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', refuse)
    for case in (probe.CASE, probe.RESUME_CASE):
        value = fixture.make(case)
        assert value.run() == 2 and value.released and not value.adapter.poisoned
        assert value.core_copy_failure is None and value.adapter.generation == 1
    value = fixture.make(strict_case)
    def hold():
        assert value.core_copy_failure is failure and value.adapter.poisoned
        assert value.coordinator._leases_held() and not value.release_attempted
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert not value.released and value.adapter.generation == 1 and value.copy_attempts == 1


def test_wal_policy_configures_all_real_authored_constructor_paths_and_restores_connect(fixture):
    value = fixture.make(); value.prepare()
    original = sqlite3.connect
    connections = []
    with runtime_probe._authored_wal_connections(value.adapter.layout) as policy:
        probe._SetupStore(value.adapter.layout.data_root/'transcript-v2.db', connections)
        exports = LexiriseService(value.adapter.layout.data_root/'lexirise')
        reading = LexiriseReadingService(value.adapter.layout.data_root/'lexirise', exports)
        reading.quiesce(1)
        policy.require_stores()
        assert policy.configured == {'transcript', 'exports', 'reading'} and policy.opens == 3
    assert sqlite3.connect is original
    for connection in connections:
        assert connection.getconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE) is True
        connection.close()


def test_wal_policy_does_not_keep_successful_connections_alive_and_bounds_opens(fixture):
    value = fixture.make(); value.prepare()
    calls = []
    class Connection:
        def setconfig(self, *_): pass
        def getconfig(self, *_): return True
    def connect(*_a, **_k):
        calls.append(True)
        return Connection()
    policy = runtime_probe._AuthoredWalConnections(value.adapter.layout, connect)
    connection = policy.connect(value.adapter.layout.data_root/'transcript-v2.db')
    reference = weakref.ref(connection)
    del connection
    gc.collect()
    assert reference() is None  # A policy registry must not become an idle holder.
    for _ in range(255): policy.connect(value.adapter.layout.data_root/'transcript-v2.db')
    with pytest.raises(runtime_probe.RuntimeBundleError, match='connection bound'):
        policy.connect(value.adapter.layout.data_root/'transcript-v2.db')
    assert len(calls) == 256


@pytest.mark.parametrize('missing', [None, 'reading', 'preimport'])
def test_fixed_api_wal_patch_precedes_service_import_and_requires_actual_constructor_roles(fixture, monkeypatch, missing):
    value = fixture.make(); value.prepare()
    layout = value.adapter.layout
    original_connect = sqlite3.connect
    imported, ran = [], []
    monkeypatch.delitem(runtime_probe.sys.modules, 'backend.api', raising=False)
    class Runtime:
        def __init__(self):
            connections = []
            try: probe._SetupStore(layout.data_root/'transcript-v2.db', connections)
            finally:
                for connection in connections: connection.close()
            exports = LexiriseService(layout.data_root/'lexirise')
            if missing != 'reading': LexiriseReadingService(layout.data_root/'lexirise', exports).quiesce(1)
        def start_updates(self): pass
    initialize = Runtime.__init__
    service = SimpleNamespace(Runtime=Runtime, CaptureService=SimpleNamespace(warmup=lambda _: None),
                              AccountStore=object, app=object())
    import_module = runtime_probe.importlib.import_module
    def module(name, *args):
        if name != 'backend.api': return import_module(name, *args)
        assert sqlite3.connect is not original_connect
        imported.append(name)
        if missing == 'preimport': sqlite3.connect(layout.data_root/'transcript-v2.db').close()
        return service
    monkeypatch.setattr(runtime_probe.importlib, 'import_module', module)
    def uvicorn(app, **options):
        assert app is service.app and options['host'] == '127.0.0.1' and options['port'] == 8766
        Runtime()
        ran.append(True)
    monkeypatch.setitem(runtime_probe.sys.modules, 'uvicorn', SimpleNamespace(run=uvicorn))
    if missing:
        message = 'before the fixed Runtime constructor' if missing == 'preimport' else 'constructor configuration is incomplete'
        with pytest.raises(runtime_probe.RuntimeBundleError, match=message):
            runtime_probe.api(layout, wal_probe=True)
    else:
        assert runtime_probe.api(layout, wal_probe=True) == 0 and ran == [True]
    assert imported == ['backend.api'] and sqlite3.connect is original_connect and Runtime.__init__ is initialize


def test_fixed_wal_api_refuses_prior_service_import_and_non_bool_policy(fixture, monkeypatch):
    value = fixture.make(); value.prepare()
    monkeypatch.setitem(runtime_probe.sys.modules, 'backend.api', object())
    with pytest.raises(runtime_probe.RuntimeBundleError, match='import was not isolated'):
        runtime_probe.api(value.adapter.layout, wal_probe=True)
    for invalid in (1, 0, 'api-wal', None):
        with pytest.raises(runtime_probe.RuntimeBundleError, match='fixed authored API policy'):
            runtime_probe.api(value.adapter.layout, wal_probe=invalid)


@pytest.mark.parametrize('sidecar', ['-wal', '-shm'])
def test_missing_real_sidecar_refuses_before_copy_without_inventing_wal_bytes(fixture, monkeypatch, sidecar):
    value = fixture.make(probe.WAL_CASE)
    close = fixture.hosts.close
    def missing(host):
        close(host)
        (host.layout.data_root/('transcript-v2.db'+sidecar)).unlink()
    monkeypatch.setattr(fixture.hosts, 'close', missing)
    assert value.run() == 2 and value.released and not value.wal_set_observed and value.copy_attempts == 0
    assert not value.adapter.poisoned


def test_unsupported_wal_capability_never_mints_a_writer_barrier(fixture, monkeypatch):
    value = fixture.make(probe.WAL_CASE)
    monkeypatch.delattr(sqlite3, 'SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE')
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.copy_attempts == value.adapter.drains == 0 and value.coordinator._barrier is None


@pytest.mark.parametrize('fault', ['setconfig', 'false', 'integer', 'close'])
def test_wal_configuration_failure_closes_once_and_never_returns_a_connection(fixture, fault):
    value = fixture.make(); value.prepare()
    calls = []
    class Connection:
        def setconfig(self, option, enabled):
            calls.append(('set', option, enabled))
            if fault == 'setconfig': raise OSError('private setting failure')
        def getconfig(self, option): return 1 if fault == 'integer' else False
        def close(self):
            calls.append('close')
            if fault == 'close': raise OSError('private close failure')
    policy = runtime_probe._AuthoredWalConnections(value.adapter.layout, lambda *_a, **_k: Connection())
    with pytest.raises(runtime_probe.RuntimeBundleError) as error:
        policy.connect(value.adapter.layout.data_root/'transcript-v2.db')
    assert calls.count('close') == 1 and not policy.configured and 'private' not in str(error.value)
    assert ('cleanup is unconfirmed' in str(error.value)) is (fault == 'close')


@pytest.mark.parametrize('selection', ['foreign', 'uri', 'memory', 'relative', 'factory', 'positional', 'traversal'])
def test_wal_selection_refuses_before_connect_or_foreign_metadata(fixture, monkeypatch, selection):
    value = fixture.make(); value.prepare()
    layout = value.adapter.layout
    policy = runtime_probe._AuthoredWalConnections(layout, lambda *_a, **_k: pytest.fail('Selection cannot reach SQLite'))
    database, args, options = layout.data_root/'transcript-v2.db', (), {}
    if selection == 'foreign': database = value.fixture/'outside-private-sentinel.db'
    if selection == 'uri': database = database.as_uri();options['uri'] = True
    if selection == 'memory': database = ':memory:'
    if selection == 'relative': database = 'transcript-v2.db'
    if selection == 'factory': options['factory'] = sqlite3.Connection
    if selection == 'positional': args = (10,)
    if selection == 'traversal': database = layout.data_root/'unused/../transcript-v2.db'
    monkeypatch.setattr(policy, 'guard', lambda *_a, **_k: pytest.fail('Rejected selection cannot inspect metadata'))
    with pytest.raises(runtime_probe.RuntimeBundleError): policy.connect(database, *args, **options)
    assert policy.opens == 0


def test_wal_parent_link_refuses_before_leaf_metadata_or_sqlite_open(fixture, monkeypatch):
    value = fixture.make(); value.prepare()
    layout = value.adapter.layout
    policy = runtime_probe._AuthoredWalConnections(layout, lambda *_a, **_k: pytest.fail('Linked selection cannot open'))
    outside = value.fixture/'outside-authored'; outside.mkdir()
    (layout.data_root/'lexirise').symlink_to(outside, target_is_directory=True)
    original = Path.lstat
    link = layout.data_root/'lexirise'
    def guarded(path, *args, **options):
        assert link not in path.parents, 'Linked descendant metadata must remain unobserved.'
        return original(path, *args, **options)
    monkeypatch.setattr(Path, 'lstat', guarded)
    with pytest.raises(probe.DataCopyFailure): policy.connect(link/'exports-v2.db')
    assert policy.opens == 0


def test_interrupted_copy_resumes_same_live_plan_barrier_generation_and_leases(fixture, monkeypatch, capsys):
    value = fixture.make(probe.RESUME_CASE)
    original = probe.migration.copy_and_verify_synthetic
    attempts = []
    closes = []
    prepare = value.prepare
    def prepared():
        prepare()
        for name in ('_legacy_lease', '_target_lease'):
            lease = getattr(value.coordinator, name)
            close = lease.close
            def watched(close=close, name=name):
                closes.append(name)
                return close()
            monkeypatch.setattr(lease, 'close', watched)
    monkeypatch.setattr(value, 'prepare', prepared)
    def copy(plan, barrier, **options):
        barrier.check(value.source)
        attempts.append((plan, barrier, value.adapter.generation, value.coordinator._legacy_lease,
                         value.coordinator._target_lease, len(value.adapter.cohorts)))
        assert value.coordinator._leases_held() and not value.adapter.capture_running()
        assert not closes
        if len(attempts) == 2:
            manifest = json.loads((value.target.path/'migrations'/plan.migration_id/'manifest.json').read_text())
            assert manifest['state'] == 'failed' and len(manifest['completed_files']) == 1
            assert manifest['failure'] == probe._AuthoredCopyInterruption.__name__
            assert manifest['activation_allowed'] is False
        return original(plan, barrier, **options)
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', copy)
    assert value.run() == 0
    assert len(attempts) == 2 and attempts[0] == attempts[1] and attempts[0][2] == attempts[0][5] == 1
    assert all(attempts[0][index] is attempts[1][index] for index in (0, 1, 3, 4))
    assert closes == ['_target_lease', '_legacy_lease']
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert tuple(event['phase'] for event in events) == probe.RESUME_PHASES
    partial = next(event for event in events if event['phase'] == 'copy-interrupted')
    assert partial['generation'] == 1 and partial['writers_signaled'] == 2
    assert partial['copy_attempts'] == partial['authored_interruptions'] == partial['partial_revalidations'] == 1
    assert partial['same_plan_barrier_generation'] is True and partial['copy_resumed'] is False
    final = events[-1]
    assert final['schema'] == probe.RESUME_SCHEMA and final['scope'] == probe.RESUME_SCOPE
    assert final['copy_attempts'] == final['partial_revalidations'] == 2 and final['authored_interruptions'] == 1
    assert final['copy_resumed'] is True and final['old_barrier_refused'] is True
    assert final['generation'] == 2 and final['writers_signaled'] == 4 and value.released


@pytest.mark.parametrize('wrong', ['different-instance', 'unrelated-error', 'missing-callback'])
def test_only_the_exact_intended_interruption_instance_can_authorize_resume(fixture, monkeypatch, capsys, wrong):
    value = fixture.make(probe.RESUME_CASE)
    original = probe.migration.copy_and_verify_synthetic
    attempts = []
    def wrong_sentinel(plan, barrier, **options):
        attempts.append(True)
        if wrong == 'missing-callback':
            return original(plan, barrier)
        try:
            return original(plan, barrier, **options)
        except probe._AuthoredCopyInterruption:
            if wrong == 'unrelated-error':
                raise OSError('authored different copy failure') from None
            raise probe._AuthoredCopyInterruption() from None
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', wrong_sentinel)
    assert value.run() == 2 and attempts == [True]
    assert value.adapter.generation == 1 and not value.copy_resumed and value.authored_interruptions == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['status'] == 'failed'


@pytest.mark.parametrize('mutation', ['source', 'completed-bytes', 'binding', 'generation', 'roots'])
def test_interruption_checkpoint_mutation_refuses_resume_without_changing_core_repair_semantics(fixture, monkeypatch, mutation):
    value = fixture.make(probe.RESUME_CASE)
    observe = value.observe
    copied = probe.migration.copy_and_verify_synthetic
    attempts = []
    def copy(*args, **options):
        attempts.append(True)
        return copied(*args, **options)
    def checkpoint(phase):
        observe(phase)
        if phase != 'copy-interrupted': return
        manifest_path = next((value.target.path/'migrations').glob('*/manifest.json'))
        manifest = json.loads(manifest_path.read_text())
        if mutation == 'source':
            (value.source.path/'data/authored-payload.bin').write_bytes(b'authored source changed')
        elif mutation == 'completed-bytes':
            (value.target.path/'staging'/manifest['migration_id']/manifest['completed_files'][0]).write_bytes(b'authored target changed')
        elif mutation == 'binding':
            manifest['binding']['database_versions']['data/transcript-v2.db'] = 1
            manifest_path.write_text(json.dumps(manifest))
        elif mutation == 'roots':
            manifest['roots'] = {'source': 'untrusted-manifest-source', 'target': 'untrusted-manifest-target'}
            manifest_path.write_text(json.dumps(manifest))
        else:
            value.adapter.generation += 1
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', copy)
    monkeypatch.setattr(value, 'observe', checkpoint)
    # The adapter stores its phase callback at construction during prepare.
    if mutation in {'source', 'generation'}:
        def hold():
            assert value.coordinator._leases_held() and value.adapter.poisoned
            raise HeldRecovery()
        monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
        with pytest.raises(HeldRecovery): value.run()
        assert not value.released
    else:
        assert value.run() == 2 and value.released
    assert attempts == [True] and not value.copy_resumed and not value.adapter.active


def test_resume_case_unconfirmed_fresh_cohort_and_broken_failure_output_keep_live_hold(fixture, monkeypatch):
    value = fixture.make(probe.RESUME_CASE)
    start = fixture.hosts.start_registered
    def partial(host, **options):
        if len(value.adapter.cohorts) == 2:
            raise OSError('authored unconfirmed second-cohort startup')
        return start(host, **options)
    monkeypatch.setattr(fixture.hosts, 'start_registered', partial)
    emit = value.emit
    def broken(phase, **options):
        if phase == 'recovery-required': raise BrokenPipeError('authored failed failure event')
        return emit(phase, **options)
    monkeypatch.setattr(value, 'emit', broken)
    def hold():
        assert value.coordinator._leases_held() and value.adapter.poisoned
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.copy_resumed and value.adapter.generation == 2 and not value.released


@pytest.mark.parametrize('fault', ['source-after-precheck', 'source-during-resume', 'source-during-first-copy',
    'barrier-lost', 'source-read-failure', 'owner-changed'])
def test_copy_failure_rechecks_real_source_authority_after_prechecks_and_during_helper(fixture, monkeypatch, fault):
    value = fixture.make(probe.RESUME_CASE)
    original = probe.migration.copy_and_verify_synthetic
    attempts = []
    def copy(plan, barrier, **options):
        attempts.append(True)
        number = len(attempts)
        if number == 2 and fault == 'source-after-precheck':
            (value.source.path/'data/authored-payload.bin').write_bytes(b'authored post-precheck mutation')
        if number == 2 and fault == 'barrier-lost': barrier.invalidate()
        if number == 2 and fault == 'owner-changed':
            value.coordinator.current = SimpleNamespace(runtime_id='authored-unconfirmed-owner')
        if number == 2 and fault == 'source-read-failure':
            def unreadable(*_args): raise OSError('authored source inventory unavailable')
            monkeypatch.setattr(probe.migration, '_source_inventory', unreadable)
        if ((number == 2 and fault == 'source-during-resume')
                or (number == 1 and fault == 'source-during-first-copy')):
            previous = options.get('checkpoint')
            def checkpoint(stage, name):
                if stage == 'file-copied':
                    (value.source.path/'data/authored-payload.bin').write_bytes(b'authored mutation during helper')
                if previous: previous(stage, name)
            options['checkpoint'] = checkpoint
        return original(plan, barrier, **options)
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', copy)
    def hold():
        assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert len(attempts) == (1 if fault == 'source-during-first-copy' else 2)


@pytest.mark.parametrize('changed', ['source', 'target-binding'])
def test_identical_core_binding_error_is_classified_by_actual_source_not_error_label(fixture, monkeypatch, changed):
    value = fixture.make(probe.RESUME_CASE)
    original = probe.migration.copy_and_verify_synthetic
    attempts, codes = [], []
    def copy(plan, barrier, **options):
        attempts.append(True)
        if len(attempts) == 2:
            if changed == 'source':
                (value.source.path/'data/authored-payload.bin').write_bytes(b'authored source differs')
            else:
                path = value.target.path/'migrations'/plan.migration_id/'manifest.json'
                manifest = json.loads(path.read_text())
                manifest['binding']['named_account_store'] = 'unreadable'
                path.write_text(json.dumps(manifest))
        try:
            return original(plan, barrier, **options)
        except HostProbeError as error:
            codes.append(error.code)
            raise
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', copy)
    if changed == 'source':
        emit = value.emit
        def broken(phase, **options):
            if phase == 'recovery-required': raise BrokenPipeError('authored failed failure output')
            return emit(phase, **options)
        monkeypatch.setattr(value, 'emit', broken)
        def hold():
            assert value.adapter.poisoned and value.coordinator._leases_held() and not value.released
            raise HeldRecovery()
        monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
        with pytest.raises(HeldRecovery): value.run()
    else:
        assert value.run() == 2 and value.released and not value.adapter.poisoned
    assert codes == ['source-or-plan-changed'] and len(attempts) == 2 and not value.copy_resumed


@pytest.mark.parametrize('where', ['manifest', 'staging'])
@pytest.mark.parametrize('kind', ['parent-link', 'windows-reparse'])
def test_partial_static_parent_links_refuse_before_outside_descendant_metadata(fixture, monkeypatch, where, kind):
    value = fixture.make(probe.RESUME_CASE)
    observe = value.observe
    original_lstat, original_stat, original_open = Path.lstat, Path.stat, Path.open
    touched, restored = [], []
    def checkpoint(phase):
        observe(phase)
        if phase != 'copy-interrupted': return
        manifest = next((value.target.path/'migrations').glob('*/manifest.json'))
        migration_id = manifest.parent.name
        link = manifest.parent if where == 'manifest' else value.target.path/'staging'/migration_id/'data'
        outside = value.fixture/('authored-outside-'+where)
        if kind == 'parent-link':
            link.rename(outside)
            link.symlink_to(outside, target_is_directory=True)
            restored.append((link, outside))
        def lstat(path, *args, **options):
            if link in path.parents:
                touched.append('lstat');raise AssertionError('Outside descendant metadata is forbidden.')
            info = original_lstat(path, *args, **options)
            if kind == 'windows-reparse' and path == link:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        def stat(path, *args, **options):
            if link in path.parents:
                touched.append('stat');raise AssertionError('Outside descendant metadata is forbidden.')
            return original_stat(path, *args, **options)
        def open_file(path, *args, **options):
            if link in path.parents or path == outside or outside in path.parents:
                touched.append('open');raise AssertionError('Outside content is forbidden.')
            return original_open(path, *args, **options)
        monkeypatch.setattr(Path, 'lstat', lstat)
        monkeypatch.setattr(Path, 'stat', stat)
        monkeypatch.setattr(Path, 'open', open_file)
    monkeypatch.setattr(value, 'observe', checkpoint)
    try:
        assert value.run() == 2 and not value.copy_resumed and value.released
        assert not touched and not value.adapter.poisoned
    finally:
        monkeypatch.setattr(Path, 'lstat', original_lstat)
        monkeypatch.setattr(Path, 'stat', original_stat)
        monkeypatch.setattr(Path, 'open', original_open)
        for link, outside in restored:
            link.unlink();outside.rename(link)


@pytest.mark.parametrize('which', ['source', 'target'])
@pytest.mark.parametrize('kind', ['parent-link', 'windows-reparse'])
def test_authority_root_link_is_guarded_before_barrier_marker_and_failure_journal_reads(fixture, monkeypatch, which, kind):
    value = fixture.make(probe.RESUME_CASE)
    observe = value.observe
    originals = {'lstat': Path.lstat, 'stat': Path.stat, 'open': Path.open}
    copied = probe.migration.copy_and_verify_synthetic
    touched, restored, plans, leases, denials, installed, held = [], [], [], [], [], [], []
    def copy(plan, barrier, **options):
        plans.append(plan)
        return copied(plan, barrier, **options)
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', copy)
    def root_state():
        return tuple((root.path, originals['stat'](root.path).st_dev,
                      originals['stat'](root.path).st_ino,
                      (root.path/'.r19-synthetic-fixture.json').read_bytes())
                     for root in (value.source, value.target))
    def lease_state():
        return tuple((lease, lease._handle) for lease in
                     (value.coordinator._legacy_lease, value.coordinator._target_lease))
    def same_leases(actual):
        assert len(actual) == len(leases) == 2
        assert all(lease is before and handle is original and handle is not None
                   for (lease, handle), (before, original) in zip(actual, leases))
    def checkpoint(phase):
        observe(phase)
        if phase != 'copy-interrupted': return
        link = getattr(value, which).path
        outside = value.fixture/('authored-outside-'+which)
        leases.extend(lease_state())
        before_roots = root_state()
        before_source = probe.migration._source_inventory(plans[0])
        if kind == 'parent-link':
            try:
                link.rename(outside)
            except OSError as error:
                # Windows may deny renaming a tree containing our share-mode-0
                # lease. This is an unmet fault-injection precondition, not a
                # successful root-link test. Inspect this branch explicitly.
                denials.append((getattr(error, 'winerror', None), before_roots, root_state(),
                    before_source, probe.migration._source_inventory(plans[0]),
                    lease_state(), link.is_symlink(), outside.exists(), value.coordinator._leases_held()))
                raise
            restored.append((link, outside))
            link.symlink_to(outside, target_is_directory=True)
        installed.append(kind)
        for name, original in originals.items():
            def guarded(path, *args, original=original, name=name, **options):
                if link in path.parents:
                    touched.append(name);raise AssertionError('Untrusted root descendant metadata/read is forbidden.')
                info = original(path, *args, **options)
                if kind == 'windows-reparse' and name == 'lstat' and path == link:
                    # Behavior injection only: retain the actual original roots
                    # and native leases while testing the Windows attribute gate.
                    return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                return info
            monkeypatch.setattr(Path, name, guarded)
    monkeypatch.setattr(value, 'observe', checkpoint)
    def hold():
        assert value.adapter.poisoned and not value.released and value.coordinator._leases_held()
        assert value.coordinator._recovery_required
        same_leases(lease_state())
        held.append(True)
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    try:
        try:
            result = value.run()
        except HeldRecovery:
            result = 'held'
        assert len(plans) == 1 and not value.copy_resumed and not touched
        if denials:
            assert kind == 'parent-link' and probe.os.name == 'nt' and len(denials) == 1
            code, before, after, source_before, source_after, captured_leases, is_link, moved, owned = denials[0]
            assert code in {5, 32}, 'Only explicit Windows access/sharing denial is this precondition outcome.'
            assert before == after and source_before == source_after
            same_leases(captured_leases)
            assert owned and not is_link and not moved and not installed and not restored
            assert result == 2 and value.released and not value.adapter.poisoned and not held
            assert not value.coordinator._leases_held()
            assert root_state() == before and probe.migration._source_inventory(plans[0]) == source_before
        else:
            assert installed == [kind] and result == 'held' and held == [True]
    finally:
        for name, original in originals.items(): monkeypatch.setattr(Path, name, original)
        for link, outside in restored:
            if link.is_symlink(): link.unlink()
            outside.rename(link)


def test_local_tree_guard_bounds_entries_and_bytes_before_content_reads(tmp_path, monkeypatch):
    root = tmp_path/'authored-tree';root.mkdir()
    (root/'first').write_bytes(b'ab');(root/'second').write_bytes(b'c')
    monkeypatch.setattr(probe, 'INSPECTION_BYTES', 1)
    with pytest.raises(probe.DataCopyFailure): probe._guard_tree(root)
    monkeypatch.setattr(probe, 'INSPECTION_BYTES', 64)
    monkeypatch.setattr(probe, 'INSPECTION_ENTRIES', 1)
    class Entries:
        def __enter__(self): return iter([SimpleNamespace(name='first'), SimpleNamespace(name='second')])
        def __exit__(self, *_args): pass
    monkeypatch.setattr(probe.os, 'scandir', lambda _root: Entries())
    original = Path.lstat
    def no_second(path, *args, **options):
        assert path != root/'second', 'Overbound child must be refused before leaf metadata.'
        return original(path, *args, **options)
    monkeypatch.setattr(Path, 'lstat', no_second)
    with pytest.raises(probe.DataCopyFailure): probe._guard_tree(root)


def test_setup_connections_include_constructor_and_are_explicitly_closed(tmp_path, monkeypatch):
    observed = []
    original = probe.TranscriptStore._connect
    def connect(self):
        connection = original(self); observed.append(connection); return connection
    monkeypatch.setattr(probe.TranscriptStore, '_connect', connect)
    rows = probe.seed_authored(tmp_path/'transcript.db')
    assert len(observed) == 3 and len(rows) == 2 and rows[0]['source_locale'] == 'zh-Hans'
    for connection in observed:
        with pytest.raises(sqlite3.ProgrammingError, match='closed'): connection.execute('SELECT 1')


def test_setup_exception_still_closes_constructor_connection(tmp_path, monkeypatch):
    observed = []
    original = probe._SetupStore._connect
    def connect(self):
        connection = original(self); observed.append(connection); return connection
    def fail_add(*_args, **_kwargs): raise RuntimeError('authored add refusal')
    monkeypatch.setattr(probe._SetupStore, '_connect', connect)
    monkeypatch.setattr(probe._SetupStore, 'add', fail_add)
    with pytest.raises(RuntimeError, match='authored add refusal'): probe.seed_authored(tmp_path/'transcript.db')
    assert len(observed) == 1
    with pytest.raises(sqlite3.ProgrammingError): observed[0].execute('SELECT 1')


def test_setup_close_refusal_attempts_every_connection_and_is_not_hidden(tmp_path, monkeypatch):
    original = probe.TranscriptStore._connect
    actual, attempts = [], []
    class Connection:
        def __init__(self, connection): self.connection = connection
        def __getattr__(self, name): return getattr(self.connection, name)
        def __enter__(self): self.connection.__enter__(); return self
        def __exit__(self, *args): return self.connection.__exit__(*args)
        def close(self):
            attempts.append(self)
            if self is actual[0]: raise OSError('authored unconfirmed close')
            self.connection.close()
    def connect(self):
        wrapped = Connection(original(self)); actual.append(wrapped); return wrapped
    monkeypatch.setattr(probe.TranscriptStore, '_connect', connect)
    try:
        with pytest.raises(probe.DataCopyFailure, match='setup-close-unconfirmed'):
            probe.seed_authored(tmp_path/'transcript.db')
        assert len(actual) == 3 and set(attempts) == set(actual)
    finally:
        for wrapped in actual: wrapped.connection.close()


class HeldRecovery(BaseException): pass


@pytest.mark.parametrize('boundary', ['create', 'drain', 'close', 'unsignaled', 'identity', 'control', 'setupclose'])
def test_unknown_writer_boundary_holds_live_owner_and_never_copies(fixture, monkeypatch, boundary):
    value = fixture.make()
    original_prepare = value.prepare
    def prepare():
        original_prepare()
        if boundary == 'control':
            value.observe = lambda _phase: (_ for _ in ()).throw(probe.DataCopyFailure('control-unavailable'))
            value.adapter.observe = value.observe
    monkeypatch.setattr(value, 'prepare', prepare)
    def fail(*_args, **_kwargs): raise OSError('private boundary value must not be published')
    if boundary == 'setupclose':
        def unclosed(_path): raise probe.DataCopyFailure('setup-close-unconfirmed')
        monkeypatch.setattr(probe, 'seed_authored', unclosed)
    if boundary == 'create': monkeypatch.setattr(fixture.hosts, 'start_registered', fail)
    if boundary == 'drain': monkeypatch.setattr(fixture.hosts, 'quiesce_registered', fail)
    if boundary == 'close': monkeypatch.setattr(fixture.hosts, 'close', fail)
    if boundary == 'unsignaled':
        original_close = fixture.hosts.close
        def close(host): original_close(host); host.registered['api'].exited = False
        monkeypatch.setattr(fixture.hosts, 'close', close)
    if boundary == 'identity':
        @contextmanager
        def foreign(_host): yield False
        monkeypatch.setattr(fixture.hosts, '_registered_listener_scope', foreign)
    copied = []
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', lambda *_a, **_k: copied.append(True))
    def hold():
        assert value.coordinator._leases_held() and value.adapter.poisoned
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert not copied and not value.released


def test_broken_failure_output_cannot_bypass_live_owner_hold(fixture, monkeypatch):
    value = fixture.make()
    def emit(*_args, **_kwargs): raise BrokenPipeError('private transport error')
    monkeypatch.setattr(value, 'emit', emit)
    def hold():
        assert value.coordinator._leases_held()
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    # Fail while the first real-adapter cohort could write; failure emit fails too.
    original_prepare = value.prepare
    def prepare():
        monkeypatch.setattr(value, 'observe', lambda _phase: None)
        original_prepare()
        value.adapter.start()
        raise OSError('authored active-writer fault')
    monkeypatch.setattr(value, 'prepare', prepare)
    with pytest.raises(HeldRecovery): value.run()
    assert value.adapter.poisoned and not value.released


def test_deterministic_copy_refusal_cannot_restart_source(fixture, monkeypatch, capsys):
    value = fixture.make()
    def refuse(*_args, **_kwargs): raise HostProbeError('insufficient-space', 'authored copy fault')
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', refuse)
    assert value.run() == 2
    assert value.adapter.generation == 1 and not value.adapter.active
    assert value.released and value.target.path.exists() and value.source.path.exists()
    assert value.coordinator.pointer_path.read_bytes() == value.pointer
    final = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert final['status'] == 'failed' and final['failure'] == 'copy-refused'
    checkpoint = json.loads((value.target.path/'host-v1/data-copy-failure.json').read_text())
    assert checkpoint['status'] == 'failed' and checkpoint['failure'] == 'copy-refused'


def test_unconfirmed_lease_close_is_never_retried_with_retained_raw_value(fixture, monkeypatch):
    value = fixture.make()
    original_prepare = value.prepare
    attempts, original_close = [], []
    def prepare():
        original_prepare()
        lease = value.coordinator._target_lease
        original_close.append(lease.close)
        def unconfirmed():
            attempts.append('close')
            raise OSError(6, 'authored invalidated close result')
        monkeypatch.setattr(lease, 'close', unconfirmed)
    monkeypatch.setattr(value, 'prepare', prepare)
    def hold():
        assert value.adapter.poisoned and not value.released
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    try:
        with pytest.raises(HeldRecovery): value.run()
        assert attempts == ['close'] and value.release_attempted
        assert value.adapter.generation == 2 and not value.adapter.active
    finally:
        if original_close: monkeypatch.setattr(value.coordinator._target_lease, 'close', original_close[0])


def test_failed_private_failure_checkpoint_keeps_live_owner_even_after_writer_stop(fixture, monkeypatch):
    value = fixture.make()
    def refuse(*_args, **_kwargs): raise HostProbeError('insufficient-space', 'authored copy fault')
    monkeypatch.setattr(probe.migration, 'copy_and_verify_synthetic', refuse)
    monkeypatch.setattr(probe, '_atomic_json', lambda *_a, **_k: (_ for _ in ()).throw(OSError('authored checkpoint I/O refusal')))
    def hold():
        assert value.coordinator._leases_held() and value.adapter.poisoned and not value.adapter.active
        raise HeldRecovery()
    monkeypatch.setattr(probe, 'hold_keeper_recovery', hold)
    with pytest.raises(HeldRecovery): value.run()
    assert value.adapter.generation == 1 and not value.release_attempted


@pytest.mark.parametrize('version,extra', [(1, False), (0, True)])
def test_fixed_schema_verification_refuses_changed_version_or_extra_table(fixture, monkeypatch, version, extra):
    value = fixture.make()
    original = probe.verify_authored_snapshot
    def verify(snapshot, target, expected):
        with closing(sqlite3.connect(snapshot/'data/transcript-v2.db')) as connection, connection:
            connection.execute('PRAGMA user_version='+str(version))
            if extra: connection.execute('CREATE TABLE unknown_authored_store(value TEXT)')
        original(snapshot, target, expected)
    monkeypatch.setattr(probe, 'verify_authored_snapshot', verify)
    assert value.run() == 2 and value.adapter.generation == 1
    assert value.released and value.target.path.exists()


def test_snapshot_semantic_check_does_not_change_source_or_snapshot_bytes(fixture, monkeypatch):
    value = fixture.make()
    observed = []
    original = probe.verify_authored_snapshot
    def verify(snapshot, target, expected):
        before = probe.migration._inventory(snapshot)
        original(snapshot, target, expected)
        assert probe.migration._inventory(snapshot) == before
        observed.append(True)
    monkeypatch.setattr(probe, 'verify_authored_snapshot', verify)
    assert value.run() == 0 and observed == [True]


@pytest.mark.parametrize('field,value', [('favorite', 1), ('id', True), ('id', 1.0), ('texts', []), ('source_locale', None)])
def test_authored_row_validation_rejects_bool_integer_and_context_coercions(tmp_path, field, value):
    row = probe.seed_authored(tmp_path/'store.db')[0]
    row[field] = value
    with pytest.raises(probe.DataCopyFailure, match='authored-rows-differ'): probe._row(row)


def test_adapter_never_admits_setup_or_warm_readiness_as_proof(fixture):
    value = fixture.make()
    value.prepare()
    adapter = value.adapter
    with pytest.raises(probe.DataCopyFailure): adapter.ready()
    with pytest.raises(probe.DataCopyFailure): adapter.prepare()
    adapter.setup_open = True
    with pytest.raises(probe.DataCopyFailure): adapter.start()
    assert adapter.generation == 0 and not adapter.cohorts
    adapter.setup_open = False


def test_partial_fresh_start_increments_generation_and_never_reuses_old_children(fixture, monkeypatch):
    value = fixture.make()
    value.prepare(); value.adapter.start()
    # Checkpoint controls in prepare consumed setup-closed only; suppress the
    # fixed native-stage handshake for this local admission-order regression.
    value.adapter.observe = lambda _phase: None
    value.adapter.quiesce()
    old = value.adapter.host
    def fail(_host, **_kwargs): raise OSError('authored second-cohort creation fault')
    monkeypatch.setattr(fixture.hosts, 'start_registered', fail)
    with pytest.raises(OSError): value.adapter.activate(probe.SyntheticHandoff(False))
    assert value.adapter.generation == 2 and value.adapter.poisoned
    assert old is not value.adapter.host and all(child.closed and child.exited for child in old.registered.values())
    assert [host for name, host in fixture.calls if name == 'resume'] == [old]


def _powershell_contract(script, functions, body, payload=None):
    executable = shutil.which('pwsh')
    if not executable: pytest.skip('PowerShell parser/contract unavailable locally; required on hosted Windows.')
    text = "$ErrorActionPreference='Stop'\n"
    text += "$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$tokens,[ref]$errors)\n"
    text += "if ($errors) { throw 'Data-copy harness parse failure.' }\n"
    for function in functions:
        text += "$definition=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq '"+function+"'},$true)\n"
        text += "if (-not $definition) { throw 'Missing fixed data-copy function.' };. ([scriptblock]::Create($definition.Extent.Text))\n"
    text += "$script:ProbeCase='authored-data-copy'\n"
    text += body
    with tempfile.TemporaryDirectory(prefix='r19-data-copy-contract-') as temporary:
        driver = Path(temporary)/'contract.ps1'
        driver.write_text(text, encoding='utf-8')
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-File', str(driver), str(script)],
            input=json.dumps(payload).encode() if payload is not None else None, capture_output=True, timeout=20)
    diagnostic = 'unavailable'
    if result.returncode and isinstance(payload, list):
        try:
            value = json.loads(result.stdout)
            if (set(value) == {'schema', 'case_index', 'expected', 'actual'}
                    and value['schema'] == 'proxy-r19-data-copy-contract-failure-v1'
                    and type(value['case_index']) is int and 0 <= value['case_index'] < len(payload)
                    and type(value['expected']) is bool and type(value['actual']) is bool):
                diagnostic = f"case={value['case_index']},expected={value['expected']},actual={value['actual']}"
        except (ValueError, TypeError, KeyError):
            pass
    assert result.returncode == 0, 'Fixed data-copy PowerShell contract failed: '+diagnostic


def test_powershell_roots_use_actual_child_temp_and_failure_receipt_cannot_skip_live_hold(tmp_path):
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['Get-DataCopyRoots', 'Complete-DataCopyHarness'], r'''
$roots=Get-DataCopyRoots ([IO.Path]::GetTempPath())
$prefix=Join-Path ([IO.Path]::GetTempPath()) 'empty-host'
if (-not $roots.PROXY_TRANSCRIPT_WORK_ROOT.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Child TEMP containment differs.' }
$script:held=$false;$script:ownerExitConfirmed=$false
$owned=@([pscustomobject]@{HasExited=$false})
function Write-DataCopyReceipt { throw 'authored failed receipt channel' }
function Wait-DataCopyRecovery { $script:held=$true;throw 'authored held sentinel' }
$Output=Join-Path ([IO.Path]::GetTempPath()) ('r19-unused-'+[guid]::NewGuid().ToString('N')+'.json')
try { Complete-DataCopyHarness $true } catch {}
if (-not $script:held) { throw 'Receipt failure bypassed live owner hold.' }
$script:held=$false;$script:ownerExitConfirmed=$true
$script:queried=0
$observer=[pscustomobject]@{}
$observer | Add-Member ScriptProperty HasExited { $script:queried++;throw 'authored unavailable disposed observer' }
$owned=@($observer)
try { Complete-DataCopyHarness $true } catch {}
if ($script:held -or $script:queried -ne 0) { throw 'Known signaled owner cannot be queried again through disposed observer state.' }
''')


def test_powershell_event_validation_requires_exact_types_lifecycle_and_safe_scope(fixture, capsys):
    value = fixture.make()
    value.prepare()
    event = json.loads(capsys.readouterr().out.splitlines()[0])
    cases = [{'name': 'valid-setup', 'event': event, 'accept': True}]
    for field, changed in [('generation', True), ('generation', 1), ('r19_complete', 'false'),
            ('kind', ['data-copy']), ('copy_verification', 'passed'), ('old_barrier_refused', True),
            ('source_commit', 'b'*40), ('authority', 'http-only'), ('phase', 'released'),
            ('wal_files', 4), ('failure', 'private-unapproved-category')]:
        cases.append({'name': field+'-refusal', 'event': {**event, field: changed}, 'accept': False})
    cases.append({'name': 'extra-property-refusal', 'event': {**event, 'unexpected': 'private sentinel'}, 'accept': False})
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['New-DataCopyControlReader','Read-DataCopyControlLine','Read-DataCopyEvent'], r'''
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$cases=[Console]::In.ReadToEnd() | ConvertFrom-Json
$index=0
foreach ($case in $cases) {
    $bytes=[Text.UTF8Encoding]::new($false,$true).GetBytes(($case.event | ConvertTo-Json -Depth 8 -Compress)+"`n")
    $stream=[IO.MemoryStream]::new($bytes,$false)
    $script:controlReader=New-DataCopyControlReader $stream ([Threading.Tasks.Task]::CompletedTask)
    $accepted=$true
    try { Read-DataCopyEvent 'setup-closed' } catch { $accepted=$false }
    if ($accepted -ne $case.accept) {
        [Console]::Out.WriteLine((@{schema='proxy-r19-data-copy-contract-failure-v1';case_index=$index;
            expected=[bool]$case.accept;actual=[bool]$accepted} | ConvertTo-Json -Compress))
        exit 2
    }
    $stream.Dispose()
    $index++
}
''', cases)


def test_powershell_control_reader_caps_raw_bytes_and_faults_hold_live_owner_even_if_receipt_fails():
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['New-DataCopyControlReader','Read-DataCopyControlLine','Complete-DataCopyHarness'], r'''
$utf8=[Text.UTF8Encoding]::new($false,$true)
$complete=[Threading.Tasks.Task]::CompletedTask
$stream=[IO.MemoryStream]::new($utf8.GetBytes("{}`n[]`n"),$false)
$reader=New-DataCopyControlReader $stream $complete
if ((Read-DataCopyControlLine $reader) -cne '{}' -or (Read-DataCopyControlLine $reader) -cne '[]' -or
    $null -ne (Read-DataCopyControlLine $reader 1000 $true) -or $reader.buffer.Length -ne 4096 -or
    $reader.line.Length -ne 8192 -or $null -ne $reader.pending) { throw 'Fixed control buffer/consumer contract differs.' }
$stream.Dispose()
$multibyte=([char]0x6f22).ToString()*3000
if ($multibyte.Length -ge 8192 -or $utf8.GetByteCount($multibyte) -le 8192) { throw 'Authored multibyte boundary differs.' }
$cases=@(
    @{bytes=$utf8.GetBytes(('x'*8193)+"`n");reason='control-overflow'},
    @{bytes=$utf8.GetBytes($multibyte+"`n");reason='control-overflow'},
    @{bytes=$utf8.GetBytes(('x'*100));reason='control-eof'},
    @{bytes=$utf8.GetBytes('{"partial":');reason='control-eof'},
    @{bytes=[byte[]]@(255,10);reason='control-invalid-utf8'})
foreach ($case in $cases) {
    $stream=[IO.MemoryStream]::new($case.bytes,$false)
    $reader=New-DataCopyControlReader $stream $complete
    $accepted=$true
    try { $null=Read-DataCopyControlLine $reader 1000 } catch { $accepted=$false }
    if ($accepted -or $reader.fault -cne $case.reason) { throw 'Fixed byte/framing refusal differs.' }
    # A poisoned reader cannot consume a newly substituted valid stream.
    $sentinel=[IO.MemoryStream]::new([byte[]]@(123,125,10),$false)
    $reader.stream=$sentinel
    try { $null=Read-DataCopyControlLine $reader 1000 } catch {}
    if ($sentinel.Position -ne 0 -or $reader.fault -cne $case.reason) { throw 'Poisoned control reader was rearmed.' }
    $sentinel.Dispose();$stream.Dispose()
}
$stream=[IO.MemoryStream]::new([byte[]]@(123,125,10),$false)
$reader=New-DataCopyControlReader $stream $complete
$stream.Dispose()
try { $null=Read-DataCopyControlLine $reader 1000 } catch {}
if ($reader.fault -cne 'control-reader-unavailable') { throw 'Reader I/O refusal differs.' }
$stream=[IO.MemoryStream]::new([byte[]]@(123,125,10),$false)
$discard=[Threading.Tasks.Task]::FromException([IO.IOException]::new('authored discard refusal'))
$reader=New-DataCopyControlReader $stream $discard
try { $null=Read-DataCopyControlLine $reader 1000 } catch {}
if ($reader.fault -cne 'stderr-unavailable' -or $stream.Position -ne 0) { throw 'Discard I/O refusal differs.' }
$stream.Dispose()
# The exact overflow path and a broken failure publisher still retain a live owner.
$stream=[IO.MemoryStream]::new($utf8.GetBytes(('x'*8193)+"`n"),$false)
$reader=New-DataCopyControlReader $stream $complete
try { $null=Read-DataCopyControlLine $reader 1000 } catch {}
if ($reader.fault -cne 'control-overflow') { throw 'Expected fixed overflow is unavailable.' }
$script:held=$false;$script:ownerExitConfirmed=$false
$owned=@([pscustomobject]@{HasExited=$false})
function Write-DataCopyReceipt { throw 'authored failed receipt channel' }
function Wait-DataCopyRecovery { $script:held=$true;throw 'authored livehold sentinel' }
$Output=Join-Path ([IO.Path]::GetTempPath()) ('r19-unused-'+[guid]::NewGuid().ToString('N')+'.json')
try { Complete-DataCopyHarness $true } catch {}
if (-not $script:held) { throw 'Control overflow/receipt failure bypassed live owner hold.' }
$stream.Dispose()
''')


def test_powershell_resume_protocol_is_distinct_and_requires_exact_partial_revalidation(fixture, capsys):
    value = fixture.make(probe.RESUME_CASE)
    assert value.run() == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    cases = [{'probe_case': probe.RESUME_CASE, 'phase': event['phase'], 'event': event, 'accept': True} for event in events]
    partial = next(event for event in events if event['phase'] == 'copy-interrupted')
    for field, changed in [('schema', probe.SCHEMA), ('generation', 2), ('copy_attempts', 2),
            ('authored_interruptions', 2), ('partial_completed_files', 2), ('partial_revalidations', 0),
            ('same_plan_barrier_generation', False), ('copy_resumed', True), ('copy_attempts', True)]:
        cases.append({'probe_case': probe.RESUME_CASE, 'phase': 'copy-interrupted',
                      'event': {**partial, field: changed}, 'accept': False})
    cases.append({'probe_case': probe.CASE, 'phase': 'setup-closed',
        'event': {**events[0], 'schema': probe.SCHEMA, 'case': probe.CASE}, 'accept': False})
    verified = next(event for event in events if event['phase'] == 'copy-verified')
    cases.append({'probe_case': probe.RESUME_CASE, 'phase': 'copy-verified',
                  'event': {**verified, 'partial_revalidations': 1}, 'accept': False})
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['New-DataCopyControlReader','Read-DataCopyControlLine','Read-DataCopyEvent'], r'''
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$cases=[Console]::In.ReadToEnd() | ConvertFrom-Json
$index=0
foreach ($case in $cases) {
    $script:ProbeCase=$case.probe_case
    $bytes=[Text.UTF8Encoding]::new($false,$true).GetBytes(($case.event | ConvertTo-Json -Depth 8 -Compress)+"`n")
    $stream=[IO.MemoryStream]::new($bytes,$false)
    $script:controlReader=New-DataCopyControlReader $stream ([Threading.Tasks.Task]::CompletedTask)
    $accepted=$true
    try { Read-DataCopyEvent $case.phase } catch { $accepted=$false }
    if ($accepted -ne $case.accept) {
        [Console]::Out.WriteLine((@{schema='proxy-r19-data-copy-contract-failure-v1';case_index=$index;
            expected=[bool]$case.accept;actual=[bool]$accepted} | ConvertTo-Json -Compress))
        exit 2
    }
    $stream.Dispose();$index++
}
''', cases)


def test_powershell_wal_protocol_binds_real_set_and_dependency_to_the_correct_phase(fixture, capsys):
    value = fixture.make(probe.WAL_CASE)
    assert value.run() == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    cases = [{'probe_case': probe.WAL_CASE, 'phase': event['phase'], 'event': event, 'accept': True} for event in events]
    observed = next(event for event in events if event['phase'] == 'wal-set-observed')
    for field, changed in [('schema', probe.SCHEMA), ('sqlite_policy', True), ('sqlite_version', '/private-sentinel'),
            ('sqlite_version_scope', 'api-asserted'), ('transcript_wal_bytes', 32), ('transcript_shm_bytes', 0),
            ('transcript_wal_bytes', True), ('transcript_shm_bytes', 8388609), ('writers_signaled', 0),
            ('wal_dependency', 'main-only-false-full-set-true')]:
        cases.append({'probe_case': probe.WAL_CASE, 'phase': 'wal-set-observed',
                      'event': {**observed, field: changed}, 'accept': False})
    verified = next(event for event in events if event['phase'] == 'copy-verified')
    for field, changed in [('wal_dependency', 'not-run'), ('wal_files', 0), ('shm_files', 0),
                           ('target_activation', True), ('r19_complete', True)]:
        cases.append({'probe_case': probe.WAL_CASE, 'phase': 'copy-verified',
                      'event': {**verified, field: changed}, 'accept': False})
    setup = events[0]
    cases.append({'probe_case': probe.WAL_CASE, 'phase': 'setup-closed',
                  'event': {**setup, 'wal_set': 'nonempty-after-retained-signals'}, 'accept': False})
    for control in (probe.CASE, probe.RESUME_CASE):
        cases.append({'probe_case': control, 'phase': 'wal-set-observed', 'event': observed, 'accept': False})
    cases.append({'probe_case': probe.WAL_CASE, 'phase': 'copy-interrupted', 'event': observed, 'accept': False})
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['New-DataCopyControlReader','Read-DataCopyControlLine','Read-DataCopyEvent'], r'''
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$cases=[Console]::In.ReadToEnd() | ConvertFrom-Json
$index=0
foreach ($case in $cases) {
    $script:ProbeCase=$case.probe_case
    $bytes=[Text.UTF8Encoding]::new($false,$true).GetBytes(($case.event | ConvertTo-Json -Depth 8 -Compress)+"`n")
    $stream=[IO.MemoryStream]::new($bytes,$false)
    $script:controlReader=New-DataCopyControlReader $stream ([Threading.Tasks.Task]::CompletedTask)
    $accepted=$true
    try { Read-DataCopyEvent $case.phase } catch { $accepted=$false }
    if ($accepted -ne $case.accept) {
        [Console]::Out.WriteLine((@{schema='proxy-r19-data-copy-contract-failure-v1';case_index=$index;
            expected=[bool]$case.accept;actual=[bool]$accepted} | ConvertTo-Json -Compress))
        exit 2
    }
    $stream.Dispose();$index++
}
''', cases)


def test_powershell_grammar_protocol_requires_order_scope_and_real_populated_row(fixture, capsys):
    value = fixture.make(probe.GRAMMAR_CASE)
    assert value.run() == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    cases = [{'probe_case':probe.GRAMMAR_CASE,'phase':event['phase'],'event':event,'accept':True} for event in events]
    written = next(event for event in events if event['phase']=='grammar-written')
    for field, changed in [('schema',probe.SCHEMA),('reading_transport','arbitrary-remote-200'),
            ('grammar_credential_fixture','environment'),('grammar_baseline','not-run'),
            ('unknown_grammar_rule','not-run'),('grammar_written','not-run'),
            ('grammar_snapshot','one-scoped-choice-four'),('grammar_override_rows',1)]:
        cases.append({'probe_case':probe.GRAMMAR_CASE,'phase':'grammar-written','event':{**written,field:changed},'accept':False})
    verified = next(event for event in events if event['phase']=='copy-verified')
    for field, changed in [('grammar_override_rows',0),('grammar_override_rows',True),('grammar_override_rows',2),
            ('grammar_snapshot','not-run'),('grammar_restarted','four-with-local-override'),('r19_complete',True)]:
        cases.append({'probe_case':probe.GRAMMAR_CASE,'phase':'copy-verified','event':{**verified,field:changed},'accept':False})
    for control in (probe.CASE,probe.RESUME_CASE,probe.WAL_CASE):
        cases.append({'probe_case':control,'phase':'grammar-written','event':written,'accept':False})
    for wrong_phase in ('copy-interrupted','wal-set-observed'):
        cases.append({'probe_case':probe.GRAMMAR_CASE,'phase':wrong_phase,'event':written,'accept':False})
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script,['New-DataCopyControlReader','Read-DataCopyControlLine','Read-DataCopyEvent'],r'''
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$cases=[Console]::In.ReadToEnd() | ConvertFrom-Json
$index=0
foreach ($case in $cases) {
    $script:ProbeCase=$case.probe_case
    $bytes=[Text.UTF8Encoding]::new($false,$true).GetBytes(($case.event | ConvertTo-Json -Depth 8 -Compress)+"`n")
    $stream=[IO.MemoryStream]::new($bytes,$false)
    $script:controlReader=New-DataCopyControlReader $stream ([Threading.Tasks.Task]::CompletedTask)
    $accepted=$true
    try { Read-DataCopyEvent $case.phase } catch { $accepted=$false }
    if ($accepted -ne $case.accept) {
        [Console]::Out.WriteLine((@{schema='proxy-r19-data-copy-contract-failure-v1';case_index=$index;
            expected=[bool]$case.accept;actual=[bool]$accepted} | ConvertTo-Json -Compress))
        exit 2
    }
    $stream.Dispose();$index++
}
''',cases)


def test_powershell_grammar_receipt_cannot_omit_populated_row_or_extra_source_block():
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script,['Write-DataCopyReceipt'],r'''
$private=Join-Path ([IO.Path]::GetTempPath()) ('r19-authored-grammar-receipt-'+[guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $private
$slotSourceOperation=Join-Path $private 'source-fixture.ps1'
[IO.File]::WriteAllText($slotSourceOperation,'authored source-operation fixture')
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$script:ProbeCase='authored-data-copy-grammar';$Output=Join-Path $private 'grammar.json'
$walFiles=0;$shmFiles=0;$stage='release';$failureCategory='none'
try {
    foreach ($fault in @('missing-block','empty-choice','bool-choice','unverified')) {
        $sourceBlocks=10;$grammarRows=1;$grammarVerified=$true
        switch ($fault) {
            'missing-block' {$sourceBlocks=9}
            'empty-choice' {$grammarRows=0}
            'bool-choice' {$grammarRows=$true}
            'unverified' {$grammarVerified=$false}
        }
        $accepted=$true
        try { Write-DataCopyReceipt 'passed' } catch { $accepted=$false }
        if ($accepted -or (Test-Path -LiteralPath $Output)) { throw 'Grammar receipt accepted incomplete fixed proof.' }
    }
    $sourceBlocks=10;$grammarRows=1;$grammarVerified=$true
    Write-DataCopyReceipt 'passed'
    $value=Get-Content -LiteralPath $Output -Raw | ConvertFrom-Json
    if ($value.schema -cne 'proxy-r19-frozen-data-copy-grammar-receipt-v1' -or
        $value.case -cne 'authored-data-copy-grammar' -or
        $value.scope -cne 'authored-populated-local-grammar-copy-with-living-coordinator' -or
        $value.grammar_override_rows -ne 1 -or $value.grammar_baseline -cne 'zero-without-local-override' -or
        $value.grammar_snapshot -cne 'one-scoped-choice-four' -or $value.grammar_restarted -cne 'four-with-local-override' -or
        $value.unknown_grammar_rule -cne 'rejected-404' -or $value.reading_transport -cne 'fixed-mock-settings-analysis-only' -or
        $value.target_activation -or $value.production_activation -or $value.r19_complete -or
        $null -ne $value.PSObject.Properties['sqlite_policy'] -or $null -ne $value.PSObject.Properties['copy_resumed']) {
        throw 'Grammar receipt scope or gates changed.'
    }
} finally { Remove-Item -LiteralPath $private -Recurse -Force }
''')


def test_powershell_wal_receipt_refuses_missing_dependency_inputs_and_extra_block():
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['Write-DataCopyReceipt'], r'''
$private=Join-Path ([IO.Path]::GetTempPath()) ('r19-authored-wal-receipt-'+[guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $private
$slotSourceOperation=Join-Path $private 'source-fixture.ps1'
[IO.File]::WriteAllText($slotSourceOperation,'authored source-operation fixture')
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$script:ProbeCase='authored-data-copy-wal';$Output=Join-Path $private 'wal.json'
$sourceBlocks=9;$walFiles=1;$shmFiles=1;$sqliteVersion='3.50.4'
$transcriptWalBytes=12392;$transcriptShmBytes=32768;$stage='release';$failureCategory='none'
try {
    $accepted=$true
    try { Write-DataCopyReceipt 'passed' } catch { $accepted=$false }
    if ($accepted -or (Test-Path -LiteralPath $Output)) { throw 'WAL receipt omitted extra actual source block.' }
    $sourceBlocks=10
    foreach ($fault in @('wal-empty','shm-empty','overbound','bad-version')) {
        $transcriptWalBytes=12392;$transcriptShmBytes=32768;$sqliteVersion='3.50.4'
        switch ($fault) {
            'wal-empty' {$transcriptWalBytes=32}
            'shm-empty' {$transcriptShmBytes=0}
            'overbound' {$transcriptWalBytes=8388609}
            'bad-version' {$sqliteVersion='private-sentinel'}
        }
        $accepted=$true
        try { Write-DataCopyReceipt 'passed' } catch { $accepted=$false }
        if ($accepted -or (Test-Path -LiteralPath $Output)) { throw 'WAL receipt accepted invalid fixed proof inputs.' }
    }
    $transcriptWalBytes=12392;$transcriptShmBytes=32768;$sqliteVersion='3.50.4'
    Write-DataCopyReceipt 'passed'
    $value=Get-Content -LiteralPath $Output -Raw | ConvertFrom-Json
    if ($value.schema -cne 'proxy-r19-frozen-data-copy-wal-receipt-v1' -or $value.case -cne 'authored-data-copy-wal' -or
        $value.scope -cne 'authored-transcript-retained-wal-copy-with-living-coordinator' -or
        $value.wal_dependency -cne 'main-only-false-full-set-true' -or $value.wal_set -cne 'nonempty-after-retained-signals' -or
        $value.sqlite_version_scope -cne 'frozen-coordinator' -or $value.source_operation_blocked_observations -ne 10 -or
        $value.copy_model -cne 'one-plain-copy-without-injected-interruption' -or
        $value.target_activation -or $value.production_activation -or $value.r19_complete -or
        $null -ne $value.PSObject.Properties['authored_interruptions']) { throw 'WAL receipt scope or gate changed.' }
} finally { Remove-Item -LiteralPath $private -Recurse -Force }
''')


def test_powershell_resume_receipt_cannot_relabel_positive_case_or_omit_extra_source_block():
    script = Path(__file__).resolve().parents[2]/'scripts/probe-frozen-data-copy.ps1'
    _powershell_contract(script, ['Write-DataCopyReceipt'], r'''
$private=Join-Path ([IO.Path]::GetTempPath()) ('r19-authored-receipt-'+[guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $private
$slotSourceOperation=Join-Path $private 'source-fixture.ps1'
[IO.File]::WriteAllText($slotSourceOperation,'authored source-operation fixture')
$proof=[pscustomobject]@{source_commit=('a'*40);build_id='authored-data-copy-fixture'}
$sourceBlocks=9;$walFiles=0;$shmFiles=0;$stage='release';$failureCategory='none'
try {
    $script:ProbeCase='authored-data-copy';$Output=Join-Path $private 'positive.json'
    Write-DataCopyReceipt 'passed'
    $positive=Get-Content -LiteralPath $Output -Raw | ConvertFrom-Json
    if ($positive.schema -cne 'proxy-r19-frozen-data-copy-receipt-v1' -or $positive.case -cne 'authored-data-copy' -or
        $positive.scope -cne 'authored-transcript-copy-with-living-coordinator' -or
        $positive.source_operation_blocked_observations -ne 9 -or $null -ne $positive.PSObject.Properties['fault_model']) {
        throw 'The existing positive receipt changed meaning.'
    }
    $script:ProbeCase='authored-data-copy-resume';$Output=Join-Path $private 'resume.json'
    $accepted=$true
    try { Write-DataCopyReceipt 'passed' } catch { $accepted=$false }
    if ($accepted -or (Test-Path -LiteralPath $Output)) { throw 'Resume receipt omitted the extra actual source block.' }
    $sourceBlocks=10;Write-DataCopyReceipt 'passed'
    $resume=Get-Content -LiteralPath $Output -Raw | ConvertFrom-Json
    if ($resume.schema -cne 'proxy-r19-frozen-data-copy-resume-receipt-v1' -or $resume.case -cne 'authored-data-copy-resume' -or
        $resume.scope -cne 'authored-transcript-interrupted-copy-resume-with-living-coordinator' -or
        $resume.copy_attempts -ne 2 -or $resume.authored_interruptions -ne 1 -or $resume.partial_completed_files -ne 1 -or
        $resume.partial_revalidations -ne 2 -or $resume.resume_authority -cne 'same-live-owner-plan-barrier-generation-leases' -or
        $resume.target_activation -isnot [bool] -or $resume.target_activation -or $resume.production_activation -or $resume.r19_complete) {
        throw 'Fixed resume receipt scope or gates differ.'
    }
} finally { Remove-Item -LiteralPath $private -Recurse -Force }
''')
