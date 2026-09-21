from pathlib import Path


def test_forward_formation_store_rejects_stale_backdated_payloads():
    root = Path(__file__).parents[1]
    sql = (
        root
        / "supabase/migrations/20260921051500_big_move_forward_formations.sql"
    ).read_text(encoding="utf-8")

    assert "created_at timestamptz not null default clock_timestamp()" in sql
    assert "formation_payload ? 'formed_at'" in sql
    assert "formation_payload ? 'evidence_cutoff'" in sql
    assert "formation_payload ? 'reference_price_observed_at'" in sql
    assert "created_at - interval '5 minutes'" in sql
    assert "(formation_payload ->> 'formed_at')::timestamptz <= created_at" in sql
    assert "(formation_payload ->> 'reference_price_observed_at')::timestamptz <= created_at" in sql
    assert "grant insert (forecast_fingerprint, formation_payload)" in sql
    assert "grant insert (forecast_fingerprint, formation_payload, created_at)" not in sql
    assert "update public.big_move_forward_formations" not in sql.lower()
    assert "delete from public.big_move_forward_formations" not in sql.lower()
