"""Source/notice/graph boundaries of the distinct ASR experiment, no native pass."""
import importlib.util
import difflib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return load('asr_reference_test', 'scripts/reference-asr.py')


def common_markers(*, runtime='Full', x64='True', empty='False', programdata='True', allusers='True', rooted='True'):
    return (f'R19-ASR-COMMON-V1 folder;runtime={runtime};x64={x64};empty={empty};programdata={programdata};allusers={allusers}\n'
        'R19-ASR-COMMON-V1 do-not-verify-returned\n'
        'R19-ASR-COMMON-V1 do-not-verify;empty=False;rooted=True;programdata=True;allusers=True\n'
        f'R19-ASR-COMMON-V1 root;empty=False;rooted={rooted}\n').encode()


def common_environment_fixture(module, tmp_path, monkeypatch):
    root = tmp_path.resolve()
    output = root / 'attempt'; output.mkdir()
    folder = root / 'os-common'; folder.mkdir()
    tools = root / 'msbuild'
    executable = tools / 'Current/Bin/amd64/MSBuild.exe'
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'owned sealed executable bytes, never executed')
    initial = {'msbuild': {'Current/Bin/amd64/MSBuild.exe': module.attributes(executable.read_bytes())}}
    module._BUILD_ENVIRONMENT_OBSERVATION = {'vc_targets': None, 'parent_import_categories': []}
    monkeypatch.setattr(module, 'query_common_data_directory', lambda: folder)
    return output, folder, executable, {'msbuild': str(tools)}, initial


def test_common_data_fixed_project_uses_only_builtin_property_functions_and_ordered_records(module):
    tree = module.ET.fromstring(module.COMMON_DATA_PROJECT)
    names = [element.tag.rsplit('}', 1)[-1] for element in tree.iter()]
    assert set(names) <= {'Project', 'Target', 'PropertyGroup', 'Message', '_R19Folder', '_R19ProgramData', '_R19AllUsers', '_R19Root', '_R19DoNotVerifyFolder'}
    assert tree.attrib == {'DefaultTargets': 'R19Root'}
    messages = [element.attrib['Text'] for element in tree.iter() if element.tag.endswith('}Message')]
    assert [message.split(';')[0] for message in messages] == [
        'R19-ASR-COMMON-V1 folder', 'R19-ASR-COMMON-V1 do-not-verify-returned',
        'R19-ASR-COMMON-V1 do-not-verify', 'R19-ASR-COMMON-V1 root']
    assert all(message.startswith('R19-ASR-COMMON-V1 ') for message in messages)
    assert 'GetFolderPath(\'SpecialFolder.CommonApplicationData\')' in module.COMMON_DATA_PROJECT
    assert "GetFolderPath('SpecialFolder.CommonApplicationData', 'SpecialFolderOption.DoNotVerify')" in module.COMMON_DATA_PROJECT
    assert all("'StringComparison.OrdinalIgnoreCase'" in message for message in messages if '::Equals(' in message)
    # Default emission precedes the contrast call, and both precede GetPathRoot.
    assert module.COMMON_DATA_PROJECT.index('R19-ASR-COMMON-V1 folder;') < module.COMMON_DATA_PROJECT.index("'SpecialFolderOption.DoNotVerify'") < module.COMMON_DATA_PROJECT.index('::GetPathRoot(')
    assert messages[1] == 'R19-ASR-COMMON-V1 do-not-verify-returned' and '$' not in messages[1]
    contrast = messages[2]
    assert {part.split('=', 1)[0] for part in contrast.split(';')[1:]} == {'empty', 'rooted', 'programdata', 'allusers'}
    assert all('=$([' in part for part in contrast.split(';')[1:])  # No raw property output.
    assert '$(_R19DoNotVerifyFolder)' not in messages[3]  # Default root authority stays separate.
    assert '$(MSBuildRuntimeType)' in module.COMMON_DATA_PROJECT and 'Is64BitProcess' in module.COMMON_DATA_PROJECT
    assert 'GetPathRoot' in module.COMMON_DATA_PROJECT and 'IsPathRooted' in module.COMMON_DATA_PROJECT
    assert 'SystemDrive' not in module.COMMON_DATA_PROJECT
    assert all('$(_R19Folder)' not in message.replace("'$(_R19Folder)'", '') for message in messages)


@pytest.mark.parametrize('ending', [b'\n', b'\r\n'])
def test_common_data_markers_are_fixed_typed_states_without_private_output(module, ending):
    raw = b'ordinary private error path must be discarded' + ending + common_markers().replace(b'\n', ending)
    value = module.common_data_markers(0, raw)
    assert value == {'status': 'observed', 'reason': 'none', 'runtime': 'full', 'x64': True,
        'folder': 'nonempty', 'root': 'nonempty', 'rooted': True,
        'programdata_equal': True, 'allusersprofile_equal': True,
        'do_not_verify_call': 'returned', 'msbuild_codes': [],
        'dnv_error_resource': 'not-observed',
        'do_not_verify': {'empty': False, 'rooted': True, 'programdata_equal': True, 'allusersprofile_equal': True}}
    assert 'private' not in json.dumps(value)
    assert module.common_data_markers(0, b'\xef\xbb\xbf' + common_markers()) == value


@pytest.mark.parametrize('raw', [b'', common_markers().splitlines()[0], common_markers() * 2,
    common_markers().replace(b'runtime=Full', b'runtime=private-secret'),
    common_markers().replace(b'x64=True', b'x64=1'), common_markers().replace(b';rooted=True', b';rooted=True;private=secret'),
    b'private prefix ' + common_markers(), common_markers().replace(b'\n', b'\r'),
    common_markers().replace(b'\n', b'\x00\n'), b'\xff' + common_markers(), b'x' * 32769,
    common_markers().replace(b'\n', '\u2028'.encode())])
def test_common_data_rejects_missing_ambiguous_raw_or_overbound_markers(module, raw):
    with pytest.raises(module.CommonDataProbeError) as error:
        module.common_data_markers(0, raw)
    assert error.value.reason in module.COMMON_DATA_REASONS
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('code', [None, True, -1, 2**32, '0'])
def test_common_data_marker_exit_code_requires_exact_bounded_integer(module, code):
    with pytest.raises(module.CommonDataProbeError): module.common_data_markers(code, common_markers())


def test_common_data_nonzero_folder_only_is_partial_evidence_not_root_success(module):
    value = module.common_data_markers(1, common_markers(empty='True').splitlines(keepends=True)[0])
    assert value['status'] == 'rejected' and value['reason'] == 'process-rejected'
    assert value['folder'] == 'empty' and value['root'] == 'not-run' and value['rooted'] is None
    assert all(v is None for v in value['do_not_verify'].values())


def test_common_data_contrast_survives_rejected_root_without_promoting_default(module):
    partial = b'\n'.join(common_markers(empty='True').splitlines()[:3]) + b'\n'
    value = module.common_data_markers(1, partial)
    assert value['status'] == 'rejected' and value['folder'] == 'empty' and value['root'] == 'not-run'
    assert value['do_not_verify'] == {'empty': False, 'rooted': True,
        'programdata_equal': True, 'allusersprofile_equal': True}
    with pytest.raises(module.CommonDataProbeError): module.common_data_markers(0, partial)


def test_common_data_constant_return_stage_precedes_private_message_evaluation(module):
    partial = b'\n'.join(common_markers(empty='True').splitlines()[:2]) + b'\n'
    value = module.common_data_markers(1, partial)
    assert value['do_not_verify_call'] == 'returned'
    assert all(v is None for v in value['do_not_verify'].values())
    assert value['status'] == 'rejected' and value['root'] == 'not-run'
    with pytest.raises(module.CommonDataProbeError) as error: module.common_data_markers(0, partial)
    assert error.value.call_stage == 'returned'
    default_only = module.common_data_markers(1, common_markers().splitlines(keepends=True)[0])
    assert default_only['do_not_verify_call'] == 'not-observed'  # No assertion that the call threw.


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'reordered', 'truncated', 'property'])
def test_common_data_constant_stage_requires_exact_cardinality_and_order(module, mutation):
    lines = common_markers().splitlines()
    if mutation == 'missing': lines.pop(1)
    if mutation == 'duplicate': lines.insert(2, lines[1])
    if mutation == 'reordered': lines[0], lines[1] = lines[1], lines[0]
    if mutation == 'truncated': lines[1] = lines[1][:-1]
    if mutation == 'property': lines[1] += b';value=private-field'
    with pytest.raises(module.CommonDataProbeError) as error:
        module.common_data_markers(1, b'\n'.join(lines) + b'\n')
    assert error.value.call_stage == 'not-observed'


def test_common_data_codes_require_owned_error_headers_and_deduplicate_canonically(module, tmp_path):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    raw = (f'{project}(9,7): error MSB4186: private invocation details\n'
        'MSBUILD : error MSB4184: private expression\n'
        f'  {project}(9,7,9,20) : error MSB4185: private function\n'
        f'{project}(9,7): error MSB4184: repeated summary\n').encode() + common_markers()
    value = module.common_data_markers(1, raw, project=project)
    assert value['msbuild_codes'] == ['MSB4184', 'MSB4185', 'MSB4186']
    assert 'private' not in json.dumps(value) and str(project) not in json.dumps(value)
    assert value['status'] == 'rejected'


def common_dnv_error(project):
    # Reference renderer joins the original qualified argument strings; the
    # exact English inner slot is mscorlib Argument_AbsolutePathRequired.
    return (f'{project}(10,7): error MSB4184: The expression "[System.Environment]::GetFolderPath('
        'SpecialFolder.CommonApplicationData, SpecialFolderOption.DoNotVerify)" cannot be evaluated. '
        'Absolute path information is required.\n').encode()


@pytest.mark.parametrize('ending', [b'\n', b'\r\n'])
def test_common_data_owned_dnv_resource_is_an_exact_partial_format_observation(module, tmp_path, ending):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    raw = common_markers(empty='True').splitlines(keepends=True)[0] + common_dnv_error(project)*2
    value = module.common_data_markers(1, raw.replace(b'\n', ending), project=project)
    assert value['dnv_error_resource'] == 'absolute-path-required' and value['msbuild_codes'] == ['MSB4184']
    assert value['status'] == 'rejected' and value['folder'] == 'empty' and value['do_not_verify_call'] == 'not-observed'
    assert all(v is None for v in value['do_not_verify'].values())
    observation = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE',
        'origin_stable': 'verified', 'baseline': module.common_data_result(), 'bound': value}
    assert module.safe_common_data_observation(observation) == observation
    assert str(project) not in json.dumps(observation) and 'The expression' not in json.dumps(observation)


@pytest.mark.parametrize('mutation', ['global', 'foreign', 'default-call', 'other-call', 'embedded', 'resource', 'suffix', 'punctuation'])
def test_common_data_dnv_resource_rejects_unowned_or_nonexact_inner_slots(module, tmp_path, mutation):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    line = common_dnv_error(project)
    if mutation == 'global': line = line.replace((str(project)+'(10,7)').encode(), b'MSBUILD')
    if mutation == 'foreign': line = line.replace(str(project).encode(), b'foreign/PRIVATE-COMMON-DATA.proj')
    if mutation == 'default-call': line = line.replace(b', SpecialFolderOption.DoNotVerify', b'')
    if mutation == 'other-call': line = line.replace(b'GetFolderPath', b'GetPathRoot')
    if mutation == 'embedded': line = line.replace(b'cannot be evaluated. ', b'cannot be evaluated. private message mentions: ')
    if mutation == 'resource': line = line.replace(b'Absolute path information is required.', b'private unknown resource')
    if mutation == 'suffix': line = line.rstrip(b'\n') + b' [private-context]\n'
    if mutation == 'punctuation': line = line.replace(b'is required.', b'is required')
    raw = common_markers(empty='True').splitlines(keepends=True)[0] + line
    assert module.common_data_markers(1, raw, project=project)['dnv_error_resource'] == 'not-observed'


@pytest.mark.parametrize('mutation', ['returned', 'conflicting-message', 'conflicting-code'])
def test_common_data_dnv_resource_cannot_override_conflicting_owned_context(module, tmp_path, mutation):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    raw = common_markers().splitlines(keepends=True)[0] + common_dnv_error(project)
    if mutation == 'returned': raw += common_markers().splitlines(keepends=True)[1]
    if mutation == 'conflicting-message': raw += common_dnv_error(project).replace(b'Absolute path information is required.', b'private conflicting inner slot')
    if mutation == 'conflicting-code': raw += common_dnv_error(project).replace(b'MSB4184', b'MSB9999')
    value = module.common_data_markers(1, raw, project=project)
    assert value['dnv_error_resource'] == 'not-observed' and 'MSB9999' not in value['msbuild_codes']


@pytest.mark.parametrize('second_position', [b'(99,9)', b'(10,7,10,7)'])
def test_common_data_equal_resource_body_at_another_owned_location_is_not_an_identical_summary(module, tmp_path, second_position):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    original = common_dnv_error(project)
    second = original.replace(b'(10,7)', second_position, 1)
    raw = common_markers(empty='True').splitlines(keepends=True)[0] + original + second
    value = module.common_data_markers(1, raw, project=project)
    assert value['dnv_error_resource'] == 'not-observed'
    assert value['msbuild_codes'] == ['MSB4184'] and value['status'] == 'rejected'


def test_common_data_matching_dnv_resource_never_authorizes_empty_default(module, tmp_path, monkeypatch):
    output, _folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    raw = common_markers(empty='True').splitlines(keepends=True)[0] + common_dnv_error(output/'PRIVATE-COMMON-DATA.proj')
    monkeypatch.setattr(module, 'capture_common_data', lambda *_: (1, raw))
    with pytest.raises(ValueError, match='Full CLR x64'):
        module.common_data_environment(output, roots, initial, {})
    value = module.safe_build_environment_observation()['common_data']['bound']
    assert value['dnv_error_resource'] == 'absolute-path-required' and value['status'] == 'rejected'


@pytest.mark.parametrize('invalid', [True, [], 'private-resource', 'path-empty', 'not-run'])
def test_common_data_public_resource_enum_rejects_unknown_types_and_states(module, invalid):
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE', 'origin_stable': 'verified',
        'baseline': module.common_data_result(), 'bound': module.common_data_result('process-rejected')}
    value['bound']['dnv_error_resource'] = invalid
    assert module.safe_common_data_observation(value) is None


@pytest.mark.parametrize('field,replacement', [('do_not_verify_call','returned'), ('msbuild_codes',[]), ('reason','invalid-markers')])
def test_common_data_public_resource_match_requires_coherent_partial_context(module, tmp_path, field, replacement):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    value = module.common_data_markers(1, common_markers().splitlines(keepends=True)[0] + common_dnv_error(project), project=project)
    value[field] = replacement
    observation = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE',
        'origin_stable': 'verified', 'baseline': module.common_data_result(), 'bound': value}
    assert module.safe_common_data_observation(observation) is None


@pytest.mark.parametrize('line', [
    'message mentions MSB4184 only', 'message: error MSB4184: private text',
    'The expression "MSBUILD : error MSB4184: private" cannot be evaluated.',
    'MSBUILD : warning MSB4184: private', 'MSBUILD : error MSB9999: private',
    'MSBUILD : error MSB41840: private', 'MSBUILD : error MSB4184/private-path',
    'private-MSB4184-folder/PRIVATE-COMMON-DATA.proj(1,2): error MSB4184: private',
    'foreign/PRIVATE-COMMON-DATA.proj(1,2): error MSB4184: private',
    'PRIVATE-COMMON-DATA.proj(1,2): error MSB4184: private',
    '{project}(0,2): error MSB4184: private', '{project}(1,10000000): error MSB4184: private',
    'prefix {project}(1,2): error MSB4184: private'])
def test_common_data_code_tokens_in_paths_messages_expressions_or_bad_headers_are_not_observations(module, tmp_path, line):
    project = tmp_path.resolve()/'PRIVATE-COMMON-DATA.proj'
    raw = (line.replace('{project}', str(project))+'\n').encode() + common_markers()
    assert module.common_data_markers(1, raw, project=project)['msbuild_codes'] == []


@pytest.mark.parametrize('malformed', [False, True])
def test_common_data_stage_and_code_survive_partial_failure_without_granting_acceptance(module, tmp_path, monkeypatch, malformed):
    output, _folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    raw = b'\n'.join(common_markers(empty='True').splitlines()[:2]) + b'\n'
    if malformed: raw += b'R19-ASR-COMMON-V1 do-not-verify;empty=private-field\n'
    raw += f'{output/"PRIVATE-COMMON-DATA.proj"}(9,7): error MSB4184: private expression/context\n'.encode()
    monkeypatch.setattr(module, 'capture_common_data', lambda *_: (1, raw))
    with pytest.raises(ValueError, match='Full CLR x64'):
        module.common_data_environment(output, roots, initial, {})
    value = module.safe_build_environment_observation()['common_data']['bound']
    assert value['do_not_verify_call'] == 'returned' and value['msbuild_codes'] == ['MSB4184']
    assert value['status'] == 'rejected' and all(v is None for v in value['do_not_verify'].values())
    assert value['reason'] == ('invalid-markers' if malformed else 'process-rejected')
    assert 'private' not in json.dumps(value)


@pytest.mark.parametrize('codes', ['MSB4184', ('MSB4184',), [True], ['private'],
    ['MSB4186','MSB4184'], ['MSB4184','MSB4184'], ['MSB4184']*4])
def test_common_data_public_code_projection_requires_exact_sorted_unique_allowlist(module, codes):
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE', 'origin_stable': 'verified',
        'baseline': module.common_data_result(), 'bound': module.common_data_result('invalid-markers')}
    value['bound']['msbuild_codes'] = codes
    assert module.safe_common_data_observation(value) is None


@pytest.mark.parametrize('stage', [True, None, [], 'private', 'threw'])
def test_common_data_public_stage_projection_has_no_inferred_failure_or_raw_context(module, stage):
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE', 'origin_stable': 'verified',
        'baseline': module.common_data_result(), 'bound': module.common_data_result('invalid-markers')}
    value['bound']['do_not_verify_call'] = stage
    assert module.safe_common_data_observation(value) is None


@pytest.mark.parametrize('mutation', ['missing', 'swapped', 'duplicate', 'truncated', 'unknown', 'lowercase', 'integer', 'extra'])
def test_common_data_contrast_refuses_ambiguous_partial_or_untyped_records(module, mutation):
    lines = common_markers().splitlines()
    if mutation == 'missing': lines.pop(2)
    if mutation == 'swapped': lines[2], lines[3] = lines[3], lines[2]
    if mutation == 'duplicate': lines.insert(3, lines[2])
    if mutation == 'truncated': lines[2] = lines[2][:-2]
    if mutation == 'unknown': lines[2] = lines[2].replace(b'do-not-verify', b'private-unknown')
    if mutation == 'lowercase': lines[2] = lines[2].replace(b'rooted=True', b'rooted=true')
    if mutation == 'integer': lines[2] = lines[2].replace(b'rooted=True', b'rooted=1')
    if mutation == 'extra': lines[2] += b';raw=private-folder-value'
    with pytest.raises(module.CommonDataProbeError) as error:
        module.common_data_markers(1, b'\n'.join(lines) + b'\n')
    assert error.value.reason == 'invalid-markers' and 'private' not in str(error.value)


@pytest.mark.parametrize('partial', [False, True])
def test_common_data_unverified_result_cannot_authorize_empty_default(module, tmp_path, monkeypatch, partial):
    output, _folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    raw = common_markers(empty='True')
    if partial: raw = b'\n'.join(raw.splitlines()[:3]) + b'\n'
    calls = []
    def capture(*_):
        calls.append(True)
        return (1 if partial else 0), raw
    monkeypatch.setattr(module, 'capture_common_data', capture)
    with pytest.raises(ValueError, match='Full CLR x64'):
        module.common_data_environment(output, roots, initial, {})
    assert calls == [True, True]
    observed = module.safe_build_environment_observation()['common_data']['bound']
    assert observed['folder'] == 'empty' and observed['do_not_verify']['rooted'] is True


def test_common_data_unverified_observation_never_replaces_default_acceptance(module, tmp_path, monkeypatch):
    output, folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    raw = common_markers().replace(
        b'do-not-verify;empty=False;rooted=True;programdata=True;allusers=True',
        b'do-not-verify;empty=True;rooted=False;programdata=False;allusers=False')
    monkeypatch.setattr(module, 'capture_common_data', lambda *_: (0, raw))
    assert module.common_data_environment(output, roots, initial, {})['PROGRAMDATA'] == str(folder)
    assert module.safe_build_environment_observation()['common_data']['bound']['do_not_verify']['empty'] is True


@pytest.mark.parametrize('malformed', [None, {}, {'empty': 'private-folder'},
    {'empty': False, 'rooted': 1, 'programdata_equal': True, 'allusersprofile_equal': True},
    {'empty': None, 'rooted': False, 'programdata_equal': False, 'allusersprofile_equal': False},
    {'empty': False, 'rooted': True, 'programdata_equal': True, 'allusersprofile_equal': True, 'raw': 'private-folder'}])
def test_common_data_contrast_public_projection_refuses_raw_unknown_or_partial_types(module, malformed):
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE', 'origin_stable': 'verified',
        'baseline': module.common_data_result(), 'bound': module.common_data_result()}
    value['bound']['do_not_verify'] = malformed
    assert module.safe_common_data_observation(value) is None


def test_common_data_two_states_bind_only_authoritative_aliases_and_sealed_x64_tool(module, tmp_path, monkeypatch):
    output, folder, executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    calls = []
    env = {'PATH': 'fixed', 'ProgramData': 'untrusted baseline', 'allusersprofile': 'other baseline',
        'ImportDirectoryBuildProps': 'false', 'MSBUILDDISABLENODEREUSE': '1'}
    original = dict(env)
    def capture(command, child_env, cwd):
        calls.append((list(command), dict(child_env), cwd))
        return (1, common_markers(empty='True').splitlines(keepends=True)[0]) if len(calls) == 1 else (0, common_markers())
    monkeypatch.setattr(module, 'capture_common_data', capture)
    bound = module.common_data_environment(output, roots, initial, env)
    assert len(calls) == 2 and calls[0][1] == original and env == original
    assert bound == {k: v for k, v in original.items() if k not in {'ProgramData', 'allusersprofile'}} | {
        'PROGRAMDATA': str(folder), 'ALLUSERSPROFILE': str(folder)}
    assert 'SystemDrive' not in bound
    assert calls[0][0] == calls[1][0] == [executable, output / 'PRIVATE-COMMON-DATA.proj',
        '/nologo', '/noautoresponse', '/nr:false', '/m:1', '/v:minimal']
    assert calls[0][2] == calls[1][2] == output
    assert (output / 'PRIVATE-COMMON-DATA.proj').read_text() == module.COMMON_DATA_PROJECT
    observed = module.safe_build_environment_observation()['common_data']
    assert observed['origin_stable'] == 'verified' and observed['bound']['runtime'] == 'full'
    assert str(folder) not in json.dumps(observed)


