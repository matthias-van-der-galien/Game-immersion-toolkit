from __future__ import annotations

import sqlite3
import json
import math
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import TextMatch, TranscriptLine, is_comic_text_id
from .runtime_writers import RuntimeWriterGate


SCHEMA = """
CREATE TABLE IF NOT EXISTS transcript_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    session_id TEXT NOT NULL,
    game TEXT NOT NULL DEFAULT 'zzz',
    source_ocr TEXT NOT NULL,
    english TEXT NOT NULL,
    chinese TEXT NOT NULL,
    text_id TEXT NOT NULL,
    score REAL NOT NULL,
    match_kind TEXT NOT NULL,
    ambiguous INTEGER NOT NULL DEFAULT 0,
    channel TEXT NOT NULL DEFAULT 'dialogue',
    voiced INTEGER NOT NULL DEFAULT 0,
    audio_path TEXT,
    speaker_english TEXT,
    speaker_chinese TEXT,
    favorite INTEGER NOT NULL DEFAULT 0
)
"""


class TranscriptConnectionCloseError(RuntimeError):
    """Private failed-close ownership; never a store-detach or retry token."""
    def __init__(self, store, connection, body_error, transaction_error, close_error):
        super().__init__('Transcript connection cleanup is unconfirmed.')
        self.store, self.connection = store, connection
        self.body_error, self.transaction_error, self.close_error = body_error, transaction_error, close_error


class TranscriptStorePoisonedError(RuntimeError):
    def __init__(self, failure):
        super().__init__('Transcript store cleanup remains unconfirmed.')
        self.failure = failure


@dataclass(frozen=True, eq=False, repr=False)
class TranscriptConnectionFence:
    """One store's closed operation scopes; no copy or process authority."""
    _store: TranscriptStore
    _epoch: int

    def check(self, store):
        if not isinstance(store, TranscriptStore) or store is not self._store:
            raise ValueError('The transcript connection fence belongs to another store.')
        with store._connections_lock:
            store._check_connection_fence(self)


