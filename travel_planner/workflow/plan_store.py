"""Persistent storage of finished plans and of every approval decision.

Two small interfaces (Interface Segregation):
    TripPlanRepository - used by the facade (plan history) and the finalize step
    ApprovalAuditLog   - used by the human-approval step
One database class implements both, but each caller depends only on what it uses.

SqlPlanStore holds the SQL shared by SQLite and PostgreSQL; subclasses only
decide how a statement is executed on their database.
"""

import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from travel_planner.shared.exceptions import PersistenceError, ValidationError

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
BUDGET_VERDICTS = ("FEASIBLE", "TIGHT", "OVER_BUDGET", "UNKNOWN", "NOT_REQUESTED")


@dataclass(frozen=True)
class TripPlanRecord:
    plan_id: str
    thread_id: str
    user_id: str
    user_query: str
    destination: str
    approved: bool
    revision_count: int
    budget_verdict: str
    final_plan: str
    created_at: datetime

    def __post_init__(self):
        if not self.user_id.strip():
            raise ValidationError("A stored plan needs a user id")
        if not self.final_plan.strip():
            raise ValidationError("A stored plan cannot be empty")
        if self.revision_count < 0:
            raise ValidationError("revision_count cannot be negative")
        if self.budget_verdict not in BUDGET_VERDICTS:
            raise ValidationError(f"Unknown budget verdict '{self.budget_verdict}'")

    @classmethod
    def create(cls, thread_id, user_id, user_query, destination, approved, revision_count,
               budget_verdict, final_plan, created_at=None) -> "TripPlanRecord":
        """Create a new record with a fresh id and (by default) the current UTC time."""
        return cls(
            plan_id=str(uuid.uuid4()),
            thread_id=thread_id,
            user_id=user_id,
            user_query=user_query,
            destination=destination,
            approved=approved,
            revision_count=revision_count,
            budget_verdict=budget_verdict,
            final_plan=final_plan,
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class ApprovalEvent:
    event_id: str
    thread_id: str
    approved: bool
    feedback: str
    decided_at: datetime


# SOLID - ISP: plan history (TripPlanRepository) and approval decisions (ApprovalAuditLog)
# are two small interfaces; each client depends only on the one it uses.
class TripPlanRepository(ABC):
    @abstractmethod
    def save_plan(self, record: TripPlanRecord) -> None:
        """Store a finished plan."""

    @abstractmethod
    def plans_for_user(self, user_id: str, limit: int = 10) -> list[TripPlanRecord]:
        """Return the user's plans, newest first."""


class ApprovalAuditLog(ABC):
    @abstractmethod
    def record_decision(self, thread_id: str, approved: bool, feedback: str) -> None:
        """Store one human approval decision."""

    @abstractmethod
    def decisions_for_thread(self, thread_id: str) -> list[ApprovalEvent]:
        """Return all decisions for one planning session, oldest first."""


INSERT_PLAN = """
INSERT INTO trip_plans (plan_id, thread_id, user_id, user_query, destination, approved,
                        revision_count, budget_verdict, final_plan, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

SELECT_PLANS = """
SELECT plan_id, thread_id, user_id, user_query, destination, approved,
       revision_count, budget_verdict, final_plan, created_at
FROM trip_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT ?"""

INSERT_DECISION = """
INSERT INTO approval_events (event_id, thread_id, approved, feedback, decided_at)
VALUES (?, ?, ?, ?, ?)"""

SELECT_DECISIONS = """
SELECT event_id, thread_id, approved, feedback, decided_at
FROM approval_events WHERE thread_id = ? ORDER BY decided_at ASC"""


# SOLID - OCP: a new database is a new SqlPlanStore subclass; the SQL logic is not edited.
class SqlPlanStore(TripPlanRepository, ApprovalAuditLog):
    """Shared SQL logic. Statements use '?' placeholders."""

    def __init__(self):
        self._clock_lock = threading.Lock()
        self._last_time = None

    @abstractmethod
    def _run(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute one statement and return all result rows."""

    @abstractmethod
    def _run_script(self, script: str) -> None:
        """Execute several statements (used to create the schema)."""

    def create_schema(self) -> None:
        self._run_script(SCHEMA_FILE.read_text(encoding="utf-8"))

    def save_plan(self, record: TripPlanRecord) -> None:
        self._run(INSERT_PLAN, (
            record.plan_id, record.thread_id, record.user_id, record.user_query, record.destination,
            record.approved, record.revision_count, record.budget_verdict, record.final_plan,
            record.created_at.isoformat(),
        ))

    def plans_for_user(self, user_id: str, limit: int = 10) -> list[TripPlanRecord]:
        rows = self._run(SELECT_PLANS, (user_id, limit))
        records = []
        for row in rows:
            records.append(TripPlanRecord(
                plan_id=row[0], thread_id=row[1], user_id=row[2], user_query=row[3], destination=row[4],
                approved=bool(row[5]), revision_count=int(row[6]), budget_verdict=row[7],
                final_plan=row[8], created_at=datetime.fromisoformat(row[9]),
            ))
        return records

    def record_decision(self, thread_id: str, approved: bool, feedback: str) -> None:
        event_id = str(uuid.uuid4())
        decided_at = self._now().isoformat()
        self._run(INSERT_DECISION, (event_id, thread_id, approved, feedback, decided_at))

    def decisions_for_thread(self, thread_id: str) -> list[ApprovalEvent]:
        rows = self._run(SELECT_DECISIONS, (thread_id,))
        events = []
        for row in rows:
            events.append(ApprovalEvent(
                event_id=row[0], thread_id=row[1], approved=bool(row[2]), feedback=row[3],
                decided_at=datetime.fromisoformat(row[4]),
            ))
        return events

    def _now(self) -> datetime:
        # Two decisions in the same microsecond would sort randomly, so keep timestamps increasing.
        with self._clock_lock:
            now = datetime.now(timezone.utc)
            if self._last_time is not None and now <= self._last_time:
                now = self._last_time + timedelta(microseconds=1)
            self._last_time = now
            return now


# SOLID - LSP: SqlitePlanStore and PostgresPlanStore can replace each other.
class SqlitePlanStore(SqlPlanStore):
    """SQLite file database, used in sample mode and in tests.

    Thread safety: every operation opens its own connection (SQLite connections
    must not be shared between threads) and a lock lets one thread write at a time.
    """

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self._lock = threading.Lock()
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise PersistenceError("sqlite", f"cannot create folder for {path}: {error}") from error
        self.create_schema()

    def _run(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            try:
                connection = sqlite3.connect(self._path, timeout=10)
                try:
                    with connection:  # commits on success, rolls back on error
                        return connection.execute(sql, params).fetchall()
                finally:
                    connection.close()
            except sqlite3.Error as error:
                raise PersistenceError("sqlite", str(error)) from error

    def _run_script(self, script: str) -> None:
        with self._lock:
            try:
                connection = sqlite3.connect(self._path, timeout=10)
                try:
                    connection.executescript(script)
                finally:
                    connection.close()
            except sqlite3.Error as error:
                raise PersistenceError("sqlite", str(error)) from error
