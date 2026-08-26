"""SQLite 会话：近 12 轮用于续聊，全量落盘（含证据 ID）。重启不丢。"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CONV_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def new_conversation_id() -> str:
    return uuid.uuid4().hex


def normalize_conversation_id(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    if not _CONV_RE.match(text):
        return None
    return text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SqliteHistory:
    def __init__(self, db_path: str | Path, max_turns: int = 12):
        self.db_path = Path(db_path)
        self.max_turns = max(1, int(max_turns))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    request_id TEXT,
                    intent TEXT,
                    sources TEXT,
                    safety TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conv
                    ON messages(conversation_id, id);
                """
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
            if "extra" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN extra TEXT")

    def ensure(self, conversation_id: str) -> str:
        cid = normalize_conversation_id(conversation_id) or new_conversation_id()
        now = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (cid, now, now),
            )
        return cid

    def exists(self, conversation_id: str) -> bool:
        cid = normalize_conversation_id(conversation_id)
        if not cid:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (cid,),
            ).fetchone()
        return row is not None

    def append_turn(
        self,
        conversation_id: str,
        query: str,
        answer: str,
        *,
        request_id: str = "",
        intent: str | None = None,
        sources: list[dict[str, Any]] | None = None,
        safety: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        cid = self.ensure(conversation_id)
        now = _now()
        sources_json = json.dumps(sources or [], ensure_ascii=False)
        safety_json = json.dumps(safety or {}, ensure_ascii=False)
        extra_json = json.dumps(extra or {}, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, request_id, intent, sources, safety, extra, created_at)
                VALUES (?, 'user', ?, ?, NULL, NULL, NULL, NULL, ?)
                """,
                (cid, query, request_id or None, now),
            )
            conn.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, request_id, intent, sources, safety, extra, created_at)
                VALUES (?, 'assistant', ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, answer, request_id or None, intent, sources_json, safety_json, extra_json, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, cid),
            )

    def load_history(self, conversation_id: str) -> list[dict[str, str]]:
        """近 N 轮，只含 role/content，给续聊上下文。"""
        cid = normalize_conversation_id(conversation_id)
        if not cid:
            return []
        limit = self.max_turns * 2
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (cid, limit),
            ).fetchall()
        items = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        return items

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        cid = normalize_conversation_id(conversation_id)
        if not cid:
            return None
        with self._connect() as conn:
            head = conn.execute(
                "SELECT id, created_at, updated_at FROM conversations WHERE id = ?",
                (cid,),
            ).fetchone()
            if not head:
                return None
            rows = conn.execute(
                """
                SELECT role, content, request_id, intent, sources, safety, extra, created_at
                FROM messages WHERE conversation_id = ? ORDER BY id ASC
                """,
                (cid,),
            ).fetchall()
        messages = []
        for row in rows:
            item: dict[str, Any] = {
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            if row["request_id"]:
                item["request_id"] = row["request_id"]
            if row["intent"]:
                item["intent"] = row["intent"]
            if row["sources"]:
                item["sources"] = json.loads(row["sources"])
            if row["safety"]:
                item["safety"] = json.loads(row["safety"])
            if row["extra"]:
                extra = json.loads(row["extra"])
                if extra.get("department_candidates"):
                    item["department_candidates"] = extra["department_candidates"]
                if extra.get("elapsed_ms") is not None:
                    item["elapsed_ms"] = extra["elapsed_ms"]
            messages.append(item)
        return {
            "conversation_id": head["id"],
            "created_at": head["created_at"],
            "updated_at": head["updated_at"],
            "messages": messages,
        }

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.updated_at, c.created_at,
                       (
                         SELECT m.content FROM messages m
                         WHERE m.conversation_id = c.id AND m.role = 'user'
                         ORDER BY m.id DESC LIMIT 1
                       ) AS preview
                FROM conversations c
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [
            {
                "conversation_id": r["id"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "preview": (r["preview"] or "")[:80],
            }
            for r in rows
        ]
