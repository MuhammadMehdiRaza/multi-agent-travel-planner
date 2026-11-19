-- Persistent data layer of the travel planner.
-- Portable SQL: the same schema is used by SQLite (sample mode) and PostgreSQL (live mode).
-- Timestamps are stored as ISO-8601 UTC text so both databases sort them identically.
-- (LangGraph creates its own checkpoint tables for paused workflows separately.)

CREATE TABLE IF NOT EXISTS trip_plans (
    plan_id         VARCHAR(36)  PRIMARY KEY,
    thread_id       VARCHAR(100) NOT NULL,
    user_id         VARCHAR(100) NOT NULL,
    user_query      TEXT         NOT NULL,
    destination     VARCHAR(200) NOT NULL,
    approved        BOOLEAN      NOT NULL,
    revision_count  INTEGER      NOT NULL CHECK (revision_count >= 0),
    budget_verdict  VARCHAR(20)  NOT NULL
        CHECK (budget_verdict IN ('FEASIBLE', 'TIGHT', 'OVER_BUDGET', 'UNKNOWN', 'NOT_REQUESTED')),
    final_plan      TEXT         NOT NULL,
    created_at      VARCHAR(40)  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trip_plans_user ON trip_plans (user_id, created_at);

CREATE TABLE IF NOT EXISTS approval_events (
    event_id    VARCHAR(36)  PRIMARY KEY,
    thread_id   VARCHAR(100) NOT NULL,
    approved    BOOLEAN      NOT NULL,
    feedback    TEXT         NOT NULL,
    decided_at  VARCHAR(40)  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_events_thread ON approval_events (thread_id, decided_at);
