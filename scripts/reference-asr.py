"""Private build-host experiment; never selected by a production runtime profile.

Download-free preparation and evidence collection for the separately identified
TTS-disabled sherpa binding. Raw archives/build logs/inventories stay private.
"""
import argparse
import base64
import csv
import hashlib
import html
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'packaging/asr/sherpa-reference.json'
CMAKE_TOOL_POLICY = 'packaging/build-tools/cmake-4.4.5-windows-x64.json'
SOURCE_FILES = (MANIFEST, 'packaging/asr/tts-off-python-symbols.patch',
                'packaging/asr/SHERPA-LICENSE.txt', 'packaging/asr/SHERPA-PATCH-NOTICE.txt',
                'packaging/asr/cmake-compilerid-instance-location.patch',
                'packaging/asr/CMAKE-LICENSE.rst', 'packaging/asr/CMAKE-MODULE-PATCH-NOTICE.txt',
                'scripts/reference-asr.py', 'scripts/build-reference-asr.ps1',
                'scripts/probe-reference-asr.py',
                'packaging/runtime-bundle/python-supplier.json',
                CMAKE_TOOL_POLICY, 'scripts/pinned-build-cmake.py',
                'backend/windows_preparation_process.py', 'LICENSE')

BUILD_PHASES = frozenset({'build-preflight', 'source-validation', 'toolchain-validation',
    'vs-installation-origin', 'tool-root-schema', 'tool-root-filesystem',
    'python-interpreter-origin', 'python-supplier-bytes', 'cmake-version-review',
    'cmake-pinned-input', 'final-cmake-pinned-input',
    'cmake-module-variant-preparation', 'final-cmake-module-variant',
    'vc-target-selection', 'parent-import-review', 'configure-argument-review',
    'toolchain-seal', 'probe-dependency-preparation', 'build-environment', 'cmake-configure',
    'common-data-origin', 'common-data-baseline', 'common-data-bound', 'common-data-final',
    'build-graph-review', 'native-build', 'native-output-review', 'candidate-assembly',
    'probe-decode', 'probe-wrong-shape', 'probe-corrupt', 'final-source-review',
    'final-candidate-review', 'final-toolchain-review', 'source-commit-review', 'success-receipt'})
PHASE_LOGS = {'cmake-configure': 'configure.log', 'native-build': 'build.log',
    'probe-decode': 'probe-decode.log', 'probe-wrong-shape': 'probe-wrong-shape.log',
    'probe-corrupt': 'probe-corrupt.log'}
# Only these fixed public code labels may leave private compiler/MSBuild logs.
# Unrecognized errors produce a category, never the unknown token or message.
KNOWN_BUILD_CODES = frozenset({'C1001', 'C1010', 'C1083', 'C1189', 'C1900', 'C2001',
    'C2011', 'C2027', 'C2039', 'C2061', 'C2065', 'C2079', 'C2084', 'C2100', 'C2131',
    'C2143', 'C2146', 'C2171', 'C2198', 'C2248', 'C2338', 'C2440', 'C2491', 'C2512',
    'C2530', 'C2660', 'C2664', 'C2665', 'C2672', 'C2678', 'C2872', 'C3646', 'C3861',
    'C4996', 'D8016', 'D8021', 'D8022', 'LNK1104', 'LNK1107', 'LNK1112', 'LNK1120',
    'LNK1181', 'LNK1257', 'LNK2001', 'LNK2005', 'LNK2019', 'LNK2038',
    'MSB1009', 'MSB1011', 'MSB3073', 'MSB3644', 'MSB4018', 'MSB4019', 'MSB4057',
    'MSB6003', 'MSB6006', 'MSB8020', 'MSB8036'})
_BUILD_PHASE = 'build-preflight'
_BUILD_SOURCE_COMMIT = None
_BUILD_CMAKE_OBSERVATION = None
_BUILD_ENVIRONMENT_OBSERVATION = None
_BUILD_VS_VERSION = None
_BUILD_TOOL_ROOTS = None  # Private paths; never serialized.
_BUILD_PROPERTIES = None  # Actual configure properties; never serialized.
_BUILD_INSTANCE = None  # Actual generator argument/root and observed version, private.
_BUILD_TOOLCHAIN_SEAL = None  # Initial exact native tool inventory, never serialized here.
_BUILD_CMAKE_VARIANT = None
_BUILD_COMMON_DATA_PATH = None  # OS value stays private; never serialized/hashed.
COMMON_DATA_BYTES = 32768
COMMON_DATA_SECONDS = 30
COMMON_DATA_REASONS = frozenset({'none', 'not-run', 'process-rejected', 'invalid-markers',
    'invalid-utf8', 'output-limit', 'deadline', 'pipe-unavailable'})
COMMON_DATA_CALL_STAGES = frozenset({'not-run', 'not-observed', 'returned'})
COMMON_DATA_MSB_CODES = ('MSB4184', 'MSB4185', 'MSB4186')
COMMON_DATA_PROJECT = r'''<Project DefaultTargets="R19Root" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <Target Name="R19Folder">
    <PropertyGroup>
      <_R19Folder>$([System.Environment]::GetFolderPath('SpecialFolder.CommonApplicationData'))</_R19Folder>
      <_R19ProgramData>$([System.Environment]::GetEnvironmentVariable('PROGRAMDATA'))</_R19ProgramData>
      <_R19AllUsers>$([System.Environment]::GetEnvironmentVariable('ALLUSERSPROFILE'))</_R19AllUsers>
    </PropertyGroup>
    <Message Importance="High" Text="R19-ASR-COMMON-V1 folder;runtime=$(MSBuildRuntimeType);x64=$([System.Environment]::Is64BitProcess);empty=$([System.String]::IsNullOrWhiteSpace('$(_R19Folder)'));programdata=$([System.String]::Equals('$(_R19Folder)', '$(_R19ProgramData)', 'StringComparison.OrdinalIgnoreCase'));allusers=$([System.String]::Equals('$(_R19Folder)', '$(_R19AllUsers)', 'StringComparison.OrdinalIgnoreCase'))" />
    <PropertyGroup>
      <_R19DoNotVerifyFolder>$([System.Environment]::GetFolderPath('SpecialFolder.CommonApplicationData', 'SpecialFolderOption.DoNotVerify'))</_R19DoNotVerifyFolder>
    </PropertyGroup>
    <Message Importance="High" Text="R19-ASR-COMMON-V1 do-not-verify-returned" />
    <Message Importance="High" Text="R19-ASR-COMMON-V1 do-not-verify;empty=$([System.String]::IsNullOrWhiteSpace('$(_R19DoNotVerifyFolder)'));rooted=$([System.IO.Path]::IsPathRooted('$(_R19DoNotVerifyFolder)'));programdata=$([System.String]::Equals('$(_R19DoNotVerifyFolder)', '$(_R19ProgramData)', 'StringComparison.OrdinalIgnoreCase'));allusers=$([System.String]::Equals('$(_R19DoNotVerifyFolder)', '$(_R19AllUsers)', 'StringComparison.OrdinalIgnoreCase'))" />
  </Target>
  <Target Name="R19Root" DependsOnTargets="R19Folder">
    <PropertyGroup><_R19Root>$([System.IO.Path]::GetPathRoot('$(_R19Folder)'))</_R19Root></PropertyGroup>
    <Message Importance="High" Text="R19-ASR-COMMON-V1 root;empty=$([System.String]::IsNullOrEmpty('$(_R19Root)'));rooted=$([System.IO.Path]::IsPathRooted('$(_R19Folder)'))" />
  </Target>
</Project>
'''
CMAKE_VARIANT_IDENTITY = 'cmake-4.4.5-r19-asr-compilerid-instance.1'
CMAKE_VARIANT_MODULE = 'share/cmake-4.4/Modules/CMakeDetermineCompilerId.cmake'
CMAKE_VARIANT_FILES = ('packaging/asr/cmake-compilerid-instance-location.patch',
    'packaging/asr/CMAKE-LICENSE.rst', 'packaging/asr/CMAKE-MODULE-PATCH-NOTICE.txt')
LOG_TAIL_BYTES = 2 * 1024 * 1024
NESTED_LOG_TOTAL_BYTES = 4 * 1024 * 1024
COMPILER_CONTEXT_FILE_BYTES = 256 * 1024
KNOWN_COMPILER_IDS = frozenset({'MSVC', 'Clang', 'GNU', 'Intel', 'IntelLLVM'})
IMPORT_CONTEXT_LIMIT = 16
MSB4018_BLOCK_BYTES = 32 * 1024
MSB4018_CHAIN_DEPTH = 8
MSB4018_FRAME_LIMIT = 16
# English .NET Framework resources in microsoft/referencesource ec9fa9ae,
# plus fixed public members in that source and dotnet/msbuild 86743d05.
ARGUMENT_MESSAGES = {
    'Value does not fall within the expected range.': 'generic-argument',
    'The path is not of a legal form.': 'path-illegal',
    'Illegal characters in path.': 'path-invalid-characters',
    'Path cannot be the empty string or all whitespace.': 'path-empty',
    'Empty path name is not legal.': 'path-empty',
    "The given path's format is not supported.": 'path-format-unsupported',
    'URI formats are not supported.': 'path-uri-unsupported',
    'Absolute path information is required.': 'absolute-path-required',
    'String cannot be of zero length.': 'string-empty', 'String may not be empty or null.': 'string-empty',
    'An item with the same key has already been added.': 'dictionary-duplicate',
    'Environment variable name cannot contain equal character.': 'env-name-invalid',
    'The first char in the string is the null character.': 'env-name-invalid',
    'Environment variable name cannot contain 1024 or more characters.': 'env-name-too-long',
    'Environment variable name or value is too long.': 'env-name-or-value-too-long'}
ARGUMENT_PARAMETERS = {'path': 'path-input', 'path1': 'path-first', 'path2': 'path-second',
    'path3': 'path-third', 'path4': 'path-fourth', 'paths': 'path-array',
    'sourceDirName': 'source-directory', 'destDirName': 'destination-directory',
    'variable': 'environment-name', 'target': 'environment-target',
    'folder': 'special-folder-selector', 'option': 'special-folder-option', 'key': 'dictionary-key'}
ARGUMENT_FRAME_ROLES = {
    **{'System.IO.Path.' + name: role for name, role in (
        ('GetPathRoot', 'path-root'), ('GetTempPath', 'temp-path'), ('GetFullPath', 'full-path'),
        ('GetFullPathInternal', 'full-path'), ('NormalizePath', 'path-normalization'),
        ('NewNormalizePath', 'path-normalization'), ('NewNormalizePathLimitedChecks', 'path-normalization'),
        ('LegacyNormalizePath', 'path-normalization'), ('CheckInvalidPathChars', 'path-character-check'),
        ('Combine', 'path-combination'), ('InternalCombine', 'path-combination'))},
    **{'System.Environment.' + name: role for name, role in (
        ('GetFolderPath', 'special-folder'), ('InternalGetFolderPath', 'special-folder'),
        ('GetEnvironmentVariable', 'environment-read'), ('SetEnvironmentVariable', 'environment-write'))},
    'System.IO.Directory.CreateDirectory': 'directory-create',
    'System.IO.DirectoryInfo..ctor': 'directory-constructor',
    'System.Collections.Generic.Dictionary`2.Insert': 'dictionary-insert',
    'Microsoft.Build.Utilities.FileTracker..cctor': 'file-tracker-initialization',
    'Microsoft.Build.Utilities.FileTracker.InitializeCommonApplicationDataPaths': 'file-tracker-common-data',
    'Microsoft.Build.Utilities.FileTracker.FormatRootingMarker': 'file-tracker-caller'}
# Microsoft C++/MSBuild task references and .NET API names; only fixed labels
# leave the private MSB4018 context. Unknown names/codes are never echoed.
MSBUILD_TASK_LABELS = {name.casefold(): label for name, label in (
    ('BscMake', 'bscmake'), ('CL', 'cl'), ('CPPClean', 'cpp-clean'),
    ('ClangCompile', 'clang-compile'), ('CustomBuild', 'custom-build'), ('FXC', 'fxc'),
    ('GetOutOfDateItems', 'get-out-of-date-items'), ('GetOutputFileName', 'get-output-file-name'),
    ('LIB', 'lib'), ('Link', 'link'), ('MIDL', 'midl'), ('MT', 'mt'),
    ('MultiToolTask', 'multi-tool-task'), ('ParallelCustomBuild', 'parallel-custom-build'),
    ('RC', 'rc'), ('SetEnv', 'set-env'), ('VCMessage', 'vc-message'),
    ('Copy', 'copy'), ('Delete', 'delete'), ('Error', 'error'), ('Exec', 'exec'),
    ('GetFrameworkPath', 'get-framework-path'), ('GetFrameworkSdkPath', 'get-framework-sdk-path'),
    ('MakeDir', 'make-dir'), ('Message', 'message'), ('MSBuild', 'msbuild'),
    ('ReadLinesFromFile', 'read-lines-from-file'), ('RemoveDir', 'remove-dir'),
    ('Warning', 'warning'), ('WriteLinesToFile', 'write-lines-to-file'))}
DOTNET_EXCEPTION_LABELS = {'System.' + name: label for name, label in (
    ('Exception', 'exception'), ('ArgumentException', 'argument'),
    ('ArgumentNullException', 'argument-null'), ('ArgumentOutOfRangeException', 'argument-out-of-range'),
    ('IndexOutOfRangeException', 'index-out-of-range'), ('InvalidOperationException', 'invalid-operation'),
    ('NullReferenceException', 'null-reference'), ('TypeInitializationException', 'type-initialization'),
    ('DllNotFoundException', 'dll-not-found'), ('BadImageFormatException', 'bad-image-format'),
    ('UnauthorizedAccessException', 'unauthorized-access'), ('IO.IOException', 'io'),
    ('IO.FileNotFoundException', 'file-not-found'), ('IO.DirectoryNotFoundException', 'directory-not-found'),
    ('IO.FileLoadException', 'file-load'), ('IO.PathTooLongException', 'path-too-long'),
    ('ComponentModel.Win32Exception', 'win32'), ('Runtime.InteropServices.COMException', 'com'))}
HRESULT_LABELS = {'0x80004001': 'e-notimpl', '0x80004002': 'e-nointerface',
    '0x80004003': 'e-pointer', '0x80004004': 'e-abort', '0x80004005': 'e-fail',
    '0x8000ffff': 'e-unexpected', '0x80070005': 'e-accessdenied', '0x80070006': 'e-handle',
    '0x8007000e': 'e-outofmemory', '0x80070057': 'e-invalidarg',
    '0x8007007e': 'win32-module-not-found-hresult'}
WIN32_ERROR_LABELS = {'2': 'file-not-found', '3': 'path-not-found', '5': 'access-denied',
    '11': 'bad-format', '87': 'invalid-parameter', '126': 'module-not-found', '193': 'bad-exe-format'}
COMPILER_ID_IMPORT_LIMIT = 16
AUX_SEAL_ENTRY_LIMIT = 50000
AUX_MAPPING_CANDIDATE_LIMIT = 32
AUX_MAPPING_FILE_BYTES = 64 * 1024
AUX_MAPPING_TOTAL_BYTES = 512 * 1024
PRIMARY_IMPORT_LEAVES = {'microsoft.cpp.default.props': 'microsoft-cpp-default-props',
    'microsoft.cpp.props': 'microsoft-cpp-props', 'microsoft.cpp.targets': 'microsoft-cpp-targets'}
PRIMARY_IMPORT_CALLERS = {**PRIMARY_IMPORT_LEAVES, 'compileridc.vcxproj': 'compiler-id-c-project',
    'compileridcxx.vcxproj': 'compiler-id-cxx-project'}
COMPILER_ID_PROPERTIES = ('VCTargetsPath', 'UserRootDir', 'MSBuildUserExtensionsPath',
    'ImportDirectoryBuildProps', 'ImportDirectoryBuildTargets')
PARENT_IMPORT_NAMES = frozenset({'Directory.Build.props', 'Directory.Build.targets',
    'Directory.Build.rsp', 'MSBuild.rsp'})
