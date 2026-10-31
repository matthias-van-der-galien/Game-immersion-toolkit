from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import closing
import sqlite3
import threading
from types import SimpleNamespace
import pytest

from backend.models import TextMatch
from backend.storage import (TranscriptStore, TranscriptConnectionCloseError, TranscriptStorePoisonedError,
                             TranscriptConnectionFence)
from backend.runtime_writers import WritersQuiescing


@pytest.fixture
def operation_connections(tmp_path, monkeypatch):
    """Actual SQLite objects observed only by the test; never a product registry."""
    raw = sqlite3.connect
    state = SimpleNamespace(opened=[], close_error=None, transaction_errors=[],
                            close_entered=None, close_release=None, threaded=False)
    class Observed(sqlite3.Connection):
        def __exit__(self, *args):
            try: return super().__exit__(*args)
            except BaseException as error:
                state.transaction_errors.append(error)
                raise
        def close(self):
            self.close_calls += 1
            if state.close_entered is not None:
                state.close_entered.set()
                assert state.close_release.wait(5), 'Owned close was not released.'
            if state.close_error is not None: raise state.close_error
            super().close()
            self.closed_cleanly = True
    def connect(*args, **options):
        if state.threaded:
            # Test-only observation/disposal; product connections retain their
            # original default thread check and thread-confined operation.
            options['check_same_thread'] = False
        connection = raw(*args, factory=Observed, **options)
        connection.close_calls, connection.closed_cleanly = 0, False
        state.opened.append(connection)
        return connection
    monkeypatch.setattr(sqlite3, 'connect', connect)
    state.path, state.raw = tmp_path/'owned-transcript.db', raw
    yield state
    # Explicit disposal of this test's failed fixtures only, after assertions.
    for connection in state.opened:
        if not connection.closed_cleanly: sqlite3.Connection.close(connection)


def _owned_match(**updates):
    return TextMatch(text_id='owned-row', game='zzz', english='Owned caption', chinese='合成记录',
        source_ocr='合成记录', score=1, kind='exact', source_locale='zh-Hans', source_text='合成记录',
        texts={'zh-Hans':'合成记录','en':'Owned caption'}, **updates)


@pytest.mark.parametrize('operation', ['get','update_audio','set_favorite','update_speaker','delete','prune',
    'purge_unvoiced','audio_path','list','list_favorites','count','hito','recent','recent-non-chinese'])
def test_real_operation_connections_close_once_on_reads_writes_and_early_returns(operation_connections, operation):
    state = operation_connections
    store = TranscriptStore(state.path)
    match = _owned_match()
    line = store.add(match, 'owned-session')
    if operation == 'get': assert store.get(line.id).texts == line.texts
    elif operation == 'update_audio': store.update_audio(line.id, 'owned-audio-alias.wav', True)
    elif operation == 'set_favorite': store.set_favorite(line.id, True)
    elif operation == 'update_speaker': store.update_speaker(line.id, 'Owned speaker', '合成人物')
    elif operation == 'delete': store.delete(line.id)
    elif operation == 'prune': store.prune(0)
    elif operation == 'purge_unvoiced': store.purge_unvoiced()
    elif operation == 'audio_path': store.audio_path(line.id)
    elif operation == 'list': assert store.list()[0].chinese == '合成记录'
    elif operation == 'list_favorites': store.list_favorites()
    elif operation == 'count': assert store.count() == 1
    elif operation == 'hito': store.add_or_touch_hito(match.model_copy(update={'game':'hito'}), 'owned-session')
    elif operation == 'recent': assert store.add_or_upgrade_recent(match, 'owned-session') == (None, False)
    else:
        other = match.model_copy(update={'source_locale':'en','source_text':'Owned caption','text_id':'owned-en'})
        store.add_or_upgrade_recent(other, 'owned-session')
        assert store.add_or_upgrade_recent(other, 'owned-session') == (None, False)
    assert not store._connection_failures
    for connection in state.opened:
        assert connection.close_calls == 1 and connection.closed_cleanly
        with pytest.raises(sqlite3.ProgrammingError, match='closed'): connection.execute('SELECT 1')


def test_operation_body_exception_rolls_back_and_closes_without_replacing_error(operation_connections):
    state = operation_connections
    store = TranscriptStore(state.path)
    line = store.add(_owned_match(), 'owned-session')
    body = RuntimeError('authored body fault')
    with pytest.raises(RuntimeError) as raised:
        with store._connection_scope() as connection:
            connection.execute('UPDATE transcript_lines SET favorite=1 WHERE id=?', (line.id,))
            raise body
    assert raised.value is body
    assert state.opened[-1].close_calls == 1 and state.opened[-1].closed_cleanly
    with closing(state.raw(state.path)) as check:
        assert check.execute('SELECT favorite FROM transcript_lines').fetchone()[0] == 0
    fence = store.freeze_connections(0)
    fence.check(store)
    store.resume_connections(fence)