@pytest.mark.parametrize('changes', [{'runtime': 'Core'}, {'runtime': 'Mono'}, {'x64': 'False'},
    {'empty': 'True'}, {'rooted': 'False'}, {'programdata': 'False'}, {'allusers': 'False'}])
def test_common_data_binding_cannot_proceed_without_full_x64_matching_nonempty_root(module, tmp_path, monkeypatch, changes):
    output, _folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'capture_common_data', lambda *_: (0, common_markers(**changes)))
    with pytest.raises(ValueError, match='Full CLR x64'):
        module.common_data_environment(output, roots, initial, {})


@pytest.mark.parametrize('reason', ['output-limit', 'deadline', 'invalid-utf8', 'pipe-unavailable'])
def test_common_data_ordinary_baseline_refusal_still_runs_bound_once(module, tmp_path, monkeypatch, reason):
    output, _folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    calls = []
    def capture(*_):
        calls.append(True)
        if len(calls) == 1: raise module.CommonDataProbeError(reason)
        return 0, common_markers()
    monkeypatch.setattr(module, 'capture_common_data', capture)
    module.common_data_environment(output, roots, initial, {})
    assert len(calls) == 2
    assert module.safe_build_environment_observation()['common_data']['baseline']['reason'] == reason


@pytest.mark.parametrize('mutation', ['cleanup', 'tool', 'origin'])
def test_common_data_cleanup_or_identity_failure_never_starts_bound(module, tmp_path, monkeypatch, mutation):
    output, folder, executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    calls = []
    def capture(*_):
        calls.append(True)
        if mutation == 'cleanup': raise OSError('private cleanup uncertainty')
        if mutation == 'tool': executable.write_bytes(b'different owned bytes')
        if mutation == 'origin': monkeypatch.setattr(module, 'query_common_data_directory', lambda: folder.parent)
        return 0, common_markers()
    monkeypatch.setattr(module, 'capture_common_data', capture)
    with pytest.raises((OSError, ValueError)):
        module.common_data_environment(output, roots, initial, {})
    assert len(calls) == 1


def test_common_data_missing_selected_x64_tool_has_no_fallback(module, tmp_path, monkeypatch):
    output, _folder, executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    executable.unlink()
    (executable.parent.parent / 'MSBuild.exe').write_bytes(b'owned alternate, must never run')
    monkeypatch.setattr(module, 'capture_common_data', lambda *_: pytest.fail('no fallback execution'))
    with pytest.raises(ValueError, match='sealed x64'):
        module.common_data_environment(output, roots, initial, {})


@pytest.mark.parametrize('component', ['child/../secret', 'child.', 'child ', 'secret:stream', 'NUL', 'COM¹.txt'])
def test_common_data_raw_noncanonical_directory_refuses_before_metadata(module, tmp_path, monkeypatch, component):
    monkeypatch.setattr(module, 'diagnostic_file_info', lambda *_: pytest.fail('raw invalid path reached metadata'))
    with pytest.raises(ValueError): module.common_data_directory(str(tmp_path.resolve() / component))


def test_common_data_link_and_reparse_ancestors_refuse_before_leaf_metadata(module, tmp_path, monkeypatch):
    root = tmp_path.resolve()
    target = root / 'target'; target.mkdir(); (target / 'leaf').mkdir()
    link = root / 'link'
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        command = shutil.which('cmd.exe') if module.os.name == 'nt' else None
        if not command: pytest.skip('Owned directory links are unavailable on this host.')
        created = module.subprocess.run([command, '/d', '/c', 'mklink', '/J', str(link), str(target)],
            capture_output=True, timeout=10)
        if created.returncode: pytest.skip('Owned directory links and junctions are unavailable on this host.')
    original = Path.lstat
    leaf = link / 'leaf'
    def guarded(path, *args, **kwargs):
        if path == leaf: pytest.fail('linked descendant metadata accessed')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', guarded)
    with pytest.raises(ValueError): module.common_data_directory(str(leaf))
    # Authored reparse metadata is portable; no actual Windows junction claim.
    def reparse(path, *args, **kwargs):
        if path == leaf: pytest.fail('reparse descendant metadata accessed')
        if path == link: return SimpleNamespace(st_mode=module.stat.S_IFDIR, st_file_attributes=0x400)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', reparse)
    with pytest.raises(ValueError): module.common_data_directory(str(leaf))


@pytest.mark.parametrize('outcome', ['success', 'hresult', 'invalid', 'null'])
def test_common_data_known_folder_typed_call_frees_allocation_on_every_outcome(module, tmp_path, monkeypatch, outcome):
    import ctypes
    buffer = ctypes.create_unicode_buffer(str(tmp_path.resolve()) if outcome != 'invalid' else 'relative/private')
    calls, freed = [], []
    def query(guid, flags, token, pointer):
        calls.append((ctypes.sizeof(guid._obj), bytes(guid._obj), flags, token))
        if outcome != 'null': ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(buffer)
        return 1 if outcome == 'hresult' else 0
    def free(pointer): freed.append(pointer.value)
    def dll(name, **kwargs):
        assert kwargs == {'use_last_error': True}
        return SimpleNamespace(SHGetKnownFolderPath=query) if name == 'shell32' else SimpleNamespace(CoTaskMemFree=free)
    monkeypatch.setattr(ctypes, 'WinDLL', dll, raising=False)
    monkeypatch.setattr(module.sys, 'platform', 'win32')
    if outcome == 'success': assert module.query_common_data_directory() == tmp_path.resolve()
    else:
        with pytest.raises(ValueError): module.query_common_data_directory()
    assert calls[0][0] == 16 and calls[0][2:] == (0x4000, None)
    assert calls[0][1] == bytes.fromhex('825dab62c1fdc34da9dd070d1d495d97')
    assert len(query.argtypes) == 4 and query.restype is ctypes.c_int32
    assert free.argtypes == [ctypes.c_void_p] and free.restype is None
    assert freed == ([] if outcome == 'null' else [ctypes.addressof(buffer)])


@pytest.mark.parametrize('outcome', ['available', 'broken', 'failed'])
def test_common_data_windows_pipe_peek_preserves_64bit_handle_and_fixed_errors(module, monkeypatch, outcome):
    import ctypes
    handle = 0x100000007
    def peek(raw_handle, buffer, size, read, available, left):
        assert raw_handle.value == handle and buffer is None and size == 0 and read is None and left is None
        available._obj.value = 7
        return int(outcome == 'available')
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *_args, **_kwargs: SimpleNamespace(PeekNamedPipe=peek), raising=False)
    monkeypatch.setattr(ctypes, 'get_last_error', lambda: 109 if outcome == 'broken' else 6, raising=False)
    monkeypatch.setitem(module.sys.modules, 'msvcrt', SimpleNamespace(get_osfhandle=lambda _: handle))
    monkeypatch.setattr(module.sys, 'platform', 'win32')
    stream = SimpleNamespace(fileno=lambda: 12)
    if outcome == 'failed':
        with pytest.raises(module.CommonDataProbeError) as error: module.common_data_available(stream)
        assert error.value.reason == 'pipe-unavailable'
    else: assert module.common_data_available(stream) == (7 if outcome == 'available' else None)
    assert peek.argtypes[0] is ctypes.c_void_p and peek.restype is ctypes.c_int


@pytest.mark.parametrize('case', ['normal', 'overflow', 'deadline'])
def test_common_data_real_owned_pipe_is_bounded_and_drained_without_logs(module, tmp_path, monkeypatch, case):
    events = []
    class Owner:
        def command(self, values): events.append('wrapped'); return values
        def terminate(self, **kwargs): events.append(('drained', kwargs))
        def close(self): events.append('closed')
    monkeypatch.setattr(module, 'process_owner', Owner)
    source = {'normal': "import os; os.write(1,b'fixed\\n')", 'overflow': "import os; os.write(1,b'x'*32769)",
        'deadline': 'import time; time.sleep(10)'}[case]
    if case == 'deadline': monkeypatch.setattr(module, 'COMMON_DATA_SECONDS', .1)
    env = {k: v for k, v in module.os.environ.items() if k.casefold() in {'systemroot', 'windir', 'temp', 'tmp'}}
    if case == 'normal':
        assert module.capture_common_data([module.sys.executable, '-I', '-B', '-c', source], env, tmp_path) == (0, b'fixed\n')
    else:
        with pytest.raises(module.CommonDataProbeError) as error:
            module.capture_common_data([module.sys.executable, '-I', '-B', '-c', source], env, tmp_path)
        assert error.value.reason == ('output-limit' if case == 'overflow' else 'deadline')
    assert events == ['wrapped', ('drained', {'timeout': 10}), 'closed']
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('failure', ['terminate', 'close'])
def test_common_data_cleanup_uncertainty_overrides_rejected_probe(module, tmp_path, monkeypatch, failure):
    events = []
    class Owner:
        def command(self, values): return values
        def terminate(self, **_):
            events.append('terminate')
            if failure == 'terminate': raise OSError('owned uncertain drain')
        def close(self):
            events.append('close')
            if failure == 'close': raise OSError('owned uncertain close')
    monkeypatch.setattr(module, 'process_owner', Owner)
    monkeypatch.setattr(module, 'common_data_available', lambda _: (_ for _ in ()).throw(module.CommonDataProbeError('pipe-unavailable')))
    with pytest.raises(OSError):
        module.capture_common_data([module.sys.executable, '-I', '-B', '-c', 'import time; time.sleep(10)'], {}, tmp_path)
    assert events == ['terminate', 'close']


@pytest.mark.parametrize('failures', [('kill',), ('wait',), ('poll',), ('kill-interrupt',), ('kill', 'wait'),
    ('kill', 'terminate'), ('wait', 'close'), ('kill', 'wait', 'terminate', 'close', 'pipe-close')])
def test_common_data_all_cleanup_attempts_survive_bootstrap_and_combined_failures(module, tmp_path, monkeypatch, failures):
    output, _folder, _executable, roots, initial = common_environment_fixture(module, tmp_path, monkeypatch)
    events, launches = [], []
    def step(name):
        events.append(name)
        if name + '-interrupt' in failures:
            raise KeyboardInterrupt('owned cleanup interruption')
        if name in failures:
            raise OSError('owned private cleanup failure')
    class Owner:
        def command(self, values): return values
        def terminate(self, **kwargs):
            assert kwargs == {'timeout': 10}
            step('terminate')
        def close(self): step('close')
    class Pipe:
        def close(self): step('pipe-close')
    class Process:
        stdout = Pipe()
        def poll(self): step('poll'); return None
        def kill(self): step('kill')
        def wait(self, **kwargs):
            assert kwargs == {'timeout': 5}
            step('wait')
            return 0
    def popen(*_args, **_kwargs):
        launches.append(True)
        return Process()
    monkeypatch.setattr(module, 'process_owner', Owner)
    monkeypatch.setattr(module.subprocess, 'Popen', popen)
    monkeypatch.setattr(module, 'common_data_available', lambda _: (_ for _ in ()).throw(module.CommonDataProbeError('pipe-unavailable')))
    with pytest.raises(OSError) as error:
        module.common_data_environment(output, roots, initial, {})
    assert str(error.value) == 'Common-data owned cleanup is unconfirmed.'
    assert events == ['poll', 'kill', 'wait', 'terminate', 'close', 'pipe-close']
    assert launches == [True]
    assert module.safe_build_environment_observation()['common_data']['bound']['status'] == 'not-run'
    assert not (output / 'ASR-RECEIPT.json').exists()


@pytest.mark.parametrize('field,malformed', [('origin', 'private'), ('binding', []), ('origin_stable', {}),
    ('baseline', {'private': 'raw'}), ('bound', None)])
def test_common_data_public_projection_drops_unknown_structure(module, field, malformed):
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE', 'origin_stable': 'verified',
        'baseline': module.common_data_result(), 'bound': module.common_data_result()}
    value[field] = malformed
    assert module.safe_common_data_observation(value) is None


@pytest.mark.parametrize('field', list(('status', 'reason', 'runtime', 'folder', 'root', 'x64', 'rooted', 'programdata_equal', 'allusersprofile_equal')))
def test_common_data_public_projection_drops_raw_marker_context(module, field):
    value = {'origin': 'FOLDERID_ProgramData', 'binding': 'PROGRAMDATA+ALLUSERSPROFILE', 'origin_stable': 'verified',
        'baseline': module.common_data_result(), 'bound': module.common_data_result()}
    value['bound'][field] = ['private-path-or-environment']
    assert module.safe_common_data_observation(value) is None