# Fixed error-template fragments reviewed in CMake 4.4.5 commit aa4fae824a02a175c4a11653d7a851a948f0c004.
# Matching private values are never captured or returned. Whitespace folding
# accommodates CMake's diagnostic wrapping; warnings are excluded separately.
CMAKE_EARLY_ERRORS = (
    ('cmake-generator-unavailable', r'(?:Could not create named generator|could not find any instance of Visual Studio)'),
    ('cmake-vs-instance-not-found', r'could not find specified instance of Visual Studio:'),
    ('cmake-vs-installation-not-found', r'could not find any instance of Visual Studio\.'),
    ('cmake-vs-installer-instance-unknown', r'instance is not known to the Visual Studio Installer'),
    ('cmake-vs-instance-version-invalid', r'but the version field is not 4 integer components starting in'),
    ('cmake-vs-instance-fields-invalid', r'given instance specification .{0,32768}? that contains (?:a field after|duplicate field key|invalid field)'),
    ('cmake-msbuild-vctargets-query-failed', r'Failed to run MSBuild command:'),
    ('cmake-toolset-version-invalid', r'given toolset and version specification .{0,32768}? contains an invalid version specification\.'),
    ('cmake-toolset-not-installed', r'given toolset and version specification .{0,32768}? does not seem to be installed at'),
    ('cmake-toolset-selection-ambiguous', r'The toolset and version specification must resolve to a single installed toolset'),
    ('cmake-toolset-fields-invalid', r'given toolset specification .{0,32768}? that contains (?:a field after|duplicate field key|invalid field)'),
    ('cmake-flagtable-not-found', r'JSON flag table for .{0,32768}? not found for toolset'),
    ('cmake-flagtable-load-failed', r'JSON flag table could not be loaded:'),
    ('cmake-platform-fields-invalid', r'given platform specification .{0,32768}? that contains (?:a field after|duplicate field key|invalid field)'),
    ('cmake-generator-specification-unsupported', r'does not support (?:instance|platform|toolset) specification'),
    ('cmake-platform-version-invalid', r'given platform specification (?:with empty version= field|containing a version=.{0,32768}? field with unsupported value\.)'),
    ('cmake-windows-sdk-not-found', r'(?:field, but no Windows SDK with that version was found\.|Could not find an appropriate version of the Windows 10 SDK installed on this machine|field, but the Windows 8\.1 SDK is not installed\.)'),
    ('cmake-build-program-not-found', r'CMake was unable to find a build program corresponding to'),
    ('cmake-compiler-not-found', r'(?:is not a full path and was not found in the PATH\.|is not a full path to an existing compiler tool\.)'),
    ('cmake-compiler-not-recorded', r'No CMAKE_(?:C|CXX|RC)_COMPILER could be found\.'),
    ('cmake-compiler-not-set', r'CMAKE_(?:C|CXX|RC)_COMPILER not set, after EnableLanguage'),
    ('cmake-environment-compiler-not-found', r'Could not find the compiler specified in the environment variable (?:CC|CXX|RC):'),
    ('cmake-compiler-identification-build-failed', r'Compiling the (?:C|CXX|RC) compiler identification source file ".{0,32768}?" failed\.'),
    ('cmake-msvc-version-not-detected', r'MSVC compiler version not detected properly:'),
    ('cmake-msvc-clui-not-found', r'Could not find clui\.dll !'),
    ('cmake-compiler-test-failed', r'is not able to compile a simple test program'),
    ('cmake-cli-argument-invalid', r'(?:Unknown argument |Parse error in command line argument:|Multiple -(?:A|T) options not allowed|No (?:source|build) directory specified for -(?:S|H|B)|No (?:platform|toolset) specified for -(?:A|T)|-D must be followed with VAR=VALUE\.|Invalid format specified for --trace-format)'),
    ('cmake-source-directory-invalid', r'The source directory ".{0,32768}?" (?:does not exist\.|is a file, not a directory\.|does not appear to contain CMakeLists\.txt\.)'),
    ('cmake-cache-source-mismatch', r'used to generate cache\. Re-run cmake with a different source directory\.'),
    ('cmake-cache-generator-mismatch', r'Does not match the generator used previously:'),
    ('cmake-cache-instance-mismatch', r'Does not match the instance used previously:'),
    ('cmake-cache-platform-mismatch', r'Does not match the platform used previously:'),
    ('cmake-cache-toolset-mismatch', r'Does not match the toolset used previously:'),
    ('cmake-project-arguments-invalid', r'(?:PROJECT called with incorrect number of arguments|project with VERSION, DESCRIPTION or HOMEPAGE_URL must use LANGUAGES before language names\.|project with COMPAT_VERSION must also provide VERSION\.|COMPAT_VERSION must be less than or equal to VERSION)'),
    ('cmake-project-include-unavailable', r'(?:could not find requested module:|could not find requested file:|could not load requested file:|requested file is a directory:)'),
    ('cmake-minimum-version-required', r'CMake [0-9]+\.[0-9]+(?:\.[0-9]+){0,2} or higher is required\. You are running version'),
    ('cmake-compatibility-removed', r'Compatibility with CMake < 3\.5 has been removed from CMake\.'),
    ('cmake-policy-minimum-invalid', r'Invalid CMAKE_POLICY_VERSION_MINIMUM value '),
    ('cmake-policy-unknown', r'(?:Policy "CMP[0-9]{4}" is not known to this version of CMake\.|GET(?:_WARNING)? given policy "CMP[0-9]{4}" which is not known to this version of CMake\.)'),
    ('cmake-policy-old-unsupported', r'(?:Policy CMP[0-9]{4} may not be set to OLD behavior because this version of CMake no longer supports it\.|this version of CMake no longer supports the OLD behavior for these policies\.)'),
    ('cmake-policy-arguments-invalid', r'cmake_policy (?:requires at least one argument\.|SET must be given exactly 2 additional arguments\.|SET given unrecognized policy status|SET failed to set policy\.|VERSION not given an argument|VERSION given too many arguments)'),
    ('cmake-command-unknown', r'Unknown CMake command "'),
)
CMAKE_ERROR_COMMANDS = frozenset({'project', 'cmake_minimum_required', 'cmake_policy',
    'message', 'find_package', 'enable_language', 'include', 'add_subdirectory',
    'add_library', 'target_link_libraries', 'set_property', 'set_target_properties',
    'fetchcontent_declare', 'fetchcontent_populate', 'fetchcontent_makeavailable',
    'find_package_handle_standard_args'})


def build_phase(value):
    global _BUILD_PHASE
    if value not in BUILD_PHASES:
        raise ValueError('Unknown private ASR build phase.')
    _BUILD_PHASE = value


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate evidence key.')
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_json)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def no_links(path):
    for item in (path, *path.parents):
        if (item.is_symlink() or getattr(item, 'is_junction', lambda: False)()
                or (item.exists() and getattr(item.lstat(), 'st_file_attributes', 0) & 0x400)):
            raise ValueError('Links and reparse points are not experiment inputs.')


def safe_name(name):
    if (not name or '\\' in name or ':' in name or PurePosixPath(name).is_absolute()
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or any(p in {'', '.', '..'} or p.endswith((' ', '.'))
                   or re.match(r'^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', p, re.I)
                   for p in name.split('/'))):
        raise ValueError('Non-canonical experiment input path.')
    return name


def attributes(data):
    return {'bytes': len(data), 'sha256': sha(data)}


def inventory(root):
    no_links(root)
    result = {}
    for path in sorted(root.rglob('*')):
        no_links(path)
        name = safe_name(path.relative_to(root).as_posix())
        if path.is_file():
            result[name] = attributes(path.read_bytes())
        elif not path.is_dir():
            raise ValueError('Non-regular experiment input.')
    return result


def pin():
    diagnostic_file_info(ROOT / MANIFEST)
    value = read_json(ROOT / MANIFEST)
    if (value['schema'] != 'proxy-r19-asr-source-reference-v1'
            or value.get('cmake_build_tool_policy') != CMAKE_TOOL_POLICY
            or value['gates'] != {'production_execution_allowed': False,
                'runtime_collection_allowed': False, 'redistribution_review': 'pending-exact-output',
                'native_windows_11_acceptance': 'unavailable',
                'trained_model_acceptance': 'not-requested-no-asr-model-weights', 'r19_complete': False}):
        raise ValueError('ASR experiment identity or pending gates differ.')
    return value


def archive_files(path, item):
    """Validate before writing; main source deliberately omits unrelated links.

    Whole original archives are retained privately and bound by exact hash. Every
    archive name is canonical; every selected entry must be a regular file/dir.
    No general link exemption or arbitrary archive is accepted.
    """
    no_links(path)
    if attributes(path.read_bytes()) != {'bytes': item['bytes'], 'sha256': item['sha256']}:
        raise ValueError('An exact source/dependency archive is missing or changed.')
    result, aliases, spelling, total = {}, set(), {}, 0
    archive = zipfile.ZipFile(path) if path.suffix == '.zip' else tarfile.open(path)
    with archive:
        members = archive.infolist() if isinstance(archive, zipfile.ZipFile) else archive.getmembers()
        if len(members) > 20000:
            raise ValueError('Source/dependency archive is too large.')
        for member in members:
            is_zip = isinstance(member, zipfile.ZipInfo)
            raw_name = member.filename if is_zip else member.name
            name = safe_name(raw_name.rstrip('/'))
            parts = name.split('/', 1)
            if parts[0] != item['archive_root']:
                raise ValueError('Source/dependency archive root differs.')
            relative = parts[1] if len(parts) == 2 else ''
            selected = not item['selected_prefixes'] or any(
                relative == p or relative.startswith(p + '/') for p in item['selected_prefixes'])
            if not selected or not relative:
                continue
            for n in range(1, len(relative.split('/')) + 1):
                prefix = '/'.join(relative.split('/')[:n])
                previous = spelling.setdefault(prefix.casefold(), prefix)
                if previous != prefix:
                    raise ValueError('Case-aliased source/dependency directory.')
            if relative.casefold() in aliases:
                raise ValueError('Duplicate or case-aliased source/dependency entry.')
            aliases.add(relative.casefold())
            if is_zip:
                mode = member.external_attr >> 16
                directory, regular = member.is_dir(), stat.S_IFMT(mode) in (0, stat.S_IFREG)
                size = member.file_size
            else:
                directory, regular, size = member.isdir(), member.isfile(), member.size
            if directory:
                continue
            if not regular or size > 32 * 1024 * 1024:
                raise ValueError('Selected source/dependency entry is not a bounded regular file.')
            total += size
            if total > 160 * 1024 * 1024:
                raise ValueError('Selected source/dependency bytes exceed the experiment bound.')
            data = archive.read(member) if is_zip else archive.extractfile(member).read()
            if len(data) != size:
                raise ValueError('Truncated source/dependency entry.')
            result[relative] = data
    if not result:
        raise ValueError('Empty source/dependency archive.')
    # Also reject file/directory aliases before creating anything.
    names = {name.casefold() for name in result}
    if any('/'.join(name.split('/')[:n]).casefold() in names
           for name in result for n in range(1, len(name.split('/')))):
        raise ValueError('Source/dependency file is used as a directory.')
    if any(attributes(result.get(name, b'')) != expected for name, expected in item['notices'].items()):
        raise ValueError('Source/dependency notice bytes differ.')
    return result


def patched_source(data, patch_pin):
    patch = ROOT / patch_pin['file']
    if sha(patch.read_bytes()) != patch_pin['sha256'] or sha(data) != patch_pin['before_sha256']:
        raise ValueError('TTS-off patch or its exact upstream base differs.')
    # Apply only the two recorded additions; no external patch program/config.
    result = data.replace(b'  /* Define "empty" TTS symbols */\n',
        b'  /* Define "empty" TTS symbols */\n  m.attr("GenerationConfig") = py::none();\n')
    result = result.replace(b'  m.attr("OfflineTtsMatchaModelConfig") = py::none();\n',
        b'  m.attr("OfflineTtsMatchaModelConfig") = py::none();\n'
        b'  m.attr("OfflineTtsSupertonicModelConfig") = py::none();\n')
    if sha(result) != patch_pin['after_sha256']:
        raise ValueError('TTS-off patch result differs.')
    return result


def verify_patch_notices(policy):
    upstream = next(i for i in policy['inputs'] if i['name'] == 'sherpa-onnx')
    if (policy['patch_notices'][policy['patch']['license_file']] != upstream['notices']['LICENSE']
            or any(attributes((ROOT / name).read_bytes()) != expected
                   for name, expected in policy['patch_notices'].items())):
        raise ValueError('Public patch attribution or complete original Apache license differs.')


def source_input_records():
    values = {}
    for name in SOURCE_FILES:
        info = diagnostic_file_info(ROOT / name)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('ASR source recipes must be regular unlinked files.')
        values[name] = attributes((ROOT / name).read_bytes())
    return values


def prepare(inputs, output):
    policy = pin()
    inputs, output = Path(inputs).absolute(), Path(output).absolute()
    no_links(inputs); no_links(output)
    if output.exists():
        raise ValueError('Choose a fresh private ASR experiment directory.')
    verify_patch_notices(policy)
    cmake_variant_sources(policy)
    prepared = {item['name']: archive_files(inputs / item['filename'], item)
                for item in policy['inputs']}
    prepared['sherpa-onnx'][policy['patch']['target']] = patched_source(
        prepared['sherpa-onnx'][policy['patch']['target']], policy['patch'])
    source_inputs = source_input_records()
    # All source/archive/notice/patch checks finish before the first output write.
    output.mkdir(parents=True)
    for item in policy['inputs']:
        shutil.copyfile(inputs / item['filename'], output / item['filename'])
        for name, data in prepared[item['name']].items():
            dest = output / 'sources' / item['name'] / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        for name in item['notices']:
            dest = output / 'notices' / item['name'] / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(prepared[item['name']][name])
    for name in SOURCE_FILES:
        dest = output / 'recipes' / name
        try:
            diagnostic_file_info(dest.parent)
        except FileNotFoundError:
            pass  # The checked ancestor chain ends before the fresh recipe directory.
        dest.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_file_info(dest.parent); diagnostic_file_info(ROOT / name)
        with (ROOT / name).open('rb') as source, dest.open('xb') as target:
            shutil.copyfileobj(source, target)
    expected = inventory(output / 'sources')
    write_json(output / 'PRIVATE-SOURCE-INVENTORY.json', expected)
    receipt = {'schema': policy['schema'], 'identity': policy['identity'],
        'manifest_sha256': sha((ROOT / MANIFEST).read_bytes()), 'source_inputs': source_inputs,
        'source_inventory_sha256': sha(canonical(expected)), 'source_file_count': len(expected),
        'input_archives': {i['name']: {'sha256': i['sha256'], 'bytes': i['bytes'],
            'kind': i['kind'], 'url': i['url']} for i in policy['inputs']},
        'patch': policy['patch'], 'patch_notices': policy['patch_notices'],
        'configuration': policy['cmake'], 'gates': policy['gates'],
        'python_supplier_pin': read_json(ROOT / policy['python_supplier_manifest']),
        'numpy_probe_dependency_pin': policy['numpy'],
        'cmake_build_tool_policy': policy['cmake_build_tool_policy'],
        'cmake_module_variant': policy['cmake_module_variant'],
        'status': 'prepared-not-built', 'rights_approval': False}
    write_json(output / 'PREPARED.json', receipt)
    return receipt


def verify_sources(output):
    policy, output = pin(), Path(output).absolute()
    receipt = read_json(output / 'PREPARED.json')
    verify_patch_notices(policy)
    cmake_variant_sources(policy)
    expected = read_json(output / 'PRIVATE-SOURCE-INVENTORY.json')
    source_inputs = source_input_records()
    if (receipt['manifest_sha256'] != sha((ROOT / MANIFEST).read_bytes())
            or receipt['source_inputs'] != source_inputs
            or inventory(output / 'recipes') != source_inputs
            or receipt.get('cmake_build_tool_policy') != policy['cmake_build_tool_policy']
            or receipt.get('cmake_module_variant') != policy['cmake_module_variant']
            or receipt['source_inventory_sha256'] != sha(canonical(expected))
            or inventory(output / 'sources') != expected or receipt['gates'] != policy['gates']):
        raise ValueError('Prepared ASR source, recipes or gates changed.')
    for item in policy['inputs']:
        archive = output / item['filename']; no_links(archive)
        if attributes(archive.read_bytes()) != {'bytes': item['bytes'], 'sha256': item['sha256']}:
            raise ValueError('Retained exact input archive changed.')
        for name, expected_notice in item['notices'].items():
            notice = output / 'notices' / item['name'] / name; no_links(notice)
            if attributes(notice.read_bytes()) != expected_notice:
                raise ValueError('Retained input notice changed.')
    return receipt


def cmake_arguments(output, python):
    output, python = Path(output).absolute(), Path(python).absolute()
    verify_sources(output)
    args = [f'-D{key}={value}' for key, value in pin()['cmake'].items()]
    args += [f'-DFETCHCONTENT_SOURCE_DIR_{item["fetchcontent_name"].upper()}=' +
             (output / 'sources' / item['name']).as_posix()
             for item in pin()['inputs'] if item['fetchcontent_name']]
    args += [f'-DPython_EXECUTABLE={python.as_posix()}', f'-DPYTHON_EXECUTABLE={python.as_posix()}',
             f'-DPython_ROOT_DIR={python.parent.as_posix()}',
             f'-DPython_INCLUDE_DIR={(python.parent / "include").as_posix()}',
             f'-DPython_LIBRARY={(python.parent / "libs/python312.lib").as_posix()}',
             '-DPython_FIND_REGISTRY=NEVER', '-DCMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH=OFF',
             '-DCMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH=OFF',
             '-DCMAKE_PREFIX_PATH=', '-DCMAKE_TOOLCHAIN_FILE=', '-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=']
    return args


