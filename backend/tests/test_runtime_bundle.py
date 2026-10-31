"""Frozen-only failure contracts missing from source worker/process tests.

These synthetic fixtures need no OCR, game, account or native model. They prevent
bootloader recursion, resource escapes/tampering and accidental diagnostic writes;
they do not establish actual Windows bootloader/DLL/Job Object acceptance.
"""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

from backend import bundle_entry
from backend import runtime_bundle as bundle


def frozen_layout(tmp_path, *, children=(), resources=None, profile='diagnostic'):
    root = tmp_path.resolve()
    app = root / 'Application 空格'
    app.mkdir()
    internal = app / '_internal'
    internal.mkdir()
    executable = app / 'ProxyTranscriptRuntime.exe'
    executable.touch()
    private = root / 'private'
    return bundle.RuntimeLayout(mode='bundle', application_root=app, resource_root=internal,
        data_root=private / 'data', settings_root=private, cache_root=private / 'cache',
        tool_root=private / 'tools', work_root=private / 'work', state_root=private / 'state',
        default_export_root=private / 'exports', executable=executable, children=children,
        resources=resources or {}, version='0.22.0', source_commit='a' * 40, build_id='synthetic', profile=profile)


def test_source_roots_ignore_cwd_and_keep_legacy_data(tmp_path, monkeypatch):
    unrelated = tmp_path / 'unrelated'
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    legacy = tmp_path / 'Legacy 空格'
    layout = bundle.discover_layout({'PROXY_TRANSCRIPT_PROJECT_ROOT': str(legacy), 'LOCALAPPDATA': str(tmp_path)})
    assert layout.application_root == Path(bundle.__file__).resolve().parents[1]
    assert layout.legacy_project_root == legacy and layout.data_root == legacy / 'data'
    assert layout.work_root == legacy / 'work/voice-assets'
    assert not legacy.exists(), 'Root discovery must not prepare or migrate anything'
    assert layout.resource('package.json').is_file()


def test_source_does_not_override_explicit_child_root_with_frozen_environment(tmp_path):
    layout = bundle.discover_layout({'PROXY_TRANSCRIPT_PROJECT_ROOT': str(tmp_path / 'legacy')})
    env = layout.child_environment(environ={'PROXY_TRANSCRIPT_DATA_ROOT': str(tmp_path / 'different'), 'KEEP': 'value'})
    assert 'PROXY_TRANSCRIPT_DATA_ROOT' not in env and env['KEEP'] == 'value'
    assert env['PROXY_TRANSCRIPT_PROJECT_ROOT'] == str(tmp_path / 'legacy')
    with pytest.raises(bundle.RuntimeBundleError, match='frozen-only'):
        bundle.discover_layout({'PROXY_TRANSCRIPT_PROJECT_ROOT': str(tmp_path / 'legacy'),
            'PROXY_TRANSCRIPT_DATA_ROOT': str(tmp_path / 'different')})


@pytest.mark.parametrize('name', ['../package.json', '/package.json', 'C:package.json',
    'C:/package.json', 'assets\\model', 'assets//model', 'assets/model:stream',
    'assets/model.', 'assets/CON.txt', './package.json'])
def test_resource_names_reject_portable_and_windows_alias_escapes(name):
    with pytest.raises(bundle.RuntimeBundleError, match='resource name'):
        bundle.relative_resource(name)


def test_frozen_resources_require_allowlist_bytes_and_containment(tmp_path):
    content = b'owned synthetic resource'
    layout = frozen_layout(tmp_path, resources={'synthetic.json': hashlib.sha256(content).hexdigest()})
    path = layout.resource_root / 'synthetic.json'
    with pytest.raises(bundle.RuntimeBundleError, match='missing'):
        layout.resource('synthetic.json')
    path.write_bytes(content)
    assert layout.resource('synthetic.json') == path
    path.write_bytes(b'changed')
    with pytest.raises(bundle.RuntimeBundleError, match='checksum'):
        layout.resource('synthetic.json')
    with pytest.raises(bundle.RuntimeBundleError, match='allowlisted'):
        layout.resource('not-collected.json')
    path.unlink()
    outside = tmp_path / 'outside.json'
    outside.write_bytes(content)
    path.symlink_to(outside)
    with pytest.raises(bundle.RuntimeBundleError, match='outside'):
        layout.resource('synthetic.json')


