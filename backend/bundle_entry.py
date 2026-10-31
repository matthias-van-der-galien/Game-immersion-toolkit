"""Fixed frozen entrypoints. Keep bootstrap dispatch free of application imports."""
from __future__ import annotations

import json
from importlib import import_module
import os
import runpy
import sys

from backend.runtime_bundle import CHILD_TARGETS, RuntimeBundleError, discover_layout


def _prepare_frozen_standard_streams():
    """A no-console child owns its NUL streams; no parent handle is inherited."""
    created = []
    if getattr(sys, 'frozen', False):
        for name, mode in (('stdin', 'r'), ('stdout', 'w'), ('stderr', 'w')):
            if getattr(sys, name) is None:
                stream = open(os.devnull, mode, encoding='utf-8')
                setattr(sys, name, stream)
                created.append(stream)
    return tuple(created)


def main(arguments=None):
    _prepare_frozen_standard_streams()
    args = list(sys.argv[1:] if arguments is None else arguments)
    if len(args) == 2 and args[0] == '--runtime-probe' and args[1] in {'native', 'asr', 'api', 'api-wal', 'api-grammar', 'host'}:
        layout = discover_layout()
        if layout.mode != 'bundle' or layout.profile != 'runtime-experiment':
            raise RuntimeBundleError('Runtime probes require the quarantined runtime-experiment profile.')
        asr_image = layout.executable.name.casefold() == 'proxytranscriptasr.exe'
        if asr_image != (args[1] == 'asr'):
            raise RuntimeBundleError('Probe must use its isolated runtime image.')
        # Keep the stdlib diagnostic/frontend and ASR analyses independent of
        # the main probe's native imports; experimental specs collect these
        # fixed modules explicitly.
        probe = import_module('backend.asr_probe' if asr_image else
            'backend.runtime_host' if args[1] == 'host' else 'backend.runtime_probe')
        return probe.main(args[1], layout)
    if args == ['--runtime-diagnose']:
        layout = discover_layout()
        # Public diagnostics contain logical state, never private root paths.
        print(json.dumps({'schema': layout.schema, 'mode': layout.mode, 'version': layout.version,
            'build_id': layout.build_id, 'profile': layout.profile, 'children': layout.children,
            'r19_complete': False, 'native_acceptance': 'unavailable'}))
        return 0
    if len(args) < 3 or args[0] != '--runtime-child' or args[2] != '--' or args[1] not in CHILD_TARGETS:
        raise RuntimeBundleError('Use a fixed --runtime-child KIND -- entrypoint or --runtime-diagnose.')
    kind, child_args = args[1], args[3:]
    layout = discover_layout()
    if layout.mode == 'bundle' and kind not in layout.children:
        raise RuntimeBundleError('This diagnostic bundle does not include child: ' + kind)
    # Joining the parent-owned job is the first operation that can spawn a
    # worker. It needs no mutable roots, API imports, or model initialization.
    if kind == 'windows-bootstrap':
        if len(child_args) < 2:
            raise RuntimeBundleError('Windows bootstrap requires a job name and child command.')
        from backend.windows_preparation_process import _bootstrap
        return _bootstrap(child_args[0], child_args[1:])
    if layout.mode == 'bundle' and kind == 'asr' and layout.executable.name.casefold() != 'proxytranscriptasr.exe':
        raise RuntimeBundleError('ASR requires its separate frozen executable and native library tree.')
    target_type, target = CHILD_TARGETS[kind]
    sys.argv = [target, *child_args]
    if target_type == 'script':
        runpy.run_path(str(layout.resource(target)), run_name='__main__')
    else:
        runpy.run_module(target, run_name='__main__', alter_sys=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RuntimeBundleError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
