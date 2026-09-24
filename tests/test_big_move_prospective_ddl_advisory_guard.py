from __future__ import annotations

from pathlib import Path

MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
MIGRATION_NAME = "20260924123000_big_move_prospective_ddl_advisory_guard.sql"
MIGRATION = MIGRATIONS / MIGRATION_NAME
LOCK_KEY = "6628152387724455858"

AUTHORITY_FUNCTIONS = (
    "acquire_big_move_prospective_ddl_read_lock_v1",
    "acquire_big_move_prospective_ddl_write_lock_v1",
    "assert_big_move_prospective_schema_contract_v1",
    "acquire_big_move_prospective_relation_locks_v1",
    "assert_big_move_prospective_function_boundary_v1",
    "append_big_move_reference_observation_v1",
    "append_big_move_forward_formation_v1",
    "append_big_move_forward_outcome_observation_v1",
    "derive_big_move_forward_hit_evidence_v1",
    "reject_big_move_forward_outcome_observation_mutation_v1",
)

PUBLIC_WRAPPERS = (
    "append_big_move_reference_observation_v1",
    "append_big_move_forward_formation_v1",
    "append_big_move_forward_outcome_observation_v1",
    "derive_big_move_forward_hit_evidence_v1",
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _function_body(sql: str, function_name: str) -> str:
    marker = f"create or replace function public.{function_name}("
    start = sql.lower().index(marker.lower())
    end = sql.index("$$;", start) + len("$$;")
    return sql[start:end]


def test_bootstrap_drains_pre_protocol_writers_before_exclusive_advisory_lock():
    sql = _sql().lower()
    relation_lock = sql.index("lock table")
    exclusive_lock = sql.index(f"pg_catalog.pg_advisory_xact_lock({LOCK_KEY})")
    first_wrapper = sql.index(
        "create or replace function public.append_big_move_reference_observation_v1("
    )
    assert relation_lock < exclusive_lock < first_wrapper
    assert "in share row exclusive mode" in sql[relation_lock:exclusive_lock]


def test_fixed_shared_and_exclusive_helpers_use_the_same_frozen_key():
    sql = _sql()
    shared = _function_body(sql, "acquire_big_move_prospective_ddl_read_lock_v1")
    exclusive = _function_body(sql, "acquire_big_move_prospective_ddl_write_lock_v1")
    assert f"pg_catalog.pg_advisory_xact_lock_shared({LOCK_KEY})" in shared
    assert f"pg_catalog.pg_advisory_xact_lock({LOCK_KEY})" in exclusive

    for helper in (
        "public.acquire_big_move_prospective_ddl_read_lock_v1()",
        "public.acquire_big_move_prospective_ddl_write_lock_v1()",
    ):
        revoke = f"revoke all on function {helper}\n  from public, anon, authenticated, service_role;"
        assert revoke in sql


def test_every_public_authority_wrapper_takes_shared_ddl_lock_first():
    sql = _sql()
    for wrapper in PUBLIC_WRAPPERS:
        body = _function_body(sql, wrapper)
        shared = body.index("perform public.acquire_big_move_prospective_ddl_read_lock_v1();")
        relation = body.index("perform public.acquire_big_move_prospective_relation_locks_v1();")
        schema = body.index("perform public.assert_big_move_prospective_schema_contract_v1();")
        function = body.index("perform public.assert_big_move_prospective_function_boundary_v1();")
        assert shared < relation < schema < function


def test_function_boundary_authenticates_both_advisory_helpers():
    sql = _sql()
    boundary = _function_body(sql, "assert_big_move_prospective_function_boundary_v1")
    assert "public.acquire_big_move_prospective_ddl_read_lock_v1()" in boundary
    assert "public.acquire_big_move_prospective_ddl_write_lock_v1()" in boundary
    assert "pg_catalog.has_function_privilege('service_role', v_fn, 'EXECUTE')" in boundary
    assert "pg_catalog.has_function_privilege('authenticated', v_fn, 'EXECUTE')" in boundary
    assert "pg_catalog.has_function_privilege('anon', v_fn, 'EXECUTE')" in boundary


def test_future_repository_migrations_touching_authority_surface_must_take_exclusive_lock():
    """Make the trusted migration protocol mechanically enforceable in-repository.

    This cannot defend against intentional owner/admin SQL outside the repository;
    that is the explicitly frozen trusted-root boundary. But any later committed
    migration that creates/replaces/alters/drops an authority-bearing function must
    opt into the reviewed exclusive advisory-lock protocol before DDL.
    """
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name <= MIGRATION_NAME:
            continue
        sql = path.read_text(encoding="utf-8").lower()
        authority_ddl = False
        for name in AUTHORITY_FUNCTIONS:
            target = f"function public.{name.lower()}"
            if target in sql and any(
                verb in sql
                for verb in (
                    f"create or replace {target}",
                    f"alter {target}",
                    f"drop {target}",
                )
            ):
                authority_ddl = True
                break
        if authority_ddl:
            assert (
                "select public.acquire_big_move_prospective_ddl_write_lock_v1();" in sql
                or f"pg_catalog.pg_advisory_xact_lock({LOCK_KEY})" in sql
            ), f"{path.name} changes prospective authority functions without exclusive DDL lock"