def test_initialization_sql_failure_closes_its_real_connection(operation_connections, monkeypatch):
    state = operation_connections
    with closing(state.raw(state.path)):
        pass
    monkeypatch.setattr(TranscriptStore, '_connect', lambda _store:
        sqlite3.connect(state.path.as_uri()+'?mode=ro', uri=True))
    with pytest.raises(sqlite3.OperationalError): TranscriptStore(state.path)
    assert len(state.opened) == 1
    assert state.opened[0].close_calls == 1 and state.opened[0].closed_cleanly


@pytest.mark.parametrize('fault', ['initialize','success','body','transaction-exit','body-and-transaction-exit'])
def test_failed_close_retains_actual_owner_errors_and_refuses_reopen_without_retry(operation_connections, fault):
    state = operation_connections
    close_error, body_error = OSError('authored close fault'), RuntimeError('authored body fault')
    if fault != 'initialize': store = TranscriptStore(state.path)
    if fault == 'body-and-transaction-exit':
        with store._connection_scope() as connection:
            connection.execute('CREATE TABLE owned_rollback (id INTEGER)')
    state.close_error = close_error
    with pytest.raises(TranscriptConnectionCloseError) as raised:
        if fault == 'initialize': TranscriptStore(state.path)
        elif fault == 'success': store.count()
        elif fault in {'body','body-and-transaction-exit'}:
            with store._connection_scope() as connection:
                if fault == 'body-and-transaction-exit':
                    connection.execute('INSERT INTO owned_rollback VALUES (1)')
                    connection.set_authorizer(lambda action, first, *_:
                        sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_TRANSACTION and first == 'ROLLBACK' else sqlite3.SQLITE_OK)
                else: connection.execute('SELECT 1')
                raise body_error
        else:
            with store._connection_scope() as connection:
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('CREATE TABLE owned_parent (id INTEGER PRIMARY KEY)')
                connection.execute('CREATE TABLE owned_child (id INTEGER REFERENCES owned_parent(id) DEFERRABLE INITIALLY DEFERRED)')
                connection.execute('INSERT INTO owned_child VALUES (1)')
    failure = raised.value
    assert failure.connection is state.opened[-1] and failure.close_error is close_error
    assert failure.connection.close_calls == 1 and failure.store._connection_failures == [failure]
    assert failure.body_error is (body_error if fault in {'body','body-and-transaction-exit'} else None)
    if fault == 'transaction-exit':
        assert failure.transaction_error is state.transaction_errors[-1]
        assert isinstance(failure.transaction_error, sqlite3.IntegrityError)
        assert failure.connection.execute('SELECT COUNT(*) FROM owned_child').fetchone()[0] == 0
    elif fault == 'body-and-transaction-exit':
        assert failure.transaction_error is state.transaction_errors[-1]
        assert isinstance(failure.transaction_error, sqlite3.DatabaseError)
    else: assert failure.transaction_error is None
    assert failure.connection.execute('SELECT 1').fetchone()[0] == 1
    opened = len(state.opened)
    with pytest.raises(TranscriptStorePoisonedError) as refused: failure.store.count()
    assert refused.value.failure is failure and len(state.opened) == opened and failure.connection.close_calls == 1


def test_repeated_poison_refusals_leave_original_failure_traceback_and_sql_ownership_bounded(operation_connections):
    state = operation_connections
    store = TranscriptStore(state.path)
    state.close_error = OSError('authored close fault')
    with pytest.raises(TranscriptConnectionCloseError) as raised: store.count()
    failure = raised.value
    traceback = failure.__traceback__
    opened = len(state.opened)
    previous = None
    for _ in range(100):
        with pytest.raises(TranscriptStorePoisonedError) as refused: store.count()
        assert refused.value is not previous and refused.value.failure is failure
        assert refused.value.__cause__ is failure and failure.__traceback__ is traceback
        assert str(refused.value) == 'Transcript store cleanup remains unconfirmed.'
        assert len(state.opened) == opened and failure.connection.close_calls == 1
        assert store._connection_failures == [failure] and failure.close_error is state.close_error
        previous = refused.value


