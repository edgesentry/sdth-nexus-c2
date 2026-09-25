"""SQLite persistence for the in-memory C2 tactical picture (demo laptop).

Stores observations / finding / proposals / inbox so a process restart can
rehydrate ``C2Runtime``. Not gate authority — OCSF ``gate.jsonl`` remains the
cryptographic SoT for Approve/Ack seals.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from core.coa import CourseOfAction
from core.schema import Observation

logger = logging.getLogger(__name__)


def _dumps(data: Any) -> str:
    return json.dumps(data, default=str)


def _loads(text: str) -> Any:
    return json.loads(text)


class RuntimeStore:
    """Best-effort SQLite picture store (writes warn and continue on failure)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        except OSError as exc:
            logger.warning("runtime store open failed (%s): %s", self.path, exc)
            self._conn = None

    def _init_schema(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS finding (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposals (
                coa_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inbox (
                coa_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS acked (
                coa_id TEXT PRIMARY KEY
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def clear(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.executescript(
                """
                DELETE FROM meta;
                DELETE FROM observations;
                DELETE FROM finding;
                DELETE FROM proposals;
                DELETE FROM inbox;
                DELETE FROM acked;
                """
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store clear failed (%s): %s", self.path, exc)

    def set_meta(self, key: str, value: str | None) -> None:
        if self._conn is None:
            return
        try:
            if value is None:
                self._conn.execute("DELETE FROM meta WHERE key = ?", (key,))
            else:
                self._conn.execute(
                    "INSERT INTO meta(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store meta write failed: %s", exc)

    def get_meta(self, key: str) -> str | None:
        if self._conn is None:
            return None
        try:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return None if row is None else str(row["value"])
        except sqlite3.Error as exc:
            logger.warning("runtime store meta read failed: %s", exc)
            return None

    def upsert_observation(self, observation: Observation) -> None:
        if self._conn is None:
            return
        try:
            observation.ensure_digest()
            self._conn.execute(
                "INSERT INTO observations(observation_id, payload) VALUES(?, ?) "
                "ON CONFLICT(observation_id) DO UPDATE SET payload = excluded.payload",
                (observation.observation_id, _dumps(observation.model_dump(mode="json"))),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store observation write failed: %s", exc)

    def replace_observations(self, observations: list[Observation]) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM observations")
            for observation in observations:
                observation.ensure_digest()
                self._conn.execute(
                    "INSERT INTO observations(observation_id, payload) VALUES(?, ?)",
                    (
                        observation.observation_id,
                        _dumps(observation.model_dump(mode="json")),
                    ),
                )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store observations replace failed: %s", exc)

    def set_finding(self, finding_payload: dict[str, Any] | None) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM finding")
            if finding_payload is not None:
                self._conn.execute(
                    "INSERT INTO finding(id, payload) VALUES(1, ?)",
                    (_dumps(finding_payload),),
                )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store finding write failed: %s", exc)

    def upsert_proposal(self, coa_id: str, payload: dict[str, Any]) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT INTO proposals(coa_id, payload) VALUES(?, ?) "
                "ON CONFLICT(coa_id) DO UPDATE SET payload = excluded.payload",
                (coa_id, _dumps(payload)),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store proposal write failed: %s", exc)

    def delete_proposal(self, coa_id: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM proposals WHERE coa_id = ?", (coa_id,))
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store proposal delete failed: %s", exc)

    def upsert_inbox(self, coa_id: str, tasking: dict[str, Any]) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT INTO inbox(coa_id, payload) VALUES(?, ?) "
                "ON CONFLICT(coa_id) DO UPDATE SET payload = excluded.payload",
                (coa_id, _dumps(tasking)),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store inbox write failed: %s", exc)

    def add_acked(self, coa_id: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("INSERT OR IGNORE INTO acked(coa_id) VALUES(?)", (coa_id,))
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("runtime store acked write failed: %s", exc)

    def load_all(self) -> dict[str, Any]:
        """Return empty picture on any read failure.

        ``finding`` is a plain dict (app-layer ``Finding`` reconstructed by caller).
        ``proposals[*].coa`` is restored as ``CourseOfAction``.
        """
        empty: dict[str, Any] = {
            "scenario_id": None,
            "observations": [],
            "finding": None,
            "proposals": {},
            "inbox": {},
            "acked": set(),
        }
        if self._conn is None:
            return empty
        try:
            scenario_id = self.get_meta("scenario_id")
            obs_rows = self._conn.execute("SELECT payload FROM observations").fetchall()
            observations = [Observation.model_validate(_loads(row["payload"])) for row in obs_rows]
            finding_payload: dict[str, Any] | None = None
            finding_row = self._conn.execute("SELECT payload FROM finding WHERE id = 1").fetchone()
            if finding_row is not None:
                loaded = _loads(finding_row["payload"])
                if isinstance(loaded, dict):
                    finding_payload = loaded

            proposals: dict[str, dict[str, Any]] = {}
            for row in self._conn.execute("SELECT coa_id, payload FROM proposals"):
                raw = _loads(row["payload"])
                if not isinstance(raw, dict):
                    continue
                coa_raw = raw.get("coa")
                if isinstance(coa_raw, dict):
                    raw = {**raw, "coa": CourseOfAction.model_validate(coa_raw)}
                proposals[str(row["coa_id"])] = raw

            inbox: dict[str, dict[str, Any]] = {}
            for row in self._conn.execute("SELECT coa_id, payload FROM inbox"):
                payload = _loads(row["payload"])
                if isinstance(payload, dict):
                    inbox[str(row["coa_id"])] = payload

            acked = {str(row["coa_id"]) for row in self._conn.execute("SELECT coa_id FROM acked")}
            return {
                "scenario_id": scenario_id,
                "observations": observations,
                "finding": finding_payload,
                "proposals": proposals,
                "inbox": inbox,
                "acked": acked,
            }
        except (sqlite3.Error, TypeError, ValueError, KeyError) as exc:
            logger.warning("runtime store load failed (%s): %s", self.path, exc)
            return empty