def archive(path, files, *, link=None, root='upstream'):
    with tarfile.open(path, 'w:gz') as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(root + '/' + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if link:
            info = tarfile.TarInfo('upstream/' + link)
            info.type = tarfile.SYMTYPE
            info.linkname = 'owned.c'
            tar.addfile(info)


def item(module, path, *, prefixes=None):
    return {'name': 'sherpa-onnx', 'kind': 'source', 'filename': path.name,
        'url': 'https://github.com/owned/fixture/archive/fixed.tar.gz',
        **module.attributes(path.read_bytes()), 'archive_root': 'upstream',
        'selected_prefixes': prefixes or [], 'fetchcontent_name': None,
        'notices': {'LICENSE': module.attributes(b'Owned source fixture notice\n')}}


def prepared(module, tmp_path, monkeypatch, *, with_cmake=False, vc_props=None):
    source, inputs, output = tmp_path / 'repo', tmp_path / 'inputs', tmp_path / 'private-run'
    source.mkdir(); inputs.mkdir()
    upstream = (b'  /* Define "empty" TTS symbols */\n'
        b'  m.attr("OfflineTtsMatchaModelConfig") = py::none();\n')
    path = inputs / 'fixture.tar.gz'
    archive(path, {'LICENSE': b'Owned source fixture notice\n', 'owned.c': b'// owned\n',
        'sherpa-onnx/python/csrc/sherpa-onnx.cc': upstream})
    production = module.pin()
    if vc_props is not None:
        production['toolchain']['vc_targets']['default_props'] = module.attributes(vc_props)
    patch = {'file': 'patch.diff', 'sha256': module.sha(b'owned patch identity'),
        'target': 'sherpa-onnx/python/csrc/sherpa-onnx.cc', 'before_sha256': module.sha(upstream),
        'after_sha256': module.sha(upstream.replace(b'  /* Define "empty" TTS symbols */\n',
            b'  /* Define "empty" TTS symbols */\n  m.attr("GenerationConfig") = py::none();\n')
            .replace(b'  m.attr("OfflineTtsMatchaModelConfig") = py::none();\n',
            b'  m.attr("OfflineTtsMatchaModelConfig") = py::none();\n  m.attr("OfflineTtsSupertonicModelConfig") = py::none();\n'))}
    (source / 'patch.diff').write_bytes(b'owned patch identity')
    (source / 'recipe.py').write_bytes(b'# owned recipe\n')
    (source / 'patch-license.txt').write_bytes(b'Owned source fixture notice\n')
    (source / 'patch-notice.txt').write_bytes(b'Owned attribution and modification notice\n')
    patch.update(license_file='patch-license.txt', attribution_file='patch-notice.txt')
    production['patch_notices'] = {name: module.attributes((source / name).read_bytes())
        for name in ('patch-license.txt', 'patch-notice.txt')}
    supplier = source / production['python_supplier_manifest']
    supplier.parent.mkdir(parents=True)
    supplier.write_text(json.dumps({'sha256': '1' * 64, 'supplier_acceptance': 'owned-fixture-pending'}))
    production.update(inputs=[item(module, path)], patch=patch)
    source_files = ('pin.json', 'patch.diff', 'recipe.py', 'patch-license.txt', 'patch-notice.txt')
    for name in module.CMAKE_VARIANT_FILES:
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    source_files += module.CMAKE_VARIANT_FILES
    if with_cmake:
        tool_script = source / 'scripts/pinned-build-cmake.py'
        tool_script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/pinned-build-cmake.py', tool_script)
        tool_policy = source / module.CMAKE_TOOL_POLICY
        tool_policy.parent.mkdir(parents=True, exist_ok=True)
        tool_pin = json.loads((ROOT / module.CMAKE_TOOL_POLICY).read_bytes())
        root = tool_pin['archive']['root']
        payload = {root + '/bin/cmake.exe': b'Owned non-executable CMake fixture',
            root + '/doc/cmake/LICENSE.rst': b'Owned tool notice fixture\n'}
        tool_archive = inputs / tool_pin['archive']['filename']
        with zipfile.ZipFile(tool_archive, 'w') as archive_zip:
            for name, data in payload.items(): archive_zip.writestr(name, data)
        tool_pin['archive'].update(**module.attributes(tool_archive.read_bytes()),
            entries=len(payload), regular_files=len(payload), expanded_bytes=sum(map(len, payload.values())))
        tool_pin['executable'] = {'path': root + '/bin/cmake.exe', **module.attributes(payload[root + '/bin/cmake.exe'])}
        tool_pin['notices'] = [{'path': root + '/doc/cmake/LICENSE.rst',
            **module.attributes(payload[root + '/doc/cmake/LICENSE.rst'])}]
        tool_policy.write_text(json.dumps(tool_pin))
        tool_spec = importlib.util.spec_from_file_location('owned_cmake_fixture', tool_script)
        tool_module = importlib.util.module_from_spec(tool_spec); tool_spec.loader.exec_module(tool_module)
        tool_module.prepare(tool_archive, tmp_path / 'pinned-cmake')
        source_files += (module.CMAKE_TOOL_POLICY, 'scripts/pinned-build-cmake.py')
    manifest = source / 'pin.json'; manifest.write_text(json.dumps(production))
    monkeypatch.setattr(module, 'ROOT', source)
    monkeypatch.setattr(module, 'MANIFEST', 'pin.json')
    monkeypatch.setattr(module, 'SOURCE_FILES', source_files)
    module.prepare(inputs, output)
    return source, inputs, output


def module_variant_fixture(module,tmp_path,monkeypatch):
    source,inputs,output=prepared(module,tmp_path,monkeypatch,with_cmake=True)
    policy=module.pin();variant=policy['cmake_module_variant'];tool=module.cmake_tool_module();supplier=tool.policy()
    original=b'# Authored original module fixture\r\nset(owned "original")\r\n'
    modified=original.replace(b'"original"',b'"corrected"')
    patch=''.join(difflib.unified_diff(original.decode().splitlines(keepends=True),modified.decode().splitlines(keepends=True),
        fromfile='a/'+module.CMAKE_VARIANT_MODULE,tofile='b/'+module.CMAKE_VARIANT_MODULE)).encode()
    license_bytes=b'Owned tool notice fixture\n'
    for key,data in (('patch',patch),('license',license_bytes)):
        (source/variant[key]['path']).write_bytes(data);variant[key].update(module.attributes(data))
    variant.update(before=module.attributes(original),after=module.attributes(modified))
    (source/'pin.json').write_text(json.dumps(policy))
    prefix=supplier['archive']['root']
    contents={prefix+'/bin/cmake.exe':b'Owned non-executable CMake fixture',
        prefix+'/doc/cmake/LICENSE.rst':license_bytes,
        prefix+'/'+module.CMAKE_VARIANT_MODULE:original,prefix+'/share/owned.txt':b'Owned unchanged fixture'}
    archive=inputs/'variant-tool-fixture.zip'
    with zipfile.ZipFile(archive,'w') as z:
        for name,data in contents.items():z.writestr(name,data)
        z.writestr(prefix+'/share/empty/',b'')
    supplier['archive'].update(filename=archive.name,**module.attributes(archive.read_bytes()),
        entries=len(contents)+1,regular_files=len(contents),expanded_bytes=sum(map(len,contents.values())))
    (source/module.CMAKE_TOOL_POLICY).write_text(json.dumps(supplier))
    container=tmp_path/'official-fixture-container';tool.prepare(archive,container)
    monkeypatch.setattr(module.sys,'platform','win32')
    return source,output,tool,container,tmp_path/'separate-module-variant',original,modified


def test_separate_module_variant_preserves_official_tree_and_changes_only_exact_source(module,tmp_path,monkeypatch):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    before=tool.tree(container);payload,summary=module.prepare_cmake_module_variant(container,target)
    assert tool.tree(container)==before and tool.verify(container)['operation']=='verified'
    assert (payload/module.CMAKE_VARIANT_MODULE).read_bytes()==modified
    assert (tool.payload_root(container)/module.CMAKE_VARIANT_MODULE).read_bytes()==original
    assert (payload/'bin/cmake.exe').read_bytes()==(tool.payload_root(container)/'bin/cmake.exe').read_bytes()
    assert (payload/'share/empty').is_dir() and not (target/tool.RECEIPT).exists()
    assert module.verify_cmake_module_variant(container,target)==summary
    assert summary['identity']==module.CMAKE_VARIANT_IDENTITY and summary['regular_files']==4
    assert summary['rights_approval'] is False and summary['source_delivery_approved'] is False
    monkeypatch.setattr(module,'_BUILD_CMAKE_VARIANT',summary)
    assert module.safe_cmake_variant_observation()==summary
    assert str(tmp_path) not in json.dumps(summary) and 'Owned non-executable' not in json.dumps(summary)


@pytest.mark.parametrize('change',['module','executable','notice','extra','missing','empty-directory',
    'original-module','original-archive','patch-source','license-source','notice-source'])
def test_module_variant_refuses_any_payload_supplier_or_bound_source_change(module,tmp_path,monkeypatch,change):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    payload,summary=module.prepare_cmake_module_variant(container,target)
    if change=='module':(payload/module.CMAKE_VARIANT_MODULE).write_bytes(original)
    elif change=='executable':(payload/'bin/cmake.exe').write_bytes(b'private changed executable fixture')
    elif change=='notice':(payload/'doc/cmake/LICENSE.rst').write_bytes(b'private changed notice')
    elif change=='extra':(target/'private-pretend-receipt.json').write_text(json.dumps(summary))
    elif change=='missing':(payload/'share/owned.txt').unlink()
    elif change=='empty-directory':(payload/'share/empty').rmdir()
    elif change=='original-module':(tool.payload_root(container)/module.CMAKE_VARIANT_MODULE).write_bytes(modified)
    elif change=='original-archive':(container/'inputs'/tool.policy()['archive']['filename']).write_bytes(b'private changed archive')
    else:
        key={'patch-source':'patch','license-source':'license','notice-source':'notice'}[change]
        (source/module.pin()['cmake_module_variant'][key]['path']).write_bytes(b'private changed recipe fixture')
    with pytest.raises(ValueError):module.verify_cmake_module_variant(container,target)


@pytest.mark.parametrize('change',['patch','original-module','post-pin','license','existing-output','original-descendant'])
def test_variant_source_refusal_precedes_any_fresh_output_write(module,tmp_path,monkeypatch,change):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    policy=module.pin()
    if change=='patch':(source/policy['cmake_module_variant']['patch']['path']).write_bytes(b'private wrong patch')
    elif change=='original-module':(tool.payload_root(container)/module.CMAKE_VARIANT_MODULE).write_bytes(modified)
    elif change=='post-pin':
        policy['cmake_module_variant']['after']['sha256']='0'*64;(source/'pin.json').write_text(json.dumps(policy))
    elif change=='license':(source/policy['cmake_module_variant']['license']['path']).write_bytes(b'private wrong license')
    elif change=='existing-output':target.mkdir();(target/'owned-sentinel').write_bytes(b'preserved')
    else:target=container/'private-nested-variant'
    with pytest.raises(ValueError):module.prepare_cmake_module_variant(container,target)
    if change=='existing-output':assert (target/'owned-sentinel').read_bytes()==b'preserved'
    else:assert not target.exists()
    if change=='original-descendant':assert tool.verify(container)['operation']=='verified'


@pytest.mark.parametrize('kind',['source-parent','destination-parent','derived-module-parent'])
def test_variant_linked_ancestors_refuse_before_descendant_metadata_or_read(module,tmp_path,monkeypatch,kind):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    if kind=='derived-module-parent':
        payload,_summary=module.prepare_cmake_module_variant(container,target);parent=(payload/module.CMAKE_VARIANT_MODULE).parent
    elif kind=='source-parent':parent=(source/module.CMAKE_VARIANT_FILES[0]).parent
    else:parent=tmp_path/'private-output-parent';parent.mkdir();target=parent/'new-variant'
    real_lstat,real_stat,real_open=Path.lstat,Path.stat,Path.open
    def reject(path):
        if path!=parent and parent in path.parents:pytest.fail('Linked variant ancestors must precede all descendant metadata/read.')
    def lstat_guard(path,*args,**kwargs):
        reject(path)
        if path==parent:return SimpleNamespace(st_mode=module.stat.S_IFDIR,st_file_attributes=0x400)
        return real_lstat(path,*args,**kwargs)
    def stat_guard(path,*args,**kwargs):reject(path);return real_stat(path,*args,**kwargs)
    def open_guard(path,*args,**kwargs):reject(path);return real_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(Path,'stat',stat_guard);monkeypatch.setattr(Path,'open',open_guard)
    with pytest.raises(ValueError):
        if kind=='derived-module-parent':module.verify_cmake_module_variant(container,target)
        else:module.prepare_cmake_module_variant(container,target)


@pytest.mark.parametrize('change',['target','second-hunk','wrong-context'])
def test_exact_module_patch_cannot_select_another_target_or_unreviewed_hunk(module,tmp_path,monkeypatch,change):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    policy=module.pin();variant=policy['cmake_module_variant'];path=source/variant['patch']['path'];patch=path.read_bytes()
    if change=='target':patch=patch.replace(module.CMAKE_VARIANT_MODULE.encode(),b'private-other.cmake')
    elif change=='second-hunk':patch+=b'@@ -1,1 +1,1 @@\n-private\n+private\n'
    else:patch=patch.replace(b'# Authored original module fixture',b'# private unrelated context')
    path.write_bytes(patch);variant['patch'].update(module.attributes(patch));(source/'pin.json').write_text(json.dumps(policy))
    with pytest.raises(ValueError):module.prepare_cmake_module_variant(container,target)
    assert not target.exists()


@pytest.mark.parametrize('change',['path','extra','tree','count-bool','source-pin','policy-extra'])
def test_variant_public_summary_is_rebuilt_from_bound_fields_and_bounded_scalars(module,tmp_path,monkeypatch,change):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    _payload,summary=module.prepare_cmake_module_variant(container,target)
    private='private-profile:'+str(tmp_path)
    if change=='path':summary['module_path']=private
    elif change=='extra':summary['private-field']=private
    elif change=='tree':summary['tree_sha256']=private
    elif change=='count-bool':summary['regular_files']=True
    elif change=='source-pin':summary['before']={'bytes':1,'sha256':'0'*64}
    else:
        policy=module.pin();policy['cmake_module_variant']['patch']['private-field']=private
        (source/'pin.json').write_text(json.dumps(policy));summary['patch']['private-field']=private
    monkeypatch.setattr(module,'_BUILD_CMAKE_VARIANT',summary)
    assert module.safe_cmake_variant_observation() is None


def test_variant_cannot_match_another_official_input_with_the_same_module_and_executable(module,tmp_path,monkeypatch):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    module.prepare_cmake_module_variant(container,target)
    supplier=tool.policy();retained=container/'inputs'/supplier['archive']['filename']
    with zipfile.ZipFile(retained) as z:entries={info.filename:z.read(info) for info in z.infolist()}
    entries[supplier['archive']['root']+'/share/owned.txt']=b'Owned different supplier input'
    different=tmp_path/'different-original.zip'
    with zipfile.ZipFile(different,'w') as z:
        for name,data in entries.items():z.writestr(name,data)
    supplier['archive'].update(filename=different.name,**module.attributes(different.read_bytes()),
        expanded_bytes=sum(map(len,entries.values())))
    (source/module.CMAKE_TOOL_POLICY).write_text(json.dumps(supplier))
    second=tmp_path/'different-original-container';tool.prepare(different,second)
    with pytest.raises(ValueError):module.verify_cmake_module_variant(second,target)


def test_native_variant_materialization_is_unavailable_on_non_windows_hosts(module,tmp_path,monkeypatch):
    source,output,tool,container,target,original,modified=module_variant_fixture(module,tmp_path,monkeypatch)
    monkeypatch.setattr(module.sys,'platform','darwin')
    with pytest.raises(ValueError):module.prepare_cmake_module_variant(container,target)
    assert not target.exists()


def test_asr_recipe_binds_shared_cmake_policy_helper_and_verified_fixture_tree(module, tmp_path, monkeypatch):
    source, _inputs, output = prepared(module, tmp_path, monkeypatch, with_cmake=True)
    tool_policy = json.loads((source / module.CMAKE_TOOL_POLICY).read_bytes())
    container = tmp_path / 'pinned-cmake'; payload = container / tool_policy['archive']['root']
    verified = module.verify_pinned_cmake(container, payload)
    assert verified['operation'] == 'verified' and verified['version'] == '4.4.5'
    assert verified['runtime_collection_allowed'] is False
    assert verified['production_execution_allowed'] is False
    receipt = module.verify_sources(output)
    for name in (module.CMAKE_TOOL_POLICY, 'scripts/pinned-build-cmake.py'):
        assert receipt['source_inputs'][name] == module.attributes((source / name).read_bytes())
        assert (output / 'recipes' / name).read_bytes() == (source / name).read_bytes()
    assert not list((output / 'recipes').rglob('*.zip'))
    assert not list((output / 'recipes').rglob('*.exe'))
    assert str(tmp_path) not in json.dumps(verified)


@pytest.mark.parametrize('changed', ['selected-payload', 'native-bytes', 'retained-zip', 'recipe-policy', 'recipe-helper'])
def test_asr_rejects_unbound_or_changed_shared_cmake_inputs(module, tmp_path, monkeypatch, changed):
    source, _inputs, output = prepared(module, tmp_path, monkeypatch, with_cmake=True)
    tool_policy = json.loads((source / module.CMAKE_TOOL_POLICY).read_bytes())
    container = tmp_path / 'pinned-cmake'; payload = container / tool_policy['archive']['root']
    if changed == 'selected-payload': payload = tmp_path / 'ambient-cmake'
    if changed == 'native-bytes': (container / tool_policy['executable']['path']).write_bytes(b'changed')
    if changed == 'retained-zip': (container / 'inputs' / tool_policy['archive']['filename']).write_bytes(b'changed')
    if changed.startswith('recipe-'):
        name = module.CMAKE_TOOL_POLICY if changed == 'recipe-policy' else 'scripts/pinned-build-cmake.py'
        (source / name).write_bytes(b'changed')
        with pytest.raises(ValueError): module.verify_sources(output)
    else:
        with pytest.raises(ValueError): module.verify_pinned_cmake(container, payload)


def test_exact_preparation_patch_notice_and_pending_gates(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    report = module.verify_sources(output)
    assert report['status'] == 'prepared-not-built'
    assert report['rights_approval'] is False
    assert report['gates']['production_execution_allowed'] is False
    assert report['gates']['runtime_collection_allowed'] is False
    assert report['gates']['native_windows_11_acceptance'] == 'unavailable'
    assert report['gates']['r19_complete'] is False
    assert (output / 'notices/sherpa-onnx/LICENSE').read_bytes() == b'Owned source fixture notice\n'
    assert (output / 'recipes/patch-license.txt').read_bytes() == b'Owned source fixture notice\n'
    assert (output / 'recipes/patch-notice.txt').read_bytes() == b'Owned attribution and modification notice\n'
    patched = (output / 'sources/sherpa-onnx/sherpa-onnx/python/csrc/sherpa-onnx.cc').read_bytes()
    assert b'm.attr("GenerationConfig") = py::none();' in patched
    assert b'm.attr("OfflineTtsSupertonicModelConfig") = py::none();' in patched
    assert str(tmp_path) not in json.dumps(report)


@pytest.mark.parametrize('changed', ['source', 'notice', 'archive', 'recipe', 'copied-recipe', 'gates', 'patch-license', 'patch-attribution'])
def test_changed_input_or_delivered_notice_rejected(module, tmp_path, monkeypatch, changed):
    source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    target = {'source': output / 'sources/sherpa-onnx/owned.c',
        'notice': output / 'notices/sherpa-onnx/LICENSE', 'archive': output / 'fixture.tar.gz',
        'recipe': source / 'recipe.py', 'copied-recipe': output / 'recipes/recipe.py',
        'patch-license': source / 'patch-license.txt', 'patch-attribution': source / 'patch-notice.txt'}.get(changed)
    if target:
        target.write_bytes(b'changed')
    else:
        report = module.read_json(output / 'PREPARED.json')
        report['gates']['r19_complete'] = True
        module.write_json(output / 'PREPARED.json', report)
    with pytest.raises(ValueError):
        module.verify_sources(output)


def test_public_patch_license_must_remain_the_complete_upstream_text_before_any_write(module, tmp_path, monkeypatch):
    source, inputs, _output = prepared(module, tmp_path, monkeypatch)
    (source / 'patch-license.txt').write_bytes(b'truncated license')
    new_output = tmp_path / 'must-not-be-created'
    with pytest.raises(ValueError): module.prepare(inputs, new_output)
    assert not new_output.exists()


@pytest.mark.parametrize('invalid', ['traversal', 'link', 'case', 'notice', 'hash', 'file-parent'])
def test_exact_archive_scope_rejects_unsafe_or_unbound_input(module, tmp_path, invalid):
    path = tmp_path / 'input.tar.gz'
    files = {'LICENSE': b'Owned source fixture notice\n', 'owned.c': b'// owned\n'}
    if invalid == 'traversal': files['../outside'] = b'outside'
    if invalid == 'case': files.update({'Dir/a': b'a', 'dir/b': b'b'})
    if invalid == 'file-parent': files.update({'dir': b'a', 'dir/b': b'b'})
    archive(path, files, link='selected-link' if invalid == 'link' else None)
    record = item(module, path)
    if invalid == 'notice': record['notices']['LICENSE']['sha256'] = '0' * 64
    if invalid == 'hash': record['sha256'] = '0' * 64
    with pytest.raises(ValueError): module.archive_files(path, record)
    assert not (tmp_path / 'outside').exists()


def test_unselected_main_platform_link_cannot_enter_selected_source(module, tmp_path):
    path = tmp_path / 'input.tar.gz'
    archive(path, {'LICENSE': b'Owned source fixture notice\n', 'source/owned.c': b'// owned\n'}, link='android/link')
    files = module.archive_files(path, item(module, path, prefixes=['LICENSE', 'source']))
    assert set(files) == {'LICENSE', 'source/owned.c'}


def trace(module, path, extra=None, *, omit=None):
    events = []
    for record in module.pin()['inputs']:
        name = record['fetchcontent_name']
        if name and name != omit:
            events += [{'cmd': 'FetchContent_Declare', 'args': [name]},
                {'cmd': 'FetchContent_Populate', 'args': [name]}]
    if extra: events.append(extra)
    path.write_text('\n'.join(json.dumps(e) for e in events))


@pytest.mark.parametrize('change', ['unknown-fetch', 'network', 'downloader', 'missing'])
def test_source_graph_does_not_accept_unreviewed_or_incomplete_fetch(module, tmp_path, change):
    path = tmp_path / 'trace.jsonl'
    extra = {'unknown-fetch': {'cmd': 'FetchContent_Declare', 'args': ['espeak-ng']},
        'network': {'cmd': 'file', 'args': ['DOWNLOAD', 'https://example.test/file']},
        'downloader': {'cmd': 'execute_process', 'args': ['COMMAND', 'curl', 'https://example.test/file']}}.get(change)
    trace(module, path, extra, omit='kissfft' if change == 'missing' else None)
    with pytest.raises(ValueError): module.verify_trace(path, tmp_path)


def test_exact_source_graph_keeps_no_network_sandbox_or_rights_claim(module, tmp_path):
    path = tmp_path / 'trace.jsonl'; trace(module, path)
    report = module.verify_trace(path, tmp_path)
    assert 'simple-sentencepiece' in report['populated']
    assert report['network_sandbox'] is False
    assert 'espeak-ng' not in report['declared']


def test_actual_cache_cannot_enable_tts_or_select_an_ambient_source(module, tmp_path):
    lines = [f'{k}:STRING={v}' for k, v in module.pin()['cmake'].items()]
    lines += ['FETCHCONTENT_SOURCE_DIR_' + i['fetchcontent_name'].upper() + ':PATH=' +
        str(tmp_path / 'sources' / i['name']) for i in module.pin()['inputs'] if i['fetchcontent_name']]
    cache = tmp_path / 'CMakeCache.txt'; cache.write_text('\n'.join(lines))
    module.verify_cache(cache, tmp_path)
    cache.write_text('\n'.join(lines).replace('SHERPA_ONNX_ENABLE_TTS:STRING=OFF', 'SHERPA_ONNX_ENABLE_TTS:STRING=ON'))
    with pytest.raises(ValueError): module.verify_cache(cache, tmp_path)
    cache.write_text('\n'.join(lines).replace(str(tmp_path / 'sources/kissfft'), str(tmp_path / 'ambient/kissfft')))
    with pytest.raises(ValueError): module.verify_cache(cache, tmp_path)


@pytest.mark.parametrize('bad', ['espeak-export', 'piper-import', 'ambient-crt', 'private-path'])
def test_native_scope_requires_actual_python_binding_and_bounded_imports(module, bad):
    evidence = {'imports': ['KERNEL32.dll', 'onnxruntime.dll', 'python312.dll'],
        'delay_imports': [], 'exports': ['PyInit__sherpa_onnx']}
    module.validate_native(evidence)
    if bad == 'espeak-export': evidence['exports'].append('espeak_Initialize')
    if bad == 'piper-import': evidence['imports'].append('piper.dll')
    if bad == 'ambient-crt': evidence['imports'].append('VCRUNTIME140.dll')
    if bad == 'private-path': evidence['exports'].append('C:/r19-authored-private/export')
    with pytest.raises(ValueError): module.validate_native(evidence)


@pytest.mark.parametrize('name', ['espeak_Initialize', 'espeak_ng_Synthesize',
    '__imp_espeak_Initialize', '?phonemize_eSpeak@piper@@YAX', '?phonemize_codepoints@piper@@YAX',
    'espeak-ng.lib', 'libespeak-ng.dll', '_deps/espeak_ng-build/Release/espeak-ng.lib',
    'piper_phonemize.lib', 'cmake/piper-phonemize.cmake', 'PiperPhonemizeLexicon',
    '?PiperPhonemesToIdsVits@sherpa_onnx@@', 'phonemizer'])
def test_native_tts_predicate_retains_real_api_library_path_and_mangled_name_rejection(module, name):
    assert module.native_tts_name(name)


@pytest.mark.parametrize('name', ['OfflineSpeakerDiarization', 'PybindOfflineSpeakerDiarization',
    '?PybindOfflineSpeakerDiarization@sherpa_onnx@@YAX', '??_7OfflineSpeakerDiarization@sherpa_onnx@@',
    'offline-speaker-diarization.cc', 'SpeakerEmbeddingExtractor'])
def test_native_tts_predicate_preserves_authored_asr_speaker_identifiers(module, name):
    assert not module.native_tts_name(name)


def test_linkmap_shaped_tts_evidence_remains_rejected_without_offline_speaker_false_positive(module):
    retained = (' 0001:00001234 ?PybindOfflineSpeakerDiarization@sherpa_onnx@@ 0000000180001234 f _sherpa_onnx.obj\n'
        ' 0002:00000020 ??_7OfflineSpeakerDiarization@sherpa_onnx@@ 0000000180010020 core.lib\n')
    assert not module.native_tts_name(retained)
    for native in ('espeak_Initialize', '__imp_espeak_ng_Synthesize', '?phonemize_eSpeak@piper@@YAX'):
        assert module.native_tts_name(retained + ' 0001:00004567 ' + native + ' 0000000180004567 f espeak-ng.lib\n')


def test_toolchain_summary_hides_private_roots_and_detects_changed_bytes(module, tmp_path):
    roots = {}
    for name in ['vc', 'vc-auxiliary', 'msbuild', 'sdk-include', 'sdk-lib', 'sdk-bin', 'cmake', 'python']:
        path = tmp_path / 'private-owner' / name; path.mkdir(parents=True)
        (path / 'owned-fixture.txt').write_bytes(b'owned-tool-fixture')
        roots[name] = str(path)
    first = module.seal_toolchain(roots)
    public = module.toolchain_summary(first)
    assert 'private-owner' not in repr(public)
    assert str(tmp_path) not in repr(public)
    (Path(roots['vc']) / 'owned-fixture.txt').write_bytes(b'changed-tool-fixture')
    assert first != module.seal_toolchain(roots)


@pytest.mark.parametrize('invalid', ['array', 'empty-array', 'missing', 'file', 'extra-root'])
def test_tool_roots_reject_ambiguous_or_unavailable_selection_before_inventory(module, tmp_path, monkeypatch, invalid):
    roots = {}
    for name in ['vc', 'vc-auxiliary', 'msbuild', 'sdk-include', 'sdk-lib', 'sdk-bin', 'cmake', 'python']:
        path = tmp_path / name; path.mkdir()
        roots[name] = str(path)
    if invalid == 'array': roots['cmake'] = [roots['cmake'], roots['vc']]
    if invalid == 'empty-array': roots['cmake'] = []
    if invalid == 'missing': roots['cmake'] = str(tmp_path / 'missing')
    if invalid == 'file':
        file = tmp_path / 'owned-tool.exe'; file.write_bytes(b'owned non-executable fixture')
        roots['cmake'] = str(file)
    if invalid == 'extra-root': roots['ambient'] = roots['vc']
    def no_inventory(_path):
        pytest.fail('No source/tool bytes may be inventoried before root selection is unambiguous.')
    monkeypatch.setattr(module, 'inventory', no_inventory)
    with pytest.raises(ValueError): module.seal_toolchain(roots)


def selected_vs_fixture(module, tmp_path, monkeypatch):
    instance = tmp_path / 'authored VS18'
    roots = {}
    for name, relative in {'vc': 'VC/Tools/MSVC/' + module.pin()['toolchain']['vc_tools_version'],
            'vc-auxiliary': 'VC/Auxiliary', 'msbuild': 'MSBuild'}.items():
        path = instance / relative; path.mkdir(parents=True)
        roots[name] = str(path)
    for name in ('sdk-include', 'sdk-lib', 'sdk-bin', 'cmake', 'python'):
        path = tmp_path / name; path.mkdir(); roots[name] = str(path)
    machine = tmp_path / 'authored Program Files x86'
    tool = machine / 'Microsoft Visual Studio/Installer/vswhere.exe'
    tool.parent.mkdir(parents=True); tool.write_bytes(b'owned non-executable query fixture')
    monkeypatch.setenv('ProgramFiles(x86)', str(machine))
    version = '18.11.12315.225'
    observed = [{'installationPath': str(instance), 'installationVersion': version,
        'displayName': 'private ignored instance metadata'}]
    def query(command, **kwargs):
        assert command == [str(tool), '-latest', '-products', '*', '-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-format', 'json', '-utf8']
        assert kwargs['stderr'] == module.subprocess.STDOUT and kwargs['timeout'] == 30
        return json.dumps(observed).encode()
    monkeypatch.setattr(module.subprocess, 'check_output', query)
    return instance, version, tool, roots, observed


def test_vs_instance_argument_uses_requeried_real_selection_and_sealed_root_binding(module, tmp_path, monkeypatch):
    instance, version, tool, roots, _ = selected_vs_fixture(module, tmp_path, monkeypatch)
    result = module.verify_vs_selection(instance, version, tool, roots)
    assert result == {'installation_version': version, 'vswhere': module.attributes(tool.read_bytes())}
    assert module.verify_vs_selection(instance, version, tool, roots, result) == result
    assert module.cmake_instance_spec(instance, version) == instance.resolve().as_posix() + ',version=' + version
    assert str(tmp_path) not in json.dumps(result) and 'private' not in json.dumps(result)


@pytest.mark.parametrize('version', [None, 18, ['18.11.12315.225'], '17.11.12315.225',
    '18.11.12315', '18.11.12315.225.1', '18.11.12315.225\n', '18.11.private.225',
    '18.11.12315.225,version=18.0.0.0'])
def test_vs_instance_argument_refuses_noncanonical_or_wrong_major_version_before_query(module, tmp_path, monkeypatch, version):
    instance, _, tool, roots, _ = selected_vs_fixture(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_a, **_k: pytest.fail('Malformed selection must not execute a query.'))
    with pytest.raises(ValueError): module.verify_vs_selection(instance, version, tool, roots)


@pytest.mark.parametrize('role', ['vc', 'vc-auxiliary', 'msbuild', 'instance-root', 'query-origin'])
def test_vs_instance_cannot_choose_foreign_root_or_query_executable(module, tmp_path, monkeypatch, role):
    instance, version, tool, roots, _ = selected_vs_fixture(module, tmp_path, monkeypatch)
    other = tmp_path / 'foreign instance'; other.mkdir()
    if role in roots: roots[role] = str(other)
    if role == 'instance-root': instance = other
    if role == 'query-origin':
        tool = other / 'vswhere.exe'; tool.write_bytes(b'owned foreign query fixture')
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_a, **_k: pytest.fail('Foreign origin must not execute a query.'))
    with pytest.raises(ValueError): module.verify_vs_selection(instance, version, tool, roots)


@pytest.mark.parametrize('change', ['version', 'root', 'multiple', 'query-bytes-during-query', 'query-bytes-before-final-query'])
def test_vs_selection_refuses_different_actual_identity_or_changed_query_bytes(module, tmp_path, monkeypatch, change):
    instance, version, tool, roots, observed = selected_vs_fixture(module, tmp_path, monkeypatch)
    initial = module.verify_vs_selection(instance, version, tool, roots)
    if change == 'version': observed[0]['installationVersion'] = '18.11.12316.225'
    if change == 'root':
        other = tmp_path / 'foreign actual instance'; other.mkdir(); observed[0]['installationPath'] = str(other)
    if change == 'multiple': observed.append(dict(observed[0]))
    if change == 'query-bytes-before-final-query': tool.write_bytes(b'changed owned query fixture')
    if change == 'query-bytes-during-query':
        def query(*_a, **_k):
            tool.write_bytes(b'changed owned query fixture'); return json.dumps(observed).encode()
        monkeypatch.setattr(module.subprocess, 'check_output', query)
    with pytest.raises(ValueError): module.verify_vs_selection(instance, version, tool, roots, initial)


@pytest.mark.parametrize('change', ['root', 'version'])
def test_configured_instance_must_retain_exact_selected_path_and_version(module, tmp_path, change):
    instance = tmp_path / 'authored VS18'; instance.mkdir()
    spec = module.cmake_instance_spec(instance, '18.11.12315.225')
    lines = [f'{k}:STRING={v}' for k, v in module.pin()['cmake'].items()]
    lines += ['FETCHCONTENT_SOURCE_DIR_' + i['fetchcontent_name'].upper() + ':PATH=' +
        str(tmp_path / 'sources' / i['name']) for i in module.pin()['inputs'] if i['fetchcontent_name']]
    lines.append('CMAKE_GENERATOR_INSTANCE:INTERNAL=' + spec)
    cache = tmp_path / 'CMakeCache.txt'; cache.write_text('\n'.join(lines))
    module.verify_cache(cache, tmp_path, spec)
    wrong = spec.replace('authored VS18', 'foreign VS18') if change == 'root' else spec.replace('12315', '12316')
    cache.write_text('\n'.join(lines).replace(spec, wrong))
    with pytest.raises(ValueError): module.verify_cache(cache, tmp_path, spec)


@pytest.mark.parametrize('observed,expected', [('18.11.12315.225', '18.11.12315.225'),
    ('C:/r19-authored-private/instance-version', None), ('18.11.12315.225\n', None)])
def test_failed_vs_metadata_keeps_only_strict_numeric_label(module, tmp_path, monkeypatch, observed, expected):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, '_BUILD_VS_VERSION', observed)
    report = module.failed_build_receipt(output, 'vs-installation-origin', ValueError('private root/version data'))
    assert report['visual_studio_instance_version'] == expected
    assert report['status'] == 'failed' and report['native_reference_probes_passed'] is False
    delivered = (output / 'ASR-FAILURE.json').read_text()
    assert str(tmp_path) not in delivered and 'r19-authored-private' not in delivered
    assert 'private root/version' not in delivered and not (output / 'ASR-RECEIPT.json').exists()


