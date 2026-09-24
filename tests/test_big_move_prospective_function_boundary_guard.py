from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924071500_big_move_prospective_function_boundary_guard.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _body(signature: str) -> str:
    sql = _sql()
    start = sql.index(signature)
    body_start = sql.index("as $$", start) + len("as $$")
    body_end = sql.index("$$;", body_start)
    return sql[body_start:body_end]


def test_function_boundary_requires_exact_empty_search_path_and_common_owner():
    body = _body(
        "create or replace function public.assert_big_move_prospective_function_boundary_v1()"
    ).lower()

    assert "v_owner is distinct from v_expected_owner" in body
    assert "not coalesce(v_security_definer, false)" in body
    assert "array_length(v_config, 1), 0) <> 1" in body
    assert "v_config[1] is distinct from 'search_path=\"\"'" in body
    assert "owner/security/search_path drift" in body


def test_function_boundary_covers_public_authority_and_quarantined_delegates():
    body = _body(
        "create or replace function public.assert_big_move_prospective_function_boundary_v1()"
    ).lower()

    required = (
        "assert_big_move_prospective_schema_contract_v1()",
        "acquire_big_move_prospective_relation_locks_v1()",
        "assert_big_move_prospective_function_boundary_v1()",
        "append_big_move_reference_observation_v1(text,text)",
        "append_big_move_forward_formation_v1(text,bigint,jsonb)",
        "append_big_move_forward_outcome_observation_v1(bigint)",
        "derive_big_move_forward_hit_evidence_v1(bigint)",
        "reject_big_move_forward_outcome_observation_mutation_v1()",
        "append_big_move_forward_formation_v1_unguarded_784(text,bigint,jsonb)",
        "append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)",
        "derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)",
    )
    for signature in required:
        assert signature in body


def test_all_ordinary_application_roles_remain_unable_to_execute_delegates():
    body = _body(
        "create or replace function public.assert_big_move_prospective_function_boundary_v1()"
    ).lower()

    for role in ("service_role", "authenticated", "anon"):
        assert f"has_function_privilege('{role}', v_fn, 'execute')" in body
    assert "delegate execution boundary drift" in body


def test_wrappers_order_relation_lock_then_both_preflights_then_delegate():
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
        body = _body(signature).lower()
        lock_at = body.index(
            "perform public.acquire_big_move_prospective_relation_locks_v1();"
        )
        structural_at = body.index(
            "perform public.assert_big_move_prospective_schema_contract_v1();"
        )
        function_at = body.index(
            "perform public.assert_big_move_prospective_function_boundary_v1();"
        )
        delegate_at = body.index(delegate)
        assert lock_at < structural_at < function_at < delegate_at


def test_helper_itself_is_not_an_application_callable_bypass():
    sql = _sql().lower()
    assert (
        "revoke all on function public.assert_big_move_prospective_function_boundary_v1()\n"
        "  from public, anon, authenticated, service_role;"
    ) in sql
    assert (
        "grant execute on function public.assert_big_move_prospective_function_boundary_v1()"
        not in sql
    )


def test_concurrent_trusted_owner_function_replacement_is_not_overclaimed():
    sql = _sql()
    assert "PROSPECTIVE_SCHEMA_FUNCTION_DEFINITION_TOCTOU_NOT_YET_PROVEN" in sql
    assert "does not claim to serialize a" in sql
    assert "concurrent CREATE OR REPLACE FUNCTION" in sql
