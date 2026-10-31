"""Separate build-host mechanism experiment; never a runtime or recovery entry.

Only a freshly marked local NTFS fixture is admitted. No candidate/data writer
is created. File identities, paths, times and native failures remain private.
"""
from __future__ import annotations

import base64
import ctypes as c
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'proxy-r19-legacy-lock-attribute-mechanism-v1'
CONTENT = b'owned R19 legacy lock attribute fixture\n'
MARKER = '.r19-lock-attribute-fixture.json'
SOURCE = ROOT / 'scripts/companion-runtime.ps1'
SOURCE_HASHES = frozenset({'c0cb1b456c029e8cb843501ffaf17cf2b054bdfecad8e788dd35d9a85ae2d3ef',
    'f9469ccb51c99b814a615e66eb9b337e8b1ba8598a0fd794dbe420c8be4c8e9e'})
HELPER_HASHES = frozenset({'24a6995cc1d4d9260a9afe3049fbdf5d927cfddcfd405095ebcd49674e7234d0',
    '841c9bc072434c931a081cd1b69019d3c65e1cd04a3bdc49d836fcb7b5be5d9e'})
LIMIT = 4096
PHASES = ('fixture', 'legacy-baseline', 'lease-start', 'arm', 'live-clear', 'rearm',
    'owner-loss', 'post-loss', 'test-restore', 'restored', 'cleanup', 'complete')
FAILURES = frozenset({'none', 'unsupported-host', 'fixture-refused', 'native-call-failed',
    'protocol-refused', 'source-changed', 'preservation-refused', 'legacy-outcome-differed',
    'owned-cleanup-unconfirmed', 'unexpected-failure'})
INVALID = c.c_void_p(-1).value
READONLY, NORMAL = 1, 128
RW, RESTORE = 0xc0000000, 0x80000100  # GENERIC_READ|WRITE; GENERIC_READ|WRITE_ATTRIBUTES.
OBSERVATIONS = ('writable-open', 'exclusive-held', 'arm', 'live-clear', 'rearm',
    'genuine-owner-signaled-and-closed', 'post-loss-readonly-refused', 'restored-open')
TIME_STATES = ('arm', 'live-clear', 'rearm', 'post-loss', 'test-restore', 'restored')
_UNCONFIRMED = []  # Private ownership records only; never an adoption/retry list.


class Refused(Exception):
    def __init__(self, code):
        self.code = code if code in FAILURES else 'unexpected-failure'
        super().__init__(self.code)


class Basic(c.Structure):
    _fields_ = [('creation', c.c_int64), ('access', c.c_int64), ('write', c.c_int64),
        ('change', c.c_int64), ('attributes', c.c_uint32)]


class Identity(c.Structure):
    _fields_ = [('volume', c.c_uint64), ('file', c.c_ubyte * 16)]


class Standard(c.Structure):
    _fields_ = [('allocation', c.c_int64), ('size', c.c_int64), ('links', c.c_uint32),
        ('deleting', c.c_ubyte), ('directory', c.c_ubyte)]


class Handle:
    def __init__(self, api, value):
        self.api, self._value, self.poisoned = api, value, False

    @property
    def value(self):
        if self.poisoned or self._value is None:
            raise Refused('owned-cleanup-unconfirmed')
        return self._value

    def close(self):
        if self.poisoned:
            raise Refused('owned-cleanup-unconfirmed')
        if self._value is None:
            return
        self.poisoned = True  # Never retry an unknown/stale numeric handle.
        try:
            closed = self.api.k.CloseHandle(self._value)
        except BaseException:
            _UNCONFIRMED.append(self)
            raise Refused('owned-cleanup-unconfirmed') from None
        if not closed:
            _UNCONFIRMED.append(self)
            raise Refused('owned-cleanup-unconfirmed')
        self._value, self.poisoned = None, False


def guarded(path):
    path = Path(path).absolute()
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise Refused('fixture-refused')
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise Refused('fixture-refused')
    return info


