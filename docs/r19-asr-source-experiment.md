# Separate TTS-disabled ASR source experiment

This manual experiment is an unapproved alternative identity,
`sherpa-onnx-1.13.8-asr-reference.1`. It does not replace the stock sherpa
artifacts, application requirements, frozen runtime profiles or Migaku. No
installer, pretrained ASR-model download or production permission is added.

The existing Python binding contains an implemented eSpeak export; removing
unused C API DLLs cannot remove that binding's code. The upstream
[top-level build](https://github.com/k2-fsa/sherpa-onnx/blob/11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf/CMakeLists.txt)
and [Python binding registration](https://github.com/k2-fsa/sherpa-onnx/blob/11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf/sherpa-onnx/python/csrc/sherpa-onnx.cc)
provide a TTS-OFF path. The recorded patch supplies its two missing `None`
placeholders, `GenerationConfig` and `OfflineTtsSupertonicModelConfig`, which
the unchanged Python initializer imports. Both upstream base and result are
hashed; the original Apache notice and patch remain with the private candidate.
[The public patch notice](../packaging/asr/SHERPA-PATCH-NOTICE.txt) retains Xiaomi's
copyright, the exact upstream source URL and a dated description of the two
additions. The complete original [Apache license](../packaging/asr/SHERPA-LICENSE.txt)
is retained byte for byte. Both are pinned in the manifest and copied into the
private source recipes and wheel notices. This preserves authoritative notices;
it does not grant new rights or alter the project's license.

## Exact inputs and dependency graph

[The experiment manifest](../packaging/asr/sherpa-reference.json) fixes upstream
commit `11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf`, all archive byte counts and
SHA-256 values, selected extraction scope, individual notice bytes, build flags
and the patch. The eleven source archives are sherpa-onnx, pybind11,
kaldi-native-fbank, kaldi-decoder, kaldifst, OpenFST, KISS FFT, Eigen, JSON,
simple-sentencepiece and hclust-cpp. Notices are retained individually; preserving
a license file does not classify every optional source as linked or approve
the combined output. The Eigen/JSON source archives also retain optional
material with other notices; output-specific review remains necessary.
The original simple-sentencepiece archive contains unused upstream tokenizer
test `.model` files. Its selected build prefixes omit those Python/test assets;
they are never loaded, placed in the candidate or presented as owned fixtures.
The retained original archive is private. The no-pretrained-weights boundary
concerns ASR weights; it does not pretend that every upstream source archive
contains only text or is free of upstream test fixtures.

ONNX Runtime 1.28.2 MT Release is a **separate prebuilt native dependency** from
the [supplier release](https://github.com/csukuangfj/onnxruntime-libs/releases/tag/v1.28.2),
with the exact hash selected by the
[upstream Windows recipe](https://github.com/k2-fsa/sherpa-onnx/blob/11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf/cmake/onnxruntime-win-x64.cmake).
Its DLL, headers, import library, LICENSE and ThirdPartyNotices are bound to the
archive. Rebuilding sherpa does not rebuild this DLL or establish its complete
source/compiler/CRT correspondence. That review stays pending.

The existing CPython 3.12.16 supplier archive supplies the separate build/probe
interpreter, headers and Python import library. Its existing supplier and notice
review limits apply. Every actual interpreter-root file must match the exact
supplier archive before sealing/building. The exact Windows NumPy 1.26.4 wheel is extracted into a
separate probe-dependency directory; no ambient installed sherpa or NumPy can
satisfy the native probe. NumPy is not silently bundled into the variant wheel.

Preparation downloads nothing. It validates every original archive hash before
writing, rejects selected traversal/links/Windows path aliases/nonregular or
oversized entries, checks each notice and applies only the fixed patch. Unused
platform links in the main archive cannot enter its explicit selected source
prefixes. Original archives and full inventories stay in private build output.
Subsequent source checks recheck source, original archives, notices and copied
recipes. The raw archive pin retains the omitted platform material's identity.

Every selected `FETCHCONTENT_SOURCE_DIR_*` is explicit, including the upstream
hyphenated `simple-sentencepiece` name. CMake's disconnected mode is mandatory;
the expanded configure trace must show exactly the declared/populated dependency
set and no `file(DOWNLOAD)` or downloader invocation. Module precedence selects
the root's Eigen 5.0.1/OpenFST recipe over nested alternative recipes. No
PortAudio/WebSocket/test/demo/CAPI/TTS fetch may enter the experiment. The trace
check is a source-graph observation, not an operating-system network sandbox.

## Build and probe boundary

### Common-data preflight and pending same-child contrast

The later [14babb6 source attempt](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41210502791)
failed during configuration. Its checksum-verified sanitized failure metadata
contained eight identical argument contexts: the fixed illegal-path resource,
FileTracker initializer, and inner path-normalization, path-root,
file-tracker-common-data and file-tracker-initialization roles. Unknown frames
left each context incomplete. This identifies delivered format context; it does
not establish the live CommonApplicationData result or a missing-variable cause.

The next source implementation adds exactly two common-data states before
configuration. The first uses the existing filtered environment. The second
removes case aliases of `PROGRAMDATA` and `ALLUSERSPROFILE` and binds those two
keys to the current token's authoritative `FOLDERID_ProgramData` answer. It
does not inherit those values from the parent, restore other variables or infer
`SystemDrive`. There is no alternate combination or fallback folder.

The original typed [Known Folder call](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
uses [DONT_VERIFY](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/ne-shlobj_core-known_folder_flag),
without CREATE, and always frees a returned allocation. The private answer must
be a canonical existing local directory. Raw components are checked before a
root-first `lstat`/reparse walk reaches descendant metadata. No common-folder
enumeration, file content, length, digest or raw path is retained. The OS answer
is requeried and compared privately around both children and before final
publication; a changed or unavailable answer refuses the attempt. These checks
do not eliminate hostile concurrent filesystem replacement between checks.

One fixed private project uses only documented
[MSBuild property functions](https://learn.microsoft.com/en-us/visualstudio/msbuild/property-functions)
and the built-in Message task. It calls ordinary default-option
[GetFolderPath](https://learn.microsoft.com/en-us/dotnet/api/system.environment.getfolderpath?view=netframework-4.8.1),
emits its default observation, then calls the same method with the qualified
`SpecialFolderOption.DoNotVerify` argument. One additional fixed record contains
only four booleans: empty, rooted, PROGRAMDATA equality and ALLUSERSPROFILE
equality. The existing default GetPathRoot/IsPathRooted step follows in the same
child. The unverified result is never used for path metadata, content access,
default substitution or configuration authority. There is no SDK import, inline
task, reflection, compiled helper or additional CLR. Both states run only the
initially sealed `Current/Bin/amd64/MSBuild.exe`; its exact bytes are checked
before and after each child, with no PATH or alternate executable fallback.
Full runtime type and a true Is64BitProcess observation are required. Existing
profile/import exclusions, no auto-response, no node reuse and final full tool
seals remain in force.

The existing retained Job Object bootstrap owns each child before it launches
MSBuild. A local pipe reader checks available bytes before reading: at most
32 KiB of accepted merged output (one overflow lookahead byte) and 30 seconds
per invocation, followed by bounded owned
cleanup. It uses no unbounded read, reader thread or raw preflight log. Exactly
four fixed ASCII marker formats supply ordered default/constant-return-stage/DoNotVerify/root observations;
malformed, duplicate, missing, non-UTF8, oversized or timed-out output supplies
only a fixed refusal category. Other command text is discarded. The public
projection rechecks every key, enum and boolean and carries no exception,
command, folder value or private marker field. The four `do_not_verify` fields
are all typed booleans when that complete record is delivered, or all null when
it is unavailable. A nonzero exit may retain a complete default-only,
default-plus-return-stage or default-plus-stage-and-contrast observation before the root step; malformed partial lines
are refused, and mixed null/boolean contrast fields cannot pass projection.

An ordinary baseline rejection still permits the one bound state. Unconfirmed
termination, reaping or close instead aborts before another child can start.
Bootstrap kill/reap, owned-job termination, owner close and pipe close are each
attempted even when an earlier cleanup step fails. A later successful step
cannot clear that uncertainty.
Configuration requires the bound child to report Full CLR/x64, nonempty folder
and root, rootedness, and equality with both aliases. It then receives that same
bound map. The new same-child DoNotVerify contrast remains **native pending**;
local authored fixtures do not establish Windows behavior. Comparable fresh
MSBuild children are not the later CL task's live process. Even repaired
configuration would not prove framework binary/source correspondence, native
closure, redistribution rights, trained recognition, Windows11 or R19 completion.
The same 15 source inputs require a new exact prepare/verify after review.

At `2a169bd`, run `41215443407` stopped in `common-data-bound`: both states
reported `invalid-markers` and the OS origin remained stable. No child exit,
MSBuild error code or actual folder/CLR value was delivered. That failure does
not establish a missing-variable cause. A subsequent source review found that
the primary [MSBuild enum coercion](https://github.com/dotnet/msbuild/blob/86743d0545fba3d043d4e7aaa12891edb3fd56e6/src/Build/Evaluation/Expander.Function.cs#L1024-L1041)
requires a qualified enum string in this late-binding route. The fixed template
now supplies `SpecialFolder.CommonApplicationData` and, twice,
`StringComparison.OrdinalIgnoreCase`. No marker, environment, tool pin, flag or
permission changes accompanied those three tokens. Exact runner binary/source
correspondence remains unproven; the later marker outcome is recorded separately.

At `5c9db76`, [run41217577067](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41217577067)
reached the fixed markers in both Full CLR/x64 children, then stopped in
`common-data-bound`. Both default folder results were empty. Baseline alias
comparisons were true, while both bound comparisons were false; those baseline
equalities compare empty results and do not identify a usable path. The OS
origin stayed verified. Its actual job used VS18.11.12315.225 and image
20261021.278.1. This is a negative two-alias intervention, not evidence for
adding SystemDrive. Configuration, complete final source/tool seals and native
format probes were not reached. It does not contain the new contrast below.

The primary [Framework implementation](https://github.com/microsoft/referencesource/blob/ec9fa9ae770d522a5b5f0607898044b7478574a3/mscorlib/system/environment.cs#L1505-L1537)
uses the legacy MAX_PATH/SHGetFolderPath interface and maps almost all negative
HRESULTs to an empty string. [Shell documentation](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetfolderpathw)
also permits empty output on failure. Thus the observed empty default result
does not identify a particular error, missing variable or nonexistent folder.
[DoNotVerify](https://learn.microsoft.com/en-us/dotnet/api/system.environment.specialfolderoption?view=netframework-4.8.1)
skips existence verification without CREATE. The new contrast keeps the same
two environments, child owner, executable seals and byte/time limits. It adds
no prefix field, environment variable, expansion call, fallback or new process.
An unverified nonempty result would be a verification-sensitive observation,
not a repair or permission to configure; all existing default requirements
remain necessary. No unverified string, length, digest or unknown field is
published. A fresh reviewed15-input prepare and Windows attempt are still
required to establish that additional observation.

At `fbcb943`, [run41219931905](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41219931905)
failed in `common-data-bound` on its first attempt. Root and peer verified the
sole 1,996-byte artifact and 5,071-byte failure JSON, initial CMake variant and
Windows-CRLF manifest. Both Full CLR/x64 default results were empty; all four
DoNotVerify fields were null in both states, with `process-rejected` and no
root result. Thus no complete contrast marker was delivered. Do not interpret
null as an empty/unrooted contrast result or infer whether GetFolderPath or a
later marker expression failed. The actual image was `20261030.294.1`, VS
`18.11.12328.437`. Configuration, native probes and final tool/source seals
remain unavailable; every acceptance gate stays closed. Exact provider identities
are in the [checkpoint ledger](r19-frozen-checkpoint-20261031.json).

The next source diagnostic inserts one constant Message immediately after the
DoNotVerify call and before its four-expression Message. That constant contains
no property expansion. `do_not_verify_call` is strictly `not-run`,
`not-observed` or `returned`; an absent constant never asserts that the call
threw. The returned observation requires the exact unique constant directly
after a valid default marker. A malformed later contrast stays rejected even
when that earlier constant was observed. Full successful marker parsing still
requires every record in order, and default-folder acceptance remains unchanged.

Only three [MSBuild resource codes](https://github.com/dotnet/msbuild/blob/86743d0545fba3d043d4e7aaa12891edb3fd56e6/src/Build/Resources/Strings.resx#L618-L663)
can enter `msbuild_codes`: MSB4184 for expression evaluation, MSB4185 for an
unavailable property function and MSB4186 for static invocation. Extraction
uses the existing capped in-memory output, without a log or new reader. The
[diagnostic header](https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild-diagnostic-format-for-tasks)
must begin with the fixed MSBUILD origin or the exact actual authored project
path plus positive bounded line/column fields, followed by the error category
and an exact allowlisted code. Basename/foreign-path matches, arbitrary message
or expression mentions, warnings, unknown codes and malformed positions do not
supply a code. The project path and positions remain private.

The list is deduplicated, sorted and capped at the three known codes. Public
projection independently rejects unknown values, non-list/incorrect types,
duplicates and noncanonical order; stage and code observations survive only as
finite diagnostic fields on a rejected partial/invalid-marker result. They
cannot authorize configuration. An empty list means no allowlisted code was
observed, not that no error occurred.

At `a1c5e92`, [run41225667278](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41225667278)
failed in `common-data-bound` on attempt1. Root and peer verified the sole
2,034-byte artifact and 5,287-byte JSON, manifest and initial variant. Both
Full CLR/x64 default results remained empty; the after-call constant was
`not-observed`, DNV's four fields were null and MSB4184 was observed in both
states. Actual image20261021.278.1 and VS18.11.12315.225 were independently
checked. This identifies a formatted expression-evaluation boundary; it supplies
no exact inner resource or missing-variable cause. Configuration, native probes,
PREPARED and complete final tool/source seals were not delivered. It is not a
native build pass, and every acceptance gate remains closed.

The next source implementation adds only `dnv_error_resource`, with the finite
values `not-run`, `not-observed` and `absolute-path-required`. The last value
requires a nonzero Full CLR/x64 default-only result, no returned-stage marker,
and an error header from the exact authored project/location. Its complete
MSB4184 body must equal the fixed two-argument DNV GetFolderPath expression
and the exact English
[Argument_AbsolutePathRequired resource](https://github.com/microsoft/referencesource/blob/ec9fa9ae770d522a5b5f0607898044b7478574a3/mscorlib/mscorlib.txt#L720).
The expected method text follows the reference
[MSBuild renderer](https://github.com/dotnet/msbuild/blob/86743d0545fba3d043d4e7aaa12891edb3fd56e6/src/Build/Evaluation/Expander.Function.cs#L1068-L1117)
and its [inner-message formatting](https://github.com/dotnet/msbuild/blob/86743d0545fba3d043d4e7aaa12891edb3fd56e6/src/Build/Evaluation/Expander.Function.cs#L591-L602).
This reuses an existing resource identity; no source catalog is expanded.

Only identical complete headers, including project location and position form,
can deduplicate; equal bodies at different owned locations stay unobserved.
A conflicting owned error, global
or foreign header, other expression/argument, embedded resource mention,
unknown/localized message or extra suffix cannot establish the resource match.
Unknown numeric codes can only invalidate this one predicate and never enter
the public code allowlist. Public projection independently checks the enum and
its coherent rejected context. No raw body, path, message, length, digest or
unknown value is published. The existing32KiB capture, two environments,
process ownership and all default configuration requirements stay unchanged.
Even a matched resource would be a format observation, not the private path,
failing variable, exact binary/source correspondence or an approved repair.
The new predicate is native pending; it adds no call, marker, environment,
flag, source input or SystemDrive binding.

### Manual source build

Use the manual **R19 separate ASR-only source experiment** workflow on a clean
candidate commit. It observes the actual PR target's development prerequisites,
audits public source, downloads only pinned public inputs, and invokes
[the Windows wrapper](../scripts/build-reference-asr.ps1). There is no push trigger.
Before this new workflow is registered, dispatch the existing R19 entry workflow
with `source_replay=sherpa-asr` on the reviewed branch. It calls the reusable ASR
workflow at that same commit and skips the frozen/FLAC/observer jobs:

```sh
gh workflow run r19-runtime-experiment.yml --ref codex/r19-runtime-bundle -f source_replay=sherpa-asr
```

Select the review repository explicitly for a checkout with multiple remotes.
No default branch or repository setting is changed. The registered dedicated
workflow remains directly dispatchable; no successful source-only run can stand
in for a skipped frozen-runtime job.

The constraints select hosted VS18 2026, MSVC 19.51.36260.0/toolset
14.51.36231, isolated CMake 4.4.5 and Windows SDK 10.0.26100.0. Version strings are not
immutable supplier identities. Exact VC/MSBuild/selected SDK/CMake/Python file
inventories are hashed before configuration and compared after the build/probes;
only counts and digests leave the host. OS services and the supplier/toolchain
rights decision remain external to this byte-stability check. It does not
assert approval of a mutable hosted image.
The workflow uses the shared [pinned CMake helper](../scripts/pinned-build-cmake.py)
and [official ZIP policy](../packaging/build-tools/cmake-4.4.5-windows-x64.json).
After doctor/audit it acquires the exact original ZIP and publisher checksum list,
prepares a fresh private build-host container, and verifies the complete tool
tree. The wrapper requires that container explicitly through `CMakeRoot` and
passes its verified official payload to Python. Before any CMake execution and after the
build/probes, Python uses the same shared verifier against the original retained
ZIP, complete file/directory inventory and notices. The observed version must
still equal 4.4.5, and the payload remains in the complete before/after tool seals.
Each declared tool root must resolve to one existing filesystem directory and
enter Python as a single string; arrays, missing roots and additional root
labels are rejected before sealing. The source manifest and `SOURCE_FILES` bind
the shared policy/helper. Source recipes retain those files; the CMake ZIP,
tool executables and complete tool tree remain runner-local and never enter
the ASR source recipes, private variant wheel, runtime or uploaded artifacts.
The successful ASR receipt retains the verified tool's safe summary only; this
grants no runtime collection or additional supplier/source approval.

The ASR experiment separately identifies build-tool module variant
`cmake-4.4.5-r19-asr-compilerid-instance.1`. The official input/container remains
unchanged; the shared helper, policy and FFmpeg route continue using the original.
On the Windows build host only, the ASR driver derives a fresh private tree from
the same original ZIP. All 8,817 files and 163 directories are required, with
exactly one changed file: `share/cmake-4.4/Modules/CMakeDetermineCompilerId.cmake`.
The source-bound [patch](../packaging/asr/cmake-compilerid-instance-location.patch)
changes only its two auxiliary property-path constructions. It derives a local
directory by removing the trailing four-component version field, then requires
the complete instance to equal that directory plus
`version=${CMAKE_VS_VERSION_BUILD_NUMBER}`. A mismatch fails closed. The global
portable instance, cache identity, generator, toolset and SDK flags are retained.
CMake's pinned [language initialization](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalGenerator.cxx)
sets the generator instance before loading language compiler modules. The
[versioned generator](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalVisualStudioVersionedGenerator.cxx)
sets `CMAKE_VS_VERSION_BUILD_NUMBER` from that chosen instance at that boundary.
This preserves portable-instance handling on both reviewed host images and
adds no installer/root/version fallback. Actual execution of the variant on
either image still requires its own native result.

The original Windows module's CRLF bytes are pinned at 62,848 bytes / SHA-256
`dfcd059e686a773e58004608e655278bd5f4d1993b3540b9392549c9499f544a`;
the derived module is 63,391 bytes /
`4ef0b318b3f80a02091ae44973dfe573f042fdd3bf6a3c25c5bddfbd2c63f0bc`.
The exact patch, complete original [license](../packaging/asr/CMAKE-LICENSE.rst)
and [modification notice](../packaging/asr/CMAKE-MODULE-PATCH-NOTICE.txt) are
retained among the 15 source inputs. Source/notice bytes, original module,
single patch hunk and resulting module must all match before materialization.
The variant verifier derives its entire expected file/directory inventory from
the original pinned ZIP and sole patch; a receipt cannot authorize extra files
or exemptions. Source files, original archive, fresh destination and every
member pass root-first no-link/reparse checks before access. The official
container remains separately closed and verified. Both original and executed
variant trees enter the complete before/after tool seals and are independently
reverified before any passing receipt. The executable and every original notice
remain byte-identical. The expected variant tree SHA-256 is
`3084625cac5d54bd47f7983ef56b06305c40718d1a0024d10f8de82632b3c022`.
Sanitized variant identity, patch/module/notice pins and bounded tree summary
are recorded separately; arbitrary summary fields and private paths are refused.
No native tool ZIP, executable or derived tree enters recipes, the private ASR
wheel, runtime or uploaded artifacts. This is a build-host source adaptation,
not an upstream CMake release or supplier/source/redistribution approval.
Failed toolchain validation distinguishes fixed root-schema/filesystem,
interpreter-origin, supplier-byte and CMake-version subphases. A failed receipt
may include only bounded numeric expected/observed CMake versions and the
executable's byte count/SHA-256; raw version lines, paths, arguments and exception
text remain private. An observed mismatch does not relax the 4.4.5 constraint.
Failed command diagnostics inspect at most the final 2 MiB of the phase's private log.
The fixed CMake error IDs are derived from the pinned 4.4.5
[command parser](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmake.cxx),
the generator sources linked below, and its
[policy implementation](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmPolicies.cxx).
They distinguish unavailable or malformed VS instances and installer lookup,
toolset/flag-table/platform/SDK selection, missing build tools or compilers,
CLI/source/cache/project input errors, and minimum-version/compatibility/policy
failures. Matching tolerates diagnostic line wrapping and excludes warning
blocks. It returns fixed IDs rather than matched text or variable values.
An optional `cmake_error_sites` field contains at most 32 unique pairs of an
allowlisted CMake command and a positive line number of at most seven digits.
Paths, unknown command names, arguments, source text, environment values and raw
logs cannot enter this projection. An unclassified error remains a failed
attempt; neither a diagnostic label nor a known call site proves its cause.
For configure failures, additional compiler labels come from CMake's pinned
[language initialization](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalGenerator.cxx),
[compiler identification](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Modules/CMakeDetermineCompilerId.cmake)
and [MSVC setup](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Modules/Platform/Windows-MSVC.cmake).
`compiler_detection_context` reads only `CMakeCache.txt` and the three fixed
4.4.5 `CMake{C,CXX,RC}Compiler.cmake` files, with a 256 KiB limit per file.
It reports fixed missing/empty/literal-`NOTFOUND`/origin states, allowlisted
compiler IDs and bounded numeric versions. Duplicate assignments are refused;
these files are never evaluated. Compiler paths outside the declared VC toolset
or SDK-bin roots are neither read, statted nor hashed. All path values remain
private; a recorded compiler state is no native-input approval.
`nested_configure_log_context` reads only the fixed
`build/CMakeFiles/CMakeConfigureLog.yaml` and `CMakeError.log`: at most the final
2 MiB each and 4 MiB total. The diagnostic guard checks each component with
`lstat` from root to leaf, refusing symlinks/reparse points before any descendant
metadata or file read. Inputs must be regular files. No YAML parser or arbitrary
log discovery is used.
Only existing known compiler/MSBuild codes and fixed context labels leave these
logs; unknown codes, lines, paths and hashes of paths remain private. Expected
failed compiler probes can appear in nested logs, so their observations are
explicitly labelled context and do not identify the fatal configure cause.
Microsoft defines [MSB4019](https://learn.microsoft.com/en-us/visualstudio/msbuild/errors/msb4019)
as an unresolved project import. Its nested-log projection shares at most 16
records with the MSB4018 task projection across both logs. Only the three direct imports in CMake's pinned
[CompilerId project](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Modules/CompilerId/VS-10.vcxproj.in)
receive fixed file labels: `Microsoft.Cpp.Default.props`, `Microsoft.Cpp.props`
and `Microsoft.Cpp.targets`. The only numeric filename additionally recognized
is `Microsoft.VCToolsVersion.<version>.props`, with `<version>` exactly equal
to the reviewed manifest's VC toolset version; other numeric names stay unknown.
Its public version field contains that reviewed pin, never an extracted version.
`literal_match_state` distinguishes a recognized MSB4019 import sentence with an
unknown file from an unrecognized message template. Unknown text stays private.
The separately labelled `mapped-toolset-version-template` recognizes only the
pinned auxiliary-import layout rooted in the actual verified full generator
argument or its canonical selected directory. Its repeated numeric alias must have two to four bounded components
and satisfy CMake's reviewed two-component prefix search. The alias itself is
never emitted: the public version remains the reviewed three-component pin.
This structural label and its instance-version-field boolean permit no access
to the raw outside-root target and establish no source or rights approval.
The historical full-argument form retains a true version-field boolean and no
raw-target inspection. The canonical form has a false boolean only when that
same verified private root/version/argument tuple agrees. Its existence state
requires the exact corresponding props/metadata pair in the initial seal;
a sealed alias in another directory layout cannot authorize that target.
The projection exposes only a fixed declared-root role and existence state;
unknown or outside-root paths are never inspected. The selected-targets role
also requires membership in the declared MSBuild root. No import path or hash
of a path is retained. Caller context recognizes only these three file labels
and `CompilerIdC.vcxproj`/`CompilerIdCXX.vcxproj`, with positive line/column
numbers of at most seven digits. Other callers remain unknown; their paths,
names and positions are omitted. No caller file is inspected.
CMake's [compiler identification](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Modules/CMakeDetermineCompilerId.cmake)
copies `CMAKE_VS_GLOBALS` into that project's Globals before its first import.
`compiler_id_globals_context` inspects only the two fixed 4.4.5
`CompilerId{C,CXX}/CompilerId{C,CXX}.vcxproj` paths, at most 256 KiB each and
4,096 XML elements per project. It accepts the generated MSBuild XML namespace
and refuses DTDs, entity declarations/references, conditional/ambiguous Globals,
and linked paths; it never executes XML or accesses external files. Only the
fixed five property names and exact-match/missing/duplicate/unsupported states
are emitted. Expected values come from the actual private configure properties;
their values, raw XML and unknown property names remain private. The same two
already-bounded XML reads project at most 16 actual Import entries total, with
explicit truncation flags. Only the author-known `$(VCTargetsPath)` prefix on
those three exact CPP filenames can use the actual private configure property,
and only when the XML's literal `VCTargetsPath` matches that property exactly;
other expressions receive a fixed unexpanded state. All resulting paths still
require declared-root containment before metadata access. Import conditions
are observed only as presence booleans and are never evaluated.
For the reviewed numeric template, `contains_verified_instance_version_field`
is a boolean only when the stored actual generator argument, selected root and
observed four-part VS version agree. It identifies the two pinned CMake
`VC/Auxiliary/Build[/.]<version>/...props` constructions using that full instance
argument. An unavailable/mismatched private tuple yields an unavailable value.
No tuple, raw expression, arbitrary numeric filename or outside-root metadata
is published or inspected. These are literal observations, not MSBuild
property evaluation or causal proof.
For that mapped template, `toolset_mapping` can additionally compare corrected
metadata members under the already declared and sealed VC/Auxiliary root. The
root must belong to the same verified selected VS directory. Only matching
`Build[/.]<alias>/Microsoft.VCToolsVersion.<same-alias>.txt` plus `.props` pairs
present in the actual initial in-memory tool inventory are considered. No
directory discovery, invented inventory or outside-root fallback is allowed.
The guard bounds the index at 50,000 entries, candidates at 32, each member at
64 KiB, and member reads for each mapping record at 512 KiB including
growth-check lookahead bytes. The existing shared limit of 16 message/task records and
16 generated-project imports bound these reads to 16 MiB per failure receipt.
Each current regular file passes root-first link checks and must match its
initial bytes/SHA-256. The metadata's first line must exactly equal the reviewed
toolset pin, allowing its line-ending CR. Public output contains only a fixed
relationship, matched-candidate count, matches-policy boolean and member-existence
state. Changed, unavailable, incomplete, over-limit and ambiguous inputs stay
explicit. No alias, relative member path, content or native-member hash is
published. These observations do not replace the complete tool seal or approve
Microsoft source delivery, redistribution or native execution.
Microsoft defines [MSB4018](https://learn.microsoft.com/en-us/visualstudio/msbuild/errors/msb4018)
as an unexpected task exception. `msb4018_tasks` separates a matched task sentence
from an unrecognized literal and returns only fixed task/exception/code labels.
Task names come from Microsoft's [C++ task reference](https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild-tasks-specific-to-visual-cpp)
and [MSBuild task reference](https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild-task-reference).
Exception families are explicit .NET API names, including documented
[common exceptions](https://learn.microsoft.com/en-us/dotnet/standard/exceptions/),
[IO exceptions](https://learn.microsoft.com/en-us/dotnet/api/system.io.ioexception),
[Win32Exception](https://learn.microsoft.com/en-us/dotnet/api/system.componentmodel.win32exception),
[TypeInitializationException](https://learn.microsoft.com/en-us/dotnet/api/system.typeinitializationexception),
[BadImageFormatException](https://learn.microsoft.com/en-us/dotnet/api/system.badimageformatexception)
and [COMException](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.comexception).
Only exception-header HRESULTs or the fixed `Exception from HRESULT:` template,
and explicit `NativeErrorCode:`/`Win32 error:` numeric fields, can produce
[reviewed HRESULT](https://learn.microsoft.com/en-us/windows/win32/seccrypto/common-hresult-values)
or [Win32-code](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-)
enums. Unknown task, exception and code tokens become fixed unknown labels;
empty code/family arrays mean no corresponding observation. A generic HRESULT
never supplies an inferred native Win32 error. Stack frames, messages, parameter
names and unknown tokens remain private. Each contiguous task block consumes at
most 32 KiB of UTF-8 byte span within the existing log tail, including connecting
LF/CRLF bytes; overflow is explicit. A new task block resets the counter without
charging preceding gaps. Header extraction scans each line without overlapping
whitespace/prefix backtracking. For a full tail,
task extraction conservatively discards the first potentially partial line.
No YAML/string unescaping, extra log discovery or larger read is added. These
observations do not establish the exception's cause or permit environment fixes.
The additive `exception_chain` retains at most eight ordered exception-family
enums, including the outer wrapper. It recognizes only the documented standard
TypeInitializationException sentence followed by the fixed ` ---> ` separator,
inline or on an immediately continuing error line. The
[.NET Framework formatter](https://github.com/microsoft/referencesource/blob/ec9fa9ae770d522a5b5f0607898044b7478574a3/mscorlib/system/exception.cs#L438-L451)
places an inner exception inline; an earlier start-of-line classifier omitted
that relation in an authored format fixture. Microsoft's
[MSBuild logging implementation](https://github.com/dotnet/msbuild/blob/86743d0545fba3d043d4e7aaa12891edb3fd56e6/src/Build/BackEnd/Components/Logging/LoggingServiceLogMethods.cs#L210-L240)
includes `exception.ToString()` in the task error without a verbosity guard.
These public sources explain format behavior; they do not establish source
correspondence for the runner's exact Microsoft task/runtime binaries.
Unknown families, unrecognized wrappers, malformed markers/headers, missing inner
observations and byte/depth truncation have fixed explicit states. The parser
stops at a non-wrapper leaf; arbitrary message or stack mentions cannot add
causal links. Existing flat families/code labels remain context and do not
assign codes to a particular chain layer. Type names, initializer names,
messages and parameter values stay private. This uses the same block/tail/record
bounds and linear header parsing, with no reflection, extra verbosity or new
native execution. An ordered formatted chain is not a live exception object or
proof of a complete underlying cause. The observed CL inner argument family
does not yet identify its message, parameter, initializer owner or throw site.
The additive `argument_context` collects those three context axes together only
for an admitted `System.ArgumentException` leaf of that standard wrapper chain.
It compares the complete leaf message against 13 fixed English resource groups
from the pinned [.NET Framework resource catalog](https://github.com/microsoft/referencesource/blob/ec9fa9ae770d522a5b5f0607898044b7478574a3/mscorlib/mscorlib.txt):
generic argument, illegal/invalid/empty/unsupported/URI/absolute paths, empty
strings, duplicate dictionary keys, environment-name syntax/length, environment
name-or-value length and invalid enum. The two formatted cases permit only
bounded opaque quoted keys (256 characters) or numeric fields (ten digits);
values, lengths and hashes are omitted. Custom/localized text, control characters
and altered resource whitespace remain unknown. A match is resource-format
context, not proof of binary source correspondence or a functional cause.
[ArgumentException.Message](https://github.com/microsoft/referencesource/blob/ec9fa9ae770d522a5b5f0607898044b7478574a3/mscorlib/system/argumentexception.cs#L70-L84)
puts a nonempty parameter on a following line. Only that immediately continuing
fixed prefix can supply exact public path/directory/environment/folder/key roles;
unknown, malformed, missing and duplicate parameter lines stay explicit. No
arbitrary parameter token is emitted.
The first inadmissible continuation, unrelated exception header, real blank
boundary or malformed frame closes this argument observation with an explicit
`incomplete` state. Unknown message continuation before the first stack frame
also revokes the resource match. Later frame-looking lines cannot resume the
closed context. Earlier admitted frames remain partial observations; a terminal
line ending alone is not a new blank message. Valid parameter/end-marker/wrapper
flow and syntactically valid unknown frames retain their explicit roles/states.
The known initializer role is limited to the public
[FileTracker class](https://github.com/dotnet/msbuild/blob/86743d0545fba3d043d4e7aaa12891edb3fd56e6/src/Utilities/TrackedDependencies/FileTracker.cs#L73-L148).
Unknown initializer names remain a boolean. At most 16 anchored stack-frame
lines per task, including unknown frames, can supply ordered fixed FileTracker,
Path, Environment, Directory/DirectoryInfo or Dictionary operation roles.
Inner argument frames are separated from later wrapper context by the fixed
.NET inner-stack end marker. Signatures/trailers are bounded at 1,024/2,048
characters and never emitted or inspected. Raw names, signatures, paths and line
numbers remain private. Unknown frames and frame overflow are explicit; stack
mentions inside message prose cannot create frames. This shares the existing
2 MiB tail, 32 KiB UTF-8/LF/CRLF task cap, 16 records and eight-layer chain limit,
without further reads or native/CLR probes. Parent-environment map context is
omitted. The exact runner CPPTasks/MSBuild/Framework source correspondence and
the actual argument context remain unverified until native evidence supplies them.
The wrapper passes the actual selected `vswhere` instance's numeric four-part
VS18 installation version together with its directory. Python queries the same
explicit machine `vswhere.exe` again before and after the experiment, requires
the same single path/version result, and requires the VC toolset, complete
MSBuild and VC/Auxiliary roots to belong to that directory. Query-executable
bytes are included in both tool seals; paths and full installer JSON remain
private. The configured `CMAKE_GENERATOR_INSTANCE` cache value must retain that
exact tuple. A failed receipt may expose only the bounded observed VS version;
the successful metadata also records the query executable's bytes/SHA-256.
CMake's documented
[explicit instance form](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Help/variable/CMAKE_GENERATOR_INSTANCE.rst)
allows `location,version=...` when installer discovery does not recognize the
directory. Its
[disk loader](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmVSSetupHelper.cxx)
assumes that supplied version and Windows SDK availability, while still requiring
the instance's default VC toolset metadata and directory. The independent
selection, file-origin, exact SDK/compiler/v180, cache and before/after byte
guards remain required. This removes installer registration as a CMake discovery
prerequisite; it grants no supplier or native-input approval and chooses no
other instance or compiler.
VC-target selection, parent-import review and configure-argument/source
validation have distinct fixed subphases. The hosted
[review run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41160408338)
observed all three installed families, `v160`, `v170` and `v180`, before configuration.
The manifest selects only `v180` and pins its actual `Microsoft.Cpp.Default.props`
at 25,028 bytes / SHA-256
`a2676be54dd09fc6b05903be07e28a3ae83c182de3d9ae91214db1ce029dd4ef`.
CMake 4.4.5's
[generator factory](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalVisualStudioVersionedGenerator.cxx)
binds the requested generator to VS18, its
[MSBuild invocation](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalVisualStudio10Generator.cxx)
uses `VisualStudioVersion=18.0`, and Microsoft's
[build-tool example](https://github.com/microsoft/cpp-language-server/blob/933ac0f10446009d972421329918b1d73bc2e0ff/AUTHORING_EXTRACTOR_SKILL.md)
documents the VS18 `v180` target family. The props pin's provenance identifies
the exact observed run, job, source commit and checksum-verified failure artifact.
Only one canonically spelled selected props file with those exact bytes is
accepted. Missing, changed or aliased selected inputs are refused; a later or
older installed family cannot become a fallback. Every installed family remains
in the complete MSBuild before/after seal and bounded diagnostics.
Before refusal, diagnostics collect every candidate's bounded numeric `v...`
label and props byte count/SHA-256, selected-family count/pin-match state, and
fixed parent-import categories. Unrecognized labels and raw paths/props contents
cannot enter the receipt. Registry fallback and parent imports remain refused.
The review run did not reach configuration. A subsequent
[native run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41161560168)
matched the selected `v180` props pin and reached `cmake-configure`, which failed
before compilation/inference. Its failure-only artifact contains the source
commit, manifest, selected props and CMake observations, but no separate
SOURCE_FILES-cohort or complete tool-seal receipt. The later
[diagnostic run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41163849991)
on the same `20261021.278.1` Server image identified
`cmake-vs-installer-instance-unknown` and `cmake-vs-instance-not-found` at
`project:26`. The existing directory was not recognized by CMake's installer
lookup, and no `version=` field was supplied. These templates do not establish
why installer lookup failed. The later
[explicit-tuple run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41167088124)
observed VS version `18.11.12315.225` and reached configuration, then failed with
only `cmake-error`/`cmake-configure-incomplete` and `project:26`. It provides no
specific cause, build-graph, compile or inference evidence. The subsequent
[bounded-context run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41169084584)
identified `cmake-compiler-not-recorded`; all three compiler cache entries and
configuration files were absent. Its observed configure-event log contains
`MSB4019` and a compiler-identification failure, but delivers no exact import
target and proves no fatal cause. The import/Globals projection above still
requires a new native result; all exact tool/source and refusal gates remain
in force.
The next [observed run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41171353894)
matched all ten C/CXX property observations and reported eight MSB4019 entries
at `CompilerIdC`/`CompilerIdCXX:37:3`, with every target still unknown. Static
substitution of the pinned template with the 15 authored Globals places its
optional toolset-version import on line 37. The
[module](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Modules/CMakeDetermineCompilerId.cmake)
constructs that import from `CMAKE_GENERATOR_INSTANCE`; the
[generator](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalVisualStudioVersionedGenerator.cxx)
preserves the explicit instance specification, including its version field.
This branch is conditional: CMake can clear an explicit toolset version when
it matches the default. Its
[configure-log emitter](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmConfigureLog.cxx)
keeps ASCII quotes literal and doubles backslashes in text blocks. These
source expectations do not identify that run's unknown target or prove its
fatal cause; the generated-import projection still requires native evidence.
The later [generated-import run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41174924122)
confirmed eight matched MSB4019 sentences, all ten Globals, and the three CPP
imports under the selected target root. The second import in each actual
project remained unknown; it did not match the exact three-component props
filename. CMake's [minor-toolset selection](https://github.com/Kitware/CMake/blob/aa4fae824a02a175c4a11653d7a851a948f0c004/Source/cmGlobalVisualStudioVersionedGenerator.cxx#L827-L855)
can translate that requested version to a metadata filename alias when the
metadata content matches. That primary source behavior motivates the mapping
observation above; it does not prove the unknown filename, malformed target or
fatal cause in that run. The new relationship still requires native evidence.
The subsequent [mapping run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41181127131)
on image `20261030.294.1` supplied that observation: both generated second
imports and all eight MSB4019 records matched the auxiliary template containing
the verified full instance-version field. Exactly one corrected canonical
metadata/props pair matched its initial tool seal and toolset pin. The other
three imports per project and all ten Globals matched. Configuration failed
before the build graph, native binding or inference. This identifies the
malformed generated import and motivates the separately pinned module variant;
it is not a native success result for the correction.
The first [module-variant run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41196924582)
at `1c2d931c9f6a7be804e5b222b34bc50291c723cf` used Server image
`20261021.278.1` and observed VS `18.11.12315.225`. Its failure artifact
`13040999035` is 2,450 bytes, SHA-256
`855f3168be12f679e045e89ba32aa074489b9c0a865d012cd63de07cacd5f0b1`.
It records the initial variant's 8,817-file/163-directory tree
`3084625cac5d54bd47f7983ef56b06305c40718d1a0024d10f8de82632b3c022`,
all ten matching Globals and the three selected CPP imports per project.
Configuration failed with nested `MSB4018` and no `MSB4019` import records.
The prior classifier left both second imports unknown; it supplied no actual
canonical-layout or task/exception identity. No build graph, binding,
inference, final variant recheck or complete before/after tool-seal receipt was
reached. The initial variant summary cannot substitute for those missing checks.
No environment, ProgramData, SDK or root cause is inferred from `MSB4018` alone.

The isolated [task-context run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41200812627)
at `ce09ea2cf844f40c4109beb8d877628585a83ed8` used image `20261030.294.1`
and VS `18.11.12328.437`. Its sole failure artifact `13042148305` is 2,681
bytes, SHA-256
`e922329b1af1685f209757cd6f5b9f37f83f6243e7b02f3a02df0f07a402f1e6`;
the contained `ASR-FAILURE.json` is 13,967 bytes, SHA-256
`3f106a4508be52fda8b3caf9e1f9a559bb98aac637d57f9acf087590c13cbde8`.
Two reviewers independently checked provider digest, exact source head,
Windows-CRLF manifest correspondence, initial module variant and closed gates.
Both actual second imports now match the canonical declared auxiliary layout,
contain no instance-version field and refer to regular files. Each matches
exactly one initially sealed metadata/props alias pair and the `14.51.36231`
toolset policy. All ten Globals and the other three imports per project match.
The nested configure log reports eight untruncated `MSB4018` task contexts:
each identifies `CL` and `System.TypeInitializationException`, with no matched
HRESULT or Win32 labels. There are no `MSB4019` import records. Configuration
failed after 9.37 seconds, before graph, compilation or inference; final
variant/tool-seal checks and a delivered source-cohort receipt were not reached.
This establishes a task type-initialization failure, not its underlying cause.
No environment or compiler-policy change is justified by that exception alone.

The subsequent [inner-chain run](https://github.com/matthias-van-der-galien/Game-immersion-toolkit/actions/runs/41204339894)
at `ed153abbbf29ab9c7cb5a71c8be58158513cf519` used image `20261021.278.1`
and VS `18.11.12315.225`. Artifact `13044461089` is 2,760 bytes, SHA-256
`bb9547d84a21f8c1aaa9f2be32f7633081d9ea2fd50d3026c5ca4be829baf395`;
its sole failure JSON is 16,255 bytes, SHA-256
`0fb361b6248631a96dd613aedb731a4aa5c753867b61a97c120aea56b1756cce`.
Two reviewers checked exact head, CRLF manifest, initial module variant,
canonical imports and all closed gates. All eight `CL` contexts contain the
ordered untruncated family chain `type-initialization, argument`, with no
matched HRESULT/Win32 labels. This identifies `ArgumentException`, not
`ArgumentNullException`. Message, parameter and initializer identity were not
delivered, so no environment/flag fix or exact underlying cause is established.
Configure failed after 6.716 seconds; graph/compile/inference, final tool/variant
checks and a delivered source-cohort receipt were not reached.

The complete VS/MSBuild and VC/Auxiliary trees and any present named NETFX4.8
headers/import libraries are included. The OS/.NET execution prerequisites
remain named, unbound native inputs. A fresh empty profile, explicit sealed VC
targets, disabled Directory.Build/user wildcard imports and disabled node reuse
prevent ambient MSBuild user configuration. Parent response/import files are
rejected; the source files are preserved. Each build/probe runs in the existing
join-before-spawn Win32 Job Object and drains only its owned descendants,
including after a timeout. Cleanup failure prevents a passing receipt.

The build uses explicit Release/x64/static-CRT flags consistent with the selected
ONNX MT input. No Microsoft redistributable is copied from a developer machine.
Package registries, installed ONNX detection, ambient Git metadata, compiler flags
and Python user sites cannot choose source inputs. Generated compilation units
must remain in the prepared/build root. Actual native project/source inputs,
the binding link map, named exports and normal/delay imports are checked for the
expected Python/ONNX/system scope and absence of eSpeak/Piper/phonemizer inputs.
One shared native-name predicate recognizes vendor/API boundaries in actual
`espeak_`/`espeak_ng_` functions, `espeak-ng`/`piper-phonemize` libraries/paths,
and native phonemizer identifiers, including MSVC-decorated forms. Retained
`OfflineSpeakerDiarization`/`PybindOfflineSpeakerDiarization` names contain an
incidental e+Speaker substring and must not count as eSpeak implementation.
This keeps diarization enabled; fixed TTS-OFF/configuration, exact source graph
and structural TTS compilation checks remain independent requirements.
Dynamic runtime loading in unexercised features is still an exact-output review
question; a marker search alone is not a broad native-closure approval.

The private wheel uses distribution name `proxy-r19-sherpa-asr-reference`, version
`1.13.8+proxy.r19.asr1`; the ordinary `sherpa_onnx` Python API is retained inside
that isolated candidate. No stock core wheel or package from site-packages is
used. Source Python files, the explicit version suffix, patched binding, exact
ONNX DLL and notices have recorded identities.
Upstream `version.cc` embeds an older Git identifier (`8c8e275d`); it is retained
as upstream metadata and explicitly cannot prove the selected source revision.
Archive/patch/source-inventory hashes provide that binding. The probe also checks
the actual ONNX API's reported version against 1.28.2.

[The owned fixture](../scripts/probe-reference-asr.py) writes a small original
ONNX protobuf graph, original six-token vocabulary and half a second of silence.
Its four inputs and metadata follow the fixed
[SenseVoice adapter](https://github.com/k2-fsa/sherpa-onnx/blob/11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf/sherpa-onnx/csrc/offline-sense-voice-model.cc)
and [decoder](https://github.com/k2-fsa/sherpa-onnx/blob/11afbd009a7f8c08f4bcf2fc1b265d0df4670fbf/sherpa-onnx/csrc/offline-recognizer-sense-voice-impl.h).
The wire fields follow the public [ONNX schema](https://github.com/onnx/onnx/blob/v1.16.0/onnx/onnx.proto).
Its dynamic logits deliberately emit `AUTHORED` regardless of sound. Separate,
bounded native child processes must exercise `from_sense_voice`, `create_stream`,
`accept_waveform`, `decode_stream` and `result.text`, reject an invalid ONNX file,
and observe the native adapter's empty result after an incompatible input shape.
They verify the imported binding and loaded ONNX DLL's exact candidate origin.
These are native format/API checks, **not speech recognition or model accuracy**.

Success uploads only `PREPARED.json` and `ASR-RECEIPT.json`. Failure may separately
upload `ASR-FAILURE.json`, containing fixed phase/category and allowlisted tool
codes, with failed status and all acceptance gates still closed. Exception,
log, command, model and path text is excluded. No native
payload, wheel, input archive, model/audio fixture, raw log/trace/link map, private
file inventory or absolute build/tool path is uploaded. An incomplete native
build/probe produces no passing final receipt.

## Open decisions

All production execution and runtime collection permissions remain false;
redistribution and ONNX/toolchain/CRT source correspondence stay pending. Source
and notice retention do not approve native ownership, static-CRT redistribution,
the existing Python supplier's mappings or the complete combined artifact.
The project license is unchanged, and the separate Xiph build-recipe grant is
not extended to this experiment.

No pretrained ASR model weights or model terms are used or accepted. The official
[SenseVoice model card](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)
declares separate model terms; a later exact weight/token selection and intended
use need their own review. An authored graph cannot close that gate.

Local preparation and regression tests do not establish a successful Windows
build. A successful hosted Server run would establish only its bounded source
build and native format/API observations. Clean ordinary-user Windows11 x64
25H2, capture/DPI, trained recognition quality, full R19 and merge readiness
remain separate gates. No such Windows11 environment is currently available.
