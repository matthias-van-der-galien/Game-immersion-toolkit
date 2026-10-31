"""Request admission and actual drain for runtime handoff.

This is one producer boundary, not native process ownership or permission to
copy stores. Runtime.quiesce_writers also settles its registered background
producers before returning the existing capture handoff.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass

class WritersQuiescing(RuntimeError):
    pass


@dataclass(frozen=True, eq=False, repr=False)
class RuntimeAdmissionTicket:
    """Opaque process-local gate/epoch binding, never copy or root authority."""
    _gate: RuntimeWriterGate
    _epoch: object


_UNTICKETED = object()


class QuiesceableExecutor(Executor):
    """Keep actual worker/callback ownership across a bounded handoff wait."""
    def __init__(self, max_workers, *, thread_name_prefix=''):
        self._options = {'max_workers': max_workers, 'thread_name_prefix': thread_name_prefix}
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(**self._options)
        self._accepting = True
        self._drained = self._drain_error = self._drain_thread = None

    def submit(self, function, /, *args, **kwargs):
        with self._lock:
            if not self._accepting:
                raise WritersQuiescing('This runtime worker is quiescing.')
            return self._pool.submit(function, *args, **kwargs)

    def shutdown(self, wait=True, *, cancel_futures=False):
        with self._lock:
            self._accepting = False
            pool = self._pool
        pool.shutdown(wait=wait, cancel_futures=cancel_futures)

    def quiesce(self, timeout):
        with self._lock:
            if self._drained is None:
                self._accepting = False
                event = self._drained = threading.Event()
                pool = self._pool
                def drain():
                    try:
                        # Worker exit follows its Future callbacks. A done
                        # future or cancelled asyncio waiter alone is weaker.
                        pool.shutdown(wait=True, cancel_futures=False)
                    except BaseException as error:
                        self._drain_error = error
                    finally:
                        event.set()
                self._drain_thread = threading.Thread(target=drain, name='runtime-worker-drain', daemon=True)
                self._drain_thread.start()
            event = self._drained
        if not event.wait(max(0, timeout)):
            raise TimeoutError('Runtime worker/callback cleanup has not finished.')
        if self._drain_error is not None:
            raise TimeoutError('Runtime worker cleanup could not be confirmed.') from self._drain_error

    def resume(self):
        with self._lock:
            if self._drained is None:
                return
            if not self._drained.is_set() or self._drain_error is not None:
                raise TimeoutError('Runtime worker cleanup is still incomplete; retry recovery.')
            self._pool = ThreadPoolExecutor(**self._options)
            self._accepting = True
            self._drained = self._drain_error = self._drain_thread = None


class RuntimeWriterGate:
    def __init__(self):
        self._condition = threading.Condition()
        self._accepting = True
        self._active = 0
        self._epoch = object()

    def capture_ticket(self):
        with self._condition:
            if not self._accepting:
                raise WritersQuiescing('Runtime handoff is stopping writers. Retry after activation or recovery.')
            return RuntimeAdmissionTicket(self, self._epoch)

    def enter(self, ticket=_UNTICKETED):
        with self._condition:
            if not self._accepting:
                raise WritersQuiescing('Runtime handoff is stopping writers. Retry after activation or recovery.')
            if ticket is not _UNTICKETED and (type(ticket) is not RuntimeAdmissionTicket
                    or ticket._gate is not self or ticket._epoch is not self._epoch):
                raise WritersQuiescing('This runtime operation belongs to a retired admission epoch.')
            self._active += 1

    def leave(self):
        with self._condition:
            if not self._active:
                raise RuntimeError('Unbalanced runtime request writer scope.')
            self._active -= 1
            self._condition.notify_all()

    def stop_admission(self):
        with self._condition:
            self._accepting = False
            self._epoch = object()  # Retire queued pre-stop work even after resume.

    def wait_drained(self, timeout):
        deadline = time.monotonic() + max(0, timeout)
        with self._condition:
            while self._active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Active runtime requests have not finished; handoff is unavailable.')
                self._condition.wait(remaining)

    def resume(self):
        with self._condition:
            self._accepting = True


class RuntimeWriterMiddleware:
    # These operations do not mutate stores, or are the explicit local handoff
    # control path. In particular, reading/lookup/status/setup GETs are *not*
    # assumed read-only: they may publish caches or finish native pickers.
    _control = {'/api/health', '/api/runtime/ready', '/api/runtime/quiesce', '/api/runtime/activate'}

    def __init__(self, app, current_runtime):
        self.app, self.current_runtime = app, current_runtime

    async def __call__(self, scope, receive, send):
        current = self.current_runtime()
        gate = getattr(current, 'request_writers', None)
        if scope['type'] != 'http' or scope.get('path') in self._control or gate is None:
            await self.app(scope, receive, send)
            return
        try:
            gate.enter()
        except WritersQuiescing as error:
            from starlette.responses import JSONResponse
            await JSONResponse({'detail': str(error)}, status_code=503, headers={'Retry-After': '1'})(scope, receive, send)
            return
        try:
            # Pure ASGI scope includes body/stream completion, unlike a
            # call_next middleware that can return before response work ends.
            await self.app(scope, receive, send)
        finally:
            gate.leave()
