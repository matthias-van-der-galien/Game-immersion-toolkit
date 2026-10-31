"""One real frozen process owner, restricted to the existing private host probe.

The frontend is real. The API is the existing fixed API probe, with its external
account/game/OCR startup side effects mocked. This is not an installed launcher,
router, updater, migration coordinator or writer-stop/store-copy capability.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import ctypes
from ctypes import wintypes
from dataclasses import replace
import hashlib
import json
import ntpath
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .runtime_bundle import RuntimeBundleError
from .runtime_probe_common import developer_environment, synthetic_roots
from .windows_preparation_process import WindowsPreparationProcess, _kernel as preparation_kernel

SCHEMA = 'proxy-r19-owned-host-probe-v1'
KEEPER_SCHEMA = 'proxy-r19-frozen-keeper-probe-v1'
KEEPER_FAILURES = frozenset({
    'registered-host-unconfirmed', 'keeper-control-unavailable', 'keeper-control-invalid',
    'keeper-guardian-startup', 'keeper-guardian-identity', 'keeper-guardian-descendants',
    'keeper-fixture-unavailable', 'keeper-lease-release-unconfirmed', 'unexpected-keeper-failure',
    'guardian-census-unavailable', 'guardian-census-truncated', 'guardian-census-close-unconfirmed',
    'registered-member-ownership-unconfirmed', 'unknown-registered-member',
    'registered-cohort-incomplete', 'registered-member-observer-unavailable',
    'registered-cohort-aliased', 'registered-observer-close-unconfirmed',
    'registered-listener-unavailable', 'registered-listener-role-mismatch',
    'registered-listener-changed', 'registered-writer-not-live',
    'registered-writer-drain-unconfirmed', 'members-remain-after-registered-stop',
    'readiness-deadline', 'keeper-recovery-required'})
START_TIMEOUT = 60
STOP_TIMEOUT = 10
FRONTEND = 'http://127.0.0.1:3000/'
API = 'http://127.0.0.1:8766'


class HostProbeFailure(RuntimeBundleError):
    def __init__(self, code):
        self.code = code
        super().__init__('Owned frozen host probe failed: ' + code)


class _TcpRow(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in
        ('state', 'local_address', 'local_port', 'remote_address', 'remote_port', 'pid')]


def listener_processes(ports=(3000, 8766)):
    """Observe selected IPv4 listeners; never authorize termination by PID."""
    library = ctypes.WinDLL('iphlpapi', use_last_error=True)
    query = library.GetExtendedTcpTable
    query.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), wintypes.BOOL,
                      ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    query.restype = ctypes.c_uint32
    size = ctypes.c_uint32()
    result = query(None, ctypes.byref(size), False, 2, 3, 0)  # AF_INET, OWNER_PID_LISTENER
    loopback = int.from_bytes(socket.inet_aton('127.0.0.1'), 'little')
    for _ in range(4):
        if result not in (0, 122) or not 4 <= size.value <= 4*1024*1024:
            raise HostProbeFailure('listener-inventory-unavailable')
        buffer = ctypes.create_string_buffer(size.value)
        result = query(buffer, ctypes.byref(size), False, 2, 3, 0)
        if result == 122:
            continue
        if result:
            raise HostProbeFailure('listener-inventory-unavailable')
        count = ctypes.c_uint32.from_buffer(buffer).value
        if count > 65536 or 4 + count*ctypes.sizeof(_TcpRow) > len(buffer):
            raise HostProbeFailure('listener-inventory-unavailable')
        owners = {}
        for index in range(count):
            row = _TcpRow.from_buffer_copy(buffer, 4 + index*ctypes.sizeof(_TcpRow))
            port = socket.ntohs(row.local_port & 0xffff)
            if row.state == 2 and row.local_address in (0, loopback) and port in ports:
                owners.setdefault(port, set()).add(row.pid)
        return owners
    raise HostProbeFailure('listener-inventory-unavailable')


def same_process_object(first, second):
    library = ctypes.WinDLL('kernelbase', use_last_error=True)
    compare = library.CompareObjectHandles
    compare.argtypes, compare.restype = [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL
    return bool(compare(first, second))


class _ProcessEntry(ctypes.Structure):
    _fields_ = [('size', ctypes.c_uint32), ('usage', ctypes.c_uint32), ('pid', ctypes.c_uint32),
        ('heap', ctypes.c_size_t), ('module', ctypes.c_uint32), ('threads', ctypes.c_uint32),
        ('parent', ctypes.c_uint32), ('priority', ctypes.c_int32), ('flags', ctypes.c_uint32),
        ('image', ctypes.c_wchar * 260)]


def guardian_children(pid):
    """A bounded current census, never complete lifetime/admission evidence.

    Only parent/child identifiers are considered privately; no process name,
    system inventory or PID is published or adopted as termination authority.
    """
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes, kernel.CreateToolhelp32Snapshot.restype = [ctypes.c_uint32, ctypes.c_uint32], wintypes.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        function = getattr(kernel, name)
        function.argtypes, function.restype = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)], wintypes.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS only.
    if snapshot in (None, ctypes.c_void_p(-1).value):
        raise HostProbeFailure('guardian-census-unavailable')
    try:
        entry = _ProcessEntry(); entry.size = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise HostProbeFailure('guardian-census-unavailable')
        parents = {}
        for _ in range(65536):
            parents[entry.pid] = entry.parent
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise HostProbeFailure('guardian-census-unavailable')
                break
        else:
            raise HostProbeFailure('guardian-census-truncated')
        pending, descendants = {pid}, set()
        while pending:
            children = {child for child, parent in parents.items() if parent in pending} - descendants - {pid}
            descendants.update(children); pending = children
        return descendants
    finally:
        if not kernel.CloseHandle(snapshot):
            raise HostProbeFailure('guardian-census-close-unconfirmed')


def _empty_guardian_observation():
    return {'schema': 'proxy-r19-guardian-census-observation-v1', 'state': 'not-observed',
        'reason': 'none', 'candidate_count': 0, 'inspected_count': 0, 'truncated': False,
        'lineage': 'census-not-authority', 'records': []}


def _guardian_observer_kernel():
    kernel = preparation_kernel()  # Reuse existing observer/wait/close bindings.
    fields = ctypes.POINTER(wintypes.FILETIME)
    for name, args, result in (
        ('GetProcessTimes', [wintypes.HANDLE, fields, fields, fields, fields], wintypes.BOOL),
        ('QueryFullProcessImageNameW', [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        ('GetSystemDirectoryW', [wintypes.LPWSTR, wintypes.UINT], wintypes.UINT),
        ('GetProcessId', [wintypes.HANDLE], wintypes.DWORD)):
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


def _guardian_image_role(actual, runtime, system_directory, retained_creation):
    # Same exact-path principle as C1; a matching basename/prefix grants nothing.
    if actual.startswith(('\\\\?\\', '\\\\.\\')):
        return 'unknown'
    key = lambda value: ntpath.normcase(ntpath.normpath(str(value)))
    if key(actual) == key(runtime):
        return 'retained-runtime-creation' if retained_creation else 'runtime-image-only'
    if key(actual) == key(ntpath.join(system_directory, 'conhost.exe')):
        return 'windows-console-host'
    return 'unknown'


def observe_guardian_candidates(guardian, runtime, candidates, retained, known_creations=()):
    """Failure-only read-only observation, never lineage/admission authority.

    Keep genuine observation objects during each query. A stale parent PID or
    creation ordering cannot promote a census candidate into an owned child.
    Unknown native outcomes retain the private handles without reuse or retry.
    """
    report = _empty_guardian_observation()
    report.update(state='observed', candidate_count=min(len(candidates), 65536))
    if retained:
        report.update(state='unavailable', reason='prior-observation-unconfirmed', truncated=bool(candidates))
        return report
    deadline = time.monotonic()+3

    def fail(reason):
        report.update(state='unavailable', reason=reason)
        # Any already-created observation handles remain private/inaccessible
        # after an unconfirmed native call; the surrounding keeper holds alive.
        for record in retained:
            record['poisoned'] = True

    def stamp(handle):
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise OSError('query-unavailable')
        return values[0].dwHighDateTime << 32 | values[0].dwLowDateTime

    def image(handle):
        buffer, count = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(count)) or not 0 < count.value < len(buffer):
            raise OSError('query-unavailable')
        return buffer.value

    def open_observer(pid):
        handle = kernel.OpenProcess(0x101000, False, pid)
        if handle:
            record = {'handle': handle, 'poisoned': False}
            retained.append(record)
            return record

    try:
        kernel = _guardian_observer_kernel()
        root = guardian._handle  # Retained genuine Popen creation handle.
        if (kernel.GetProcessId(root) != guardian.pid or kernel.WaitForSingleObject(root, 0) != 258):
            fail('root-unavailable')
            return report
        root_stamp = stamp(root)
        system = ctypes.create_unicode_buffer(32768)
        length = kernel.GetSystemDirectoryW(system, len(system))
        if not 0 < length < len(system):
            fail('query-unavailable')
            return report
        for pid in sorted(candidates)[:16]:
            if time.monotonic() >= deadline:
                fail('query-budget-exhausted'); break
            item = {'role': 'unknown', 'state': 'observed', 'creation_order': 'unavailable'}
            report['records'].append(item)
            first = open_observer(pid)
            if first is None:
                item['state'] = 'open-unavailable'
                report.update(state='unavailable', reason='query-unavailable')
                continue
            held = [first]
            try:
                result = kernel.WaitForSingleObject(first['handle'], 0)
                if result == 0:
                    item['state'] = 'exit-observed'
                    report.update(state='unavailable', reason='query-unavailable')
                elif result != 258 or kernel.GetProcessId(first['handle']) != pid:
                    item['state'] = 'identity-unavailable'; fail('identity-unavailable'); break
                else:
                    started = stamp(first['handle'])
                    item['creation_order'] = 'before-guardian' if started < root_stamp else 'at-or-after-guardian'
                    actual = image(first['handle'])
                    second = open_observer(pid)
                    if second is None:
                        item['state'] = 'identity-unavailable'; fail('identity-unavailable'); break
                    held.append(second)
                    if not same_process_object(first['handle'], second['handle']):
                        item['state'] = 'identity-changed'; fail('identity-changed'); break
                    live = kernel.WaitForSingleObject(first['handle'], 0)
                    if live not in (0, 258):
                        item['state'] = 'identity-unavailable'; fail('identity-unavailable'); break
                    root_live = kernel.WaitForSingleObject(root, 0)
                    if root_live not in (0, 258):
                        item['state'] = 'identity-unavailable'; fail('root-unavailable'); break
                    if live == 0 or root_live == 0:
                        item['state'] = 'exit-observed'
                        report.update(state='unavailable', reason='query-unavailable')
                    else:
                        created = any(same_process_object(first['handle'], handle) for handle in (root, *known_creations))
                        item['role'] = _guardian_image_role(actual, runtime, system.value, created)
                for record in reversed(held):
                    try:
                        closed = kernel.CloseHandle(record['handle'])
                    except BaseException:
                        closed = False
                    if not closed:
                        item.update(role='unknown', state='observer-close-unconfirmed'); fail('observer-close-unconfirmed'); break
                    retained.remove(record)
                if report['reason'] == 'observer-close-unconfirmed':
                    break
            except BaseException:
                item['state'] = 'query-unavailable'; fail('query-unavailable'); break
    except BaseException:
        fail('query-unavailable')
    finally:
        report['inspected_count'] = len(report['records'])
        report['truncated'] = report['candidate_count'] > report['inspected_count']
    return report


class FrozenProbeHost:
    """Own precisely two existing frozen entrypoints and their real Windows job."""
    def __init__(self, layout):
        if (sys.platform != 'win32' or layout.mode != 'bundle' or layout.profile != 'runtime-experiment'
                or layout.executable.name.casefold() != 'proxytranscriptruntime.exe'):
            raise HostProbeFailure('experimental-windows-image-required')
        synthetic_roots(layout)
        developer_environment()
        self.layout = layout
        self.tree = None
        self.processes = {}
        self.logs = []
        self.scratch = None
        self.closed = False
        self.registered_mode = False
        self.registered = {}
        self.recovery_required = False

    def start(self):
        if self.tree is not None or self.closed:
            raise HostProbeFailure('host-already-started-or-closed')
        self.layout.work_root.mkdir(parents=True, exist_ok=True)
        self.scratch = Path(tempfile.mkdtemp(prefix='owned-host-', dir=self.layout.work_root))
        self.tree = WindowsPreparationProcess()
        # No arbitrary child, executable, command text, port or live root input.
        commands = [('frontend', self.layout.child_command('frontend', ['--port', '3000'])),
                    ('api', [str(self.layout.executable), '--runtime-probe', 'api'])]
        for role, command in commands:
            output = (self.scratch / (role + '.log')).open('wb')
            self.logs.append(output)
            environment = self.layout.child_environment(role)
            environment['PROXY_TRANSCRIPT_STANDBY'] = '1'
            self.processes[role] = subprocess.Popen(self.tree.command(command), cwd=self.scratch,
                env=environment, stdin=subprocess.DEVNULL,
                stdout=output, stderr=output, creationflags=subprocess.CREATE_NO_WINDOW)

    def _recovery(self, code):
        self.recovery_required = True
        raise HostProbeFailure(code)

    def start_registered(self, *, detached_console=False, wal_probe=False, grammar_probe=False):
        """Create the two fixed actual writers before resuming either of them."""
        if type(wal_probe) is not bool or type(grammar_probe) is not bool or wal_probe and grammar_probe:
            raise HostProbeFailure('invalid-private-probe-case')
        if self.tree is not None or self.closed:
            raise HostProbeFailure('host-already-started-or-closed')
        self.registered_mode = True
        self.layout.work_root.mkdir(parents=True, exist_ok=True)
        self.scratch = Path(tempfile.mkdtemp(prefix='registered-host-', dir=self.layout.work_root))
        self.tree = WindowsPreparationProcess()
        commands = [('frontend', self.layout.child_command('frontend', ['--port', '3000'])),
                    ('api', [str(self.layout.executable), '--runtime-probe',
                             'api-grammar' if grammar_probe else 'api-wal' if wal_probe else 'api'])]
        try:
            for role, command in commands:
                environment = self.layout.child_environment(role)
                environment['PROXY_TRANSCRIPT_STANDBY'] = '1'
                self.registered[role] = self.tree.create_suspended(command, cwd=self.scratch, env=environment,
                    detached_console=detached_console)
            self.check_registered_members()
        except BaseException:
            self.recovery_required = True
            raise

    def _registered_role(self, observer):
        kernel = self.tree.kernel
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(observer, self.tree.handle, ctypes.byref(member)) or not member.value:
            self._recovery('registered-member-ownership-unconfirmed')
        matches = [role for role, child in self.registered.items()
                   if same_process_object(observer, child.process_handle)]
        if len(matches) != 1:
            self._recovery('unknown-registered-member')
        return matches[0]

    def check_registered_members(self, require_all=True):
        if self.recovery_required:
            raise HostProbeFailure('keeper-recovery-required')
        if self.tree is None or set(self.registered) != {'frontend', 'api'}:
            self._recovery('registered-cohort-incomplete')
        kernel = self.tree.kernel
        with self.tree._lifecycle:
            seen = set()
            for pid in self.tree._process_ids(time.monotonic()+3):
                observer = kernel.OpenProcess(0x101000, False, pid)
                if not observer:
                    self._recovery('registered-member-observer-unavailable')
                try:
                    role = self._registered_role(observer)
                    if role in seen:
                        self._recovery('registered-cohort-aliased')
                    seen.add(role)
                finally:
                    if not kernel.CloseHandle(observer):
                        self._recovery('registered-observer-close-unconfirmed')
            if require_all and seen != {'frontend', 'api'}:
                self._recovery('registered-cohort-incomplete')

    def resume_registered(self):
        try:
            self.check_registered_members()
            for child in self.registered.values():
                child.resume_once()
        except BaseException:
            self.recovery_required = True
            raise

    def quiesce_registered(self):
        """Existing opt-in C2 barrier, only for the paused authored API probe."""
        if not self.registered_mode:
            raise HostProbeFailure('registered-cohort-required')
        with self._registered_listener_scope() as owned:
            if not owned:
                self._recovery('registered-listener-unavailable')
            request = Request(API+'/api/runtime/quiesce?writers=true', data=b'', method='POST',
                              headers={'X-Proxy-Transcript': 'update'})
            # The API owns its existing total 30-second deadline; 35 is only
            # the transport budget. A failure leaves the keeper holding leases.
            with urlopen(request, timeout=35) as response:
                handoff = json.loads(response.read(65537))
                if response.status != 200 or handoff.get('running') is not False:
                    self._recovery('registered-writer-drain-unconfirmed')
            try:
                with urlopen(API+'/api/status', timeout=3) as response:
                    status = response.status
                    response.read(1)
            except HTTPError as response:
                with response:
                    status = response.code
                    response.read(1)
            if status != 503 or self._json('/api/health', 3).get('status') != 'ok':
                self._recovery('registered-writer-drain-unconfirmed')

    @contextmanager
    def _registered_listener_scope(self):
        self.check_registered_members()
        owners, kernel = listener_processes(), self.tree.kernel
        with self.tree._lifecycle:
            for port, members in owners.items():
                for pid in members:
                    observer = kernel.OpenProcess(0x101000, False, pid)
                    if not observer:
                        self._recovery('registered-listener-unavailable')
                    try:
                        role = self._registered_role(observer)
                        if role != ('frontend' if port == 3000 else 'api'):
                            self._recovery('registered-listener-role-mismatch')
                    finally:
                        if not kernel.CloseHandle(observer):
                            self._recovery('registered-observer-close-unconfirmed')
            ready = set(owners) == {3000, 8766} and all(len(ids) == 1 for ids in owners.values())
            yield ready
            if listener_processes() != owners:
                self._recovery('registered-listener-changed')
            self._alive()
            self.check_registered_members()

    def _alive(self):
        if self.registered_mode:
            for child in self.registered.values():
                if self.tree.kernel.WaitForSingleObject(child.process_handle, 0) != 258:
                    self._recovery('registered-writer-not-live')
        if any(process.poll() is not None for process in self.processes.values()):
            raise HostProbeFailure('child-exited')

    @contextmanager
    def _listener_scope(self):
        if self.registered_mode:
            with self._registered_listener_scope() as ready:
                yield ready
            return
        owners = listener_processes()
        kernel = self.tree.kernel
        with ExitStack() as handles:
            def close_observer(handle):
                if not kernel.CloseHandle(handle):
                    raise HostProbeFailure('listener-observer-close-unconfirmed')
            retained = []
            for members in owners.values():
                for pid in members:
                    handle = kernel.OpenProcess(0x101000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED
                    if not handle:
                        raise HostProbeFailure('listener-ownership-unconfirmed')
                    handles.callback(close_observer, handle)
                    member = wintypes.BOOL()
                    if not kernel.IsProcessInJob(handle, self.tree.handle, ctypes.byref(member)):
                        raise HostProbeFailure('listener-ownership-unconfirmed')
                    if not member.value:
                        raise HostProbeFailure('foreign-canonical-listener')
                    if kernel.WaitForSingleObject(handle, 0) != 258:
                        raise HostProbeFailure('listener-exited')
                    retained.append(handle)
            if set(owners) != {3000, 8766} or any(len(members) != 1 for members in owners.values()):
                yield False
                return
            yield True
            # The HTTP result is accepted only while the same real owned
            # listeners and retained process objects are still live.
            if listener_processes() != owners or any(kernel.WaitForSingleObject(handle, 0) != 258 for handle in retained):
                raise HostProbeFailure('listener-ownership-changed')

    @staticmethod
    def _json(path, timeout):
        with urlopen(API + path, timeout=timeout) as response:
            return json.loads(response.read(65537))

    def wait_services(self, timeout=START_TIMEOUT):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._alive()
            remaining = min(.5, max(.001, deadline-time.monotonic()))
            try:
                with self._listener_scope() as owned:
                    if owned:
                        ready = self._json('/api/runtime/ready', remaining)
                        with urlopen(FRONTEND, timeout=remaining) as response:
                            frontend_ready = response.status == 200
                            response.read(1)
                        if ready.get('ready') is True and frontend_ready:
                            self._alive()
                            return
            except (OSError, ValueError):
                pass
            time.sleep(min(.05, max(0, deadline-time.monotonic())))
        raise HostProbeFailure('readiness-deadline')

    def wait_unprepared_index(self, timeout=3):
        """A fixed negative fixture: live HTTP/OCR-probe, absent ZZZ index."""
        deadline, observed = time.monotonic() + timeout, False
        while time.monotonic() < deadline:
            self._alive()
            try:
                with self._listener_scope() as owned:
                    if owned:
                        state = self._json('/api/runtime/ready?game=zzz', min(.5, max(.001, deadline-time.monotonic())))
                        if state.get('ready') is True:
                            raise HostProbeFailure('negative-index-fixture-was-ready')
                        observed = state.get('ready') is False
            except (OSError, ValueError):
                pass
            time.sleep(min(.05, max(0, deadline-time.monotonic())))
        raise HostProbeFailure('unprepared-index-deadline' if observed else 'negative-index-http-unavailable')

    def members(self):
        self._alive()
        # Private control output only. IDs come from the live owned Job Object;
        # the caller retains observation handles, never uses this JSON to kill.
        return self.tree._process_ids(time.monotonic()+3)

    def exit_frontend(self):
        process = self.processes['frontend']
        if process.poll() is None:
            process.kill()  # The retained Popen handle, not a reopened PID.
        process.wait(timeout=3)

    def monitor(self, stream):
        commands = queue.Queue()
        def read():
            for line in stream:
                commands.put(line.strip())
            commands.put('stop')
        threading.Thread(target=read, daemon=True, name='owned-host-probe-control').start()
        while True:
            self._alive()
            try:
                command = commands.get(timeout=.05)
            except queue.Empty:
                continue
            if command == 'stop':
                return
            if command == 'exit-frontend':
                self.exit_frontend()
            else:
                raise HostProbeFailure('invalid-private-probe-command')

    def close(self, timeout=STOP_TIMEOUT):
        if self.closed:
            return
        if self.registered_mode:
            return self._close_registered(timeout)
        deadline = time.monotonic()+timeout
        try:
            # Reap every bootstrap before an empty-job observation. A delayed
            # bootstrap must not join and spawn after cleanup was confirmed.
            for process in self.processes.values():
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=max(.001, deadline-time.monotonic()))
            if self.tree is not None:
                self.tree.terminate(timeout=max(.001, deadline-time.monotonic()))
                self.tree.close()
                self.tree = None
        except (OSError, TimeoutError, subprocess.TimeoutExpired) as error:
            # Retain ownership and private evidence. OS job-handle cleanup on
            # host exit is not reported as confirmed child-process exit.
            raise HostProbeFailure('owned-cleanup-unconfirmed') from error
        finally:
            for output in self.logs:
                output.close()
        if self.scratch is not None:
            shutil.rmtree(self.scratch)
        self.closed = True

    def _close_registered(self, timeout):
        if self.recovery_required:
            raise HostProbeFailure('keeper-recovery-required')
        deadline = time.monotonic()+timeout
        try:
            with self.tree._lifecycle:
                self.tree._admission_closed = True
                self.check_registered_members(require_all=False)
                for child in self.registered.values():
                    child.stop_and_wait(deadline)
                # Unknown descendants must never disappear through the legacy
                # generic drain and become a passing fixed-cohort result.
                if self.tree._process_ids(deadline):
                    self._recovery('members-remain-after-registered-stop')
                self.tree.close()
                self.tree = None
            shutil.rmtree(self.scratch)
            self.closed = True
        except BaseException:
            self.recovery_required = True
            raise


def hold_keeper_recovery():
    # Exiting would close leases before unknown writers were confirmed stopped.
    # The build-host harness may terminate us only as an unverified failure.
    while True:
        time.sleep(5)


class _FrozenKeeperProbe:
    """Fixed probe orchestration around FrozenProbeHost, not a second host."""
    def __init__(self, layout, case, stream):
        FrozenProbeHost(layout)  # Same profile/image/synthetic/dev-tool guards.
        self.layout, self.case = layout, case
        self.host = self.guardian = None
        self.leases = []
        self.fixture = layout.work_root / 'keeper-fixture'
        self.commands = queue.Queue(maxsize=4)
        self.guardian_port = None
        self.guardian_signaled = False
        self.released = False
        self.descendant_observation = _empty_guardian_observation()
        self._guardian_observer_holds = []
        def read():
            try:
                while True:
                    line = stream.readline(65)
                    if not line:
                        self.commands.put(None); return
                    if len(line) > 64 or not line.endswith('\n'):
                        self.commands.put('invalid'); return
                    self.commands.put(line.strip())
            except BaseException:
                self.commands.put(None)
        threading.Thread(target=read, daemon=True, name='fixed-keeper-probe-input').start()

    def emit(self, phase, *, status='observing', failure=None):
        records = self.host.registered.values() if self.host is not None else ()
        value = {'schema': KEEPER_SCHEMA, 'kind': 'keeper', 'phase': phase,
            'case': self.case, 'status': status, 'build_id': self.layout.build_id,
            'source_commit': self.layout.source_commit, 'writers_created': len(self.host.registered) if self.host else 0,
            'writers_resumed': sum(child.resumed for child in records),
            'guardian': 'readonly-frozen-frontend-port-zero', 'guardian_exit': 'signaled' if self.guardian_signaled else 'not-confirmed',
            'guardian_console_mode': 'detached-process', 'writer_console_mode': 'detached-process',
            'api_external_side_effects': 'mocked', 'native_owned_process_tree': 'real',
            'census': 'observations-only-not-lifetime-proof', 'keeper_loss': 'unavailable',
            'dynamic_writer_admission': 'unavailable', 'production_activation': False,
            'store_copy': False, 'installer': 'not-built', 'r19_complete': False}
        if failure is not None:
            # Only fixed code categories, never exception/model/log/path text.
            value['failure'] = failure if failure in KEEPER_FAILURES else 'unexpected-keeper-failure'
            value['guardian_descendants'] = self.descendant_observation
        print(json.dumps(value), flush=True)

    def command(self, expected, timeout=60):
        try:
            value = self.commands.get(timeout=timeout)
        except queue.Empty as error:
            raise HostProbeFailure('keeper-control-unavailable') from error
        if value != expected:
            raise HostProbeFailure('keeper-control-invalid')

    def prepare(self):
        from .bundle_host import ExclusiveFileLease, _reject_links
        temporary = Path(tempfile.gettempdir()).resolve()
        _reject_links(self.layout.work_root)
        if not self.layout.work_root.resolve().is_relative_to(temporary):
            raise HostProbeFailure('keeper-fixture-unavailable')
        self.fixture.mkdir(parents=True, exist_ok=False)
        private = self.fixture / 'authored-state'
        roots = dict(settings_root=private, data_root=private/'data-v1', cache_root=private/'cache-v1',
            work_root=private/'cache-v1/work', tool_root=private/'tools-v1', state_root=private/'host-v1',
            default_export_root=private/'exports')
        roots['state_root'].mkdir(parents=True)
        (roots['state_root']/'synthetic-probe.json').write_text(json.dumps({'build_id': self.layout.build_id, 'synthetic': True}))
        self.writer_layout = replace(self.layout, **roots)
        self.host = FrozenProbeHost(self.writer_layout)
        paths = (self.fixture/'legacy/data/companion-operation.lock',
                 self.fixture/'private-target/host-v1/migration-runtime.lock')
        for path in paths:
            path.parent.mkdir(parents=True)
            self.leases.append(ExclusiveFileLease(path))
        self.emit('roots-ready')

    def start_guardian(self):
        environment = self.writer_layout.child_environment('frontend')
        self.guardian = subprocess.Popen(self.writer_layout.child_command('frontend', ['--port', '0']),
            cwd=self.fixture, env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS)
        line = queue.Queue(maxsize=1)
        def read():
            try: line.put(self.guardian.stdout.readline(65537))
            except BaseException: line.put(None)
        threading.Thread(target=read, daemon=True, name='readonly-guardian-startup').start()
        try:
            ready = json.loads(line.get(timeout=20))
            manifest = json.loads(self.layout.resource('desktop/desktop-manifest.json').read_bytes())
            port = ready.get('port')
            if (ready.get('ready') is not True or type(port) is not int or not 1024 < port < 65536
                    or port in (3000, 8766) or ready.get('build_id') != manifest['build_id']):
                raise ValueError('invalid fixed guardian metadata')
            self.guardian_port, self.guardian_index = port, manifest['files']['index.html']
        except (ValueError, TypeError, KeyError, queue.Empty) as error:
            raise HostProbeFailure('keeper-guardian-startup') from error
        self.check_guardian()

    def check_guardian(self):
        guardian, port = self.guardian, self.guardian_port
        if guardian.poll() is not None or listener_processes((port,)) != {port: {guardian.pid}}:
            raise HostProbeFailure('keeper-guardian-identity')
        candidates = guardian_children(guardian.pid)
        if candidates:
            self.observe_descendants(candidates)
            raise HostProbeFailure('keeper-guardian-descendants')
        with urlopen('http://127.0.0.1:'+str(port)+'/', timeout=1) as response:
            body = response.read(self.guardian_index['bytes']+1)
            if (response.status != 200 or len(body) != self.guardian_index['bytes']
                    or hashlib.sha256(body).hexdigest() != self.guardian_index['sha256']):
                raise HostProbeFailure('keeper-guardian-identity')
        if guardian.poll() is not None or listener_processes((port,)) != {port: {guardian.pid}}:
            raise HostProbeFailure('keeper-guardian-identity')
        candidates = guardian_children(guardian.pid)
        if candidates:
            self.observe_descendants(candidates)
            raise HostProbeFailure('keeper-guardian-identity')

    def observe_descendants(self, candidates):
        if self.descendant_observation['state'] != 'not-observed':
            return  # Failure-only one-shot; never retry unconfirmed root/query handles.
        try:
            known = tuple(child.process_handle for child in self.host.registered.values())
            self.descendant_observation = observe_guardian_candidates(self.guardian, self.layout.executable,
                candidates, self._guardian_observer_holds, known)
        except BaseException:
            self.descendant_observation = _empty_guardian_observation()
            self.descendant_observation.update(state='unavailable', reason='query-unavailable',
                candidate_count=min(len(candidates), 65536), truncated=bool(candidates))

    def wait_guardian_loss(self):
        deadline, next_census = time.monotonic()+60, 0
        while self.guardian.poll() is None:
            if time.monotonic() >= deadline:
                raise HostProbeFailure('keeper-control-unavailable')
            self.host._alive()
            if time.monotonic() >= next_census:
                self.host.check_registered_members()
                self.check_guardian()
                next_census = time.monotonic()+.25
            try:
                command = self.commands.get(timeout=.05)
            except queue.Empty:
                continue
            if command != 'lose-guardian':
                raise HostProbeFailure('keeper-control-invalid')
            self.guardian.kill()  # Only our retained Popen creation object.
        self.guardian.wait(timeout=3)
        self.guardian_signaled = True
        candidates = guardian_children(self.guardian.pid)
        if candidates:
            self.observe_descendants(candidates)
            raise HostProbeFailure('keeper-guardian-descendants')

    def run(self):
        try:
            self.prepare()
            self.command('start')
            for lease in self.leases:
                lease.acquire()
            self.start_guardian()
            self.host.start_registered(detached_console=True)
            if self.case == 'keeper-after-ready':
                self.host.resume_registered()
                self.host.wait_services()
                self.check_guardian()
                self.emit('services-ready')
            else:
                self.emit('writers-suspended')
            self.wait_guardian_loss()
            # Loss itself drives drainage; there is no separate drain command.
            if self.case == 'keeper-after-ready':
                self.host.quiesce_registered()
            self.host.close()
            self.guardian.stdout.close()
            self.emit('writers-signaled-leases-held')
            self.command('release')  # Probe observation latch, not writer authority.
            for lease in reversed(self.leases):
                try: lease.close()
                except BaseException as error:
                    raise HostProbeFailure('keeper-lease-release-unconfirmed') from error
            self.released = True
            self.emit('released', status='passed')
            return 0
        except BaseException as error:
            category = error.code if isinstance(error, HostProbeFailure) else 'unexpected-keeper-failure'
            if not isinstance(error, HostProbeFailure) and self.host is not None and self.host.recovery_required:
                category = 'registered-host-unconfirmed'
            # No finally/context manager releases leases or exits with live or
            # unknown writer objects. Even a broken event pipe cannot bypass
            # the live owner/Job/creation-handle recovery hold.
            try:
                self.emit('recovery-required', status='failed', failure=category)
            except BaseException:
                pass
            hold_keeper_recovery()
            raise AssertionError('Recovery holder must not return.')


def main(kind, layout):
    if kind != 'host':
        raise HostProbeFailure('unknown-host-probe')
    # Fixed authored test controls only. Nothing is accepted by a production
    # child or API; the full runtime profile and source launcher stay unchanged.
    case = sys.stdin.readline().strip()
    if case in {'authored-data-copy', 'authored-data-copy-resume', 'authored-data-copy-wal', 'authored-data-copy-grammar'}:
        from .runtime_data_copy_probe import run as data_copy_probe
        return data_copy_probe(layout, sys.stdin, case=case)
    if case in {'keeper-before-resume', 'keeper-after-ready'}:
        return _FrozenKeeperProbe(layout, case, sys.stdin).run()
    if case not in {'normal', 'unprepared-index'}:
        raise HostProbeFailure('invalid-private-probe-case')
    host = FrozenProbeHost(layout)
    failure = None
    try:
        host.start()
        host.wait_services()
        print(json.dumps({'schema': SCHEMA, 'status': 'services-ready', 'kind': 'host',
            'build_id': layout.build_id, 'source_commit': layout.source_commit,
            'job_members': host.members(), 'api_external_side_effects': 'mocked',
            'native_owned_process_tree': 'real', 'r19_complete': False}), flush=True)
        if case == 'unprepared-index':
            host.wait_unprepared_index()
        host.monitor(sys.stdin)
    except BaseException as error:
        failure = error
    try:
        host.close()
    except BaseException as error:
        failure = error
    result = {'schema': SCHEMA, 'status': 'failed' if failure else 'passed', 'kind': 'host',
        'build_id': layout.build_id, 'source_commit': layout.source_commit,
        'api_external_side_effects': 'mocked', 'native_owned_process_tree': 'real',
        'owned_cleanup': 'confirmed' if host.closed else 'unconfirmed', 'r19_complete': False}
    if failure:
        result['failure'] = failure.code if isinstance(failure, HostProbeFailure) else 'unexpected-host-failure'
    print(json.dumps(result), flush=True)
    return 2 if failure else 0
