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
        conn.execute("drop function if exists public.toctou_function_probe()")
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


def test_residual_function_definition_race_is_reproduced_and_remains_blocking():
    """Prove the separately documented pg_proc race is real, not hypothetical.

    #785's relation locks protect the truth tables, but they do not lock pg_proc.
    The current function-boundary guard validates owner, SECURITY DEFINER and an
    exact local search_path setting; it does not bind the function body. This
    falsifier shows a same-owner/same-security/same-search_path CREATE OR REPLACE
    can commit while the relation locks are held, after which the first session
    executes the replacement body. Until a separately reviewed mechanism closes
    this class, PROSPECTIVE_SCHEMA_FUNCTION_DEFINITION_TOCTOU_NOT_YET_PROVEN must
    remain a blocking state.
    """
    assert DSN is not None
    _reset_fixture()

    original_sql = """
        create or replace function public.toctou_function_probe()
        returns text
        language sql
        security definer
        set search_path = ''
        as $$ select 'ORIGINAL'::text $$
    """
    replacement_sql = """
        create or replace function public.toctou_function_probe()
        returns text
        language sql
        security definer
        set search_path = ''
        as $$ select 'REPLACED'::text $$
    """

    with psycopg.connect(DSN, autocommit=True) as setup:
        setup.execute(original_sql)

    with psycopg.connect(DSN) as session_a, psycopg.connect(DSN) as session_b:
        session_a.execute("select public.acquire_big_move_prospective_relation_locks_v1()")

        metadata_before = session_a.execute(
            """
            select p.proowner, p.prosecdef, p.proconfig
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()
        source_before = session_a.execute(
            """
            select p.prosrc
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()[0]
        assert session_a.execute("select public.toctou_function_probe()").fetchone()[0] == "ORIGINAL"

        # Relation locks must not be misrepresented as pg_proc serialization.
        session_b.execute("set local lock_timeout = '1s'")
        session_b.execute(replacement_sql)
        session_b.commit()

        metadata_after = session_a.execute(
            """
            select p.proowner, p.prosecdef, p.proconfig
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()
        source_after = session_a.execute(
            """
            select p.prosrc
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()[0]

        # These are the same metadata dimensions frozen by the current #785
        # function-boundary guard, so a body-only replacement is invisible to it.
        assert metadata_after == metadata_before
        assert source_after != source_before
        assert session_a.execute("select public.toctou_function_probe()").fetchone()[0] == "REPLACED"
        session_a.rollback()