def test_real_commit_failure_rolls_back_and_closes(operation_connections):
    state = operation_connections
    store = TranscriptStore(state.path)
    with pytest.raises(sqlite3.IntegrityError) as raised:
        with store._connection_scope() as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('CREATE TABLE owned_parent (id INTEGER PRIMARY KEY)')
            connection.execute('CREATE TABLE owned_child (id INTEGER REFERENCES owned_parent(id) DEFERRABLE INITIALLY DEFERRED)')
            connection.execute('INSERT INTO owned_child VALUES (1)')
    assert raised.value is state.transaction_errors[-1]
    assert state.opened[-1].close_calls == 1 and state.opened[-1].closed_cleanly
    assert not store._connection_failures
    fence = store.freeze_connections(0)
    store.resume_connections(fence)


def _thread_call(operation):
    state = SimpleNamespace(done=threading.Event(), value=None, error=None)
    def call():
        try: state.value = operation()
        except BaseException as error: state.error = error
        finally: state.done.set()
    state.thread = threading.Thread(target=call)
    state.thread.start()
    return state


def _observe_admission_stop(store, monkeypatch):
    stopped = threading.Event()
    original = store._connections_gate.stop_admission
    def stop():
        original()
        stopped.set()
    monkeypatch.setattr(store._connections_gate, 'stop_admission', stop)
    return stopped


def test_connection_fence_waits_for_real_transaction_and_close_before_resuming(operation_connections, monkeypatch):
    state = operation_connections
    store = TranscriptStore(state.path)
    line = store.add(_owned_match(), 'owned-session')
    state.threaded = True
    body_entered, body_release = threading.Event(), threading.Event()
    state.close_entered, state.close_release = threading.Event(), threading.Event()
    stopped = _observe_admission_stop(store, monkeypatch)
    def update():
        with store._connection_scope() as connection:
            connection.execute('UPDATE transcript_lines SET favorite=1 WHERE id=?', (line.id,))
            body_entered.set()
            assert body_release.wait(5)
    operation = _thread_call(update)
    freezer = None
    try:
        assert body_entered.wait(2)
        freezer = _thread_call(lambda: store.freeze_connections(4))
        assert stopped.wait(2)
        opened = len(state.opened)
        with pytest.raises(WritersQuiescing): store.count()
        assert len(state.opened) == opened and not freezer.done.is_set()
        body_release.set()
        assert state.close_entered.wait(2)
        assert not freezer.done.is_set(), 'SQL commit alone must not complete the fence.'
        state.close_release.set()
        assert operation.done.wait(2) and freezer.done.wait(2)
        assert operation.error is None and freezer.error is None
        fence = freezer.value
        fence.check(store)
        assert state.opened[-1].closed_cleanly and state.opened[-1].close_calls == 1
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            state.opened[-1].execute('SELECT 1')
        with pytest.raises(WritersQuiescing): store.get(line.id)
        original_resume = store._connections_gate.resume
        def resume():
            # Actual new operation is still refused at the point the old token
            # is invalidated, before the underlying admission gate opens.
            with pytest.raises(ValueError): store._check_connection_fence(fence)
            with pytest.raises(WritersQuiescing): store.count()
            original_resume()
        monkeypatch.setattr(store._connections_gate, 'resume', resume)
        store.resume_connections(fence)
        with pytest.raises(ValueError): fence.check(store)
        assert store.get(line.id).favorite is True and store.get(line.id).chinese == '合成记录'
    finally:
        body_release.set(); state.close_release.set()
        operation.thread.join(5)
        if freezer is not None: freezer.thread.join(5)
        assert not operation.thread.is_alive() and (freezer is None or not freezer.thread.is_alive())


def test_freeze_timeout_retains_closed_admission_until_actual_scope_completion(operation_connections):
    state = operation_connections
    store = TranscriptStore(state.path)
    state.threaded = True
    entered, release = threading.Event(), threading.Event()
    def read():
        with store._connection_scope() as connection:
            connection.execute('SELECT COUNT(*) FROM transcript_lines').fetchone()
            entered.set()
            assert release.wait(5)
    operation = _thread_call(read)
    try:
        assert entered.wait(2)
        with pytest.raises(TimeoutError): store.freeze_connections(.02)
        assert store._connections_fence is None and not operation.done.is_set()
        opened = len(state.opened)
        with pytest.raises(WritersQuiescing): store.count()
        with pytest.raises(ValueError): store.resume_connections(None)
        assert len(state.opened) == opened
        release.set()
        assert operation.done.wait(2) and operation.error is None
        fence = store.freeze_connections(1)
        fence.check(store)
        store.resume_connections(fence)
        assert store.count() == 0
    finally:
        release.set(); operation.thread.join(5)
        assert not operation.thread.is_alive()