def source_bytes(path, hashes):
    info = guarded(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > 131072:
        raise Refused('source-changed')
    with path.open('rb') as stream:
        data = stream.read(131073)
    if len(data) > 131072:
        raise Refused('source-changed')
    digest = hashlib.sha256(data).hexdigest()
    if digest not in hashes:
        raise Refused('source-changed')
    return digest


def process_module():
    path = Path(__file__).with_name('windows_preparation_process.py')
    source_bytes(path, HELPER_HASHES)
    spec = importlib.util.spec_from_file_location('r19_attribute_owned_process', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Windows:
    def __init__(self):
        if sys.platform != 'win32' or c.sizeof(c.c_void_p) != 8:
            raise Refused('unsupported-host')
        if (c.sizeof(Basic), c.sizeof(Identity), c.sizeof(Standard)) != (40, 24, 24):
            raise Refused('unsupported-host')
        self.k = c.WinDLL('kernel32', use_last_error=True)
        H, P, U, B, W = c.c_void_p, c.c_void_p, c.c_uint32, c.c_int32, c.c_wchar_p
        api = {
            'CreateFileW': ([W, U, U, P, U, U, H], H),
            'CloseHandle': ([H], B),
            'GetFileInformationByHandleEx': ([H, c.c_int32, P, U], B),
            'SetFileInformationByHandle': ([H, c.c_int32, P, U], B),
            'SetFilePointerEx': ([H, c.c_int64, P, U], B),
            'ReadFile': ([H, P, U, P, P], B), 'WriteFile': ([H, P, U, P, P], B),
            'CreateNamedPipeW': ([W, U, U, U, U, U, U, P], H),
            'ConnectNamedPipe': ([H, P], B),
            'PeekNamedPipe': ([H, P, U, P, P, P], B),
            'SetNamedPipeHandleState': ([H, P, P, P], B),
            'GetNamedPipeClientProcessId': ([H, P], B), 'GetProcessId': ([H], U),
            'GetModuleFileNameW': ([H, W, U], U),
            'GetSystemDirectoryW': ([W, U], U),
            'GetVolumePathNameW': ([W, W, U], B),
            'GetVolumeInformationW': ([W, W, U, P, P, P, W, U], B),
            'GetDriveTypeW': ([W], U),
        }
        for name, (args, result) in api.items():
            function = getattr(self.k, name)
            function.argtypes, function.restype = args, result

    def check(self, value):
        if not value:
            raise Refused('native-call-failed')
        return value

    def open(self, path, access):
        guarded(path)
        handle = self.k.CreateFileW(str(path), access, 0, None, 3, 0, None)
        if handle in (None, 0, INVALID):
            raise Refused('native-call-failed')
        return Handle(self, handle)

    def close(self, handle):
        handle.close()

    def query(self, handle, kind, value):
        self.check(self.k.GetFileInformationByHandleEx(handle.value, kind, c.byref(value), c.sizeof(value)))
        return value

    def snapshot(self, handle):
        basic = self.query(handle, 0, Basic())
        identity = self.query(handle, 18, Identity())
        standard = self.query(handle, 1, Standard())
        if (standard.links != 1 or standard.directory or standard.deleting
                or standard.size != len(CONTENT) or basic.attributes & ~(READONLY | NORMAL | 32)):
            raise Refused('preservation-refused')
        self.check(self.k.SetFilePointerEx(handle.value, 0, None, 0))
        data, count = c.create_string_buffer(len(CONTENT) + 1), c.c_uint32()
        self.check(self.k.ReadFile(handle.value, data, len(data), c.byref(count), None))
        if data.raw[:count.value] != CONTENT:
            raise Refused('preservation-refused')
        return {'identity': [identity.volume, bytes(identity.file).hex()],
            'attributes': basic.attributes, 'times': [getattr(basic, n) for n in ('creation', 'access', 'write', 'change')]}

    def attributes(self, handle, original, armed):
        value = Basic()  # Zero times: no invented -1/-2 update suppression.
        value.attributes = ((original & ~NORMAL) | READONLY) if armed else original
        self.check(self.k.SetFileInformationByHandle(handle.value, 0, c.byref(value), c.sizeof(value)))

    def ntfs(self, root):
        volume, filesystem = c.create_unicode_buffer(32768), c.create_unicode_buffer(32)
        self.check(self.k.GetVolumePathNameW(str(root), volume, len(volume)))
        self.check(self.k.GetVolumeInformationW(volume, None, 0, None, None, None, filesystem, len(filesystem)))
        if filesystem.value != 'NTFS' or self.k.GetDriveTypeW(volume) != 3:
            raise Refused('fixture-refused')

    def image(self):
        value = c.create_unicode_buffer(32768)
        size = self.check(self.k.GetModuleFileNameW(None, value, len(value)))
        if size >= len(value):
            raise Refused('native-call-failed')
        return value.value

    def powershell(self):
        value = c.create_unicode_buffer(32768)
        size = self.check(self.k.GetSystemDirectoryW(value, len(value)))
        if size >= len(value):
            raise Refused('native-call-failed')
        path = Path(value.value) / 'WindowsPowerShell/v1.0/powershell.exe'
        guarded(path)
        return str(path)


def decode(data):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refused('protocol-refused')
            result[key] = value
        return result
    if type(data) is not bytes or len(data) > LIMIT:
        raise Refused('protocol-refused')
    try:
        result = json.loads(data.decode('ascii'), object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise Refused('protocol-refused') from None
    if type(result) is not dict:
        raise Refused('protocol-refused')
    return result


class Pipe:
    def __init__(self, api, name=None):
        self.api, self.buffer, self.handle = api, bytearray(), None
        self.name = name or ('r19-lock-attribute-' + uuid.uuid4().hex)
        if not re.fullmatch(r'r19-lock-attribute-[a-f0-9]{32}', self.name):
            raise Refused('protocol-refused')
        path = '\\\\.\\pipe\\' + self.name
        if name is None:
            value = api.k.CreateNamedPipeW(path, 3 | 0x80000, 1 | 8, 1, LIMIT, LIMIT, 0, None)
            if value in (None, 0, INVALID):
                raise Refused('native-call-failed')
            self.handle = Handle(api, value)
            try:
                if not api.k.ConnectNamedPipe(self.handle.value, None) and c.get_last_error() not in (535, 536):
                    raise Refused('native-call-failed')
            except BaseException:
                self.close()
                raise
        else:
            value = api.k.CreateFileW(path, RW, 0, None, 3, 0, None)
            if value in (None, 0, INVALID):
                raise Refused('native-call-failed')
            self.handle = Handle(api, value)
            try:
                mode = c.c_uint32(1)  # Explicit nonblocking byte mode on this end.
                api.check(api.k.SetNamedPipeHandleState(self.handle.value, c.byref(mode), None, None))
            except BaseException:
                self.close()
                raise

    def bind(self, child, deadline):
        observed = c.c_uint32()
        expected = self.api.check(self.api.k.GetProcessId(child.process_handle))
        while time.monotonic() < deadline:
            if self.api.k.GetNamedPipeClientProcessId(self.handle.value, c.byref(observed)):
                if observed.value != expected:
                    raise Refused('protocol-refused')
                return
            time.sleep(.01)
        raise Refused('protocol-refused')

    def send(self, value, deadline):
        data = json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('ascii') + b'\n'
        if len(data) > LIMIT:
            raise Refused('protocol-refused')
        sent = 0
        while sent < len(data) and time.monotonic() < deadline:
            count = c.c_uint32()
            part = c.create_string_buffer(data[sent:])
            if not self.api.k.WriteFile(self.handle.value, part, len(data) - sent, c.byref(count), None):
                raise Refused('protocol-refused')
            if count.value > len(data) - sent:
                raise Refused('protocol-refused')
            sent += count.value
            if not count.value:
                time.sleep(.01)
        if sent != len(data):
            raise Refused('protocol-refused')

    def receive(self, deadline):
        while time.monotonic() < deadline:
            if b'\n' in self.buffer:
                line, _, rest = self.buffer.partition(b'\n')
                self.buffer = bytearray(rest)
                return decode(bytes(line))
            count = c.c_uint32()
            if not self.api.k.PeekNamedPipe(self.handle.value, None, 0, None, c.byref(count), None):
                raise Refused('protocol-refused')
            if count.value:
                remaining = LIMIT + 1 - len(self.buffer)
                data = c.create_string_buffer(min(count.value, remaining))
                read = c.c_uint32()
                self.api.check(self.api.k.ReadFile(self.handle.value, data, len(data), c.byref(read), None))
                self.buffer.extend(data.raw[:read.value])
                if len(self.buffer) > LIMIT:
                    raise Refused('protocol-refused')
            else:
                time.sleep(.01)
        raise Refused('protocol-refused')

    def close(self):
        if self.handle is not None:
            self.api.close(self.handle)
            self.handle = None


def fixture(root, nonce):
    if not isinstance(root, (str, Path)) or type(nonce) is not str:
        raise Refused('fixture-refused')
    root = Path(root)
    base = Path(tempfile.gettempdir()).absolute()
    guarded(base)
    base = base.resolve()
    if (not root.is_absolute() or not re.fullmatch('r19-lock-attribute-[a-z0-9_]+', root.name)
            or root.parent != base or not re.fullmatch('[a-f0-9]{32}', nonce)):
        raise Refused('fixture-refused')
    for path in (root, root / 'data', root / MARKER, root / 'data/companion-operation.lock'):
        guarded(path)
    marker = root / MARKER
    info = guarded(marker)
    if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
        raise Refused('fixture-refused')
    with marker.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if decode(raw) != {'schema': SCHEMA, 'nonce': nonce}:
        raise Refused('fixture-refused')
    return root / 'data/companion-operation.lock'


def private_snapshot(value):
    if (type(value) is not dict or set(value) != {'identity', 'attributes', 'times'}
            or type(value['identity']) is not list or len(value['identity']) != 2
            or type(value['identity'][0]) is not int or not 0 <= value['identity'][0] < 2**64
            or type(value['identity'][1]) is not str or not re.fullmatch('[0-9a-f]{32}', value['identity'][1])
            or type(value['attributes']) is not int or not 0 < value['attributes'] <= 0xffffffff
            or value['attributes'] & ~(READONLY | NORMAL | 32)
            or (value['attributes'] & NORMAL and value['attributes'] != NORMAL)
            or type(value['times']) is not list or len(value['times']) != 4
            or any(type(t) is not int or not 0 <= t < 2**63 for t in value['times'])):
        raise Refused('protocol-refused')
    return value


def transition(original, observed, armed):
    original, observed = private_snapshot(original), private_snapshot(observed)
    expected = ((original['attributes'] & ~NORMAL) | READONLY) if armed else original['attributes']
    if (original['attributes'] & READONLY or observed['identity'] != original['identity']
            or observed['attributes'] != expected):
        raise Refused('preservation-refused')
    equal = [a == b for a, b in zip(original['times'], observed['times'])]
    # Metadata ChangeTime may change intentionally; reads may update access time.
    if not equal[0] or not equal[2]:
        raise Refused('preservation-refused')
    return dict(zip(('creation_equal', 'access_equal', 'write_equal', 'change_equal'), equal))


def child_main(name):
    api, pipe, handle = Windows(), None, None
    try:
        pipe = Pipe(api, name)
        grant = pipe.receive(time.monotonic() + 10)
        if set(grant) != {'root', 'nonce'}:
            raise Refused('protocol-refused')
        path = fixture(grant['root'], grant['nonce'])
        api.ntfs(path.parent)
        handle = api.open(path, RW)
        original = api.snapshot(handle)
        if original['attributes'] & READONLY:
            raise Refused('fixture-refused')
        pipe.send({'state': 'held', 'snapshot': original}, time.monotonic() + 5)
        for command, armed in (('arm', True), ('live-clear', False), ('rearm', True)):
            if pipe.receive(time.monotonic() + 30) != {'command': command}:
                raise Refused('protocol-refused')
            api.attributes(handle, original['attributes'], armed)
            observed = api.snapshot(handle)
            transition(original, observed, armed)
            pipe.send({'state': command, 'snapshot': observed}, time.monotonic() + 5)
        # Only the parent-held genuine creation object may end this lease owner.
        time.sleep(90)
    except BaseException:
        # No raw child stderr/exception, restoration, or borrowed cleanup grant.
        if pipe is not None:
            try:
                pipe.send({'state': 'refused'}, time.monotonic() + 1)
            except BaseException:
                pass
    finally:
        for operation in (lambda: api.close(handle) if handle is not None else None,
                          lambda: pipe.close() if pipe is not None else None):
            try:
                operation()
            except BaseException:
                pass  # Parent requires a genuine signaled child and job drain.
    return 2


LEGACY_SCRIPT = r'''
$ErrorActionPreference='Stop'
$pipe=[IO.Pipes.NamedPipeClientStream]::new('.', '__PIPE__', [IO.Pipes.PipeDirection]::InOut)
try {
    $pipe.Connect(5000)
    $reader=[IO.StreamReader]::new($pipe,[Text.Encoding]::ASCII,$false,4096,$true)
    $writer=[IO.StreamWriter]::new($pipe,[Text.Encoding]::ASCII,4096,$true)
    $writer.AutoFlush=$true
    $grant=$reader.ReadLine()|ConvertFrom-Json
    $source=[IO.File]::Open([string]$grant.source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        if ($source.Length -gt 131072) { throw 'Source exceeds bound.' }
        $raw=[byte[]]::new([int]$source.Length)
        $offset=0
        while ($offset -lt $raw.Length) {
            $count=$source.Read($raw,$offset,$raw.Length-$offset)
            if ($count -le 0) { throw 'Source read incomplete.' }
            $offset+=$count
        }
    } finally { $source.Dispose() }
    $hash=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($raw))).Replace('-','').ToLowerInvariant()
    if ($hash -cne [string]$grant.sha256) { throw 'Source differs.' }
    $tokens=$null; $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseInput([Text.UTF8Encoding]::new($false,$true).GetString($raw),[ref]$tokens,[ref]$errors)
    $defs=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Enter-CompanionOperation'},$true))
    if ($errors -or $defs.Count -ne 1) { throw 'Source definition differs.' }
    . ([scriptblock]::Create($defs[0].Extent.Text))
    $state='unclassified-refusal'; $file=$null
    try { $file=Enter-CompanionOperation ([string]$grant.root) -TimeoutSeconds 0 }
    catch {
        $base=$_.Exception.GetBaseException()
        if ($base -is [UnauthorizedAccessException] -and ($base.HResult -band 65535) -eq 5) { $state='readonly-refused' }
        elseif ($_.Exception.Message -ceq 'Another companion start or update is still in progress. Try again when it finishes.') { $state='sharing-refused' }
    }
    if ($null -ne $file) {
        try { $file.Dispose(); $state='open' } catch { $state='file-close-unconfirmed' }
    }
    $writer.WriteLine('{"state":"'+$state+'"}')
} finally {
    try { if ($null -ne $writer) { $writer.Dispose() } }
    finally { try { if ($null -ne $reader) { $reader.Dispose() } } finally { $pipe.Dispose() } }
}
'''


class Attempt:
    def __init__(self, api, command, cwd):
        self.api, self.pipe, self.owner, self.child = api, None, None, None
        self.closed = self.poisoned = False
        try:
            self.pipe = Pipe(api)
            self.owner = process_module().WindowsPreparationProcess()
            env = {k: v for k, v in os.environ.items() if k.casefold() in {'systemroot', 'windir', 'temp', 'tmp'}}
            self.child = self.owner.create_suspended(command(self.pipe.name), cwd=cwd, env=env)
            self.child.resume_once()
            self.pipe.bind(self.child, time.monotonic() + 10)
        except BaseException:
            self.close()
            raise

    def exchange(self, value):
        self.pipe.send(value, time.monotonic() + 5)
        return self.pipe.receive(time.monotonic() + 10)

    def close(self):
        if self.poisoned:
            raise Refused('owned-cleanup-unconfirmed')
        if self.closed:
            return
        self.poisoned = True
        uncertain = False
        for operation in (
            lambda: self.child.stop_and_wait(time.monotonic() + 5) if self.child is not None else None,
            lambda: self.owner.terminate(timeout=5) if self.owner is not None else None,
            lambda: self.owner.close() if self.owner is not None else None,
            lambda: self.pipe.close() if self.pipe is not None else None,
        ):
            try:
                operation()
            except BaseException:
                uncertain = True
        if uncertain:
            _UNCONFIRMED.append(self)
            raise Refused('owned-cleanup-unconfirmed')
        self.closed, self.poisoned = True, False


def legacy(api, root, expected_source, expected):
    source_bytes(SOURCE, SOURCE_HASHES)
    executable = api.powershell()
    def command(name):
        script = LEGACY_SCRIPT.replace('__PIPE__', name)
        return [executable, '-NoProfile', '-NonInteractive', '-EncodedCommand', base64.b64encode(script.encode('utf-16le')).decode('ascii')]
    attempt = Attempt(api, command, root)
    try:
        observed = attempt.exchange({'root': str(root), 'source': str(SOURCE), 'sha256': expected_source})
        if observed != {'state': expected}:
            raise Refused('legacy-outcome-differed')
    finally:
        attempt.close()
    source_bytes(SOURCE, SOURCE_HASHES)


def receipt():
    return {'schema': SCHEMA, 'scope': 'authored-local-ntfs-no-writers-mechanism',
        'status': 'failed', 'phase': 'fixture', 'failure': 'unexpected-failure',
        'legacy_source_sha256': None,
        'candidate_data_writers': 0, 'observed': [], 'timestamp_equalities': {},
        'cleanup': 'unconfirmed-fixture-retained', 'production_allowed': False,
        'keeper_loss_acceptance': False, 'rights_approval': False,
        'native_windows_11_acceptance': 'unavailable', 'r19_complete': False}


def public_receipt(value):
    template = receipt()
    if type(value) is not dict or set(value) != set(template):
        raise Refused('protocol-refused')
    flexible = {'status', 'phase', 'failure', 'observed', 'timestamp_equalities', 'cleanup', 'legacy_source_sha256'}
    for key in set(template) - flexible:
        if type(value[key]) is not type(template[key]) or value[key] != template[key]:
            raise Refused('protocol-refused')
    if (type(value['status']) is not str or value['status'] not in {'failed', 'mechanism-observed'}
            or type(value['phase']) is not str or value['phase'] not in PHASES
            or type(value['failure']) is not str or value['failure'] not in FAILURES
            or type(value['cleanup']) is not str
            or value['cleanup'] not in {'unconfirmed-fixture-retained', 'owned-handles-closed-fixture-retained'}
            or (value['legacy_source_sha256'] is not None and (type(value['legacy_source_sha256']) is not str
                or value['legacy_source_sha256'] not in SOURCE_HASHES))
            or type(value['observed']) is not list or len(value['observed']) > len(OBSERVATIONS)
            or tuple(value['observed']) != OBSERVATIONS[:len(value['observed'])]
            or type(value['timestamp_equalities']) is not dict
            or set(value['timestamp_equalities']) - set(TIME_STATES)):
        raise Refused('protocol-refused')
    for item in value['timestamp_equalities'].values():
        if (type(item) is not dict or set(item) != {'creation_equal', 'access_equal', 'write_equal', 'change_equal'}
                or any(type(v) is not bool for v in item.values())):
            raise Refused('protocol-refused')
    if value['status'] == 'mechanism-observed' and (value['phase'] != 'complete' or value['failure'] != 'none'
            or tuple(value['observed']) != OBSERVATIONS or set(value['timestamp_equalities']) != set(TIME_STATES)
            or value['cleanup'] != 'owned-handles-closed-fixture-retained' or value['legacy_source_sha256'] is None
            or any(not item['creation_equal'] or not item['write_equal'] for item in value['timestamp_equalities'].values())):
        raise Refused('protocol-refused')
    return json.loads(json.dumps(value))


def experiment():
    result, attempt, restore, api = receipt(), None, None, None
    try:
        api = Windows()
        digest = source_bytes(SOURCE, SOURCE_HASHES)
        result['legacy_source_sha256'] = digest
        base = Path(tempfile.gettempdir()).absolute()
        guarded(base)
        base = base.resolve()
        api.ntfs(base)  # Refuse remote/unsupported storage before fixture writes.
        root = Path(tempfile.mkdtemp(prefix='r19-lock-attribute-', dir=base))
        (root / 'data').mkdir()
        nonce = uuid.uuid4().hex
        (root / MARKER).write_text(json.dumps({'schema': SCHEMA, 'nonce': nonce}), encoding='ascii')
        path = root / 'data/companion-operation.lock'
        path.write_bytes(CONTENT)
        fixture(root, nonce); api.ntfs(root)
        result['phase'] = 'legacy-baseline'
        legacy(api, root, digest, 'open'); result['observed'].append('writable-open')
        result['phase'] = 'lease-start'
        attempt = Attempt(api, lambda name: [api.image(), '-I', '-B', str(Path(__file__).resolve()), '--owned-lease', name], root)
        observed = attempt.exchange({'root': str(root), 'nonce': nonce})
        if set(observed) != {'state', 'snapshot'} or observed['state'] != 'held':
            raise Refused('protocol-refused')
        original = private_snapshot(observed['snapshot'])
        if original['attributes'] & READONLY:
            raise Refused('fixture-refused')
        legacy(api, root, digest, 'sharing-refused'); result['observed'].append('exclusive-held')
        for phase, armed in (('arm', True), ('live-clear', False), ('rearm', True)):
            result['phase'] = phase
            observed = attempt.exchange({'command': phase})
            if set(observed) != {'state', 'snapshot'} or observed['state'] != phase:
                raise Refused('protocol-refused')
            result['timestamp_equalities'][phase] = transition(original, observed['snapshot'], armed)
            if phase == 'live-clear':
                legacy(api, root, digest, 'sharing-refused')
            result['observed'].append(phase)
        result['phase'] = 'owner-loss'
        attempt.close(); attempt = None
        result['observed'].append('genuine-owner-signaled-and-closed')
        result['phase'] = 'post-loss'
        # Observer has no lease until this temporary read-data observation open.
        restore = api.open(path, RESTORE)
        result['timestamp_equalities']['post-loss'] = transition(original, api.snapshot(restore), True)
        api.close(restore); restore = None
        legacy(api, root, digest, 'readonly-refused')
        result['observed'].append('post-loss-readonly-refused')
        result['phase'] = 'test-restore'
        # Test-only authority: this experiment has admitted exactly zero writers.
        restore = api.open(path, RESTORE)
        transition(original, api.snapshot(restore), True)
        api.attributes(restore, original['attributes'], False)
        result['timestamp_equalities']['test-restore'] = transition(original, api.snapshot(restore), False)
        legacy(api, root, digest, 'sharing-refused')
        api.close(restore); restore = None
        result['phase'] = 'restored'
        legacy(api, root, digest, 'open'); result['observed'].append('restored-open')
        restore = api.open(path, RESTORE)
        result['timestamp_equalities']['restored'] = transition(original, api.snapshot(restore), False)
        api.close(restore); restore = None
        if source_bytes(SOURCE, SOURCE_HASHES) != digest:
            raise Refused('source-changed')
        result.update(status='mechanism-observed', phase='complete', failure='none',
            cleanup='owned-handles-closed-fixture-retained')
    except BaseException as error:
        result['failure'] = error.code if isinstance(error, Refused) else 'unexpected-failure'
    finally:
        uncertain = False
        for operation in (lambda: attempt.close() if attempt is not None else None,
                          lambda: api.close(restore) if restore is not None else None):
            try:
                operation()
            except BaseException:
                uncertain = True
        if uncertain:
            result.update(status='failed', failure='owned-cleanup-unconfirmed', cleanup='unconfirmed-fixture-retained')
    return public_receipt(result)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--owned-lease':
        try:
            code = child_main(sys.argv[2])
        except BaseException:
            code = 2
        raise SystemExit(code)
    try:
        if len(sys.argv) != 1:
            value = receipt(); value['failure'] = 'protocol-refused'
        else:
            value = experiment()
    except BaseException:
        value = receipt()
    print(json.dumps(value, sort_keys=True))
    raise SystemExit(0 if value['status'] == 'mechanism-observed' else 2)
