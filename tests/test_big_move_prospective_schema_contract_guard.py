from pathlib import Path


MIGRATION = (
    Path(__file__).parents[1]
    / "supabase/migrations/20260924051000_big_move_prospective_schema_contract_guard.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _guard_body() -> str:
    sql = _sql()
    start = sql.index(
        "create or replace function public.assert_big_move_prospective_schema_contract_v1()"
    )
    body_start = sql.index("as $$", start) + len("as $$")
    body_end = sql.index("$$;", body_start)
    return sql[body_start:body_end]


def test_guard_is_live_structural_not_migration_timestamp_authority():
    sql = _sql().lower()
    body = _guard_body().lower()

    assert "schema_migrations" not in body
    assert "max(version" not in body
    assert "to_regclass('public.big_move_reference_observations')" in body
    assert "to_regclass('public.big_move_forward_formations')" in body
    assert "to_regclass('public.big_move_forward_outcome_observations')" in body
    assert "pg_catalog.pg_attribute" in body
    assert "pg_catalog.pg_constraint" in body
    assert "relrowsecurity" in body
    assert "pg_catalog.pg_trigger" in body
    assert "pg_catalog.pg_get_function_result" in body
    assert "pg_catalog.has_table_privilege" in body
    assert "migration chronology is diagnostic only" in sql


def test_guard_fails_closed_for_required_drift_classes():
    body = _guard_body()

    assert body.count("PROSPECTIVE_SCHEMA_CONTRACT_NOT_PROVEN") >= 15
    for blocker in (
        "outcome table missing/incompatible",
        "formation column contract drift",
        "required RLS disabled",
        "formation identity/linkage constraint missing",
        "outcome identity/linkage constraint missing",
        "formation append RPC missing/wrong signature",
        "outcome append RPC missing/wrong signature",
        "hit derive RPC missing/wrong signature",
        "outcome mutation-rejection trigger drift",
        "service_role table privilege drift",
    ):
        assert blocker in body


def test_guard_freezes_exact_authoritative_rpc_signatures_and_result_contracts():
    body = _guard_body().lower()

    assert "append_big_move_reference_observation_v1(text,text)" in body
    assert "append_big_move_forward_formation_v1(text,bigint,jsonb)" in body
    assert "append_big_move_forward_outcome_observation_v1(bigint)" in body
    assert "derive_big_move_forward_hit_evidence_v1(bigint)" in body
    assert "reference_observation_created_attimestampwithtimezone" in body
    assert "source_reference_observation_sequencebigint" in body
    assert "breach_observationjsonb" in body
    assert body.count("p.prosecdef") >= 4
    assert body.count("search_path=%") >= 4


def test_guard_requires_append_only_outcome_trigger_and_rpc_only_mutation_boundary():
    body = _guard_body().lower()

    assert "big_move_forward_outcome_observations_append_only" in body
    assert "t.tgtype = 27" in body
    assert "reject_big_move_forward_outcome_observation_mutation_v1()" in body
    assert "insert,update,delete,truncate" in body
    assert "not pg_catalog.has_table_privilege('service_role', v_ref, 'select')" in body
    assert "not pg_catalog.has_table_privilege('service_role', v_form, 'select')" in body
    assert "not pg_catalog.has_table_privilege('service_role', v_out, 'select')" in body


def test_guard_itself_is_read_only():
    body = _guard_body().lower()

    # Catalog reads, comparisons, and RAISE are allowed. The preflight itself must
    # never repair production or mutate truth tables.
    for mutation in (
        "insert into",
        "update public.",
        "delete from",
        "alter table",
        "create table",
        "drop table",
        "grant ",
        "revoke ",
    ):
        assert mutation not in body


def test_all_authoritative_formation_outcome_hit_entrypoints_are_guarded():
    sql = _sql().lower()

    assert "rename to append_big_move_forward_formation_v1_unguarded_784" in sql
    assert "rename to append_big_move_forward_outcome_observation_v1_unguarded_784" in sql
    assert "rename to derive_big_move_forward_hit_evidence_v1_unguarded_784" in sql
    assert sql.count("perform public.assert_big_move_prospective_schema_contract_v1();") == 3

    for internal in (
        "append_big_move_forward_formation_v1_unguarded_784(text, bigint, jsonb)",
        "append_big_move_forward_outcome_observation_v1_unguarded_784(bigint)",
        "derive_big_move_forward_hit_evidence_v1_unguarded_784(bigint)",
    ):
        marker = f"revoke all on function public.{internal}"
        assert marker in sql


def test_structurally_valid_schema_does_not_depend_on_migration_version_parity():
    body = _guard_body().lower()

    # This regression intentionally has no assertion about a deployment timestamp.
    # The guard's PASS path is simply reaching function end after the live structural
    # checks.  A later/different migration version therefore cannot grant or revoke
    # authority unless it actually changes the inspected contract.
    assert "supabase_migrations" not in body
    assert "schema_migrations" not in body
    assert "20260924032612" not in body
    assert "repair_missing_big_move_forward_outcome_observations" not in body
