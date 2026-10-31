# R19 — Windows runtime-bundle prototype

Status: **active implementation; full R19 acceptance incomplete**. This task
starts from R18 commit `8369c9534762cd2232fb44424772bd6b5a72b6d2` on
`codex/r19-runtime-bundle`. The dependency remains [PR #59](https://github.com/Firebird55/Game-immersion-toolkit/pull/59).
It is not changed or merged by this work. The actual target is
`Firebird55/Game-immersion-toolkit:main`; freshly fetched `upstream/main` was
`ba0b7c34c358f1664220674e5ff8bb7f30502e5f` on 2026-10-29.

This implements the source/frozen host boundary, static frontend and integrated
quarantined runtime experiments needed for the
[R18 acceptance plan](r18-runtime-inventory.md#r19-acceptance-plan). It retains
the Python runtime, normal browser, existing public origins and all 25 active
game/language choices. R14 onboarding, an OCR rewrite, R20 installation and live
data migration are outside this task. No release, tag or Pages publication is
authorized. Engineering evidence below distinguishes source contracts,
synthetic probes, a diagnostic executable and the accepted product candidate.

## R02b method fixed before optimization

No optimization or speed/size claim is proposed. Native measurements require
Windows 11 25H2 x64 and the same machine, power mode, selected browser/profile,
Snipping Tool build, selected game/locale, model and tool bytes for both source
and candidate. Record OS edition/build, architecture, CPU/GPU/RAM, storage,
display/DPI, runtime/CRT versions and a random private installation identity.
Do not publish usernames, absolute paths, account or game-derived contents.

Freeze source commit, requirements/npm locks, packaging-input receipt, candidate
SHA-256, tool/model/fixture digests and selected cases before recording timings.
Use authored Chinese/non-Chinese captions, synthetic catalogs/owned audio and
protected **TEST** credentials. Installed-game probes are separately private;
their absence cannot be replaced by a synthetic pass.

Measure one cold start after reboot and five warm starts for each adapter.
Start the clock immediately before process creation; stop only when both the
frontend and `/api/runtime/ready` (including OCR and the preselected prepared
language) succeed, followed by a usable browser page. Record each sample,
median/range, time to first usable caption, process-tree peak private bytes/RSS,
CPU time and 60-second idle CPU. Record extracted/compressed size and peak disk
usage during preparation and failed update. Account login/network time is a
separate observation; never silently omit a timeout or failure.

Preselected correctness criteria: exact retained origins and local-access
policy, unchanged synthetic transcript/favorite/locale/export identities, zero
competing capture owners, no app-tree writes and no user development-tool
dependency. Preselected recovery budget: a 30-second bounded quiesce attempt
must either confirm all owned processes stopped or refuse takeover and retain
recoverable state. A timeout is a failed recovery probe. There is no performance
pass threshold until these initial source measurements exist; report numerical
comparisons without retrospectively selecting favorable samples. Retain all
failed starts in the denominator.

The current development host is macOS arm64 with Node 22.22.2 (package-engine
supported; CI recommends 24). It cannot establish the Windows baseline, native
OCR/capture/DPI, DPAPI or installed-game playback. Those measurements remain
**unavailable**, not zero and not a pass.

## Ownership and evidence boundary

The initial runtime/frontend/helper phases used two GPT-6.1 Sol agents with xhigh
reasoning in nonoverlapping lanes and reciprocal reviews. The integrator owned
composition, consumer adapters, Git and combined checks. The 2026-10-29 integrated
runtime continuation is implemented and reviewed by the integrator without
additional agents. The [host experiment](r19-host-experiment.md) records static-host and
synthetic recovery results. This task keeps the source Vinext host until an
equivalent replacement is proved.

The copy prototype accepts explicitly marked synthetic fixtures only. It must
retain originals, audio aliases, reading grammar choices, export ledgers,
previous libraries and encrypted fallback bytes; named-store repair, same-user
DPAPI, browser IndexedDB/OPFS and actual launch-pointer recovery remain distinct
gates. Preparation/readiness is not a global writer barrier. The current nested
PowerShell updater is never run under a lifetime guard or given a bypass flag.

## Remaining acceptance gates

The [completion plan](r19-completion-plan.md) turns the remaining R18 acceptance
rows into ordered implementation, component-review and native-validation work,
with per-toolchain cases, dependencies and explicit completion criteria. It does
not change the acceptance contract or approve production activation.

The continued [compiler-free helper experiment](r19-compiler-free-helpers.md)
separates authored packaging probes, the owned NTE bridge and blocked game chains.
It does not convert unresolved helper rights or native evidence into approval.
The [first codec step](r19-codec-experiment.md) added one pinned experimental
FFmpeg artifact, fixed FLAC-to-PCM dispatch and an independently authored decode
case. General game FFmpeg, redistribution and Windows 11 gates remain open.
The [codec artifact review](r19-codec-artifact-review.md) now resolves the original
Gyan supplier/top-level FFmpeg source identity and rejects that snapshot for
production. Its dependency source/notice and maintenance gaps remain recorded;
the successful experimental decode does not override that disposition.
The [Xiph replacement selection](r19-codec-replacement.md) now has complete-source
kit/rebuild evidence on Server 2025. The [frozen integration](r19-frozen-xiph.md)
collects its exact CLI/DLL, notices and source kit into the experiment. It does
not close native Windows 11 or general game-codec acceptance.

All [R18 component gates](r18-runtime-components.md) remain binding for the
actual shipped bytes. Exact maintained CPython supplier, Windows wheels and
native closure, models/fonts/WASM, FFmpeg configuration/source obligations,
vgmstream codec closure, GPL integrations, PRAGMATA REE rights, Oodle and
game-derived constants require evidence before inclusion in an approved distribution. Snipping Tool's OCR
DLL/model files and Death Stranding's install-local DLL are never collected.
Persona's pinned character metadata remains separately acquired private state.

A diagnostic subset or core startup does not pass the all-toolchains gate.
Every active game retains its R18 per-game row, including Half-Life's current
unvoiced-only capture boundary and the separate global setup/audio conditions.
Unprobed installed packs, codecs, helpers and unknown bindings remain explicit.

## Integration checks and review

The two implementers reviewed each other's actual files and check outputs. Fixed
findings included a disabled-profile bootstrap bypass, raw symlink/reparse roots,
settings overlapping disposable storage, build-doctor CWD dependence, expired
copy barriers resuming writers, incomplete quiesce not persisting recovery,
linked checkpoints and unexpected resumed snapshot files. Source-only legacy
root arguments remain authoritative: the source adapter rejects new nondefault
frozen-root environment overrides rather than splitting export/index state.
The standalone ZZZ source reader retains its legacy-directory bridge; frozen
execution is gated before reaching it. Optional ASR keeps a separate process.

On macOS with task-local Python 3.12.13, pinned pytest 9.1.1 and the applicable
platform-independent lock packages:

| Command / scope | Outcome and evidence limit |
| --- | --- |
| `npm run dev:doctor -- --base upstream/main` | **Unavailable (2)**: Node/npm metadata, Python 3.12, generated assets and installed browser binaries observed; full product Python distribution metadata and Windows host unavailable. Node 22 differs from recommended CI 24. |
| Focused runtime/composition/host/migration tests | **57 passed**, independently repeated after review; about 0.61 seconds. Synthetic/source contracts only. |
| Integrated affected Python selection (25 test modules) | Final run: **243 passed, one Windows-only skip**, about 2.94 seconds. An initial failure exposed a Windows-only constant used by a mocked agent worker; `getattr(..., 0)` preserves Windows flags and allows the synthetic test. Its eight-test module and the integrated selection were rechecked. Native startup flags remain unavailable. |
| `npm run typecheck`; `npm test` | Typecheck passed; Node tests: 260 passed, one skipped, zero failed, about 14.85 seconds. This does not establish the full aggregate or browser scenarios. |
| `npm run build` | Existing Vinext build passed. The static experiment rejects client-only desktop hosting; it does not prove static hydration or storage equivalence. |
| Existing router HTTP/WS tests | Two passed with synthetic loopback services. Initial sandbox listener denial was resolved by running the same owned-listener probe with the required host permission. |
| `npm run docs:check`; `npm run audit:public`; `git diff --check` | Passed. New docs were staged before the final link check. Public scan covered the sanitized history and working source. |
| `npm run check:changed -- --base upstream/main` | **Failed/incomplete**, not a full pass. Evidence `a446cfba-de08-4526-a734-b9016b8621f3`: resolved base `ba0b7c3`, available unchanged source snapshot, failed `npm:check` because `pyaudiowpatch` is unavailable during Python collection. Browser/Windows/docs/audit commands later in that aggregate are **not run**; separate successful checks above do not rewrite its status. |

The standard aggregate record and additional private probe reports live under
ignored `output/checks/`. The record identifies the precommit source snapshot;
the final Windows-constant correction is separately rechecked. Full product
browser/package checks belong to hosted CI, while native Windows 11 25H2,
protected TEST credentials and real game/playback evidence remain independent.

### Frontend phase continued on 2026-10-28

The [static adapter and comparison contract](r19-host-experiment.md#explicit-static-desktop-adapter)
now have an actual client-rendered build, pinned local fonts, a stdlib-only Python
loopback host and a restricted frozen `frontend-experiment` profile. Source Vinext
remains available and default. The new profile permits only the frontend child;
the stdlib diagnostic still permits none, and the full runtime remains disabled.
No installer is built. PR #59 and its dependency branch are unchanged.

Focused host/runtime/local-access checks: **227 passed** on task-local Python
3.12.13, including real owned loopback listeners, startup and per-request file
verification, malformed Host/Origin, route isolation, retained immutable chunks,
empty/private tree rejection, MIME and profile dispatch. Six build/comparison
unit tests and typecheck passed. These are separate source/contract checks; the
browser report and hosted frontend executable evidence must be assessed on their
actual source/build identities before claiming those gates passed.

The actual local Chromium/Firefox comparison subsequently passed for build
`3332793ef3e6f75b0ff0039d4d9df8c3082f9a4cd086d2cc10d861ed259ad551`,
including same-origin host swap and browser restart with authored persistent
localStorage/IndexedDB/OPFS, actual worker/WASM English OCR and old chunks.
Both viewport/zoom and lookup pixel comparisons were exactly equal. This is a
temporary synthetic profile observation, not a real-user extension/profile or
Windows 11 pass. Detailed versions and limitations are in the host experiment.

The continued Node run passed **266 tests with one skip** after granting the
owned process/loopback probe its required host permission. The preceding
`check:changed -- --base upstream/main` record
`1b509abb-f236-4478-a0e4-1adcec1112b7` remains **invalid/incomplete**: its aggregate
failed in the sandboxed Node run and source changed during execution. Later
commands were not run by that aggregate; separate successful checks do not amend it.
The stable-source repeat `29b5ec73-d344-48de-93d1-9948e3e6da6f` is **failed**,
with available source/base evidence: typecheck and 266 Node tests passed (one skip),
then Python collection stopped because macOS lacks `pyaudiowpatch`. Remaining
aggregate commands were not run. Full browser/package validation remains hosted.

The first continued hosted run `40761371026` at `50ca8a0` passed the stdlib
diagnostic and protected TEST state jobs. Its frontend build failed before browser
or frozen-host validation because Windows Git converted the pinned OFL notice to
CRLF. Explicit `-text` attributes now retain the exact upstream notice bytes in
both source locations; their original license hash is unchanged. This failed run
does not establish frontend acceptance. The affected Windows job must be repeated.

That repeat, [hosted run 40762619844](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40762619844)
at exact commit `96ed0df69533a72257869a10b4d3b0ecd2183ca6`, passed all three jobs.
The frontend observation contains Chromium 156.0.8078.4 and Firefox 157.0 with
zero pixel differences, actual worker/WASM OCR, persistent synthetic browser state
and confirmed cleanup. The relocated frozen frontend served manifest-exact bytes
without developer PATH and observed no application/data writes. Its frontend build
identity was `22d0f0cf26d8216cd1573adbef9b273ef1267ecc4d61d10aac85f71489c24435`;
the executable SHA-256 recorded by the job was
`caeaf47095f9c30dd1141ea79815c6a9590c26f243978915f8e6487b6d8b418c`.

Downloaded metadata artifact `12848857172` was verified against GitHub's ZIP digest
`efb08a55548f2028641fafc3b6fe3081cb21493bbd05f5768b670016ae9d7192`,
then checked for exact source/build identity, passing owned cleanup and incomplete
rights/native scope. The binary is deliberately not uploaded, so its recorded
executable/provenance hashes are job observations, not independently downloaded
binary verification. The old Python supplier, exact-output redistribution, full
game toolchains and Windows 11 acceptance remain unapproved; `r19_complete` is false.

### Continued integrated source candidate

[Full hosted run 40765392618](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40765392618)
at `8c8a4e90a1337ff82b8150c80487b7ac7042c730` passed source audit, the complete
source check (**1736 Python tests passed, one skipped**), all five browser groups
(desktop/setup/capture/offline/OCR), `required-checks`, packaging and extracted
source-ZIP validation. Publish was skipped. This is the existing source-style
candidate, not an accepted full frozen runtime or installer.

Downloaded source artifact `12851521128` matched ZIP SHA-256
`27db246196994a088509dd62fcc5ae1c74836522710b3fee0bf24e8193796c2b`.
Every `SHA256SUMS` entry matched downloaded bytes; `PROVENANCE.json` identified
the exact `8c8a4e9` source and shared **1.0.12** revision
`2e84f74cf77ea4773463331c7ecde0b05faf31f8`. Downloaded gate artifact `12851955008`
matched `dd2f7564f0f20240661a36902f35b7f23f84894bc12321f73098ee8814291f51`
and reported success, verified identity, full/valid scope, equal tested/workflow
commits and no errors. Its event was manual dispatch; PR base freshness is not
applicable, so this fork evidence does not replace the upstream PR required context.

Subsequent commits change only managed build/probe/workflow isolation and its
documentation, with actual helper validation at `d297b42` recorded in the
[helper experiment](r19-compiler-free-helpers.md). Production UI/API code is unchanged
from the fully checked source candidate. Freshly fetched `upstream/main` and PR #59's
head remained `ba0b7c3` and `8369c953` respectively. Full R19 rights, native Windows
11, serviced Python supplier and supervised-update gates remain explicit and open.
The frontend/stdlib/protected-TEST workflow also passed again at `d297b42` in
[run 40768109482](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40768109482).

The quarantined Windows diagnostic workflow builds from an observed official
3.12.10 installer and exact recorded packaging wheels. That old installer is
deliberately **not** an accepted maintained-runtime supplier. It validates its
publisher signature, relocates the onedir executable to a Unicode/spaces path,
removes developer PATH entries, observes candidate/data writes and uploads only
sanitized metadata. It does not upload binaries, private receipts or caches.
Windows Server bootloader evidence cannot replace Windows 11 acceptance.

### Hosted diagnostic observation

[Diagnostic run 40749551495](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40749551495)
passed on Windows Server 2025 at `09df6c7c533563af0948f0ac8b52defa651caf01`.
It built and started the relocated stdlib-only onedir diagnostic, with developer
PATH removed and no observed application/data writes. The first attempt had
failed before building because setuptools' nested vendored metadata was counted
as a second wheel identity. The corrected parser accepts one top-level identity
and rejects genuinely duplicated top-level records; 34 focused tests and an
independent review passed.

Downloaded **metadata only** was verified against GitHub's artifact digest:
`1a46b62c9ee1727316df52c3b85893b6666a870612af3ad45b690f489a8eb24e`.
Its tested executable SHA-256 is
`239d070bbfd3d151d809d2db018cfcfc3091e045ffd0a15f9050d9ec2348c1a2`;
the candidate-provenance file SHA-256 is
`346a785c7aca179d3b4a8905d63546afa966b94da997a48a91550ed724e8c15a`.
The metadata binds the exact source and explicitly retains `r19_complete: false`,
doctor exit 2, pending exact-output redistribution review and unavailable full
toolchain/native acceptance. No candidate binary or private input receipt was
published or downloaded, so this is not independent verification of a delivered
runtime artifact, signing or attestation.

The first separate full source candidate check at `d2ff584` ran 1,682 Python
tests successfully, skipped one and failed cleanup of one newly added migration
fixture on Windows. SQLite's transaction context does not close its connection;
the assertion reads now use explicit `closing`, including failure paths. The
production verifier already closed connections and was unchanged. Both reviewers
rechecked the eighteen host/migration cases without skipping or weakening
cleanup. The latest hosted rerun and the separate upstream PR gate are tracked
in [draft PR #60](https://github.com/Firebird55/Game-immersion-toolkit/pull/60).
Upstream fork workflow approval requires a repository admin; the current account
received HTTP 403. A manual fork candidate run is additional evidence and cannot
replace that PR's required check context.

## Integrated extracted runtime continuation (2026-10-29)

The new `runtime-experiment` build profile composes the static frontend with
the complete backend/dynamic-reader import closure, workers, reviewed-in-source
FireRedVAD resources and a separately collected ASR executable/native tree.
Credential-writing prompts and the source updater remain disabled. All existing
frozen game-helper/codec rights refusals remain in force. The production
`runtime` profile remains hard-disabled; approval-like strings cannot enable it.

The observed supplier is [Astral's immutable 20261026 release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026),
CPython **3.12.16**, Windows x64, source revision
`fa506e0858ac9f2cc5b289c137b888a2aa24d1ee`. Its install-only archive SHA-256 is
`590dfcbe3a34c07301e6332e13e2188b98655cd072b08afa45a7998dc4c22bc5`,
independently downloaded and matched against GitHub's asset digest. The
[Python release](https://www.python.org/downloads/release/python-31216/)
is a source-only security release; the Astral binary is a distinct supplier,
not a new PSF Windows installer. Exact-output incorporated notices, CRT/native
closure and supplier acceptance remain open. Existing diagnostic observations
using 3.12.10 remain historical and do not establish maintained-runtime acceptance.

Before collection, `record_runtime.py` compares actual installed interpreter and
wheel payloads against their archives and records exact artifacts, installed
hashes and actual notices. Missing standalone notice text retains complete
METADATA as explicitly incomplete evidence, never an inferred license approval.
The frontend, required application resources and source-pinned VAD model hashes
are bound to the same clean commit. The complete extracted file inventory is
checked again after relocation; binaries are not published.

Fixed frozen probes use new build-bound synthetic roots and an allowlisted OS
environment without inherited developer/loader/account variables. They exercise
actual native imports and all 25 registry adapters, VAD on authored silence,
separate ASR native loading, real index/language workers on authored GoldSrc
fixtures, catalog-library export, and frontend plus real API HTTP/WS together.
API background updates, game discovery and OCR warmup are mocked in that probe
process. No account writes or installed game files are used. The ASR import
probe does not establish model inference; catalog-library export and worker help
do not establish full game export. Loaded native images must originate in the
selected application tree or Windows; main/ASR families remain separate.

Local development doctor returned 2 for unavailable macOS native dependencies.
The focused source contracts passed **101 tests** after granting the owned
loopback tests their required host permission. A sandboxed first attempt passed
93 and failed eight loopback binds; it is not a pass. Windows build/probe results
must be recorded after the integrated workflow executes. Local `check:changed`
record `70735e9b-3fc3-4c89-8a3b-95cea5a231c1` remains failed: typecheck and
271 Node tests passed (one skip), then Python collection lacked macOS
`pyaudiowpatch`; subsequent aggregate checks did not run. The preceding sandboxed
aggregate also failed on process/loopback restrictions. Neither is a full pass.
No installer, release,
tag, Pages publication, live migration or change to PR #59 is part of this phase.

Public compatibility watch returned 2 on 2026-10-29: docs/UI changed, with no
endpoint additions or removals. Public API/settings/language documentation and
the public landing page were inspected without an account. Full live lookup/UI
compatibility remains open; the baseline is unchanged.

### First integrated Windows observation

[Integrated run 40844344068](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40844344068)
passed at clean commit `cb6a3addcd9abf0b941aebf4cb7a506ca29e0099` on hosted
Windows Server 2025 with the pinned CPython 3.12.16 supplier. The relocated
application had only `ProxyTranscriptRuntime.exe` and its separate
`asr/ProxyTranscriptAsr.exe`; no external Python/Node/npm/dotnet/compiler was
discoverable in the cleared child environment. Application files were read-only;
content hashes were unchanged and owned process/fixture cleanup passed.

The actual runtime imported all **25** registry readers, ran FireRedVAD inference
on authored silence, executed game-index and language workers on authored
GoldSrc fixtures with retained Chinese translation, exported an authored catalog
through the library, and passed frontend/API HTTP plus a complete WebSocket
snapshot. Main and ASR processes observed **211** and **59** loaded images,
respectively, all originating inside their application tree or Windows. This
proves observed native loading, not complete CRT/native or Windows 11 acceptance.
ASR model inference, native OCR/frame capture, voice refresh, installed-game
formats/playback and full game-export execution remain unrun.

Downloaded metadata artifact **12883719274** matched GitHub ZIP SHA-256
`4a462a8c0c653f3ffb15a3a4bc54279c258fa080996b46494004f8f9c0996e58`.
Its source/build/scope/cleanup fields were checked. The independently hashed
inventory matched the probe's
`8329ecdb64b7f48df6b267cc5d0f33fa4dbaa37b10e268e8e1a3bba44efe9be8`:
**1,301 files**, **540,463,762 bytes**, **57 component identities**, all rights
gates still pending and `r19_complete: false`. Recorded executable hashes are
`a082adde39246f2c73cddd79103c964e0adb6e2c4f59723132f3d5e9ef2f255d`
and `79d37668d05223b50b612418beb573f88854e834fed8223734978538dfbae040`.
Those match inventory entries, but remain job observations: no binary was
uploaded or independently downloaded. Size is an inventory observation, not an
R02b optimization result.

Earlier integrated attempts failed closed: `40841870506` compared pip-rewritten
RECORD metadata as immutable payload; `40842311387` found non-JSON UTF-8 email
headers in license metadata; `40842833946` found the generic PyInstaller hook's
wrong `webrtcvad` distribution identity; `40843631872` collected unused OpenCV
Haar-cascade examples under `cv2/data`. The corrections preserve actual payload
hash checking, full available notice bytes, the pinned `webrtcvad-wheels`
distribution and the private-tree gate. No failed attempt counts as a pass.

### Integrated follow-up with Setup and directory verification

[Run 40845350877](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40845350877)
passed at clean `63d0602aa7a2f1e0f0aefeb1e834f60e92583b47`, including **104
affected contracts** and the complete extracted probes. Frozen Setup no longer
requires Node/npm or recommends an Endfield SDK/source installer; it reports
explicit pending runtime/codec/OCR/toolchain gates. Source Setup is unchanged.
The actual frozen API's Setup response is checked. The pre/post inventory now
includes directories, detecting directory-only application writes as well as
file creation, deletion, renaming and content changes.

Downloaded artifact **12885490202** matched ZIP SHA-256
`e43844daea4fae794b2588a5fe808764e2e55cd18186c082b33be4144b6630ab`.
Its matching source/build identity, incomplete acceptance, successful cleanup,
two executable entries, **1,301 files**, **628 directories**, **540,464,283
bytes**, 57 components and all pending rights gates were verified. Inventory
SHA-256 `96abce9641e7e9419dc4cd6540e791f3ce60b29e4713012673e843643239b063`
matches the probe receipt. Main/ASR executable hashes are respectively
`b2c3cc4cc31bd2a0b218772835653db9e5377625085bda078de329e7e045a0d1`
and `da41b4fb76a0881a48e816b4fe0e309f15c47737510812f2374bc7837924abe2`.
They remain job observations, not verification of downloaded binaries.

At the same exact source, all three frontend/stdlib/protected-TEST jobs passed in
[40845350966](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40845350966),
and both authored managed/Node helper jobs passed in
[40845350864](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40845350864).
These preserve their existing narrower scopes. Local affected setup/runtime
contracts also passed **65 tests** (one existing deprecation warning).

PR #59 remains open and unchanged at `8369c9534762cd2232fb44424772bd6b5a72b6d2`.
The upstream required PR context at this head remains `action_required` in
[40845361053](https://github.com/Firebird55/Game-immersion-toolkit/actions/runs/40845361053).
Current-account admin approval was previously refused; manual fork observations
do not replace that context. No ready-for-review transition, merge, installer,
release or production migration is enabled.

### Full source/browser candidate

[Run 40842180569](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40842180569)
at `1fdf1608d4a6a1a460a7528d316d3514b95a568f` passed source audit, full source
checks (**1,746 Python tests passed, one skipped**), all five browser groups,
`required-checks`, packaging and extracted source-ZIP validation. Publish was
skipped. Setup's first attempt failed a 30-second page navigation in the React
fixture; that job was repeated unchanged and passed. The original failure is
retained; no test, timeout or threshold was relaxed. Other successful groups
were reused by the workflow's aggregate.

Downloaded source artifact **12885241570** matched GitHub ZIP digest
`ca9342b3b2ec69480c550f98f97d9f6512899cf8c6022d99b60a282e524506e3`.
All **12** SHA256SUMS entries matched actual downloaded bytes. PROVENANCE binds
the exact source and shared component **1.0.12** revision
`2e84f74cf77ea4773463331c7ecde0b05faf31f8`.
Downloaded gate artifact **12884817934** matched
`afa0dfc8379bfe1e79c9020e8f43625d6c0e8314764baaadf0f7dd9b9d533f47`
and confirmed success, verified identity, full valid scope, equal tested/workflow
commits and no errors. Its manual event has no PR base-freshness evidence.

Later changes affect frozen packaging/probes/Setup and their evidence; the
affected contracts and actual frozen Setup are verified at `63d0602` above.
This source-style ZIP remains separate from the quarantined extracted runtime.
Neither observation completes R19 rights, Windows 11 or supervised-update gates.

The final documentation-only `check:changed` invocation
`ab57f584-42c8-4e37-93d2-f6f694f1bbaf` conservatively selected full checks for
the packaging README, then again stopped at unavailable macOS `pyaudiowpatch`.
It is not a full pass. Documentation links/generated guides, public audit and
diff checks were run explicitly for the evidence-only changes.

### Integrated owned NTE bridge

[Run 40877210344](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40877210344)
passed **112 affected contracts** and the extracted runtime probes at clean
`d6e593ad2853b155ea2ed9faae7c25cceb31387a`. Collection now requires the owned,
self-contained NTE bridge and verifies its exact current source inputs, nested
manifest, runtime-package payloads and notices. The frozen native probe executes
only its fixed read-only runtime identity operation: app-local CoreLib
**10.0.14**, SHA-256
`69d56e12535d3a8f2f8f89ac8f97577e6dc788d26f2e7b69be8fb5f6ff17ff28`.
Normal NTE game execution remains blocked; external UEExtractor/CUE4Parse/Oodle
files are rejected from this owned subtree. Endfield and REE blocked build
manifests cannot be collected as NTE resources.

Downloaded metadata artifact **12899640632** matched GitHub ZIP SHA-256
`5e21d09c92fe3643093384876d15c127edbfbae7b079236a8f90349a5919244d`.
The inventory digest independently matched the frozen receipt:
`a416000639832711cd43bd24606acbdab7504d4366443e476fd011292a15f1bf`.
Source/build identity, **1,502 files**, **633 directories**, **622,316,061 bytes**,
57 Python/build component identities and the separate NTE helper identity were
checked. Its four executable entries are the main runtime, isolated ASR,
`NteReader.exe` and the pinned .NET runtime's `createdump.exe`. No SDK/compiler
is collected. These sizes and hashes are metadata observations; no binary was
uploaded or independently downloaded, and no R02b size/performance pass is claimed.

The actual native/registry/VAD/worker/ASR/frontend/API/WS/Setup probes passed
with cleared developer/loader/account environment, read-only application files,
unchanged file/directory inventory and confirmed owned cleanup. The receipt keeps
all rights gates pending, native Windows 11 acceptance unavailable,
`game_execution_approved: false`, `r19_complete: false` and `installer: not-built`.
Previously unrun native/game/model/export scopes remain unrun.

At subsequent clean `a72c703`, the actual owned NTE reflection fixture and private
precompiled Endfield/selective x86 REE probes passed. Endfield/REE remain excluded
from runtime collection and distribution. Their exact scopes, digests, original
failure/correction and remaining rights/Windows gates are recorded in the
[compiler-free helper evidence](r19-compiler-free-helpers.md#continued-windows-evidence-2026-10-29).
That REE-only build/probe correction did not modify the integrated runtime code
or NTE builder tested at `d6e593a`. Frontend/stdlib/protected-TEST jobs also passed
at `a72c703`; this does not claim a new full source/browser/package run.

### Critical recheck of collection and Windows inventories

Review reproduced a destination-link failure in the NTE collector: an existing
private evidence `helpers` junction could receive copied bytes before validation
failed. `06eeb97` checks that ancestry before any destination write. Both authored
external-tree preservation regressions now pass. Review also found that several
Windows probes omitted Hidden/System entries; the shared scanner and actual
Windows attribute/mutation fixture are recorded with the original fixture failure
and correction in the [helper recheck](r19-compiler-free-helpers.md#critical-recheck).

[Integrated run 40892020624](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40892020624)
passed **114 affected contracts** at clean `3837b6dd6222ab3a2fd057e498ea8a847fc45547`, including the corrected
Windows inventory fixture and the extracted native/worker/ASR/frontend/API/WS/Setup
probes. Downloaded artifact **12906455506** matched GitHub ZIP SHA-256
`01d416893fcf4f86ddc1260ff31777e5c1f650c9d0cc44e91ed43fa39da49593`.
Its inventory digest independently matched the frozen receipt:
`2a8c34f1eed254050c79d58fd7184e36c9ef02078825af85f8ddd612bc995cbf`.
The same four executable roles, **1,502 files**, **633 directories** and
**622,316,065 bytes** were recorded. The four-byte difference from `d6e593a`
is an inventory observation, not a measured optimization. Source/build identity,
app-local NTE identity, passing cleanup, no observed application writes and all
pending rights/native/full-R19 gates were checked. No binary was downloaded.

Managed/NTE/Node, frontend equivalence, frozen frontend and protected-TEST jobs
also passed at that same clean source. Endfield/selective REE retain their separate
private blocked scope. The [recheck metadata table](r19-compiler-free-helpers.md#critical-recheck)
records all exact ZIP digests. Native Windows 11 25H2, real games/voices, model/codec
closure and owner-aware update/recovery remain unaccepted; no installer is built.

The fresh [full source/browser candidate run 40888558019](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/40888558019)
at `06eeb9790ef7f2103343327a3ee64f6e5001c766` passed source audit, full source
checks (**1,759 Python tests passed, one skipped**) and all five browser groups.
Desktop first failed a 30-second click because the account-preferences dialog
remained open. The failed group passed on one unchanged repeat in Chromium and
Firefox across its complete viewport/zoom matrix; the original timeout is retained,
and no assertion, retry, timeout or threshold was changed. The other successful
groups were reused by the aggregate, not silently rerun or relabelled.

Downloaded successful gate artifact **12905408338** matched ZIP SHA-256
`74922230ef97cf4d043c7348be1e025f24668e32b14cfc65afe3258ef0c8791c`.
Its verified identity, full/valid scope, equal tested/workflow commits, passing
audit/check/browser jobs and empty errors were checked. The manual event has no
PR base-freshness evidence and cannot replace the upstream PR required context.
Later commits change only the Windows probe inventory and its authored fixture;
their native execution is independently verified at `3837b6d` above.

Packaging and extracted source-ZIP validation also passed in that full run;
publish was skipped. Downloaded artifact **12905867145** matched GitHub ZIP SHA-256
`cc8d1aff6b3b2671e9912067c2b27a3a39208bbda04a86f20730d88575611f0a`.
All **12** SHA256SUMS entries matched downloaded bytes, including the actual
distribution ZIP. Outer and nested PROVENANCE agreed on exact source `06eeb97`
and shared **1.0.12** revision `2e84f74cf77ea4773463331c7ecde0b05faf31f8`.
This remains the existing source-style distribution, separate from the quarantined
extracted runtime and its narrower native/rights evidence. No installer, tag,
release, merge or Pages publication occurred.

## Downloaded acc68be checkpoint

[Integrated run 41144087092](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41144087092)
passed at `acc68be0f6f47cb9a0cd928c9394743483c40c24` on hosted Server 2025,
image `windows-2025-vs2026/20261021.278.1`, with **628 Windows contracts** and
actual relocated frozen probes. The [download review](r19-frozen-checkpoint-20261031.json)
binds both artifacts, build identity and inventory SHA-256
491f4277802249fa7cee42cffcd5cae642ed0f390d926be7e31ca45513d9bf5b:
1,535 files, 641 directories and 624,729,673 bytes. Native binaries stayed
runner-local; the downloaded evidence contains source and sanitized metadata.

The grant-bearing Xiph kit, all six source inputs, pinned codec/notice bytes,
actual decode/fault/DLL-origin receipts, real authored Half-Life unvoiced export
and Portal original-PCM paths matched. All twenty retained Python supplier
texts plus the Windows-checkout provenance bytes reached central delivery;
the exact ONNX incorporated notice and windows-capture LICENCE also matched.
Later Flatbuffers source-notice collection is outside this checkpoint and needs
its own frozen output. Native output attribution reports 461 exact, seven
ambiguous, two generated and 91 unmatched files; no hash match grants rights.

The actual frozen host passed normal stop, child failure, host crash and absent
index readiness with all retained runtime/Windows-console handles signaled and
ports released. A foreign-ready-listener case refused adoption without stopping
the outer fixture services. API external effects remained mocked. No account,
installed game, actual OCR/capture or trained-model inference was exercised.
Every rights/production/Windows 11/R19 gate remains open.

The separate full source run 41143154298 at `1958866` passed 1,933 Python tests,
one skip and five subtests, all five browser groups, the aggregate and extracted
source-package validation; publish was skipped. The initial capture attempt
timed out on Firefox's bare loopback document before VDO code. A bounded
unchanged local reproduction passed, followed by one successful same-head
failed-job retry. The original failure remains recorded; no assertion was waived.
Downloaded tested-source artifact
13020538696 matched 33,409,219 bytes and SHA-256
98fa6332557452e4678cf848f99c2c27f057ef082e08ca272fcf1cfe2576db0a.
All twelve SHA256SUMS entries and outer/nested provenance matched source
`1958866` and shared 1.0.12 revision `2e84f74cf77ea4773463331c7ecde0b05faf31f8`.
The matching required-checks artifact 13020952307 passed identity/full/scope
validation, with manual-event base freshness explicitly not applicable. This
source-style ZIP remains distinct from frozen and native Windows 11 acceptance.

The later `12d0d0e` frozen checkpoint passed **640 Windows contracts**, the new
Flatbuffers central source notices and the [guarded cold-slot experiment](r19-guarded-slot-probe.md).
Downloaded metadata artifact 13021800802 matched SHA-256
823d4a7e995d0cb6f6ba89ac0d6c97923cf96266c15102f09ec1bcf7e0f42f9b.
The [review ledger](r19-frozen-checkpoint-20261031.json) retains both checkpoints
and the source-package evidence, including their exact different source heads.
It grants no acceptance to subsequent changes without new matching evidence.

At `0b76427`, [run 41152516394](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41152516394)
passed **649 Windows contracts**, source build/rebuild and the same actual
frozen/guarded cold-slot protocol after Job/observer handle-cleanup hardening.
Downloaded metadata artifact 13023663874 matched 1,232,252 bytes and SHA-256
f6dd602407e463074c7783ec42f4a5ed420053a653bf195a5f3ebf62b880af03;
source/rebuild artifact 13023871979 matched 1,095,191 bytes and SHA-256
12030a0576098fc9c231bd3f7d892da7411feb51a3a570cc0b1552fdd724d1f9.
The independent review rechecked exact source inputs, notices, native bindings,
all host outcomes, all nine cold-slot phases and the 29 blocked real-source
observations. Its inventory is 1,537 files, 642 directories and 624,746,487 bytes.
All production/rights/Windows 11/R19 gates remain unchanged. The later immutable
frontend snapshot adapter and suspended-writer work are outside this checkpoint.

The subsequent `4046147` [run 41153315339](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41153315339)
passed **664 Windows contracts** and the same frozen/source/guarded probes.
Its frontend snapshot cases use authored manifests in source Python; this does
not establish frozen warm routing or native chunk continuity. Downloaded metadata
13024576600 (1,232,310 bytes; SHA-256
b9c965422b5eb7a83461bba8e92c601e8d0b37398121fef199aa19226547cf61)
and source/rebuild 13023941191 (1,095,193 bytes; SHA-256
d97c28a97ddc0a7f8c48967e870d977308057d5e417ca1d6839eb6d946740d4f)
passed the independent source/notice/inventory/module/host checks. The inventory
contains 1,537 files, 642 directories and 624,749,411 bytes. Subsequent suspended
creation and tool-diagnostic changes require new matching native evidence.

The later full source [run 41152537471 at `0b76427`](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41152537471)
passed 2,006 Python tests, one skip and 27 subtests, plus four browser groups.
Setup failed in Firefox while waiting for the React fixture's `NEW VERSION`;
the aggregate failed and packaging was skipped. An unchanged local four-case
run passed. A controlled mock connection/message ordering reproduced the same
failure: an initial HTTP result could enable controls before WebSocket open
reset state and requested a newer synthetic snapshot. The fixture now gates
that exact HTTP-before-open order, then waits for the post-open snapshot to
render before publishing versioned events. Its original assertions/timeouts
remain, and the local four-case matrix plus controlled reproduction pass.
The observed CI failure remains recorded; no current full-source pass is
inferred from that local correction.

The corrected `f11e96d` [full source run 41155289055](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41155289055)
then passed 2,058 Python tests, one skip and 36 subtests, all five browser groups,
the aggregate and extracted source-package validation on its first attempt.
Publishing was skipped. Downloaded tested-source artifact 13025361570 matched
33,555,951 bytes and SHA-256
4a28fc447c33555a2d24bf632c74821cc90225835ffd26d05d88b001d10ecd9c.
All twelve sums and outer/source/shared provenance were verified, including
the unchanged scoped Xiph source kit. The source ZIP SHA-256 is
fba8da886351c36d1158e591208ce422c732da945541c00491a06a94a6c97574.
The matching required-checks artifact 13025580858 passed full/scope/identity
validation, with manual-event base freshness not applicable. This is exact
source-style package evidence; the later pinned CMake input and autonomous
keeper work need their own matching checks. The earlier setup failure remains
in the ledger and no ordinary-user/native Windows 11 gate is closed.

The subsequent `a079232` [integrated run 41157097572](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41157097572)
passed 689 Windows contracts, all existing frozen/cold-slot cases and Xiph
source/rebuild. Downloaded metadata 13025298596 matched 1,232,316 bytes and
SHA-256 a98a30b6e0e834e93ff140c7590c125e7b0570a9724c425b14b2f35051b86cef;
source/rebuild 13025661915 matched 1,095,193 bytes and
82d48e7e6d5294738b84e5fb64619b60901cce8c1c90b5f658532d8156f67e88.
The independent review retained every preceding source/notice/module/host
assertion. Its 1,537 files, 642 directories and 624,765,091 bytes are bound in
the [checkpoint ledger](r19-frozen-checkpoint-20261031.json). This historical
output contains no receipt for the new living-keeper experiment.

The same head's [full source run 41157232246](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41157232246)
passed 2,070 Python tests with one skip and 58 subtests, but failed one Windows
raw ZIP-name refusal case. Browser and packaging jobs did not run. Python had
normalized the name before the parser inspected it; the fixture also needed to
preserve its authored raw header bytes on Windows. The parser now checks
`ZipInfo.orig_filename` before separator/NUL normalization, and the fixtures
verify actual local and central header bytes. The failed result remains in the
ledger; this source correction requires a new matching hosted result.

The first `c18d07a` keeper attempt, [run 41160402137](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41160402137),
stopped before freezing: 721 affected contracts passed and one logging test
failed. Uvicorn successfully initialized with the owned NUL streams, but the
test incorrectly required automatic colors to be disabled. Windows CRT's
[`_isatty`](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/isatty)
detects character devices, so that POSIX-specific expectation was invalid.
The corrected test requires actual Unicode log formatting and non-inheritable
owned stream descriptors, retaining NUL read/write and existing-pipe behavior.
No production implementation was changed for this failure. The original result
is retained; neither a frozen build nor a keeper receipt was produced.

The `e8a76d4` [full source run 41161762483](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41161762483)
passed 2,138 Python tests, one skip and 62 subtests, all five browser groups,
the aggregate and extracted source-ZIP validation on its first attempt.
Publishing was skipped. Tested-assets 13027753225 matched 33,601,963 bytes /
SHA-256 cad8928450899e9e9203178782f6d0f6cb388e1ad98aa4211942d756848cefab;
all twelve checksums matched, including source ZIP
c112e279fa9b7104f45178912aa4c0dd20808a79883ccf744ffb2eb11e7d2101.
Outer and nested root provenance were byte-identical for exact source
`e8a76d408ee8ddd79f75bbbbbcd08681749c06e0` and shared 1.0.12 revision
`2e84f74cf77ea4773463331c7ecde0b05faf31f8`. The two retained Xiph source kits
matched Git bytes. Five supplier/vendor provenance JSON files were semantically
and LF-normalized text equivalent to Git, with ordinary Windows CRLF bytes;
they are not described as raw Git-byte matches. Required-gate 13027198460 and
package-evidence 13027653466 passed exact identity, full/scope and stable-source
checks. Manual-event base freshness remains not applicable. This is source-style
package evidence, with no frozen or ordinary-user Windows 11 acceptance.

The same head's [integrated run 41161553165](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41161553165)
passed 722 Windows contracts with zero skips, freezing and the existing
relocated native/C1/cold-slot steps. The new keeper then refused a guardian
descendant before creating its writer cohort. Its failure-only artifact
13027876505 matched 813 bytes /
5712699b524eafcff0129483be91e6505dc335e255fed56d02af57da0c5f807c.
Both cases are empty, independent blocked-source observations are zero and
cleanup remains unconfirmed/recovery-required. The external five-minute
deadline ended a failed live hold; it proves no keeper-loss containment.
The descendant's identity is unknown. The later failure prevented the original
combined metadata upload, so the earlier job-step results are not a new complete
downloaded frozen checkpoint. The collector now preserves those earlier
sanitized observations independently of a later keeper failure; receipt and
workflow status must still be checked separately.

At `dc62a46`, [run 41163848906](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41163848906)
passed 735 Windows contracts with zero skips, freezing and the earlier
native/C1/cold-slot steps. The preserved metadata artifact 13028966469 matched
1,233,308 bytes / SHA-256
b0f5efeb723fbdcd4a8603cd52db602e2784099ddf5190435b893387d9b9c4d0;
source/rebuild 13028875035 matched 1,095,193 bytes /
cb08a16c7bfc138e0216d22d11d68b203d735b003357b299129611234f6858c5.
The independent review retained every preceding source/notice/module/host/slot
assertion. Its inventory has 1,537 files, 642 directories and 624,783,815 bytes,
bound by digest 637c2febfb13428e5b15530ca5c0453dcee14c5ba3b7caa81aa3b4050d08dcc0.

The workflow still failed at the keeper step. Separate failure artifact
13029071295 matched 967 bytes /
a61f1d81119c7e8bd31f25da501b0be05ddafa393d588af0906caa32464c69dc;
its receipt is byte-identical to the copy inside the preserved metadata.
The one inspected descendant matched authoritative SystemDirectory `conhost.exe`
through retained read-only observations and was created at or after the guardian.
This remains census evidence, with no admission or termination authority.
The guard refused it before writer creation: both cases remain empty, blocked
source observations are zero and cleanup is unconfirmed/recovery-required.
The later detached-console variant needs fresh native evidence.

Image identity is per job: extracted runtime used 20261021.278.1 while the
separate Xiph source/rebuild job used 20261030.294.1. Actual observed system-DLL
names/hashes matched the historical comparison across the five probe scopes;
this does not transfer rights or Windows acceptance from another checkpoint.
The [ledger](r19-frozen-checkpoint-20261031.json) preserves the failed workflow
alongside the narrower verified observations. Native source provenance, complete
rights, keeper loss and ordinary-user Windows 11 remain open.

At `423e843`, [run 41169070412](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41169070412)
passed 769 affected Windows contracts with zero skips, including all four
default/detached leaf-process cases. The new collection guard then refused an
`other-host-unresolved` input after 239 observed records. Downloaded refusal
artifact 13030418382 matched 520 bytes and SHA-256
25f3fdfe867e369facb851233639dd9de72b78cace721a19aa9ec87831580d16;
its sole fixed-schema entry, source identity and pending/false gates were checked
independently. Collection/freezing did not finish; frozen host/cold-slot and
detached-keeper probes did not run. Source contracts do not supply their proof.

The same head's [ASR run 41169084584](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41169084584)
failed at configure with missing compiler registration. Its bounded nested log
context records `MSB4019` during compiler identification; the exact missing import
and fatal cause remain unknown. Downloaded artifact 13030152316 matched 1,387
bytes and SHA-256
79d8bc8184c6a319669bcea76e1b3d15b86c188d78f2cf68f070f78976257b87,
including exact source/manifest and unchanged gates. This supplies no native
compile, inference, full tool seal or source-input-cohort receipt. Both failures
remain in the checkpoint ledger; earlier narrow passes are not transferred.

The same head's [FFmpeg run 41169075509](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41169075509)
first stopped on a connection reset during input acquisition. One justified
same-head job retry passed three early Windows contracts with zero skips and
reached `build-ffmpeg`, which returned 2. The earlier strict build commands
returned zero; that is not final codec/output or tool-seal evidence. Downloaded
failure artifact 13030628980 matched 467 bytes and SHA-256
af2cdd2a0ed337fbfb1594bf3637a32b8cdc81bca50366a0689e528e9741d38a,
with exact source, no known error code and `unclassified-command-failure`.
Its log tail was not truncated. The compile cause remains unknown, and the
final decode and after-build tool verification did not run. The retry used
the older `20261021.278.1` image; it is not evidence about another job's image.

At `ab84772`, [run 41171329086](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41171329086)
passed 886 affected Windows contracts with zero skips. The main analysis still
refused unknown inputs: 495 current-call rows, 474 native rows, 426 admitted
records and 48 unresolved sources. Its complete bounded census reports 29
api-core, 14 api-crt, one ucrt and four vc-runtime spellings, all in root category
`other`; ASR analysis did not run. These categories do not identify a supplier.
Downloaded artifact 13031377564 matched 747 bytes and SHA-256
3916c89595831595c3e773948883870134f23dc732152bcbf113f9f858af37e8.
Source binding, census and false gates were independently checked. P1, freezing,
host/cold-slot and detached-keeper probes were not reached. A bounded freezer
lookup experiment may test ambient PATH selection; the census alone does not
prove that hypothesis or authorize those sources.

The same head's [ASR run 41171353894](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41171353894)
again failed at configure. Both generated CompilerId projects contain all five
reviewed properties exactly. Eight untruncated nested MSB4019 observations point
to line 37, column 3 in those projects; their import targets remain unknown and
uninspected. Artifact 13031640010 matched 1,680 bytes and SHA-256
2b8a6b4f379a3d6c77d5f400d2e8a2fbfe1e48b99dc33af0079b42569cefba2b,
including independently checked source/gates. This narrows the investigation
without proving a missing filename, native compile or inference success.

The same head's [FFmpeg run 41171349043](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41171349043)
failed at `build-ffmpeg`, exit 2. Its new fixed categories identify
`ffmpeg-makedef-temporary-library`, `make-fatal-error` and `make-recipe-error`,
with no allowlisted numeric code or truncated log tail. Downloaded artifact
13031800496 matched 492 bytes and SHA-256
3353975fa4c79dc72117ca32df7619607b3390ca4d5c3b6503772af8ab630edb;
source and false gates were independently checked. The original makedef discards
the temporary archiver's stdout. That explains a diagnostic gap, not the
underlying tool failure. No final decode or after-build tool seal was reached.

At `702d667`, [run 41174915697](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41174915697)
passed 909 Windows contracts with zero skips, including all seven real PATH
contracts. Both EXE/COLLECT pairs completed, then mandatory P1 refused
`invalid-import`. Artifact 13031904081 matched 498 bytes and SHA-256
ae73fe5c1c26ec9d69f9d2e0d361444a1f1ca2ce8b4b89bf6a8868640a4f2a49;
source and false gates were independently checked. The final inventory and A2
sidecars were not uploaded, so their counts and retention of the earlier 48
unknown bytes remain unproved. Public missing-library warnings stayed at zero;
PyInstaller can suppress unresolved imports, so this is not import closure.
No host/cold-slot or detached-keeper probe ran after the P1 refusal.

The same head's [ASR run 41174924122](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41174924122)
again failed at configure. All ten property comparisons matched, and each
generated project has three present known CPP imports plus an unknown second
import. All eight MSB4019 messages matched the literal template at line 37,
column 3; the actual toolset alias and instance-version suffix remain unproved.
Artifact 13033155032 matched 1,889 bytes and SHA-256
b18022bbfd24c84e924152a004d0418f831facd5d995b8eefd8ea53af48ca434.
Independent review checked source/manifest and unchanged gates. Compiler
selection, native compile/inference and a complete final tool seal are not
established by these observations.

The same head's [codec run 41174918440](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41174918440)
failed during FFmpeg's build. The source-bound diagnostic guard reported
`nonempty-ar` before collecting librarian stdout, with no component records or
underlying LIB error code. Artifact 13032836679 matched 668 bytes and SHA-256
7966cf9b4b153d823972994adfef7d85a4eaf31983e5ee0e05f501e93c53a4dd;
independent review checked the exact source, single entry and false gates.
PowerShell's empty-string versus null environment semantics exposed a concrete
orchestration defect: the two existing wipes could retain empty process keys,
which GNU make can export after a makefile assignment. Both wipes now require
actual deletion and verify absence, with a separate early Windows contract.
The previous raw AR value and final LIB/decode outcome remain unknown; the fix
requires a new native run and does not change the diagnostic source variant,
compiler pins, codec options or rights gates.

At `02c6380`, [ASR run 41181127131](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41181127131)
identified the invalid generated import. Both CompilerId projects and all eight
MSB4019 records contain the fixed mapped-template label and verified
instance-version-field boolean. Each relationship matches one unchanged,
initially sealed auxiliary pair with the exact toolset policy. The actual
target includes the full generator argument's version field as a directory;
it stays outside the declared roots and was not inspected. The three known CPP
imports per project and all ten reviewed Globals still match. Artifact
13034697875 matched 2,049 bytes and SHA-256
58d020c5208facffb91d8ec554cf35d3ad63ed25d5e7167bb4c764fec68ba77f;
independent review checked the exact source, CRLF manifest and false gates.
This run used image 20261030.294.1 and observed VS 18.11.12328.437. Configure
failed before native compilation; no inference or complete final tool seal is
established. The selector fix and its native result remain pending.

The same head's [runtime run 41181114221](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41181114221)
passed 955 Windows contracts without skips, then P1 refused a repeated normal
import name at selected image 430 of 473. The retained inventory identifies
`_internal/windows_capture/windows_capture.pyd`; A2 binds it to the exact
windows-capture 2.0.1 wheel member. Independent static reading of that cached
member reproduces 18 descriptors for 17 case-independent module names,
including both `kernel32.dll` and `KERNEL32.dll`; no DLL was loaded. Refusal
artifact 13035391503 matched 614 bytes and SHA-256
7b23530cb9b10a25a27e3924dde62aaa5658bdc2bb7f67cdcae77810b66bb2ca.
The three completed JSON observations in artifact 13035177079 matched 196,875
bytes and SHA-256
1a997798baf2e7d4c190e9576d94564851a82aa1bb6decaae8760fdb8342e541.
Independent review verified the raw inventory/snapshot bindings, 473 identical
A2 input/final records (431 main, 42 ASR) and unchanged gates. These observations
are from a failed run, with no host or keeper probe. Current output contains no
api-core, api-crt or ucrt basenames: the earlier 44 bucketed files are not proved
retained, and zero missing-library warnings cannot establish import closure.

The same head's [codec run 41181125810](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41181125810)
passed all four early Windows contracts, then hit a download timeout before
building on image 20261030.294.1. One justified retry of only the failed job used
image 20261021.278.1, passed the same contracts and completed build/probes.
The four diagnostic roles now observe empty AR with no error codes. Authored
FLAC decode (1,024 PCM bytes), truncation/CRC refusal, prior-output preservation,
Opus roundtrip/invalid-packet refusal and four candidate DLL origins passed.
Artifact 13035402527 matched 24,210,834 bytes and SHA-256
fb6167d101e1cb31894d1c223d5ed833a43c04d679962739b854f6d6be0e9cbf.
Independent review verified the receipt, all 18 source-kit members, unchanged
source/variant bindings and false gates. The eight regular project text inputs
have CRLF Windows bytes that normalize exactly to the reviewed LF inputs; the
patch is raw-byte identical. The two raw cohorts are not identical. Review also
found an existing `config.log` hash in the public generated-file inventory;
its private projection is pending. No raw log or native payload was downloaded.
This is bounded source-experiment evidence, with runtime integration, complete
corresponding-source/rights approval and ordinary Windows 11 acceptance open.

At `1c2d931`, [ASR run 41196924582](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41196924582)
verified the initial separate CMake module variant on image 20261021.278.1,
with all 8,817 files/163 directories and the exact sole-module postimage. The
original executable/notices and full VS identity remained bound. Configure
then failed: the bounded event log reports `MSB4018` and no MSB4019 records.
That identifies an unexpected task exception, not its task, exception or cause.
All ten Globals and three known CPP imports per project still match; the second
import remains unknown to the historical full-argument classifier. Artifact
13040999035 matched 2,450 bytes and SHA-256
855f3168be12f679e045e89ba32aa074489b9c0a865d012cd63de07cacd5f0b1.
Independent review verified source/CRLF manifest, initial variant and unchanged
failure gates. Native compilation, inference, final tool/variant verification
and the complete source graph were not reached. No environment or compiler
change is justified by that general task-error code alone.

The same head's [integrated run 41196908591](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41196908591)
passed 971 Windows contracts without skips and completed the extracted runtime,
five host cases, nine cold-slot stages and both detached guardian-loss cases.
Independent artifact review binds 1,449 inventory files, 473 identical A2
input/final records and all 473 P1 image records. P1 observes 392 x64 and 81
AnyCPU images, including 173 CLR images. Its 2,708 normal and six delay module
identity occurrences are not descriptor counts or proof of complete loading.
All 113 notice hashes for 57 components and the selected loaded application
hashes match the inventory; this is not an incorporated-rights approval.

Both keeper cases retain actual process-object signals, continuous legacy
exclusion through writer exit, detached console modes and confirmed cleanup.
The cold-slot and keeper receipts contain 29 and four actual source-operation
blocks respectively. The outer keeper remains alive in these cases: keeper
loss, general dynamic writer admission, warm routing and store copy stay open.
Metadata artifact 13041353581 matched 1,333,511 bytes and SHA-256
1b162244abd6f9c13a25210b6b9c0982854549320dea4c4f3082ec4b56d69ceb.
Reference source/rebuild artifact 13041157227 matched 1,095,191 bytes and SHA-256
226d683295d73c9fa77e6078b76d9a763fb21a53523b2e189e8379d0d3285989.
The unchanged approved Xiph source kit is identical in both artifacts, and the
original/delivered rebuild's nine outputs match frozen resources. These are
bounded Server observations. Doctor exit 2, missing old-file retention proof,
complete import closure, rights and ordinary-user Windows 11 acceptance remain
explicitly unavailable or pending; production and R19-complete flags stay false.

The same head's [codec run 41196918141](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41196918141)
also passed, including the four early Windows contracts and the bounded native
decode/fault/DLL-origin probes. Independent review confirms exactly four public
generated configuration records, no private log size/hash or private-inventory
digest, and a candidate identity recomputed solely from public correspondence.
All 18 source-kit files match the receipt. The raw Windows nine-input cohort is
4bd3fb2a7a4f536c571d3786c89c34127ce546c878325cf61d9a83cf9672acd4;
eight CRLF-only transformations map exactly to reviewed LF cohort
a736ba26ad7f6d04bd7f26212bbaeca5d8829c94e1c99b0342c56bbb15085df3,
while the patch remains raw-identical. The official CMake module is unchanged
in this separate FFmpeg route. Artifact 13040643659 matched 24,211,130 bytes and
SHA-256 efe36ef86dd853f5ecefff74a6946a6419f3db3df9bb2c9c3f835f8883e8d6ed.
Source delivery, recipe/component rights, runtime integration and ordinary
Windows 11 acceptance remain open.

## Verified authored-copy checkpoint at ed153ab

[Integrated run 41204305394](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41204305394)
at `ed153abbbf29ab9c7cb5a71c8be58158513cf519` passed 1,018 Windows contracts
without skips on image `20261030.294.1`, then freezing, native/C1/cold-slot,
living-keeper and the new [authored SQLite-copy](r19-frozen-data-copy-probe.md)
cases. All downloaded metadata was independently reviewed. Artifact
`13044112368` has ten exact entries, 1,334,433 bytes and SHA-256
`89e3f21dd887c60a72958612f7765562e812018cd065161b2db989d9160988e6`.
Its 1,449-file inventory matches 473 unchanged A2 input/final records and all
473 P1 identities. The 113 component notice occurrences represent 104 distinct
hashes for 57 components; every hash is present. Application load hashes and
the retained original/delivered-source Xiph rebuild outputs match the inventory.
Native closure and incorporated rights remain unverified.

The authored copy confirms strict drains, four retained writer signals across
two source cohorts, Chinese/context/favorite preservation, source bytes before
restart, logical state after restart, unchanged pointer, stale-barrier refusal
and explicit cleanup. Its nine actual source-entry blocks supplement 29 cold
and four keeper blocks. All three legacy-operation receipt hashes match the
same commit's actual Windows-CRLF source bytes. The copy fixture had zero
WAL/SHM files. It proves no interrupted copy, target activation, global/dynamic
writer lifetime, keeper loss, warm route, user credential/browser/schema
continuity or Windows 11 acceptance.

Reference source/rebuild artifact `13043907363` is 1,095,193 bytes, SHA-256
`ad32e13b8ad2230d914e65c128884a5fb1d31bcd255c387a1654e06ad8a0a626`.
The unchanged approved `7dd55f62…ab7b9` kit retains six inputs and 907 upstream
tar entries; original/rebuild nine outputs, authored PCM, faults and origins
pass. The separate diagnostic and authored-helper workflows also passed on
this head, with their allowlisted metadata independently checked.

The same head's ASR source run failed during configure. Its eight untruncated
records identify `CL` with `TypeInitializationException → ArgumentException`;
the underlying cause, compilation, inference and final tool seals remain
unproved. The separate read-only MSVC census failed before publishing any
artifact. Neither failure is a runtime/source/rights acceptance result.
Doctor exit 2 and all production/R19-complete gates remain unchanged. Exact
download identities and limits are in the [checkpoint ledger](r19-frozen-checkpoint-20261031.json).

## Verified living-owner interrupted copy at 5640d6b

Run `41212338528` at `5640d6b5aa6365402f0872bd097dc6020d596bbf`
passed 1,047 Windows contracts without skips, then the extracted runtime,
native/C1/cold-slot/living-keeper probes and both authored copy cases. Two
reviewers verified the eleven-entry metadata artifact and its exact
inventory/A2/P1/native/notice bindings: 1,449 files, 642 directories, 473 native
records, 57 components and 113 notice occurrences (104 distinct hashes).
The source/rebuild kit remains byte-identical with nine identical rebuilt
outputs. Exact provider/byte identities are retained in the checkpoint ledger.

The separate [interruption/resume receipt](r19-frozen-data-copy-probe.md)
verifies one authored post-file exception, two actual copy-helper attempts,
two partial revalidations, ten actual source-entry blocks, the same living
owner/plan/barrier/generation/leases and explicit cleanup after a fresh source
cohort. WAL and SHM counts remain zero. This is no process-crash/keeper-death,
global/dynamic admission, target activation, warm routing, rights or ordinary-user
Windows 11 proof. Image `20261021.278.1` is hosted Server evidence.

## Verified retained-WAL copy at 5c9db76

Run `41217533269` at `5c9db765d86b2fa7787788dadc1f742dfd478c5b`
passed 1,090 Windows contracts without skips and all selected extracted-runtime
observations on its first attempt. Root and peer verified the twelve-entry
metadata artifact, 1,449 files/642 directories/620,104,421 bytes, all 473 A2/P1
native bindings and delivery of all 113 component-notice references (104 distinct
hashes). The unchanged six-input Xiph source kit reproduced nine identical
outputs; decode, error, cancellation and DLL-origin probes passed. Its actual
build-host tools were CMake `4.4.4` and compiler `19.51.36260.0`.

The separate [C5 receipt](r19-frozen-data-copy-probe.md) verifies an actual
16,512-byte transcript WAL and 32,768-byte SHM, a main-only/full-set semantic
contrast, ten actual source-entry blocks and preserved source/pointer through
fresh-source restart and cleanup. C3/C4 passed again with zero WAL/SHM. The
diagnostic, static frontend, protected TEST and authored-helper artifacts were
also checked at this head; their existing scope limits remain.

The same head's ASR source run `41217577067` stopped before configure: both
Full CLR/x64 children reported an empty default common-data folder. Binding
`PROGRAMDATA` and `ALLUSERSPROFILE` did not repair it. The underlying Shell cause,
compile/probe results and final native tool/source seals remain unproved. This
negative result grants no runtime or rights acceptance. Main image
`20261021.278.1` is hosted Server evidence; doctor exit 2, rights, ordinary-user
Windows 11, keeper-death, global admission and warm-routing gates remain open.
The [checkpoint ledger](r19-frozen-checkpoint-20261031.json) retains exact bytes.

The subsequent `fbcb943dd05ea2b60fe40a15277b1143fa849aa0` checkpoint,
run `41219911357`, passed the same 1,090 Windows contracts and all selected
runtime/C3/C4/C5 observations. Root and peer verified all seven metadata/source
archives and the same inventory/A2/P1/notice/source-rebuild bindings. Its actual
main/reference image was `20261030.294.1`; reference CMake was `4.4.5`.
The separate ASR run `41219931905` again failed before configure. Both default
folders were empty, but all four new DoNotVerify fields were null: no complete
contrast marker was delivered. Null is not an empty-folder observation, and
the failure does not distinguish that call from its marker-expression evaluation.
All existing rights, native, host and activation limits remain.

## Verified populated local grammar copy at a1c5e92

[Run 41225646234](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41225646234)
at `a1c5e9261d1115ba80c73b0fb4d7dcea1c32ff89` passed 1,150 Windows
contracts without skips (one warning, 128.30 seconds), freezing and all selected
runtime/C1/cold-slot/living-keeper/C3/C4/C5/C6 observations. Root and peer checked
the thirteen-entry metadata archive `13051759650`: 1,337,539 bytes, SHA-256
`a57651dea4c9e2fdded92e3cdab91167ab84ddd28ad53a69595eed8525722333`.
Its inventory binds 1,449 files, 642 directories and 620,135,324 bytes; all
473 native A2/P1 records and 113 component-notice references (104 distinct hashes)
were checked. Native payloads remained runner-local. Named immutable source pins
and original supplier notices were checked; no global local source-fingerprint
recomputation is claimed.

The distinct [C6 receipt](r19-frozen-data-copy-probe.md#verified-c6-checkpoint-at-a1c5e92)
adds actual local HTTP/SQLite preservation of one populated grammar override.
Fixed mocked external analysis continues to report proficiency0 while the real
local setter writes4; the separate semantic copy contains exactly one scoped4
row, and a fresh original-source cohort reads4 with localOverride=true. Two
source cohorts, four retained writer signals, ten actual source-operation blocks,
unchanged source/pointer and explicit cleanup passed. C3/C4 passed again with
zero WAL/SHM; C5 again retained the 16,512-byte transcript WAL and 32,768-byte SHM.
These are authored fixture observations, not real account, general populated-data,
export-ledger, settings/browser, target-activation or global writer acceptance.

Reference source/rebuild archive `13050998049` is 1,095,193 bytes, SHA-256
`1552446a8d266f53fe76f75f7b46be318ac2bc9a0ddc9686a490e5091d24d2f3`.
The unchanged six-input source kit reproduced nine identical outputs and passed
PCM, fault, cleanup and DLL-origin probes. Actual reference tools were CMake
`4.4.5` and compiler `19.51.36260.0`. Five same-head diagnostic/frontend,
protected-TEST and authored-helper metadata archives were also independently
checked within their existing limits. Main/reference image `20261030.294.1`
and the separately recorded auxiliary image versions are hosted Server evidence.

Two separate same-head experiments failed. ASR run `41225667278` observed empty
default common-data folders, an unobserved after-call constant and owned MSB4184
in both states; DoNotVerify return/properties and the native cause remain unknown.
No configure, compilation, inference or final source/tool seals passed. C7 v1 run
`41225668722` refused its `legacy-baseline` protocol with `observed=[]` and
unconfirmed retained-fixture cleanup. That empty list proves no recorded bounded
legacy-open/attribute observation; it does not prove physical operations never
occurred. Neither result closes R18 lock behavior, keeper loss, rights or native
Windows 11 gates. Exact artifact identities and earlier checkpoints remain in
the [checkpoint ledger](r19-frozen-checkpoint-20261031.json); R19 stays incomplete.

## Negative explicit-close checkpoint at 31ee4c9

[Run 41230110931](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41230110931)
at `31ee4c9d14594b34ef8bfbfbe583543f6261c296` includes the deterministic
TranscriptStore close change and its explicit hosted contract selection.
It passed 1,191 contracts without skips (one warning, 131.00 seconds), freezing
and the native/C1/cold-slot probes. The keeper step then reported
`registered-start` / `registered-listener-changed`, with
`cleanup=unconfirmed-recovery-required`, and hit its external five-minute
deadline. That deadline records a failed attempt with unconfirmed cleanup;
it does not establish that every owned process or lease closed. The native cause
remains unknown; this is not a
demonstrated storage regression or permission to weaken listener identity.

Only `keeper-before-resume` completed: two writers created, none resumed,
retained signals and two source-entry blocks. There is no completed second-case
result. Missing metadata does not prove that no intermediate physical activity
occurred. All four downstream C3/C4/C5/C6 steps were skipped and their receipts
are absent. **`a1c5e92` remains the last complete frozen checkpoint.**

Root and peer verified partial archive `13053797653`, 1,333,529 bytes, SHA-256
`2081ae84727f87b44778c79fdd6ff2d85d103759a22ee808ef354ccd3a9dd5dd`.
Its nine exact entries retain pre-failure observations, the failed keeper receipt,
source kit and inventory/A2/P1 metadata. Failure-only archive `13053678109`,
1,052 bytes, SHA-256
`2411187b394117ea47691e43f1a26e3dfb3805a5a88df057a4dcb08acedea6ce`,
contains the identical 2,038-byte keeper JSON, SHA-256
`dfd759fd78cff5e46f920c6bad8e30b562749265d070c8be586e1325a16159a9`.
The six other source/metadata archives were separately verified, for eight in
total. Their success does not promote the failed runtime run.

The partial inventory binds 1,449 files, 642 directories and 620,139,242 bytes;
all 473 A2/P1 records and 113 notice references (104 distinct hashes) matched.
Reference artifact `13052663910`, 1,095,192 bytes, SHA-256
`cb362a43a315ffb51467adade3c8a461383cb027bf4b8286602a9ae256b9e502`,
again reproduced nine identical outputs from the six-input Xiph kit and passed
decode/fault/origin checks. Its actual CMake was `4.4.4`, compiler
`19.51.36260.0`, on image `20261021.278.1`; the main image was
`20261030.294.1`. This reference-recipe observation changes no isolated
FFmpeg/ASR CMake4.4.5 pin. Exact Git31 source pins were checked without using
mutable local runtime files or claiming a locally recomputed global fingerprint.
Generated compiled internals remain unverified without binary inspection.

The independent source repro also shows that a not-ready listener snapshot can
change to ordinary startup listeners before any HTTP attempt and trigger the
same refusal. That identifies a bounded readiness-review boundary, not this
run's native cause. Complete ready-listener/process ownership checks remain
required. Rights, Windows 11, keeper loss, global writers, warm routing and
R19 completion remain open; no installer was built.

## Separate e8416e9 negatives and source-only follow-ups

[ASR run 41229142323](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41229142323)
at `e8416e9ed20bf0595d7559fa8430609ca0a74803` still failed before configure.
Its independently verified single-entry artifact `13052702817`, 2,058 bytes,
SHA-256 `2db0bb18a79576042bfc89a48952d2a3f009311af77386345621901880deb2f2`,
reports the fixed `absolute-path-required` resource in both rejected states,
empty default folders and no after-call constant or DoNotVerify properties.
The resource does not identify a private path/variable or prove a repair.

[C7 v2 run 41229013616](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41229013616)
on the same head passed 89 contracts without skips, then failed its baseline
protocol. Artifact `13052329447`, 750 bytes, SHA-256
`bbb2f106c32f1fc107e3dbacc9ab775338d94e2ba418294506bda759529bb894`,
delivered `connected` / `receive-script-progress` / `not-signaled` only.
The child signal is pre-close context; cleanup is unconfirmed and native cause
unknown. No bounded legacy-open or READONLY observation was delivered.

The [operation fence](r19-mutable-store-lifetime.md) at `1d933dd` builds on
explicit connection close but proves only a programmatic per-store scope drain.
It does not prove physical handle release, detach/reopen, global admission or a
usable warm OCR session. The [OS-derived SystemDrive source change](r19-asr-source-experiment.md#common-data-preflight-and-pending-os-derived-systemdrive-binding)
at `3b3a282` is separately native pending. Neither change upgrades these
historical negative receipts or any rights/Windows/R19 gate.

## Continuation and rollback

Use the integrated workflow for the extracted runtime/native/ASR observations,
keeping the production runtime profile disabled until required helper/host and
exact-output rights/native evidence exist. The static CSR frontend removes
end-user Node/Wrangler in the observed experiment; real browser-profile/update
continuity and the native acceptance gates remain open. Prebuild NTE/Endfield
helpers only with complete runtime/NuGet/source evidence; keep PRAGMATA/Oodle/GPL
and metadata rights gates explicit. Execute every toolchain's R18 functional
protocol against the same accepted extracted artifact, then the native and R02b
measurements above. Implement and prove the supervising global writer barrier,
continuous legacy exclusion, owner-aware updates and launch-pointer recovery
before any live migration activation.

The branch is reversible independently of R18. No live user data, credentials,
source installation, R18 branch or dependency PR is changed by these probes.
