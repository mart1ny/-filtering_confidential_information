from pathlib import Path

import pandas as pd
import pytest

from app.domain.models import Decision, ReviewStatus
from app.review import store as review_store_module
from app.review.store import ReviewQueueStore


def test_review_store_creates_and_lists_pending_cases(tmp_path: Path) -> None:
    store = ReviewQueueStore(str(tmp_path))

    created = store.create_case(
        text="user@example.com",
        risk_score=0.55,
        detector_decision=Decision.REVIEW,
        reason="email_pattern",
    )

    pending = store.list_cases(status=ReviewStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].case_id == created.case_id
    assert pending[0].status == ReviewStatus.PENDING


def test_review_store_labels_case_and_exports_dataset(tmp_path: Path) -> None:
    store = ReviewQueueStore(str(tmp_path))
    case = store.create_case(
        text="user@example.com",
        risk_score=0.55,
        detector_decision=Decision.REVIEW,
        reason="email_pattern",
    )

    labeled = store.label_case(case.case_id, is_contains_confidential=1, reviewer="admin")
    export_path = store.export_labeled_dataset(str(tmp_path / "dataset.parquet"))

    assert labeled.status == ReviewStatus.LABELED
    frame = pd.read_parquet(export_path)
    assert frame["text"].tolist() == ["user@example.com"]
    assert frame["is_contains_confidential"].tolist() == [1]


def test_review_store_raises_for_unknown_case(tmp_path: Path) -> None:
    store = ReviewQueueStore(str(tmp_path))

    with pytest.raises(KeyError, match="Review case not found"):
        store.label_case("missing", is_contains_confidential=0)


def test_review_store_export_requires_labeled_cases(tmp_path: Path) -> None:
    store = ReviewQueueStore(str(tmp_path))

    with pytest.raises(ValueError, match="No labeled review cases available"):
        store.export_labeled_dataset(str(tmp_path / "dataset.parquet"))


def test_review_store_supports_postgres_backend(monkeypatch, tmp_path: Path) -> None:
    fake_module = _FakePsycopgModule()
    monkeypatch.setattr(review_store_module, "_load_psycopg", lambda: fake_module)

    store = ReviewQueueStore(
        storage_dir=str(tmp_path),
        database_url="postgresql://user:pass@db.example.com:5432/review",
    )
    case = store.create_case(
        text="passport 1234 567890",
        risk_score=0.91,
        detector_decision=Decision.REVIEW,
        reason="passport_pattern",
    )

    pending = store.list_cases(status=ReviewStatus.PENDING)
    labeled = store.label_case(case.case_id, is_contains_confidential=1, reviewer="admin")
    export_path = store.export_labeled_dataset(str(tmp_path / "dataset.parquet"))

    assert len(fake_module.connections) >= 1
    assert pending[0].case_id == case.case_id
    assert labeled.status == ReviewStatus.LABELED
    frame = pd.read_parquet(export_path)
    assert frame["text"].tolist() == ["passport 1234 567890"]
    assert frame["is_contains_confidential"].tolist() == [1]


class _FakePsycopgModule:
    def __init__(self) -> None:
        self.state = {"rows": {}}
        self.connections: list[_FakeConnection] = []

    def connect(self, _: str) -> "_FakeConnection":
        connection = _FakeConnection(self.state)
        self.connections.append(connection)
        return connection


class _FakeConnection:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state

    def cursor(self) -> "_FakeCursor":
        return _FakeCursor(self.state)

    def commit(self) -> None:
        return None

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeCursor:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state
        self._result: list[tuple[object, ...]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        rows = self.state["rows"]
        assert isinstance(rows, dict)
        compact_query = " ".join(query.split())
        if compact_query.startswith("CREATE TABLE IF NOT EXISTS review_cases"):
            self._result = []
            return
        if compact_query.startswith("INSERT INTO review_cases"):
            assert params is not None
            rows[str(params[0])] = (
                params[0],
                params[1],
                params[2],
                params[3],
                params[4],
                params[5],
                params[6],
                params[7],
                params[8],
                params[9],
                params[10],
            )
            self._result = []
            return
        if compact_query.startswith("SELECT"):
            sorted_rows = sorted(rows.values(), key=lambda row: row[9])
            if "WHERE status = %s" in compact_query:
                assert params is not None
                sorted_rows = [row for row in sorted_rows if row[5] == params[0]]
            self._result = list(sorted_rows)
            return
        if compact_query.startswith("UPDATE review_cases"):
            assert params is not None
            case_id = str(params[5])
            if case_id not in rows:
                self._result = []
                return
            current = rows[case_id]
            updated = (
                current[0],
                current[1],
                current[2],
                current[3],
                current[4],
                params[0],
                params[1],
                params[2],
                params[3],
                current[9],
                params[4],
            )
            rows[case_id] = updated
            self._result = [updated]
            return
        raise AssertionError(f"Unexpected query: {compact_query}")

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._result)

    def fetchone(self) -> tuple[object, ...] | None:
        if not self._result:
            return None
        return self._result[0]

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
