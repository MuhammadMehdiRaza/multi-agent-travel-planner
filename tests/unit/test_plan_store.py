import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from travel_planner.shared.exceptions import PersistenceError, ValidationError
from travel_planner.workflow.plan_store import SqlitePlanStore, TripPlanRecord
from travel_planner.workflow.postgres_store import PostgresPlanStore

START = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def make_record(user_id="mehdi", minutes=0, **changes):
    values = dict(
        thread_id="t-1", user_id=user_id, user_query="Japan trip", destination="Japan",
        approved=True, revision_count=0, budget_verdict="OVER_BUDGET", final_plan="Day 1 ...",
        created_at=START + timedelta(minutes=minutes),
    )
    values.update(changes)
    return TripPlanRecord.create(**values)


class FakePostgresPool:
    """Stands in for psycopg_pool.ConnectionPool: hands out connections that accept %s placeholders.

    PostgresPlanStore can then run the same contract tests as SqlitePlanStore without a PostgreSQL server
    (the real server is checked by the live smoke test).
    """

    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()

    @contextmanager
    def connection(self):
        with self._lock:  # psycopg's pool gives each thread its own connection; one at a time is enough here
            connection = sqlite3.connect(self._path)
            try:
                yield FakePostgresConnection(connection)
                connection.commit()
            finally:
                connection.close()


class FakePostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        return self._connection.execute(sql.replace("%s", "?"), params)


# LSP: both plan stores must pass exactly the same tests.
@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path):
    path = str(tmp_path / "plans.sqlite3")
    if request.param == "sqlite":
        return SqlitePlanStore(path)
    return PostgresPlanStore(FakePostgresPool(path))


def test_saved_plan_can_be_read_back(store):
    record = make_record()
    store.save_plan(record)
    assert store.plans_for_user("mehdi") == [record]


def test_plans_are_newest_first_and_limited(store):
    for minute in range(5):
        store.save_plan(make_record(minutes=minute, final_plan=f"plan {minute}"))
    plans = store.plans_for_user("mehdi", limit=3)
    assert [plan.final_plan for plan in plans] == ["plan 4", "plan 3", "plan 2"]


def test_users_only_see_their_own_plans(store):
    store.save_plan(make_record(user_id="owais"))
    assert store.plans_for_user("mehdi") == []


def test_data_survives_a_new_store_instance(tmp_path):
    path = str(tmp_path / "plans.sqlite3")
    SqlitePlanStore(path).save_plan(make_record())
    assert len(SqlitePlanStore(path).plans_for_user("mehdi")) == 1


def test_approval_decisions_are_audited_in_order(store):
    store.record_decision("t-1", approved=False, feedback="cheaper hotels")
    store.record_decision("t-1", approved=True, feedback="")
    store.record_decision("t-2", approved=True, feedback="")
    events = store.decisions_for_thread("t-1")
    assert [(event.approved, event.feedback) for event in events] == [(False, "cheaper hotels"), (True, "")]


def test_concurrent_saves_from_many_threads_are_all_stored(store):
    def save(index):
        store.save_plan(make_record(minutes=index, final_plan=f"plan {index}"))

    threads = [threading.Thread(target=save, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(store.plans_for_user("mehdi", limit=100)) == 20


@pytest.mark.parametrize(
    "changes",
    [{"user_id": ""}, {"final_plan": "  "}, {"revision_count": -1}, {"budget_verdict": "MAYBE"}],
)
def test_invalid_records_are_rejected(changes):
    with pytest.raises(ValidationError):
        make_record(**changes)


def test_database_failure_raises_persistence_error(tmp_path):
    with pytest.raises(PersistenceError):
        SqlitePlanStore(str(tmp_path))  # a directory, not a database file
