from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from app.domain.models import Decision, ReviewCase, ReviewStatus


class ReviewQueueStore:
    def __init__(self, storage_dir: str, database_url: str | None = None) -> None:
        self.storage_dir = Path(storage_dir)
        self.database_url = database_url
        self._use_database = bool(database_url)
        if self._use_database:
            self.storage_file = None
            self._ensure_database_schema()
            return
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage_file = self.storage_dir / "review_cases.jsonl"

    def create_case(
        self, text: str, risk_score: float, detector_decision: Decision, reason: str
    ) -> ReviewCase:
        case = ReviewCase(
            case_id=str(uuid4()),
            text=text,
            risk_score=risk_score,
            detector_decision=detector_decision,
            reason=reason,
            status=ReviewStatus.PENDING,
            is_contains_confidential=None,
            reviewer=None,
            note=None,
            created_at=datetime.now(timezone.utc),
            reviewed_at=None,
        )
        if self._use_database:
            self._insert_case(case)
            return case
        assert self.storage_file is not None
        with self.storage_file.open("a", encoding="utf-8") as output:
            output.write(json.dumps(self._serialize_case(case), ensure_ascii=True) + "\n")
        return case

    def list_cases(self, status: ReviewStatus | None = None) -> list[ReviewCase]:
        if self._use_database:
            return self._list_cases_from_database(status=status)
        cases = [self._deserialize_case(payload) for payload in self._read_payloads()]
        if status is None:
            return cases
        return [case for case in cases if case.status == status]

    def label_case(
        self,
        case_id: str,
        is_contains_confidential: int,
        reviewer: str | None = None,
        note: str | None = None,
    ) -> ReviewCase:
        if self._use_database:
            return self._label_case_in_database(
                case_id=case_id,
                is_contains_confidential=is_contains_confidential,
                reviewer=reviewer,
                note=note,
            )
        cases = self.list_cases()
        updated_case: ReviewCase | None = None
        rewritten_cases: list[ReviewCase] = []
        for case in cases:
            if case.case_id == case_id:
                updated_case = replace(
                    case,
                    status=ReviewStatus.LABELED,
                    is_contains_confidential=is_contains_confidential,
                    reviewer=reviewer,
                    note=note,
                    reviewed_at=datetime.now(timezone.utc),
                )
                rewritten_cases.append(updated_case)
                continue
            rewritten_cases.append(case)
        if updated_case is None:
            raise KeyError(f"Review case not found: {case_id}")
        self._write_cases(rewritten_cases)
        return updated_case

    def export_labeled_dataset(self, output_path: str) -> Path:
        labeled_cases = self.list_cases(status=ReviewStatus.LABELED)
        if not labeled_cases:
            raise ValueError("No labeled review cases available for dataset export")

        frame = pd.DataFrame(
            [
                {
                    "id": case.case_id,
                    "text": case.text,
                    "source": "admin_review",
                    "conversation": case.case_id,
                    "prompt_lang": "unknown",
                    "answer_lang": "unknown",
                    "is_contains_confidential": int(case.is_contains_confidential or 0),
                }
                for case in labeled_cases
            ]
        )
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(target, index=False)
        return target

    def _ensure_database_schema(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS review_cases (
                    case_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    risk_score DOUBLE PRECISION NOT NULL,
                    detector_decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_contains_confidential SMALLINT NULL,
                    reviewer TEXT NULL,
                    note TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    reviewed_at TIMESTAMPTZ NULL
                )
                """
            )
            connection.commit()

    def _insert_case(self, case: ReviewCase) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO review_cases (
                    case_id,
                    text,
                    risk_score,
                    detector_decision,
                    reason,
                    status,
                    is_contains_confidential,
                    reviewer,
                    note,
                    created_at,
                    reviewed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    case.case_id,
                    case.text,
                    case.risk_score,
                    case.detector_decision.value,
                    case.reason,
                    case.status.value,
                    case.is_contains_confidential,
                    case.reviewer,
                    case.note,
                    case.created_at,
                    case.reviewed_at,
                ),
            )
            connection.commit()

    def _list_cases_from_database(self, status: ReviewStatus | None = None) -> list[ReviewCase]:
        query = """
            SELECT
                case_id,
                text,
                risk_score,
                detector_decision,
                reason,
                status,
                is_contains_confidential,
                reviewer,
                note,
                created_at,
                reviewed_at
            FROM review_cases
        """
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status = %s"
            params = (status.value,)
        query += " ORDER BY created_at ASC"
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [self._deserialize_row(row) for row in rows]

    def _label_case_in_database(
        self,
        case_id: str,
        is_contains_confidential: int,
        reviewer: str | None,
        note: str | None,
    ) -> ReviewCase:
        reviewed_at = datetime.now(timezone.utc)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE review_cases
                SET status = %s,
                    is_contains_confidential = %s,
                    reviewer = %s,
                    note = %s,
                    reviewed_at = %s
                WHERE case_id = %s
                RETURNING
                    case_id,
                    text,
                    risk_score,
                    detector_decision,
                    reason,
                    status,
                    is_contains_confidential,
                    reviewer,
                    note,
                    created_at,
                    reviewed_at
                """,
                (
                    ReviewStatus.LABELED.value,
                    is_contains_confidential,
                    reviewer,
                    note,
                    reviewed_at,
                    case_id,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise KeyError(f"Review case not found: {case_id}")
        return self._deserialize_row(row)

    def _connect(self) -> Any:
        if not self.database_url:
            raise ValueError("Review database URL is not configured")
        psycopg = _load_psycopg()
        return psycopg.connect(self.database_url)

    def _read_payloads(self) -> list[dict[str, object]]:
        if self.storage_file is None or not self.storage_file.exists():
            return []
        with self.storage_file.open("r", encoding="utf-8") as source:
            return [json.loads(line) for line in source if line.strip()]

    def _write_cases(self, cases: list[ReviewCase]) -> None:
        assert self.storage_file is not None
        with self.storage_file.open("w", encoding="utf-8") as output:
            for case in cases:
                output.write(json.dumps(self._serialize_case(case), ensure_ascii=True) + "\n")

    def _serialize_case(self, case: ReviewCase) -> dict[str, object]:
        payload = asdict(case)
        payload["detector_decision"] = case.detector_decision.value
        payload["status"] = case.status.value
        payload["created_at"] = case.created_at.isoformat()
        payload["reviewed_at"] = case.reviewed_at.isoformat() if case.reviewed_at else None
        return payload

    def _deserialize_case(self, payload: dict[str, object]) -> ReviewCase:
        return ReviewCase(
            case_id=str(payload["case_id"]),
            text=str(payload["text"]),
            risk_score=float(payload["risk_score"]),
            detector_decision=Decision(str(payload["detector_decision"])),
            reason=str(payload["reason"]),
            status=ReviewStatus(str(payload["status"])),
            is_contains_confidential=(
                int(payload["is_contains_confidential"])
                if payload["is_contains_confidential"] is not None
                else None
            ),
            reviewer=str(payload["reviewer"]) if payload["reviewer"] is not None else None,
            note=str(payload["note"]) if payload["note"] is not None else None,
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            reviewed_at=(
                datetime.fromisoformat(str(payload["reviewed_at"]))
                if payload["reviewed_at"] is not None
                else None
            ),
        )

    def _deserialize_row(self, row: tuple[Any, ...]) -> ReviewCase:
        created_at = row[9]
        reviewed_at = row[10]
        return ReviewCase(
            case_id=str(row[0]),
            text=str(row[1]),
            risk_score=float(row[2]),
            detector_decision=Decision(str(row[3])),
            reason=str(row[4]),
            status=ReviewStatus(str(row[5])),
            is_contains_confidential=int(row[6]) if row[6] is not None else None,
            reviewer=str(row[7]) if row[7] is not None else None,
            note=str(row[8]) if row[8] is not None else None,
            created_at=created_at,
            reviewed_at=reviewed_at,
        )


def _load_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised only in misconfigured runtime
        raise RuntimeError(
            "psycopg is required for PostgreSQL-backed review storage. "
            "Install project dependencies with database support."
        ) from exc
    return psycopg
