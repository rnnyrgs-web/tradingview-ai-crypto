from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924081500_big_move_reference_append_guard.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _body(signature: str) -> str:
    sql = _sql()
    start = sql.index(signature)
    body_start = sql.index("as $$", start) + len("as $$")
    body_end = sql.index("$$;", body_start)
    return sql[body_start:body_end]


def test_reference_implementation_is_quarantined_from_application_roles():
    sql = _sql()
    assert (
        "alter function public.append_big_move_reference_observation_v1(text, text)\n"
        "  rename to append_big_move_reference_observation_v1_unguarded_784;"
    ) in sql
    assert (
        "revoke all on function public.append_big_move_reference_observation_v1_unguarded_784(text, text)\n"
        "  from public, anon, authenticated, service_role;"
    ) in sql


def test_reference_delegate_is_inside_function_definition_boundary():
    body = _body(
        "create or replace function public.assert_big_move_prospective_function_boundary_v1()"
    )
    assert "append_big_move_reference_observation_v1_unguarded_784(text,text)" in body
    for role in ("service_role", "authenticated", "anon"):
        assert f"has_function_privilege('{role}', v_fn, 'execute')" in body


def test_reference_wrapper_orders_all_guards_before_delegate():
    body = _body(
        "create or replace function public.append_big_move_reference_observation_v1("
    )
    lock_at = body.index(
        "perform public.acquire_big_move_prospective_relation_locks_v1();"
    )
    structural_at = body.index(
        "perform public.assert_big_move_prospective_schema_contract_v1();"
    )
    function_at = body.index(
        "perform public.assert_big_move_prospective_function_boundary_v1();"
    )
    delegate_at = body.index("append_big_move_reference_observation_v1_unguarded_784")
    assert lock_at < structural_at < function_at < delegate_at


def test_only_public_reference_wrapper_restores_service_role_execution():
    sql = _sql()
    assert (
        "grant execute on function public.append_big_move_reference_observation_v1(text, text)\n"
        "  to service_role;"
    ) in sql
    assert (
        "grant execute on function public.append_big_move_reference_observation_v1_unguarded_784"
        not in sql
    )
