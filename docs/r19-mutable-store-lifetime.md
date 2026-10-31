# R19 transcript connection-operation fence

Status: implemented programmatic source boundary with local SQLite/thread
regressions; no new frozen/native runtime receipt or full mutable-root detach
acceptance. The [completion plan](r19-completion-plan.md) and
[R18 host contract](r18-storage-host-contract.md) retain their existing gates.
This change builds no installer and changes no source updater, schema, settings
mapping, account, shared component or PR #59 behavior.

`TranscriptStore.freeze_connections(timeout)` closes admission to that store's
normal SQL connection-operation scopes, waits for their transaction exit and
actual `Connection.close()` return, then returns a typed
`TranscriptConnectionFence`. The existing request admission mechanism is reused
at this underlying store boundary; capture/publication/speaker callers do not
need to arrive through an HTTP request to be counted. Ordinary behavior is
unchanged while the new programmatic API is unused. There is no HTTP/CLI control
path or production caller for it.

The token binds the exact issuing store, issued token object and local admission
epoch. `fence.check(store)` refuses a different store, a manually constructed
token, stale epoch, reopened admission, active scopes or retained failed-close
ownership. `store.resume_connections(fence)` invalidates the old token before
opening admission and advances the epoch. Repeated successful freeze while the
same fence is current returns that checked object. There is no force-resume,
data-path setter, root replacement, database reopen, copy permission or owner
reconstruction from metadata.

Use one finite, non-boolean int/float timeout between zero and Python's native
`threading.TIMEOUT_MAX`. One monotonic deadline covers waiting for freeze/resume
serialization, gate/failure-lock acquisition and operation drain; phases do not
receive fresh budgets. Zero requests an immediate, nonblocking poll. A short
concurrent freezer cannot wait indefinitely behind a longer one. Once this
freeze closes admission, timeout leaves it closed and issues no token; a later
explicit freeze must observe actual scope completion before succeeding. A
timeout waiting for serialization before touching admission changes no state.
Neither timeout nor cancellation proves another thread stopped.

Drain uses short bounded polling with a deadline-limited condition-lock acquire
on every round. It does not use `Condition.wait`: that API reacquires its RLock
without a timeout after the timed wait and could exceed the total budget under
late contention. The gate lock is released between checks; bounded rests are
at most 10 ms and never exceed the remaining budget.

Scopes leave the active gate only after transaction/close handling and any
failure publication. The failure-ownership lock is not held while awaiting
drain. Existing close failures keep their actual connection and original body,
transaction and close exceptions; subsequent calls raise fresh poison wrappers
without retrying that close or reopening the store. A zero active-call count
alone cannot create or resume a fence after failed close. The implementation
does not keep a registry of successful connections or inspect GC/weakrefs.

## Exact proof limit

This token certifies that the issuing store's **admitted connection-operation
scopes have drained** and their close calls returned without a recorded failure.
It does not certify physical SQLite/OS handle closure. CPython uses
`sqlite3_close_v2`; a retained unfinished cursor/statement can keep SQLite
resources alive after a successful close return. See the
[SQLite close contract](https://www.sqlite.org/c3ref/close.html),
[CPython 3.12 connection implementation](https://raw.githubusercontent.com/python/cpython/v3.12.13/Modules/_sqlite/connection.c)
and [cursor implementation](https://raw.githubusercontent.com/python/cpython/v3.12.13/Modules/_sqlite/cursor.c).
No GC, cursor registry, pointer inspection or rename success is substituted for
that missing resource-lifetime boundary.

Ordinary TranscriptStore methods return materialized rows/models/scalars,
consume multirow queries, and do not expose a cursor. Its private connection
factory/scope is not a containment boundary against arbitrary Python code.
Exception tracebacks or an explicitly retained private cursor can retain
resources; explicit cursor/resource lifetime remains a separate prerequisite
before physical store detach. A method with multiple connection scopes may be
between them when freeze succeeds; its next scope is refused. The fence does
not certify that every outer public method invocation has returned.

This is not a RuntimeDataFence, all-store/global writer proof, process signal,
`WriterStopProof`, immutable-slot eligibility or safe copy/directory-swap token.
Other TranscriptStore instances/raw SQLite clients are not covered. Reading,
Lexirise pinned sessions and ledger operations, settings/file access, dynamic
reader creation, WebSocket status workers, indexes/voice references and other
registered workers still require their own closed-admission/resource-lifetime
connections. Producer drains which write their final bookkeeping must complete
before underlying store admission closes.

The existing capture C2 path normally retains the OCR engine object while
joining its current/retired worker pools. This change neither proves native OCR
usability nor changes capture. Retaining an object while resume creates a fresh
worker pool is not proof of a usable warm native session. That future aggregate
boundary needs explicit same-engine operation evidence and must remain distinct
from whole registered-cohort process-signaled ownership. Global/dynamic writers,
keeper death, warm routing, copied-data activation, rights and Windows 11
acceptance remain open.

## Validation

The focused [storage tests](../backend/tests/test_storage.py) use actual SQLite
connections and Events to hold both a transaction and its close call. They
exercise refusal before new connection creation, bounded competing freezers,
one deadline across serialization/drain, timeout/retry after actual completion,
close failure retention/no retry, invalid tokens and invalid timeout values.
An Event-controlled holder takes the gate condition only after admission closes;
freeze must time out while that holder and the actual connection-close remain
live, with no token and admission still closed.
An actual SQLite negative case retains an unfinished private cursor and shows
that a valid token can coexist with an independent exclusive-lock refusal;
fixture disposal is not used as product resource-release evidence.
The existing Chinese/Hito/body/transaction/early-return tests remain applicable.
These are local source regressions, not native Windows or full R19 acceptance.