class TranscriptStore:
    def __init__(self, path: Path):
        self.path = path
        self._connection_failures = []  # Failed objects only; no successful connection registry.
        self._failure_lock = threading.Lock()
        self._connections_gate = RuntimeWriterGate()
        self._connections_lock = threading.Lock()
        self._connections_epoch = 0
        self._connections_fence = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection_scope(self):
        self._require_connections_clean()
        self._connections_gate.enter()
        try:
            self._require_connections_clean()
            with self._admitted_connection() as connection:
                yield connection
        finally:
            # Includes actual transaction exit, close, and failure publication.
            self._connections_gate.leave()

    def _require_connections_clean(self, deadline=None):
        # This lock protects failure ownership, not admission of active work.
        if deadline is None:
            self._failure_lock.acquire()
        else:
            self._acquire_connections_lock(self._failure_lock, deadline)
        try:
            if self._connection_failures:
                failure = self._connection_failures[0]
                raise TranscriptStorePoisonedError(failure) from failure
        finally:
            self._failure_lock.release()

    @contextmanager
    def _admitted_connection(self):
        connection = self._connect()
        body_error = transaction_error = None
        try:
            try:
                with connection:
                    try:
                        yield connection
                    except BaseException as error:
                        body_error = error
                        raise
            except BaseException as error:
                if error is not body_error:
                    transaction_error = error
                raise
        finally:
            try:
                connection.close()
            except BaseException as close_error:
                failure = TranscriptConnectionCloseError(self, connection, body_error, transaction_error, close_error)
                with self._failure_lock:
                    self._connection_failures.append(failure)
                cause = transaction_error if transaction_error is not None else body_error if body_error is not None else close_error
                raise failure from cause

    @staticmethod
    def _acquire_connections_lock(lock, deadline):
        remaining = min(threading.TIMEOUT_MAX, max(0.0, deadline-time.monotonic()))
        if not lock.acquire(timeout=remaining):
            raise TimeoutError('Transcript connection freeze has not finished.')

    def _check_connection_fence(self, fence):
        self._require_connections_clean()
        gate = self._connections_gate
        with gate._condition:
            if (type(fence) is not TranscriptConnectionFence or self._connections_fence is not fence
                    or fence._store is not self or fence._epoch != self._connections_epoch
                    or gate._accepting or gate._active):
                raise ValueError('The transcript connection fence is no longer current.')

    def freeze_connections(self, timeout):
        """Close SQL admission and await real close, using one total wait budget."""
        if type(timeout) not in {int, float}:
            raise ValueError('Transcript connection freeze requires a finite timeout.')
        try:
            duration = float(timeout)
        except OverflowError:
            raise ValueError('Transcript connection freeze requires a finite timeout.') from None
        if not math.isfinite(duration) or not 0 <= duration <= threading.TIMEOUT_MAX:
            raise ValueError('Transcript connection freeze requires a finite timeout.')
        deadline = time.monotonic()+duration
        self._acquire_connections_lock(self._connections_lock, deadline)
        try:
            self._require_connections_clean(deadline)
            gate = self._connections_gate
            self._acquire_connections_lock(gate._condition, deadline)
            try:
                gate.stop_admission()
            finally:
                gate._condition.release()
            while True:
                # Condition.wait reacquires its underlying RLock without a
                # timeout. Poll with bounded acquisition instead, so contention
                # after admission closes still uses this same total deadline.
                self._acquire_connections_lock(gate._condition, deadline)
                try:
                    if gate._accepting:
                        raise ValueError('Transcript connection admission reopened during freeze.')
                    if not gate._active:
                        self._require_connections_clean(deadline)
                        if duration and time.monotonic() > deadline:
                            raise TimeoutError('Transcript connection freeze has not finished.')
                        if self._connections_fence is None:
                            self._connections_fence = TranscriptConnectionFence(self, self._connections_epoch)
                        fence = self._connections_fence
                        if (type(fence) is not TranscriptConnectionFence or fence._store is not self
                                or fence._epoch != self._connections_epoch):
                            raise ValueError('The transcript connection fence is no longer current.')
                        return fence
                finally:
                    gate._condition.release()
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Transcript connection freeze has not finished.')
                time.sleep(min(.01, remaining))
        finally:
            self._connections_lock.release()

    def resume_connections(self, fence):
        """Invalidate the exact local token before admitting another operation."""
        with self._connections_lock:
            self._check_connection_fence(fence)
            self._connections_fence = None
            self._connections_epoch += 1
            self._connections_gate.resume()

    def _initialize(self) -> None:
        with self._connection_scope() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(SCHEMA)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(transcript_lines)")}
            if 'language_context' not in columns:
                connection.execute("ALTER TABLE transcript_lines ADD COLUMN language_context TEXT NOT NULL DEFAULT '{}'")
            if "channel" not in columns:
                connection.execute(
                    "ALTER TABLE transcript_lines ADD COLUMN channel TEXT NOT NULL DEFAULT 'dialogue'"
                )
            if "game" not in columns:
                connection.execute(
                    "ALTER TABLE transcript_lines ADD COLUMN game TEXT NOT NULL DEFAULT 'zzz'"
                )
            if "voiced" not in columns:
                connection.execute(
                    "ALTER TABLE transcript_lines ADD COLUMN voiced INTEGER NOT NULL DEFAULT 0"
                )
            if "audio_path" not in columns:
                connection.execute("ALTER TABLE transcript_lines ADD COLUMN audio_path TEXT")
            if "favorite" not in columns:
                connection.execute(
                    "ALTER TABLE transcript_lines ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
                )
            if "speaker_english" not in columns:
                connection.execute("ALTER TABLE transcript_lines ADD COLUMN speaker_english TEXT")
            if "speaker_chinese" not in columns:
                connection.execute("ALTER TABLE transcript_lines ADD COLUMN speaker_chinese TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_transcript_created_at "
                "ON transcript_lines(created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_transcript_session_id_created_at "
                "ON transcript_lines(session_id, created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_transcript_favorites_id "
                "ON transcript_lines(id DESC) WHERE favorite = 1"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_hito_identity "
                "ON transcript_lines(game, text_id) WHERE game = 'hito'"
            )
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _row_to_line(row: sqlite3.Row) -> TranscriptLine:
        return TranscriptLine(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            session_id=row["session_id"],
            game=row["game"],
            source_ocr=row["source_ocr"],
            english=row["english"],
            chinese=row["chinese"],
            text_id=row["text_id"],
            score=row["score"],
            match_kind=row["match_kind"],
            ambiguous=bool(row["ambiguous"]),
            channel=row["channel"],
            voiced=bool(row["voiced"]),
            has_audio=bool(row["audio_path"]),
            audio_source="original" if not row["audio_path"] or row["audio_path"].startswith("official-") else "recording",
            speaker_english=row["speaker_english"],
            speaker_chinese=row["speaker_chinese"],
            favorite=bool(row["favorite"]),
            **json.loads(row['language_context']),
        )

    def add(
        self,
        match: TextMatch,
        session_id: str,
        created_at: datetime | None = None,
        channel: str = "dialogue",
    ) -> TranscriptLine:
        timestamp = created_at or datetime.now(timezone.utc).astimezone()
        with self._connection_scope() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transcript_lines (
                    created_at, session_id, game, source_ocr, english, chinese,
                    text_id, score, match_kind, ambiguous, channel, voiced, audio_path,
                    speaker_english, speaker_chinese, favorite, language_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp.isoformat(),
                    session_id,
                    match.game,
                    match.source_ocr,
                    match.english,
                    match.chinese,
                    match.text_id,
                    match.score,
                    match.kind,
                    int(match.ambiguous),
                    channel,
                    0,
                    None,
                    match.speaker_english,
                    match.speaker_chinese,
                    0,
                    json.dumps({key: getattr(match, key) for key in ('source_language', 'source_locale',
                        'source_text', 'translation_locale', 'translation_text', 'audio_locale', 'texts',
                        'voice_status', 'dialogue_kind')}, ensure_ascii=False),
                ),
            )
            row = connection.execute(
                "SELECT * FROM transcript_lines WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._row_to_line(row)

    @staticmethod
    def _prefix_text(value: str) -> str:
        return "".join(character.casefold() for character in value if character.isalnum())

    def add_or_touch_hito(
        self,
        match: TextMatch,
        session_id: str,
        created_at: datetime | None = None,
        channel: str = "dialogue",
    ) -> TranscriptLine:
        if match.game != "hito":
            raise ValueError("Hito identity handling requires a Hito match")
        timestamp = created_at or datetime.now(timezone.utc).astimezone()
        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO transcript_lines (
                    created_at, session_id, game, source_ocr, english, chinese,
                    text_id, score, match_kind, ambiguous, channel
                ) VALUES (?, ?, 'hito', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game, text_id) WHERE game = 'hito' DO UPDATE SET
                    created_at = excluded.created_at, session_id = excluded.session_id,
                    source_ocr = excluded.source_ocr, english = excluded.english,
                    chinese = excluded.chinese, score = excluded.score,
                    match_kind = excluded.match_kind, ambiguous = excluded.ambiguous,
                    channel = excluded.channel
                """,
                (
                    timestamp.isoformat(), session_id, match.source_ocr, match.english,
                    match.chinese, match.text_id, match.score, match.kind,
                    int(match.ambiguous), channel,
                ),
            )
            row = connection.execute(
                "SELECT * FROM transcript_lines WHERE game = 'hito' AND text_id = ?",
                (match.text_id,),
            ).fetchone()
        return self._row_to_line(row)

    def add_or_upgrade_recent(
        self,
        match: TextMatch,
        session_id: str,
        created_at: datetime | None = None,
        channel: str = "dialogue",
        cooldown_seconds: float = 180.0,
        upgrade_seconds: float = 5.0,
        fragment_seconds: float = 30.0,
        adjacent_seconds: float = 20.0,
    ) -> tuple[TranscriptLine | None, bool]:
        """Store a line, or upgrade a just-captured prefix to its complete form.

        This database check complements the in-memory capture cooldown and keeps
        duplicates out even when two OCR regions race or the companion restarts
        while a subtitle is still visible.
        """
        timestamp = created_at or datetime.now(timezone.utc).astimezone()
        if match.source_locale != 'zh-Hans':
            with self._connection_scope() as connection:
                duplicate = connection.execute("""SELECT 1 FROM transcript_lines
                    WHERE game=? AND text_id=? AND json_extract(language_context, '$.source_locale')=?
                    AND json_extract(language_context, '$.source_text')=? AND datetime(created_at)>=datetime(?) LIMIT 1""",
                    (match.game, match.text_id, match.source_locale, match.source_text,
                     (timestamp-timedelta(seconds=max(0.0,cooldown_seconds))).isoformat())).fetchone()
            if duplicate:
                return None, False
            return self.add(match, session_id, created_at=timestamp, channel=channel), False
        cutoff = timestamp - timedelta(seconds=max(0.0, cooldown_seconds))
        is_comic = match.game == "zzz" and channel == "cinematic" and is_comic_text_id(match.text_id)
        with self._connection_scope() as connection:
            adjacent_cutoff = timestamp - timedelta(seconds=max(0.0, adjacent_seconds))
            adjacent = connection.execute(
                """
                SELECT * FROM transcript_lines
                WHERE game = ? AND COALESCE(json_extract(language_context, '$.source_locale'), 'zh-Hans')='zh-Hans' AND datetime(created_at) >= datetime(?)
                ORDER BY id DESC LIMIT 1
                """,
                (match.game, adjacent_cutoff.isoformat()),
            ).fetchone()
            if (
                adjacent
                and not (is_comic or self._row_to_line(adjacent).is_comic)
                and self._prefix_text(adjacent["english"]) == self._prefix_text(match.english)
            ):
                return None, False

            duplicate = connection.execute(
                """
                SELECT 1 FROM transcript_lines
                WHERE text_id = ? AND english = ?
                  AND game = ? AND COALESCE(json_extract(language_context, '$.source_locale'), 'zh-Hans')='zh-Hans'
                  AND datetime(created_at) >= datetime(?)
                LIMIT 1
                """,
                (match.text_id, match.english, match.game, cutoff.isoformat()),
            ).fetchone()
            if duplicate:
                return None, False

            fragment_cutoff = timestamp - timedelta(seconds=max(0.0, fragment_seconds))
            recent_rows = connection.execute(
                """
                SELECT * FROM transcript_lines
                WHERE game = ? AND COALESCE(json_extract(language_context, '$.source_locale'), 'zh-Hans')='zh-Hans' AND datetime(created_at) >= datetime(?)
                ORDER BY id DESC LIMIT 8
                """,
                (match.game, fragment_cutoff.isoformat()),
            ).fetchall()
            incoming_text = self._prefix_text(match.english)
            for recent in recent_rows:
                # Each official comic ID is already a complete utterance.
                # Similar wording in another bubble is not an OCR fragment.
                if is_comic or self._row_to_line(recent).is_comic:
                    continue
                recent_text = self._prefix_text(recent["english"])
                if (
                    len(incoming_text) >= 4
                    and len(incoming_text) + 8 <= len(recent_text)
                    and incoming_text in recent_text
                ):
                    return None, False

            upgrade_cutoff = timestamp - timedelta(seconds=max(0.0, upgrade_seconds))
            previous = connection.execute(
                """
                SELECT * FROM transcript_lines
                WHERE session_id = ? AND game = ? AND COALESCE(json_extract(language_context, '$.source_locale'), 'zh-Hans')='zh-Hans' AND datetime(created_at) >= datetime(?)
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, match.game, upgrade_cutoff.isoformat()),
            ).fetchone()
            if previous and not (is_comic or self._row_to_line(previous).is_comic):
                previous_text = self._prefix_text(previous["english"])
                complete_text = self._prefix_text(match.english)
                is_completion = (
                    len(previous_text) >= 8
                    and len(complete_text) >= len(previous_text) + 10
                    and previous_text in complete_text
                )
                if is_completion:
                    connection.execute(
                        """
                        UPDATE transcript_lines
                        SET source_ocr = ?, english = ?, chinese = ?, text_id = ?,
                            score = ?, match_kind = ?, ambiguous = ?, channel = ?,
                            speaker_english = ?, speaker_chinese = ?,
                            voiced = 0, audio_path = NULL, language_context = ?
                        WHERE id = ?
                        """,
                        (
                            match.source_ocr,
                            match.english,
                            match.chinese,
                            match.text_id,
                            match.score,
                            match.kind,
                            int(match.ambiguous),
                            channel,
                            match.speaker_english,
                            match.speaker_chinese,
                            json.dumps({key: getattr(match, key) for key in ('source_language', 'source_locale',
                                'source_text', 'translation_locale', 'translation_text', 'audio_locale', 'texts',
                                'voice_status', 'dialogue_kind')}, ensure_ascii=False),
                            previous["id"],
                        ),
                    )
                    row = connection.execute(
                        "SELECT * FROM transcript_lines WHERE id = ?", (previous["id"],)
                    ).fetchone()
                    return self._row_to_line(row), True

        return self.add(match, session_id, created_at=timestamp, channel=channel), False

    def get(self, line_id: int) -> TranscriptLine | None:
        with self._connection_scope() as connection:
            row = connection.execute(
                "SELECT * FROM transcript_lines WHERE id = ?", (line_id,)
            ).fetchone()
        return self._row_to_line(row) if row else None

    def update_audio(self, line_id: int, audio_path: str | None, voiced: bool) -> TranscriptLine | None:
        with self._connection_scope() as connection:
            connection.execute(
                "UPDATE transcript_lines SET audio_path = ?, voiced = ? WHERE id = ?",
                (audio_path, int(voiced), line_id),
            )
            row = connection.execute(
                "SELECT * FROM transcript_lines WHERE id = ?", (line_id,)
            ).fetchone()
        return self._row_to_line(row) if row else None

    def set_favorite(self, line_id: int, favorite: bool) -> TranscriptLine | None:
        with self._connection_scope() as connection:
            connection.execute(
                "UPDATE transcript_lines SET favorite = ? WHERE id = ?",
                (int(favorite), line_id),
            )
            row = connection.execute(
                "SELECT * FROM transcript_lines WHERE id = ?", (line_id,)
            ).fetchone()
        return self._row_to_line(row) if row else None

    def update_speaker(
        self,
        line_id: int,
        speaker_english: str | None,
        speaker_chinese: str | None,
    ) -> TranscriptLine | None:
        with self._connection_scope() as connection:
            connection.execute(
                "UPDATE transcript_lines SET speaker_english = ?, speaker_chinese = ? WHERE id = ?",
                (speaker_english, speaker_chinese, line_id),
            )
            row = connection.execute(
                "SELECT * FROM transcript_lines WHERE id = ?", (line_id,)
            ).fetchone()
        return self._row_to_line(row) if row else None

    def delete(self, line_id: int) -> str | None:
        with self._connection_scope() as connection:
            row = connection.execute(
                "SELECT audio_path FROM transcript_lines WHERE id = ?", (line_id,)
            ).fetchone()
            connection.execute("DELETE FROM transcript_lines WHERE id = ?", (line_id,))
        return str(row["audio_path"]) if row and row["audio_path"] else None

    def prune(self, keep_nonfavorite: int = 50) -> list[tuple[int, str | None]]:
        """Keep favorites plus the newest non-favorites for each supported game."""
        keep_nonfavorite = max(0, keep_nonfavorite)
        with self._connection_scope() as connection:
            rows = []
            games = [row[0] for row in connection.execute("SELECT DISTINCT game FROM transcript_lines")]
            for game in games:
                if game == "hito":
                    continue
                rows.extend(connection.execute(
                    """
                    SELECT id, audio_path FROM transcript_lines
                    WHERE favorite = 0 AND game = ?
                    ORDER BY id DESC LIMIT -1 OFFSET ?
                    """,
                    (game, keep_nonfavorite),
                ).fetchall())
            if rows:
                connection.executemany(
                    "DELETE FROM transcript_lines WHERE id = ?",
                    [(row["id"],) for row in rows],
                )
        return [
            (int(row["id"]), str(row["audio_path"]) if row["audio_path"] else None)
            for row in rows
        ]

    def purge_unvoiced(self) -> list[tuple[int, str | None]]:
        """Keep favorites, confirmed voices and certified unvoiced dialogue."""
        with self._connection_scope() as connection:
            rows = connection.execute(
                """
                SELECT * FROM transcript_lines
                WHERE game <> 'hito' AND voiced = 0 AND favorite = 0
                """
            ).fetchall()
            rows = [row for row in rows if not (self._row_to_line(row).is_comic
                                               or self._row_to_line(row).voice_status == 'unvoiced')]
            if rows:
                connection.executemany(
                    "DELETE FROM transcript_lines WHERE id = ?",
                    [(row["id"],) for row in rows],
                )
        return [
            (int(row["id"]), str(row["audio_path"]) if row["audio_path"] else None)
            for row in rows
        ]

    def audio_path(self, line_id: int) -> str | None:
        with self._connection_scope() as connection:
            row = connection.execute(
                "SELECT audio_path FROM transcript_lines WHERE id = ?", (line_id,)
            ).fetchone()
        return str(row["audio_path"]) if row and row["audio_path"] else None

    def list(
        self, limit: int = 250, before_id: int | None = None, game: str | None = None
    ) -> list[TranscriptLine]:
        limit = max(1, min(limit, 1000))
        query = "SELECT * FROM transcript_lines"
        parameters: list[object] = []
        conditions: list[str] = []
        if before_id is not None:
            conditions.append("id < ?")
            parameters.append(before_id)
        if game is not None:
            conditions.append("game = ?")
            parameters.append(game)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY julianday(created_at) DESC, id DESC LIMIT ?"
        parameters.append(limit)
        with self._connection_scope() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_line(row) for row in rows]

    def list_favorites(self, game: str | None = None) -> list[TranscriptLine]:
        """Return every saved favorite, newest first."""
        with self._connection_scope() as connection:
            query = "SELECT * FROM transcript_lines WHERE favorite = 1"
            parameters: list[object] = []
            if game is not None:
                query += " AND game = ?"
                parameters.append(game)
            query += " ORDER BY julianday(created_at) DESC, id DESC"
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_line(row) for row in rows]

    def count(self, session_id: str | None = None, game: str | None = None) -> int:
        with self._connection_scope() as connection:
            query = "SELECT COUNT(*) AS total FROM transcript_lines"
            conditions: list[str] = []
            parameters: list[object] = []
            if session_id:
                conditions.append("session_id = ?")
                parameters.append(session_id)
            if game:
                conditions.append("game = ?")
                parameters.append(game)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            row = connection.execute(query, parameters).fetchone()
        return int(row["total"])
