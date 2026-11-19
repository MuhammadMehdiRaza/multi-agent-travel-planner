"""PostgreSQL implementation of the plan store (live mode).

Thread safety: connections come from a psycopg ConnectionPool, which is safe
to share between threads; each operation borrows its own connection. (The
prototype shared ONE raw connection between all Streamlit sessions.)
"""

import psycopg

from travel_planner.shared.exceptions import PersistenceError
from travel_planner.workflow.plan_store import SqlPlanStore


# SOLID - LSP: same behaviour as SqlitePlanStore, so the workflow works with either store.
class PostgresPlanStore(SqlPlanStore):
    def __init__(self, pool):
        super().__init__()
        self._pool = pool
        self.create_schema()

    def _run(self, sql: str, params: tuple = ()) -> list[tuple]:
        try:
            with self._pool.connection() as connection:
                cursor = connection.execute(sql.replace("?", "%s"), params)
                if cursor.description is None:  # INSERT / CREATE return no rows
                    return []
                rows = cursor.fetchall()
        except psycopg.Error as error:
            raise PersistenceError("postgres", str(error)) from error
        # The shared pool returns rows as dicts (LangGraph needs that); convert them to tuples.
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(tuple(row.values()))
            else:
                result.append(tuple(row))
        return result

    def _run_script(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self._run(statement)
