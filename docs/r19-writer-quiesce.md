# R19 runtime writer quiesce boundary

The explicit local `/api/runtime/quiesce?writers=true` and
`/api/runtime/activate?writers=true` protocol accounts for application writers
before returning capture handoff state. The default endpoints retain the source
updater's existing capture-only handoff, including its recovery behavior; they
do not close HTTP admission or impose the new Hito writer gate. Neither protocol
returns a store-copy proof. The strict protocol advances C2 of the
[completion plan](r19-completion-plan.md). The supervising host/update transaction
and native Windows acceptance remain open. Frozen automatic updates and production runtime activation retain
their existing disabled gates. No installer is built.

## Admission, drain and recovery

The strict protocol closes ordinary HTTP admission and keeps admitted requests counted
through their final response body, including streaming responses. GET requests
are included because reading/lookup/setup endpoints can write caches or consume
folder-picker results. Health, readiness and the authenticated local handoff
controls remain available. Existing local-access and account isolation checks
still apply; an idle read-only WebSocket is not a writer barrier.

The initial WebSocket status snapshot is a known store-accessing producer. Its
endpoint captures one Runtime, hub, bound status function and writer gate before
the first await. It also captures an opaque process-local admission ticket while
that gate is accepting. The actual status worker enters the gate with that
ticket inside its thread and leaves only after the full status operation ends.
Cancelling/disconnecting the async waiter cannot decrement that active scope
early. Cleanup disconnects the same captured hub, including cancellation and
partially completed connection setup.

Stopping admission retires all earlier tickets. A queued pre-stop snapshot
refuses status/SQL even if its thread starts after a later resume. Tickets bind
the exact gate and opaque epoch, are not serialized or stored in a successful
ticket registry, and do not increase the active count merely by being captured.
They are epoch bindings, not one-use operation IDs. Ordinary unticketed HTTP/
source admission retains its existing behavior. A valid local WebSocket refused
by this gate completes acceptance before closing with retryable code 1013;
untrusted Host/Origin still receives middleware code 1008 before acceptance or
status access.

The shared lifecycle lock serializes quiesce and activation. A strict
quiesce attempt has the existing 30-second budget. A timed-out or disconnected
waiter retains the real cleanup task. Activation refuses while that task or a
retired preparation/worker generation still runs. Recovery reopens ordinary
HTTP admission only after worker recovery and update/capture activation. A failed
native capture stop retains its control and session state; strict recovery
retries that actual stop before resuming executors or capture. An unresolved
native stop keeps strict recovery unavailable.

The lifecycle covers these existing producers:

| Producer | Drain or explicit refusal |
| --- | --- |
| Admitted HTTP work | Wait through ASGI completion; new ordinary requests receive 503 while closed |
| Initial WebSocket status | Count the actual status thread; retire its queued ticket on admission stop, including across resume |
| Manual mobile exports and pickers | Close admission; refuse live monitor/process, picker or asynchronous cancellation work |
| Automatic export destination picker | Refuse an active picker before stopping the existing automatic-export service |
| Native setup/tool preparation | Close admission; join the actual tool thread and native-completion callbacks, including refresh work after process exit |
| Language preparation | Reuse its generation/publication locks, bounded close and cleanup-failure handling; recovery requires the retired workers to finish |
| Background update/index jobs | Await the existing close/index/map operations and check their tracked thread/process liveness |
| Reading lookups | Close the executor and join actual worker exit, including cache-writing Future callbacks |
| Capture/OCR | Stop capture and retain/drain current and timed-out retired OCR executors |
| Voice decoding and transcript audio publication | Drain every legacy/current/locale voice executor, then await queued capture publication coroutines that can enrich stored speakers |
| Hito grammar/cache worker | Refuse handoff while its tracked preparation thread or subprocess remains live; a supervising shutdown/restart adapter remains required |

An export's `cancelled` status, an exited setup process, a done Future, standby,
health and OCR readiness cannot substitute for those waits. Failed cleanup
keeps admission closed until explicit strict activation/recovery succeeds. A
strict handoff cannot be recovered with a default capture-only activation: both
calls must opt into `writers=true`. The default source updater does not opt in
and remains usable with a live Hito worker. Under the strict protocol an active
Hito grammar worker prevents successful handoff until its supervising adapter
exists. The code does not start a native process termination operation merely to manufacture a
successful handoff.

## Limits and remaining gates

A return from quiesce is capture handoff state, not independent authorization to
copy settings, databases or credentials. The synthetic migration coordinator
still requires its own synthetic proof and does not accept this response as a
production barrier. No live migration or account write is exercised here.
The WebSocket fix covers this one initial status producer, not every future
message/queued callback, active socket or mutable resource. Its ticket does not
prove physical connection/cursor/file closure, a complete RuntimeDataFence,
whole-process signaling, a safe copied-store cutover or preserved OCR warmth.

Existing export/update cancellation and several game/legacy native processes
still lack complete supervising host ownership. Checking their tracked process
and thread is necessary but does not establish descendant exit, prevent PID
reuse, cover detached legacy updaters, or retain a lease across crash/restart.
The Hito refusal deliberately leaves its integration unavailable. The source
updater's nested-lock/detached transaction is not approved for frozen updates.

Completion-plan C1–C4 and E still require an extracted compiler-free entry host,
Windows owned-handle/Job Object integration, continuous legacy exclusion,
verified immutable-slot takeover and route publication, native failure/crash
recovery, protected TEST credentials, copied-store continuity and real browser
profile/reconnect evidence. Windows 10/11 native checks remain explicit and
unavailable on a macOS development host. Component rights, durable source
supply, notices and maintenance approval remain separate prerequisites.

## Focused regressions

`backend/tests/test_runtime_writers.py` exercises real blocked threads, a Future
whose callback still writes after `done()`, response streaming, retired OCR
workers, post-process native refresh, cancelled export labels, queued capture
publications, activation serialization and disconnected handoff waiters.
It also checks wrong-gate/type and retired admission tickets without changing
ordinary unticketed admission. `test_hito_api.py` uses real SQLite and controlled
thread Events for snapshot cancellation/error balance, queued execution after
stop-plus-resume, and binding/cleanup of the original Runtime and hub.
`test_local_access.py` exercises the actual ASGI acceptance/1013 ordering and
preserved pre-dispatch Host/Origin refusal. Account side effects are mocked;
these source tests introduce no new native runtime receipt.
`test_runtime_handoff.py` exercises the existing endpoint ordering and explicit
Hito refusal, default source compatibility and rejection of a default-protocol
bypass. `test_preparation_cancellation.py` retains capture/session identity
through failed drain, delayed recovery and restarted preparation.

The related local-access, reading, capture, setup and manual/automatic export
suites remain necessary. These authored fixtures are behavioral regressions;
they are not Windows process-tree or protected-store acceptance evidence.
