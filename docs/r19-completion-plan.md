# R19 completion plan

Status: **planned remaining work; no acceptance gate is closed by this plan**.
Plan baseline: 2026-10-29 at `2e10dff78fb89f48584ff4f3ddb087e12e71c3ec`;
codec integration checkpoint updated 2026-10-30.
The acceptance contract remains the [R18 plan](r18-runtime-inventory.md#r19-acceptance-plan),
[component inventory](r18-runtime-components.md) and
[storage/host contract](r18-storage-host-contract.md). Current implementation and
exact test/artifact identities are in the [runtime evidence](r19-runtime-bundle.md)
and [helper evidence](r19-compiler-free-helpers.md).
The [first codec slice](r19-codec-experiment.md) used experimental fixed
FFmpeg/FLAC dispatch and its decode/failure probe. That historical execution
evidence remains separate from the Xiph integration and earlier checkpoint below.
The [codec artifact review](r19-codec-artifact-review.md) identifies the exact
Gyan supplier/FFmpeg source and rejects that 7.1 snapshot for production.
It does not establish complete dependency source/notice delivery or acceptable
maintenance for that artifact. This is a completed negative disposition.
The subsequent [Xiph FLAC replacement selection](r19-codec-replacement.md) verifies
the maintained source candidate, complete source kit and independent Windows
rebuild. Its new CLI/DLL is now [integrated in the frozen experiment](r19-frozen-xiph.md);
source/rebuild, extracted-runtime and clean Windows acceptance remain distinct.
The [rights/source/maintenance review](r19-xiph-distribution-review.md) now retains
the exact source kit in Git and records all 35 post-release changes. It also
corrects the earlier MIT description. The owner approved a limited additional
GPL-2.0-or-later route for the two codec build scripts and input policy on
2026-10-30. The new source kit contains that grant; its independent Windows
build/rebuild and downloaded source artifact are verified. The bounded frozen
checkpoint at `acc68be` also passed with downloaded source/metadata verification;
this is not final-candidate acceptance. Canonical binary/source
cohosting, other component rights and native gates remain open.

The deliverable is an extracted Windows x64 runtime that an ordinary user can
operate without separately installed Python/Node/npm, a Wrangler service, an
SDK, restore or a game-reader compiler. App-local runtimes remain allowed;
build-host tools stay separate. Keep the existing origins, 25 active
games/languages, Chinese transcripts, independent Migaku mode, storage keys and
source installation behavior. Preserve unavailable pack/format states explicitly.
PR #59 remains unchanged. No installer, release/tag, Pages publication, installed
shortcut transaction or live migration is authorized by this plan.

## Starting point

| Area | Established evidence | Remaining boundary |
| --- | --- | --- |
| Source candidate | Full Windows source/browser/package run at `e8a76d4`: 2,138 Python tests, one skip and 62 subtests; all five browser groups and extracted source-ZIP validation passed on the first attempt; all twelve downloaded sums/provenance checked | This is the source-style ZIP, not acceptance of the frozen runtime; the earlier `a079232`/`c18d07a` source failures remain recorded |
| Extracted runtime | At `5c9db76`, 1,090 Windows contracts, freezing, native/C1/cold-slot, living-keeper and authored SQLite plain/interrupted-resumed/retained-WAL cases passed; root and peer checked downloaded metadata/source artifacts | C5 proves one plain retained-WAL copy under a living coordinator; no target activation, keeper loss, global/dynamic writer admission, production rights, real OCR/capture, general voices, ASR inference, full export or ordinary-user Windows 11 operation |
| Static frontend | Chromium/Firefox comparison, authored persistent stores, worker/WASM OCR, retained chunks and frozen serving passed | Ordinary selected browser profile/extensions and update continuity need candidate evidence |
| NTE | Owned self-contained bridge collected; exact runtime identity and actual bridge protocol with authored reflected assemblies passed | Actual UEExtractor/CUE4Parse/Oodle, real locres/voice formats and combined rights remain open |
| Endfield / PRAGMATA | Actual prebuilt readers passed bounded private probes: Endfield empty/malformed input; selective x86 REE authored uncompressed PAK selection/rejection | Separate blocked manifests; neither reader is collected or approved for distribution/game use |
| ZZZ | App-local Node/worker/WASM authored probe passed; actual reader transpilation/private preparation exists | Actual extractor/codec operation, corresponding source, custom terms and metadata rights remain open |
| Host/data recovery | Guarded cold slots, living-keeper and `5c9db76` plain/interrupted-resumed/retained-WAL receipts verify bounded retained-process/continuous-lease behavior with actual source-entry contenders; protected-TEST probes also exist | No production global writer barrier, keeper-loss lifetime, interrupted-WAL, warm supervising updater or full populated-data/settings/browser/credential/schema continuity proof |
| Unvoiced export | Actual source and `acc68be` frozen authored Half-Life index/language/mobile-export workers and the portable mobile parser pass for English and Simplified Chinese, with missing-pack rejection and previous-export preservation | Ordinary-user/installed-pack acceptance remains pending; no original speech binding is added |
| Source original PCM | Source and bounded frozen authored Portal VPK/VCCD/event and selected English/French pack bindings pass actual index/language workers and in-process extraction/PCM validation; truncated PCM preserves prior output | Voiced mobile export still requires the unavailable general MP3 conversion path: bundle FFmpeg is disabled, the voice service requires decoder readiness and the transfer format requires MP3. Xiph FLAC and the quarantined FFmpeg DLL replay do not provide that encoder. MP3/composite/Bink decoding and installed-game/native coverage also remain pending |

The [Python component review](r19-python-component-review.md) retains twenty
exact supplier notice texts and provenance. Runtime collection/finalization
requires their delivery, now confirmed in the bounded frozen checkpoints along
with ONNX/windows-capture/Flatbuffers notice additions. Native ownership, complete
incorporated notices and rights remain pending. The [native acceptance protocol](r19-native-acceptance.md) validates
candidate-bound receipts without granting acceptance. The user confirmed on
2026-10-30 that Windows 11 25H2 x64 test hardware is not yet available.

The `runtime` profile stays hard-disabled and `r19_complete` stays false. The
dated `packaging/runtime-bundle/toolchains.json` now distinguishes later bounded
helper evidence from remaining rights, format and Windows blockers for all 25
games. A successful helper build does not erase those remaining gates.
The [strict writer protocol](r19-writer-quiesce.md) accounts for admitted HTTP
work and registered background producers, while default source updates retain
their capture-only protocol. Neither returns production store-copy authority.
The [owned frozen host probe](r19-owned-host-probe.md) now uses actual Windows
Job Objects and retained process/listener handles for one disposable frontend/API
slot. Its API external side effects remain mocked. Local ordering/refusal tests
pass; actual extracted Windows stop, child-exit, parent-crash, readiness and
foreign-listener cases passed at `acc68be`, with retained runtime/OS-helper
handles signaled and ports released. The [download review](r19-frozen-checkpoint-20261031.json)
binds the exact checkpoint. It is not a production launcher or update transaction.

The [guarded cold-slot checkpoint](r19-guarded-slot-probe.md) establishes continuous
lease exclusion while its outer guardian remains alive, including host crash and
rollback. Guardian death, warm routing and actual store/credential continuity stay
open. The separate [living frozen keeper probe](r19-frozen-keeper-probe.md)
adds two fixed guardian-loss cases using retained suspended creation objects.
Its first actual frozen attempt at `e8a76d4` refused a guardian descendant
before writer creation; that failure remains recorded. At `1c2d931`, both
detached cases passed with actual source-entry exclusion held through retained
writer signals and explicit cleanup. The outer keeper remained alive: keeper
loss and general writer lifetime remain open.
The [authored frozen data-copy adapter](r19-frozen-data-copy-probe.md) now
connects that fixed writer cohort to the existing typed migration barrier.
Its local SQLite/ordering contracts and first frozen Windows case at `ed153ab`
pass. The downloaded receipt verifies two source cohorts, four retained writer
signals and nine actual source-operation blocks. No WAL/SHM file was present.
It restarts the original source with a fresh cohort; it does not activate a
copied target, warm a candidate or publish a route. At `5640d6b`, the separate
fixed post-file-exception case also passed with the same live owner, two helper
attempts, two partial revalidations and ten actual source blocks. Two reviewers
verified its downloaded receipt, but WAL/SHM remained zero and keeper/global
writer/target-activation gates stay open.
At `5c9db76`, the distinct plain-copy C5 case passed with a real stopped
16,512-byte transcript WAL and 32,768-byte SHM, main-only `favorite=false`
versus full-set `favorite=true`, ten source-entry blocks and the same two-cohort
preservation/cleanup protocol. C3/C4 again observed zero WAL/SHM. This closes
only that retained-WAL fixture observation; populated grammar/export data,
settings continuity, keeper death, global admission and warm routing remain
code/integration work. The same head's ASR source attempt still failed before
configure: both Full CLR/x64 default-folder results were empty despite the
two-alias binding. No specific Shell cause or native ASR success is inferred.
The [FFmpeg/Opus source replay](r19-game-codec-replay.md) is implemented as
a separate manual build-host experiment. The [TTS-disabled ASR source
experiment](r19-asr-source-experiment.md) is a distinct private binding variant,
with an authored native-format graph rather than accepted pretrained model
weights. Neither experiment is a runtime replacement or a corresponding-source
approval. Earlier ambiguous discovery, wrong installed CMake, compiler quoting,
search-root and missing-import failures remain in their dated evidence ledgers.
The exact official [isolated CMake input](pinned-build-cmake.md) preserves the
4.4.5 requirement. At `1c2d931`, FFmpeg/Opus source build and native
decode/error/origin probes passed; its independently reviewed public source kit
also excludes private configure-log metadata. Complete corresponding-source
review and the separately proposed six-file recipe license remain pending.
At that same checkpoint, ASR verified the initial exact CMake module variant
and selected VS18 `v180` inputs, then failed configure with MSB4018. The isolated
`ce09ea2` follow-up confirmed canonical imports and a `CL` task
type-initialization exception. At `ed153ab`, eight bounded records additionally
identify an inner `ArgumentException`; message, parameter, initializer and
underlying cause remain unknown. These runs prove no compilation or inference.
The diagnostic changes altered no tool pins,
compiler flags or full selected-instance identity.
The [MSVC metadata census](r19-msvc-redist-observation.md) is a separate
read-only first step, with no component selection, redistribution permission
or runtime admission. Its first hosted census at `ed153ab` failed before
publication, with no artifact or proven Python-contract/census subphase. Fixed
phase diagnosis subsequently identified an observer-startup failure. Direct
binding to setup-python's exact executable allowed eleven Node and 37 Python
contracts without skips at `c3639ce`; the first independently verified
source-bound census remains negative with `unknown-version-entry`. No versions,
families or files are admitted. Its unknown entry still needs a bounded layout
review; no path-policy relaxation or CRT selection follows from this result.
The first v2 observation at `2a169bd` narrows only its name bucket to
`other-noncanonical-name`; the actual spelling/type remains unknown.
The strict toolchain and source guards remain in force.
The [immutable frontend retention adapter](r19-frontend-slot-retention.md) now
binds a fixed current/retired frontend snapshot to independently trusted slot
manifest hashes. Its authored loopback tests cover old Vite/Next chunks and
refusal cases; production CLI access, route swaps and browser continuity remain
unavailable.

## Execution order and ownership

Owner names below are roles for the implementation, artifact review and Windows
test work, not assignments to new agents or people.

| Work package | Owner role | Dependency / first useful result | Completion artifact |
| --- | --- | --- | --- |
| A. Exact component disposition | Runtime implementer + component reviewer | Start now; review codecs first because most voiced chains share them | Exact file/native/notice/source-delivery ledger; every unresolved file stays excluded |
| B. Functional toolchains | Runtime implementer | Build-only fixtures can advance now; each runtime integration requires its A decision | Fixed resolvers and real subprocess/format receipts, mapped to all 25 games |
| C. Supervising host | Host implementer | Can advance independently of blocked game rights, using authored services | Prebuilt host/interop, real ownership/quiesce/update/recovery integration |
| D. Clean Windows acceptance | Windows tester | Protocol/fixtures can be prepared now; results require a frozen eligible candidate | Exact-image ordinary-user OCR/capture/DPI/dependency report |
| E. Browser/data continuity | Host implementer + Windows tester | C writer exclusion before copy/update tests; disposable copied data only | Candidate copy/restore, protected TEST and selected-profile continuity evidence |
| F. Final candidate and R02b | Integrator + Windows tester | A–E on one final artifact; reuse unaffected evidence only with matching identities | Frozen acceptance matrix, measurements, downloaded sums/provenance and explicit remaining limits |

Work can proceed on independent packages while a particular right or native
input is unavailable. That unavailable gate stays open; it does not justify
removing supported languages, substituting a compiler fallback or silently
reducing the R19 definition of done.

Implementation boundaries are the existing collection scripts
(`packaging/runtime-bundle/record_runtime.py`, `closure.py`, `runtime.spec`),
tool adapters (`backend/media_tools.py`, `game_tools.py`, `bundle_tools.py`,
`prebuilt_readers.py`, `prebuilt_node_reader.py`), and runtime dispatch
(`backend/runtime_bundle.py`, `bundle_entry.py`). Host work connects the existing
API/handoff/preparation lifecycle and Windows ownership code; keep the explicitly
synthetic `bundle_host.py`/`bundle_migration.py` fixtures distinguishable from new
production adapters. Extend the existing frozen/helper/functional probes and
GitHub workflows instead of duplicating the source updater or extractor stack.

## A. Exact components, resources and rights

**A1 — Record decisions per actual file.** Extend the existing input/closure
records with archive/source revision, file SHA-256, architecture, native imports
and delay imports, complete notice paths, applicable source-delivery mapping,
acquisition mode and deterministic execution/resource path. Use the existing
P1/J1/M1/V1/F1/G1 requirements. Distinguish app-local files, separately verified
downloads, named OS/VC prerequisites and install-local game files. A receipt's
`approved` string cannot unlock a disabled helper kind.

**A2 — Close the observed runtime inputs.** Review the pinned CPython 3.12.16
supplier and exact wheel/native payloads already collected, including CRT/CPU
requirements and the independent ASR native tree. Complete missing notice text
instead of treating retained METADATA as approval. Review emitted frontend,
fonts, WASM, dictionaries and model bytes; build-only npm/SDK/test packages do
not become user dependencies. Record the chosen x64/x86 VC runtime requirements
and official repair path without copying arbitrary System32 files.

The [native collection observation](r19-native-collection-provenance.md) now
binds existing PyInstaller sources to final output bytes. Its first actual
`423e843` run refused an unresolved source before freezing; the bounded
current-call census adds diagnostic categories without admitting that source.
The [static image review](r19-native-image-review.md) adds a mandatory final
inventory check for selected EXE/DLL/PYD architecture, CLR flags and import
tables. Its authored contracts are distinct from actual frozen output evidence.
Other extensions, embedded images, dynamic loads, incorporated rights and full
P1/A1 closure remain open.

**A3 — Resolve the shared audio and blocked reader inputs.** For FFmpeg and
vgmstream, select exact artifacts/configuration, codec/native dependencies,
notices and required source delivery. Recheck actual current primary upstream
sources before recording a disposition. Independently close NTE external/Oodle,
Endfield constants/port provenance, REE modified-reader/native and ZZZ GPL/WASM/
custom-term/metadata questions. Separate downloads are not automatic rights
approval. Preserve the never-collect rules for Snipping Tool OCR and the Decima
game DLL, and the separate private Persona character cache.

Acceptance: the collector can identify every selected output file and rejects
unreviewed extras, changed bytes, path aliases and wrong architectures. Each
required component has an evidenced delivery/prerequisite decision and an actual
functional probe. If a needed component remains unresolved, the related toolchain
and full R19 acceptance remain unavailable.

## B. Functional compiler-free toolchains

**B1 — Add the shared executable adapters first.** Implement fixed bundle
resolution/invocation for accepted FFmpeg/vgmstream artifacts, preserving source
behavior. Where A selects a separately acquired tool, use its verified private
tool root and exact receipt. Do not discover arbitrary PATH binaries, borrow a
development installation or start SDK/npm/pip/restore. Test real decoding with
owned audio, bounded cancellation and previous-output retention before attaching
more game readers.

**B2 — Complete the per-family integrations below.** Use the current adapters,
prebuilt helper resolvers and collection gate; do not create an independent
extractor stack. The public fixtures must be authored and exercise the actual
format/parser/subprocess rather than mock process success. Keep game constants,
private sources and unapproved binaries in the existing blocked quarantine.

| Games / chain | Missing implementation or proof | Required positive case and boundary |
| --- | --- | --- |
| NTE | Exact external managed/native closure; reviewed fixed game dispatch | Real locres/text-to-bank/media binding and one original-voice output; authored reflection stand-ins remain separately labelled |
| Endfield | Accepted selected-source/helper policy and actual VFS/audio path | Representative VFS block/chunk/hash lookup and voice bytes; retain four voice choices and actionable absent-pack states |
| ZZZ | Reviewed precompiled reader, app-local Node/modules/WASM and immutable extractor integration | Real scene/cinematic unpacking, worker/WASM codec execution and text/voice identity without runtime transpilation |
| PRAGMATA | Modified x86/native rights and resolver integration; remaining PAK formats | Selective compressed/encrypted-format cases and oversized/corrupt rejection; preserve the existing uncompressed selection pass |
| Cyberpunk | Exact WolvenKit/.NET/native invocation and source obligations | Real selected text/voice extraction with accepted app-local or declared runtime, no developer SDK |
| Wuthering Waves | Exact FModel/decompression/native policy and invocation | Actual archive/binding/decompression path; unresolved Oodle stays blocked |
| The Witcher 3 | Frozen speech/narrative path through the shared decoder | Original text/voice identity and codec output, preserving selected player voice |
| BEYOND / Heavy Rain / Detroit | Three distinct Quantic resource/audio variants | Separate reservoir-sensitive MP3, legacy resources/game-data and v18 Wwise cases; one game's pass cannot cover all three |
| Star Rail / Genshin | Private snapshot acquisition and distinct pack/root layouts | Separate original-voice binding cases, including the regional-root distinction; no shipped metadata seed |
| Rise / Shadow of the Tomb Raider | Distinct Tiger MUL/movie and locale-segment/Wwise paths | One fixture per distinct variant, including channel/locale and voice identity |
| Spyro | Frozen Unreal/zlib and three-game table/media mapping | Three game namespaces retained with representative actual-format text/WEM binding |
| MGSV TPP / Ground Zeroes | Distinct Fox SQAR and GZS/XOR/container bindings | Separate radio/tape/cinematic and STE/WIN/SANI/FSM coverage where those formats apply |
| Death Stranding | Explicit installed-game DLL ABI/loader boundary | Exact read-only install-local DLL binding and missing/wrong-ABI rejection; never collect that DLL |
| A Plague Tale: Innocence | Frozen Asobo raw/LZ4/Wwise chain | Package precedence, text/voice binding and decoder output |
| Portal / Portal 2 / Half-Life 2 | Source mount/version/campaign and Bink/multitrack differences | Separate ordered mounts, VSIF3/Bink and VSIF2/campaign cases; preserve each game's identity |
| Half-Life | Candidate execution of the existing unvoiced GoldSrc capability | Exact text/translation behavior and text-only capture; no invented original-voice support or per-reader vgmstream dependency |
| Persona 5 Royal | Separately verified character cache and CRI MSG/flow/ADX integration | Correct character/text and cue/bank/ADX output; missing cache is actionable and remains private |
| Deus Ex: Human Revolution DC | Frozen bigfile/CDRM/MUL/USM decoding | Stereo interleave, USM/ADX and exact text/voice identity |

This table maps all 25 active games to distinct remaining cases. Reuse shared
codec probes; retain separate format/locale cases where the table names a
difference. Installed-game playback is a private additional observation for the
named installed pack; an authored-format pass never labels an absent pack as
played or native-verified.

**B3 — Exercise ordinary consumers.** Run the actual language/index worker and
full mobile-export worker through an accepted chain, including original audio,
chosen source/translation locale and normal package import/readback. Worker
`--help` and direct catalog-library export do not satisfy this case. For optional
ASR, record the separately licensed model/token source/version/hash and execute
one actual inference in the isolated image when enabled. Missing model files
remain actionable; they are never filled from an arbitrary old installation.

For each chain, require exact expected/forbidden text and voice identities,
wrong/missing/corrupt native inputs, interrupted extraction, cancellation and
unchanged last complete indexes. Output stays outside the app/helper/game trees.
No failed voice lookup becomes unvoiced dialogue or a different language.

## C. Real host ownership, update and recovery

**C1 — Establish the extracted entry host.** Prebuild/adapt the owned host and
interop on Windows, preserving existing ports, ordinary-browser selection and
legacy exclusion. Inventory any remaining PowerShell/Framework behavior. A
remaining `Add-Type` path is not proved compiler-free by a game-helper pass;
prefer the precompiled interop path. Installer registration and shortcut/pointer
installation transactions stay with R20/R21.

**C2 — Connect real ownership and a global writer barrier.** Adapt existing
runtime readiness/quiesce/handoff and Windows process-tree ownership. Identify
children using owned handles/start identity/image/root; a copied PID or route
record cannot authorize termination. Stop preparation/native setup jobs,
manual/automatic exports, capture, queued reading/audio writes and request
mutations before copy or takeover. Wait for actual drain/descendant exit. A
cancelled future, `/api/health`, standby or OCR readiness is not that barrier.

**C3 — Implement the frozen update transaction.** Verify a new immutable slot,
prepare it against copied test state, warm OCR/selected index and frontend, drain
the old owner within the preselected 30-second budget, transfer bounded capture
state, publish the route atomically and retire owned old children. Retain old
chunks and reconnect WebSockets. Keep the legacy operation lease continuously
held: do not invoke the current nested-lock source updater or briefly release
exclusion. Reuse its established behavior through an owner-aware adapter, with
the frozen updater still disabled until the integrated transaction passes.

**C4 — Prove failure and recovery.** Inject failure after verification, standby,
drain, activation and route publication. Also cover nested update contention,
quiesce timeout, corrupt receipts, parent crash, reused/unknown PIDs, stale routes
and native child failure. Confirm at most one capture owner, previous runtime
usability or a retained explicit recovery-required state. Application rollback
must not let old code open an incompatible new writable schema. Never infer
permission to restore data merely because code rollback is possible.

Acceptance: actual extracted processes, handles, routes and copied stores satisfy
these cases. The `SyntheticHostCoordinator` and synthetic migration tests remain
cheap ordering/failure regressions, not replacements for this integration.

## D. Clean Windows 11 acceptance

Prepare a private protocol and safe result template before involving a tester.
Use a standard Windows 11 25H2 x64 user without development tools. Record exact
OS/build, CPU/GPU, selected browser, runtime/CRT, Snipping Tool build and relevant
file hashes, display topology/DPI and candidate/inventory identity. Keep personal
paths, game files, credentials and recordings out of public reports.

Run one bounded case for each distinct risk:

- Extract to spaces/Unicode, start from unrelated CWD and a read-only app tree;
  prove fixed child dispatch and app-local or declared OS DLL origins.
- Initialize user-provided Snipping Tool OCR and read independently authored
  Chinese and non-Chinese captions through native capture and transcript output.
- Cover window and monitor selection, 125/150/200% DPI, multiple monitors and
  negative display coordinates; verify expected and forbidden crop bounds.
- Exercise missing/stale OCR assets, denied capture, unavailable display/device,
  wrong architecture, missing CRT, offline first start/reuse, interrupted or
  blocked tool acquisition, no space and locked files. Never report partly ready.
- Confirm an audio/decoder failure preserves the confirmed transcript and prior
  complete index/export. Run selected installed-game/locale playback only where
  those private inputs are available; label other packs unavailable.

Server 2025 CI remains build/loading evidence. It cannot close these Windows 11
hardware/capture criteria. No real account write is needed for the protocol.

## E. Data and ordinary-browser continuity

**E1 — Extend copied-data probes after C2.** Use opt-in disposable copies and a
current writer-stop proof. Preserve synthetic transcripts/favorites, archived
data, account/locale selections, grammar choices, export ledgers, outstanding
export-volume work and previous complete libraries. Validate SQLite/WAL/schema
sets, aliases and inventories. Cover interrupted/resumed copy, no space, locks,
unknown schema and malformed/changed manifests; retain originals and failed
targets. Do not perform an actual existing-installation migration in this phase.

**E2 — Verify protected TEST credentials on the candidate.** Preserve host
locators and encrypted legacy fallback under the same Windows user. Use newly
created protected TEST blobs and mock clients only. Verify no plaintext or key
enters a manifest, log, browser or workflow secret. An unreadable named store
retains its bytes and reaches an explicit preserving repair/reconnect design;
the existing add-account prompt is not evidence of that repair.

**E3 — Reopen the selected ordinary browser profile.** On the retained origin,
verify localStorage, IndexedDB, OPFS, userscript keys, reading mode, account/locale
selection, audio/export and WebSocket recovery through restart and update.
Exercise Chromium and Firefox with relevant real extension behavior separately
from fresh synthetic profiles. Test missing/stale assets, old chunks and offline
reopen without copying raw browser-profile directories or clearing user stores.

Acceptance: copied-state and ordinary-profile evidence names the actual candidate,
browser/extension versions and verified operations. Keep source/Server protected
TEST evidence, synthetic browser equivalence and candidate results distinguishable.

## F. Final artifact, measurements and completion decision

Freeze one eligible candidate after A–E implementation: source commit, source/
dependency locks, per-component inputs, model/tool digests, complete files and
directories, executable hashes, native/host policy and fixture versions. Run
functional, ordinary-browser and native acceptance against those exact bytes.
Change only invalidates the affected evidence, but final combined acceptance
must identify one coherent candidate rather than combine unrelated artifacts.

Use the [preselected R02b method](r19-runtime-bundle.md#r02b-method-fixed-before-optimization):
one cold start after reboot, five warm starts, frontend plus true runtime
readiness, first usable caption, process-tree memory/CPU and 60-second idle CPU,
extracted/compressed size, peak preparation/failure disk usage and recovery.
Measure the source runtime on the same machine/configuration. Retain failures
and unavailable measurements; invent no retrospective speed/size threshold.

Run supported-target full source/browser/package CI and the relevant **extracted
runtime** probes. The existing source-ZIP package job is useful evidence but does
not replace a frozen artifact check. Download eligible candidate/check metadata,
verify every checksum and exact source/shared provenance, and report signature/
attestation status separately. Until distribution is eligible, keep binaries and
raw/private evidence quarantined and publish only allowlisted sanitized metadata.

The completion review must answer every R18 acceptance row with pass, failure or
unavailable, exact artifact/case identity and scope. Required unavailable or
failed rows prevent a full R19-complete claim. Optional component absence must
have its declared actionable state and cannot conceal a required capability.
Only after this review may a separate implementation change enable the production
profile; this document does not flip a gate or authorize activation/release.

## Check cost and evidence rules

Use `dev:doctor` before dependency preparation and `check:changed` for edits;
fetch the actual PR target for branch comparisons. Run cheap contract tests for
new resolver/ownership/failure behavior and only missing authored format cases.
Do not mirror implementation details or multiply every game by every locale,
browser and DPI. Batch cases by distinct format/codec and retain the per-game map.

Reuse existing hosted helper budgets (managed 20 minutes, Node 15 minutes,
private readers 25 minutes per kind) and the integrated-runtime 45-minute ceiling.
These are limits, not target durations or permission to add a full matrix to
every commit. Measure the first new case's cost before expanding a job. Build
once per exact input identity and reuse the output across probes. Rerun passed
broad suites only for relevant changes, reproduced failures or final acceptance.
Documentation-only work uses documentation/publication checks.

Each result records source, exact artifact/inventory, build/probe/fixture identity,
OS/architecture, elapsed time, result, cleanup and unrun scope. A skipped native
case, delegated check, successful import or receipt label is not a functional or
rights pass. Preserve the observed first failures, including unchanged successful
repeats, in the evidence ledger. Never upload private source/constants, accounts,
game media, raw compiler logs or recordings as failure artifacts.

## Immediate next implementation slice

Continue A1/A3 and B1 from the [frozen Xiph integration](r19-frozen-xiph.md),
retaining its complete source/recipe/notice delivery and exact observed binary
identity. Review its extracted decode/failure/DLL-origin evidence separately from
clean Windows 11/ordinary-user CRT acceptance and production source hosting.
The limited build-recipe grant in the
[rights/source review](r19-xiph-distribution-review.md) is approved and delivered
in the exact retained source kit. Keep that completed scope separate from
remaining canonical binary/source cohosting, incorporated-component rights and
clean-host acceptance. No blanket relicense is inferred and no runtime acceptance
flag changes. The standalone source-build/rebuild pass alone does not establish
those remaining gates.

Finish the separate FFmpeg/Opus and TTS-disabled ASR native build experiments
before considering their source/notice disposition or runtime integration. A
passing authored ASR graph would prove mechanical inference APIs only, not
speech recognition accuracy, pretrained model rights or complete ONNX source
reconstruction. In parallel, C can extend verified immutable frontend retention
and the independently owned lease lifetime using authored private state; neither
a frontend snapshot nor a cold-slot pass is a warm update transaction.

For each subsequent codec family use one accepted artifact and an independently
authored real decode, plus missing/corrupt/cancellation cases. Add its exact
disposition record before broadening FFmpeg/vgmstream/game coverage. Keep
unresolved artifacts disabled; NTE stand-ins and private Endfield/REE outputs
remain distinct from accepted game chains.

Then integrate B2 one distinct chain at a time while C proceeds on authored
services. D/E protocols can be prepared before device access; their results wait
for the corresponding candidate. Final measurements and the full R19 decision
follow F. Installer construction, installed repair/uninstall and installed
shortcut/upgrade migration remain R20/R21; release/signing delivery remains R22.

PR #60 may be reviewed as a bounded experimental foundation while this ledger
remains open. That review decision is separate from full R19 acceptance and
upstream CI approval. This plan does not change its draft state or PR #59.
