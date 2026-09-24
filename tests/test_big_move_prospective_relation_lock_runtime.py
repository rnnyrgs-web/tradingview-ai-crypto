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

RELATION_MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924065000_big_move_prospective_relation_lock_guard.sql"
)
DDL_MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924123000_big_move_prospective_ddl_advisory_guard.sql"
)

TABLES = (
    "big_move_reference_observations",
    "big_move_forward_formations",
    "big_move_forward_outcome_observations",
)


def _exact_function_sql(path: Path, signature: str) -> str:
    """Extract one exact behavior-bearing function from a reviewed migration."""
    sql = path.read_text(encoding="utf-8")
    start = sql.lower().index(signature.lower())
    end = sql.index("$$;", start) + len("$$;")
    return sql[start:end]


def _exact_relation_lock_helper_sql() -> str:
    return _exact_function_sql(
        RELATION_MIGRATION,
        "create or replace function public.acquire_big_move_prospective_relation_locks_v1()",
    )


def _exact_ddl_read_lock_helper_sql() -> str:
    return _exact_function_sql(
        DDL_MIGRATION,
        "create or replace function public.acquire_big_move_prospective_ddl_read_lock_v1()",
    )


def _exact_ddl_write_lock_helper_sql() -> str:
    return _exact_function_sql(
        DDL_MIGRATION,
        "create or replace function public.acquire_big_move_prospective_ddl_write_lock_v1()",
    )


def _reset_fixture() -> None:
    assert DSN is not None
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("drop function if exists public.toctou_function_probe()")
        conn.execute(
            "drop function if exists public.acquire_big_move_prospective_ddl_write_lock_v1()"
        )
        conn.execute(
            "drop function if exists public.acquire_big_move_prospective_ddl_read_lock_v1()"
        )
        conn.execute(
            "drop function if exists public.acquire_big_move_prospective_relation_locks_v1()"
        )
        for table in reversed(TABLES):
            conn.execute(f"drop table if exists public.{table} cascade")
        for table in TABLES:
            conn.execute(f"create table public.{table} (id bigint primary key)")
        conn.execute(_exact_relation_lock_helper_sql())
        conn.execute(_exact_ddl_read_lock_helper_sql())
        conn.execute(_exact_ddl_write_lock_helper_sql())


def _install_probe(value: str, conn) -> None:
    conn.execute(
        f"""
        create or replace function public.toctou_function_probe()
        returns text
        language sql
        security definer
        set search_path = ''
        as $$ select '{value}'::text $$
        """
    )


def test_relation_lock_barrier_blocks_concurrent_required_relation_ddl_until_tx_end():
    """Runtime falsifier for the relation-level check/use TOCTOU class."""
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


def test_authorized_function_ddl_and_authority_calls_serialize_both_directions():
    """Prove the reviewed shared-writer/exclusive-migration advisory protocol.

    An authority transaction holding the shared lock must block an authorized
    repository migration from acquiring the exclusive lock. After the authority
    transaction ends, the migration can obtain the exclusive lock and replace a
    function. While the migration lock is held, a new authority transaction must
    block rather than run against a half-migrated function set.
    """
    assert DSN is not None
    _reset_fixture()
    with psycopg.connect(DSN, autocommit=True) as setup:
        _install_probe("ORIGINAL", setup)

    with (
        psycopg.connect(DSN) as authority_a,
        psycopg.connect(DSN) as migration_b,
        psycopg.connect(DSN) as authority_c,
    ):
        authority_a.execute("select public.acquire_big_move_prospective_ddl_read_lock_v1()")
        authority_a.execute("select public.acquire_big_move_prospective_relation_locks_v1()")
        assert authority_a.execute("select public.toctou_function_probe()").fetchone()[0] == "ORIGINAL"

        migration_b.execute("set local lock_timeout = '500ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            migration_b.execute("select public.acquire_big_move_prospective_ddl_write_lock_v1()")
        migration_b.rollback()

        # No replacement occurred while the in-flight authority call was protected.
        with psycopg.connect(DSN, autocommit=True) as observer:
            assert observer.execute("select public.toctou_function_probe()").fetchone()[0] == "ORIGINAL"

        authority_a.commit()

        migration_b.execute("set local lock_timeout = '2s'")
        migration_b.execute("select public.acquire_big_move_prospective_ddl_write_lock_v1()")
        _install_probe("REPLACED", migration_b)

        authority_c.execute("set local lock_timeout = '500ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            authority_c.execute("select public.acquire_big_move_prospective_ddl_read_lock_v1()")
        authority_c.rollback()

        migration_b.commit()

        authority_c.execute("set local lock_timeout = '2s'")
        authority_c.execute("select public.acquire_big_move_prospective_ddl_read_lock_v1()")
        assert authority_c.execute("select public.toctou_function_probe()").fetchone()[0] == "REPLACED"
        authority_c.rollback()


def test_noncooperative_owner_ddl_is_explicit_trusted_root_not_self_defendable():
    """Keep the owner-bypass falsifier: the protocol only serializes authorized DDL.

    A same-owner CREATE OR REPLACE that intentionally ignores the exclusive advisory
    lock can still replace a function while an authority transaction holds the shared
    advisory + relation locks. That is not hidden or mislabeled as solved: it defines
    the explicit DB-owner/control-plane trust root. The SQL layer must never claim to
    defend against an owner that can also replace the guard and lock helpers.
    """
    assert DSN is not None
    _reset_fixture()
    with psycopg.connect(DSN, autocommit=True) as setup:
        _install_probe("ORIGINAL", setup)

    with psycopg.connect(DSN) as authority_a, psycopg.connect(DSN) as owner_bypass:
        authority_a.execute("select public.acquire_big_move_prospective_ddl_read_lock_v1()")
        authority_a.execute("select public.acquire_big_move_prospective_relation_locks_v1()")

        metadata_before = authority_a.execute(
            """
            select p.proowner, p.prosecdef, p.proconfig
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()
        source_before = authority_a.execute(
            """
            select p.prosrc
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()[0]

        # Deliberately ignore acquire_big_move_prospective_ddl_write_lock_v1().
        owner_bypass.execute("set local lock_timeout = '1s'")
        _install_probe("OWNER_BYPASS", owner_bypass)
        owner_bypass.commit()

        metadata_after = authority_a.execute(
            """
            select p.proowner, p.prosecdef, p.proconfig
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()
        source_after = authority_a.execute(
            """
            select p.prosrc
              from pg_catalog.pg_proc p
             where p.oid = to_regprocedure('public.toctou_function_probe()')
            """
        ).fetchone()[0]

        assert metadata_after == metadata_before
        assert source_after != source_before
        assert authority_a.execute("select public.toctou_function_probe()").fetchone()[0] == "OWNER_BYPASS"
        authority_a.rollback()