def test_layout_refuses_writable_app_and_cache_data_overlap(tmp_path):
    layout = frozen_layout(tmp_path)
    with pytest.raises(bundle.RuntimeBundleError, match='immutable'):
        replace(layout, data_root=layout.application_root / 'data')
    with pytest.raises(bundle.RuntimeBundleError, match='Disposable'):
        replace(layout, cache_root=layout.data_root.parent)
    with pytest.raises(bundle.RuntimeBundleError, match='Durable'):
        replace(layout, tool_root=layout.data_root / 'tools')
    with pytest.raises(bundle.RuntimeBundleError, match='source layout'):
        _ = layout.legacy_project_root


def test_frozen_root_selection_rejects_raw_symlink_and_repository_ancestry(tmp_path, monkeypatch):
    layout = frozen_layout(tmp_path)
    target = tmp_path.resolve() / 'outside'
    target.mkdir()
    linked = tmp_path.resolve() / 'linked'
    linked.symlink_to(target, target_is_directory=True)
    with pytest.raises(bundle.RuntimeBundleError, match='links or reparse'):
        replace(layout, data_root=linked / 'not-created')
    repo = tmp_path.resolve() / 'repository'
    repo.mkdir()
    (repo / '.git').write_text('synthetic worktree pointer')
    with pytest.raises(bundle.RuntimeBundleError, match='repository'):
        replace(layout, data_root=repo / 'private-data')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(layout.resource_root), raising=False)
    monkeypatch.setattr(sys, 'executable', str(layout.executable))
    manifest = {'schema': bundle.MANIFEST_SCHEMA, 'profile': 'diagnostic', 'version': '0.22.0',
        'source_commit': 'a' * 40, 'build_id': 'synthetic', 'children': [], 'resources': {}}
    (layout.resource_root / 'runtime-manifest.json').write_text(json.dumps(manifest))
    env = layout.child_environment(environ={})
    env['PROXY_TRANSCRIPT_DATA_ROOT'] = str(linked / 'not-created')
    with pytest.raises(bundle.RuntimeBundleError, match='links or reparse'):
        bundle.discover_layout(env)
    assert not (target / 'not-created').exists()


def test_durable_settings_cannot_be_equal_to_or_below_disposable_roots(tmp_path):
    layout = frozen_layout(tmp_path)
    for selected in (layout.cache_root, layout.cache_root / 'settings', layout.work_root / 'settings'):
        with pytest.raises(bundle.RuntimeBundleError, match='Settings root'):
            replace(layout, settings_root=selected)
    assert layout.settings_root in layout.cache_root.parents, 'The intended settings parent may contain disposable sibling groups'


@pytest.mark.parametrize('kind', ['api', 'api-wal', 'api-grammar'])
def test_fixed_api_probe_dispatch_keeps_experimental_main_image_gate(tmp_path, monkeypatch, kind):
    layout = frozen_layout(tmp_path, profile='runtime-experiment')
    calls = []
    monkeypatch.setattr(bundle_entry, 'discover_layout', lambda: layout)
    monkeypatch.setattr(bundle_entry, 'import_module', lambda name: SimpleNamespace(
        main=lambda probe_kind, current: calls.append((name, probe_kind, current)) or 17))
    assert bundle_entry.main(['--runtime-probe', kind]) == 17
    assert calls == [('backend.runtime_probe', kind, layout)]
    for forbidden in (replace(layout, profile='runtime'), replace(layout, profile='diagnostic'),
                      replace(layout, executable=layout.application_root/'ProxyTranscriptAsr.exe')):
        monkeypatch.setattr(bundle_entry, 'discover_layout', lambda: forbidden)
        with pytest.raises(bundle.RuntimeBundleError): bundle_entry.main(['--runtime-probe', kind])
    assert len(calls) == 1 and 'api-wal' not in bundle_entry.CHILD_TARGETS and 'api-grammar' not in bundle_entry.CHILD_TARGETS
    for arguments in (['--runtime-probe', 'api-wal-extra'], ['--runtime-probe', kind, 'extra']):
        with pytest.raises(bundle.RuntimeBundleError): bundle_entry.main(arguments)


