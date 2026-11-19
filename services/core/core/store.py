"""SQLite 저장소. 행마다 JSON 문서 1개. api와 mcp-server가 같은 파일을 공유한다 (plan.md ADR-7)."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  kind TEXT NOT NULL,
  id TEXT NOT NULL,
  parent TEXT,
  body TEXT NOT NULL,
  updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            c = sqlite3.connect(self.path, timeout=10)
            c.execute("PRAGMA journal_mode=WAL")
            try:
                yield c
                c.commit()
            finally:
                c.close()

    def next_id(self, prefix: str) -> str:
        with self._conn() as c:
            c.execute("INSERT INTO counters(name, value) VALUES(?, 1) ON CONFLICT(name) DO UPDATE SET value = value + 1",
                      (prefix,))
            (v,) = c.execute("SELECT value FROM counters WHERE name=?", (prefix,)).fetchone()
        return f"{prefix}_{v:03d}"

    def put(self, kind: str, id_: str, body: dict[str, Any], parent: str | None = None) -> dict[str, Any]:
        with self._conn() as c:
            c.execute(
                "INSERT INTO docs(kind, id, parent, body) VALUES(?,?,?,?) ON CONFLICT(kind, id) DO UPDATE SET "
                "body=excluded.body, parent=excluded.parent, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                (kind, id_, parent, json.dumps(body, ensure_ascii=False)),
            )
        return body

    def get(self, kind: str, id_: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT body FROM docs WHERE kind=? AND id=?", (kind, id_)).fetchone()
        return None if row is None else json.loads(row[0])

    def list(self, kind: str, parent: str | None = None) -> list[dict[str, Any]]:
        q, args = "SELECT body FROM docs WHERE kind=?", [kind]
        if parent is not None:
            q += " AND parent=?"
            args.append(parent)
        with self._conn() as c:
            rows = c.execute(q + " ORDER BY rowid", args).fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, kind: str, id_: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM docs WHERE kind=? AND id=?", (kind, id_))
        return cur.rowcount > 0
