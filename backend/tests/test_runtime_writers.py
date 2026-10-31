"""Real thread/request drain cases missing from synthetic coordinator fixtures."""
import asyncio
from types import SimpleNamespace
import threading

import pytest

from backend.runtime_writers import QuiesceableExecutor, RuntimeWriterGate, RuntimeWriterMiddleware, WritersQuiescing


def test_admission_tickets_bind_gate_and_epoch_and_retire_across_resume():
    gate, other = RuntimeWriterGate(), RuntimeWriterGate()
    ticket = gate.capture_ticket()
    for rejected in (None, True, {}, other.capture_ticket()):
        with pytest.raises(WritersQuiescing): gate.enter(rejected)
    gate.wait_drained(0)
    gate.enter(ticket)
    gate.stop_admission()
    with pytest.raises(WritersQuiescing): gate.capture_ticket()
    with pytest.raises(WritersQuiescing): gate.enter(ticket)
    with pytest.raises(TimeoutError): gate.wait_drained(0)
    gate.leave()
    gate.wait_drained(0)
    gate.resume()
    with pytest.raises(WritersQuiescing): gate.enter(ticket)
    replacement = gate.capture_ticket()
    gate.enter(replacement); gate.leave()
    gate.enter(); gate.leave()  # Legacy unticketed admission remains usable.
    gate.stop_admission(); gate.stop_admission(); gate.resume()
    with pytest.raises(WritersQuiescing): gate.enter(replacement)
    gate.wait_drained(0)


def test_done_future_callback_must_finish_before_resume_or_drain_proof():
    work_release, callback_entered, callback_release = threading.Event(), threading.Event(), threading.Event()
    pool = QuiesceableExecutor(1)
    try:
        future = pool.submit(lambda: work_release.wait(3))
        def callback(_):
            callback_entered.set()
            assert callback_release.wait(3)
        future.add_done_callback(callback)
        work_release.set()
        assert callback_entered.wait(1) and future.done()
        with pytest.raises(TimeoutError): pool.quiesce(.01)
        with pytest.raises(WritersQuiescing): pool.submit(lambda: None)
        with pytest.raises(TimeoutError): pool.resume()
        callback_release.set()
        pool.quiesce(1)
        pool.resume()
        assert pool.submit(lambda: 'resumed').result(timeout=1) == 'resumed'
    finally:
        work_release.set(); callback_release.set()
        pool.shutdown()


def test_request_scope_includes_stream_completion_and_blocks_cache_writing_gets():
    async def run():
        gate = RuntimeWriterGate()
        started, finish = asyncio.Event(), asyncio.Event()
        calls, output = [], []
        async def app(scope, receive, send):
            calls.append(scope['path'])
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            if scope['path'] == '/api/lines/1/reading':
                await send({'type': 'http.response.body', 'body': b'first', 'more_body': True})
                started.set(); await finish.wait()
            await send({'type': 'http.response.body', 'body': b'finished'})
        middleware = RuntimeWriterMiddleware(app, lambda: SimpleNamespace(request_writers=gate))
        async def receive(): return {'type': 'http.request'}
        async def send(message): output.append(message)
        scope = {'type': 'http', 'path': '/api/lines/1/reading', 'method': 'GET'}
        old = asyncio.create_task(middleware(scope, receive, send))
        await started.wait()
        gate.stop_admission()
        try:
            with pytest.raises(TimeoutError): await asyncio.to_thread(gate.wait_drained, .01)
            output.clear()
            await middleware(scope, receive, send)
            assert output[0]['status'] == 503
            assert calls == ['/api/lines/1/reading']
            output.clear()
            await middleware({**scope, 'path': '/api/health'}, receive, send)
            assert output[0]['status'] == 200
        finally:
            finish.set(); await old
        await asyncio.to_thread(gate.wait_drained, 1)
        gate.resume()
        gate.enter(); gate.leave()
    asyncio.run(run())