def test_fixed_wal_probe_requires_exact_supplier_before_api_start(tmp_path, monkeypatch):
    from backend import runtime_probe
    layout = frozen_layout(tmp_path, profile='runtime-experiment')
    layout.state_root.mkdir(parents=True)
    (layout.state_root/'synthetic-probe.json').write_text(json.dumps({'build_id': layout.build_id, 'synthetic': True}))
    calls = []
    monkeypatch.setattr(runtime_probe, 'sys', SimpleNamespace(platform='win32', version_info=(3,12,16),
        addaudithook=lambda hook: calls.append('audit')))
    monkeypatch.setattr(runtime_probe, 'developer_environment', lambda: None)
    monkeypatch.setattr(runtime_probe, 'api', lambda current, **options: calls.append((current, options)) or 23)
    assert runtime_probe.main('api-wal', layout) == 23
    assert calls[-1] == (layout, {'wal_probe': True})
    monkeypatch.setattr(runtime_probe.sys, 'version_info', (3,12,15))
    with pytest.raises(bundle.RuntimeBundleError, match='exact reviewed Python supplier'):
        runtime_probe.main('api-wal', layout)
    assert runtime_probe.main('api', layout) == 23 and calls[-1] == (layout, {'wal_probe': False})
    assert runtime_probe.main('api-grammar', layout) == 23 and calls[-1] == (layout, {'grammar_probe': True})
    supplier = json.loads((Path(__file__).parents[2]/'packaging/runtime-bundle/python-supplier.json').read_text())
    assert supplier['version'] == '3.12.16'


def test_children_use_fixed_dispatch_and_keep_arguments_opaque(tmp_path):
    layout = frozen_layout(tmp_path, children=('language', 'asr'), profile='runtime')
    args = ['--output', str(tmp_path / 'private 中文/out.json'), '--value=$(untouched)']
    assert layout.child_command('language', args) == [str(layout.executable), '--runtime-child', 'language', '--', *args]
    with pytest.raises(bundle.RuntimeBundleError, match='Unknown'):
        layout.child_command('arbitrary.module', [])
    with pytest.raises(bundle.RuntimeBundleError, match='does not include'):
        layout.child_command('mobile-export', [])
    with pytest.raises(bundle.RuntimeBundleError, match='sequence'):
        layout.child_command('language', '--unsafe-string')
    with pytest.raises(bundle.RuntimeBundleError, match='missing'):
        layout.child_command('asr', [])
    helper = layout.application_root / 'asr/ProxyTranscriptAsr.exe'
    helper.parent.mkdir()
    helper.touch()
    assert layout.child_command('asr', [])[0] == str(helper)
    source = bundle.discover_layout({})
    assert source.child_command('language', args)[1:3] == ['-m', 'backend.language_worker']


def test_child_environment_is_copied_and_asr_removes_app_dll_path(tmp_path):
    layout = frozen_layout(tmp_path)
    env = {'PATH': str(layout.resource_root) + bundle.os.pathsep + str(tmp_path / 'system'), 'UNCHANGED': 'value'}
    result = layout.child_environment('asr', env)
    assert result['PATH'] == str(tmp_path / 'system')
    assert result['UNCHANGED'] == 'value' and result['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert result['PROXY_TRANSCRIPT_DATA_ROOT'] == str(layout.data_root)
    assert 'PROXY_TRANSCRIPT_DATA_ROOT' not in env


def test_frozen_discovery_requires_manifest_identity_roots_and_child_profile(tmp_path, monkeypatch):
    layout = frozen_layout(tmp_path)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(layout.resource_root), raising=False)
    monkeypatch.setattr(sys, 'executable', str(layout.executable))
    with pytest.raises(bundle.RuntimeBundleError, match='manifest is missing'):
        bundle.discover_layout({})
    manifest = {'schema': bundle.MANIFEST_SCHEMA, 'profile': 'diagnostic', 'version': '0.22.0',
        'source_commit': 'a' * 40, 'build_id': 'synthetic', 'children': [], 'resources': {}}
    path = layout.resource_root / 'runtime-manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(bundle.RuntimeBundleError, match='explicitly selected'):
        bundle.discover_layout({})
    env = layout.child_environment(environ={})
    assert bundle.discover_layout(env).data_root == layout.data_root
    manifest['children'] = ['api']
    path.write_text(json.dumps(manifest))
    with pytest.raises(bundle.RuntimeBundleError, match='child inventory'):
        bundle.discover_layout(env)


