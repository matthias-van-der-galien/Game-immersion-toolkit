import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from backend import api
from backend.models import AppSettings, CaptureSnapshot
from backend.runtime_writers import RuntimeWriterGate
from backend.storage import TranscriptStore


def test_browser_snapshot_does_not_block_capture_event_loop(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    events = []

    def slow_status():
        started.set()
        assert release.wait(2)
        return {'capture': {'active_game': 'hito'}}

    class Socket:
        async def send_json(self, value):
            events.append(value)

        async def receive_text(self):
            raise WebSocketDisconnect()

    class Hub:
        async def connect(self, socket):
            pass

        async def disconnect(self, socket):
            pass

    monkeypatch.setattr(api, 'runtime', SimpleNamespace(status=slow_status, hub=Hub(),
                       request_writers=RuntimeWriterGate()), raising=False)

    async def check():
        task = asyncio.create_task(api.websocket_endpoint(Socket()))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            assert not task.done()
        finally:
            release.set()
        await task

    asyncio.run(check())
    assert events[0]['snapshot']['capture']['active_game'] == 'hito'


class _SnapshotSocket:
    def __init__(self):
        self.accepted, self.events, self.closed = False, [], []

    async def accept(self):
        self.accepted = True

    async def send_json(self, event):
        self.events.append(event)

    async def receive_text(self):
        raise WebSocketDisconnect()

    async def close(self, *, code):
        assert self.accepted
        self.closed.append(code)


@pytest.mark.parametrize('outcome', ['success', 'status-error', 'cancelled-waiter'])
def test_websocket_sql_status_scope_survives_async_cancel_and_balances_on_error(tmp_path, monkeypatch, outcome):
    store = TranscriptStore(tmp_path/'owned-transcript.db')
    release = threading.Event()
    gate, hub, socket = RuntimeWriterGate(), api.EventHub(), _SnapshotSocket()
    context = {'runtime_id': 'authored-runtime', 'state_version': 1, 'account_generation': 0}
    async def run():
        loop = asyncio.get_running_loop()
        entered, finished = asyncio.Event(), asyncio.Event()
        thread_ids = []
        def status():
            thread_ids.append(threading.get_ident())
            try:
                with store._connection_scope() as connection:
                    total = connection.execute('SELECT COUNT(*) FROM transcript_lines').fetchone()[0]
                    loop.call_soon_threadsafe(entered.set)
                    assert release.wait(5)
                    if outcome == 'status-error':
                        raise RuntimeError('authored status failure')
                return {'context': context, 'total': total}
            finally:
                loop.call_soon_threadsafe(finished.set)
        monkeypatch.setattr(api, 'runtime', SimpleNamespace(status=status, hub=hub, request_writers=gate), raising=False)
        task = asyncio.create_task(api.websocket_endpoint(socket))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            assert thread_ids == [thread_ids[0]] and thread_ids[0] != threading.get_ident()
            assert socket in hub.clients
            gate.stop_admission()
            with pytest.raises(TimeoutError): gate.wait_drained(0)
            if outcome == 'cancelled-waiter':
                task.cancel()
                with pytest.raises(asyncio.CancelledError): await task
                assert socket not in hub.clients
                with pytest.raises(TimeoutError): gate.wait_drained(0)
                assert not finished.is_set()
            release.set()
            await asyncio.wait_for(finished.wait(), 2)
            gate.wait_drained(1)  # Real worker scope, including SQLite close, must leave.
            if outcome != 'cancelled-waiter': await task
            assert hub.clients == set()
            if outcome == 'success':
                assert socket.events == [{'type': 'snapshot', 'snapshot': {'context': context, 'total': 0},
                                          'context': context}]
            else:
                assert socket.events == []
            assert store.count() == 0  # No account or remote service is invoked.
        finally:
            release.set()
            if not task.done(): task.cancel()
            try: await task
            except asyncio.CancelledError: pass
    asyncio.run(run())


def test_queued_websocket_status_cannot_enter_after_stop_and_resume(tmp_path, monkeypatch):
    store = TranscriptStore(tmp_path/'owned-transcript.db')
    release = threading.Event()
    gate, hub, socket = RuntimeWriterGate(), api.EventHub(), _SnapshotSocket()
    calls = []
    async def run():
        loop = asyncio.get_running_loop()
        blocker_started, snapshot_queued = asyncio.Event(), asyncio.Event()
        class ObservedExecutor(ThreadPoolExecutor):
            def __init__(self):
                super().__init__(max_workers=1)
                self.submissions = 0
            def submit(self, *args, **options):
                future = super().submit(*args, **options)
                self.submissions += 1
                if self.submissions == 2: snapshot_queued.set()
                return future
        pool = ObservedExecutor()
        loop.set_default_executor(pool)
        def block():
            loop.call_soon_threadsafe(blocker_started.set)
            assert release.wait(5)
        def status():
            calls.append('status')
            return {'total': store.count()}
        monkeypatch.setattr(api, 'runtime', SimpleNamespace(status=status, hub=hub, request_writers=gate), raising=False)
        blocker = loop.run_in_executor(None, block)
        task = None
        try:
            await asyncio.wait_for(blocker_started.wait(), 2)
            task = asyncio.create_task(api.websocket_endpoint(socket))
            await asyncio.wait_for(snapshot_queued.wait(), 2)
            assert socket in hub.clients and calls == []
            gate.stop_admission()
            gate.wait_drained(0)  # No actual status operation has started yet.
            gate.resume()
            release.set()
            await blocker
            await asyncio.wait_for(task, 2)
            assert calls == [] and socket.events == [] and socket.closed == [1013]
            assert hub.clients == set()
            gate.enter(gate.capture_ticket()); gate.leave()  # Fresh epoch remains usable.
        finally:
            release.set()
            await blocker
            if task is not None:
                if not task.done(): task.cancel()
                try: await task
                except asyncio.CancelledError: pass
    asyncio.run(run())


def test_websocket_captures_one_runtime_gate_status_and_hub_before_connect(monkeypatch):
    gate, other_gate = RuntimeWriterGate(), RuntimeWriterGate()
    other_hub, socket, calls = api.EventHub(), _SnapshotSocket(), []
    other_client = object()
    other_hub.clients.add(other_client)
    def original_status():
        calls.append('original-status')
        gate.stop_admission()
        with pytest.raises(TimeoutError): gate.wait_drained(0)
        return {'authored': True}
    other = SimpleNamespace(hub=other_hub, request_writers=other_gate,
                            status=lambda: pytest.fail('Replacement runtime status must not run.'))
    class SwitchingHub(api.EventHub):
        async def connect(self, websocket):
            await super().connect(websocket)
            original.request_writers = other_gate
            original.status = lambda: pytest.fail('A later status replacement must not run.')
            monkeypatch.setattr(api, 'runtime', other)
    hub = SwitchingHub()
    original = SimpleNamespace(hub=hub, request_writers=gate, status=original_status)
    monkeypatch.setattr(api, 'runtime', original, raising=False)
    asyncio.run(api.websocket_endpoint(socket))
    assert calls == ['original-status'] and socket.events == [{'type': 'snapshot', 'snapshot': {'authored': True}}]
    assert hub.clients == set() and other_hub.clients == {other_client}
    gate.wait_drained(0); other_gate.wait_drained(0)


@pytest.mark.parametrize('failure', ['error', 'cancel'])
def test_websocket_disconnects_bound_hub_even_when_connect_does_not_finish(monkeypatch, failure):
    gate, socket = RuntimeWriterGate(), _SnapshotSocket()
    error = OSError('authored connect failure') if failure == 'error' else asyncio.CancelledError()
    class FailingHub(api.EventHub):
        async def connect(self, websocket):
            await super().connect(websocket)
            raise error
    hub = FailingHub()
    monkeypatch.setattr(api, 'runtime', SimpleNamespace(hub=hub, request_writers=gate,
                       status=lambda: pytest.fail('No status may start after failed connect.')), raising=False)
    with pytest.raises(type(error)) as raised:
        asyncio.run(api.websocket_endpoint(socket))
    assert raised.value is error and hub.clients == set() and socket.events == []
    gate.wait_drained(0)


def test_status_exposes_hito_capture_and_text_index():
    runtime = object.__new__(api.Runtime)
    runtime.capture = SimpleNamespace(session_id='test', snapshot=lambda: CaptureSnapshot(active_game='hito'))
    for name in ('textmaps', 'pragmata'):
        setattr(runtime, name, SimpleNamespace(status=lambda: {}))
    runtime.voice_assets = SimpleNamespace(ready=True, status=lambda: {})
    runtime.pragmata_voice_assets = SimpleNamespace(ready=True, status=lambda: {})
    runtime.game_indexes = {"cyberpunk": SimpleNamespace(status=lambda: {"ready": True, "entry_count": 12})}
    runtime.game_voice_assets = {"cyberpunk": SimpleNamespace(ready=True, status=lambda: {})}
    runtime.hito = SimpleNamespace(status=lambda: {
        'ready': True, 'state': 'ready', 'message': 'ready', 'entry_count': 123,
    })
    runtime.settings = SimpleNamespace(get=AppSettings)
    runtime.update_status = lambda: {}
    runtime.transcript = SimpleNamespace(count=lambda session_id=None: 2 if session_id else 30)

    runtime.languages = SimpleNamespace(selected=lambda *_: None)
    runtime.accounts = SimpleNamespace(generation=0, status=lambda: {'active':'legacy'})
    runtime.state_version = api.StateVersion()
    status = runtime.status()
    assert status['capture']['active_game'] == 'hito'
    assert status['game_textmaps']['hito']['entry_count'] == 123
    assert status['session'] == {'id': 'test', 'line_count': 2, 'total_line_count': 30}


def test_hito_update_endpoint_refreshes_last_detected_archive(monkeypatch):
    hito = SimpleNamespace(
        refresh=lambda: True,
        status=lambda: {'ready': True, 'entry_count': 321},
    )
    monkeypatch.setattr(api, 'runtime', SimpleNamespace(hito=hito), raising=False)

    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        api.update_hito_text()
    assert error.value.status_code == 410