def test_concurrent_short_freezer_is_bounded_while_another_waits_on_real_close(operation_connections, monkeypatch):
    state = operation_connections
    store = TranscriptStore(state.path)
    state.threaded = True
    state.close_entered, state.close_release = threading.Event(), threading.Event()
    stopped = _observe_admission_stop(store, monkeypatch)
    operation = _thread_call(store.count)
    long_freezer = short_freezer = None
    try:
        assert state.close_entered.wait(2)
        long_freezer = _thread_call(lambda: store.freeze_connections(4))
        assert stopped.wait(2)
        short_freezer = _thread_call(lambda: store.freeze_connections(.02))
        assert short_freezer.done.wait(2), 'A short freeze must not wait for the long freezer budget.'
        assert isinstance(short_freezer.error, TimeoutError)
        assert not long_freezer.done.is_set() and not operation.done.is_set()
        state.close_release.set()
        assert operation.done.wait(2) and long_freezer.done.wait(2)
        assert operation.error is None and long_freezer.error is None
        assert store.freeze_connections(0) is long_freezer.value
        store.resume_connections(long_freezer.value)
    finally:
        state.close_release.set(); operation.thread.join(5)
        if long_freezer is not None: long_freezer.thread.join(5)
        if short_freezer is not None: short_freezer.thread.join(5)
        assert not operation.thread.is_alive()
        assert long_freezer is None or not long_freezer.thread.is_alive()
        assert short_freezer is None or not short_freezer.thread.is_alive()


def test_serialization_time_consumes_the_same_freeze_drain_budget(operation_connections, monkeypatch):
    # Deterministic clock advancement at an actual lock boundary, without a
    # timing sleep or replacing the gate's real closed-admission behavior.
    from backend import storage
    state = operation_connections
    store = TranscriptStore(state.path)
    clock = SimpleNamespace(now=100.0)
    lock = store._connections_lock
    class ObservedLock:
        def acquire(self, *, timeout):
            assert timeout == pytest.approx(1.0)
            acquired = lock.acquire(timeout=timeout)
            clock.now += .75
            return acquired
        def release(self): lock.release()
    observed = []
    original = store._connections_gate._condition.acquire
    def acquire(*, timeout):
        observed.append(timeout)
        acquired = original(timeout=timeout)
        if len(observed) == 2: clock.now += .3
        return acquired
    monkeypatch.setattr(storage, 'time', SimpleNamespace(monotonic=lambda: clock.now))
    monkeypatch.setattr(store, '_connections_lock', ObservedLock())
    monkeypatch.setattr(store._connections_gate._condition, 'acquire', acquire)
    with pytest.raises(TimeoutError): store.freeze_connections(1)
    assert observed == [pytest.approx(.25), pytest.approx(.25)] and store._connections_fence is None
    with pytest.raises(WritersQuiescing): store.count()


def test_freeze_timeout_bounds_gate_contention_after_admission_and_drain_begin(operation_connections, monkeypatch):
    state = operation_connections
    store = TranscriptStore(state.path)
    state.threaded = True
    state.close_entered, state.close_release = threading.Event(), threading.Event()
    stopped = _observe_admission_stop(store, monkeypatch)
    held, release = threading.Event(), threading.Event()
    operation = _thread_call(store.count)
    holder = freezer = None
    def hold_after_stop():
        assert stopped.wait(2)
        with store._connections_gate._condition:
            held.set()
            assert release.wait(5)
    try:
        assert state.close_entered.wait(2)
        holder = _thread_call(hold_after_stop)
        freezer = _thread_call(lambda: store.freeze_connections(.05))
        assert held.wait(2), 'The condition holder must enter after freeze closes admission.'
        assert freezer.done.wait(.5), 'Late condition reacquisition must still respect the total freeze budget.'
        assert isinstance(freezer.error, TimeoutError)
        assert not holder.done.is_set() and not operation.done.is_set()
        assert store._connections_fence is None and not store._connections_gate._accepting
    finally:
        release.set(); state.close_release.set()
        operation.thread.join(5)
        if holder is not None: holder.thread.join(5)
        if freezer is not None: freezer.thread.join(5)
        assert not operation.thread.is_alive()
        assert holder is None or not holder.thread.is_alive()
        assert freezer is None or not freezer.thread.is_alive()
    assert holder.error is None and operation.error is None
    fence = store.freeze_connections(0)
    store.resume_connections(fence)
    assert store.count() == 0