def test_frozen_missing_streams_allow_actual_uvicorn_formatter_without_inheriting_parent_handles(monkeypatch):
    import logging
    from uvicorn.logging import DefaultFormatter
    created = ()
    try:
        with monkeypatch.context() as context:
            context.setattr(sys, 'frozen', True, raising=False)
            for name in ('stdin', 'stdout', 'stderr'):
                context.setattr(sys, name, None)
            created = bundle_entry._prepare_frozen_standard_streams()
            assert len(created) == 3
            # Windows CRT treats NUL as a character device, so automatic color
            # detection may be true. The required contract is usable logging,
            # not a POSIX-specific isatty result.
            formatter = DefaultFormatter()
            record = logging.LogRecord('authored', logging.INFO, '', 0,
                'owned no-console message %s', ('漢字',), None)
            assert formatter.format(record) == 'owned no-console message 漢字'
            assert all(not bundle_entry.os.get_inheritable(stream.fileno()) for stream in created)
            assert sys.stdin.read() == ''
            assert sys.stdout.write('authored no-console output') > 0
            assert sys.stderr.write('authored no-console diagnostic') > 0
    finally:
        for stream in created:
            stream.close()


def test_frozen_entry_preserves_explicit_streams_and_source_callers(monkeypatch):
    import io
    explicit = io.StringIO()
    created = ()
    try:
        with monkeypatch.context() as context:
            context.setattr(sys, 'frozen', True, raising=False)
            context.setattr(sys, 'stdin', explicit)
            context.setattr(sys, 'stdout', explicit)
            context.setattr(sys, 'stderr', None)
            created = bundle_entry._prepare_frozen_standard_streams()
            assert len(created) == 1 and sys.stdin is explicit and sys.stdout is explicit
            assert bundle_entry._prepare_frozen_standard_streams() == ()
            context.setattr(sys, 'frozen', False)
            context.setattr(sys, 'stderr', None)
            assert bundle_entry._prepare_frozen_standard_streams() == () and sys.stderr is None
    finally:
        for stream in created:
            stream.close()


def test_diagnostic_dispatch_refuses_bootstrap_and_api_before_any_worker(tmp_path, monkeypatch, capsys):
    layout = frozen_layout(tmp_path)
    monkeypatch.setattr(bundle_entry, 'discover_layout', lambda: layout)
    monkeypatch.setattr(bundle_entry.runpy, 'run_module', lambda *_a, **_k: pytest.fail('No application worker may start'))
    import backend.windows_preparation_process as preparation
    monkeypatch.setattr(preparation, '_bootstrap', lambda *_a: pytest.fail('Disabled bootstrap cannot spawn'))
    for kind, args in [('api', []), ('windows-bootstrap', ['job-name', 'forbidden.exe'])]:
        with pytest.raises(bundle.RuntimeBundleError, match='does not include'):
            bundle_entry.main(['--runtime-child', kind, '--', *args])
    assert bundle_entry.main(['--runtime-diagnose']) == 0
    diagnostic = json.loads(capsys.readouterr().out)
    assert diagnostic['r19_complete'] is False and diagnostic['children'] == []
    assert str(tmp_path) not in json.dumps(diagnostic)