@pytest.mark.parametrize('observed,valid', [('4.4.5', True), ('4.4.4', False)])
def test_cmake_numeric_observation_preserves_exact_constraint_without_private_text(module, tmp_path, monkeypatch, observed, valid):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    executable = tmp_path / 'private-directory/cmake.exe'; executable.parent.mkdir()
    executable.write_bytes(b'owned non-executable CMake fixture with private model text')
    def version_query(command, **kwargs):
        assert command == [str(executable), '--version']
        assert kwargs['stderr'] == module.subprocess.STDOUT and kwargs['timeout'] == 30
        return 'cmake version ' + observed + '\nprivate directory/model/exception text\n'
    monkeypatch.setattr(module.subprocess, 'check_output', version_query)
    if valid:
        observation = module.observe_cmake_version(executable, '4.4.5')
    else:
        with pytest.raises(ValueError): module.observe_cmake_version(executable, '4.4.5')
        report = module.failed_build_receipt(output, 'cmake-version-review', ValueError('private exception'))
        assert report['status'] == 'failed' and report['native_reference_probes_passed'] is False
        observation = report['cmake_observation']
        assert not (output / 'ASR-RECEIPT.json').exists()
    assert observation == {'expected_version': '4.4.5', 'observed_version': observed,
        'executable': module.attributes(executable.read_bytes())}
    assert str(tmp_path) not in json.dumps(observation) and 'private' not in json.dumps(observation)
    assert module.pin()['toolchain']['cmake_version'] == '4.4.5'


def test_cmake_observation_never_serializes_raw_version_output_or_unbounded_private_state(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    executable = tmp_path / 'cmake.exe'; executable.write_bytes(b'owned executable fixture')
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *_args, **_kwargs:
        'cmake version 4.4.5/private-model-and-path\n')
    with pytest.raises(ValueError): module.observe_cmake_version(executable, '4.4.5')
    assert module.safe_cmake_observation()['observed_version'] is None
    monkeypatch.setattr(module, '_BUILD_CMAKE_OBSERVATION', {'expected_version': '4.4.5',
        'observed_version': str(tmp_path / 'private-model'),
        'executable': {**module.attributes(executable.read_bytes()), 'path': str(executable)},
        'raw_output': 'private model and log text'})
    report = module.failed_build_receipt(output, 'cmake-version-review', ValueError('private message'))
    assert report['cmake_observation']['observed_version'] is None
    delivered = (output / 'ASR-FAILURE.json').read_text()
    assert str(tmp_path) not in delivered and 'private' not in delivered and 'raw_output' not in delivered


@pytest.mark.parametrize('labels', [[], ['v170'], ['v170', 'v180']])
def test_vc_target_diagnostics_keep_selected_pin_guard_and_collect_parent_categories_before_refusal(module, tmp_path, monkeypatch, labels):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    msbuild = tmp_path / 'msbuild'; msbuild.mkdir()
    for label in labels:
        props = msbuild / 'Microsoft/VC' / label / 'Microsoft.Cpp.Default.props'
        props.parent.mkdir(parents=True); props.write_bytes(('Owned props fixture ' + label).encode())
    (output.parent / 'Directory.Build.targets').write_bytes(b'owned parent import fixture')
    with pytest.raises(ValueError): module.review_vc_targets(output, msbuild)
    assert module._BUILD_PHASE == 'vc-target-selection'
    report = module.failed_build_receipt(output, module._BUILD_PHASE, ValueError('private failure text'))
    observation = report['build_environment_observation']
    assert observation['vc_targets']['candidate_count'] == len(labels)
    assert [v['label'] for v in observation['vc_targets']['candidates']] == labels
    assert observation['vc_targets']['selected_family'] == 'v180'
    assert observation['vc_targets']['selected_props_pin_matched'] is False
    assert observation['parent_import_categories'] == ['Directory.Build.targets']
    for candidate in observation['vc_targets']['candidates']:
        props = msbuild / 'Microsoft/VC' / candidate['label'] / 'Microsoft.Cpp.Default.props'
        assert candidate['props'] == module.attributes(props.read_bytes())
    assert str(tmp_path) not in json.dumps(observation)
    assert report['status'] == 'failed' and not (output / 'ASR-RECEIPT.json').exists()


def test_single_vc_target_does_not_bypass_parent_import_gate(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch, vc_props=b'owned props fixture')
    msbuild = tmp_path / 'msbuild'
    props = msbuild / 'Microsoft/VC/v180/Microsoft.Cpp.Default.props'
    props.parent.mkdir(parents=True); props.write_bytes(b'owned props fixture')
    (output.parent / 'MSBuild.rsp').write_bytes(b'owned response fixture')
    assert module.review_vc_targets(output, msbuild) == [props]
    module.build_phase('parent-import-review')
    with pytest.raises(ValueError): module.reject_parent_imports(output)
    report = module.failed_build_receipt(output, module._BUILD_PHASE, ValueError('owned refusal'))
    assert report['phase'] == 'parent-import-review'
    assert report['build_environment_observation']['parent_import_categories'] == ['MSBuild.rsp']


def test_explicit_pinned_vc_family_is_selected_among_other_sealed_families_without_latest_fallback(module, tmp_path, monkeypatch):
    data = b'owned selected props fixture'
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch, vc_props=data)
    msbuild = tmp_path / 'msbuild'
    for label in ('v160', 'v170', 'v180', 'v999'):
        props = msbuild / 'Microsoft/VC' / label / 'Microsoft.Cpp.Default.props'
        props.parent.mkdir(parents=True)
        props.write_bytes(data if label == 'v180' else b'owned unselected props fixture')
    selected = msbuild / 'Microsoft/VC/v180/Microsoft.Cpp.Default.props'
    assert module.review_vc_targets(output, msbuild) == [selected]
    observation = module.safe_build_environment_observation()['vc_targets']
    assert observation['candidate_count'] == 4
    assert [v['label'] for v in observation['candidates']] == ['v160', 'v170', 'v180', 'v999']
    assert observation['selected_family'] == 'v180' and observation['selected_candidate_count'] == 1
    assert observation['selected_props_pin_matched'] is True
    assert str(tmp_path) not in json.dumps(observation)


@pytest.mark.parametrize('changed', ['missing', 'props-bytes', 'props-size', 'family-case-alias', 'props-case-alias'])
def test_selected_vc_family_refuses_missing_changed_or_aliased_props(module, tmp_path, monkeypatch, changed):
    data = b'owned selected props fixture'
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch, vc_props=data)
    msbuild = tmp_path / 'msbuild'
    props = msbuild / 'Microsoft/VC/v180/Microsoft.Cpp.Default.props'
    if changed == 'family-case-alias': props = props.parent.with_name('V180') / props.name
    if changed == 'props-case-alias': props = props.with_name('microsoft.cpp.default.props')
    props.parent.mkdir(parents=True)
    props.write_bytes(data)
    if changed == 'missing': props.unlink()
    if changed == 'props-bytes': props.write_bytes(data.replace(b'owned', b'other'))
    if changed == 'props-size': props.write_bytes(data + b' changed')
    with pytest.raises(ValueError): module.review_vc_targets(output, msbuild)
    assert module.safe_build_environment_observation()['vc_targets']['selected_props_pin_matched'] is False


def test_duplicate_selected_vc_discovery_records_are_refused_even_with_matching_fixture_bytes(module, tmp_path, monkeypatch):
    data = b'owned selected props fixture'
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch, vc_props=data)
    msbuild = tmp_path / 'msbuild'
    props = msbuild / 'Microsoft/VC/v180/Microsoft.Cpp.Default.props'
    props.parent.mkdir(parents=True); props.write_bytes(data)
    glob = Path.glob
    def duplicate_selected(base, pattern):
        found = list(glob(base, pattern))
        return found + found if base == msbuild / 'Microsoft/VC' else found
    monkeypatch.setattr(Path, 'glob', duplicate_selected)
    with pytest.raises(ValueError): module.review_vc_targets(output, msbuild)
    observation = module.safe_build_environment_observation()['vc_targets']
    assert observation['selected_candidate_count'] == 2
    assert observation['selected_props_pin_matched'] is False


def test_build_environment_projection_cannot_publish_unknown_labels_paths_or_raw_props(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, '_BUILD_ENVIRONMENT_OBSERVATION', {'vc_targets': {
        'candidate_count': 1, 'selected_family': str(tmp_path / 'private-target'),
        'selected_candidate_count': 'private count', 'selected_props_pin_matched': 'private result',
        'candidates': [{'label': 'v-private-tenant',
            'props': {**module.attributes(b'owned props'), 'contents': 'private model text'},
            'path': str(tmp_path / 'private-props')}]},
        'parent_import_categories': ['Directory.Build.props', str(tmp_path / 'private-import'),
            {'unexpected': 'private object'}], 'raw_exception': 'private exception text'})
    report = module.failed_build_receipt(output, 'vc-target-selection', ValueError('private error'))
    observation = report['build_environment_observation']
    assert observation['vc_targets']['candidates'] == [{'label': None, 'props': module.attributes(b'owned props')}]
    assert observation['vc_targets']['selected_family'] is None
    assert observation['vc_targets']['selected_candidate_count'] is None
    assert observation['vc_targets']['selected_props_pin_matched'] is False
    assert observation['parent_import_categories'] == ['Directory.Build.props']
    delivered = (output / 'ASR-FAILURE.json').read_text()
    assert str(tmp_path) not in delivered and 'private' not in delivered and 'contents' not in delivered


def test_actual_python_tree_must_match_supplier_archive_not_only_version(module, tmp_path, monkeypatch):
    source = tmp_path / 'source'; source.mkdir()
    archive_path = tmp_path / 'python.tar.gz'
    archive(archive_path, {'python.exe': b'owned non-executable interpreter fixture',
        'include/Python.h': b'owned header'}, root='python')
    (source / 'supplier.json').write_text(json.dumps({'archive': archive_path.name,
        'sha256': module.sha(archive_path.read_bytes())}))
    monkeypatch.setattr(module, 'ROOT', source)
    monkeypatch.setattr(module, 'pin', lambda: {'python_supplier_manifest': 'supplier.json'})
    output = tmp_path / 'supplier-extracted'
    module.prepare_python(archive_path, output)
    module.verify_python(tmp_path, output / 'python')
    (output / 'python/sitecustomize.py').write_bytes(b'# ambient extra file')
    with pytest.raises(ValueError): module.verify_python(tmp_path, output / 'python')


