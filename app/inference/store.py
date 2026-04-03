from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.domain.models import Decision


@dataclass(frozen=True)
class AssessmentEvent:
    event_id: str
    text: str
    risk_score: float
    decision: Decision
    reason: str
    detector_used: str
    created_at: datetime


class AssessmentEventStore:
    def __init__(self, database_url: str | None) -> None:
        self.database_url = database_url
        self._use_database = bool(database_url)
        if self._use_database:
            self._ensure_database_schema()

    def record_event(
        self,
        text: str,
        risk_score: float,
        decision: Decision,
        reason: str,
        detector_used: str,
    ) -> AssessmentEvent | None:
        if not self._use_database:
            return None

        event = AssessmentEvent(
            event_id=str(uuid4()),
            text=text,
            risk_score=risk_score,
            decision=decision,
            reason=reason,
            detector_used=detector_used,
            created_at=datetime.now(timezone.utc),
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO assess_events (
                    event_id,
                    text,
                    risk_score,
                    decision,
                    reason,
                    detector_used,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.event_id,
                    event.text,
                    event.risk_score,
                    event.decision.value,
                    event.reason,
                    event.detector_used,
                    event.created_at,
                ),
            )
            connection.commit()
        return event

    def list_events_for_day(self, target_day: date) -> list[AssessmentEvent]:
        return self.list_events_between(
            start=datetime.combine(target_day, time.min, tzinfo=timezone.utc),
            end=datetime.combine(target_day + timedelta(days=1), time.min, tzinfo=timezone.utc),
        )

    def list_events_between(self, start: datetime, end: datetime) -> list[AssessmentEvent]:
        if not self._use_database:
            return []
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    event_id,
                    text,
                    risk_score,
                    decision,
                    reason,
                    detector_used,
                    created_at
                FROM assess_events
                WHERE created_at >= %s AND created_at < %s
                ORDER BY created_at ASC
                """,
                (start, end),
            )
            rows = cursor.fetchall()
        return [self._deserialize_row(row) for row in rows]

    def _ensure_database_schema(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS assess_events (
                    event_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    risk_score DOUBLE PRECISION NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    detector_used TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.commit()

    def _deserialize_row(self, row: tuple[Any, ...]) -> AssessmentEvent:
        return AssessmentEvent(
            event_id=str(row[0]),
            text=str(row[1]),
            risk_score=float(row[2]),
            decision=Decision(str(row[3])),
            reason=str(row[4]),
            detector_used=str(row[5]),
            created_at=row[6],
        )

    def _connect(self) -> Any:
        if not self.database_url:
            raise ValueError("Assessment database URL is not configured")
        psycopg = _load_psycopg()
        return psycopg.connect(self.database_url)


def _load_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "psycopg is required for PostgreSQL-backed assessment storage. "
            "Install project dependencies with database support."
        ) from exc
    return psycopg