def test_frontend_experiment_discovery_and_dispatch_cannot_enable_application_children(tmp_path, monkeypatch):
    layout = frozen_layout(tmp_path, children=('frontend',), profile='frontend-experiment')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(layout.resource_root), raising=False)
    monkeypatch.setattr(sys, 'executable', str(layout.executable))
    manifest = {'schema': bundle.MANIFEST_SCHEMA, 'profile': 'frontend-experiment', 'version': '0.22.0',
        'source_commit': 'a' * 40, 'build_id': 'synthetic', 'children': ['frontend'], 'resources': {}}
    path = layout.resource_root / 'runtime-manifest.json'
    path.write_text(json.dumps(manifest))
    assert bundle.discover_layout(layout.child_environment(environ={})).children == ('frontend',)
    monkeypatch.setattr(bundle_entry, 'discover_layout', lambda: layout)
    monkeypatch.setattr(bundle_entry.runpy, 'run_module', lambda *_a, **_k: pytest.fail('No disabled application child may start'))
    for kind in ('api', 'toolkit-update', 'windows-bootstrap', 'asr'):
        with pytest.raises(bundle.RuntimeBundleError, match='does not include'):
            bundle_entry.main(['--runtime-child', kind, '--'])
    manifest['children'].append('api')
    path.write_text(json.dumps(manifest))
    with pytest.raises(bundle.RuntimeBundleError, match='child inventory'):
        bundle.discover_layout(layout.child_environment(environ={}))


