from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924065000_big_move_prospective_relation_lock_guard.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _function_body(signature: str) -> str:
    sql = _sql()
    start = sql.index(signature)
    body_start = sql.index("as $$", start) + len("as $$")
    body_end = sql.index("$$;", body_start)
    return sql[body_start:body_end]


def test_lock_barrier_covers_all_authority_bearing_relations_with_strong_mode():
    body = _function_body(
        "create or replace function public.acquire_big_move_prospective_relation_locks_v1()"
    ).lower()

    assert "lock table" in body
    assert "public.big_move_reference_observations" in body
    assert "public.big_move_forward_formations" in body
    assert "public.big_move_forward_outcome_observations" in body
    assert "in share row exclusive mode;" in body
    assert "prospective_schema_contract_not_proven: relation lock target missing" in body


def test_lock_helper_is_not_directly_executable_by_application_roles():
    sql = _sql().lower()

    assert (
        "revoke all on function public.acquire_big_move_prospective_relation_locks_v1()\n"
        "  from public, anon, authenticated, service_role;"
    ) in sql
    assert (
        "grant execute on function public.acquire_big_move_prospective_relation_locks_v1()"
        not in sql
    )


def test_every_authoritative_wrapper_orders_lock_then_validate_then_use():
    wrappers = (
        (
            "create or replace function public.append_big_move_forward_formation_v1(",
            "append_big_move_forward_formation_v1_unguarded_784",
        ),
        (
            "create or replace function public.append_big_move_forward_outcome_observation_v1(",
            "append_big_move_forward_outcome_observation_v1_unguarded_784",
        ),
        (
            "create or replace function public.derive_big_move_forward_hit_evidence_v1(",
            "derive_big_move_forward_hit_evidence_v1_unguarded_784",
        ),
    )

    for signature, delegate in wrappers:
        body = _function_body(signature).lower()
        lock_at = body.index(
            "perform public.acquire_big_move_prospective_relation_locks_v1();"
        )
        validate_at = body.index(
            "perform public.assert_big_move_prospective_schema_contract_v1();"
        )
        use_at = body.index(delegate)
        assert lock_at < validate_at < use_at


def test_followup_does_not_weaken_public_service_role_surface():
    sql = _sql().lower()

    for signature in (
        "append_big_move_forward_formation_v1(text, bigint, jsonb)",
        "append_big_move_forward_outcome_observation_v1(bigint)",
        "derive_big_move_forward_hit_evidence_v1(bigint)",
    ):
        assert f"revoke all on function public.{signature}" in sql
        assert f"grant execute on function public.{signature}" in sql
        grant_at = sql.index(f"grant execute on function public.{signature}")
        assert "to service_role;" in sql[grant_at : grant_at + 180]


def test_relation_lock_repair_keeps_function_definition_race_explicitly_closed():
    sql = _sql()

    assert "PROSPECTIVE_SCHEMA_FUNCTION_DEFINITION_TOCTOU_NOT_YET_PROVEN" in sql
    assert "does NOT claim that relation locks freeze pg_proc" in sql


def test_followup_is_scope_bounded_to_lock_validate_use_reordering():
    sql = _sql().lower()

    # This migration may replace the wrappers but must not create/alter truth tables,
    # backfill evidence, open a candidate, or mutate broker/trading state.
    for forbidden in (
        "create table",
        "alter table",
        "drop table",
        "insert into public.big_move_",
        "update public.big_move_",
        "delete from public.big_move_",
    ):
        assert forbidden not in sql

    assert sql.count("perform public.acquire_big_move_prospective_relation_locks_v1();") == 3
    assert sql.count("perform public.assert_big_move_prospective_schema_contract_v1();") == 3
