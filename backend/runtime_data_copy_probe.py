"""One authored frozen store copy; never a production migration authority."""
from __future__ import annotations

from dataclasses import replace
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import shutil
import sqlite3
import stat
import tempfile
import threading
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from . import bundle_migration as migration
from .bundle_host import (HostProbeError, SyntheticHandoff, SyntheticHostCoordinator,
                          WriterStopProof, _atomic_json, create_synthetic_root)
from .models import TextMatch
from .runtime_host import FrozenProbeHost, HostProbeFailure, hold_keeper_recovery
from .runtime_probe import GRAMMAR_TEXT, GRAMMAR_SLUG, GRAMMAR_ABSENT_SLUG, GRAMMAR_CHOICE_KEY
from .storage import TranscriptStore, TranscriptConnectionCloseError

SCHEMA = 'proxy-r19-frozen-data-copy-probe-v1'
CASE = 'authored-data-copy'
RESUME_CASE = 'authored-data-copy-resume'
RESUME_SCHEMA = 'proxy-r19-frozen-data-copy-resume-probe-v1'
RESUME_SCOPE = 'authored-transcript-interrupted-copy-resume-with-living-coordinator'
WAL_CASE = 'authored-data-copy-wal'
WAL_SCHEMA = 'proxy-r19-frozen-data-copy-wal-probe-v1'
WAL_SCOPE = 'authored-transcript-retained-wal-copy-with-living-coordinator'
WAL_POLICY = 'no-checkpoint-on-close-per-open-readback'
WAL_FILE_BYTES = 8 * 1024 * 1024
GRAMMAR_CASE = 'authored-data-copy-grammar'
GRAMMAR_SCHEMA = 'proxy-r19-frozen-data-copy-grammar-probe-v1'
GRAMMAR_SCOPE = 'authored-populated-local-grammar-copy-with-living-coordinator'
PHASES = ('setup-closed', 'favorite-written', 'strict-drain-complete', 'writers-signaled',
          'copy-progress', 'copy-verified', 'source-resumed', 'final-strict-drain-complete',
          'final-writers-signaled', 'released')
RESUME_PHASES = (*PHASES[:5], 'copy-interrupted', *PHASES[5:])
WAL_PHASES = (*PHASES[:4], 'wal-set-observed', *PHASES[4:])
GRAMMAR_PHASES = (*PHASES[:2], 'grammar-written', *PHASES[2:])
FAILURES = frozenset({'fixture-unavailable', 'setup-close-unconfirmed', 'setup-still-open',
    'cohort-unconfirmed', 'owned-host-unconfirmed', 'copy-refused', 'copy-result-unconfirmed',
    'schema-unconfirmed', 'authored-rows-differ', 'pointer-changed', 'source-changed',
    'control-unavailable', 'control-invalid', 'lease-release-unconfirmed', 'interrupted-copy-unconfirmed',
    'unexpected-data-copy-failure', 'wal-set-unavailable', 'wal-dependency-unconfirmed',
    'wal-verification-cleanup-unconfirmed', 'sqlite-version-unavailable', 'grammar-choice-unconfirmed'})
DATABASE_VERSIONS = {'data/transcript-v2.db': 0, 'data/lexirise/exports-v2.db': 0,
                     'data/lexirise/reading-cache-v2.db': 0}
TABLE_COLUMNS = {
    'data/transcript-v2.db': {'transcript_lines': ('id', 'created_at', 'session_id', 'game',
        'source_ocr', 'english', 'chinese', 'text_id', 'score', 'match_kind', 'ambiguous',
        'channel', 'voiced', 'audio_path', 'speaker_english', 'speaker_chinese', 'favorite',
        'language_context'), 'sqlite_sequence': ('name', 'seq')},
    'data/lexirise/exports-v2.db': {'exports': ('key', 'state'), 'export_refs': ('ref', 'export_key'),
        'scoped_exports': ('scope', 'key', 'state'),
        'scoped_export_refs': ('scope', 'ref', 'export_key'),
        'game_decks': ('scope', 'game', 'deck_id', 'title')},
    'data/lexirise/reading-cache-v2.db': {'cache': ('kind', 'key', 'value', 'at'),
        'grammar_choices': ('slug', 'proficiency')},
}
OPTIONAL_TABLE_COLUMNS = {'data/transcript-v2.db': {'sqlite_stat1': ('tbl', 'idx', 'stat')}}
ROW_FIELDS = ('id', 'game', 'text_id', 'english', 'chinese', 'source_ocr', 'source_language',
    'source_locale', 'source_text', 'translation_locale', 'translation_text', 'audio_locale',
    'texts', 'voice_status', 'dialogue_kind', 'favorite', 'voiced', 'has_audio')
STOPPED = WriterStopProof(True, True, True, True, True)
INSPECTION_ENTRIES = 4096
INSPECTION_DEPTH = 32
INSPECTION_BYTES = 64 * 1024 * 1024
AUTHORED_PAYLOAD = b'R19 authored bytes only\x00\xff'


class DataCopyFailure(RuntimeError):
    def __init__(self, code):
        self.code = code if code in FAILURES else 'unexpected-data-copy-failure'
        super().__init__('Authored frozen data copy failed: '+self.code)


class _AuthoredCopyInterruption(RuntimeError):
    """Only one exact private instance from the fixed callback permits resume."""