def test_bootstrap_joins_job_before_spawn_and_failed_join_never_spawns(monkeypatch):
    import backend.windows_preparation_process as preparation
    from types import SimpleNamespace
    events = []
    kernel = SimpleNamespace(OpenJobObjectW=lambda *_: events.append('open') or 1,
        GetCurrentProcess=lambda: 2, AssignProcessToJobObject=lambda *_: events.append('join') or 1,
        CloseHandle=lambda *_: events.append('close') or 1, SetDllDirectoryW=lambda *_: 1)
    monkeypatch.setattr(preparation, '_kernel', lambda: kernel)
    monkeypatch.setattr(preparation.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    monkeypatch.setattr(preparation.subprocess, 'call', lambda *_a, **_k: events.append('spawn') or 0)
    assert preparation._bootstrap('owned-job', ['worker.exe']) == 0
    assert events == ['open', 'join', 'close', 'spawn']
    events.clear()
    kernel.AssignProcessToJobObject = lambda *_: (_ for _ in ()).throw(OSError('synthetic assignment failure'))
    with pytest.raises(OSError, match='assignment'):
        preparation._bootstrap('owned-job', ['worker.exe'])
    assert events == ['open', 'close']


def test_frozen_windows_command_uses_real_image_and_never_py_file(monkeypatch):
    import backend.windows_preparation_process as preparation
    from types import SimpleNamespace
    image = r'C:\Owned App\ProxyTranscriptRuntime.exe'
    def get_image(_module, output, _size):
        output.value = image
        return len(image)
    tree = preparation.WindowsPreparationProcess.__new__(preparation.WindowsPreparationProcess)
    tree._handle = 123
    tree.kernel, tree.name = SimpleNamespace(GetModuleFileNameW=get_image), 'owned-job'
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert tree.command(['extractor.exe', 'arg']) == [image, '--runtime-child', 'windows-bootstrap', '--', 'owned-job', 'extractor.exe', 'arg']


def closure_module():
    path = Path(bundle.__file__).resolve().parents[1] / 'packaging/runtime-bundle/closure.py'
    spec = importlib.util.spec_from_file_location('runtime_closure_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnostic_recorder_module(monkeypatch):
    path = Path(bundle.__file__).resolve().parents[1] / 'packaging/runtime-bundle/record_diagnostic.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location('runtime_diagnostic_recorder_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wheel_identity_uses_own_metadata_while_retaining_vendored_metadata(tmp_path, monkeypatch):
    # Source import tests never inspect wheel archives. setuptools' vendored
    # dist-info must not turn its one actual wheel identity into an ambiguity.
    recorder = diagnostic_recorder_module(monkeypatch)
    wheel = tmp_path / 'owned-1.0-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as package:
        package.writestr('owned-1.0.dist-info/METADATA', 'Name: owned\nVersion: 1.0\n')
        package.writestr('owned/_vendor/other-9.0.dist-info/METADATA', 'Name: other\nVersion: 9.0\n')
    with zipfile.ZipFile(wheel) as package:
        metadata = recorder.wheel_metadata(package)
    assert (metadata['Name'], metadata['Version']) == ('owned', '1.0')


@pytest.mark.parametrize('case', ['nested-only', 'multiple-roots', 'duplicate-root'])
def test_wheel_identity_rejects_missing_or_duplicate_top_level_metadata(tmp_path, monkeypatch, case):
    from contextlib import nullcontext
    recorder = diagnostic_recorder_module(monkeypatch)
    wheel = tmp_path / 'ambiguous.whl'
    own = 'owned-1.0.dist-info/METADATA'
    entries = {
        'nested-only': ['owned/_vendor/other-9.0.dist-info/METADATA'],
        'multiple-roots': [own, 'other-9.0.dist-info/METADATA'],
        'duplicate-root': [own, own],
    }[case]
    warning = pytest.warns(UserWarning, match='Duplicate name') if case == 'duplicate-root' else nullcontext()
    with warning, zipfile.ZipFile(wheel, 'w') as package:
        for name in entries:
            package.writestr(name, 'Name: owned\nVersion: 1.0\n')
    with zipfile.ZipFile(wheel) as package, pytest.raises(recorder.ClosureError, match='top-level package identity'):
        recorder.wheel_metadata(package)


def test_input_gate_blocks_unpinned_and_unreviewed_runtime(tmp_path):
    closure = closure_module()
    value = {'schema': 'proxy-runtime-build-inputs-v1', 'profile': 'diagnostic',
        'source_commit': 'a' * 40, 'build_id': 'synthetic', 'components': []}
    with pytest.raises(closure.ClosureError, match='unpinned'):
        closure.validate_inputs(value, tmp_path, tmp_path, check_host=False)
    value['profile'] = 'runtime'
    value['components'] = [{'name': 'cpython', 'version': '3.12.10',
        'review_status': 'observed-diagnostic', 'native_closure': 'unverified'}]
    with pytest.raises(closure.ClosureError, match='review are required'):
        closure.validate_inputs(value, tmp_path, tmp_path, check_host=False)


@pytest.mark.parametrize('name', ['oneocr.dll', 'oneocr.onemodel', 'oo2core_7_win64.dll', 'data/history.db', 'persona5-charsets/P5R_CHS.tsv'])
def test_collected_file_gate_rejects_proprietary_and_private_artifacts(tmp_path, name):
    closure = closure_module()
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'synthetic forbidden bytes')
    with pytest.raises(closure.ClosureError, match='private|proprietary|Private'):
        closure.inventory_output(tmp_path)


def test_every_active_game_retains_toolchain_mapping():
    from backend.game_paths import GAMES
    from backend.game_assets import _ADAPTERS
    path = Path(bundle.__file__).resolve().parents[1] / 'packaging/runtime-bundle/toolchains.json'
    table = json.loads(path.read_text())
    assert set(table['games']) == set(GAMES) and len(GAMES) == 25
    assert all(row['adapter'] == _ADAPTERS[game][0] for game, row in table['games'].items())
    assert table['native_probe'] == 'unavailable' and table['r19_complete'] is False
    assert table['games']['halflife']['voiced_capture'] is False


def test_frozen_toolkit_update_never_downloads_or_writes_source_tree(tmp_path, monkeypatch):
    from backend import toolkit_update
    layout = frozen_layout(tmp_path)
    monkeypatch.setattr(toolkit_update, 'discover_layout', lambda: layout)
    monkeypatch.setattr(toolkit_update, 'request_json', lambda *_: pytest.fail('Frozen updater cannot contact source release flow'))
    updater = toolkit_update.ToolkitUpdater(layout.application_root)
    assert updater.status()['state'] == 'unavailable' and updater.request() is False
    with pytest.raises(bundle.RuntimeBundleError, match='supervis'):
        updater.configure(True)
    with pytest.raises(bundle.RuntimeBundleError, match='supervis'):
        toolkit_update.update_once(layout.application_root, layout.version)
    assert not (layout.application_root / 'data').exists()