def test_timed_out_handoff_owns_its_real_thread_and_refuses_early_recovery():
    from backend.api import Runtime
    async def run():
        entered, release = threading.Event(), threading.Event()
        runtime = Runtime.__new__(Runtime)
        runtime._handoff_drains = []
        def write():
            entered.set(); assert release.wait(3)
        try:
            with pytest.raises(TimeoutError):
                await runtime._handoff_step(write, __import__('time').monotonic()+.02, blocking=True)
            assert entered.is_set() and not runtime._handoff_drains[0].done()
            with pytest.raises(TimeoutError): runtime.resume_writers()
            release.set()
            await runtime._handoff_drains[0]
        finally:
            release.set()
    asyncio.run(run())


def test_retired_ocr_thread_is_retained_until_quiesce_and_recovery_finish(tmp_path):
    from backend.tests.test_subtitle_capture import fixture_service
    capture, _, _, _ = fixture_service(tmp_path)
    retired = QuiesceableExecutor(1)
    entered, release = threading.Event(), threading.Event()
    def old_native():
        entered.set(); assert release.wait(3)
    retired.submit(old_native)
    assert entered.wait(1)
    retired.shutdown(wait=False, cancel_futures=True)
    capture._retired_executors.append(retired)
    try:
        with pytest.raises(TimeoutError): asyncio.run(capture.quiesce(.02))
        with pytest.raises(TimeoutError): capture.resume_workers()
        release.set(); retired.quiesce(1)
        capture.resume_workers()
        assert capture._executor.submit(lambda: 'new native work').result(timeout=1) == 'new native work'
    finally:
        release.set(); retired.shutdown(); capture._executor.shutdown()


def test_manual_export_cancelled_label_cannot_hide_a_live_writer(tmp_path, monkeypatch):
    from backend.mobile_export_controls import MobileExportManager
    manager = MobileExportManager(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def export():
        entered.set(); assert release.wait(3)
    worker = manager._thread = threading.Thread(target=export)
    worker.start(); assert entered.wait(1)
    manager._status['state'] = 'cancelled'
    monkeypatch.setattr(manager, 'cancel', lambda: pytest.fail('Handoff must not infer native cleanup from cancel'))
    try:
        with pytest.raises(TimeoutError): manager.quiesce()
        assert manager.start('zzz') is False
    finally:
        release.set(); worker.join(1)
    manager.quiesce()
    manager.resume()


def test_setup_process_exit_does_not_precede_its_write_callback(tmp_path, monkeypatch):
    from backend import installation
    from backend.config import SettingsStore
    entered, release = threading.Event(), threading.Event()
    def refresh(_game):
        entered.set(); assert release.wait(3)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    service = installation.InstallationService(tmp_path,
        settings=SettingsStore(tmp_path/'settings.json'), game_state=lambda _: {},
        refresh=refresh, account_configured=lambda: False, install_lookup=lambda _: None)
    process = SimpleNamespace(wait=lambda: 0, poll=lambda: 0)
    monkeypatch.setattr(installation, 'load_paths', lambda: {'zzz': 'authored-folder'})
    worker = threading.Thread(target=service._native_finished, args=('folders', process, {}))
    service._native_threads.add(worker); service._native['folders'] = process
    worker.start(); assert entered.wait(1)
    try:
        with pytest.raises(TimeoutError): service.quiesce(.01)
        assert service.prepare('zzz') is False
    finally:
        release.set(); worker.join(1)
    service.quiesce(1); service.resume()


def test_queued_capture_publication_is_still_owned_after_native_worker_returns(tmp_path):
    from backend.tests.test_subtitle_capture import fixture_service
    capture, _, _, _ = fixture_service(tmp_path)
    async def run():
        capture._event_loop = asyncio.get_running_loop()
        entered, release = asyncio.Event(), asyncio.Event()
        async def persist():
            entered.set()
            await release.wait()
        capture._queue_publication(persist())
        await entered.wait()
        draining = asyncio.create_task(capture.drain_publications())
        await asyncio.sleep(0)
        assert not draining.done()
        release.set()
        await draining
        assert not capture._publications
    try:
        asyncio.run(run())
    finally:
        capture._executor.shutdown()


def test_activation_serializes_with_the_complete_quiesce_operation():
    from backend.api import Runtime
    from backend.runtime_handoff import CaptureHandoff
    async def run():
        runtime = Runtime.__new__(Runtime)
        runtime._handoff_lock, runtime._writer_handoff = asyncio.Lock(), True
        calls = []
        runtime.resume_writers = lambda: calls.append('resume')
        runtime._handoff_drains = []
        runtime.capture = SimpleNamespace(snapshot=lambda: SimpleNamespace(running=True), native_stop_pending=False)
        runtime.start_updates = lambda: calls.append('updates')
        runtime.admit_requests = lambda: calls.append('admit')
        await runtime._handoff_lock.acquire()
        activating = asyncio.create_task(runtime.activate_handoff(CaptureHandoff(running=True), writers=True))
        await asyncio.sleep(0)
        assert calls == [] and not activating.done()
        runtime._handoff_lock.release()
        assert await activating == {'active': True}
        assert calls == ['resume', 'updates', 'admit']
    asyncio.run(run())


def test_disconnected_handoff_waiter_does_not_cancel_the_actual_drain():
    from backend.api import Runtime
    import time
    async def run():
        entered, release = threading.Event(), threading.Event()
        runtime = Runtime.__new__(Runtime)
        runtime._handoff_drains = []
        def write():
            entered.set()
            assert release.wait(3)
        waiting = asyncio.create_task(runtime._handoff_step(write, time.monotonic()+2, blocking=True))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError): await waiting
            assert not runtime._handoff_drains[0].done()
            with pytest.raises(TimeoutError): runtime.resume_writers()
        finally:
            release.set()
            await runtime._handoff_drains[0]
    asyncio.run(run())