def verify_trace(path, output):
    """Require the exact selected FetchContent set, no undeclared downloads.

    CMake trace/logs remain private. This bounded source-graph check does not
    claim an OS network sandbox or blanket absence of runtime LoadLibrary.
    """
    output = Path(output).absolute()
    expected = {i['fetchcontent_name'] for i in pin()['inputs'] if i['fetchcontent_name']}
    declared, populated = set(), set()
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        event = json.loads(line)
        command, args = event.get('cmd', '').casefold(), event.get('args', [])
        if not command:
            continue
        if command == 'file' and args and args[0].casefold() in {'download', 'upload'}:
            raise ValueError('The ASR build attempted an undeclared network transfer.')
        if command == 'fetchcontent_declare' and args:
            name = args[0].casefold()
            if name not in expected:
                raise ValueError('The ASR build declared an unreviewed source dependency.')
            declared.add(name)
        if command in {'fetchcontent_populate', 'fetchcontent_makeavailable'} and args:
            name = args[0].casefold()
            if name not in expected:
                raise ValueError('The ASR build populated an unreviewed source dependency.')
            populated.add(name)
        if command == 'execute_process' and any(re.search(r'(?i)(?:https?://|(?:^|[/\\])(?:curl|wget)(?:\.exe)?$)', str(a)) for a in args):
            raise ValueError('The ASR build attempted an unreviewed downloader.')
    if declared != expected or populated != expected:
        raise ValueError('The observed ASR source dependency graph differs.')
    return {'declared': sorted(declared), 'populated': sorted(populated),
            'no_undeclared_fetch_observed': True, 'network_sandbox': False}


def verify_cache(path, output, vs_instance=None):
    values = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([^#/:][^:]*):[^=]+=(.*)', line)
        if match:
            if match[1] in values: raise ValueError('Duplicate CMake cache observation.')
            values[match[1]] = match[2]
    if any(values.get(key) != expected for key, expected in pin()['cmake'].items()):
        raise ValueError('The observed ASR configuration differs from the fixed recipe.')
    if vs_instance is not None and values.get('CMAKE_GENERATOR_INSTANCE') != vs_instance:
        raise ValueError('The configured VS instance differs from the exact selected path/version tuple.')
    for item in pin()['inputs']:
        name = item['fetchcontent_name']
        if name and Path(values.get('FETCHCONTENT_SOURCE_DIR_' + name.upper(), '')).resolve() != (output / 'sources' / item['name']).resolve():
            raise ValueError('The observed ASR source override differs from its exact prepared input.')


def validate_tool_root_schema(roots):
    required = {'vc', 'vc-auxiliary', 'msbuild', 'sdk-include', 'sdk-lib', 'sdk-bin', 'cmake', 'python'}
    if (not isinstance(roots, dict) or not required <= set(roots)
            or set(roots) - required - {'netfx-include', 'netfx-lib'}):
        raise ValueError('Incomplete explicit toolchain roots.')
    # Check all JSON value types before constructing even the first Path. A
    # PowerShell command-discovery array must never become an implicit choice.
    if any(not isinstance(value, str) or not value.strip()
           or any(ord(c) < 32 or ord(c) == 127 for c in value) for value in roots.values()):
        raise ValueError('Every explicit tool root must be one directory string.')


def validate_tool_roots(roots):
    validate_tool_root_schema(roots)
    for value in roots.values():
        path = Path(value)
        no_links(path)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError('Every explicit tool root must be one existing absolute directory.')


def numeric_version(value):
    return value if isinstance(value, str) and re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,4}', value) else None


def vs_instance_version(value):
    return value if isinstance(value, str) and re.fullmatch(r'18(?:\.[0-9]{1,6}){3}', value) else None


def cmake_instance_spec(root, version):
    if vs_instance_version(version) is None or not isinstance(root, (str, Path)):
        raise ValueError('One exact numeric four-component VS18 instance is required.')
    root = Path(root)
    if (not root.is_absolute() or any(ord(c) < 32 or ord(c) == 127 or c in ',;' for c in str(root))):
        raise ValueError('The VS instance root must be one explicit unambiguous absolute directory.')
    no_links(root)
    if not root.is_dir():
        raise ValueError('The selected VS instance directory is unavailable.')
    return root.resolve().as_posix() + ',version=' + version


def verify_vs_selection(root, version, vswhere, roots, expected_selection=None):
    """Re-query the wrapper's exact instance; never choose another installation."""
    global _BUILD_VS_VERSION
    cmake_instance_spec(root, version)
    validate_tool_roots(roots)
    root = Path(root).resolve()
    for name, relative in {'vc': 'VC/Tools/MSVC/' + pin()['toolchain']['vc_tools_version'],
            'vc-auxiliary': 'VC/Auxiliary', 'msbuild': 'MSBuild'}.items():
        if Path(roots[name]).resolve() != (root / relative).resolve():
            raise ValueError('The selected VS instance and sealed tool roots differ.')
    base = os.environ.get('ProgramFiles(x86)', '')
    if (not base or not Path(base).is_absolute() or not isinstance(vswhere, (str, Path))
            or not Path(vswhere).is_absolute()):
        raise ValueError('The explicit machine installer query tool is unavailable.')
    expected = Path(base) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    path = Path(vswhere)
    no_links(path); no_links(expected)
    if path.resolve() != expected.resolve() or not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
        raise ValueError('The selected VS discovery executable has a different origin.')
    before = attributes(path.read_bytes())
    data = subprocess.check_output([str(path), '-latest', '-products', '*', '-requires',
        'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-format', 'json', '-utf8'],
        stderr=subprocess.STDOUT, timeout=30)
    if attributes(path.read_bytes()) != before or len(data) > 1024 * 1024:
        raise ValueError('The VS discovery input changed or returned unbounded metadata.')
    values = json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique_json)
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise ValueError('The exact selected VS discovery result differs.')
    actual = values[0]
    _BUILD_VS_VERSION = vs_instance_version(actual.get('installationVersion'))
    if _BUILD_VS_VERSION != version:
        raise ValueError('The observed selected VS version differs from the supplied identity.')
    observed_root = actual.get('installationPath')
    if (not isinstance(observed_root, str)
            or cmake_instance_spec(observed_root, version) != cmake_instance_spec(root, version)):
        raise ValueError('The observed selected VS root differs from the sealed instance.')
    result = {'installation_version': version, 'vswhere': before}
    if expected_selection is not None and result != expected_selection:
        raise ValueError('The selected VS discovery bytes or instance version changed during the experiment.')
    return result


def safe_cmake_observation():
    """Project only bounded values, including if a caller alters private state."""
    value = _BUILD_CMAKE_OBSERVATION
    if not isinstance(value, dict):
        return None
    result = {'expected_version': numeric_version(value.get('expected_version')),
        'observed_version': numeric_version(value.get('observed_version')), 'executable': None}
    executable = value.get('executable')
    if (isinstance(executable, dict) and type(executable.get('bytes')) is int
            and 0 < executable['bytes'] <= 512 * 1024 * 1024
            and isinstance(executable.get('sha256'), str)
            and re.fullmatch('[0-9a-f]{64}', executable['sha256'])):
        result['executable'] = {'bytes': executable['bytes'], 'sha256': executable['sha256']}
    return result