@pytest.mark.parametrize('held_lock', ['failure', 'gate'])
def test_freeze_budget_also_bounds_failure_and_gate_lock_entry(tmp_path, held_lock):
    store = TranscriptStore(tmp_path/'owned.db')
    lock = store._failure_lock if held_lock == 'failure' else store._connections_gate._condition
    held, release = threading.Event(), threading.Event()
    def hold():
        with lock:
            held.set()
            assert release.wait(5)
    holder = _thread_call(hold)
    freezer = None
    try:
        assert held.wait(2)
        freezer = _thread_call(lambda: store.freeze_connections(.02))
        assert freezer.done.wait(2), 'The same freeze budget must cover each lock acquisition.'
        assert isinstance(freezer.error, TimeoutError) and not holder.done.is_set()
        assert store._connections_fence is None
    finally:
        release.set(); holder.thread.join(5)
        if freezer is not None: freezer.thread.join(5)
        assert not holder.thread.is_alive() and (freezer is None or not freezer.thread.is_alive())
    assert holder.error is None
    fence = store.freeze_connections(0)
    store.resume_connections(fence)
    assert store.count() == 0


def test_failed_real_close_cannot_mint_or_resume_a_connection_fence(operation_connections, monkeypatch):
    state = operation_connections
    store = TranscriptStore(state.path)
    state.threaded = True
    state.close_entered, state.close_release = threading.Event(), threading.Event()
    state.close_error = OSError('authored close fault')
    stopped = _observe_admission_stop(store, monkeypatch)
    operation = _thread_call(store.count)
    freezer = None
    try:
        assert state.close_entered.wait(2)
        freezer = _thread_call(lambda: store.freeze_connections(4))
        assert stopped.wait(2)
        state.close_release.set()
        assert operation.done.wait(2) and freezer.done.wait(2)
        failure = operation.error
        assert isinstance(failure, TranscriptConnectionCloseError)
        assert isinstance(freezer.error, TranscriptStorePoisonedError) and freezer.error.failure is failure
        assert failure.connection is state.opened[-1] and failure.close_error is state.close_error
        assert store._connections_fence is None and store._connection_failures == [failure]
        opened, traceback = len(state.opened), failure.__traceback__
        for _ in range(3):
            with pytest.raises(TranscriptStorePoisonedError) as refused: store.freeze_connections(0)
            assert refused.value.failure is failure
            with pytest.raises(TranscriptStorePoisonedError) as refused: store.resume_connections(None)
            assert refused.value.failure is failure
        assert len(state.opened) == opened and failure.connection.close_calls == 1
        assert failure.__traceback__ is traceback
    finally:
        state.close_release.set(); operation.thread.join(5)
        if freezer is not None: freezer.thread.join(5)
        assert not operation.thread.is_alive() and (freezer is None or not freezer.thread.is_alive())


def test_connection_fence_tokens_are_store_epoch_and_issued_object_bound(tmp_path):
    first, second = TranscriptStore(tmp_path/'first.db'), TranscriptStore(tmp_path/'second.db')
    fence = first.freeze_connections(0)
    assert type(fence) is TranscriptConnectionFence and first.freeze_connections(0) is fence
    forged = TranscriptConnectionFence(first, fence._epoch)
    for invalid in (None, True, forged):
        with pytest.raises(ValueError): first.resume_connections(invalid)
    with pytest.raises(ValueError): forged.check(first)
    with pytest.raises(ValueError): fence.check(second)
    with pytest.raises(ValueError): second.resume_connections(fence)
    fence.check(first)
    first.resume_connections(fence)
    replacement = first.freeze_connections(0)
    with pytest.raises(ValueError): fence.check(first)
    with pytest.raises(ValueError): first.resume_connections(fence)
    replacement.check(first)
    first.resume_connections(replacement)
    assert first.count() == second.count() == 0


@pytest.mark.parametrize('timeout', [True, False, None, '1', -1, float('nan'), float('inf'),
    -float('inf'), 10**1000, threading.TIMEOUT_MAX*2])
def test_invalid_connection_freeze_timeout_does_not_close_admission(tmp_path, timeout):
    store = TranscriptStore(tmp_path/'owned.db')
    with pytest.raises(ValueError): store.freeze_connections(timeout)
    assert store._connections_fence is None and store.count() == 0


def test_connection_freeze_accepts_zero_poll_and_native_wait_limit(tmp_path):
    store = TranscriptStore(tmp_path/'owned.db')
    for timeout in (0.0, 1, threading.TIMEOUT_MAX):
        fence = store.freeze_connections(timeout)
        fence.check(store)
        store.resume_connections(fence)
    assert store.count() == 0