def _guard_path(path, kind=None, *, missing=False):
    """Raw root-first metadata; never inspect a descendant through a link."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise DataCopyFailure('interrupted-copy-unconfirmed')
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if missing:
                return None
            raise DataCopyFailure('interrupted-copy-unconfirmed') from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise DataCopyFailure('interrupted-copy-unconfirmed')
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise DataCopyFailure('interrupted-copy-unconfirmed')
    if ((kind == 'directory' and not stat.S_ISDIR(info.st_mode))
            or (kind == 'file' and not stat.S_ISREG(info.st_mode))
            or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
        raise DataCopyFailure('interrupted-copy-unconfirmed')
    return info


def _guard_tree(root, *, missing=False, files=None, directories=None, sizes=None):
    """Bounded top-down census. Unknown partial names are refused before stat."""
    if _guard_path(root, 'directory', missing=missing) is None:
        return
    pending, inspected, total_bytes = [Path(root)], 0, 0
    while pending:
        directory = pending.pop()
        _guard_path(directory, 'directory')
        with os.scandir(directory) as entries:
            for entry in entries:
                inspected += 1
                child = directory/entry.name
                relative = child.relative_to(root)
                if inspected > INSPECTION_ENTRIES or len(relative.parts) > INSPECTION_DEPTH:
                    raise DataCopyFailure('interrupted-copy-unconfirmed')
                name = relative.as_posix()
                if files is not None:
                    if name in files:
                        kind = 'file'
                    elif name in directories:
                        kind = 'directory'
                    else:
                        raise DataCopyFailure('interrupted-copy-unconfirmed')
                else:
                    kind = None
                info = _guard_path(child, kind)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(child)
                else:
                    total_bytes += info.st_size
                    if (total_bytes > INSPECTION_BYTES or sizes is not None and name in sizes
                            and info.st_size != sizes[name]):
                        raise DataCopyFailure('interrupted-copy-unconfirmed')


def _guard_snapshot(snapshot, files, directories):
    allowed = set(directories)
    for name in (*directories, *(item['name'] for item in files)):
        allowed.update(parent.as_posix() for parent in Path(name).parents if parent != Path('.'))
    _guard_tree(snapshot, files={item['name'] for item in files}, directories=allowed,
                sizes={item['name']: item['size'] for item in files})


class _ProbeCoordinator(SyntheticHostCoordinator):
    """Same lease owner/operations; guard fixed filesystem entrypoints only."""
    def _failed_entry(self):
        self._recovery_required = True
        for runtime in self._owned:
            runtime.poisoned = True

    def _require_owner(self, owner, *, closing=False):
        try:
            for root in (self.legacy.path, self.state.path):
                _guard_path(root, 'directory')
                if _guard_path(root/'.r19-synthetic-fixture.json', 'file').st_size > 4096:
                    raise DataCopyFailure('cohort-unconfirmed')
            return super()._require_owner(owner, closing=closing)
        except BaseException:
            self._failed_entry()
            raise

    def _record(self, stage, **details):
        if stage == 'recovery-required':
            self._recovery_required = True  # Preserve core's flag-before-I/O order.
        try:
            _guard_path(self.journal_path.parent, 'directory')
            _guard_path(self.journal_path, 'file', missing=True)
            return super()._record(stage, **details)
        except BaseException:
            self._failed_entry()
            raise

    def _publish_pointer(self, runtime):
        try:
            _guard_path(self.pointer_path.parent, 'directory')
            _guard_path(self.pointer_path, 'file', missing=True)
            return super()._publish_pointer(runtime)
        except BaseException:
            self._failed_entry()
            raise


def _row(value):
    if not isinstance(value, dict) or any(key not in value for key in ROW_FIELDS):
        raise DataCopyFailure('authored-rows-differ')
    if (type(value['id']) is not int or value['id'] < 1
            or any(type(value[key]) is not bool for key in ('favorite', 'voiced', 'has_audio'))
            or any(type(value[key]) is not str for key in ROW_FIELDS
                   if key not in {'id', 'favorite', 'voiced', 'has_audio', 'texts'})
            or type(value['texts']) is not dict
            or any(type(key) is not str or type(text) is not str for key, text in value['texts'].items())):
        raise DataCopyFailure('authored-rows-differ')
    return {key: value[key] for key in ROW_FIELDS}


def seed_authored(path):
    """Production operation scopes own close; never retry their failed handle."""
    try:
        store = TranscriptStore(path)
        rows = []
        for index, (chinese, english) in enumerate((('这是保留的中文。', 'This Chinese text stays.'),
                ('第二行保持原样。', 'The second line stays unchanged.')), 1):
            match = TextMatch(game='hito', text_id=f'r19-authored-{index}', english=english,
                chinese=chinese, source_ocr=chinese, score=1, kind='exact',
                source_language='zh', source_locale='zh-Hans', source_text=chinese,
                translation_locale='en', translation_text=english, audio_locale='zh-Hans',
                texts={'zh-Hans': chinese, 'en': english}, voice_status='unvoiced',
                dialogue_kind='ordinary-conversation')
            line = store.add(match, 'r19-authored-session',
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
            rows.append(_row(line.model_dump(mode='json')))
        return rows
    except TranscriptConnectionCloseError as error:
        raise DataCopyFailure('setup-close-unconfirmed') from error


@contextmanager
def _verification_scope(target, retained=None):
    if retained is None:
        # Existing C3/C4 lifetime and error behavior stay unchanged.
        with tempfile.TemporaryDirectory(prefix='authored-semantic-', dir=target) as temporary:
            record = {'root': Path(temporary), 'connection': None}
            try:
                yield record
            finally:
                if record['connection'] is not None:
                    record['connection'].close()
        return
    record = {'root': Path(tempfile.mkdtemp(prefix='authored-wal-semantic-', dir=target)), 'connection': None}
    retained.append(record)
    try:
        yield record
    finally:
        try:
            if record['connection'] is not None:
                record['connection'].close()
                record['connection'] = None
            shutil.rmtree(record['root'])
        except BaseException:
            # Retain the exact failed verification owner; no destructor/retry
            # or successful metadata can silently dispose unknown cleanup.
            raise DataCopyFailure('wal-verification-cleanup-unconfirmed') from None
        retained.remove(record)


def verify_authored_snapshot(snapshot, target, expected, *, retained=None, grammar_probe=False):
    """Read separate verification copies; never run store initialization here."""
    for name in TABLE_COLUMNS:
        with _verification_scope(target, retained) as record:
            database = record['root']/'store.db'
            source = snapshot/name
            shutil.copy2(source, database)
            for suffix in ('-wal', '-shm'):
                sidecar = source.with_name(source.name+suffix)
                if sidecar.exists():
                    shutil.copy2(sidecar, database.with_name(database.name+suffix))
            connection = record['connection'] = sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)
            connection.row_factory = sqlite3.Row
            _verify_store(connection, name, expected, grammar_probe=grammar_probe)


def _verify_store(connection, name, expected, *, grammar_probe=False):
    tables = TABLE_COLUMNS[name]
    actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    known = {**tables, **OPTIONAL_TABLE_COLUMNS.get(name, {})}
    if (not set(tables) <= actual or not actual <= set(known)
            or connection.execute('PRAGMA user_version').fetchone()[0] != 0):
        raise DataCopyFailure('schema-unconfirmed')
    for table in actual:
        found = tuple(row[1] for row in connection.execute('PRAGMA table_info('+table+')'))
        if found != known[table]:
            raise DataCopyFailure('schema-unconfirmed')
    if name == 'data/transcript-v2.db':
        rows = [_row(TranscriptStore._row_to_line(row).model_dump(mode='json'))
                for row in connection.execute('SELECT * FROM transcript_lines ORDER BY id')]
        if rows != expected:
            raise DataCopyFailure('authored-rows-differ')
    if grammar_probe and name == 'data/lexirise/reading-cache-v2.db':
        rows = [tuple(row) for row in connection.execute('SELECT slug,proficiency FROM grammar_choices ORDER BY slug')]
        if rows != [(GRAMMAR_CHOICE_KEY, 4)] or type(rows[0][1]) is not int:
            raise DataCopyFailure('grammar-choice-unconfirmed')


def verify_main_only_transcript(source, target, expected, retained):
    """Frozen private DB-only copy; never assert immutable on a live source."""
    _guard_path(target, 'directory')
    _guard_path(source, 'file')
    try:
        with _verification_scope(target, retained) as record:
            database = record['root']/'store.db'
            shutil.copy2(source, database)
            connection = record['connection'] = sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1', uri=True)
            connection.row_factory = sqlite3.Row
            _verify_store(connection, 'data/transcript-v2.db', expected)
    except DataCopyFailure as error:
        if error.code == 'wal-verification-cleanup-unconfirmed':
            raise
        raise DataCopyFailure('wal-dependency-unconfirmed') from None


class _FrozenAuthoredDataRuntime:
    """Fixed writer admission only. The coordinator, not this adapter, owns leases."""
    def __init__(self, layout, installation_id, observe, *, wal_probe=False, grammar_probe=False,
                 grammar_checkpoint=None):
        if type(wal_probe) is not bool or type(grammar_probe) is not bool or wal_probe and grammar_probe:
            raise DataCopyFailure('control-invalid')
        if grammar_probe and not callable(grammar_checkpoint) or not grammar_probe and grammar_checkpoint is not None:
            raise DataCopyFailure('control-invalid')
        self.layout, self.installation_id, self.observe = layout, installation_id, observe
        self.wal_probe = wal_probe
        self.grammar_probe = grammar_probe
        self.grammar_checkpoint = grammar_checkpoint
        self.runtime_id = 'authored-source'
        self.generation = self.drains = 0
        self.setup_open = self.active = self.poisoned = False
        self.host = None
        self.cohorts = []

    def _require_owned(self):
        if self.poisoned:
            raise DataCopyFailure('cohort-unconfirmed')

    def prepare(self):
        raise DataCopyFailure('cohort-unconfirmed')  # No warm-candidate preparation in this case.

    def ready(self):
        raise DataCopyFailure('cohort-unconfirmed')  # Readiness cannot become a copy token.

    def capture_running(self):
        # Conservative producer state, not an observation of physical capture.
        return self.setup_open or self.active or self.poisoned

    def write_generation(self):
        return self.generation

    def start(self):
        self._require_owned()
        if self.setup_open or self.active or self.generation >= 2:
            raise DataCopyFailure('setup-still-open')
        self.generation += 1  # Invalidate older proof before even a partial creation attempt.
        self.active = True
        try:
            self.host = FrozenProbeHost(self.layout)
            self.cohorts.append(self.host)
            if self.grammar_probe:
                self.host.start_registered(detached_console=True, grammar_probe=True)
            elif self.wal_probe:
                self.host.start_registered(detached_console=True, wal_probe=True)
            else:
                self.host.start_registered(detached_console=True)
            self.host.resume_registered()
            self.host.wait_services()
        except BaseException:
            self.poisoned = True
            raise

    def request(self, request):
        self._require_owned()
        if not self.active:
            raise DataCopyFailure('cohort-unconfirmed')
        try:
            with self.host._registered_listener_scope() as owned:
                if not owned:
                    raise DataCopyFailure('owned-host-unconfirmed')
                with urlopen(request, timeout=5) as response:
                    data = response.read(65537)
                    if response.status != 200 or len(data) > 65536:
                        raise DataCopyFailure('owned-host-unconfirmed')
                    return json.loads(data)
        except BaseException:
            self.poisoned = True
            raise

    def quiesce(self):
        self._require_owned()
        if self.setup_open or not self.active or self.host is None:
            raise DataCopyFailure('cohort-unconfirmed')
        first_grammar_cohort = self.grammar_probe and self.generation == 1
        try:
            self.host.quiesce_registered()
            self.drains += 1
            prefix = 'final-' if self.generation == 2 else ''
            self.observe(prefix+'strict-drain-complete')
            if first_grammar_cohort:
                self.grammar_checkpoint('strict-drain-complete')
            self.host.close()
            children = self.host.registered
            if (not self.host.closed or self.host.tree is not None or self.host.recovery_required
                    or set(children) != {'frontend', 'api'} or
                    not all(child.created and child.resumed and child.exited and child.closed
                            for child in children.values())):
                raise DataCopyFailure('cohort-unconfirmed')
            self.active = False
            self.observe(prefix+'writers-signaled')
            if first_grammar_cohort:
                self.grammar_checkpoint('writers-signaled')
            return STOPPED, SyntheticHandoff(False)
        except BaseException:
            self.poisoned = True
            raise

    def reject_unknown_grammar(self):
        """One fixed negative HTTP case; never arbitrary expected status/URL."""
        self._require_owned()
        if not self.grammar_probe or not self.active:
            raise DataCopyFailure('cohort-unconfirmed')
        request = Request('http://127.0.0.1:8766/api/lines/1/reading/grammar',
            data=json.dumps({'slug': GRAMMAR_ABSENT_SLUG, 'known': True}).encode(), method='POST',
            headers={'Content-Type': 'application/json', 'X-Proxy-Transcript': 'lexirise',
                     'X-Proxy-Transcript-Account': 'legacy'})
        try:
            with self.host._registered_listener_scope() as owned:
                if not owned:
                    raise DataCopyFailure('owned-host-unconfirmed')
                try:
                    with urlopen(request, timeout=5) as response:
                        response.read(65537)
                    raise DataCopyFailure('grammar-choice-unconfirmed')
                except HTTPError as response:
                    with response:
                        body = response.read(65537)
                        if (response.code != 404 or len(body) > 65536
                                or json.loads(body) != {'detail': 'Grammar rule not found in this line'}):
                            raise DataCopyFailure('grammar-choice-unconfirmed')
        except BaseException:
            self.poisoned = True
            raise

    def activate(self, handoff):
        self._require_owned()
        if type(handoff) is not SyntheticHandoff or handoff.running is not False or self.active or self.generation != 1:
            self.poisoned = True
            raise DataCopyFailure('cohort-unconfirmed')
        self.start()  # A new same-source Job/cohort; never the snapshot or old exited handles.

    def stop(self):
        self._require_owned()
        if self.setup_open:
            self.poisoned = True
            raise DataCopyFailure('setup-still-open')
        if self.active:
            return self.quiesce()[0]
        return STOPPED


class _DataCopyProbe:
    def __init__(self, layout, stream, *, case=CASE):
        if type(case) is not str or case not in {CASE, RESUME_CASE, WAL_CASE, GRAMMAR_CASE}:
            raise DataCopyFailure('control-invalid')
        FrozenProbeHost(layout)  # Existing exact-image/profile/private-root/dev-tool guards.
        self.outer, self.stream = layout, stream
        self.case = case
        self.adapter = self.coordinator = None
        self.enter_attempted = self.entered = self.released = self.release_attempted = False
        self.phase = 'prepare'
        self.copy_verified = self.source_preserved = self.logical_preserved = False
        self.old_barrier_refused = False
        self.wal_files = self.shm_files = 0
        self.copy_attempts = self.authored_interruptions = self.partial_revalidations = 0
        self.partial_completed_files = 0
        self.same_plan_barrier_generation = self.copy_resumed = False
        self.sqlite_version = ''
        self.transcript_wal_bytes = self.transcript_shm_bytes = 0
        self.wal_set_observed = self.wal_dependency = False
        self.verification_ownership = []
        self.core_copy_failure = None
        self.setup_failure = None
        self.grammar_baseline = self.grammar_unknown_refused = self.grammar_written = False
        self.grammar_snapshot = self.grammar_restarted = False
        self.grammar_ack_state = None
        self.commands = queue.Queue(maxsize=1)
        def read():
            try:
                while True:
                    value = stream.readline(257)
                    self.commands.put(value)
                    if not value:
                        return
            except BaseException:
                self.commands.put(None)
        threading.Thread(target=read, name='authored-copy-control', daemon=True).start()

    def emit(self, phase, *, failure='none'):
        adapter = self.adapter
        children = [child for host in adapter.cohorts for child in host.registered.values()] if adapter else []
        value = {'schema': GRAMMAR_SCHEMA if self.case == GRAMMAR_CASE else WAL_SCHEMA if self.case == WAL_CASE else RESUME_SCHEMA if self.case == RESUME_CASE else SCHEMA,
            'kind': 'data-copy', 'case': self.case, 'phase': phase,
            'status': 'failed' if failure != 'none' else 'passed' if phase == 'released' else 'observing',
            'failure': failure, 'source_commit': self.outer.source_commit, 'build_id': self.outer.build_id,
            'generation': adapter.generation if adapter else 0,
            'writers_created': sum(bool(child.created) for child in children),
            'writers_resumed': sum(bool(child.resumed) for child in children),
            'writers_signaled': sum(bool(child.exited) for child in children),
            'strict_drains': adapter.drains if adapter else 0,
            'copy_verification': 'passed' if self.copy_verified else 'not-run',
            'source_bytes': 'preserved-before-resume' if self.source_preserved else 'not-run',
            'source_logical': 'passed' if self.logical_preserved else 'not-run',
            'wal_files': self.wal_files, 'shm_files': self.shm_files,
            'old_barrier_refused': self.old_barrier_refused,
            'api_external_side_effects': 'mocked', 'sqlite': 'real', 'native_owned_process_tree': 'real',
            'writer_console_mode': 'detached-process', 'authority': 'retained-creation-objects-and-typed-barrier',
            'production_activation': False, 'target_activation': False, 'r19_complete': False,
            'keeper_loss': 'unavailable', 'dynamic_writer_admission': 'unavailable',
            'warm_routing': 'unavailable', 'credentials': 'not-accessed', 'browser': 'not-run', 'installer': 'not-built'}
        if self.case == RESUME_CASE:
            value.update(scope=RESUME_SCOPE, copy_attempts=self.copy_attempts,
                authored_interruptions=self.authored_interruptions,
                partial_completed_files=self.partial_completed_files,
                partial_revalidations=self.partial_revalidations,
                same_plan_barrier_generation=self.same_plan_barrier_generation,
                copy_resumed=self.copy_resumed)
        if self.case == WAL_CASE:
            value.update(scope=WAL_SCOPE, sqlite_policy=WAL_POLICY, sqlite_version=self.sqlite_version,
                sqlite_version_scope='frozen-coordinator',
                transcript_wal_bytes=self.transcript_wal_bytes, transcript_shm_bytes=self.transcript_shm_bytes,
                wal_set='nonempty-after-retained-signals' if self.wal_set_observed else 'not-run',
                wal_dependency='main-only-false-full-set-true' if self.wal_dependency else 'not-run')
        if self.case == GRAMMAR_CASE:
            value.update(scope=GRAMMAR_SCOPE, reading_transport='fixed-mock-settings-analysis-only',
                grammar_credential_fixture='in-memory-noncredential',
                grammar_baseline='zero-without-local-override' if self.grammar_baseline else 'not-run',
                unknown_grammar_rule='rejected-404' if self.grammar_unknown_refused else 'not-run',
                grammar_written='four-with-local-override' if self.grammar_written else 'not-run',
                grammar_snapshot='one-scoped-choice-four' if self.grammar_snapshot else 'not-run',
                grammar_restarted='four-with-local-override' if self.grammar_restarted else 'not-run',
                grammar_override_rows=int(self.grammar_snapshot))
        print(json.dumps(value, separators=(',', ':')), flush=True)

    def observe(self, phase):
        phases = GRAMMAR_PHASES if self.case == GRAMMAR_CASE else WAL_PHASES if self.case == WAL_CASE else RESUME_PHASES if self.case == RESUME_CASE else PHASES
        if phase not in phases or phase == 'released':
            raise DataCopyFailure('control-invalid')
        self.phase = phase
        self._pointer_unchanged()
        self.emit(phase)
        try:
            command = self.commands.get(timeout=45)
        except queue.Empty:
            raise DataCopyFailure('control-unavailable') from None
        if command != 'observed '+phase+'\n':
            raise DataCopyFailure('control-invalid')

    def _pointer_unchanged(self):
        _guard_path(self.coordinator.pointer_path, 'file')
        with self.coordinator.pointer_path.open('rb') as stream:
            actual = stream.read(len(self.pointer)+1)
        if actual != self.pointer:
            raise DataCopyFailure('pointer-changed')

    def prepare(self):
        if self.case == WAL_CASE:
            version = sqlite3.sqlite_version
            if type(version) is not str or re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', version) is None:
                raise DataCopyFailure('sqlite-version-unavailable')
            self.sqlite_version = version
        work = self.outer.work_root
        temporary = Path(tempfile.gettempdir()).resolve()
        if work == temporary or not work.is_relative_to(temporary):
            raise DataCopyFailure('fixture-unavailable')
        self.fixture = work/self.case
        self.fixture.mkdir(parents=True, exist_ok=False)
        self.source = create_synthetic_root(self.fixture/'legacy')
        self.target = create_synthetic_root(self.fixture/'private-target', installation_id=self.source.installation_id)
        root = self.source.path
        layout = replace(self.outer, settings_root=root, data_root=root/'data', cache_root=root/'cache-v1',
            work_root=root/'cache-v1/work', tool_root=root/'tools-v1', state_root=root/'probe-state',
            default_export_root=root/'exports')
        layout.state_root.mkdir()
        (layout.state_root/'synthetic-probe.json').write_text(
            json.dumps({'build_id': layout.build_id, 'synthetic': True}), encoding='utf-8')
        self.adapter = _FrozenAuthoredDataRuntime(layout, self.source.installation_id, self.observe,
            wal_probe=self.case == WAL_CASE, grammar_probe=self.case == GRAMMAR_CASE,
            grammar_checkpoint=self._grammar_stop_checkpoint if self.case == GRAMMAR_CASE else None)
        self.coordinator = _ProbeCoordinator(self.source, self.target, self.adapter)
        self.enter_attempted = True
        self.coordinator.__enter__()
        self.entered = True
        self.pointer = self.coordinator.pointer_path.read_bytes()
        self.adapter.setup_open = True
        try:
            self.expected = seed_authored(layout.data_root/'transcript-v2.db')
            if self.case == WAL_CASE:
                self.main_only_expected = json.loads(json.dumps(self.expected))
            (layout.data_root/'authored-payload.bin').write_bytes(AUTHORED_PAYLOAD)
        except BaseException as error:
            if isinstance(error, DataCopyFailure) and error.code == 'setup-close-unconfirmed':
                self.setup_failure = error
                self.adapter.poisoned = True
            raise
        finally:
            self.adapter.setup_open = False
        self.observe('setup-closed')

    def _guard_source_groups(self, baseline=None):
        for group in ('data', 'host-settings', 'work/voice-assets'):
            files = directories = sizes = None
            if baseline is not None:
                prefix = group+'/'
                files = {item['name'][len(prefix):] for item in baseline[0] if item['name'].startswith(prefix)}
                directories = {name[len(prefix):] for name in baseline[1] if name.startswith(prefix)}
                sizes = {item['name'][len(prefix):]: item['size'] for item in baseline[0] if item['name'].startswith(prefix)}
                if group == 'data':
                    files.add('companion-operation.lock')  # Metadata only; the core inventory skips the held lease.
            _guard_tree(self.source.path/group, missing=True, files=files, directories=directories, sizes=sizes)

    def _guard_wal_file_bounds(self):
        for name in DATABASE_VERSIONS:
            for suffix in ('', '-wal', '-shm'):
                info = _guard_path(self.source.path/(name+suffix), 'file', missing=True)
                if info is not None and info.st_size > WAL_FILE_BYTES:
                    raise DataCopyFailure('wal-set-unavailable')

    def _confirm_source_authority(self, plan, barrier, baseline, generation, leases):
        """Recheck actual authority on failure, never infer cause from a core code."""
        try:
            if self.adapter.poisoned:
                raise DataCopyFailure('cohort-unconfirmed')
            if self.case == GRAMMAR_CASE:
                self._confirm_grammar_payload()
            for root in (self.source.path, self.target.path):
                _guard_path(root, 'directory')
                if _guard_path(root/'.r19-synthetic-fixture.json', 'file').st_size > 4096:
                    raise DataCopyFailure('cohort-unconfirmed')
            self._guard_source_groups(baseline)
            _guard_path(self.source.path/'data/companion-operation.lock', 'file')
            _guard_path(self.target.path/'host-v1/migration-runtime.lock', 'file')
            barrier.check(self.source)
            barrier.check_target(self.target)
            if (self.adapter.write_generation() != generation or self.adapter.capture_running()
                    or leases != (self.coordinator._legacy_lease, self.coordinator._target_lease)
                    or self.coordinator.current is not self.adapter):
                raise DataCopyFailure('cohort-unconfirmed')
            if migration._source_inventory(plan) != baseline:
                raise DataCopyFailure('source-changed')
            self._pointer_unchanged()
        except BaseException:
            self.adapter.poisoned = True
            raise

    def _invoke_copy(self, plan, barrier, baseline, generation, leases, **options):
        try:
            return migration.copy_and_verify_synthetic(plan, barrier, **options)
        except BaseException as error:
            if self.case in {WAL_CASE, GRAMMAR_CASE}:
                # The unchanged helper also opens integrity-verification copies.
                # Its exception may mean failed close/cleanup, even while source
                # bytes still match. Keep the original private traceback/context
                # owner alive for the WAL and populated-grammar cases.
                self.core_copy_failure = error
                self.adapter.poisoned = True
                raise
            # Includes the exact planned sentinel. A target binding mismatch
            # can share a core error code with source change; inspect real state.
            self._confirm_source_authority(plan, barrier, baseline, generation, leases)
            raise

    def _validate_interrupted_copy(self, plan, barrier, baseline, generation, leases, first_name):
        """The trusted in-process plan/source grant authority, never manifest roots."""
        self._confirm_source_authority(plan, barrier, baseline, generation, leases)
        path = self.target.path/'migrations'/plan.migration_id/'manifest.json'
        _guard_path(path, 'file')
        def unique(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise DataCopyFailure('interrupted-copy-unconfirmed')
                value[key] = item
            return value
        with path.open('rb') as stream:
            raw = stream.read(1024*1024+1)
        if len(raw) > 1024*1024:
            raise DataCopyFailure('interrupted-copy-unconfirmed')
        manifest = json.loads(raw, object_pairs_hook=unique)
        binding = {'source_fixture_id': self.source.fixture_id, 'target_fixture_id': self.target.fixture_id,
            'inventory_sha256': migration._fingerprint(*baseline), 'database_versions': dict(DATABASE_VERSIONS),
            'external_inventory': [], 'named_account_store': 'unverified'}
        if (type(manifest) is not dict or manifest.get('schema') != 'proxy-storage-migration-v1'
                or manifest.get('migration_id') != plan.migration_id or manifest.get('binding') != binding
                or manifest.get('roots') != {'source': str(self.source.path), 'target': str(self.target.path)}
                or manifest.get('state') != 'failed' or manifest.get('activation_allowed') is not False
                or manifest.get('completed_files') != [first_name] or manifest.get('last_checkpoint') != first_name
                or manifest.get('failure') != _AuthoredCopyInterruption.__name__
                or manifest.get('inventory') != baseline[0]):
            raise DataCopyFailure('interrupted-copy-unconfirmed')
        completed = [item for item in baseline[0] if item['name'] == first_name]
        if len(completed) != 1:
            raise DataCopyFailure('interrupted-copy-unconfirmed')
        # Stricter than the core resume helper: this case refuses modified
        # partial bytes before retry rather than exercising its repair route.
        snapshot = self.target.path/'staging'/plan.migration_id
        _guard_snapshot(snapshot, completed, baseline[1])
        migration._verify_snapshot(snapshot, completed, baseline[1])
        self._confirm_source_authority(plan, barrier, baseline, generation, leases)
        self.partial_completed_files = 1
        self.partial_revalidations += 1
        self.same_plan_barrier_generation = True

    def _copy(self, plan, barrier, baseline):
        progress = False
        interrupted = self.case == RESUME_CASE
        sentinel = _AuthoredCopyInterruption()
        generation = self.adapter.write_generation()
        leases = (self.coordinator._legacy_lease, self.coordinator._target_lease)
        first_name = baseline[0][0]['name']
        def checkpoint(stage, name):
            nonlocal progress
            if stage == 'file-copied' and not progress:
                if interrupted and name != first_name:
                    raise DataCopyFailure('interrupted-copy-unconfirmed')
                progress = True
                self.observe('copy-progress')
                if interrupted:
                    raise sentinel
        self.copy_attempts += 1
        try:
            result = self._invoke_copy(plan, barrier, baseline, generation, leases, checkpoint=checkpoint)
        except _AuthoredCopyInterruption as error:
            if not interrupted or error is not sentinel or not progress:
                raise
            self.authored_interruptions = 1
            self._validate_interrupted_copy(plan, barrier, baseline, generation, leases, first_name)
            self.observe('copy-interrupted')
            # The independent source contender runs during this handshake;
            # revalidate again afterward, immediately before the second call.
            self._validate_interrupted_copy(plan, barrier, baseline, generation, leases, first_name)
            self.copy_attempts += 1
            result = self._invoke_copy(plan, barrier, baseline, generation, leases)
            self.copy_resumed = True
        if interrupted and not self.copy_resumed:
            raise DataCopyFailure('interrupted-copy-unconfirmed')
        return result, progress

    def _observe_wal_set(self, plan, barrier, baseline, generation, leases):
        self._confirm_source_authority(plan, barrier, baseline, generation, leases)
        files = {item['name']: item['size'] for item in baseline[0]}
        for name in DATABASE_VERSIONS:
            for suffix in ('', '-wal', '-shm'):
                if files.get(name+suffix, 0) > WAL_FILE_BYTES:
                    raise DataCopyFailure('wal-set-unavailable')
        name = 'data/transcript-v2.db'
        wal, shm = files.get(name+'-wal', 0), files.get(name+'-shm', 0)
        if wal <= 32 or shm <= 0:
            raise DataCopyFailure('wal-set-unavailable')
        verify_main_only_transcript(self.source.path/name, self.target.path, self.main_only_expected,
                                    self.verification_ownership)
        self.transcript_wal_bytes, self.transcript_shm_bytes = wal, shm
        self.wal_set_observed = True
        self.observe('wal-set-observed')
        self._confirm_source_authority(plan, barrier, baseline, generation, leases)

    def _read_grammar(self):
        return self.adapter.request(Request('http://127.0.0.1:8766/api/lines/1/reading',
            headers={'X-Proxy-Transcript-Account': 'legacy'}))

    @staticmethod
    def _check_grammar(value, *, known):
        if (type(value) is not dict or value.get('text') != GRAMMAR_TEXT
                or value.get('pendingMeanings') is not False or value.get('analysisPending') is not False
                or type(value.get('grammar')) is not list or len(value['grammar']) != 1):
            raise DataCopyFailure('grammar-choice-unconfirmed')
        rule = value['grammar'][0]
        expected = {'slug': GRAMMAR_SLUG, 'title': 'Owned fixture rule', 'subtitle': '', 'level': 'authored',
            'proficiency': 4 if known else 0, 'localOverride': known,
            'spans': [{'start': 0, 'end': 1}], 'examples': ['这']}
        if (type(rule) is not dict or rule != expected or type(rule['proficiency']) is not int
                or type(rule['localOverride']) is not bool
                or any(type(span['start']) is not int or type(span['end']) is not int for span in rule['spans'])):
            raise DataCopyFailure('grammar-choice-unconfirmed')

    def _write_grammar(self):
        if self.expected[0]['id'] != 1 or self.expected[0]['source_text'] != GRAMMAR_TEXT:
            raise DataCopyFailure('grammar-choice-unconfirmed')
        self._check_grammar(self._read_grammar(), known=False)
        self.grammar_baseline = True
        self.adapter.reject_unknown_grammar()
        self._check_grammar(self._read_grammar(), known=False)
        self.grammar_unknown_refused = True
        result = self.adapter.request(Request('http://127.0.0.1:8766/api/lines/1/reading/grammar',
            data=json.dumps({'slug': GRAMMAR_SLUG, 'known': True}).encode(), method='POST',
            headers={'Content-Type': 'application/json', 'X-Proxy-Transcript': 'lexirise',
                     'X-Proxy-Transcript-Account': 'legacy'}))
        if (type(result) is not dict or result != {'slug': GRAMMAR_SLUG, 'proficiency': 4, 'localOverride': True}
                or type(result['proficiency']) is not int or result['localOverride'] is not True):
            raise DataCopyFailure('grammar-choice-unconfirmed')
        self._check_grammar(self._read_grammar(), known=True)
        self.grammar_written = True
        self.grammar_ack_state = self._grammar_checkpoint()
        self.observe('grammar-written')
        self._grammar_checkpoint(self.grammar_ack_state)

    def _confirm_grammar_payload(self):
        # This file is authored immutable fixture input, not a live SQLite set.
        # Its known bytes never become authority for any database or writer.
        if (self.source is not self.coordinator.legacy or self.target is not self.coordinator.state
                or self.grammar_ack_state is not None and
                (self.coordinator is not self.grammar_ack_state['coordinator']
                 or self.source is not self.grammar_ack_state['source']
                 or self.target is not self.grammar_ack_state['target'])):
            raise DataCopyFailure('cohort-unconfirmed')
        state = self.grammar_ack_state
        if state is not None:
            coordinator = self.coordinator
            owned = tuple(coordinator._owned)
            leases = (coordinator._legacy_lease, coordinator._target_lease)
            generation = self.adapter.write_generation()
            if (coordinator.owner is not state['owner'] or coordinator.current is not state['current']
                    or self.adapter is not state['current'] or type(generation) is not int or generation != state['generation']
                    or len(owned) != len(state['owned'])
                    or any(current is not previous for current, previous in zip(owned, state['owned']))
                    or any(current is not previous for current, previous in zip(leases, state['leases']))
                    or not all(lease.held for lease in leases)):
                raise DataCopyFailure('cohort-unconfirmed')
        path = self.source.path/'data/authored-payload.bin'
        if _guard_path(path, 'file').st_size != len(AUTHORED_PAYLOAD):
            raise DataCopyFailure('source-changed')
        with path.open('rb') as stream:
            if stream.read(len(AUTHORED_PAYLOAD)+1) != AUTHORED_PAYLOAD:
                raise DataCopyFailure('source-changed')

    def _grammar_checkpoint(self, expected=None, *, writers_signaled=False):
        """Recheck the live pre-drain owner; this does not mint a copy barrier."""
        try:
            if type(writers_signaled) is not bool or writers_signaled and expected is None:
                raise DataCopyFailure('cohort-unconfirmed')
            coordinator = self.coordinator
            if expected is not None and coordinator is not expected['coordinator']:
                raise DataCopyFailure('cohort-unconfirmed')
            owner = expected['owner'] if expected is not None else coordinator.owner
            coordinator._require_owner(owner)
            self._confirm_grammar_payload()
            leases = (coordinator._legacy_lease, coordinator._target_lease)
            generation = self.adapter.write_generation()
            owned = tuple(coordinator._owned)
            if (coordinator.current is not self.adapter or len(owned) != 1 or owned[0] is not self.adapter
                    or self.adapter.poisoned or self.adapter.active is not (not writers_signaled) or self.adapter.setup_open
                    or type(generation) is not int or generation != 1 or coordinator._barrier is not None
                    or not all(lease.held for lease in leases)):
                raise DataCopyFailure('cohort-unconfirmed')
            if expected is not None and (coordinator.owner is not expected['owner']
                    or coordinator.current is not expected['current'] or generation != expected['generation']
                    or coordinator._barrier is not expected['barrier']
                    or len(owned) != len(expected['owned'])
                    or any(current is not previous for current, previous in zip(owned, expected['owned']))
                    or any(current is not previous for current, previous in zip(leases, expected['leases']))):
                raise DataCopyFailure('cohort-unconfirmed')
            return {'coordinator': coordinator, 'owner': owner, 'current': coordinator.current,
                'source': self.source, 'target': self.target, 'owned': owned, 'generation': generation,
                'barrier': coordinator._barrier, 'leases': leases}
        except BaseException:
            self.adapter.poisoned = True
            raise

    def _grammar_stop_checkpoint(self, phase):
        if phase not in {'strict-drain-complete', 'writers-signaled'} or self.grammar_ack_state is None:
            self.adapter.poisoned = True
            raise DataCopyFailure('cohort-unconfirmed')
        self._grammar_checkpoint(self.grammar_ack_state, writers_signaled=phase == 'writers-signaled')

    def exercise(self):
        self.adapter.start()
        first = self.expected[0]
        value = self.adapter.request(Request('http://127.0.0.1:8766/api/lines/'+str(first['id'])+'/favorite',
            data=b'{"favorite":true}', method='PATCH', headers={'Content-Type': 'application/json'}))
        first['favorite'] = True
        if _row(value) != first:
            raise DataCopyFailure('authored-rows-differ')
        self.observe('favorite-written')
        if self.case == GRAMMAR_CASE:
            self._write_grammar()
        plan = migration.SyntheticMigrationPlan(self.source, self.target, str(uuid.uuid4()),
            database_versions=DATABASE_VERSIONS)
        failure_source_confirmed = False
        try:
            with self.coordinator.stopped_writers(self.coordinator.owner) as barrier:
                try:
                    self._guard_source_groups()
                    if self.case == GRAMMAR_CASE:
                        self._confirm_grammar_payload()
                        barrier.check(self.source)
                        barrier.check_target(self.target)
                    if self.case == WAL_CASE:
                        self._guard_wal_file_bounds()
                    baseline = migration._source_inventory(plan)
                except BaseException:
                    self.adapter.poisoned = True
                    raise
                generation = self.adapter.write_generation()
                leases = (self.coordinator._legacy_lease, self.coordinator._target_lease)
                try:
                    if self.case == WAL_CASE:
                        self._observe_wal_set(plan, barrier, baseline, generation, leases)
                    result, progress = self._copy(plan, barrier, baseline)
                    if (result.get('state') != 'verified' or result.get('activation_allowed') is not False
                            or result.get('migration_acceptance') != 'incomplete' or not progress):
                        raise DataCopyFailure('copy-result-unconfirmed')
                    snapshot = self.target.path/'staging'/plan.migration_id
                    _guard_snapshot(snapshot, *baseline)
                    if self.case == GRAMMAR_CASE:
                        verify_authored_snapshot(snapshot, self.target.path, self.expected,
                            retained=self.verification_ownership, grammar_probe=True)
                        self.grammar_snapshot = True
                    elif self.case == WAL_CASE:
                        verify_authored_snapshot(snapshot, self.target.path, self.expected,
                                                 retained=self.verification_ownership)
                    else:
                        verify_authored_snapshot(snapshot, self.target.path, self.expected)
                    if self.case == WAL_CASE:
                        self.wal_dependency = True
                    self._confirm_source_authority(plan, barrier, baseline, generation, leases)
                    migration._verify_snapshot(snapshot, *baseline)
                    self.wal_files = sum((snapshot/name).with_name(Path(name).name+'-wal').is_file() for name in DATABASE_VERSIONS)
                    self.shm_files = sum((snapshot/name).with_name(Path(name).name+'-shm').is_file() for name in DATABASE_VERSIONS)
                    self.copy_verified = self.source_preserved = True
                    self.observe('copy-verified')
                    self._confirm_source_authority(plan, barrier, baseline, generation, leases)
                except BaseException:
                    if self.case in {WAL_CASE, GRAMMAR_CASE} and self.verification_ownership:
                        self.adapter.poisoned = True
                    if not self.adapter.poisoned:
                        self._confirm_source_authority(plan, barrier, baseline, generation, leases)
                        failure_source_confirmed = True
                    raise
        except BaseException:
            if not failure_source_confirmed:
                # Includes context exit/entry errors outside the guarded copy
                # body. A cleared barrier is not authority to close exclusion.
                self.adapter.poisoned = True
            raise
        try:
            barrier.check(self.source)
        except HostProbeError as error:
            if error.code != 'writer-barrier-required':
                raise
            self.old_barrier_refused = True
        else:
            raise DataCopyFailure('cohort-unconfirmed')
        rows = self.adapter.request('http://127.0.0.1:8766/api/lines?game=hito')
        if not isinstance(rows, list) or sorted((_row(row) for row in rows), key=lambda row: row['id']) != self.expected:
            raise DataCopyFailure('authored-rows-differ')
        self.logical_preserved = True
        if self.case == GRAMMAR_CASE:
            self._check_grammar(self._read_grammar(), known=True)
            self.grammar_restarted = True
        self.observe('source-resumed')
        self.adapter.quiesce()
        self._pointer_unchanged()
        self.phase = 'release'
        self.release_attempted = True
        try:
            self.coordinator.close(self.coordinator.owner)
        except BaseException:
            raise DataCopyFailure('lease-release-unconfirmed') from None
        self.released = True
        self._pointer_unchanged()
        self.emit('released')

    def run(self):
        try:
            self.prepare()
            self.exercise()
            return 0
        except BaseException as error:
            hold = ((self.enter_attempted and not self.entered)
                    or (self.release_attempted and not self.released))
            if self.adapter and self.adapter.capture_running():
                self.adapter.poisoned = True
                hold = True
            if isinstance(error, DataCopyFailure):
                code = error.code
            elif isinstance(error, HostProbeFailure):
                code = 'owned-host-unconfirmed'
            elif isinstance(error, HostProbeError):
                code = 'copy-refused'
            else:
                code = 'unexpected-data-copy-failure'
            if self.entered and not self.release_attempted:
                try:
                    failure = {
                        'schema': GRAMMAR_SCHEMA if self.case == GRAMMAR_CASE else WAL_SCHEMA if self.case == WAL_CASE else RESUME_SCHEMA if self.case == RESUME_CASE else SCHEMA,
                        'status': 'failed', 'failure': code, 'phase': self.phase,
                        'source_commit': self.outer.source_commit, 'build_id': self.outer.build_id,
                        'target_activation': False, 'r19_complete': False}
                    if self.case == RESUME_CASE:
                        failure.update(case=self.case, scope=RESUME_SCOPE)
                    if self.case == WAL_CASE:
                        failure.update(case=self.case, scope=WAL_SCOPE)
                    if self.case == GRAMMAR_CASE:
                        failure.update(case=self.case, scope=GRAMMAR_SCOPE)
                    failure_path = self.target.path/'host-v1/data-copy-failure.json'
                    _guard_path(failure_path.parent, 'directory')
                    _guard_path(failure_path, 'file', missing=True)
                    _atomic_json(failure_path, failure)
                except BaseException:
                    hold = True
            if self.entered and not self.released and not hold:
                try:
                    self.release_attempted = True
                    self.coordinator.close(self.coordinator.owner)
                    self.released = True
                except BaseException:
                    hold = True
            if hold and self.adapter:
                self.adapter.poisoned = True
            try:
                self.emit('recovery-required', failure=code)
            except BaseException:
                pass
            if hold:
                # Neither failed metadata output nor closed stdin may release
                # exclusion while writer/handle cleanup is unconfirmed.
                hold_keeper_recovery()
            return 2


def run(layout, stream, *, case=CASE):
    return _DataCopyProbe(layout, stream, case=case).run()