@pytest.mark.parametrize('timeout', [False, True])
def test_private_command_is_owned_before_spawn_and_drained_even_on_timeout(module, tmp_path, monkeypatch, timeout):
    events = []
    class Owner:
        def command(self, value):
            events.append('wrap-before-spawn')
            return ['owned-bootstrap', *value]
        def terminate(self, **_kwargs): events.append('drain-owned-job')
        def close(self): events.append('close-owned-job')
    class Process:
        def __init__(self): self.code = None
        def wait(self, **_kwargs):
            if timeout and self.code is None:
                raise module.subprocess.TimeoutExpired('owned-command', 1)
            self.code = 0 if not timeout else 1
            events.append('reap-bootstrap')
            return self.code
        def poll(self): return self.code
        def kill(self):
            events.append('kill-owned-bootstrap')
            self.code = 1
    def popen(command, **kwargs):
        assert command == ['owned-bootstrap', 'owned-command']
        assert kwargs['stdout'] is not None
        events.append('spawn-bootstrap')
        return Process()
    monkeypatch.setattr(module, 'process_owner', Owner)
    monkeypatch.setattr(module.subprocess, 'Popen', popen)
    monkeypatch.setattr(module.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    if timeout:
        with pytest.raises(module.subprocess.TimeoutExpired):
            module.run_private(['owned-command'], tmp_path / 'private.log', {}, tmp_path, 1)
        assert events.index('kill-owned-bootstrap') < events.index('reap-bootstrap')
    else:
        module.run_private(['owned-command'], tmp_path / 'private.log', {}, tmp_path, 1)
    assert events.index('wrap-before-spawn') < events.index('spawn-bootstrap')
    assert events.index('reap-bootstrap') < events.index('drain-owned-job') < events.index('close-owned-job')


def test_parent_msbuild_import_is_rejected_and_preserved(module, tmp_path):
    parent = tmp_path / 'parent'; parent.mkdir()
    output = parent / 'owned'; output.mkdir()
    ambient = parent / 'Directory.Build.targets'; ambient.write_bytes(b'owned ambient-import fixture')
    with pytest.raises(ValueError): module.reject_parent_imports(output)
    assert ambient.read_bytes() == b'owned ambient-import fixture'


def test_private_command_cleanup_failure_cannot_be_reported_as_success(module, tmp_path, monkeypatch):
    events = []
    class Owner:
        def command(self, value): return value
        def terminate(self, **_kwargs):
            events.append('unconfirmed-drain')
            raise OSError('owned cleanup failure fixture')
        def close(self): events.append('close-handle-only')
    class Process:
        def wait(self, **_kwargs): return 0
        def poll(self): return 0
    monkeypatch.setattr(module, 'process_owner', Owner)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(module.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    with pytest.raises(OSError, match='owned cleanup failure fixture'):
        module.run_private(['owned-command'], tmp_path / 'private.log', {}, tmp_path, 1)
    assert events == ['unconfirmed-drain', 'close-handle-only']


def test_failed_receipt_contains_only_fixed_phase_known_codes_and_categories(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    logs = output / 'private-logs'; logs.mkdir()
    raw = (str(tmp_path / 'private-profile/model-secret.onnx') + '\n'
        'fatal error C1083: raw private missing-header text\n'
        'error LNK1104: raw private library text\n'
        'error MSB8020: raw private toolchain text\n'
        'error C9999: unrecognized code must not leave the host\n'
        'CMake Error at private-profile/private-build.cmake:42\n'
        'Configuring incomplete, errors occurred!\n'
        '[ONNXRuntimeError]: private model text\n')
    (logs / 'configure.log').write_text(raw)
    monkeypatch.setattr(module, '_BUILD_SOURCE_COMMIT', 'private-profile/not-a-commit')
    report = module.failed_build_receipt(output, 'cmake-configure', OSError(raw))
    delivered = (output / 'ASR-FAILURE.json').read_text()
    assert report['schema'] == 'proxy-r19-asr-source-failure-v1' and report['status'] == 'failed'
    assert report['phase'] == 'cmake-configure'
    assert report['failure_category'] == 'io-or-cleanup-unconfirmed'
    assert report['diagnostics']['known_codes'] == ['C1083', 'LNK1104', 'MSB8020']
    assert 'cmake-error' in report['diagnostics']['categories']
    assert 'onnx-native-error' in report['diagnostics']['categories']
    assert 'unclassified-tool-error' in report['diagnostics']['categories']
    assert report['source_commit'] is None
    assert report['native_reference_probes_passed'] is False
    assert report['success_receipt_for_this_attempt'] is False
    assert report['gates']['production_execution_allowed'] is False
    assert report['gates']['runtime_collection_allowed'] is False
    assert report['gates']['r19_complete'] is False and report['rights_approval'] is False
    for private in [str(tmp_path), 'private-profile', 'model-secret', 'private missing-header', 'C9999']:
        assert private not in delivered
    assert not (output / 'ASR-RECEIPT.json').exists()


@pytest.mark.parametrize('label,body', [
    ('cmake-generator-unavailable', 'Could not create named generator private-generator'),
    ('cmake-vs-instance-not-found', 'Generator Visual Studio 18 2026 could not find specified instance of Visual Studio:\n  {private}'),
    ('cmake-vs-installation-not-found', 'Generator Visual Studio 18 2026 could not find any instance of Visual Studio.'),
    ('cmake-vs-installer-instance-unknown', "The directory exists, but the instance is not known to the Visual Studio Installer, and no 'version=' field was given."),
    ('cmake-vs-instance-version-invalid', 'given instance specification {private} but the version field is not 4 integer components starting in 18.'),
    ('cmake-vs-instance-fields-invalid', "given instance specification {private} that contains invalid field 'private-model'."),
    ('cmake-msbuild-vctargets-query-failed', 'Failed to run MSBuild command:\n  {private}\nto get the value of VCTargetsPath:'),
    ('cmake-toolset-version-invalid', 'given toolset and version specification v145,version=14.51.36231 contains an invalid version specification.'),
    ('cmake-toolset-not-installed', 'given toolset and version specification v145,version=14.51.36231 does not seem to be installed at\n  {private}'),
    ('cmake-toolset-selection-ambiguous', 'given toolset and version specification {private} has multiple matches installed at {private}\nThe toolset and version specification must resolve\nto a single installed toolset'),
    ('cmake-toolset-fields-invalid', "given toolset specification {private} that contains duplicate field key 'private-model'."),
    ('cmake-flagtable-not-found', 'JSON flag table for private-table not found for toolset private-toolset'),
    ('cmake-flagtable-load-failed', 'JSON flag table could not be loaded:\n  {private}'),
    ('cmake-platform-fields-invalid', "given platform specification {private} that contains a field after the first ',' with no '='."),
    ('cmake-generator-specification-unsupported', 'Generator private-generator does not support platform specification, but platform private-platform was specified.'),
    ('cmake-platform-version-invalid', 'given platform specification containing a version=private-version field with unsupported value.'),
    ('cmake-windows-sdk-not-found', 'given platform specification with version=10.0.26100.0 field, but no Windows SDK with that version was found.'),
    ('cmake-build-program-not-found', 'CMake was unable to find a build program corresponding to "private-generator". CMAKE_MAKE_PROGRAM is not set.'),
    ('cmake-compiler-not-found', 'The CMAKE_CXX_COMPILER:\n  {private}\nis not a full path to an existing compiler tool.'),
    ('cmake-compiler-not-recorded', 'No CMAKE_C_COMPILER could be found.'),
    ('cmake-compiler-not-set', 'CMAKE_RC_COMPILER not set, after EnableLanguage'),
    ('cmake-environment-compiler-not-found', 'Could not find the compiler specified in the environment variable CXX:\n{private}.'),
    ('cmake-compiler-identification-build-failed', 'Compiling the CXX compiler identification source file "private-id.cxx" failed.'),
    ('cmake-msvc-version-not-detected', 'MSVC compiler version not detected properly: private-version'),
    ('cmake-msvc-clui-not-found', 'Could not find clui.dll !'),
    ('cmake-compiler-test-failed', 'The C compiler "{private}"\nis not able to compile a simple test program.'),
    ('cmake-cli-argument-invalid', 'Unknown argument {private}'),
    ('cmake-cli-argument-invalid', 'Parse error in command line argument: {private}\n Should be: VAR:type=value'),
    ('cmake-source-directory-invalid', 'The source directory "{private}" does not appear to contain CMakeLists.txt.'),
    ('cmake-cache-source-mismatch', 'The source "{private}" does not match the source "{private}" used to generate cache. Re-run cmake with a different source directory.'),
    ('cmake-cache-generator-mismatch', 'Error: generator : private-value\nDoes not match the generator used previously: private-value'),
    ('cmake-cache-instance-mismatch', 'Error: generator instance: {private}\nDoes not match the instance used previously: {private}'),
    ('cmake-cache-platform-mismatch', 'Error: generator platform: private-value\nDoes not match the platform used previously: private-value'),
    ('cmake-cache-toolset-mismatch', 'Error: generator toolset: private-value\nDoes not match the toolset used previously: private-value'),
    ('cmake-project-arguments-invalid', 'project with VERSION, DESCRIPTION or HOMEPAGE_URL must\nuse LANGUAGES before language names.'),
    ('cmake-project-include-unavailable', 'could not load requested file:\n  {private}'),
    ('cmake-minimum-version-required', 'CMake 4.5 or higher is required. You are running version 4.4.5'),
    ('cmake-compatibility-removed', 'Compatibility with CMake < 3.5 has been removed\nfrom CMake.'),
    ('cmake-policy-minimum-invalid', 'Invalid CMAKE_POLICY_VERSION_MINIMUM value "private-version". A numeric major.minor[.patch[.tweak]] must be given.'),
    ('cmake-policy-unknown', 'Policy "CMP1234" is not known to this version of CMake.'),
    ('cmake-policy-old-unsupported', 'Policy CMP0001 may not be set to OLD behavior because this version of CMake no longer supports it.'),
    ('cmake-policy-arguments-invalid', 'cmake_policy SET given unrecognized policy status "private-status"'),
    ('cmake-command-unknown', 'Unknown CMake command "private-command".'),
])
def test_cmake445_error_templates_yield_fixed_ids_without_private_values(module, tmp_path, label, body):
    content = 'CMake Error at ' + str(tmp_path / 'private-project.cmake') + ':26 (project):\n  '
    content += body.replace('{private}', str(tmp_path / 'private-owner/model-secret')) + '\n'
    categories, sites = module.cmake_failure_details(content)
    assert label in categories
    assert sites == [{'command': 'project', 'line': 26}]
    delivered = json.dumps({'categories': categories, 'cmake_error_sites': sites})
    for private in (str(tmp_path), 'private-', 'model-secret'):
        assert private not in delivered


def test_cmake_error_sites_are_bounded_known_commands_and_warnings_do_not_become_causes(module, tmp_path):
    warning = ('CMake Warning at ' + str(tmp_path / 'private.cmake') + ':12 (message):\n'
        '  could not find specified instance of Visual Studio: private-model\n')
    assert module.cmake_failure_details(warning) == ([], [])
    content = (warning + 'CMake Error at private.cmake:0 (project):\n  private-model\n'
        'CMake Error at private.cmake:10000000 (project):\n  private-model\n'
        'CMake Error at private.cmake:25 (private-command):\n  private-model\n')
    content += ''.join('CMake Error at ' + str(tmp_path / 'private.cmake') + ':' + str(line)
        + ' (project):\n  private-model\n' for line in range(1, 40))
    categories, sites = module.cmake_failure_details(content)
    assert categories == [] and len(sites) == 32
    assert sites == [{'command': 'project', 'line': line} for line in range(1, 33)]
    assert str(tmp_path) not in json.dumps(sites) and 'private' not in json.dumps(sites)


def test_cmake_failure_receipt_delivers_known_sites_and_tail_only_without_native_success(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    logs = output / 'private-logs'; logs.mkdir()
    prefix = b'CMake Error: Unknown CMake command "private-early-command".\n'
    tail = ('CMake Error at ' + str(tmp_path / 'private-project.cmake') + ':26 (project):\n'
        '  Generator Visual Studio 18 2026\n'
        '  could not find specified instance of Visual Studio:\n  private-instance\n'
        'CMake Warning at private-warning.cmake:7 (message):\n'
        '  Unknown argument private-warning\n'
        'Configuring incomplete, errors occurred!\n')
    (logs / 'configure.log').write_bytes(prefix + b'x' * (2 * 1024 * 1024) + b'\n' + tail.encode())
    report = module.failed_build_receipt(output, 'cmake-configure', ValueError('private exception'))
    diagnostics = report['diagnostics']
    assert 'cmake-vs-instance-not-found' in diagnostics['categories']
    assert 'cmake-command-unknown' not in diagnostics['categories']
    assert 'cmake-cli-argument-invalid' not in diagnostics['categories']
    assert diagnostics['cmake_error_sites'] == [{'command': 'project', 'line': 26}]
    assert report['status'] == 'failed' and report['native_reference_probes_passed'] is False
    assert report['rights_approval'] is False and report['gates']['production_execution_allowed'] is False
    assert not (output / 'ASR-RECEIPT.json').exists()
    delivered = (output / 'ASR-FAILURE.json').read_text()
    for private in (str(tmp_path), 'private-early-command', 'private-project',
                    'private-instance', 'private-warning', 'private exception'):
        assert private not in delivered


def test_compiler_context_observes_known_fields_without_reading_outside_compiler_paths(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    vc, sdk = tmp_path/'sealed-vc', tmp_path/'sealed-sdk-bin'
    vc.mkdir(); sdk.mkdir(); (vc/'cl.exe').write_bytes(b'owned compiler fixture'); (sdk/'rc.exe').write_bytes(b'owned resource tool fixture')
    roots={'vc':str(vc),'sdk-bin':str(sdk)}
    build=output/'build'; config=build/'CMakeFiles/4.4.5'; config.mkdir(parents=True)
    (build/'CMakeCache.txt').write_text('CMAKE_C_COMPILER:FILEPATH='+str(vc/'cl.exe')+'\n'
        'CMAKE_C_COMPILER_ID:STRING=MSVC\nCMAKE_C_COMPILER_VERSION:STRING=19.51.36260.0\n'
        'CMAKE_CXX_COMPILER:FILEPATH=CMAKE_CXX_COMPILER-NOTFOUND\n'
        'CMAKE_CXX_COMPILER_ID:STRING=private-compiler-id\nCMAKE_CXX_COMPILER_VERSION:STRING=private-version\n'
        'CMAKE_RC_COMPILER:FILEPATH='+str(sdk/'rc.exe')+'\n')
    (config/'CMakeCCompiler.cmake').write_text('set(CMAKE_C_COMPILER "'+(vc/'cl.exe').as_posix()+'")\n'
        'set(CMAKE_C_COMPILER_ID "MSVC")\nset(CMAKE_C_COMPILER_VERSION "19.51.36260.0")\n')
    outside=tmp_path/'private-account/compiler.exe'; outside.parent.mkdir(); outside.write_bytes(b'private compiler text')
    (config/'CMakeRCCompiler.cmake').write_text('set(CMAKE_RC_COMPILER "'+outside.as_posix()+'")\n')
    real_stat,real_open=Path.stat,Path.open
    def stat_guard(path,*a,**k):
        if path==outside: pytest.fail('Outside compiler paths must not be statted.')
        return real_stat(path,*a,**k)
    def open_guard(path,*a,**k):
        if path==outside: pytest.fail('Outside compiler paths must not be read.')
        return real_open(path,*a,**k)
    monkeypatch.setattr(Path,'stat',stat_guard); monkeypatch.setattr(Path,'open',open_guard)
    monkeypatch.setattr(module,'_BUILD_TOOL_ROOTS',roots)
    report=module.failed_build_receipt(output,'cmake-configure',ValueError('private failure text'))
    context=report['compiler_detection_context']; c,cxx,rc=context['languages']
    assert context['evidence_scope']=='compiler-file-observation-not-native-approval'
    assert c['cache']==c['configuration']=={'state':'observed','compiler_state':'sealed-vc-toolset','compiler_id':'MSVC','compiler_version':'19.51.36260.0'}
    assert cxx['cache']['compiler_state']=='not-found' and cxx['cache']['compiler_id'] is None
    assert cxx['cache']['compiler_version'] is None and cxx['configuration']['state']=='missing'
    assert rc['cache']['compiler_state']=='sealed-sdk-bin' and rc['configuration']['compiler_state']=='outside-declared-roots'
    delivered=(output/'ASR-FAILURE.json').read_text()
    for private in (str(tmp_path),'private-account','private-compiler-id','private-version','private compiler text','private failure text'):
        assert private not in delivered
    assert report['status']=='failed' and report['rights_approval'] is False and not (output/'ASR-RECEIPT.json').exists()


@pytest.mark.parametrize('value,state', [(None,'missing-entry'),('','empty'),('NOTFOUND','not-found'),
    ('CMAKE_C_COMPILER-NOTFOUND','not-found'),('private-NOTFOUND','not-absolute'),
    ('private-relative','not-absolute'),('private\nvalue','invalid-value'),([], 'invalid-value')])
def test_compiler_context_distinguishes_only_evidenced_missing_notfound_and_invalid_values(module, value, state):
    assert module.compiler_path_state(value,'C',None)==state


def test_compiler_context_parent_traversal_duplicate_values_and_file_caps_fail_closed(module, tmp_path, monkeypatch):
    _source,_inputs,output=prepared(module,tmp_path,monkeypatch)
    vc=tmp_path/'sealed-vc'; vc.mkdir()
    assert module.compiler_path_state(str(vc/'..'/'private-account'/'compiler.exe'),'C',{'vc':str(vc)})=='outside-declared-roots'
    build=output/'build'; config=build/'CMakeFiles/4.4.5'; config.mkdir(parents=True)
    (build/'CMakeCache.txt').write_text('CMAKE_C_COMPILER:FILEPATH=private-a\nCMAKE_C_COMPILER:FILEPATH=private-b\n')
    context=module.compiler_detection_context(output,{'vc':str(vc)})
    assert context['languages'][0]['cache']['state']=='duplicate-entry'
    monkeypatch.setattr(module,'COMPILER_CONTEXT_FILE_BYTES',32)
    (config/'CMakeCCompiler.cmake').write_bytes(b'private compiler text'*10)
    context=module.compiler_detection_context(output,{'vc':str(vc)})
    assert context['languages'][0]['cache']['state']==context['languages'][0]['configuration']['state']=='size-limit'
    assert 'private' not in json.dumps(context)


def test_compiler_context_link_and_nonregular_inputs_are_not_read(module, tmp_path, monkeypatch):
    _source,_inputs,output=prepared(module,tmp_path,monkeypatch)
    build=output/'build'; config=build/'CMakeFiles/4.4.5'; config.mkdir(parents=True)
    cache=build/'CMakeCache.txt'; cache.write_text('private linked input')
    (config/'CMakeCCompiler.cmake').mkdir()
    real_lstat=Path.lstat
    monkeypatch.setattr(Path,'lstat',lambda p,*a,**k:
        SimpleNamespace(st_mode=module.stat.S_IFLNK) if p==cache else real_lstat(p,*a,**k))
    context=module.compiler_detection_context(output,None)
    assert context['languages'][0]['cache']['state']=='inspection-error'
    assert context['languages'][0]['configuration']['state']=='not-regular'
    assert 'private' not in json.dumps(context)


def test_nested_logs_are_fixed_context_only_with_perfile_and_total_caps(module, tmp_path, monkeypatch):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    first=directory/'CMakeConfigureLog.yaml'; second=directory/'CMakeError.log'
    first.write_bytes(b'error C1083: private early\n'+b'x'*80+b'\nerror C2065: private late\n')
    second.write_bytes(b'private prefix '*10+b'\nerror MSB8020\n')
    forbidden=directory/'CMakeOutput.log';forbidden.write_bytes(b'error LNK2019: private unknown log')
    monkeypatch.setattr(module,'LOG_TAIL_BYTES',64);monkeypatch.setattr(module,'NESTED_LOG_TOTAL_BYTES',80)
    real_reader=module.diagnostic_file;calls=[]
    def reader(path,limit,**options):
        assert path in (first,second)
        result=real_reader(path,limit,**options);calls.append((limit,len(result[1])));return result
    monkeypatch.setattr(module,'diagnostic_file',reader)
    context=module.nested_configure_log_context(tmp_path)
    assert context['evidence_scope']=='observed-context-not-fatal-cause'
    assert context['logs'][0]['known_codes']==['C2065'] and context['logs'][1]['known_codes']==['MSB8020']
    assert calls==[(64,64),(16,16)] and sum(n for _,n in calls)==80
    assert 'private' not in json.dumps(context) and str(tmp_path) not in json.dumps(context)
    monkeypatch.setattr(module,'NESTED_LOG_TOTAL_BYTES',1);calls.clear()
    context=module.nested_configure_log_context(tmp_path)
    assert calls==[(1,1)] and context['logs'][1]['state']=='total-byte-limit'


def test_nested_log_nonregular_and_unknown_codes_remain_private_context(module,tmp_path):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    (directory/'CMakeConfigureLog.yaml').mkdir()
    (directory/'CMakeError.log').write_text('error C9999: private secret model text\n')
    context=module.nested_configure_log_context(tmp_path)
    assert context['logs'][0]['state']=='not-regular'
    assert context['logs'][1]['known_codes']==[] and context['logs'][1]['context_labels']==['compiler-or-linker-error','unclassified-tool-error']
    assert 'C9999' not in json.dumps(context) and 'private' not in json.dumps(context)


@pytest.mark.parametrize('kind',['symlink','windows-reparse'])
def test_nested_log_linked_parent_is_rejected_before_descendant_metadata_or_open(module,tmp_path,monkeypatch,kind):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    for filename in ('CMakeConfigureLog.yaml','CMakeError.log'):
        (directory/filename).write_text('error C1083: private linked content\n')
    real_lstat,real_stat,real_open=Path.lstat,Path.stat,Path.open
    def reject_descendant(path):
        if path != directory and path.is_relative_to(directory):
            pytest.fail('Linked log parents must be rejected before descendant stat/lstat/open.')
    def lstat_guard(path,*a,**k):
        reject_descendant(path)
        if path==directory:
            return SimpleNamespace(st_mode=module.stat.S_IFLNK if kind=='symlink' else module.stat.S_IFDIR,
                st_file_attributes=0x400 if kind=='windows-reparse' else 0)
        return real_lstat(path,*a,**k)
    def stat_guard(path,*a,**k):
        reject_descendant(path);return real_stat(path,*a,**k)
    def open_guard(path,*a,**k):
        reject_descendant(path);return real_open(path,*a,**k)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(Path,'stat',stat_guard)
    monkeypatch.setattr(Path,'open',open_guard)
    context=module.nested_configure_log_context(tmp_path)
    assert all(row['state']=='inspection-error' and row['known_codes']==[] for row in context['logs'])
    assert 'private' not in json.dumps(context)


@pytest.mark.parametrize('kind',['symlink','windows-reparse'])
def test_compiler_linked_parent_is_rejected_before_descendant_metadata_or_open(module,tmp_path,monkeypatch,kind):
    vc=tmp_path/'sealed-vc';directory=vc/'bin';directory.mkdir(parents=True)
    compiler=directory/'cl.exe';compiler.write_bytes(b'private compiler fixture')
    real_lstat,real_stat,real_open=Path.lstat,Path.stat,Path.open
    def reject_descendant(path):
        if path != directory and path.is_relative_to(directory):
            pytest.fail('Linked compiler parents must be rejected before descendant stat/lstat/open.')
    def lstat_guard(path,*a,**k):
        reject_descendant(path)
        if path==directory:
            return SimpleNamespace(st_mode=module.stat.S_IFLNK if kind=='symlink' else module.stat.S_IFDIR,
                st_file_attributes=0x400 if kind=='windows-reparse' else 0)
        return real_lstat(path,*a,**k)
    def stat_guard(path,*a,**k):
        reject_descendant(path);return real_stat(path,*a,**k)
    def open_guard(path,*a,**k):
        reject_descendant(path);return real_open(path,*a,**k)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(Path,'stat',stat_guard)
    monkeypatch.setattr(Path,'open',open_guard)
    assert module.compiler_path_state(str(compiler),'C',{'vc':str(vc)})=='inspection-error'


def test_msb4019_context_labels_known_imports_without_inspecting_unknown_or_outside_targets(module,tmp_path,monkeypatch):
    msbuild=tmp_path/'sealed-msbuild';selected=msbuild/'Microsoft/VC/v180';selected.mkdir(parents=True)
    present=selected/'Microsoft.Cpp.Default.props';present.write_bytes(b'owned props fixture')
    missing=selected/'Microsoft.Cpp.props';nonregular=selected/'Microsoft.Cpp.targets';nonregular.mkdir()
    outside=tmp_path/'private-outside/Microsoft.Cpp.props';outside.parent.mkdir();outside.write_bytes(b'private import fixture')
    unknown=selected/'private-unknown.props';unknown.write_bytes(b'private unknown fixture')
    real_stat,real_lstat,real_open=Path.stat,Path.lstat,Path.open
    def guard(original):
        def call(path,*args,**kwargs):
            if path==unknown or path.is_relative_to(outside.parent):pytest.fail('Outside and unknown imports must not be inspected.')
            return original(path,*args,**kwargs)
        return call
    monkeypatch.setattr(Path,'stat',guard(real_stat));monkeypatch.setattr(Path,'lstat',guard(real_lstat))
    monkeypatch.setattr(Path,'open',guard(real_open))
    content='\n'.join('error MSB4019: The imported project "'+str(p)+'" was not found.'
        for p in (present,missing,nonregular,outside,unknown))
    content+='\nerror MSB4019: private new diagnostic template\nerror MSB4999: private unknown tool code\n'
    context=module.msb4019_import_context(content,{'msbuild':str(msbuild)},
        {'VCTargetsPath':str(selected)},16)
    assert context['truncated'] is False and len(context['records'])==6
    targets=[{key:row[key] for key in ('import_label','root_role','existence')} for row in context['records']]
    assert targets[:3]==[
        {'import_label':'microsoft-cpp-default-props','root_role':'selected-vc-targets','existence':'regular-file-present'},
        {'import_label':'microsoft-cpp-props','root_role':'selected-vc-targets','existence':'missing'},
        {'import_label':'microsoft-cpp-targets','root_role':'selected-vc-targets','existence':'nonregular'}]
    assert targets[3]=={'import_label':'microsoft-cpp-props','root_role':'outside-declared-roots','existence':'not-inspected'}
    assert targets[4:]==[{'import_label':'unknown-import','root_role':'not-inspected','existence':'not-inspected'}]*2
    # An expected property value cannot authorize reads outside declared roots.
    assert module.import_target_context(str(outside),{'msbuild':str(msbuild)},
        {'VCTargetsPath':str(outside.parent)})['root_role']=='outside-declared-roots'
    assert module.import_target_context(str(selected/'private-parent/../Microsoft.Cpp.props'),
        {'msbuild':str(msbuild)},{})['root_role']=='not-inspected'
    delivered=json.dumps(context)
    for value in (str(tmp_path),'private','MSB4999','owned props fixture'):
        assert value not in delivered


@pytest.mark.parametrize('caller,label,line,column',[
    (r'C:\private-root\CompilerIdC.vcxproj(21,7)','compiler-id-c-project',21,7),
    (r'C:\private-root\CompilerIdCXX.vcxproj(32)','compiler-id-cxx-project',32,None),
    (r'C:\private-root\Microsoft.Cpp.Default.props(42,3)','microsoft-cpp-default-props',42,3),
    (r'C:\private-root\private-caller.vcxproj(21,7)','unknown-caller',None,None),
    ('CompilerIdC.vcxproj(0,7)','unknown-caller',None,None),
    ('CompilerIdC.vcxproj(99999999,7)','unknown-caller',None,None),
    ('CompilerIdC.vcxproj(21,0)','unknown-caller',None,None)])
def test_msb4019_callers_are_only_primary_labels_and_bounded_positive_positions(module,caller,label,line,column):
    content='  '+caller+': error MSB4019: The imported project "private-target/Microsoft.Cpp.props" was not found.'
    result=module.msb4019_import_context(content,{},None,16)
    assert result['records'][0]['caller']=={'file_label':label,'line':line,'column':column}
    delivered=json.dumps(result)
    assert 'private-' not in delivered and caller not in delivered


def test_msb4019_context_limits_records_across_both_fixed_logs(module,tmp_path,monkeypatch):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    message='error MSB4019: The imported project "private-root/Microsoft.Cpp.props" was not found.\n'
    for filename in ('CMakeConfigureLog.yaml','CMakeError.log'):(directory/filename).write_text(message*2)
    monkeypatch.setattr(module,'IMPORT_CONTEXT_LIMIT',3)
    result=module.nested_configure_log_context(tmp_path)
    contexts=[row['msb4019_imports'] for row in result['logs']]
    assert [len(row['records']) for row in contexts]==[2,1]
    assert [row['truncated'] for row in contexts]==[False,True]
    assert 'private-root' not in json.dumps(result)


def compiler_id_project(output,language,body):
    path=output/'build/CMakeFiles/4.4.5'/('CompilerId'+language)/('CompilerId'+language+'.vcxproj')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(body)
    return path


def test_compiler_id_globals_deliver_only_literal_match_states_from_actual_private_properties(module,tmp_path,monkeypatch):
    _source,_inputs,output=prepared(module,tmp_path,monkeypatch)
    properties={'VCTargetsPath':(tmp_path/'private-v180').as_posix()+'/',
        'UserRootDir':(tmp_path/'private-user').as_posix()+'/',
        'MSBuildUserExtensionsPath':(tmp_path/'private-extensions').as_posix()+'/',
        'ImportDirectoryBuildProps':'false','ImportDirectoryBuildTargets':'false'}
    prefix='<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup Label="Globals">'
    suffix='</PropertyGroup></Project>'
    body=''.join('<'+key+'>'+value+'</'+key+'>' for key,value in properties.items())
    compiler_id_project(output,'CXX',(prefix+body+suffix).encode())
    changed=body.replace('<UserRootDir>','<UserRootDir>private-duplicate</UserRootDir><UserRootDir>',1)
    changed=changed.replace(properties['MSBuildUserExtensionsPath'],'private-different-value')
    changed=changed.replace('<ImportDirectoryBuildProps>false</ImportDirectoryBuildProps>',
        '<ImportDirectoryBuildProps Condition="private-condition">false</ImportDirectoryBuildProps>')
    changed=changed.replace('<ImportDirectoryBuildTargets>false</ImportDirectoryBuildTargets>','')
    changed+='<private-new-property>private-new-value</private-new-property>'
    compiler_id_project(output,'C',(prefix+changed+suffix).encode())
    monkeypatch.setattr(module,'_BUILD_PROPERTIES',properties)
    receipt=module.failed_build_receipt(output,'cmake-configure',ValueError('private exception'))
    context=receipt['compiler_id_globals_context']
    assert context['evidence_scope']=='observed-context-not-fatal-cause'
    c,cxx=context['projects']
    assert c['state']==cxx['state']=='observed'
    assert {p['property']:p['state'] for p in c['properties']}=={
        'VCTargetsPath':'exact-match','UserRootDir':'duplicate-property',
        'MSBuildUserExtensionsPath':'different','ImportDirectoryBuildProps':'structured-or-conditional-property',
        'ImportDirectoryBuildTargets':'missing'}
    assert all(p['state']=='exact-match' for p in cxx['properties'])
    delivered=(output/'ASR-FAILURE.json').read_text()
    assert str(tmp_path) not in delivered
    for value in ('private-v180','private-user','private-extensions','private-duplicate',
            'private-different-value','private-condition','private-new-property','private-new-value','private exception'):
        assert value not in delivered
    assert receipt['rights_approval'] is False and not (output/'ASR-RECEIPT.json').exists()
    unavailable=module.compiler_id_globals_context(output,None)
    assert all(p['state']=='expected-unavailable' for p in unavailable['projects'][1]['properties'])


@pytest.mark.parametrize('body',[
    b'<!DOCTYPE Project [<!ENTITY private "private value">]><Project>&private;</Project>',
    b'<!DOCTYPE Project SYSTEM "file:///private-authored-fixture"><Project/>',
    b'<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">&#97;</Project>',
    b'<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">&amp;</Project>',
    b'<Project>\xff</Project>',b'<Project>',b'<Project xmlns="private-unknown-namespace"/>'])
def test_compiler_id_globals_reject_entities_external_declarations_and_unsupported_xml(module,tmp_path,body):
    compiler_id_project(tmp_path,'C',body)
    result=module.compiler_id_globals_context(tmp_path,{})
    assert result['projects'][0]['state']=='unsupported-xml'
    assert all(p['state']=='unavailable' for p in result['projects'][0]['properties'])
    assert 'private' not in json.dumps(result) and str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize('groups,state',[
    ('','missing-globals'),
    ('<PropertyGroup Label="Globals"/><PropertyGroup Label="Globals"/>','ambiguous-globals'),
    ('<PropertyGroup Label="Globals" Condition="private-value"/>','ambiguous-globals')])
def test_compiler_id_globals_refuse_ambiguous_or_conditional_property_groups(module,tmp_path,groups,state):
    compiler_id_project(tmp_path,'C',('<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'+groups+'</Project>').encode())
    result=module.compiler_id_globals_context(tmp_path,{})
    assert result['projects'][0]['state']==state
    assert 'private-value' not in json.dumps(result)


def test_compiler_id_xml_byte_and_element_caps_reject_without_parsing_other_projects(module,tmp_path,monkeypatch):
    path=compiler_id_project(tmp_path,'C',b'<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'+b'<X/>'*4096+b'</Project>')
    forbidden=path.parent/'private-other.vcxproj';forbidden.write_bytes(b'private external fixture')
    real_open=Path.open
    def open_guard(path,*args,**kwargs):
        if path==forbidden:pytest.fail('No arbitrary XML project discovery.')
        return real_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',open_guard)
    assert module.compiler_id_globals_context(tmp_path,{})['projects'][0]['state']=='unsupported-xml'
    monkeypatch.setattr(module,'COMPILER_CONTEXT_FILE_BYTES',32)
    assert module.compiler_id_globals_context(tmp_path,{})['projects'][0]['state']=='size-limit'


@pytest.mark.parametrize('operation',['import-context','numeric-import-context','compiler-id-xml'])
@pytest.mark.parametrize('kind',['symlink','windows-reparse'])
def test_import_and_xml_context_reject_linked_ancestors_before_descendant_metadata(module,tmp_path,monkeypatch,operation,kind):
    directory=tmp_path/'declared-root/linked-parent';directory.mkdir(parents=True)
    target=directory/'Microsoft.Cpp.props';target.write_bytes(b'private import fixture')
    if operation=='numeric-import-context':
        target=directory/('Microsoft.VCToolsVersion.'+module.pin()['toolchain']['vc_tools_version']+'.props')
        target.write_bytes(b'private numeric import fixture')
    if operation=='compiler-id-xml':
        target=compiler_id_project(tmp_path,'C',b'<Project/>');directory=target.parent
    real_stat,real_lstat,real_open=Path.stat,Path.lstat,Path.open
    def reject_descendant(path):
        if path!=directory and path.is_relative_to(directory):pytest.fail('Linked ancestors must precede all descendant metadata/read.')
    def lstat_guard(path,*args,**kwargs):
        reject_descendant(path)
        if path==directory:return SimpleNamespace(st_mode=module.stat.S_IFLNK if kind=='symlink' else module.stat.S_IFDIR,
            st_file_attributes=0x400 if kind=='windows-reparse' else 0)
        return real_lstat(path,*args,**kwargs)
    def stat_guard(path,*args,**kwargs):
        reject_descendant(path);return real_stat(path,*args,**kwargs)
    def open_guard(path,*args,**kwargs):
        reject_descendant(path);return real_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(Path,'stat',stat_guard)
    monkeypatch.setattr(Path,'open',open_guard)
    if operation in {'import-context','numeric-import-context'}:
        result=module.import_target_context(str(target),{'msbuild':str(directory.parent)},{})
        assert result['existence']=='inspection-error'
    else:
        result=module.compiler_id_globals_context(tmp_path,{})
        assert result['projects'][0]['state']=='inspection-error'
    assert str(tmp_path) not in json.dumps(result) and 'private' not in json.dumps(result)


@pytest.mark.parametrize('separator',['/','.'])
def test_generated_numeric_toolset_import_exposes_only_exact_verified_instance_suffix_branch(module,tmp_path,monkeypatch,separator):
    version=module.pin()['toolchain']['vc_tools_version'];observed='18.11.12315.225'
    vs=tmp_path/'private-vs';msbuild=vs/'MSBuild';selected=msbuild/'Microsoft/VC/v180'
    auxiliary=vs/'VC/Auxiliary';selected.mkdir(parents=True);auxiliary.mkdir(parents=True)
    roots={'msbuild':str(msbuild),'vc-auxiliary':str(auxiliary)}
    properties={'VCTargetsPath':str(selected)}
    for filename in ('Microsoft.Cpp.Default.props','Microsoft.Cpp.props','Microsoft.Cpp.targets'):
        (selected/filename).write_bytes(b'owned CPP property fixture')
    leaf='Microsoft.VCToolsVersion.'+version+'.props'
    good=auxiliary/('Build/'+version if separator=='/' else 'Build.'+version)/leaf
    good.parent.mkdir(parents=True);good.write_bytes(b'owned toolset property fixture')
    instance={'argument':vs.as_posix()+',version='+observed,'root':str(vs),'observed_version':observed}
    # Exactly the conditional construction in pinned CMakeDetermineCompilerId:
    # use the full instance string as a path before adding Build[/.]<version>.
    malformed=instance['argument']+'/VC/Auxiliary/Build'+separator+version+'/'+leaf
    prefix='<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup Label="Globals">'
    prefix+='<VCTargetsPath>'+str(selected)+'</VCTargetsPath></PropertyGroup>'
    cpp='<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props"/>'
    compiler_id_project(tmp_path,'C',(prefix+cpp+'<Import Project="'+malformed+'"/></Project>').encode())
    compiler_id_project(tmp_path,'CXX',(prefix+cpp+'<Import Project="'+good.as_posix()+'"/></Project>').encode())
    real_stat,real_lstat,real_open=Path.stat,Path.lstat,Path.open
    def guard(original):
        def call(path,*args,**kwargs):
            if ',version=' in str(path):pytest.fail('The malformed outside-root import cannot receive metadata or content access.')
            return original(path,*args,**kwargs)
        return call
    monkeypatch.setattr(Path,'stat',guard(real_stat));monkeypatch.setattr(Path,'lstat',guard(real_lstat))
    monkeypatch.setattr(Path,'open',guard(real_open))
    result=module.compiler_id_globals_context(tmp_path,properties,roots,instance)
    c,cxx=result['projects']
    assert c['imports'][0]['import_label']=='microsoft-cpp-default-props'
    assert c['imports'][0]['existence']=='regular-file-present' and c['imports'][0]['root_role']=='selected-vc-targets'
    bad=c['imports'][1];assert bad['import_label']=='mapped-toolset-version-template'
    assert bad['reviewed_version']==version and bad['contains_verified_instance_version_field'] is True
    assert bad['root_role']=='outside-declared-roots' and bad['existence']=='not-inspected'
    actual=cxx['imports'][1]
    assert actual['import_label']=='mapped-toolset-version-template' and actual['reviewed_version']==version
    assert actual['contains_verified_instance_version_field'] is False
    assert actual['root_role']=='not-inspected' and actual['existence']=='not-inspected'
    assert actual['toolset_mapping']['relationship']=='initial-seal-unavailable'
    delivered=json.dumps(result)
    for private in (str(tmp_path),'private-vs',instance['argument'],observed,'owned toolset property fixture'):
        assert private not in delivered


def test_msb4019_literal_extraction_and_exact_reviewed_toolset_version_are_separate_states(module,tmp_path,monkeypatch):
    version=module.pin()['toolchain']['vc_tools_version']
    root=tmp_path/'private-vs';root.mkdir()
    instance={'argument':root.as_posix()+',version=18.11.12315.225','root':str(root),'observed_version':'18.11.12315.225'}
    monkeypatch.setattr(module,'_BUILD_INSTANCE',instance)
    target=instance['argument']+'/VC/Auxiliary/Build/'+version+'/Microsoft.VCToolsVersion.'+version+'.props'
    content='error MSB4019: The imported project "'+target+'" was not found.\n'
    content+='error MSB4019: The imported project "private/Microsoft.VCToolsVersion.14.51.999999.props" was not found.\n'
    content+='error MSB4019: private new template with unrecognized quotes\n'
    result=module.msb4019_import_context(content,{},None,16)
    known,unknown,unrecognized=result['records']
    assert known['literal_match_state']==unknown['literal_match_state']=='matched-import-template'
    assert known['import_label']=='mapped-toolset-version-template' and known['reviewed_version']==version
    assert known['contains_verified_instance_version_field'] is True
    assert unknown['import_label']=='unknown-import' and unknown['reviewed_version'] is None
    assert unknown['contains_verified_instance_version_field'] is None
    assert unrecognized['literal_match_state']=='unrecognized-template' and unrecognized['import_label']=='unknown-import'
    delivered=json.dumps(result)
    for private in ('private',str(tmp_path),'999999','18.11.12315.225',target):assert private not in delivered


@pytest.mark.parametrize('change',['argument','observed-version','root','missing-observation'])
def test_numeric_toolset_import_never_claims_verified_suffix_from_mismatched_private_instance(module,tmp_path,change):
    version=module.pin()['toolchain']['vc_tools_version'];root=tmp_path/'private-vs';root.mkdir()
    instance={'argument':root.as_posix()+',version=18.11.12315.225','root':str(root),'observed_version':'18.11.12315.225'}
    target=instance['argument']+'/VC/Auxiliary/Build/'+version+'/Microsoft.VCToolsVersion.'+version+'.props'
    if change=='argument':instance['argument']=root.as_posix()+',version=18.11.12315.226'
    elif change=='observed-version':instance['observed_version']='18.11.12315.226'
    elif change=='root':instance['root']=str(tmp_path/'private-other-vs')
    else:instance['observed_version']=None
    result=module.import_target_context(target,{},None,instance=instance)
    assert result['import_label']=='microsoft-vctools-version-props'
    assert result['contains_verified_instance_version_field'] is None and result['existence']=='not-inspected'
    assert 'private' not in json.dumps(result)


def test_generated_imports_are_bounded_and_unknown_macros_never_evaluated_or_inspected(module,tmp_path,monkeypatch):
    version=module.pin()['toolchain']['vc_tools_version'];msbuild=tmp_path/'private-msbuild';msbuild.mkdir()
    unknown=msbuild/'Microsoft.VCToolsVersion.14.51.999999.props';unknown.write_bytes(b'private unknown fixture')
    xml='<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup Label="Globals"/>'
    xml+='<Import Project="$(privateMacro)/Microsoft.Cpp.props" Condition="private-condition"/>'
    xml+='<Import Project="'+unknown.as_posix()+'"/>'
    xml+='<Import Project="private/unknown-'+version+'.props"/></Project>'
    compiler_id_project(tmp_path,'C',xml.encode());compiler_id_project(tmp_path,'CXX',xml.encode())
    real_lstat=Path.lstat
    def lstat_guard(path,*args,**kwargs):
        if path==unknown:pytest.fail('Unreviewed numeric-version inputs remain unknown and uninspected.')
        return real_lstat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(module,'COMPILER_ID_IMPORT_LIMIT',4)
    result=module.compiler_id_globals_context(tmp_path,{'VCTargetsPath':str(msbuild)},{'msbuild':str(msbuild)})
    c,cxx=result['projects'];assert len(c['imports'])==3 and len(cxx['imports'])==1
    assert c['imports_truncated'] is False and cxx['imports_truncated'] is True
    assert c['imports'][0]['existence']=='unexpanded-template' and c['imports'][0]['conditional'] is True
    assert c['imports'][1]['import_label']=='unknown-import' and c['imports'][1]['reviewed_version'] is None
    assert 'private' not in json.dumps(result) and '999999' not in json.dumps(result)


@pytest.mark.parametrize('state',['missing','different','duplicate'])
def test_generated_cpp_prefix_is_not_substituted_without_actual_literal_vctargets_match(module,tmp_path,monkeypatch,state):
    desired=tmp_path/'private-configured-targets';desired.mkdir()
    target=desired/'Microsoft.Cpp.props';target.write_bytes(b'private target fixture')
    property_xml='' if state=='missing' else '<VCTargetsPath>private-different-root</VCTargetsPath>'
    if state=='duplicate':property_xml=('<VCTargetsPath>'+str(desired)+'</VCTargetsPath>')*2
    xml='<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup Label="Globals">'
    xml+=property_xml+'</PropertyGroup><Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props"/></Project>'
    compiler_id_project(tmp_path,'C',xml.encode())
    real_lstat=Path.lstat
    def guard(path,*args,**kwargs):
        if path==desired or desired in path.parents:pytest.fail('Unmatched actual Globals cannot select a target for inspection.')
        return real_lstat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',guard)
    result=module.compiler_id_globals_context(tmp_path,{'VCTargetsPath':str(desired)},{'msbuild':str(desired)})
    record=result['projects'][0]['imports'][0]
    assert record['import_label']=='microsoft-cpp-props' and record['existence']=='unexpanded-template'
    assert record['root_role']=='not-inspected' and 'private' not in json.dumps(result)


def alias_mapping_inputs(module,tmp_path,layout='/'):
    version=module.pin()['toolchain']['vc_tools_version'];alias='14.51.18.0'
    root=tmp_path/'private-vs';aux=root/'VC/Auxiliary'
    directory=aux/('Build/'+alias if layout=='/' else 'Build.'+alias);directory.mkdir(parents=True)
    metadata=directory/('Microsoft.VCToolsVersion.'+alias+'.txt')
    props=directory/('Microsoft.VCToolsVersion.'+alias+'.props')
    metadata.write_bytes((version+'\r\n').encode());props.write_bytes(b'owned auxiliary props fixture\n')
    index={p.relative_to(aux).as_posix():module.attributes(p.read_bytes()) for p in (metadata,props)}
    instance={'root':str(root),'argument':root.as_posix()+',version=18.11.12315.225',
        'observed_version':'18.11.12315.225'}
    value=instance['argument']+'/VC/Auxiliary/Build/'+alias+'/Microsoft.VCToolsVersion.'+alias+'.props'
    return version,alias,aux,metadata,props,index,instance,value


@pytest.mark.parametrize('layout',['/','.'])
def test_actual_alias_template_is_bound_to_initial_auxiliary_members_and_exact_policy_without_alias_disclosure(module,tmp_path,monkeypatch,layout):
    version,alias,aux,metadata,props,index,instance,value=alias_mapping_inputs(module,tmp_path,layout)
    prefix='<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup Label="Globals"/>'
    compiler_id_project(tmp_path,'C',(prefix+'<Import Project="'+value+'"/></Project>').encode())
    real_lstat=Path.lstat
    def guard(path,*args,**kwargs):
        if ',version=' in str(path):pytest.fail('Only corrected members under the declared Auxiliary root may be inspected.')
        return real_lstat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',guard)
    result=module.compiler_id_globals_context(tmp_path,{}, {'vc-auxiliary':str(aux)},instance,{'vc-auxiliary':index})
    record=result['projects'][0]['imports'][0]
    assert record['import_label']=='mapped-toolset-version-template' and record['reviewed_version']==version
    assert record['contains_verified_instance_version_field'] is True and record['root_role']=='outside-declared-roots'
    assert record['existence']=='not-inspected'
    assert record['toolset_mapping']=={'relationship':'verified-toolset-alias','matched_candidate_count':1,
        'matches_policy':True,'member_exists_state':'regular-files-present'}
    delivered=json.dumps(result)
    for private in (alias,str(tmp_path),str(metadata),str(props),instance['argument'],
            module.sha(metadata.read_bytes()),module.sha(props.read_bytes())):
        assert private not in delivered


@pytest.mark.parametrize('change,relationship,matches',[
    ('metadata-changed','sealed-member-changed',None),('props-changed','sealed-member-changed',None),
    ('different-policy','different-policy-version',False),('missing-member','unavailable-sealed-member',None),
    ('missing-props-seal','incomplete-or-unbounded-sealed-pair',None),
    ('unknown-layout','no-sealed-alias-candidate',None),('wrong-declared-root','declared-root-mismatch',None),
    ('missing-initial-seal','initial-seal-unavailable',None)])
def test_alias_mapping_cannot_replace_initial_source_binding_or_exact_metadata_policy(module,tmp_path,change,relationship,matches):
    version,alias,aux,metadata,props,index,instance,value=alias_mapping_inputs(module,tmp_path)
    roots={'vc-auxiliary':str(aux)};initial={'vc-auxiliary':index}
    if change=='metadata-changed':metadata.write_bytes(b'private changed metadata\n')
    elif change=='props-changed':props.write_bytes(b'private changed props\n')
    elif change=='different-policy':
        metadata.write_bytes(b'14.51.999999\r\n');index[metadata.relative_to(aux).as_posix()]=module.attributes(metadata.read_bytes())
    elif change=='missing-member':metadata.unlink()
    elif change=='missing-props-seal':del index[props.relative_to(aux).as_posix()]
    elif change=='unknown-layout':initial={'vc-auxiliary':{'private/../unknown.txt':module.attributes(b'private')}}
    elif change=='wrong-declared-root':roots={'vc-auxiliary':str(tmp_path/'private-other-auxiliary')}
    else:initial=None
    result=module.import_target_context(value,roots,{},instance=instance,initial_seal=initial)
    mapping=result['toolset_mapping']
    assert result['import_label']=='mapped-toolset-version-template' and result['contains_verified_instance_version_field'] is True
    assert mapping['relationship']==relationship and mapping['matches_policy'] is matches
    assert mapping['matched_candidate_count']==0
    if change=='props-changed':assert mapping['member_exists_state']=='regular-member-observed'
    if change=='metadata-changed':assert mapping['member_exists_state']=='size-limit'
    for private in (alias,str(tmp_path),'private','999999'):
        assert private not in json.dumps(result)


def test_alias_mapping_candidate_and_byte_limits_are_checked_before_native_member_access(module,tmp_path,monkeypatch):
    version,alias,aux,metadata,props,index,instance,value=alias_mapping_inputs(module,tmp_path)
    alternate=aux/('Build.'+alias);alternate.mkdir()
    for original in (metadata,props):
        target=alternate/original.name;target.write_bytes(original.read_bytes())
        index[target.relative_to(aux).as_posix()]=module.attributes(target.read_bytes())
    roots={'vc-auxiliary':str(aux)};initial={'vc-auxiliary':index}
    expected=sum(record['bytes']+1 for record in index.values())
    monkeypatch.setattr(module,'AUX_MAPPING_TOTAL_BYTES',expected)
    result=module.import_target_context(value,roots,{},instance=instance,initial_seal=initial)
    assert result['toolset_mapping']['relationship']=='ambiguous-toolset-alias'
    assert result['toolset_mapping']['matched_candidate_count']==2
    real_reader=module.diagnostic_file
    def forbidden(*_args,**_kwargs):pytest.fail('Over-limit mapping must not read a member.')
    monkeypatch.setattr(module,'diagnostic_file',forbidden)
    monkeypatch.setattr(module,'AUX_MAPPING_TOTAL_BYTES',expected-1)
    assert module.import_target_context(value,roots,{},instance=instance,initial_seal=initial)['toolset_mapping']['relationship']=='byte-limit'
    monkeypatch.setattr(module,'AUX_MAPPING_TOTAL_BYTES',expected)
    monkeypatch.setattr(module,'AUX_MAPPING_CANDIDATE_LIMIT',1)
    assert module.import_target_context(value,roots,{},instance=instance,initial_seal=initial)['toolset_mapping']['relationship']=='candidate-limit'
    monkeypatch.setattr(module,'AUX_MAPPING_CANDIDATE_LIMIT',32)
    monkeypatch.setattr(module,'AUX_SEAL_ENTRY_LIMIT',1)
    assert module.import_target_context(value,roots,{},instance=instance,initial_seal=initial)['toolset_mapping']['relationship']=='initial-seal-limit'
    monkeypatch.setattr(module,'AUX_SEAL_ENTRY_LIMIT',50000)
    monkeypatch.setattr(module,'AUX_MAPPING_FILE_BYTES',1)
    assert module.import_target_context(value,roots,{},instance=instance,initial_seal=initial)['toolset_mapping']['relationship']=='incomplete-or-unbounded-sealed-pair'
    monkeypatch.setattr(module,'diagnostic_file',real_reader)


@pytest.mark.parametrize('kind',['symlink','windows-reparse'])
def test_alias_mapping_rejects_linked_corrected_member_ancestor_before_leaf_metadata_or_read(module,tmp_path,monkeypatch,kind):
    version,alias,aux,metadata,props,index,instance,value=alias_mapping_inputs(module,tmp_path)
    directory=metadata.parent;real_lstat,real_stat,real_open=Path.lstat,Path.stat,Path.open
    def reject(path):
        if path!=directory and directory in path.parents:pytest.fail('Linked Auxiliary ancestor must precede corrected member metadata/read.')
    def lstat_guard(path,*args,**kwargs):
        reject(path)
        if path==directory:return SimpleNamespace(st_mode=module.stat.S_IFLNK if kind=='symlink' else module.stat.S_IFDIR,
            st_file_attributes=0x400 if kind=='windows-reparse' else 0)
        return real_lstat(path,*args,**kwargs)
    def stat_guard(path,*args,**kwargs):reject(path);return real_stat(path,*args,**kwargs)
    def open_guard(path,*args,**kwargs):reject(path);return real_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(Path,'stat',stat_guard);monkeypatch.setattr(Path,'open',open_guard)
    result=module.import_target_context(value,{'vc-auxiliary':str(aux)},{},instance=instance,initial_seal={'vc-auxiliary':index})
    assert result['toolset_mapping']['relationship']=='unavailable-sealed-member'
    assert result['toolset_mapping']['member_exists_state']=='inspection-error'
    assert alias not in json.dumps(result) and str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize('directory_alias,file_alias',[
    ('99.99','99.99'),('14','14'),('14.51.1.2.3','14.51.1.2.3'),('14.51.18.0','14.51.19.0')])
def test_new_unknown_numeric_layouts_cannot_become_mapped_policy_evidence(module,tmp_path,monkeypatch,directory_alias,file_alias):
    root=tmp_path/'private-vs';root.mkdir()
    instance={'argument':root.as_posix()+',version=18.11.12315.225','root':str(root),'observed_version':'18.11.12315.225'}
    value=instance['argument']+'/VC/Auxiliary/Build/'+directory_alias+'/Microsoft.VCToolsVersion.'+file_alias+'.props'
    def forbidden(*_args,**_kwargs):pytest.fail('Unknown numeric layouts cannot request corrected-member inspection.')
    monkeypatch.setattr(module,'diagnostic_file',forbidden)
    result=module.import_target_context(value,{},None,instance=instance,initial_seal={})
    assert result['import_label']=='unknown-import' and result['toolset_mapping'] is None
    for private in (str(tmp_path),directory_alias,file_alias):assert private not in json.dumps(result)


@pytest.mark.parametrize('layout',['/','.'])
def test_canonical_generated_auxiliary_import_requires_the_same_initial_sealed_pair(module,tmp_path,layout):
    version,alias,aux,metadata,props,index,instance,historical=alias_mapping_inputs(module,tmp_path,layout)
    canonical=props.as_posix()
    xml='<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup Label="Globals"/>'
    compiler_id_project(tmp_path,'C',(xml+'<Import Project="'+canonical+'"/></Project>').encode())
    result=module.compiler_id_globals_context(tmp_path,{}, {'vc-auxiliary':str(aux)},instance,{'vc-auxiliary':index})
    record=result['projects'][0]['imports'][0]
    assert record['import_label']=='mapped-toolset-version-template' and record['reviewed_version']==version
    assert record['contains_verified_instance_version_field'] is False
    assert record['root_role']=='declared-vc-auxiliary' and record['existence']=='regular-file-present'
    assert record['toolset_mapping']=={'relationship':'verified-toolset-alias','matched_candidate_count':1,
        'matches_policy':True,'member_exists_state':'regular-files-present'}
    old=module.import_target_context(historical,{'vc-auxiliary':str(aux)},{},instance=instance,initial_seal={'vc-auxiliary':index})
    assert old['contains_verified_instance_version_field'] is True and old['existence']=='not-inspected'
    delivered=json.dumps(result)
    for private in (str(tmp_path),alias,canonical,instance['argument'],instance['observed_version'],module.sha(props.read_bytes())):
        assert private not in delivered


@pytest.mark.parametrize('change,relationship',[
    ('metadata-changed','sealed-member-changed'),('props-changed','sealed-member-changed'),
    ('foreign-seal-bytes','sealed-member-changed'),('foreign-seal-role','initial-seal-unavailable'),
    ('other-layout-only','no-sealed-alias-candidate'),('wrong-declared-root','declared-root-mismatch')])
def test_canonical_auxiliary_context_cannot_inspect_an_unsealed_alternative_or_accept_changed_bytes(module,tmp_path,monkeypatch,change,relationship):
    version,alias,aux,metadata,props,index,instance,_value=alias_mapping_inputs(module,tmp_path)
    roots={'vc-auxiliary':str(aux)};initial={'vc-auxiliary':index}
    if change=='metadata-changed':metadata.write_bytes(b'private changed metadata')
    elif change=='props-changed':props.write_bytes(b'private changed props')
    elif change=='foreign-seal-bytes':index[props.relative_to(aux).as_posix()]=module.attributes(b'foreign supplier bytes')
    elif change=='foreign-seal-role':initial={'foreign-role':index}
    elif change=='other-layout-only':
        initial={'vc-auxiliary':{name.replace('Build/','Build.'):record for name,record in index.items()}}
    else:roots={'vc-auxiliary':str(tmp_path/'private-other-auxiliary')}
    if change in {'foreign-seal-role','other-layout-only','wrong-declared-root'}:
        private_root=aux.parents[1]
        def guard(original):
            def call(path,*args,**kwargs):
                if path==private_root or private_root in path.parents or path==Path(roots['vc-auxiliary']):
                    pytest.fail('Unbound canonical members cannot request metadata or content access.')
                return original(path,*args,**kwargs)
            return call
        monkeypatch.setattr(Path,'stat',guard(Path.stat));monkeypatch.setattr(Path,'lstat',guard(Path.lstat))
        monkeypatch.setattr(Path,'open',guard(Path.open))
    record=module.import_target_context(props.as_posix(),roots,{},instance=instance,initial_seal=initial)
    assert record['contains_verified_instance_version_field'] is False
    assert record['toolset_mapping']['relationship']==relationship
    assert record['toolset_mapping']['matched_candidate_count']==0
    assert record['existence']!='regular-file-present'
    for private in (str(tmp_path),alias,'foreign supplier bytes','private changed'):
        assert private not in json.dumps(record)


@pytest.mark.parametrize('kind',['symlink','windows-reparse'])
def test_canonical_auxiliary_context_refuses_parent_links_before_leaf_metadata(module,tmp_path,monkeypatch,kind):
    _version,_alias,aux,metadata,props,index,instance,_value=alias_mapping_inputs(module,tmp_path)
    directory=metadata.parent;real_lstat,real_stat,real_open=Path.lstat,Path.stat,Path.open
    def reject(path):
        if path!=directory and directory in path.parents:pytest.fail('A linked canonical parent must be refused before leaf access.')
    def lstat_guard(path,*args,**kwargs):
        reject(path)
        if path==directory:return SimpleNamespace(st_mode=module.stat.S_IFLNK if kind=='symlink' else module.stat.S_IFDIR,
            st_file_attributes=0x400 if kind=='windows-reparse' else 0)
        return real_lstat(path,*args,**kwargs)
    def stat_guard(path,*args,**kwargs):reject(path);return real_stat(path,*args,**kwargs)
    def open_guard(path,*args,**kwargs):reject(path);return real_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',lstat_guard);monkeypatch.setattr(Path,'stat',stat_guard);monkeypatch.setattr(Path,'open',open_guard)
    record=module.import_target_context(props.as_posix(),{'vc-auxiliary':str(aux)},{},instance=instance,initial_seal={'vc-auxiliary':index})
    assert record['contains_verified_instance_version_field'] is False and record['existence']=='inspection-error'
    assert record['toolset_mapping']['relationship']=='unavailable-sealed-member'


@pytest.mark.parametrize('change',['argument','root','observed-version','missing-observation'])
def test_canonical_auxiliary_absence_boolean_requires_the_verified_full_instance_tuple(module,tmp_path,monkeypatch,change):
    _version,_alias,aux,_metadata,props,index,instance,_value=alias_mapping_inputs(module,tmp_path)
    if change=='argument':instance['argument']+=',private-unknown-field'
    elif change=='root':instance['root']=str(tmp_path/'private-foreign-vs')
    elif change=='observed-version':instance['observed_version']='18.11.12315.226'
    else:instance['observed_version']=None
    def forbidden(*_args,**_kwargs):pytest.fail('An unverified instance tuple cannot authorize canonical member reads.')
    monkeypatch.setattr(module,'diagnostic_file',forbidden)
    record=module.import_target_context(props.as_posix(),{'vc-auxiliary':str(aux)},{},instance=instance,initial_seal={'vc-auxiliary':index})
    assert record['import_label']=='unknown-import' and record['contains_verified_instance_version_field'] is None
    assert record['toolset_mapping'] is None and record['existence']=='not-inspected'
    assert 'private' not in json.dumps(record)


def test_msb4018_projects_only_reviewed_task_exception_and_explicit_code_labels(module):
    prefix='  1>C:/r19-authored-private/targets(22,5): error MSB4018: '
    content=prefix+'The "SetEnv" task failed unexpectedly. [C:/r19-authored-private/project]\n'
    content+=prefix+'System.ArgumentNullException: private parameter/model text (Exception from HRESULT: 0x80004003) NativeErrorCode: 5\n'
    content+=prefix+'   at PrivateStack.PrivateMethod(C:/r19-authored-private/account)\n'
    result=module.msb4018_task_context(content,16)
    assert result=={'records':[{'literal_match_state':'matched-task-template','task_label':'set-env',
        'exception_families':['argument-null'],'hresult_labels':['e-pointer'],'win32_labels':['access-denied'],
        'context_truncated':False,'exception_chain':{'state':'not-observed','families':[],'truncated':False},
        'argument_context':{'state':'not-observed','resource_state':'not-observed','resource_label':None,
            'parameter_state':'not-observed','parameter_role':None,'initializer_roles':[],
            'unknown_initializer_seen':False,'framework_frames':[],'unknown_frame_seen':False,'frames_truncated':False}}],
        'truncated':False}
    for private in ('r19-authored-private','PrivateStack','parameter/model','targets','22','System.ArgumentNullException','0x80004003'):
        assert private not in json.dumps(result)


def test_msb4018_unknown_literals_and_codes_never_echo_tokens_or_infer_native_error_from_hresult(module):
    prefix='error MSB4018: '
    content=prefix+'The "OwnedPrivateTask" task failed unexpectedly.\n'
    content+=prefix+'Owned.PrivateException (0x81234567): private account NativeErrorCode: 998877\n'
    content+=prefix+'   at System.ArgumentNullException: (Exception from HRESULT: 0x80004003)\n'
    content+='\n'+prefix+'unrecognized private task template\n'
    content+=prefix+'System.ComponentModel.Win32Exception (0x80004005): private message\n'
    first,second=module.msb4018_task_context(content,16)['records']
    assert first['literal_match_state']=='matched-task-template' and first['task_label']=='unknown-task'
    assert first['exception_families']==['unknown-exception'] and first['hresult_labels']==['unknown-hresult']
    assert first['win32_labels']==['unknown-win32-error']
    assert second['literal_match_state']=='unrecognized-template' and second['task_label']=='unknown-task'
    assert second['exception_families']==['win32'] and second['hresult_labels']==['e-fail']
    assert second['win32_labels']==[]
    for private in ('Owned','PrivateException','81234567','998877','private account','private message'):
        assert private not in json.dumps((first,second))


def test_msb4018_primary_dll_exception_hresult_and_explicit_win32_code_are_separate_observations(module):
    prefix='C:/r19-authored-private/task(6,7): error MSB4018: '
    content=prefix+'The "CL" task failed unexpectedly.\n'
    content+=prefix+'System.DllNotFoundException: private module (Exception from HRESULT: 0x8007007E)\n'
    content+=prefix+'---> System.ComponentModel.Win32Exception: private message Win32 error: 126\n'
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['task_label']=='cl' and record['exception_families']==['dll-not-found','win32']
    assert record['hresult_labels']==['win32-module-not-found-hresult'] and record['win32_labels']==['module-not-found']
    assert 'private' not in json.dumps(record) and '126' not in json.dumps(record)


def owned_type_initializer(name='Owned.PrivateInitializer'):
    return "System.TypeInitializationException: The type initializer for '"+name+"' threw an exception."


def owned_argument_record(module,message,lines=(),*,initializer='Microsoft.Build.Utilities.FileTracker',newline='\n'):
    bodies=['The "CL" task failed unexpectedly.',owned_type_initializer(initializer)+' ---> System.ArgumentException: '+message,*lines]
    return module.msb4018_task_context(newline.join('error MSB4018: '+body for body in bodies),16)['records'][0]


@pytest.mark.parametrize('message,label',[
    ('Value does not fall within the expected range.','generic-argument'),
    ('The path is not of a legal form.','path-illegal'),('Illegal characters in path.','path-invalid-characters'),
    ('Path cannot be the empty string or all whitespace.','path-empty'),('Empty path name is not legal.','path-empty'),
    ("The given path's format is not supported.",'path-format-unsupported'),('URI formats are not supported.','path-uri-unsupported'),
    ('Absolute path information is required.','absolute-path-required'),('String cannot be of zero length.','string-empty'),
    ('String may not be empty or null.','string-empty'),('An item with the same key has already been added.','dictionary-duplicate'),
    ('Environment variable name cannot contain equal character.','env-name-invalid'),
    ('The first char in the string is the null character.','env-name-invalid'),
    ('Environment variable name cannot contain 1024 or more characters.','env-name-too-long'),
    ('Environment variable name or value is too long.','env-name-or-value-too-long')])
def test_argument_resources_match_only_the_complete_admitted_leaf_and_hide_project_decoration(module,message,label):
    record=owned_argument_record(module,message+' [C:/r19-authored-private/project]')
    context=record['argument_context']
    assert context['state']=='observed' and context['resource_state']=='matched' and context['resource_label']==label
    assert context['initializer_roles']==['file-tracker'] and context['unknown_initializer_seen'] is False
    assert record['exception_chain']['families']==['type-initialization','argument']
    assert 'r19-authored-private' not in json.dumps(context) and message not in json.dumps(context)


@pytest.mark.parametrize('message,label',[
    ("Item has already been added. Key in dictionary: 'private-key'  Key being added: 'PRIVATE-KEY'",'dictionary-duplicate'),
    ('Illegal enum value: -1234567890.','enum-invalid'),
    ('Illegal enum value: 12345678901.',None),
    ("Item has already been added. Key in dictionary: '"+'x'*257+"'  Key being added: 'private-key'",None),
    ("Item has already been added. Key in dictionary: 'private'quote'  Key being added: 'private-key'",None),
    ('Illegal characters in path. private extra message',None),('Onjuiste tekens in pad.',None),
    ('The path is not of a legal form.\x00',None),
    ('The path is not of a legal form. [private\x00project]',None),
    (' The path is not of a legal form.',None),('The path is not of a legal form. ',None)])
def test_argument_formatted_resources_bound_opaque_values_and_leave_custom_or_localized_text_unknown(module,message,label):
    context=owned_argument_record(module,message)['argument_context']
    assert context['resource_label']==label and context['resource_state']==('matched' if label else 'unknown')
    for private in ('private-key','PRIVATE-KEY','1234567890','private extra','Onjuiste','private\'quote'):
        assert private not in json.dumps(context)


@pytest.mark.parametrize('parameter,state,role',[
    ('path','known-role','path-input'),('path2','known-role','path-second'),('paths','known-role','path-array'),
    ('sourceDirName','known-role','source-directory'),('variable','known-role','environment-name'),
    ('folder','known-role','special-folder-selector'),('key','known-role','dictionary-key'),
    ('OwnedPrivateParameter','unknown',None),('PATH','unknown',None),('private/value','malformed',None),
    ('x'*65,'malformed',None),('','malformed',None),('path ','malformed',None),
    ('path [private\x00project]','malformed',None)])
def test_argument_parameter_line_has_only_exact_public_roles_without_token_or_value_disclosure(module,parameter,state,role):
    context=owned_argument_record(module,'The path is not of a legal form.',
        ['Parameter name: '+parameter+' [C:/r19-authored-private/project]'])['argument_context']
    assert context['parameter_state']==state and context['parameter_role']==role
    assert 'OwnedPrivateParameter' not in json.dumps(context) and 'private/value' not in json.dumps(context)
    assert 'r19-authored-private' not in json.dumps(context)


def test_argument_duplicate_malformed_or_late_parameter_lines_do_not_invent_a_role(module):
    message='The path is not of a legal form.'
    duplicate=owned_argument_record(module,message,['Parameter name: path','Parameter name: private-key'])['argument_context']
    assert duplicate['parameter_state']=='ambiguous' and duplicate['parameter_role'] is None
    malformed=owned_argument_record(module,message,['Parameter name=path'])['argument_context']
    assert malformed['parameter_state']=='malformed' and malformed['parameter_role'] is None
    late=owned_argument_record(module,message,['at Owned.PrivateFrame()','Parameter name: path'])['argument_context']
    assert late['parameter_state']=='not-observed' and late['parameter_role'] is None


@pytest.mark.parametrize('newline',['\n','\r\n'])
@pytest.mark.parametrize('continuation',[
    'Additional opaque message text.', 'System.IO.IOException: An unrelated opaque failure.', '',
    'Parameter name=path', 'at System.IO.Path.GetPathRoot(String path) non-frame opaque trailer'])
def test_argument_inadmissible_continuation_revokes_resource_and_cannot_jump_to_a_later_frame(module,newline,continuation):
    frame='at System.IO.Path.GetPathRoot(String opaqueValue)'
    valid=owned_argument_record(module,'The path is not of a legal form.',[frame],newline=newline)
    value=owned_argument_record(module,'The path is not of a legal form.',[continuation,frame],newline=newline)
    context=value['argument_context']
    assert context['state']=='incomplete' and context['resource_state']=='unknown' and context['resource_label'] is None
    assert context['framework_frames']==[] and context!=valid['argument_context'] and value!=valid
    assert 'opaque' not in json.dumps(context) and 'System.IO.IOException' not in json.dumps(context)


def test_argument_unknown_continuation_after_stack_keeps_prior_observation_but_closes_later_roles(module):
    context=owned_argument_record(module,'The path is not of a legal form.',[
        'at System.IO.Path.NormalizePath(String path)', 'unrelated opaque continuation',
        'at System.IO.Path.GetPathRoot(String path)'])['argument_context']
    assert context['state']=='incomplete' and context['resource_label']=='path-illegal'
    assert context['framework_frames']==[{'section':'argument-inner','role':'path-normalization'}]


@pytest.mark.parametrize('newline',['\n','\r\n'])
def test_argument_real_blank_boundary_closes_context_while_terminal_newline_does_not(module,newline):
    prefix='error MSB4018: '
    initial=newline.join(prefix+body for body in ('The "CL" task failed unexpectedly.',
        owned_type_initializer()+' ---> System.ArgumentException: The path is not of a legal form.'))
    terminal=module.msb4018_task_context(initial+newline,16)['records'][0]['argument_context']
    assert terminal['state']=='observed' and terminal['resource_label']=='path-illegal'
    records=module.msb4018_task_context(initial+newline+newline+prefix+'at System.IO.Path.GetPathRoot(String path)',16)['records']
    assert len(records)==2 and records[0]['argument_context']['state']=='incomplete'
    assert records[0]['argument_context']['resource_state']=='unknown' and records[0]['argument_context']['framework_frames']==[]
    assert records[1]['argument_context']['state']=='not-observed' and records[1]['argument_context']['framework_frames']==[]


def test_argument_known_parameter_and_end_marker_allow_only_coherent_wrapper_flow(module):
    context=owned_argument_record(module,'The path is not of a legal form.',[
        'Parameter name: path','--- End of inner exception stack trace ---',
        'at Microsoft.Build.Utilities.FileTracker.FormatRootingMarker(ITaskItem[] sources)'])['argument_context']
    assert context['state']=='observed' and context['resource_label']=='path-illegal' and context['parameter_role']=='path-input'
    assert context['framework_frames']==[{'section':'wrapper-context','role':'file-tracker-caller'}]
    duplicate=owned_argument_record(module,'The path is not of a legal form.',[
        'Parameter name: path','Parameter name: path','at System.IO.Path.GetPathRoot(String path)'])['argument_context']
    assert duplicate['state']=='incomplete' and duplicate['parameter_state']=='ambiguous'
    assert duplicate['resource_state']=='unknown' and duplicate['framework_frames']==[]


def test_argument_framework_frames_separate_inner_throw_operations_from_wrapper_callers(module):
    context=owned_argument_record(module,'The path is not of a legal form.',[
        'Parameter name: path',
        'at System.IO.Path.NormalizePath(String privateValue, Boolean fullCheck) in C:/r19-authored-private/source:line 42',
        'at System.IO.Path.GetPathRoot(String path) [C:/r19-authored-private/project]',
        'at Microsoft.Build.Utilities.FileTracker.InitializeCommonApplicationDataPaths()',
        'at Microsoft.Build.Utilities.FileTracker..cctor()',
        '--- End of inner exception stack trace --- [C:/r19-authored-private/project]',
        'at Microsoft.Build.Utilities.FileTracker.FormatRootingMarker(ITaskItem[] privateItems)',
        'at Owned.PrivateCaller()'])['argument_context']
    assert context['framework_frames']==[{'section':'argument-inner','role':role} for role in
        ('path-normalization','path-root','file-tracker-common-data','file-tracker-initialization')]+[
        {'section':'wrapper-context','role':'file-tracker-caller'}]
    assert context['unknown_frame_seen'] is True and context['frames_truncated'] is False
    for private in ('privateValue','privateItems','PrivateCaller','r19-authored-private','42','System.IO.Path'):
        assert private not in json.dumps(context)


@pytest.mark.parametrize('frame',[
    'at System.IO.Path.GetPathRootInjected(String privateValue)',
    'at System.IO.Path.GetPathRoot('+('x'*1025)+')',
    'at System.IO.Path.GetPathRoot(String path) in '+('x'*2049),
    'at System.IO.Path.GetPathRoot(String path) private non-frame trailer',
    'at System.IO.Path.GetPathRoot(String\x00 path)'])
def test_argument_frame_method_boundaries_signatures_and_trailers_cannot_expand_the_allowlist(module,frame):
    context=owned_argument_record(module,'private custom message',[frame],initializer='Owned.PrivateInitializer')['argument_context']
    assert context['framework_frames']==[] and context['unknown_frame_seen'] is True
    assert context['initializer_roles']==[] and context['unknown_initializer_seen'] is True
    assert context['resource_state']=='unknown'
    assert 'Owned' not in json.dumps(context) and 'private custom' not in json.dumps(context)


def test_argument_unknown_stack_lines_consume_the_shared_frame_limit_and_new_task_resets_it(module):
    frames=['at Owned.PrivateFrame()']*10+['at System.IO.Path.GetPathRoot(String path)']*7
    context=owned_argument_record(module,'The path is not of a legal form.',frames)['argument_context']
    assert len(context['framework_frames'])==6 and context['frames_truncated'] is True and context['unknown_frame_seen'] is True
    block='\n'.join('error MSB4018: '+body for body in ('The "CL" task failed unexpectedly.',
        owned_type_initializer()+' ---> System.ArgumentException: The path is not of a legal form.',*frames))
    result=module.msb4018_task_context('\n'.join((block,block,block)),2)
    assert len(result['records'])==2 and result['truncated'] is True
    assert all(len(row['argument_context']['framework_frames'])==6 for row in result['records'])


def test_argument_context_requires_the_admitted_argument_leaf_and_never_inspects_private_paths(module,monkeypatch):
    bodies=['The "CL" task failed unexpectedly.',owned_type_initializer()+' ---> System.ArgumentException: private message at System.IO.Path.GetPathRoot(String path)',
        'at Owned.PrivateCaller(C:/r19-authored-private/value)']
    def forbidden(*_args,**_kwargs):pytest.fail('Argument context must not inspect files or call native APIs.')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'stat',forbidden);patch.setattr(Path,'lstat',forbidden);patch.setattr(Path,'open',forbidden)
        context=module.msb4018_task_context('\n'.join('error MSB4018: '+body for body in bodies),16)['records'][0]['argument_context']
    assert context['resource_state']=='unknown' and context['framework_frames']==[]
    assert context['unknown_frame_seen'] is True and 'r19-authored-private' not in json.dumps(context)
    for body in ('System.ArgumentException: The path is not of a legal form.',
            'System.TypeInitializationException: private prose ---> System.ArgumentException: The path is not of a legal form.'):
        record=module.msb4018_task_context('error MSB4018: '+body,16)['records'][0]
        assert record['argument_context']['state']=='not-observed'


@pytest.mark.parametrize('newline',['\n','\r\n'])
@pytest.mark.parametrize('extra_byte',[False,True])
def test_argument_context_keeps_exact_utf8_block_cap_for_resource_parameter_and_frame(module,monkeypatch,newline,extra_byte):
    bodies=[owned_type_initializer('Owned.\u4e2d')+' ---> System.ArgumentException: The path is not of a legal form.',
        'Parameter name: path','at System.IO.Path.GetPathRoot(String path)']
    content=newline.join('error MSB4018: '+body for body in bodies)
    monkeypatch.setattr(module,'MSB4018_BLOCK_BYTES',len(content.encode())-int(extra_byte))
    record=module.msb4018_task_context(content,16)['records'][0];context=record['argument_context']
    assert context['state']==('byte-limit' if extra_byte else 'observed')
    assert context['resource_label']=='path-illegal' and context['parameter_role']=='path-input'
    assert context['framework_frames']==([] if extra_byte else [{'section':'argument-inner','role':'path-root'}])


@pytest.mark.parametrize('newline',['\n','\r\n'])
@pytest.mark.parametrize('form',['inline','continuation','header-continuation'])
def test_msb4018_standard_type_initializer_chain_retains_order_without_private_types_or_messages(module,newline,form):
    prefix='C:/r19-authored-private/task(5,7): error MSB4018: '
    outer=owned_type_initializer();inner='System.ArgumentNullException: private parameter (Exception from HRESULT: 0x80004003)'
    if form=='inline':bodies=[outer+' ---> '+inner]
    elif form=='continuation':bodies=[outer+' [C:/r19-authored-private/project]','---> '+inner]
    else:bodies=[outer+' ---> [C:/r19-authored-private/project]',inner]
    content=newline.join([prefix+'The "CL" task failed unexpectedly.']+[prefix+body for body in bodies])
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['exception_chain']=={'state':'observed-inner','families':['type-initialization','argument-null'],'truncated':False}
    assert record['exception_families']==['argument-null','type-initialization']
    assert record['hresult_labels']==['e-pointer'] and record['context_truncated'] is False
    for private in ('Owned.PrivateInitializer','r19-authored-private','private parameter','System.ArgumentNullException','0x80004003'):
        assert private not in json.dumps(record)


@pytest.mark.parametrize('inner,state,families',[
    ('Owned.PrivateException: private message','unknown-inner',['type-initialization','unknown-exception']),
    ('not an exception header','malformed-inner-header',['type-initialization']),
    ('','malformed-inner-header',['type-initialization'])])
def test_msb4018_inner_chain_unknown_and_malformed_headers_have_only_finite_states(module,inner,state,families):
    content='error MSB4018: The "CL" task failed unexpectedly.\nerror MSB4018: '+owned_type_initializer()+' ---> '+inner
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['exception_chain']=={'state':state,'families':families,'truncated':False}
    assert 'Owned' not in json.dumps(record) and 'private message' not in json.dumps(record)


@pytest.mark.parametrize('body,state,families',[
    ('System.TypeInitializationException: private message ---> System.ArgumentNullException: private detail',
        'unrecognized-wrapper',['type-initialization']),
    ('at '+owned_type_initializer()+' ---> System.ArgumentNullException: private detail','not-observed',[]),
    ('System.ArgumentNullException: '+owned_type_initializer()+' ---> System.DllNotFoundException: private detail',
        'not-observed',[]),
    (owned_type_initializer('Owned ---> System.ArgumentNullException: private detail'),'inner-not-observed',['type-initialization']),
    (owned_type_initializer()+' private prose ---> System.ArgumentNullException: private detail','malformed-inner-marker',['type-initialization']),
    (owned_type_initializer()+' -- > System.ArgumentNullException: private detail','malformed-inner-marker',['type-initialization'])])
def test_msb4018_message_stack_and_malformed_marker_mentions_cannot_invent_an_inner_chain(module,body,state,families):
    content='error MSB4018: The "CL" task failed unexpectedly.\nerror MSB4018: '+body
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['exception_chain']=={'state':state,'families':families,'truncated':False}
    assert 'private detail' not in json.dumps(record) and 'Owned' not in json.dumps(record)


def test_msb4018_inner_chain_does_not_continue_after_intervening_stack_or_a_non_wrapper_leaf(module):
    prefix='error MSB4018: '
    bodies=[owned_type_initializer(),'at Owned.PrivateFrame: private detail','---> System.ArgumentNullException: private detail']
    record=module.msb4018_task_context('\n'.join(prefix+body for body in bodies),16)['records'][0]
    assert record['exception_chain']=={'state':'inner-not-observed','families':['type-initialization'],'truncated':False}
    body=owned_type_initializer()+' ---> System.ArgumentNullException: private text ---> System.DllNotFoundException: private detail'
    record=module.msb4018_task_context(prefix+body,16)['records'][0]
    assert record['exception_chain']=={'state':'observed-inner','families':['type-initialization','argument-null'],'truncated':False}
    assert 'dll-not-found' not in record['exception_families']


@pytest.mark.parametrize('wrappers,truncated',[(7,False),(8,True)])
def test_msb4018_nested_type_initializer_depth_is_eight_including_the_outer_wrapper(module,wrappers,truncated):
    body=' ---> '.join([owned_type_initializer('Owned.Private'+str(i)) for i in range(wrappers)]+
        ['System.ArgumentNullException: private final cause'])
    record=module.msb4018_task_context('error MSB4018: '+body,16)['records'][0]
    chain=record['exception_chain']
    assert chain['state']==('depth-limit' if truncated else 'observed-inner') and chain['truncated'] is truncated
    assert len(chain['families'])==8
    assert chain['families']==(['type-initialization']*8 if truncated else ['type-initialization']*7+['argument-null'])
    assert record['context_truncated'] is False
    assert 'Owned' not in json.dumps(record) and 'private final cause' not in json.dumps(record)


@pytest.mark.parametrize('newline',['\n','\r\n'])
@pytest.mark.parametrize('extra_byte',[False,True])
def test_msb4018_type_initializer_chain_obeys_exact_utf8_block_boundary(module,monkeypatch,newline,extra_byte):
    prefix='error MSB4018: '
    outer=prefix+owned_type_initializer('Owned.\u4e2d')
    inner=prefix+'---> System.ArgumentNullException: private parameter'
    content=newline.join((outer,inner))
    monkeypatch.setattr(module,'MSB4018_BLOCK_BYTES',len(content.encode())-int(extra_byte))
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['exception_chain']=={'state':'byte-limit' if extra_byte else 'observed-inner',
        'families':['type-initialization'] if extra_byte else ['type-initialization','argument-null'],
        'truncated':extra_byte}
    assert record['context_truncated'] is extra_byte


def test_msb4018_requires_anchored_error_and_literal_quotes_without_unescaping(module):
    content='private error MSB4018: The "CL" task failed unexpectedly.\n'
    content+='warning MSB4018: The "CL" task failed unexpectedly.\n'
    assert module.msb4018_task_context(content,16)=={'records':[],'truncated':False}
    content+='error MSB4018: The \\"CL\\" task failed unexpectedly.\n'
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['literal_match_state']=='unrecognized-template' and record['task_label']=='unknown-task'
    assert record['exception_families']==record['hresult_labels']==record['win32_labels']==[]


def test_msb4018_and_import_records_share_one_limit_across_both_fixed_logs(module,tmp_path,monkeypatch):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    task='error MSB4018: The "SetEnv" task failed unexpectedly.\n'
    (directory/'CMakeConfigureLog.yaml').write_text('error MSB4019: private import template\n'+task)
    (directory/'CMakeError.log').write_text(task+task)
    monkeypatch.setattr(module,'IMPORT_CONTEXT_LIMIT',3)
    logs=module.nested_configure_log_context(tmp_path)['logs']
    assert len(logs[0]['msb4019_imports']['records'])==len(logs[0]['msb4018_tasks']['records'])==1
    assert len(logs[1]['msb4018_tasks']['records'])==1 and logs[1]['msb4018_tasks']['truncated'] is True
    assert sum(len(row[key]['records']) for row in logs for key in ('msb4019_imports','msb4018_tasks'))==3
    assert 'private' not in json.dumps(logs)


def test_msb4018_record_byte_cap_prevents_late_exception_labels_even_with_multibyte_text(module,monkeypatch):
    header='error MSB4018: The "SetEnv" task failed unexpectedly.\n'
    line='error MSB4018: '+('\u4e2d'*30)+'\n'
    late='error MSB4018: System.ArgumentNullException: private late (Exception from HRESULT: 0x80004003)\n'
    monkeypatch.setattr(module,'MSB4018_BLOCK_BYTES',len((header+line).encode())-2)
    record=module.msb4018_task_context(header+line+late,16)['records'][0]
    assert record['task_label']=='set-env' and record['context_truncated'] is True
    assert record['exception_families']==record['hresult_labels']==record['win32_labels']==[]


@pytest.mark.parametrize('newline',['\n','\r\n'])
def test_msb4018_many_short_lines_count_connecting_newline_bytes_before_late_exception(module,newline):
    header='error MSB4018: The "SetEnv" task failed unexpectedly.'
    short='error MSB4018: x'
    late='error MSB4018: System.ArgumentNullException: private late (Exception from HRESULT: 0x80004003)'
    count=(module.MSB4018_BLOCK_BYTES-len((header+late).encode()))//len(short.encode())
    content=newline.join([header]+[short]*count+[late])
    assert len(content.encode())>module.MSB4018_BLOCK_BYTES
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['task_label']=='set-env' and record['context_truncated'] is True
    assert record['exception_families']==record['hresult_labels']==record['win32_labels']==[]


@pytest.mark.parametrize('newline',['\n','\r\n'])
@pytest.mark.parametrize('extra_byte',[False,True])
def test_msb4018_byte_span_boundary_includes_only_connecting_line_endings(module,monkeypatch,newline,extra_byte):
    header='error MSB4018: The "SetEnv" task failed unexpectedly.'
    exception='error MSB4018: System.ArgumentNullException: private parameter'
    content=newline.join((header,exception))
    monkeypatch.setattr(module,'MSB4018_BLOCK_BYTES',len(content.encode())-int(extra_byte))
    record=module.msb4018_task_context(content,16)['records'][0]
    assert record['context_truncated'] is extra_byte
    assert record['exception_families']==([] if extra_byte else ['argument-null'])


@pytest.mark.parametrize('newline',['\n','\r\n'])
def test_msb4018_new_task_block_resets_without_charging_the_previous_block_gap(module,monkeypatch,newline):
    block=newline.join(('error MSB4018: The "SetEnv" task failed unexpectedly.',
        'error MSB4018: System.ArgumentNullException: private parameter'))
    monkeypatch.setattr(module,'MSB4018_BLOCK_BYTES',len(block.encode()))
    records=module.msb4018_task_context(newline.join((block,block)),16)['records']
    assert len(records)==2
    assert all(record['exception_families']==['argument-null'] and record['context_truncated'] is False for record in records)


def test_msb4018_long_nonmatching_headers_finish_in_one_bounded_child_within_the_real_log_tail(module,tmp_path):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    noise=((' '*32000+'x\n')+(' '*32000+'x\r\n'))*24
    content=noise+'error MSB4018: The "SetEnv" task failed unexpectedly.\n'
    content+=('error MSB4018: The "CL" task failed unexpectedly.\nerror MSB4018: '
        'System.TypeInitializationException: '+' '*16000+'private non-wrapper\n')*8
    content+=('error MSB4018: The "CL" task failed unexpectedly.\nerror MSB4018: '+
        owned_type_initializer()+' ---> System.ArgumentException: '+'x'*28000+'\n'+
        'error MSB4018: at System.IO.Path.GetPathRoot('+('x'*1025)+')\n')*3
    assert len(content.encode())<module.LOG_TAIL_BYTES
    (directory/'CMakeConfigureLog.yaml').write_bytes(content.encode())
    script='''import importlib.util, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("owned_asr_parser",sys.argv[1])
driver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
logs=driver.nested_configure_log_context(Path(sys.argv[2]))["logs"]
records=logs[0]["msb4018_tasks"]["records"]
assert len(records)==12 and records[0]["task_label"]=="set-env"
assert records[0]["context_truncated"] is False
assert all(item["exception_chain"]["state"]=="unrecognized-wrapper" for item in records[1:9])
assert all(item["argument_context"]["resource_state"]=="unknown" and item["argument_context"]["unknown_frame_seen"] for item in records[9:])
print("bounded-msb4018-parser-passed")
'''
    result=module.subprocess.run([module.sys.executable,'-I','-B','-c',script,
        str(ROOT/'scripts/reference-asr.py'),str(tmp_path)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and result.stdout=='bounded-msb4018-parser-passed\n' and result.stderr==''


def test_msb4018_full_tail_discards_partial_prefix_without_more_reads(module,tmp_path,monkeypatch):
    directory=tmp_path/'build/CMakeFiles';directory.mkdir(parents=True)
    partial='error MSB4018: The "CL" task failed unexpectedly.\n'
    complete='error MSB4018: The "SetEnv" task failed unexpectedly.\n'
    retained=(partial+complete).encode()
    (directory/'CMakeConfigureLog.yaml').write_bytes(b'private truncated prefix '+retained)
    monkeypatch.setattr(module,'LOG_TAIL_BYTES',len(retained))
    monkeypatch.setattr(module,'NESTED_LOG_TOTAL_BYTES',len(retained))
    logs=module.nested_configure_log_context(tmp_path)['logs']
    assert [row['task_label'] for row in logs[0]['msb4018_tasks']['records']]==['set-env']
    assert logs[1]['state']=='total-byte-limit' and logs[1]['msb4018_tasks']['records']==[]
    assert 'private' not in json.dumps(logs)


@pytest.mark.parametrize('kind,expected', [('command', 'private-command-failed'),
    ('timeout', 'owned-process-timeout'), ('cleanup', 'io-or-cleanup-unconfirmed')])
def test_build_failure_wrapper_never_issues_a_success_receipt(module, tmp_path, monkeypatch, capsys, kind, expected):
    _source, inputs, output = prepared(module, tmp_path, monkeypatch)
    logs = output / 'private-logs'; logs.mkdir()
    (logs / 'build.log').write_text('fatal error C2065: private-symbol-and-model-text\n')
    def failure(*_args):
        module.build_phase('native-build')
        if kind == 'timeout':
            raise module.subprocess.TimeoutExpired([str(tmp_path / 'private-tool.exe')], 1)
        if kind == 'cleanup':
            raise OSError(str(tmp_path / 'private-handle-diagnostic'))
        raise ValueError(str(tmp_path / 'private-native-failure'))
    monkeypatch.setattr(module, '_build', failure)
    with pytest.raises((ValueError, OSError, module.subprocess.TimeoutExpired)):
        module.build(output, tmp_path / 'roots.json', tmp_path / 'vs', inputs)
    report = module.read_json(output / 'ASR-FAILURE.json')
    assert report['status'] == 'failed' and report['failure_category'] == expected
    assert report['diagnostics']['known_codes'] == ['C2065']
    assert report['success_receipt_for_this_attempt'] is False
    assert not (output / 'ASR-RECEIPT.json').exists()
    public = capsys.readouterr().err + json.dumps(report)
    assert str(tmp_path) not in public and 'private-symbol-and-model-text' not in public


def test_failure_report_refuses_unprepared_or_unbounded_caller_and_preserves_previous_record(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        module.failed_build_receipt(output, str(tmp_path / 'private-phase'), ValueError('private'))
    assert not (output / 'ASR-FAILURE.json').exists()
    empty = tmp_path / 'unprepared'; empty.mkdir()
    with pytest.raises(OSError):
        module.failed_build_receipt(empty, 'native-build', ValueError('private'))
    assert list(empty.iterdir()) == []
    module.failed_build_receipt(output, 'native-build', ValueError('first private message'))
    original = (output / 'ASR-FAILURE.json').read_bytes()
    with pytest.raises(FileExistsError):
        module.failed_build_receipt(output, 'native-build', ValueError('second private message'))
    assert (output / 'ASR-FAILURE.json').read_bytes() == original


def test_failed_receipt_cannot_be_published_as_native_asr_success(module, tmp_path, monkeypatch):
    _source, _inputs, output = prepared(module, tmp_path, monkeypatch)
    failed = module.failed_build_receipt(output, 'native-build', ValueError('owned failure'))
    with pytest.raises(ValueError): module.publish_success_receipt(output, failed)
    assert not (output / 'ASR-RECEIPT.json').exists()
    assert not (output / 'PRIVATE-ASR-RECEIPT.pending.json').exists()


def test_fixture_is_owned_dynamic_format_graph_with_no_pretrained_payload(tmp_path):
    fixture = load('asr_owned_fixture_test', 'scripts/probe-reference-asr.py')
    report = fixture.fixtures(tmp_path / 'fixtures')
    graph = (tmp_path / 'fixtures/model.onnx').read_bytes()
    assert len(graph) < 4096
    assert b'OwnedFormatFixture' in graph and b'Range' in graph and b'OneHot' in graph
    assert b'features_length' in graph and b'language' in graph and b'text_norm' in graph
    assert b'no trained weights' in graph
    assert graph != (tmp_path / 'fixtures/wrong-shape.onnx').read_bytes()
    assert report['silence.f32']['bytes'] == 8000 * 4
    assert not any((tmp_path / 'fixtures/silence.f32').read_bytes())
    assert (tmp_path / 'fixtures/tokens.txt').read_text().endswith('AUTHORED 5\n')


def test_private_variant_wheel_preserves_notices_and_actual_record_hashes(module, tmp_path):
    import base64
    import csv
    import zipfile
    output = tmp_path / 'private-output'
    package = output / 'sources/sherpa-onnx/sherpa-onnx/python/sherpa_onnx'
    package.mkdir(parents=True)
    (package / '__init__.py').write_bytes(b'# owned Python package fixture\n')
    native = output / 'sources/onnxruntime/lib'; native.mkdir(parents=True)
    (native / 'onnxruntime.dll').write_bytes(b'owned non-executable native-file fixture')
    pyd = tmp_path / '_sherpa_onnx.cp312-win_amd64.pyd'; pyd.write_bytes(b'owned non-executable binding fixture')
    notice = output / 'notices/sherpa-onnx/LICENSE'; notice.parent.mkdir(parents=True)
    notice.write_bytes(b'owned retained notice\r\n')
    wheel = module.make_wheel(output, pyd)
    with zipfile.ZipFile(wheel) as archive:
        dist = 'proxy_r19_sherpa_asr_reference-1.13.8+proxy.r19.asr1.dist-info'
        assert archive.read(dist + '/notices/sherpa-onnx/LICENSE') == b'owned retained notice\r\n'
        assert archive.read(dist + '/notices/PROJECT-LICENSE.txt') == (ROOT / 'LICENSE').read_bytes()
        assert archive.read(dist + '/notices/TTS-OFF-MODIFICATION.patch') == (ROOT / module.pin()['patch']['file']).read_bytes()
        for name, expected_notice in module.pin()['patch_notices'].items():
            delivered = archive.read(dist + '/notices/' + Path(name).name)
            assert delivered == (ROOT / name).read_bytes()
            assert module.attributes(delivered) == expected_notice
        notice = archive.read(dist + '/notices/SHERPA-PATCH-NOTICE.txt')
        assert b'sherpa_onnx/__init__.py' in notice
        assert b'__version__ = "1.13.8+proxy.r19.asr1"' in notice
        metadata = archive.read(dist + '/METADATA')
        assert b'Name: proxy-r19-sherpa-asr-reference' in metadata
        assert b'sherpa-onnx-core' not in metadata
        for name, digest, size in csv.reader(io.StringIO(archive.read(dist + '/RECORD').decode())):
            if name.endswith('/RECORD'): continue
            data = archive.read(name)
            expected = 'sha256=' + base64.urlsafe_b64encode(bytes.fromhex(module.sha(data))).decode().rstrip('=')
            assert digest == expected and int(size) == len(data)


def test_manual_workflow_has_metadata_only_delivery_and_no_default_runtime_replacement(module):
    workflow = (ROOT / '.github/workflows/r19-asr-source-experiment.yml').read_text()
    assert 'workflow_dispatch:' in workflow and '\n  push:' not in workflow
    uploads = set(re.findall(r'\$\{\{\s*env\.R19_ASR_OUTPUT\s*\}\}/([^\s\'\"]+)', workflow))
    assert {'PREPARED.json', 'ASR-RECEIPT.json'} <= uploads
    assert uploads <= {'PREPARED.json', 'ASR-RECEIPT.json', 'ASR-FAILURE.json'}
    assert module.pin()['identity'] == 'sherpa-onnx-1.13.8-asr-reference.1'
    assert module.pin()['cmake']['SHERPA_ONNX_ENABLE_TTS'] == 'OFF'
    assert 'SHERPA_ONNX_SPLIT_PYTHON_PACKAGE' not in module.pin()['cmake']
    locked = (ROOT / 'requirements.lock.txt').read_text()
    assert 'sherpa_onnx==1.13.8' in locked and 'sherpa-onnx-core==1.13.8' in locked