def test_connection_fence_does_not_certify_physical_sqlite_resource_release(tmp_path):
    store = TranscriptStore(tmp_path/'owned.db')
    with store._connection_scope() as connection:
        assert connection.execute('PRAGMA journal_mode=DELETE').fetchone()[0] == 'delete'
        connection.execute('CREATE TABLE owned_cursor_rows (id INTEGER)')
        connection.executemany('INSERT INTO owned_cursor_rows VALUES (?)', [(1,), (2,)])
    cursor = None
    try:
        with store._connection_scope() as connection:
            cursor = connection.execute('SELECT id FROM owned_cursor_rows')
            assert cursor.fetchone()[0] == 1  # Authored private-scope escape, not a store API result.
        fence = store.freeze_connections(0)
        fence.check(store)
        with pytest.raises(sqlite3.ProgrammingError, match='closed'): connection.execute('SELECT 1')
        with closing(sqlite3.connect(store.path, timeout=0)) as independent:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                independent.execute('BEGIN EXCLUSIVE')
        # A valid operation token did not imply all sqlite3_close_v2 resources
        # were finalized. No resource-release assertion follows fixture disposal.
        store.resume_connections(fence)
    finally:
        cursor = None  # Dispose this test's authored escape only, never product proof.


def test_transcript_round_trip(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    match = TextMatch(
        text_id="dialogue_1",
        english="Stay close to me.",
        chinese="跟紧我。",
        source_ocr="Stay close to me",
        score=100,
        kind="exact",
    )
    created = store.add(match, "session-a")

    lines = store.list()
    assert lines == [created]
    assert store.count() == 1
    assert store.count("session-a") == 1
    assert store.count("session-b") == 0


def test_game_histories_are_partitioned(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    zzz = TextMatch(
        text_id="zzz-line", english="A shared line.", chinese="一句台词。",
        source_ocr="A shared line.", score=100, kind="exact",
    )
    pragmata = TextMatch(
        game="pragmata", text_id="pragmata-line", english="A shared line.",
        chinese="一句台词。", source_ocr="A shared line.", score=100, kind="exact",
        speaker_english="Ken", speaker_chinese="肯",
    )
    first, _ = store.add_or_upgrade_recent(zzz, "session-a")
    second, _ = store.add_or_upgrade_recent(pragmata, "session-a")
    assert first is not None and second is not None
    assert store.list(game="zzz") == [first]
    assert store.list(game="pragmata") == [second]
    assert second.speaker_english == "Ken"
    assert second.speaker_chinese == "肯"


def test_transcript_channel_migrates_and_round_trips(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    match = TextMatch(
        text_id="Tips_1",
        english="Obtain an S-Rank in the previous battle.",
        chinese="在上次战斗中取得S级评价。",
        source_ocr="Obtain an S-Rank in the previous battle.",
        score=100,
        kind="exact",
    )
    created = store.add(match, "session-a", channel="tip")
    assert created.channel == "tip"
    assert store.list()[0].channel == "tip"
    updated = store.update_audio(created.id, f"{created.id}.mp3", voiced=True)
    assert updated is not None
    assert updated.voiced is True
    assert updated.has_audio is True
    assert store.audio_path(created.id) == f"{created.id}.mp3"
    labelled = store.update_speaker(created.id, "Belle", "铃")
    assert labelled is not None
    assert labelled.speaker_english == "Belle"
    assert labelled.speaker_chinese == "铃"


def test_partial_line_is_upgraded_and_recent_duplicates_are_skipped(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    started = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    partial = TextMatch(
        text_id="line_short",
        english='What is "reinforce the seal" supposed to mean?',
        chinese="「加固封印」是什么意思？",
        source_ocr='What is "reinforce the seal" supposed to mean?',
        score=89.2,
        kind="fuzzy",
    )
    complete = TextMatch(
        text_id="line_complete",
        english=(
            'What is "reinforce the seal" supposed to mean? '
            "Wasn't that part of his over-the-top delusions?"
        ),
        chinese="「加固封印」是什么意思？这竟然不是它的中二病妄想吗。",
        source_ocr=(
            'What is "reinforce the seal" supposed to mean? '
            "Wasn't that part of his over-the-top delusions?"
        ),
        score=100,
        kind="exact",
    )

    first, upgraded = store.add_or_upgrade_recent(partial, "session-a", created_at=started)
    assert first is not None and upgraded is False
    replacement, upgraded = store.add_or_upgrade_recent(
        complete, "session-a", created_at=started + timedelta(seconds=1.5)
    )
    assert replacement is not None and upgraded is True
    assert replacement.id == first.id
    assert replacement.english == complete.english
    assert store.count() == 1

    duplicate, upgraded = store.add_or_upgrade_recent(
        complete, "session-a", created_at=started + timedelta(seconds=3)
    )
    assert duplicate is None and upgraded is False
    assert store.count() == 1


def test_suffix_fragment_after_complete_line_is_skipped(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    started = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    complete = TextMatch(
        text_id="complete",
        english="But that's not important. We should start looking for the prototype.",
        chinese="不过现在就不说这些了，我们还是赶快开始找原型机吧。",
        source_ocr="Ben But that's not important. We should start looking for the prototype.",
        score=100,
        kind="exact",
    )
    fragment = TextMatch(
        text_id="fragment",
        english="The prototype?",
        chinese="「原型机」？",
        source_ocr="the prototype.",
        score=100,
        kind="exact",
    )
    line, _ = store.add_or_upgrade_recent(complete, "session-a", created_at=started)
    assert line is not None
    skipped, upgraded = store.add_or_upgrade_recent(
        fragment, "session-a", created_at=started + timedelta(seconds=12)
    )
    assert skipped is None and upgraded is False
    assert store.count() == 1


def test_suffix_seen_first_is_replaced_by_complete_line(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    started = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    fragment = TextMatch(
        text_id="fragment",
        english="The prototype?",
        chinese="「原型机」？",
        source_ocr="the prototype.  ?",
        score=100,
        kind="exact",
    )
    complete = TextMatch(
        text_id="complete",
        english="But that's not important. We should start looking for the prototype.",
        chinese="不过现在就不说这些了，我们还是赶快开始找原型机吧。",
        source_ocr="But that's not important. We should start looking for the prototype.",
        score=92,
        kind="fuzzy",
    )
    first, upgraded = store.add_or_upgrade_recent(fragment, "session-a", created_at=started)
    assert first is not None and upgraded is False
    replacement, upgraded = store.add_or_upgrade_recent(
        complete, "session-a", created_at=started + timedelta(seconds=2)
    )
    assert replacement is not None and upgraded is True
    assert replacement.id == first.id
    assert replacement.english == complete.english
    assert store.count() == 1


def test_adjacent_duplicate_ignores_punctuation_and_spacing(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    started = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    first = TextMatch(
        text_id="variant-a",
        english="The prototype?",
        chinese="「原型机」？",
        source_ocr="The prototype?",
        score=100,
        kind="exact",
    )
    punctuation_variant = TextMatch(
        text_id="variant-b",
        english="The prototype.  ?",
        chinese="「原型机」？",
        source_ocr="The prototype.  ?",
        score=100,
        kind="exact",
    )
    line, _ = store.add_or_upgrade_recent(first, "session-a", created_at=started)
    assert line is not None
    duplicate, upgraded = store.add_or_upgrade_recent(
        punctuation_variant, "session-a", created_at=started + timedelta(seconds=3)
    )
    assert duplicate is None and upgraded is False
    assert store.count() == 1


def test_prune_keeps_favorites_plus_fifty_recent_lines(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    favorite_id = None
    for index in range(53):
        line = store.add(
            TextMatch(
                text_id=f"line-{index}",
                english=f"Spoken sentence number {index}.",
                chinese=f"句子{index}。",
                source_ocr=f"Spoken sentence number {index}.",
                score=100,
                kind="exact",
            ),
            "session-a",
        )
        store.update_audio(line.id, f"{line.id}.mp3", voiced=True)
        if index == 0:
            favorite_id = line.id
            store.set_favorite(line.id, True)

    removed = store.prune(keep_nonfavorite=50)
    assert len(removed) == 2
    assert favorite_id is not None
    favorite = store.get(favorite_id)
    assert favorite is not None and favorite.favorite is True
    assert store.count() == 51


def test_list_favorites_returns_all_favorites_newest_first(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    match = TextMatch(
        text_id="favorite",
        english="Keep this spoken line.",
        chinese="保存这句台词。",
        source_ocr="Keep this spoken line.",
        score=100,
        kind="exact",
    )
    first = store.add(match.model_copy(update={"text_id": "favorite-a"}), "session-a")
    store.add(match.model_copy(update={"text_id": "ordinary"}), "session-a")
    last = store.add(match.model_copy(update={"text_id": "favorite-b"}), "session-b")
    store.set_favorite(first.id, True)
    store.set_favorite(last.id, True)

    favorites = store.list_favorites()

    assert [line.id for line in favorites] == [last.id, first.id]
    assert all(line.favorite for line in favorites)


def test_purge_unvoiced_keeps_confirmed_subtitles_and_favorites(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    match = TextMatch(
        text_id="line",
        english="A spoken line.",
        chinese="一句台词。",
        source_ocr="A spoken line.",
        score=100,
        kind="exact",
    )
    unvoiced = store.add(match.model_copy(update={"text_id": "unvoiced"}), "session-a")
    voiced = store.add(match.model_copy(update={"text_id": "voiced"}), "session-a")
    favorite = store.add(match.model_copy(update={"text_id": "favorite"}), "session-a")
    cinematic = store.add(
        match.model_copy(update={"text_id": "cinematic"}),
        "session-a",
        channel="cinematic",
    )
    store.update_audio(voiced.id, f"{voiced.id}.mp3", voiced=True)
    store.update_audio(cinematic.id, None, voiced=True)
    pending = store.add(match.model_copy(update={"text_id": "pending"}), "session-a")
    store.update_audio(pending.id, None, voiced=True)
    store.set_favorite(favorite.id, True)

    removed_ids = {line_id for line_id, _ in store.purge_unvoiced()}
    assert unvoiced.id in removed_ids
    assert favorite.id not in removed_ids
    assert store.get(voiced.id) is not None
    assert store.get(cinematic.id) is not None
    assert store.get(favorite.id) is not None
    assert store.get(pending.id).audio_source == "original"


def test_only_zzz_cinematic_comic_ids_are_exempt_from_voice_cleanup(tmp_path) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    match = TextMatch(text_id="Comic_" + "b" * 32, english="Please wait here.",
                      chinese="请在这里等。", source_ocr="Please wait here.", score=100, kind="exact")
    comic = store.add(match, "session", channel="cinematic")
    wrong_channel = store.add(match, "session", channel="dialogue")
    wrong_game = store.add(match.model_copy(update={"game": "pragmata"}), "session", channel="cinematic")
    video = store.add(match.model_copy(update={"text_id": "Video_" + "c" * 32}), "session", channel="cinematic")
    invalid = store.add(match.model_copy(update={"text_id": "Comic_not-an-official-id"}), "session", channel="cinematic")
    removed = {line_id for line_id, _ in store.purge_unvoiced()}
    assert removed == {wrong_channel.id, wrong_game.id, video.id, invalid.id}
    assert TranscriptStore(store.path).get(comic.id) is not None


@pytest.mark.parametrize("previous_comic,incoming_comic,previous_text,incoming_text", [
    (False, True, "Please stay here.", "Please stay here. We will return tomorrow."),
    (True, True, "Please stay here.", "Please stay here. We will return tomorrow."),
    (True, True, "Please stay here. We will return tomorrow.", "Please stay here."),
    (True, True, "Please stay here.", "Please stay here!"),
    (True, False, "Please stay here.", "Please stay here. We will return tomorrow."),
    (False, True, "Please stay here. We will return tomorrow.", "Please stay here."),
])
def test_comic_identity_preserves_independent_bubbles_and_prior_audio(
    tmp_path, previous_comic, incoming_comic, previous_text, incoming_text,
) -> None:
    store = TranscriptStore(tmp_path / "transcript.db")
    started = datetime.now(timezone.utc)
    first = TextMatch(text_id="Comic_" + "a" * 32 if previous_comic else "GalGame_previous",
                      english=previous_text, chinese="请在这里等。", source_ocr=previous_text, score=100, kind="exact")
    previous = store.add(first, "session", created_at=started,
                         channel="cinematic" if previous_comic else "dialogue")
    store.update_audio(previous.id, "original-previous.mp3", True)
    store.set_favorite(previous.id, True)
    second = first.model_copy(update={
        "text_id": "Comic_" + "b" * 32 if incoming_comic else "GalGame_next",
        "english": incoming_text, "source_ocr": incoming_text, "chinese": "我们明天会回来。"})
    channel = "cinematic" if incoming_comic else "dialogue"
    incoming, upgraded = store.add_or_upgrade_recent(
        second, "session", created_at=started + timedelta(seconds=1), channel=channel)
    assert incoming is not None and incoming.id != previous.id and not upgraded
    unchanged = store.get(previous.id)
    assert unchanged.english == previous_text and unchanged.chinese == first.chinese
    assert unchanged.voiced and unchanged.favorite and unchanged.has_audio
    assert store.audio_path(previous.id) == "original-previous.mp3"
    assert store.add_or_upgrade_recent(
        second, "session", created_at=started + timedelta(seconds=2), channel=channel) == (None, False)
    assert store.count() == 2
