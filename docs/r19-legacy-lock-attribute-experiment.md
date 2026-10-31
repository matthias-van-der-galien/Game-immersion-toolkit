# Separate legacy-lock READONLY mechanism experiment

This is a build-host source experiment, **native pending**. No Windows attribute
or owner-loss result is claimed from local authored tests. It is not registered
as a frozen child or production API and does not change existing C1/C3/C4/C5/C6,
keeper, migration, runtime or installer behavior. PR #59 remains untouched.

The question is narrow: can READONLY on the exact existing legacy operation
file preserve an unchanged launcher's refusal after the last genuine lease
owner exits? [File.Open](https://learn.microsoft.com/en-us/dotnet/api/system.io.file.open?view=netframework-4.8.1)
documents a refusal when ReadWrite is requested for a read-only file. This
would complement live sharing exclusion; it would not keep a dead process's
handle alive or prove any candidate writer stopped.

The [R18 contract](r18-storage-host-contract.md), steps 3 and 6, still requires
continuous handle ownership and both exclusions through writer shutdown.
Step 7 still requires verified process ownership for recovery. This experiment
cannot quietly replace those requirements with a sticky attribute. Its scope
contains **zero candidate/data writers**, no pointer change, no user data and no
activation. A passing mechanism result does not close the keeper-loss gate.

## Fixed mechanism and containment

[The standalone module](../backend/runtime_lock_attribute_probe.py) accepts no
fixture, source, executable or output path from the operator. On 64-bit Windows
it checks the existing temporary directory through root-first non-link metadata
guards and requires a fixed local NTFS volume before creating anything. It then
creates one marked temporary root and one original lock file with owned text.
The private child grant must name that exact temporary namespace and marker.
Initially READONLY, linked, multiply linked, deleting, unknown-attribute,
wrong-sized or changed-content files cannot become accepted observations.

Actual contenders execute only the unchanged `Enter-CompanionOperation` function
from [the current source](../scripts/companion-runtime.ps1). The whole source
is checked against its reviewed exact LF or Windows CRLF hash. A bounded
read-only source stream is hashed before its exact bytes are parsed as an AST;
there must be exactly one named definition. No script body is rewritten. The
operation still uses OpenOrCreate, ReadWrite and FileShare.None.

The existing [creation helper](../backend/windows_preparation_process.py) creates
the actual lease owner suspended directly into its retained Job. The retained
creation object resumes once and is the only authority used for termination and
signaling. No PID, copied handle or file journal is adopted. Each private local
named pipe has one first-instance server, rejects remote clients and has a
bounded 4 KiB ASCII JSON frame. Its client PID is only compared with the PID
queried from the genuine creation handle. It is not a process-ownership grant.
The lease child's pipe uses explicit nonblocking mode; there is no inherited
stdio, reader thread, raw log or arbitrary child command.

The fixed observation sequence is:

1. The actual legacy operation opens the writable file and closes successfully.
2. One genuine child acquires its original ReadWrite exclusive handle. A separate
   actual legacy contender reports the existing sharing refusal.
3. The child sets READONLY and reads back through that handle. It clears while
   retaining the same handle, proves sharing still refuses the contender, then
   re-arms and reads back before owner loss.
4. The parent stops only that retained creation object, waits for its signal,
   drains/closes its owned Job and closes the pipe. No duplicate lease is kept.
5. A temporary read-data/attribute observation handle verifies the same file and
   retained READONLY, then closes. With no file lease held, the actual legacy
   operation must take its specific UnauthorizedAccess/known access-denial path.
   A generic permission error is not a passing result. The initial and final
   writable controls and unchanged file identity constrain this contrast.
6. Only because this fixture admitted zero writers, a separate test restoration
   handle requests GENERIC_READ plus FILE_WRITE_ATTRIBUTES, no WRITE_DATA, with
   share=0. It verifies the armed file, clears while still holding data-read
   exclusion and proves sharing still refuses the contender. After explicit
   close, the actual old operation opens again. Final by-handle preservation is
   checked through a fresh observation handle.

An attribute-only handle is deliberately insufficient:
[CreateFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
exempts attribute-only access from ordinary share checks. The native behavior
of the proposed read-data/write-attributes restoration combination is itself
pending. Failure is reported, without a clear-then-acquire gap or alternate
handle/permission strategy. This is not an automatic recovery route for a dead
keeper with unknown surviving writers.

## Private preservation and public result

Typed 64-bit Win32 APIs query FileIdInfo, FileStandardInfo and
[FileBasicInfo](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)
on retained handles. The same volume/file ID, fixed content, link count and
unrelated attributes must remain valid. NORMAL is treated as the no-other-flags
placeholder; it is not combined with READONLY. The setter uses no undocumented
timestamp suppression. All four times remain private. The receipt includes
only four equality booleans for each transition. Creation and stream-write
time changes refuse preservation; access-time changes from reads and metadata
ChangeTime changes can be observed as false. They are not hidden or presented
as exact timestamp preservation. No private path, file ID, raw time, private
content hash, exception, environment, command or stack is serialized.

The public schema is `proxy-r19-legacy-lock-attribute-mechanism-v3`, scope
`authored-local-ntfs-no-writers-mechanism`. It revalidates exact keys, fixed
ordered observations, enum values, booleans and the known public legacy-source
hash. Its only successful status is `mechanism-observed`. The final gates stay
false: production, keeper-loss acceptance, rights and R19 completion; ordinary
Windows 11 acceptance stays unavailable.

Version 2 introduced the closed `baseline_checkpoint` object with three finite
strings: `parent_step`, `script_step` and `child_state`. The parent marks pipe
creation, owned process creation/resume, client binding, grant send, progress
receive, result receive and cleanup immediately before the action. On refusal,
cleanup cannot overwrite the first failed parent action. Child state is only
not-created, signaled, not-signaled or unavailable, queried through the genuine
retained creation handle before close. No closed handle, PID lookup or exit code
supplies it. Query failure is unavailable context; it cannot grant or revoke
the existing process cleanup or mechanism acceptance requirements.

Version 3 retains those exact three keys. The same PowerShell child now sends
fixed ordered progress: connected, grantread, grantparsed, grantvalidated,
sourceopened, hashbound, definitionbound and operationentered. The existing
single ReadLine call returns before grantread; its result enters the same
string pipeline to ConvertFrom-Json, which returns before grantparsed.
Neither acknowledgement proves a non-null grant, its shape, or a successful
operation. Only the unchanged three-name/string-type checks permit
grantvalidated. Null, malformed or incomplete progress still refuses; no
line, property, parser output or exception is published.
Only actual hash equality permits hashbound; only the exact AST checks and
definition permit definitionbound. The terminal `state` result is unchanged.
Only a complete typed terminal record supplies operationresult. A stage before
the function call does not establish that the legacy operation opened.

All received bytes across an Attempt share one cumulative 4KiB cap. Grant,
progress, terminal and pipe completion share one existing10-second exchange
deadline, with no per-record extension. Unknown, skipped, duplicate, malformed
or trailing records refuse the attempt; only the last complete admitted stage
is retained. Terminal completion requires the peer to close without trailing
bytes within that deadline. There is no new runtime, process, raw output,
environment variable, source-function change, pipe-mode change or fallback.

Every owned cleanup stage is attempted independently. A failed handle close is
sticky and its numeric value is never retried as a possibly reused handle.
Unknown identity, source, protocol, attribute or owned cleanup fails the attempt.
The fixture is retained on success and failure: there is no unlink, chmod,
recursive deletion or path-based reset. Success says only
`owned-handles-closed-fixture-retained`; it is not full R19 cleanup acceptance.
Windows closes files on process termination, but no process-crash experiment or
[buffer flush](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
establishes power-loss durability.

## Execution and evidence

The historical version1 attempt at `a1c5e92`,
[run41225668722](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41225668722),
passed57 authored Windows contracts using Python3.12.10 on hosted image
20261030.294.1. Its source-bound metadata then reported failed /
legacy-baseline / protocol-refused, no observations, no timestamp booleans and
unconfirmed-fixture-retained. Root and peer independently verified the provider
ZIP digest, exact single JSON entry, candidate source, equal before/after
fingerprints and false gates. No actual legacy Open, READONLY set or owner loss
was delivered. The phase conflated startup, pipe binding and the script's source
and operation steps; it established no native cause. It contains no version2
checkpoint. The new wire and projection need their own reviewed CI publisher
and actual exact-source Windows attempt; the old negative is not relabeled.

The historical version 2 attempt at `e8416e9`,
[run41229013616](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41229013616),
passed 89 authored Windows contracts without skips on image `20261021.278.1`.
Its independently verified receipt stopped at legacy-baseline/protocol-refused:
parent receive-script-progress, script connected and child not-signaled before
close. Observations and timestamp equalities were empty; cleanup remained
unconfirmed-fixture-retained. It does not identify whether ReadLine, conversion
or shape validation returned, and establishes no successful legacy Open,
READONLY transition, owner loss or native cause.

Version 3 distinguishes only those existing grant boundaries, with no additional
read, conversion, parser/runtime import or acceptance authority. Its wire needs
the separately reviewed publisher and a new exact-source Windows receipt;
native execution remains pending. The v1/v2 negatives retain their original
schemas and meaning. No environment, timeout, source-function or pipe repair is
inferred from them.

On the selected Windows build host, run the selected 64-bit source
interpreter directly:

```sh
python -I -B backend/runtime_lock_attribute_probe.py
```

It prints one finite JSON result and exits 0 only for the complete mechanism
observation; refusal exits 2. There is no output-path or cleanup-path option.
Its internal `--owned-lease` mode accepts only the fresh pipe name, then receives
the bounded private fixture grant after creation-identity binding. Do not run it
against a real installation. No native pass is currently recorded.

The existing **R19 integrated extracted runtime experiment** workflow exposes
the separate manual `source_replay=legacy-lock-attribute` selection. It runs
only this Windows source job, using Python `3.12.10` and the exactly locked
pytest dependency subset. The independent wrapper checks the finite receipt
schema, actual exit status, clean checkout and matching before/after raw source
fingerprints at the event commit. Its fixed output sink checks ancestors before
creating directories, rejects links and existing leaves, reads back the actual
written bytes through a bounded descriptor and checks source/cleanliness again
before the upload sentinel. It uploads only
`r19-legacy-lock-attribute.json`, including source binding; no fixture or raw
stdout/stderr is retained. A validated failed receipt remains failure evidence.
Its outer deadline records a failed, unverified attempt rather than cleanup
containment. Native acceptance still requires the actual job and independently
downloaded provider/artifact/receipt review.

The cheap [authored tests](../backend/tests/test_runtime_lock_attribute_probe.py)
cover frame/type/overflow refusal, exact transition preservation, ABI widths,
sticky cleanup, creation-handle/client comparison, zero-writer ordering and
retention on failure. They do not exercise real Windows READONLY, PowerShell,
file sharing, pipe or process behavior. Run them with
`python -B -m pytest --noconftest -q backend/tests/test_runtime_lock_attribute_probe.py`
and run documentation checks. Existing shared process-helper tests remain their
own evidence. No installer, old ZIP edit, global writer admission, real data
copy, owner-aware update, preserving recovery or Windows11 acceptance follows.
