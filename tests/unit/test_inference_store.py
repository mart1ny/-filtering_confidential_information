from datetime import date

from app.domain.models import Decision
from app.inference import store as inference_store_module
from app.inference.store import AssessmentEventStore


def test_assessment_store_records_and_reads_events(monkeypatch) -> None:
    fake_module = _FakePsycopgModule()
    monkeypatch.setattr(inference_store_module, "_load_psycopg", lambda: fake_module)

    store = AssessmentEventStore(database_url="postgresql://user:pass@db.example.com:5432/app")
    created = store.record_event(
        text="passport 1234 567890",
        risk_score=0.91,
        decision=Decision.BLOCK,
        reason="passport_pattern",
        detector_used="hybrid",
    )

    assert created is not None
    same_day = store.list_events_for_day(created.created_at.date())
    assert len(same_day) == 1
    assert same_day[0].text == "passport 1234 567890"
    assert same_day[0].detector_used == "hybrid"


def test_assessment_store_is_noop_without_database() -> None:
    store = AssessmentEventStore(database_url=None)
    assert (
        store.record_event(
            text="hello",
            risk_score=0.1,
            decision=Decision.ALLOW,
            reason="bert_risk_low",
            detector_used="bert",
        )
        is None
    )
    assert store.list_events_for_day(date(2026, 4, 3)) == []


class _FakePsycopgModule:
    def __init__(self) -> None:
        self.state = {"rows": {}}

    def connect(self, _: str) -> "_FakeConnection":
        return _FakeConnection(self.state)


class _FakeConnection:
    def __init__(self, state) -> None:
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
    def __init__(self, state) -> None:
        self.state = state
        self._result = []

    def execute(self, query: str, params=None) -> None:
        rows = self.state["rows"]
        compact_query = " ".join(query.split())
        if compact_query.startswith("CREATE TABLE IF NOT EXISTS assess_events"):
            self._result = []
            return
        if compact_query.startswith("INSERT INTO assess_events"):
            rows[str(params[0])] = tuple(params)
            self._result = []
            return
        if compact_query.startswith("SELECT"):
            start, end = params
            self._result = [row for row in rows.values() if row[6] >= start and row[6] < end]
            return
        raise AssertionError(f"Unexpected query: {compact_query}")

    def fetchall(self):
        return list(self._result)

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