def safe_build_environment_observation():
    value = _BUILD_ENVIRONMENT_OBSERVATION
    if not isinstance(value, dict):
        return None
    targets = value.get('vc_targets')
    observed = None
    if isinstance(targets, dict):
        count = targets.get('candidate_count')
        observed = {'candidate_count': count if type(count) is int and 0 <= count <= 4096 else None,
            'candidates': [], 'selected_family': None, 'selected_candidate_count': None,
            'selected_props_pin_matched': targets.get('selected_props_pin_matched') is True}
        family, selected_count = targets.get('selected_family'), targets.get('selected_candidate_count')
        if isinstance(family, str) and re.fullmatch(r'v[0-9]{1,4}', family):
            observed['selected_family'] = family
        if type(selected_count) is int and 0 <= selected_count <= 4096:
            observed['selected_candidate_count'] = selected_count
        candidates = targets.get('candidates')
        for candidate in candidates[:4096] if isinstance(candidates, list) else []:
            if not isinstance(candidate, dict):
                continue
            label = candidate.get('label')
            record = {'label': label if isinstance(label, str) and re.fullmatch(r'v[0-9]{1,4}', label) else None,
                'props': None}
            props = candidate.get('props')
            if (isinstance(props, dict) and type(props.get('bytes')) is int
                    and 0 <= props['bytes'] <= 16 * 1024 * 1024
                    and isinstance(props.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', props['sha256'])):
                record['props'] = {'bytes': props['bytes'], 'sha256': props['sha256']}
            observed['candidates'].append(record)
    categories = value.get('parent_import_categories')
    result = {'vc_targets': observed, 'parent_import_categories': sorted({
        name for name in categories if isinstance(name, str) and name in PARENT_IMPORT_NAMES}
        if isinstance(categories, list) else set())}
    if 'common_data' in value:
        result['common_data'] = safe_common_data_observation(value['common_data'])
    return result


def parent_import_categories(output):
    return sorted({name for directory in (output, *output.parents) for name in PARENT_IMPORT_NAMES
        if (directory / name).exists()})


def review_vc_targets(output, msbuild):
    """Select only the pinned family/props; retain every family's observation."""
    global _BUILD_ENVIRONMENT_OBSERVATION
    build_phase('vc-target-selection')
    # Inspect actual spelling before choosing a directory. A case/trailing-dot
    # alias must not become a second selected props input or a silent fallback.
    props_name = 'Microsoft.Cpp.Default.props'
    targets = sorted(path for path in (Path(msbuild) / 'Microsoft/VC').glob('*/*')
        if path.parent.name.casefold().startswith('v')
        and path.name.rstrip(' .').casefold() == props_name.casefold())
    candidates = []
    for path in targets[:4096]:
        label, props = path.parent.name.lower(), None
        try:
            no_links(path)
            if path.is_file() and path.stat().st_size <= 16 * 1024 * 1024:
                props = attributes(path.read_bytes())
        except (OSError, ValueError):
            pass  # Unavailable props remain explicit; no exception text escapes.
        candidates.append({'label': label, 'props': props})
    _BUILD_ENVIRONMENT_OBSERVATION = {'vc_targets': {'candidate_count': len(targets), 'candidates': candidates},
        'parent_import_categories': parent_import_categories(output)}
    selected_pin = pin()['toolchain']['vc_targets']
    family, expected = selected_pin.get('family'), selected_pin.get('default_props')
    if (not isinstance(family, str) or not re.fullmatch(r'v[0-9]{1,4}', family)
            or not isinstance(expected, dict) or set(expected) != {'bytes', 'sha256'}
            or type(expected.get('bytes')) is not int or not 0 < expected['bytes'] <= 16 * 1024 * 1024
            or not isinstance(expected.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', expected['sha256'])):
        raise ValueError('The explicit VC target family/props pin is invalid.')
    selected = [path for path in targets if path.parent.name.rstrip(' .').casefold() == family]
    observation = _BUILD_ENVIRONMENT_OBSERVATION['vc_targets']
    observation.update(selected_family=family, selected_candidate_count=len(selected), selected_props_pin_matched=False)
    if (len(selected) != 1 or selected[0].parent.name != family or selected[0].name != props_name):
        raise ValueError('One exact pinned VC target input is required; aliases and registry fallback are refused.')
    path = selected[0]
    no_links(path)
    if (not path.is_file() or path.stat().st_size != expected['bytes']
            or attributes(path.read_bytes()) != expected):
        raise ValueError('The selected VC target props bytes differ from the observed exact pin.')
    observation['selected_props_pin_matched'] = True
    return selected


def observe_cmake_version(executable, expected):
    global _BUILD_CMAKE_OBSERVATION
    _BUILD_CMAKE_OBSERVATION = {'expected_version': numeric_version(expected),
        'observed_version': None, 'executable': None}
    no_links(executable)
    if not executable.is_file() or numeric_version(expected) is None:
        raise ValueError('The explicit CMake executable or numeric version constraint is unavailable.')
    _BUILD_CMAKE_OBSERVATION['executable'] = attributes(executable.read_bytes())
    output = subprocess.check_output([str(executable), '--version'], text=True,
        stderr=subprocess.STDOUT, timeout=30)
    first = output.splitlines()[0] if output.splitlines() else ''
    match = re.fullmatch(r'cmake version ([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,4})', first)
    if match:
        _BUILD_CMAKE_OBSERVATION['observed_version'] = match[1]
    if first != 'cmake version ' + expected:
        raise ValueError('The required CMake version is unavailable.')
    if attributes(executable.read_bytes()) != _BUILD_CMAKE_OBSERVATION['executable']:
        raise ValueError('The observed CMake executable changed during its version query.')
    return safe_cmake_observation()


def cmake_tool_module():
    diagnostic_file_info(ROOT / 'scripts/pinned-build-cmake.py')
    spec = importlib.util.spec_from_file_location('r19_shared_pinned_cmake', ROOT / 'scripts/pinned-build-cmake.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    diagnostic_file_info(module.POLICY)
    if module.POLICY != ROOT / pin()['cmake_build_tool_policy']:
        raise ValueError('The shared CMake verifier policy differs from the ASR source binding.')
    supplier = module.policy()
    if supplier['version'] != pin()['toolchain']['cmake_version']:
        raise ValueError('The pinned build tool differs from the ASR version constraint.')
    return module


def verify_pinned_cmake(root, payload):
    """Reuse the common exact ZIP/tree verifier; no native execution or fallback."""
    if root is None:
        raise ValueError('The separate verified CMake container is required.')
    module = cmake_tool_module()
    receipt = module.verify(Path(root))
    if Path(payload).resolve() != module.payload_root(root).resolve():
        raise ValueError('The selected CMake payload is outside the verified container.')
    return receipt


def cmake_variant_sources(policy=None):
    value = (policy or pin())['cmake_module_variant']
    if (value['identity'] != CMAKE_VARIANT_IDENTITY or value['module_path'] != CMAKE_VARIANT_MODULE
            or value['license']['original_member'] != 'doc/cmake/LICENSE.rst'
            or any(value[key] is not False for key in ('runtime_collection_allowed', 'source_delivery_approved', 'rights_approval'))):
        raise ValueError('The separate CMake module variant identity or boundary differs.')
    sources = {}
    for key in ('before', 'after'):
        record = value[key]
        if (type(record) is not dict or set(record) != {'bytes', 'sha256'}
                or type(record['bytes']) is not int or not 0 < record['bytes'] <= 65536
                or not isinstance(record['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise ValueError('The exact CMake module input/output pin is invalid.')
    for key, name in zip(('patch', 'license', 'notice'), CMAKE_VARIANT_FILES):
        record = value[key]
        fields = {'path', 'bytes', 'sha256'} | ({'original_member'} if key == 'license' else set())
        if (type(record) is not dict or set(record) != fields or record['path'] != name
                or type(record['bytes']) is not int or not 0 < record['bytes'] <= 65536
                or not isinstance(record['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
            raise ValueError('The CMake module source/notice pin is invalid.')
        info = diagnostic_file_info(ROOT / name)
        if not stat.S_ISREG(info.st_mode) or info.st_size != record['bytes']:
            raise ValueError('The CMake module source/notice size differs.')
        data = (ROOT / name).read_bytes()
        if attributes(data) != {field: record[field] for field in ('bytes', 'sha256')}:
            raise ValueError('The CMake module source/notice bytes differ.')
        sources[key] = data
    return value, sources


def patched_cmake_module(original, variant, patch):
    if attributes(original) != variant['before'] or attributes(patch) != {
            field: variant['patch'][field] for field in ('bytes', 'sha256')}:
        raise ValueError('The original CMake module or exact patch differs.')
    lines = patch.splitlines(keepends=True)
    target = variant['module_path'].encode('ascii')
    if len(lines) < 4 or lines[:2] != [b'--- a/' + target + b'\n', b'+++ b/' + target + b'\n']:
        raise ValueError('Only the exact single CMake module patch is accepted.')
    header = re.fullmatch(rb'@@ -([1-9][0-9]{0,6}),([1-9][0-9]{0,6}) \+([1-9][0-9]{0,6}),([1-9][0-9]{0,6}) @@\n', lines[2])
    if not header or header[1] != header[3] or any(line[:1] not in (b' ', b'+', b'-') for line in lines[3:]):
        raise ValueError('The bounded CMake patch hunk differs.')
    old = [line[1:] for line in lines[3:] if line[:1] in (b' ', b'-')]
    new = [line[1:] for line in lines[3:] if line[:1] in (b' ', b'+')]
    source = original.splitlines(keepends=True); start = int(header[1]) - 1
    if len(old) != int(header[2]) or len(new) != int(header[4]) or source[start:start + len(old)] != old:
        raise ValueError('The CMake patch does not match its exact original context.')
    result = b''.join(source[:start] + new + source[start + len(old):])
    if attributes(result) != variant['after']:
        raise ValueError('The sole changed CMake module differs from its derived pin.')
    return result


def cmake_variant_plan(archive, tool=None):
    """Static ZIP/module inspection only; no native extraction or execution."""
    tool = tool or cmake_tool_module()
    supplier = tool.policy(); variant, sources = cmake_variant_sources()
    records, directories = tool.inspect_archive(Path(archive), supplier)
    member = supplier['archive']['root'] + '/' + variant['module_path']
    license_member = supplier['archive']['root'] + '/' + variant['license']['original_member']
    if (records.get(member) != variant['before'] or records.get(license_member) != {
            field: variant['license'][field] for field in ('bytes', 'sha256')}):
        raise ValueError('The original ZIP does not supply this module and complete license.')
    tool.no_links(archive)
    with zipfile.ZipFile(archive) as zipped:
        modified = patched_cmake_module(zipped.read(member), variant, sources['patch'])
        if zipped.read(license_member) != sources['license']:
            raise ValueError('The delivered original CMake license differs.')
    expected = dict(records); expected[member] = variant['after']
    summary = {'schema': 'proxy-r19-asr-cmake-module-variant-v1', 'identity': CMAKE_VARIANT_IDENTITY,
        'scope': 'ASR-build-host-only; initial-exact-tree; final-required-for-success',
        'module_path': CMAKE_VARIANT_MODULE, 'before': variant['before'], 'after': variant['after'],
        'patch': variant['patch'], 'license': variant['license'], 'notice': variant['notice'],
        'original_archive': {field: supplier['archive'][field] for field in ('bytes', 'sha256')},
        'unchanged_executable': {field: supplier['executable'][field] for field in ('bytes', 'sha256')},
        'regular_files': len(expected), 'directories': len(directories),
        'tree_sha256': sha(canonical({'files': expected, 'directories': sorted(directories)})),
        'runtime_collection_allowed': False, 'rights_approval': False, 'source_delivery_approved': False}
    return tool, supplier, expected, directories, member, modified, summary


def safe_cmake_variant_observation():
    value = _BUILD_CMAKE_VARIANT
    if not isinstance(value, dict):
        return None
    try:
        variant, _sources = cmake_variant_sources()
    except (ValueError, KeyError, OSError):
        return None
    diagnostic_file_info(ROOT / CMAKE_TOOL_POLICY)
    supplier = read_json(ROOT / CMAKE_TOOL_POLICY)
    expected = {'schema': 'proxy-r19-asr-cmake-module-variant-v1', 'identity': CMAKE_VARIANT_IDENTITY,
        'scope': 'ASR-build-host-only; initial-exact-tree; final-required-for-success',
        'module_path': CMAKE_VARIANT_MODULE, 'before': variant['before'], 'after': variant['after'],
        'patch': variant['patch'], 'license': variant['license'], 'notice': variant['notice'],
        'original_archive': {key: supplier['archive'][key] for key in ('bytes', 'sha256')},
        'unchanged_executable': {key: supplier['executable'][key] for key in ('bytes', 'sha256')},
        'runtime_collection_allowed': False, 'rights_approval': False, 'source_delivery_approved': False}
    if set(value) != set(expected) | {'tree_sha256', 'regular_files', 'directories'}:
        return None
    if any(value[key] != item for key, item in expected.items()):
        return None
    if (not isinstance(value['tree_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['tree_sha256'])
            or any(type(value[key]) is not int or not 0 < value[key] <= 12000 for key in ('regular_files', 'directories'))):
        return None
    return {**expected, **{key: value[key] for key in ('tree_sha256', 'regular_files', 'directories')}}


def separate_cmake_variant_roots(tool, original_root, variant_root):
    original_root, variant_root = Path(original_root).absolute(), Path(variant_root).absolute()
    tool.no_links(original_root); tool.no_links(variant_root)
    if (original_root == variant_root or original_root in variant_root.parents
            or variant_root in original_root.parents):
        raise ValueError('Official and derived CMake containers must be separate trees.')
    return original_root, variant_root


def verify_cmake_module_variant(original_root, variant_root):
    tool = cmake_tool_module(); supplier = tool.policy()
    original_root, variant_root = separate_cmake_variant_roots(tool, original_root, variant_root)
    tool.verify(Path(original_root))
    archive = Path(original_root) / 'inputs' / supplier['archive']['filename']
    tool, _supplier, files, directories, _member, _modified, summary = cmake_variant_plan(archive, tool)
    tool.no_links(variant_root)
    actual_files, actual_directories = tool.tree(Path(variant_root))
    if actual_files != files or actual_directories != directories:
        raise ValueError('The ASR CMake variant is not the exact single-module closed tree.')
    return summary


def prepare_cmake_module_variant(original_root, variant_root):
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise ValueError('The native module variant is materialized only on the Windows build host.')
    tool = cmake_tool_module(); supplier = tool.policy()
    original_root, variant_root = separate_cmake_variant_roots(tool, original_root, variant_root)
    tool.verify(Path(original_root))
    tool.no_links(variant_root)
    if Path(variant_root).exists():
        raise ValueError('The ASR CMake module variant requires a fresh private destination.')
    archive = Path(original_root) / 'inputs' / supplier['archive']['filename']
    tool, supplier, files, directories, member, modified, summary = cmake_variant_plan(archive, tool)
    Path(variant_root).mkdir(parents=True)
    tool.no_links(archive)
    with zipfile.ZipFile(archive) as zipped:
        for name in sorted(directories):
            path = Path(variant_root) / name; tool.no_links(path)
            path.mkdir(parents=True, exist_ok=True); tool.no_links(path)
        for name, expected in files.items():
            path = Path(variant_root) / name; tool.no_links(path)
            data = modified if name == member else zipped.read(name)
            if attributes(data) != expected:
                raise ValueError('CMake variant extraction differs from the exact pinned input.')
            with path.open('xb') as handle: handle.write(data)
    if verify_cmake_module_variant(original_root, variant_root) != summary:
        raise ValueError('The newly materialized CMake module variant differs.')
    return Path(variant_root) / supplier['archive']['root'], summary


def seal_toolchain(roots):
    """Hash exact bytes under explicitly selected tool roots; keep file list private."""
    validate_tool_roots(roots)
    values = {name: inventory(Path(path).absolute()) for name, path in sorted(roots.items())}
    if any(not files for files in values.values()):
        raise ValueError('An explicit toolchain root is empty.')
    return values


def toolchain_summary(value):
    return {name: {'sha256': sha(canonical(files)), 'file_count': len(files),
                   'bytes': sum(f['bytes'] for f in files.values())}
            for name, files in value.items()}


def python_files(archive):
    supplier = read_json(ROOT / pin()['python_supplier_manifest'])
    archive = Path(archive).absolute(); no_links(archive)
    return archive_files(archive, {'bytes': archive.stat().st_size,
        'sha256': supplier['sha256'], 'archive_root': 'python',
        'selected_prefixes': [], 'notices': {}})


def prepare_python(archive, output):
    """Extract only the exact existing supplier pin; not supplier approval."""
    output = Path(output).absolute(); no_links(output)
    if output.exists():
        raise ValueError('A fresh separate Python directory is required.')
    files = python_files(archive)
    for name, data in files.items():
        dest = output / 'python' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return output / 'python' / 'python.exe'


def verify_python(inputs, root):
    supplier = read_json(ROOT / pin()['python_supplier_manifest'])
    expected = {name: attributes(data) for name, data in python_files(Path(inputs) / supplier['archive']).items()}
    if inventory(Path(root)) != expected:
        raise ValueError('The actual build/probe Python differs from the exact supplier archive.')


def prepare_numpy(inputs, output):
    item = pin()['numpy']
    wheel = Path(inputs) / item['filename']
    no_links(wheel); no_links(output)
    if output.exists() or attributes(wheel.read_bytes()) != {'bytes': item['bytes'], 'sha256': item['sha256']}:
        raise ValueError('Exact separate NumPy probe dependency required.')
    files, aliases = {}, set()
    with zipfile.ZipFile(wheel) as archive:
        if (len(archive.infolist()) > 2000
                or sum(m.file_size for m in archive.infolist()) > 256 * 1024 * 1024):
            raise ValueError('NumPy probe wheel exceeds the bounded inventory.')
        for member in archive.infolist():
            name = safe_name(member.filename.rstrip('/'))
            if name.casefold() in aliases or member.file_size > 64 * 1024 * 1024:
                raise ValueError('Unsupported NumPy probe wheel inventory.')
            aliases.add(name.casefold())
            if member.is_dir():
                continue
            if stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG):
                raise ValueError('Non-regular NumPy probe wheel entry.')
            files[name] = archive.read(member)
    if sum(map(len, files.values())) > 256 * 1024 * 1024 or len(files) > 2000:
        raise ValueError('NumPy probe wheel exceeds the bounded inventory.')
    for name, data in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return inventory(output)


def pe_evidence(data):
    """Read normal/delay imports and named exports without executing native code."""
    def u16(p): return struct.unpack_from('<H', data, p)[0]
    def u32(p): return struct.unpack_from('<I', data, p)[0]
    def u64(p): return struct.unpack_from('<Q', data, p)[0]
    pe = u32(60)
    opt = pe + 24
    if data[:2] != b'MZ' or data[pe:pe + 4] != b'PE\0\0' or u16(pe + 4) != 0x8664 or u16(opt) != 0x20b:
        raise ValueError('An x64 PE32+ artifact is required.')
    sections = [(u32(opt + u16(pe + 20) + n * 40 + 12),
                 max(u32(opt + u16(pe + 20) + n * 40 + 8), u32(opt + u16(pe + 20) + n * 40 + 16)),
                 u32(opt + u16(pe + 20) + n * 40 + 20)) for n in range(u16(pe + 6))]
    def offset(rva):
        for va, size, raw in sections:
            if va <= rva < va + size and raw + rva - va < len(data):
                return raw + rva - va
        raise ValueError('Unmapped PE address.')
    def string(rva):
        start = offset(rva)
        end = data.index(0, start, min(len(data), start + 1024))
        result = data[start:end].decode('ascii')
        if any(ord(c) < 32 or ord(c) > 126 for c in result):
            raise ValueError('Invalid PE name.')
        return result
    result = {}
    for label, index, stride in [('imports', 1, 20), ('delay_imports', 13, 32)]:
        rva, size = u32(opt + 112 + index * 8), u32(opt + 116 + index * 8)
        names = []
        if rva:
            for n in range(min(size // stride, 256)):
                p = offset(rva) + n * stride
                if not any(data[p:p + stride]): break
                addr = u32(p + 12) if index == 1 else u32(p + 4) - (0 if u32(p) & 1 else u64(opt + 24))
                names.append(string(addr))
        result[label] = sorted(names)
    export_rva = u32(opt + 112)
    exports = []
    if export_rva:
        table = offset(export_rva)
        count = u32(table + 24)
        if count > 10000: raise ValueError('Unbounded PE export inventory.')
        names = offset(u32(table + 32))
        exports = [string(u32(names + n * 4)) for n in range(count)]
    result['exports'] = sorted(exports)
    return result


def native_tts_name(value):
    """Vendor/API identifiers, not the e+Speaker substring in OfflineSpeaker.

    Real inputs include espeak_/espeak_ng_ APIs, piper namespaces/library names,
    phonemize_eSpeak and the upstream PiperPhonemizeLexicon/PiperPhonemes names.
    The phonemiz stem intentionally covers their C++ and C identifier forms.
    """
    return bool(re.search(r'(?<![a-z0-9])(?:lib)?(?:espeak|piper)(?=$|[^a-z0-9])|phonemiz', value, re.I)
        or re.search(r'(?<![A-Za-z0-9])(?:Piper|eSpeak|ESpeak)(?=[A-Z])', value))


def validate_native(evidence):
    imports = evidence['imports'] + evidence['delay_imports']
    allowed = {'advapi32.dll', 'kernel32.dll', 'ntdll.dll', 'ole32.dll', 'oleaut32.dll',
        'user32.dll', 'ws2_32.dll', 'bcrypt.dll', 'crypt32.dll', 'secur32.dll',
        'shell32.dll', 'shlwapi.dll', 'version.dll', 'python312.dll', 'onnxruntime.dll'}
    if (not {'python312.dll', 'onnxruntime.dll'} <= {n.casefold() for n in imports}
            or any(n.casefold() not in allowed and not re.fullmatch(r'api-ms-win-[a-z0-9-]+\.dll', n.casefold()) for n in imports)
            or 'PyInit__sherpa_onnx' not in evidence['exports']
            or any(any(c in n for c in '/\\:') for n in imports + evidence['exports'])
            or any(native_tts_name(n) for n in imports + evidence['exports'])):
        raise ValueError('The isolated ASR binding native dependency/export scope differs.')


def make_wheel(output, pyd):
    policy = pin()
    source = output / 'sources/sherpa-onnx/sherpa-onnx/python/sherpa_onnx'
    target = output / 'candidate'
    target.mkdir()
    for path in source.rglob('*.py'):
        dest = target / 'sherpa_onnx' / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    init = target / 'sherpa_onnx/__init__.py'
    with init.open('a', encoding='utf-8') as f:
        f.write('\n# Separate unpublished reference identity; upstream Python sources retained.\n'
                '__version__ = "1.13.8+proxy.r19.asr1"\n')
    lib = target / 'sherpa_onnx/lib'
    lib.mkdir(exist_ok=True)
    shutil.copyfile(pyd, lib / pyd.name)
    shutil.copyfile(output / 'sources/onnxruntime/lib/onnxruntime.dll', lib / 'onnxruntime.dll')
    dist = target / 'proxy_r19_sherpa_asr_reference-1.13.8+proxy.r19.asr1.dist-info'
    dist.mkdir()
    (dist / 'WHEEL').write_text('Wheel-Version: 1.0\nGenerator: proxy-r19-private-reference\nRoot-Is-Purelib: false\nTag: cp312-cp312-win_amd64\n', encoding='utf-8')
    (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: proxy-r19-sherpa-asr-reference\nVersion: 1.13.8+proxy.r19.asr1\nSummary: Unapproved private TTS-disabled source experiment\nRequires-Dist: numpy==1.26.4\n', encoding='utf-8')
    shutil.copytree(output / 'notices', dist / 'notices')
    shutil.copyfile(ROOT / 'LICENSE', dist / 'notices/PROJECT-LICENSE.txt')
    shutil.copyfile(ROOT / policy['patch']['file'], dist / 'notices/TTS-OFF-MODIFICATION.patch')
    for name in policy['patch_notices']:
        shutil.copyfile(ROOT / name, dist / 'notices' / Path(name).name)
    record = io.StringIO(newline='')
    writer = csv.writer(record)
    for name in sorted(inventory(target)):
        data = (target / name).read_bytes()
        writer.writerow([name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('='), str(len(data))])
    writer.writerow([dist.name + '/RECORD', '', ''])
    (dist / 'RECORD').write_text(record.getvalue(), encoding='utf-8')
    wheel = output / 'private-wheelhouse/proxy_r19_sherpa_asr_reference-1.13.8+proxy.r19.asr1-cp312-cp312-win_amd64.whl'
    wheel.parent.mkdir()
    with zipfile.ZipFile(wheel, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(inventory(target)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (target / name).read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return wheel


def process_owner():
    spec = importlib.util.spec_from_file_location('asr_owned_windows_process', ROOT / 'backend/windows_preparation_process.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.WindowsPreparationProcess()


def run_private(command, log, env, cwd, timeout):
    # Existing stdlib bootstrap joins the retained kill-on-close Win32 job
    # before spawning. Timeout cleanup addresses only this owned subtree.
    owner, process = process_owner(), None
    try:
        with log.open('wb') as handle:
            try:
                process = subprocess.Popen(owner.command([str(v) for v in command]),
                    stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
                    cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
                code = process.wait(timeout=timeout)
            finally:
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                owner.terminate(timeout=10)
    finally:
        owner.close()
    if code:
        raise ValueError('A private ASR build/probe command failed.')


def cmake_failure_details(content):
    """Only fixed CMake error IDs and bounded known-command/line pairs leave logs."""
    headers = list(re.finditer(r'(?m)^CMake (Error|Warning|Deprecation Warning)\b', content))
    categories, sites = set(), set()
    for index, header in enumerate(headers):
        if header[1] != 'Error':
            continue
        block = content[header.start():headers[index + 1].start() if index + 1 < len(headers) else len(content)]
        folded = ' '.join(block.split())
        categories.update(label for label, pattern in CMAKE_EARLY_ERRORS if re.search(pattern, folded, re.I))
        site = re.match(r'^CMake Error(?: \((?:dev|deprecated)\))? at [^\r\n]{1,32768}:'
            r'([1-9][0-9]{0,6}) \(([^()\r\n]{1,64})\):', block)
        if site and site[2].casefold() in CMAKE_ERROR_COMMANDS:
            sites.add((site[2].casefold(), int(site[1])))
    return sorted(categories), [{'command': command, 'line': line} for command, line in sorted(sites)[:32]]


class CommonDataProbeError(ValueError):
    def __init__(self, reason, *, call_stage='not-observed', codes=()):
        self.reason = reason if reason in COMMON_DATA_REASONS else 'invalid-markers'
        self.call_stage = call_stage if type(call_stage) is str and call_stage in COMMON_DATA_CALL_STAGES else 'not-observed'
        self.codes = sorted({c for c in codes if type(c) is str and c in COMMON_DATA_MSB_CODES}) if type(codes) in (list, tuple) and len(codes) <= 3 else []
        super().__init__('The fixed common-data preflight was rejected.')


def common_data_directory(value):
    """Validate the private OS answer using metadata only, root before leaf."""
    if type(value) is not str or not 1 <= len(value) <= 32767 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('The OS common-data directory is unavailable.')
    raw = value.replace('\\', '/')
    parts = (raw[2:] if re.match(r'^[A-Za-z]:', raw) else raw).split('/')[1:]
    if (raw.startswith('//') or not parts or any(not p or p in {'.', '..'}
            or p.endswith((' ', '.')) or re.search(r'[<>:"|?*]', p)
            or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', p, re.I)
            for p in parts)):
        raise ValueError('The OS common-data directory is not canonical.')
    path = Path(value)
    if not path.is_absolute() or (os.name == 'nt' and not re.fullmatch(r'[A-Za-z]:', path.drive)):
        raise ValueError('A local absolute OS common-data directory is required.')
    if not stat.S_ISDIR(diagnostic_file_info(path).st_mode):
        raise ValueError('The OS common-data directory is not an existing directory.')
    return path


def query_common_data_directory():
    """Original typed Known Folder call; no creation or content enumeration."""
    import ctypes
    import uuid
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise ValueError('The Windows x64 Known Folder API is required.')
    class GUID(ctypes.Structure):
        _fields_ = [('data1', ctypes.c_uint32), ('data2', ctypes.c_uint16),
            ('data3', ctypes.c_uint16), ('data4', ctypes.c_ubyte * 8)]
    folder = GUID.from_buffer_copy(uuid.UUID('62ab5d82-fdc1-4dc3-a9dd-070d1d495d97').bytes_le)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    query = shell.SHGetKnownFolderPath
    query.argtypes = [ctypes.POINTER(GUID), ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    query.restype = ctypes.c_int32
    free = ole.CoTaskMemFree
    free.argtypes, free.restype = [ctypes.c_void_p], None
    pointer = ctypes.c_void_p()
    try:
        if query(ctypes.byref(folder), 0x4000, None, ctypes.byref(pointer)) != 0 or not pointer.value:
            raise ValueError('The OS common-data query failed.')
        return common_data_directory(ctypes.wstring_at(pointer))
    finally:
        if pointer.value:
            free(pointer)


def common_data_available(stream):
    if sys.platform != 'win32':  # Owned source-only pipe fixtures.
        import select
        return 4096 if select.select([stream], [], [], .01)[0] else 0
    import ctypes
    import msvcrt
    peek = ctypes.WinDLL('kernel32', use_last_error=True).PeekNamedPipe
    peek.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
    peek.restype = ctypes.c_int
    available = ctypes.c_uint32()
    if not peek(ctypes.c_void_p(msvcrt.get_osfhandle(stream.fileno())), None, 0, None,
            ctypes.byref(available), None):
        if ctypes.get_last_error() == 109:
            return None
        raise CommonDataProbeError('pipe-unavailable')
    return available.value


def capture_common_data(command, env, cwd):
    """One owned bootstrap, bounded merged output, then confirmed owned cleanup."""
    owner, process = process_owner(), None
    data = bytearray()
    deadline = time.monotonic() + COMMON_DATA_SECONDS
    try:
        process = subprocess.Popen(owner.command([str(v) for v in command]),
            cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        while True:
            if time.monotonic() >= deadline:
                raise CommonDataProbeError('deadline')
            available = common_data_available(process.stdout)
            if available is None or (available == 0 and process.poll() is not None):
                break
            if not available:
                time.sleep(.01)
                continue
            part = os.read(process.stdout.fileno(), min(4096, available, COMMON_DATA_BYTES + 1 - len(data)))
            if not part:
                break
            data.extend(part)
            if len(data) > COMMON_DATA_BYTES:
                raise CommonDataProbeError('output-limit')
        try:
            code = process.wait(timeout=max(.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise CommonDataProbeError('deadline') from None
    finally:
        # Cleanup uncertainty overrides an ordinary rejected baseline. No second
        # child may start while this bootstrap or its retained job is uncertain.
        uncertain = False
        if process is not None:
            try:
                live = process.poll() is None
            except BaseException:
                uncertain, live = True, True
            if live:
                try:
                    process.kill()
                except BaseException:
                    uncertain = True
            try:
                process.wait(timeout=5)
            except BaseException:
                uncertain = True
        try:
            owner.terminate(timeout=10)
        except BaseException:
            uncertain = True
        try:
            owner.close()
        except BaseException:
            uncertain = True
        try:
            if process is not None and process.stdout is not None:
                process.stdout.close()
        except BaseException:
            uncertain = True
        if uncertain:
            raise OSError('Common-data owned cleanup is unconfirmed.') from None
    return code, bytes(data)


def common_data_result(reason='not-run'):
    return {'status': 'not-run' if reason == 'not-run' else 'rejected', 'reason': reason,
        'runtime': 'unavailable', 'x64': None, 'folder': 'unavailable', 'root': 'not-run',
        'rooted': None, 'programdata_equal': None, 'allusersprofile_equal': None,
        'do_not_verify_call': 'not-run' if reason == 'not-run' else 'not-observed', 'msbuild_codes': [],
        'do_not_verify': {'empty': None, 'rooted': None, 'programdata_equal': None, 'allusersprofile_equal': None}}


def common_data_markers(code, data, *, project=None):
    if type(code) is not int or not 0 <= code <= 0xffffffff or type(data) is not bytes:
        raise CommonDataProbeError('invalid-markers')
    if len(data) > COMMON_DATA_BYTES:
        raise CommonDataProbeError('output-limit')
    try:
        text = data.decode('utf-8', errors='strict')
    except UnicodeError:
        raise CommonDataProbeError('invalid-utf8') from None
    if text.startswith('\ufeff'):
        text = text[1:]
    if (re.search(r'\r(?!\n)', text) or any(c in text for c in ('\x00', '\x85', '\u2028', '\u2029'))):
        raise CommonDataProbeError('invalid-markers')
    # Other MSBuild messages are discarded, never retained in an observation.
    lines = [line.removesuffix('\r').lstrip(' \t') for line in text.split('\n') if 'R19-ASR-COMMON' in line]
    # Only a fixed MSBUILD origin or this actual authored project can supply a
    # code. Unknown paths/messages/expressions are never searched for tokens.
    origins = ['MSBUILD']
    if (isinstance(project, Path) and project.is_absolute() and project.name == 'PRIVATE-COMMON-DATA.proj'
            and len(str(project)) <= 32767 and not any(c in str(project) for c in ('\r', '\n', '\x00'))):
        position = r'\([1-9][0-9]{0,6},[1-9][0-9]{0,6}(?:,[1-9][0-9]{0,6},[1-9][0-9]{0,6})?\)'
        origins.append(re.escape(str(project)) + position)
    header = re.compile(r'^[ \t]*(?:' + '|'.join(origins) + r')[ \t]*:[ \t]+error[ \t]+(MSB418[456]):(?:[ \t]|$)')
    codes = sorted({match[1] for line in text.split('\n') if (match := header.match(line.removesuffix('\r')))})
    folder = re.fullmatch(r'R19-ASR-COMMON-V1 folder;runtime=(Full|Core|Mono);x64=(True|False);empty=(True|False);programdata=(True|False);allusers=(True|False)', lines[0]) if lines else None
    returned = 'R19-ASR-COMMON-V1 do-not-verify-returned'
    stage = 'returned' if folder and len(lines) >= 2 and lines[1] == returned and lines.count(returned) == 1 else 'not-observed'
    unverified = re.fullmatch(r'R19-ASR-COMMON-V1 do-not-verify;empty=(True|False);rooted=(True|False);programdata=(True|False);allusers=(True|False)', lines[2]) if len(lines) >= 3 else None
    root = re.fullmatch(r'R19-ASR-COMMON-V1 root;empty=(True|False);rooted=(True|False)', lines[3]) if len(lines) == 4 else None
    if (not folder or len(lines) > 4 or (len(lines) >= 2 and stage != 'returned')
            or (len(lines) >= 3 and not unverified) or (len(lines) == 4 and not root) or (code == 0 and not root)):
        raise CommonDataProbeError('invalid-markers', call_stage=stage, codes=codes)
    value = common_data_result('none' if code == 0 else 'process-rejected')
    value.update(status='observed' if code == 0 else 'rejected', runtime=folder[1].lower(),
        x64=folder[2] == 'True', folder='empty' if folder[3] == 'True' else 'nonempty',
        programdata_equal=folder[4] == 'True', allusersprofile_equal=folder[5] == 'True',
        do_not_verify_call=stage, msbuild_codes=codes)
    if unverified:
        value['do_not_verify'] = dict(zip(('empty', 'rooted', 'programdata_equal', 'allusersprofile_equal'),
                                        (unverified[i] == 'True' for i in range(1, 5))))
    if root:
        value.update(root='empty' if root[1] == 'True' else 'nonempty', rooted=root[2] == 'True')
    return value


def safe_common_data_observation(value):
    if (type(value) is not dict or set(value) != {'origin', 'binding', 'origin_stable', 'baseline', 'bound'}
            or type(value['origin']) is not str or value['origin'] != 'FOLDERID_ProgramData'
            or type(value['binding']) is not str or value['binding'] != 'PROGRAMDATA+ALLUSERSPROFILE'
            or type(value['origin_stable']) is not str
            or value['origin_stable'] not in {'not-checked', 'verified', 'changed', 'unavailable'}):
        return None
    result = {k: value[k] for k in ('origin', 'binding', 'origin_stable')}
    enums = {'status': {'not-run', 'observed', 'rejected'}, 'reason': COMMON_DATA_REASONS,
        'runtime': {'unavailable', 'full', 'core', 'mono'}, 'folder': {'unavailable', 'empty', 'nonempty'},
        'root': {'not-run', 'empty', 'nonempty'}}
    for state in ('baseline', 'bound'):
        item = value[state]
        if type(item) is not dict or set(item) != set(common_data_result()):
            return None
        if any(type(item[k]) is not str or item[k] not in allowed for k, allowed in enums.items()):
            return None
        if any(item[k] is not None and type(item[k]) is not bool
                for k in ('x64', 'rooted', 'programdata_equal', 'allusersprofile_equal')):
            return None
        stage, codes = item['do_not_verify_call'], item['msbuild_codes']
        if (type(stage) is not str or stage not in COMMON_DATA_CALL_STAGES or type(codes) is not list
                or len(codes) > 3 or any(type(c) is not str or c not in COMMON_DATA_MSB_CODES for c in codes)
                or codes != sorted(set(codes))):
            return None
        unverified = item['do_not_verify']
        if (type(unverified) is not dict or set(unverified) != set(common_data_result()['do_not_verify'])
                or not (all(v is None for v in unverified.values())
                        or all(type(v) is bool for v in unverified.values()))):
            return None
        if ((all(type(v) is bool for v in unverified.values()) and stage != 'returned')
                or (item['status'] == 'not-run' and (stage != 'not-run' or codes))):
            return None
        result[state] = {**item, 'do_not_verify': dict(unverified), 'msbuild_codes': list(codes)}
    return result


def check_common_data_origin():
    if _BUILD_COMMON_DATA_PATH is None:
        return
    value = _BUILD_ENVIRONMENT_OBSERVATION['common_data']
    try:
        current = query_common_data_directory()
    except Exception:
        value['origin_stable'] = 'unavailable'
        raise ValueError('The OS common-data origin could not be reverified.') from None
    if current != _BUILD_COMMON_DATA_PATH:
        value['origin_stable'] = 'changed'
        raise ValueError('The OS common-data origin changed.')
    value['origin_stable'] = 'verified'


def common_data_environment(output, roots, initial, env):
    global _BUILD_COMMON_DATA_PATH
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE',
        'origin_stable': 'not-checked', 'baseline': common_data_result(), 'bound': common_data_result()}
    _BUILD_ENVIRONMENT_OBSERVATION['common_data'] = value
    build_phase('common-data-origin')
    try:
        _BUILD_COMMON_DATA_PATH = query_common_data_directory()
    except Exception:
        value['origin_stable'] = 'unavailable'
        raise ValueError('The OS common-data origin is unavailable.') from None
    member = 'Current/Bin/amd64/MSBuild.exe'
    executable = Path(roots['msbuild']) / member
    def verify_executable():
        state, data = diagnostic_file(executable, 64 * 1024 * 1024)
        if state != 'observed' or attributes(data) != initial['msbuild'].get(member):
            raise ValueError('The selected sealed x64 MSBuild executable differs.')
    verify_executable()
    diagnostic_file_info(output)
    project = output / 'PRIVATE-COMMON-DATA.proj'
    with project.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(COMMON_DATA_PROJECT)
    command = [executable, project, '/nologo', '/noautoresponse', '/nr:false', '/m:1', '/v:minimal']
    bound = {k: v for k, v in env.items() if k.casefold() not in {'programdata', 'allusersprofile'}}
    bound.update(PROGRAMDATA=str(_BUILD_COMMON_DATA_PATH), ALLUSERSPROFILE=str(_BUILD_COMMON_DATA_PATH))
    for name, child_env in (('baseline', env), ('bound', bound)):
        build_phase('common-data-' + name)
        check_common_data_origin()
        verify_executable()
        try:
            value[name] = common_data_markers(*capture_common_data(command, child_env, output), project=project)
        except CommonDataProbeError as error:
            value[name] = common_data_result(error.reason)
            value[name].update(do_not_verify_call=error.call_stage, msbuild_codes=list(error.codes))
        verify_executable()
        check_common_data_origin()
    observed = value['bound']
    if (observed['status'] != 'observed' or observed['runtime'] != 'full' or observed['x64'] is not True
            or observed['folder'] != 'nonempty' or observed['root'] != 'nonempty'
            or any(observed[k] is not True for k in ('rooted', 'programdata_equal', 'allusersprofile_equal'))):
        raise ValueError('The authoritative common-data binding was not observed by Full CLR x64 MSBuild.')
    return bound


def diagnostic_file_info(path):
    """Reject linked ancestors before requesting metadata from descendants."""
    path = Path(path).absolute()
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked diagnostic inputs are not inspected.')
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError('Diagnostic ancestors must be ordinary directories.')
    return info


def diagnostic_file(path, limit, *, tail=False):
    """Read a fixed private regular file only, with explicit byte limits."""
    try:
        info = diagnostic_file_info(path)
        if not stat.S_ISREG(info.st_mode):
            return 'not-regular', b''
        if not tail and info.st_size > limit:
            return 'size-limit', b''
        with path.open('rb') as handle:
            if tail:
                handle.seek(0, os.SEEK_END)
                handle.seek(max(0, handle.tell() - limit))
            data = handle.read(limit if tail else limit + 1)
        if not tail and len(data) > limit:
            return 'size-limit', b''
        return 'observed', data
    except FileNotFoundError:
        return 'missing', b''
    except (OSError, ValueError):
        return 'inspection-error', b''


def fixed_log_diagnostics(content):
    tokens = set(re.findall(r'\b(?:fatal\s+)?error\s+((?:C|D|LNK|MSB)[0-9]{4})\b', content, re.I))
    tokens = {token.upper() for token in tokens}
    categories = set()
    if any(t.startswith(('C', 'D', 'LNK')) for t in tokens): categories.add('compiler-or-linker-error')
    if any(t.startswith('MSB') for t in tokens): categories.add('msbuild-error')
    if tokens - KNOWN_BUILD_CODES: categories.add('unclassified-tool-error')
    if re.search(r'(?im)^CMake Error(?:\s|:)', content): categories.add('cmake-error')
    if re.search(r'Configuring incomplete, errors occurred', content, re.I): categories.add('cmake-configure-incomplete')
    if re.search(r'CMake Generate step failed', content, re.I): categories.add('cmake-generate-failed')
    if 'Native ASR reference probe failed;' in content: categories.add('native-probe-failed')
    if '[ONNXRuntimeError]' in content: categories.add('onnx-native-error')
    cmake_categories, cmake_sites = cmake_failure_details(content)
    categories.update(cmake_categories)
    result = {'known_codes': sorted(tokens & KNOWN_BUILD_CODES), 'categories': sorted(categories)}
    if cmake_sites:
        result['cmake_error_sites'] = cmake_sites
    return result


def known_log_diagnostics(output, phase):
    """Return fixed labels only; never serialize a line, match text or raw log."""
    if phase not in PHASE_LOGS:
        return {'known_codes': [], 'categories': []}
    state, data = diagnostic_file(output / 'private-logs' / PHASE_LOGS[phase], LOG_TAIL_BYTES, tail=True)
    if state != 'observed':
        return {'known_codes': [], 'categories': ['private-log-unavailable']}
    return fixed_log_diagnostics(data.decode('utf-8', errors='replace'))


def reviewed_toolset_version():
    value = pin()['toolchain']['vc_tools_version']
    return value if isinstance(value, str) and re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,6}){2}', value) else None


def private_instance_parts(instance):
    if not isinstance(instance, dict):
        return None
    argument, root, observed = (instance.get(key) for key in ('argument', 'root', 'observed_version'))
    if (not all(isinstance(item, str) and len(item) <= 32767
            and not any(ord(c) < 32 or ord(c) == 127 for c in item) for item in (argument, root, observed))
            or vs_instance_version(observed) != observed or not Path(root).is_absolute()
            or ',' in root or ';' in root or '..' in Path(root).parts):
        return None
    normalized = lambda item: re.sub(r'/+', '/', item.replace('\\', '/')).rstrip('/').casefold()
    if normalized(argument) != normalized(root) + ',version=' + observed:
        return None
    return argument, root


def diagnostic_normalized(value):
    return re.sub(r'/+', '/', value.replace('\\', '/')).rstrip('/').casefold()


def verified_instance_field(value, version, instance):
    parts = private_instance_parts(instance)
    if parts is None:
        return None
    argument, _root = parts
    suffix = '/Microsoft.VCToolsVersion.' + version + '.props'
    return diagnostic_normalized(value) in {diagnostic_normalized(argument + '/VC/Auxiliary/Build/' + version + suffix),
        diagnostic_normalized(argument + '/VC/Auxiliary/Build.' + version + suffix)}


def sealed_aux_mapping(alias, roots, initial_seal, instance, version, *, required_member=None):
    result = {'relationship': 'initial-seal-unavailable', 'matched_candidate_count': 0,
        'matches_policy': None, 'member_exists_state': 'not-inspected'}
    parts = private_instance_parts(instance)
    if parts is None or not isinstance(roots, dict):
        return result
    root = roots.get('vc-auxiliary')
    if (not isinstance(root, str) or len(root) > 32767
            or any(ord(c) < 32 or ord(c) == 127 for c in root)
            or not Path(root).is_absolute() or '..' in Path(root).parts
            or Path(os.path.abspath(root)) != Path(os.path.abspath(Path(parts[1]) / 'VC/Auxiliary'))):
        result['relationship'] = 'declared-root-mismatch'
        return result
    files = initial_seal.get('vc-auxiliary') if type(initial_seal) is dict else None
    if type(files) is not dict:
        return result
    if len(files) > AUX_SEAL_ENTRY_LIMIT:
        result['relationship'] = 'initial-seal-limit'
        return result
    candidates, byte_count = [], 0
    pattern = r'Build(?:/|\.)([0-9]{1,6}(?:\.[0-9]{1,6}){1,3})/Microsoft\.VCToolsVersion\.\1\.txt'
    for name, expected in files.items():
        if not isinstance(name, str) or len(name) > 32767:
            result['relationship'] = 'invalid-initial-seal'
            return result
        match = re.fullmatch(pattern, name)
        if not match or match[1] != alias:
            continue
        if required_member is not None and diagnostic_normalized(name[:-4] + '.props') != required_member:
            continue
        if len(candidates) >= AUX_MAPPING_CANDIDATE_LIMIT:
            result['relationship'] = 'candidate-limit'
            return result
        props_name = name[:-4] + '.props'
        pair = ((name, expected), (props_name, files.get(props_name)))
        for _member, record in pair:
            if (type(record) is not dict or set(record) != {'bytes', 'sha256'}
                    or type(record['bytes']) is not int or not 0 < record['bytes'] <= AUX_MAPPING_FILE_BYTES
                    or not isinstance(record['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
                result['relationship'] = 'incomplete-or-unbounded-sealed-pair'
                return result
            # Include the diagnostic reader's one-byte growth check.
            byte_count += record['bytes'] + 1
        if byte_count > AUX_MAPPING_TOTAL_BYTES:
            result['relationship'] = 'byte-limit'
            return result
        candidates.append(pair)
    if not candidates:
        result['relationship'] = 'no-sealed-alias-candidate'
        return result
    matched = 0
    for pair in candidates:
        content = []
        for member, expected in pair:
            state, data = diagnostic_file(Path(root) / member, expected['bytes'])
            if state != 'observed':
                result.update(relationship='sealed-member-changed' if state == 'size-limit' else 'unavailable-sealed-member',
                    member_exists_state=state)
                return result
            if attributes(data) != expected:
                result.update(relationship='sealed-member-changed', member_exists_state='regular-member-observed')
                return result
            content.append(data)
        if content[0].split(b'\n', 1)[0].removesuffix(b'\r') == version.encode('ascii'):
            matched += 1
    result.update(relationship=('verified-toolset-alias' if matched == 1 else
        'ambiguous-toolset-alias' if matched > 1 else 'different-policy-version'),
        matched_candidate_count=matched, matches_policy=matched > 0, member_exists_state='regular-files-present')
    return result


def mapped_aux_import(value, roots, initial_seal, instance, version):
    parts = private_instance_parts(instance)
    if parts is None:
        return None
    normalized = diagnostic_normalized(value)
    for contains_version, base in ((True, parts[0]), (False, parts[1])):
        prefix = diagnostic_normalized(base) + '/vc/auxiliary/'
        pattern = re.escape(prefix) + r'build(?:/|\.)([0-9]{1,6}(?:\.[0-9]{1,6}){1,3})/microsoft\.vctoolsversion\.\1\.props'
        match = re.fullmatch(pattern, normalized)
        if not match or not match[1].startswith('.'.join(version.split('.')[:2])):
            continue
        mapping = sealed_aux_mapping(match[1], roots, initial_seal, instance, version,
            required_member=None if contains_version else normalized[len(prefix):])
        role, existence = 'outside-declared-roots', 'not-inspected'
        if not contains_version:
            role = ('not-inspected' if mapping['relationship'] == 'initial-seal-unavailable' else
                'outside-declared-roots' if mapping['relationship'] == 'declared-root-mismatch' else 'declared-vc-auxiliary')
            existence = {'regular-files-present': 'regular-file-present', 'missing': 'missing',
                'inspection-error': 'inspection-error', 'not-regular': 'nonregular'}.get(mapping['member_exists_state'], 'not-inspected')
        return {'import_label': 'mapped-toolset-version-template', 'reviewed_version': version,
            'contains_verified_instance_version_field': contains_version, 'root_role': role,
            'existence': existence, 'toolset_mapping': mapping}
    return None


def import_target_context(value, roots, properties, *, instance=None, initial_seal=None, allow_vctargets_prefix=False):
    result = {'import_label': 'unknown-import', 'reviewed_version': None,
        'contains_verified_instance_version_field': None, 'root_role': 'not-inspected', 'existence': 'not-inspected',
        'toolset_mapping': None}
    if (not isinstance(value, str) or len(value) > 32767
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return result
    leaf = re.split(r'[/\\]', value)[-1].casefold()
    version = reviewed_toolset_version()
    mapped = mapped_aux_import(value, roots, initial_seal, instance, version) if version else None
    if mapped is not None:
        return mapped
    if leaf in PRIMARY_IMPORT_LEAVES:
        result['import_label'] = PRIMARY_IMPORT_LEAVES[leaf]
    elif version and leaf == ('Microsoft.VCToolsVersion.' + version + '.props').casefold():
        result.update(import_label='microsoft-vctools-version-props', reviewed_version=version,
            contains_verified_instance_version_field=verified_instance_field(value, version, instance))
    else:
        return result
    if '$' in value or '%(' in value or '@(' in value:
        result['existence'] = 'unexpanded-template'
        match = re.fullmatch(r'\$\(VCTargetsPath\)[\\/](Microsoft\.Cpp\.(?:Default\.props|props|targets))', value)
        base = properties.get('VCTargetsPath') if isinstance(properties, dict) else None
        if (not allow_vctargets_prefix or not match or not isinstance(base, str) or len(base) > 32767
                or any(ord(c) < 32 or ord(c) == 127 for c in base)
                or not Path(base).is_absolute() or '..' in Path(base).parts):
            return result
        value = str(Path(base) / match[1])
        result['existence'] = 'not-inspected'
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or not isinstance(roots, dict):
        return result
    path = Path(os.path.abspath(path))
    candidates = [('declared-' + role, roots.get(role)) for role in
        ('msbuild', 'vc-auxiliary', 'vc', 'sdk-include', 'sdk-lib', 'sdk-bin',
         'netfx-include', 'netfx-lib', 'cmake', 'python')]
    for role, base in candidates:
        if (isinstance(base, str) and len(base) <= 32767
                and not any(ord(c) < 32 or ord(c) == 127 for c in base)
                and Path(base).is_absolute() and path.is_relative_to(Path(os.path.abspath(base)))):
            result['root_role'] = role
            selected = properties.get('VCTargetsPath') if isinstance(properties, dict) else None
            if (role == 'declared-msbuild' and isinstance(selected, str) and len(selected) <= 32767
                    and not any(ord(c) < 32 or ord(c) == 127 for c in selected)
                    and Path(selected).is_absolute()):
                selected = Path(os.path.abspath(selected))
                if selected.is_relative_to(Path(os.path.abspath(base))) and path.is_relative_to(selected):
                    result['root_role'] = 'selected-vc-targets'
            try:
                info = diagnostic_file_info(path)
                result['existence'] = 'regular-file-present' if stat.S_ISREG(info.st_mode) else 'nonregular'
            except FileNotFoundError:
                result['existence'] = 'missing'
            except (OSError, ValueError):
                result['existence'] = 'inspection-error'
            return result
    result['root_role'] = 'outside-declared-roots'
    return result


def import_caller_context(prefix):
    result = {'file_label': 'unknown-caller', 'line': None, 'column': None}
    match = re.fullmatch(r'([^\r\n]{1,32767})\(([1-9][0-9]{0,6})(?:,([1-9][0-9]{0,6}))?\):\s*', prefix)
    if match:
        leaf = re.split(r'[/\\]', match[1])[-1].strip().casefold()
        if leaf in PRIMARY_IMPORT_CALLERS:
            result = {'file_label': PRIMARY_IMPORT_CALLERS[leaf], 'line': int(match[2]),
                'column': int(match[3]) if match[3] else None}
    return result


def msb4019_import_context(content, roots, properties, limit):
    records, truncated = [], False
    pattern = r'\berror\s+MSB4019:\s*(?:The imported project "([^"\r\n]{1,32767})" was not found\.)?'
    for index, match in enumerate(re.finditer(pattern, content, re.I)):
        if index >= limit:
            truncated = True
            break
        record = import_target_context(match[1], roots, properties, instance=_BUILD_INSTANCE,
            initial_seal=_BUILD_TOOLCHAIN_SEAL)
        record['literal_match_state'] = 'matched-import-template' if match[1] is not None else 'unrecognized-template'
        start = max(content.rfind('\n', 0, match.start()) + 1, match.start() - 32767)
        record['caller'] = import_caller_context(content[start:match.start()])
        records.append(record)
    return {'records': records, 'truncated': truncated}


def msb4018_line_body(line):
    """Linear header extraction; leading whitespace cannot backtrack as a prefix."""
    if '\r' in line:
        return None
    line = line.lstrip(' \t')
    node = re.match(r'[0-9]{1,6}>', line)
    if node is not None:
        line = line[node.end():].lstrip(' \t')
    marker = re.search(r'\berror[ \t]+MSB4018:[ \t]*', line, re.I)
    if marker is None:
        return None
    prefix = line[:marker.start()].rstrip(' \t')
    if prefix and (len(prefix) > 32768 or not prefix.endswith(':')):
        return None
    return line[marker.end():]


def msb4018_exception_header(body):
    match = re.match(r'([A-Za-z_][A-Za-z0-9_.]{0,254})'
        r'(?:[ \t]+\((0x[0-9a-fA-F]{8})\))?:', body)
    return match if match is not None and match[1].endswith('Exception') else None


def msb4018_undecorated(value):
    index = value.rfind(' [')
    if (index >= 0 and value.endswith(']') and len(value) - index <= 2050
            and not any(ord(c) < 32 or ord(c) == 127 for c in value[index:])):
        value = value[:index]
    return value


def msb4018_argument_message(value):
    if not value.startswith(' '):
        return None  # Exception.ToString adds exactly this separator before Message.
    value = msb4018_undecorated(value[1:])
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    if value in ARGUMENT_MESSAGES:
        return ARGUMENT_MESSAGES[value]
    opaque = r"[^'\x00-\x1f\x7f]{0,256}"
    if re.fullmatch(r"Item has already been added\. Key in dictionary: '" + opaque +
            r"'  Key being added: '" + opaque + "'", value):
        return 'dictionary-duplicate'
    if re.fullmatch(r'Illegal enum value: -?[0-9]{1,10}\.', value):
        return 'enum-invalid'
    return None


def msb4018_argument_close(public, private):
    """Do not resume a resource/stack observation across an unknown continuation."""
    if not private['active']:
        return
    public['state'] = 'incomplete'
    if not private['stack_started']:
        public.update(resource_state='unknown', resource_label=None)
    private.update(active=False, parameter_open=False)


def msb4018_argument_line(body, public, private):
    if not private['active']:
        return
    if private['parameter_open'] and body.startswith('Parameter name'):
        private['parameter_count'] += 1
        value = msb4018_undecorated(body[len('Parameter name: '):]) if body.startswith('Parameter name: ') else ''
        role = ARGUMENT_PARAMETERS.get(value)
        state = 'known-role' if role else ('unknown' if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value) else 'malformed')
        if private['parameter_count'] > 1:
            state, role = 'ambiguous', None
        public.update(parameter_state=state, parameter_role=role)
        if state in {'malformed', 'ambiguous'}:
            msb4018_argument_close(public, private)
        return
    private['parameter_open'] = False
    if msb4018_undecorated(body) == '--- End of inner exception stack trace ---':
        private.update(section='wrapper-context', stack_started=True)
        return
    if not body.startswith('at '):
        msb4018_argument_close(public, private)
        return
    if private['frame_count'] >= MSB4018_FRAME_LIMIT:
        public['frames_truncated'] = True
        return
    private['frame_count'] += 1
    name, separator, rest = body[3:].partition('(')
    signature, closing, trailer = rest.partition(')')
    role = ARGUMENT_FRAME_ROLES.get(name)
    if (not separator or not closing or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.`+]{0,255}', name)
            or len(signature) > 1024 or len(trailer) > 2048
            or any(ord(c) < 32 or ord(c) == 127 for c in name + signature + trailer)
            or (trailer and not trailer.startswith(' in ') and msb4018_undecorated('frame' + trailer) != 'frame')):
        public['unknown_frame_seen'] = True
        msb4018_argument_close(public, private)
        return
    private['stack_started'] = True
    if role is None:
        public['unknown_frame_seen'] = True
    else:
        public['framework_frames'].append({'section': private['section'], 'role': role})


def msb4018_inner_chain(body, chain, pending, argument=None, private=None):
    """Recognize the standard TypeInitializationException wrapper, not message prose."""
    if pending == 'marker':
        if not body.startswith('---> '):
            return None
        body = body[5:]
    elif pending != 'header':
        if chain['state'] != 'not-observed':
            return None
        first = msb4018_exception_header(body)
        if first is None or first[1] != 'System.TypeInitializationException':
            return None
    while True:
        header = msb4018_exception_header(body)
        if header is None:
            chain['state'] = 'malformed-inner-header'
            return None
        if len(chain['families']) >= MSB4018_CHAIN_DEPTH:
            chain.update(state='depth-limit', truncated=True)
            return None
        family = DOTNET_EXCEPTION_LABELS.get(header[1], 'unknown-exception')
        chain['families'].append(family)
        chain['state'] = 'outer-only' if len(chain['families']) == 1 else 'observed-inner'
        if family == 'unknown-exception':
            chain['state'] = 'unknown-inner'
            return None
        if header[1] == 'System.ArgumentException' and argument is not None:
            label = msb4018_argument_message(body[header.end():])
            argument.update(state='observed', resource_state='matched' if label else 'unknown',
                resource_label=label, initializer_roles=list(private['initializers']),
                unknown_initializer_seen=private['unknown_initializer'])
            private.update(active=True, parameter_open=True)
        if header[1] != 'System.TypeInitializationException':
            return None  # Arbitrary leaf messages cannot introduce a causal link.
        wrapper_body = body[header.end():].lstrip(' \t')
        wrapper = re.match(r"The type initializer for '([^'\r\n\x00-\x1f\x7f]{1,512})' threw an exception\.", wrapper_body)
        if wrapper is None:
            chain['state'] = 'unrecognized-wrapper'
            return None
        if private is not None:
            if wrapper[1] == 'Microsoft.Build.Utilities.FileTracker':
                private['initializers'].append('file-tracker')
            else:
                private['unknown_initializer'] = True
        remainder = wrapper_body[wrapper.end():]
        # MSBuild can append its private project decoration to each output line.
        if not remainder.strip() or re.fullmatch(r'[ \t]+\[[^\r\n]{0,32767}\][ \t]*', remainder):
            chain['state'] = 'inner-not-observed'
            return 'marker'
        if not remainder.startswith(' ---> '):
            chain['state'] = 'malformed-inner-marker'
            return None
        body = remainder[6:]
        if not body.strip() or re.fullmatch(r'\[[^\r\n]{0,32767}\][ \t]*', body):
            chain['state'] = 'malformed-inner-header'
            return 'header'


def msb4018_task_context(content, limit, *, discard_first_line=False):
    """Fixed observations from contiguous MSB4018 lines, never exception text."""
    if discard_first_line:
        content = content.partition('\n')[2]
    records, truncated, current, joining_bytes, block_bytes, chain_pending, argument_private = [], False, None, 0, 0, None, None
    lines = content.split('\n')
    for index, raw_line in enumerate(lines):
        if index == len(lines) - 1 and raw_line == '':
            break  # A terminal line ending is not a new, empty message body.
        line = raw_line.removesuffix('\r')
        body = msb4018_line_body(line)
        if body is None:
            if current is not None:
                msb4018_argument_close(current['argument_context'], argument_private)
            current, joining_bytes, chain_pending = None, 0, None
            continue
        task = re.fullmatch(r'The "([^"\r\n]{1,256})" task failed unexpectedly\.'
            r'(?:[ \t]+\[[^\r\n]{0,32767}\])?[ \t]*', body)
        if current is None or task is not None:
            if len(records) >= limit:
                truncated = True
                break
            current = {'literal_match_state': 'unrecognized-template', 'task_label': 'unknown-task',
                'exception_families': [], 'hresult_labels': [], 'win32_labels': [], 'context_truncated': False,
                'exception_chain': {'state': 'not-observed', 'families': [], 'truncated': False},
                'argument_context': {'state': 'not-observed', 'resource_state': 'not-observed', 'resource_label': None,
                    'parameter_state': 'not-observed', 'parameter_role': None, 'initializer_roles': [],
                    'unknown_initializer_seen': False, 'framework_frames': [], 'unknown_frame_seen': False,
                    'frames_truncated': False}}
            records.append(current)
            block_bytes, chain_pending = 0, None
            argument_private = {'initializers': [], 'unknown_initializer': False, 'active': False,
                'parameter_open': False, 'parameter_count': 0, 'section': 'argument-inner', 'frame_count': 0,
                'stack_started': False}
        else:
            block_bytes += joining_bytes
        block_bytes += len(line.encode('utf-8'))
        joining_bytes = 1 + len(raw_line) - len(line)  # Connecting LF or CRLF, not the next block's gap.
        if block_bytes > MSB4018_BLOCK_BYTES:
            current['context_truncated'] = True
            current['exception_chain'].update(state='byte-limit', truncated=True)
            current['argument_context']['state'] = 'byte-limit'
            chain_pending = None
            continue
        if task is not None:
            current.update(literal_match_state='matched-task-template',
                task_label=MSBUILD_TASK_LABELS.get(task[1].casefold(), 'unknown-task'))
        msb4018_argument_line(body, current['argument_context'], argument_private)
        chain_pending = msb4018_inner_chain(body, current['exception_chain'], chain_pending,
            current['argument_context'], argument_private)
        current['exception_families'] = sorted(set(current['exception_families']) | set(current['exception_chain']['families']))
        exception = msb4018_exception_header(body[5:] if body.startswith('---> ') else body)
        if exception is None:
            continue  # Stack frames, messages, parameters and arbitrary lines stay private.
        family = DOTNET_EXCEPTION_LABELS.get(exception[1], 'unknown-exception')
        current['exception_families'] = sorted(set(current['exception_families']) | {family})
        hresults = re.findall(r'\(Exception from HRESULT:[ \t]*(0x[0-9a-fA-F]{8})\)', body)
        if exception[2] is not None:
            hresults.append(exception[2])
        current['hresult_labels'] = sorted(set(current['hresult_labels']) |
            {HRESULT_LABELS.get(value.casefold(), 'unknown-hresult') for value in hresults})
        native_codes = re.findall(r'\b(?:NativeErrorCode|Win32 error)[ \t]*:[ \t]*'
            r'([0-9]{1,10})(?![0-9A-Za-z_.])', body)
        current['win32_labels'] = sorted(set(current['win32_labels']) |
            {WIN32_ERROR_LABELS.get(value, 'unknown-win32-error') for value in native_codes})
    return {'records': records, 'truncated': truncated}


def nested_configure_log_context(output):
    remaining, record_remaining, result = NESTED_LOG_TOTAL_BYTES, IMPORT_CONTEXT_LIMIT, []
    for origin, filename in (('cmake-configure-events', 'CMakeConfigureLog.yaml'),
            ('cmake-error-log', 'CMakeError.log')):
        row = {'origin': origin, 'state': 'total-byte-limit', 'known_codes': [], 'context_labels': [],
            'msb4019_imports': {'records': [], 'truncated': False},
            'msb4018_tasks': {'records': [], 'truncated': False}}
        if remaining > 0:
            read_limit = min(LOG_TAIL_BYTES, remaining)
            state, data = diagnostic_file(output / 'build/CMakeFiles' / filename,
                read_limit, tail=True)
            remaining -= len(data)
            row['state'] = state
            if state == 'observed':
                content = data.decode('utf-8', errors='replace')
                fixed = fixed_log_diagnostics(content)
                # Expected failed compiler probes may appear in these logs.
                # Their literal observations are context, never a fatal cause.
                folded = ' '.join(content.split())
                labels = {label for label, pattern in CMAKE_EARLY_ERRORS if re.search(pattern, folded, re.I)}
                row['known_codes'] = fixed['known_codes']
                row['context_labels'] = sorted(labels | set(fixed['categories']))
                row['msb4019_imports'] = msb4019_import_context(content, _BUILD_TOOL_ROOTS,
                    _BUILD_PROPERTIES, record_remaining)
                record_remaining -= len(row['msb4019_imports']['records'])
                # A full tail may start inside a private line. Conservatively
                # discard its first line for task/exception literal extraction.
                row['msb4018_tasks'] = msb4018_task_context(content, record_remaining,
                    discard_first_line=len(data) == read_limit)
                record_remaining -= len(row['msb4018_tasks']['records'])
        result.append(row)
    return {'evidence_scope': 'observed-context-not-fatal-cause', 'logs': result}


def compiler_path_state(value, language, roots):
    if value is None:
        return 'missing-entry'
    if not isinstance(value, str):
        return 'invalid-value'
    if value in {'NOTFOUND', 'CMAKE_' + language + '_COMPILER-NOTFOUND'}:
        return 'not-found'
    if value == '':
        return 'empty'
    if len(value) > 32767 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return 'invalid-value'
    path = Path(value)
    if not path.is_absolute():
        return 'not-absolute'
    if not isinstance(roots, dict):
        return 'roots-unavailable'
    # Normalize lexically before checking scope. Outside paths are never read,
    # statted or hashed, including paths containing parent traversals.
    path = Path(os.path.abspath(path))
    origin = None
    for role, label in (('vc', 'sealed-vc-toolset'), ('sdk-bin', 'sealed-sdk-bin')):
        base = roots.get(role)
        if isinstance(base, str) and Path(base).is_absolute() and path.is_relative_to(Path(os.path.abspath(base))):
            origin = label
            break
    if origin is None:
        return 'outside-declared-roots'
    try:
        return origin if stat.S_ISREG(diagnostic_file_info(path).st_mode) else 'not-regular'
    except FileNotFoundError:
        return 'missing-file'
    except (OSError, ValueError):
        return 'inspection-error'


def compiler_variables(data, language, *, cache=False):
    keys = {'CMAKE_' + language + '_COMPILER' + suffix for suffix in ('', '_ID', '_VERSION')}
    values = {}
    pattern = r'([^#/:][^:]*):[^=]+=(.*)' if cache else r'set\((CMAKE_[A-Z_]+) "([^"\r\n]*)"\)'
    for line in data.decode('utf-8', errors='replace').splitlines():
        match = re.fullmatch(pattern, line)
        if match and match[1] in keys:
            if match[1] in values:
                return None
            values[match[1]] = match[2]
    return values


def compiler_detection_context(output, roots):
    cache_state, cache_data = diagnostic_file(output / 'build/CMakeCache.txt', COMPILER_CONTEXT_FILE_BYTES)
    version = numeric_version(pin()['toolchain']['cmake_version'])
    rows = []
    for language in ('C', 'CXX', 'RC'):
        row = {'language': language}
        configuration_state, configuration_data = ('unavailable', b'')
        if version is not None:
            configuration_state, configuration_data = diagnostic_file(
                output / 'build/CMakeFiles' / version / ('CMake' + language + 'Compiler.cmake'),
                COMPILER_CONTEXT_FILE_BYTES)
        for source, state, data in (('cache', cache_state, cache_data),
                ('configuration', configuration_state, configuration_data)):
            values = compiler_variables(data, language, cache=source == 'cache') if state == 'observed' else {}
            entry = {'state': 'duplicate-entry' if values is None else state,
                'compiler_state': 'unavailable', 'compiler_id': None, 'compiler_version': None}
            if state == 'observed' and values is not None:
                key = 'CMAKE_' + language + '_COMPILER'
                entry['compiler_state'] = compiler_path_state(values.get(key), language, roots)
                identity, observed_version = values.get(key + '_ID'), values.get(key + '_VERSION')
                if identity in KNOWN_COMPILER_IDS:
                    entry['compiler_id'] = identity
                if isinstance(observed_version, str) and re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,6}){1,3}', observed_version):
                    entry['compiler_version'] = observed_version
            row[source] = entry
        rows.append(row)
    return {'evidence_scope': 'compiler-file-observation-not-native-approval', 'languages': rows}


def compiler_id_globals_context(output, properties, roots=None, instance=None, initial_seal=None):
    namespace = '{http://schemas.microsoft.com/developer/msbuild/2003}'
    rows, imports_remaining = [], COMPILER_ID_IMPORT_LIMIT
    for language in ('C', 'CXX'):
        path = output / 'build/CMakeFiles/4.4.5' / ('CompilerId' + language) / ('CompilerId' + language + '.vcxproj')
        state, data = diagnostic_file(path, COMPILER_CONTEXT_FILE_BYTES)
        row = {'language': language, 'state': state, 'imports': [], 'imports_truncated': False, 'properties': [
            {'property': name, 'state': 'unavailable'} for name in COMPILER_ID_PROPERTIES]}
        if state == 'observed':
            try:
                text = data.decode('utf-8-sig')
                if '<!' in text or '&' in text or '\0' in text:
                    raise ValueError('Diagnostic XML declarations/entities are not accepted.')
                tree = ET.fromstring(text)
                if tree.tag != namespace + 'Project' or sum(1 for _ in tree.iter()) > 4096:
                    raise ValueError('Diagnostic XML has an unsupported shape.')
                groups = [item for item in tree if item.tag == namespace + 'PropertyGroup'
                    and item.get('Label') == 'Globals']
                if len(groups) != 1 or 'Condition' in groups[0].attrib:
                    row['state'] = 'missing-globals' if not groups else 'ambiguous-globals'
                else:
                    for entry in row['properties']:
                        name = entry['property']
                        found = [item for item in groups[0] if item.tag == namespace + name]
                        if not found:
                            entry['state'] = 'missing'
                        elif len(found) != 1:
                            entry['state'] = 'duplicate-property'
                        elif len(found[0]) or found[0].attrib:
                            entry['state'] = 'structured-or-conditional-property'
                        elif not isinstance(properties, dict) or not isinstance(properties.get(name), str):
                            entry['state'] = 'expected-unavailable'
                        else:
                            entry['state'] = 'exact-match' if found[0].text == properties[name] else 'different'
                vctargets_matched = any(entry['property'] == 'VCTargetsPath' and entry['state'] == 'exact-match'
                    for entry in row['properties'])
                for item in tree.iter(namespace + 'Import'):
                    if imports_remaining <= 0:
                        row['imports_truncated'] = True
                        break
                    record = import_target_context(item.get('Project'), roots, properties,
                        instance=instance, initial_seal=initial_seal, allow_vctargets_prefix=vctargets_matched)
                    record['conditional'] = 'Condition' in item.attrib
                    row['imports'].append(record)
                    imports_remaining -= 1
            except (UnicodeError, ET.ParseError, ValueError):
                row['state'] = 'unsupported-xml'
        rows.append(row)
    return {'evidence_scope': 'observed-context-not-fatal-cause', 'projects': rows}


def failed_build_receipt(output, phase, error):
    """Write only to this prepared attempt; a failure is never an ASR success."""
    output = Path(output).absolute()
    if phase not in BUILD_PHASES:
        raise ValueError('Unknown private ASR build phase.')
    no_links(output)
    policy = pin()
    prepared = read_json(output / 'PREPARED.json')
    if (prepared.get('schema') != policy['schema'] or prepared.get('identity') != policy['identity']
            or prepared.get('gates') != policy['gates']):
        raise ValueError('Failure diagnostics require this explicit prepared ASR attempt.')
    if isinstance(error, subprocess.TimeoutExpired):
        category = 'owned-process-timeout'
    elif isinstance(error, OSError):
        category = 'io-or-cleanup-unconfirmed'
    elif isinstance(error, subprocess.SubprocessError) or phase in PHASE_LOGS:
        category = 'private-command-failed'
    elif isinstance(error, (ValueError, KeyError, struct.error)):
        category = 'input-or-output-validation-rejected'
    else:
        category = 'unexpected-operation-failed'
    # Do not serialize exception text, command args, environment, model output,
    # source/tool paths, private log names or unrecognized compiler tokens.
    receipt = {'schema': 'proxy-r19-asr-source-failure-v1', 'identity': policy['identity'],
        'status': 'failed', 'phase': phase, 'failure_category': category,
        'diagnostics': known_log_diagnostics(output, phase),
        'cmake_observation': safe_cmake_observation(),
        'cmake_module_variant_observation': safe_cmake_variant_observation(),
        'visual_studio_instance_version': vs_instance_version(_BUILD_VS_VERSION),
        'compiler_detection_context': compiler_detection_context(output, _BUILD_TOOL_ROOTS)
            if phase == 'cmake-configure' else None,
        'compiler_id_globals_context': compiler_id_globals_context(output, _BUILD_PROPERTIES,
            _BUILD_TOOL_ROOTS, _BUILD_INSTANCE, _BUILD_TOOLCHAIN_SEAL)
            if phase == 'cmake-configure' else None,
        'nested_configure_log_context': nested_configure_log_context(output)
            if phase == 'cmake-configure' else None,
        'build_environment_observation': safe_build_environment_observation(),
        'source_commit': _BUILD_SOURCE_COMMIT if isinstance(_BUILD_SOURCE_COMMIT, str)
            and re.fullmatch('[0-9a-f]{40}', _BUILD_SOURCE_COMMIT) else None,
        'manifest_sha256': sha((ROOT / MANIFEST).read_bytes()),
        'native_reference_probes_passed': False, 'success_receipt_for_this_attempt': False,
        'rights_approval': False, 'gates': policy['gates']}
    path = output / 'ASR-FAILURE.json'; no_links(path)
    # A retry must choose a fresh attempt; preserve any previous failure record.
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return receipt


def publish_success_receipt(output, receipt):
    policy = pin()
    if (receipt.get('schema') != policy['schema'] or receipt.get('identity') != policy['identity']
            or receipt.get('status') != 'native-reference-probes-passed'
            or receipt.get('gates') != policy['gates'] or receipt.get('rights_approval') is not False):
        raise ValueError('A failed or unapproved result cannot become an ASR success receipt.')
    target = output / 'ASR-RECEIPT.json'
    pending = output / 'PRIVATE-ASR-RECEIPT.pending.json'
    no_links(target); no_links(pending)
    if target.exists():
        raise ValueError('Preserve the existing ASR result and choose a fresh attempt.')
    with pending.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    # No visible success file if serialization/close fails. This is the final
    # commit point; the caller performs no subsequent fallible work.
    pending.rename(target)


def reject_parent_imports(output):
    global _BUILD_ENVIRONMENT_OBSERVATION
    categories = parent_import_categories(output)
    if _BUILD_ENVIRONMENT_OBSERVATION is None:
        _BUILD_ENVIRONMENT_OBSERVATION = {'vc_targets': None}
    _BUILD_ENVIRONMENT_OBSERVATION['parent_import_categories'] = categories
    if categories:
        raise ValueError('An ambient parent MSBuild import/response file would affect the experiment.')


def build(output, tool_roots, vs_root, inputs, cmake_root=None, vs_version=None, vswhere=None):
    global _BUILD_SOURCE_COMMIT, _BUILD_CMAKE_OBSERVATION, _BUILD_ENVIRONMENT_OBSERVATION, _BUILD_VS_VERSION, _BUILD_TOOL_ROOTS, _BUILD_PROPERTIES, _BUILD_INSTANCE, _BUILD_TOOLCHAIN_SEAL, _BUILD_CMAKE_VARIANT
    global _BUILD_COMMON_DATA_PATH
    build_phase('build-preflight')
    _BUILD_SOURCE_COMMIT = None
    _BUILD_CMAKE_OBSERVATION = None
    _BUILD_ENVIRONMENT_OBSERVATION = None
    _BUILD_VS_VERSION = None
    _BUILD_TOOL_ROOTS = None
    _BUILD_PROPERTIES = None
    _BUILD_INSTANCE = None
    _BUILD_TOOLCHAIN_SEAL = None
    _BUILD_CMAKE_VARIANT = None
    _BUILD_COMMON_DATA_PATH = None
    try:
        return _build(output, tool_roots, vs_root, inputs, cmake_root, vs_version, vswhere)
    except Exception as error:
        try:
            check_common_data_origin()
        except Exception:
            pass  # Fixed origin state records failure; preserve the actual failed phase.
        try:
            failure = failed_build_receipt(output, _BUILD_PHASE, error)
        except Exception:
            # Invalid/unprepared caller paths cannot gain a diagnostic write.
            print('ASR reference failure metadata unavailable; no success claimed.', file=sys.stderr)
        else:
            print('ASR reference failed in ' + failure['phase'] + ' (' + failure['failure_category'] + ').', file=sys.stderr)
        raise


def _build(output, tool_roots, vs_root, inputs, cmake_root, vs_version, vswhere):
    global _BUILD_SOURCE_COMMIT, _BUILD_TOOL_ROOTS, _BUILD_PROPERTIES, _BUILD_INSTANCE, _BUILD_TOOLCHAIN_SEAL, _BUILD_CMAKE_VARIANT
    output, vs_root = Path(output).absolute(), Path(vs_root).absolute()
    build_phase('source-validation')
    receipt, policy = verify_sources(output), pin()
    if (output / 'ASR-RECEIPT.json').exists() or (output / 'ASR-FAILURE.json').exists():
        raise ValueError('Choose a fresh prepared ASR attempt; existing results are preserved.')
    build_phase('toolchain-validation')
    if sys.platform != 'win32' or struct.calcsize('P') != 8 or sys.version_info[:3] != (3, 12, 16):
        raise ValueError('The exact separate Windows x64 Python supplier is required.')
    source_commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if (not re.fullmatch('[0-9a-f]{40}', source_commit)
            or subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip()):
        raise ValueError('A clean candidate source commit is required before native building.')
    _BUILD_SOURCE_COMMIT = source_commit
    build_phase('vs-installation-origin')
    no_links(vs_root)
    build_phase('tool-root-schema')
    roots = read_json(Path(tool_roots))
    validate_tool_root_schema(roots)
    build_phase('tool-root-filesystem')
    validate_tool_roots(roots)
    _BUILD_TOOL_ROOTS = dict(roots)
    build_phase('python-interpreter-origin')
    if Path(roots['python']).resolve() != Path(sys.prefix).resolve():
        raise ValueError('The sealed Python root is not this interpreter.')
    build_phase('python-supplier-bytes')
    verify_python(inputs, roots['python'])
    build_phase('tool-root-filesystem')
    for path in roots.values(): no_links(Path(path))
    build_phase('vs-installation-origin')
    vs_initial = verify_vs_selection(vs_root, vs_version, vswhere, roots)
    build_phase('cmake-pinned-input')
    cmake_supplier = verify_pinned_cmake(cmake_root, roots['cmake'])
    build_phase('cmake-module-variant-preparation')
    variant_root = output / 'PRIVATE-CMAKE-MODULE-VARIANT'
    variant_payload, cmake_variant = prepare_cmake_module_variant(cmake_root, variant_root)
    _BUILD_CMAKE_VARIANT = cmake_variant
    cmake = variant_payload / 'bin/cmake.exe'
    build_phase('cmake-version-review')
    observe_cmake_version(cmake, policy['toolchain']['cmake_version'])
    build_phase('toolchain-seal')
    initial = seal_toolchain(roots)
    initial['vswhere-query'] = {'vswhere.exe': vs_initial['vswhere']}
    initial['cmake-module-variant'] = cmake_tool_module().tree(variant_root)[0]
    _BUILD_TOOLCHAIN_SEAL = initial
    write_json(output / 'PRIVATE-TOOLCHAIN-INVENTORY.json', initial)
    build_phase('probe-dependency-preparation')
    numpy_files = prepare_numpy(inputs, output / 'probe-dependencies')
    build_phase('build-environment')
    logs = output / 'private-logs'; logs.mkdir()
    build_root = output / 'build'
    env = {k: v for k, v in os.environ.items() if k.casefold() in {
        'systemroot', 'windir', 'comspec', 'processor_architecture', 'number_of_processors',
        'programfiles', 'programfiles(x86)', 'programw6432', 'temp', 'tmp'}}
    env.update({'PATH': os.pathsep.join([str(cmake.parent), str(Path(sys.executable).parent),
        str(Path(os.environ['SystemRoot']) / 'System32'),
        str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0')]),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
        'HOME': str(output / 'empty-home'), 'USERPROFILE': str(output / 'empty-home'),
        'APPDATA': str(output / 'empty-home/AppData/Roaming'),
        'LOCALAPPDATA': str(output / 'empty-home/AppData/Local')})
    (output / 'empty-home').mkdir()
    user_props = output / 'empty-home/MSBuild'; user_props.mkdir()
    targets = review_vc_targets(output, roots['msbuild'])
    build_properties = {'ImportDirectoryBuildProps': 'false', 'ImportDirectoryBuildTargets': 'false',
        'UserRootDir': user_props.as_posix() + '/', 'MSBuildUserExtensionsPath': user_props.as_posix() + '/',
        'VCTargetsPath': targets[0].parent.as_posix() + '/'}
    for when in ('Before', 'After'):
        for kind in ('CommonProps', 'CommonTargets', 'CppDefaultProps', 'CppProps', 'CppTargets'):
            build_properties['ImportUserLocationsByWildcard' + when + 'Microsoft' + kind] = 'false'
    _BUILD_PROPERTIES = dict(build_properties)
    env.update(build_properties)
    env['MSBUILDDISABLENODEREUSE'] = '1'
    build_phase('parent-import-review')
    reject_parent_imports(output)
    env = common_data_environment(output, roots, initial, env)
    _BUILD_INSTANCE = {'argument': cmake_instance_spec(vs_root, vs_version), 'root': str(vs_root),
        'observed_version': _BUILD_VS_VERSION}
    configure = [cmake, '-S', output / 'sources/sherpa-onnx', '-B', build_root,
        '-G', policy['toolchain']['generator'], '-A', 'x64',
        '-T', 'host=x64,version=' + policy['toolchain']['vc_tools_version'],
        '-DCMAKE_GENERATOR_INSTANCE=' + _BUILD_INSTANCE['argument'],
        '-DCMAKE_SYSTEM_VERSION=' + policy['toolchain']['windows_sdk_version'],
        '--trace-expand', '--trace-format=json-v1', '--trace-redirect=' + str(output / 'PRIVATE-CMAKE-TRACE.jsonl')]
    build_phase('configure-argument-review')
    configure += cmake_arguments(output, sys.executable)
    configure += ['-DCMAKE_VS_GLOBALS=' + ';'.join(k + '=' + v for k, v in build_properties.items())]
    map_option = '/INCREMENTAL:NO /Brepro /MAP:' + (output / 'PRIVATE-BINDING.map').as_posix()
    configure += ['-DCMAKE_MODULE_LINKER_FLAGS_RELEASE=' + map_option,
                  '-DCMAKE_SHARED_LINKER_FLAGS_RELEASE=' + map_option]
    print('Configuring the distinct ASR source experiment; raw paths/logs remain private.', flush=True)
    build_phase('cmake-configure')
    run_private(configure, logs / 'configure.log', env, output, 600)
    build_phase('build-graph-review')
    graph = verify_trace(output / 'PRIVATE-CMAKE-TRACE.jsonl', output)
    verify_cache(build_root / 'CMakeCache.txt', output, cmake_instance_spec(vs_root, vs_version))
    for language in ('C', 'CXX'):
        compilers = list(build_root.glob('CMakeFiles/**/CMake' + language + 'Compiler.cmake'))
        if len(compilers) != 1:
            raise ValueError('A unique selected compiler observation is required.')
        observed = compilers[0].read_text()
        compiler = re.search(r'set\(CMAKE_' + language + r'_COMPILER "([^"]+)"\)', observed)
        if (('set(CMAKE_' + language + '_COMPILER_VERSION "' + policy['toolchain']['compiler_version'] + '")') not in observed
                or not compiler or not Path(compiler[1]).resolve().is_relative_to(Path(roots['vc']).resolve())):
            raise ValueError('The observed compiler version or sealed tool origin differs.')
    projects = list(build_root.rglob('*.vcxproj'))
    if not projects or any(native_tts_name(p.name) for p in projects):
        raise ValueError('Unexpected TTS/native project in the ASR build graph.')
    compiled = [str((p.parent / html.unescape(v)).resolve()) for p in projects
                for v in re.findall(r'<ClCompile Include="([^"]+)"', p.read_text(encoding='utf-8-sig'))]
    if (not any(v.endswith('offline-sense-voice-model.cc') for v in compiled)
            or any(native_tts_name(v) or re.search(r'offline-tts', v, re.I) for v in compiled)):
        raise ValueError('The actual ASR compilation input scope differs.')
    if any(not Path(v).is_relative_to(output) for v in compiled):
        raise ValueError('A compilation unit is outside the prepared/build output.')
    verify_sources(output)
    print('Building the binding with the sealed source graph; no production collection.', flush=True)
    build_phase('native-build')
    run_private([cmake, '--build', build_root, '--config', 'Release', '--target', '_sherpa_onnx', '--parallel', '2',
                 '--', '/nodeReuse:false', '/noAutoResponse'],
                logs / 'build.log', env, output, 1800)
    build_phase('native-output-review')
    outputs = list((build_root / 'lib/Release').glob('_sherpa_onnx*.pyd'))
    if len(outputs) != 1 or outputs[0].name != '_sherpa_onnx.cp312-win_amd64.pyd':
        raise ValueError('A unique rebuilt Python binding was not produced.')
    pyd = outputs[0]
    native_binding = attributes(pyd.read_bytes())
    native = pe_evidence(pyd.read_bytes())
    validate_native(native)
    link_map = (output / 'PRIVATE-BINDING.map').read_text(encoding='utf-8', errors='replace')
    if not link_map or native_tts_name(link_map):
        raise ValueError('Unexpected phonemizer in the actual binding link map.')
    build_phase('candidate-assembly')
    wheel = make_wheel(output, pyd)
    wheel_bytes = attributes(wheel.read_bytes())
    candidate_files = inventory(output / 'candidate')
    spec = importlib.util.spec_from_file_location('owned_asr_fixture', ROOT / 'scripts/probe-reference-asr.py')
    fixture_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture_module)
    fixtures = fixture_module.fixtures(output / 'owned-fixtures')
    probes = []
    for case in ('decode', 'wrong-shape', 'corrupt'):
        build_phase('probe-' + case)
        report = output / ('PRIVATE-PROBE-' + case + '.json')
        run_private([sys.executable, '-I', '-B', ROOT / 'scripts/probe-reference-asr.py',
            '--package', output / 'candidate', '--numpy', output / 'probe-dependencies',
            '--fixtures', output / 'owned-fixtures', '--case', case, '--report', report],
            logs / ('probe-' + case + '.log'), env, output / 'empty-home', 90)
        result = read_json(report)
        if (result['onnx_dll_sha256'] != sha((output / 'sources/onnxruntime/lib/onnxruntime.dll').read_bytes())
                or result['binding_filename'] != pyd.name or result['binding_sha256'] != native_binding['sha256']):
            raise ValueError('Native probe DLL bytes differ from the exact ONNX input.')
        probes.append(result)
    build_phase('final-source-review')
    verify_sources(output)
    reject_parent_imports(output)
    build_phase('final-candidate-review')
    if (inventory(output / 'candidate') != candidate_files
            or inventory(output / 'probe-dependencies') != numpy_files
            or attributes(pyd.read_bytes()) != native_binding
            or attributes(wheel.read_bytes()) != wheel_bytes):
        raise ValueError('An actual candidate/native/probe input changed during execution.')
    build_phase('final-toolchain-review')
    vs_final = verify_vs_selection(vs_root, vs_version, vswhere, roots, vs_initial)
    final_tools = seal_toolchain(roots)
    final_tools['vswhere-query'] = {'vswhere.exe': vs_final['vswhere']}
    final_tools['cmake-module-variant'] = cmake_tool_module().tree(variant_root)[0]
    if final_tools != initial or vs_final != vs_initial:
        raise ValueError('Compiler, SDK, CMake, MSBuild or Python bytes changed during the experiment.')
    build_phase('final-cmake-pinned-input')
    if verify_pinned_cmake(cmake_root, roots['cmake']) != cmake_supplier:
        raise ValueError('The exact CMake input/tree receipt changed during the experiment.')
    build_phase('final-cmake-module-variant')
    if verify_cmake_module_variant(cmake_root, variant_root) != cmake_variant:
        raise ValueError('The separate exact CMake module variant changed during execution.')
    build_phase('common-data-final')
    check_common_data_origin()
    build_phase('source-commit-review')
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip()
    if commit != source_commit or dirty:
        raise ValueError('A clean candidate source commit is required for the final receipt.')
    receipt.update({'status': 'native-reference-probes-passed', 'source_commit': commit,
        'toolchain_constraints': policy['toolchain'], 'toolchain_observed_bytes': toolchain_summary(initial),
        'visual_studio_selection': vs_initial,
        'pinned_cmake': cmake_supplier,
        'cmake_module_variant_observation': safe_cmake_variant_observation(),
        'build_environment_observation': safe_build_environment_observation(),
        'source_graph': graph, 'native_binding': native_binding,
        'native_pe': native, 'link_map_sha256': sha((output / 'PRIVATE-BINDING.map').read_bytes()),
        'no_espeak_link_input_observed': True, 'private_wheel': wheel_bytes,
        'owned_fixtures': fixtures, 'native_probes': probes,
        'trained_model': False, 'speech_recognition_accuracy_verified': False,
        'onnx_native_source_crt_review': 'pending-exact-inputs',
        'windows_11_acceptance': 'unavailable', 'rights_approval': False})
    build_phase('success-receipt')
    print('Owned native format/API probes passed; all production/rights/Windows11 gates remain open.', flush=True)
    publish_success_receipt(output, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--inputs', type=Path, required=True)
    prep.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('verify-sources')
    check.add_argument('--output', type=Path, required=True)
    python = sub.add_parser('prepare-python')
    python.add_argument('--archive', type=Path, required=True)
    python.add_argument('--output', type=Path, required=True)
    native = sub.add_parser('build')
    native.add_argument('--output', type=Path, required=True)
    native.add_argument('--inputs', type=Path, required=True)
    native.add_argument('--tool-roots', type=Path, required=True)
    native.add_argument('--vs-root', type=Path, required=True)
    native.add_argument('--vs-version', required=True)
    native.add_argument('--vswhere', type=Path, required=True)
    native.add_argument('--cmake-root', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.inputs, args.output)
        print('ASR reference inputs prepared; no native build or rights acceptance claimed.')
    elif args.command == 'verify-sources':
        verify_sources(args.output)
        print('Exact ASR prepared source/recipe bytes verified.')
    elif args.command == 'prepare-python':
        prepare_python(args.archive, args.output)
        print('Exact separate Python supplier prepared; supplier rights review remains open.')
    else:
        build(args.output, args.tool_roots, args.vs_root, args.inputs, args.cmake_root, args.vs_version, args.vswhere)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Raw source/build/tool locations are private, including exception text.
        print('ASR reference operation failed; inspect the private build-host inputs.', file=sys.stderr)
        sys.exit(1)
