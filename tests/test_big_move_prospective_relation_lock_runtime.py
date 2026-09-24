from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

DSN = os.environ.get("TOCTOU_PG_DSN")
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="runtime PostgreSQL falsifier requires TOCTOU_PG_DSN",
)

MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924065000_big_move_prospective_relation_lock_guard.sql"
)

TABLES = (
    "big_move_reference_observations",
    "big_move_forward_formations",
    "big_move_forward_outcome_observations",
)


def _exact_lock_helper_sql() -> str:
    """Extract the exact behavior-bearing lock helper from the reviewed migration."""
    sql = MIGRATION.read_text(encoding="utf-8")
    signature = (
        "create or replace function public.acquire_big_move_prospective_relation_locks_v1()"
    )
    start = sql.lower().index(signature)
    end = sql.index("$$;", start) + len("$$;")
    return sql[start:end]


def _reset_fixture() -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "drop function if exists public.acquire_big_move_prospective_relation_locks_v1()"
        )
        for table in reversed(TABLES):
            conn.execute(f"drop table if exists public.{table} cascade")
        for table in TABLES:
            conn.execute(f"create table public.{table} (id bigint primary key)")
        conn.execute(_exact_lock_helper_sql())


def test_relation_lock_barrier_blocks_concurrent_required_relation_ddl_until_tx_end():
    """Runtime RED->GREEN falsifier for the relation-level check/use TOCTOU class.

    The helper must retain SHARE ROW EXCLUSIVE locks after it returns. A second
    PostgreSQL session attempting authority-bearing relation DDL must therefore
    fail on lock timeout while session A's transaction is open, then succeed
    after session A ends. This uses the exact helper SQL from the migration rather
    than a hand-written approximation.
    """
    assert DSN is not None
    _reset_fixture()

    with psycopg.connect(DSN) as session_a, psycopg.connect(DSN) as session_b:
        session_a.execute("select public.acquire_big_move_prospective_relation_locks_v1()")

        held = session_a.execute(
            """
            select c.relname, l.mode, l.granted
              from pg_locks l
              join pg_class c on c.oid = l.relation
             where l.pid = pg_backend_pid()
               and c.relname = any(%s)
               and l.mode = 'ShareRowExclusiveLock'
             order by c.relname
            """,
            (list(TABLES),),
        ).fetchall()
        assert held == [
            (table, "ShareRowExclusiveLock", True) for table in sorted(TABLES)
        ]

        session_b.execute("set local lock_timeout = '500ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            session_b.execute(
                "alter table public.big_move_reference_observations "
                "add column drift_marker integer"
            )
        session_b.rollback()

        # The DDL was not applied while the reviewed lock barrier was held.
        with psycopg.connect(DSN, autocommit=True) as observer:
            drift_before_commit = observer.execute(
                """
                select count(*)
                  from information_schema.columns
                 where table_schema = 'public'
                   and table_name = 'big_move_reference_observations'
                   and column_name = 'drift_marker'
                """
            ).fetchone()[0]
        assert drift_before_commit == 0

        session_a.commit()

        # After the authority transaction ends, the same DDL can acquire its lock.
        session_b.execute("set local lock_timeout = '2s'")
        session_b.execute(
            "alter table public.big_move_reference_observations "
            "add column drift_marker integer"
        )
        session_b.commit()

    with psycopg.connect(DSN, autocommit=True) as observer:
        drift_after_commit = observer.execute(
            """
            select count(*)
              from information_schema.columns
             where table_schema = 'public'
               and table_name = 'big_move_reference_observations'
               and column_name = 'drift_marker'
            """
        ).fetchone()[0]
    assert drift_after_commit == 1