def test_failed_native_cleanup_retains_ownership_and_blocks_strict_activation(tmp_path, monkeypatch):
    from backend import api
    from backend.runtime_handoff import CaptureHandoff
    from backend.tests.test_subtitle_capture import fixture_service
    capture, _, _, _ = fixture_service(tmp_path)
    failing, calls = [True], []
    def stop_native():
        calls.append('native-stop')
        if failing[0]:
            raise TimeoutError('Synthetic background cleanup is incomplete')
    control = SimpleNamespace(stop=stop_native)
    capture._background_capture._control = control
    monkeypatch.setattr(capture, 'start', lambda: calls.append('capture-start'))
    async def run():
        capture._update_snapshot(running=True)
        capture._task = asyncio.create_task(asyncio.sleep(100))
        with pytest.raises(TimeoutError): await capture.quiesce(.2)
        assert capture._task is None and not capture.snapshot().running
        assert capture.native_stop_pending and capture._background_capture._control is control
        with pytest.raises(TimeoutError): capture.resume_workers()
        runtime = api.Runtime.__new__(api.Runtime)
        runtime._handoff_lock, runtime._writer_handoff, runtime._handoff_drains = asyncio.Lock(), True, []
        runtime.capture = capture
        def resume():
            calls.append('resume')
            capture.resume_workers()
        runtime.resume_writers = resume
        runtime.start_updates = lambda: calls.append('updates')
        runtime.admit_requests = lambda: calls.append('admit')
        payload = CaptureHandoff(running=True)
        with pytest.raises(TimeoutError): await runtime.activate_handoff(payload, writers=True)
        assert calls == ['native-stop', 'native-stop']
        assert capture._background_capture._control is control and runtime._writer_handoff
        failing[0] = False
        assert await runtime.activate_handoff(payload, writers=True) == {'active': True}
        assert capture._background_capture._control is None and not capture.native_stop_pending
        assert calls == ['native-stop', 'native-stop', 'native-stop', 'resume', 'capture-start', 'updates', 'admit']
    try:
        asyncio.run(run())
    finally:
        capture._executor.shutdown()


@pytest.mark.parametrize('strict', [False, True])
def test_index_drain_is_explicit_without_changing_source_cancellation(strict):
    from backend.api import Runtime
    async def run():
        release = asyncio.Event()
        index = asyncio.create_task(release.wait())
        idle = SimpleNamespace(close=lambda: None)
        runtime = SimpleNamespace(_updates_started=True, languages=idle, repair_task=None,
            index_task=index, update_manager=idle, pragmata_updater=idle, game_updaters={})
        stopping = asyncio.create_task(Runtime.stop_updates(runtime, drain=strict))
        await asyncio.sleep(.01)
        try:
            if strict:
                assert not stopping.done() and not index.cancelled()
            else:
                await stopping
                assert index.cancelled()
        finally:
            release.set()
            await stopping
        assert runtime.index_task is None
    asyncio.run(run())
