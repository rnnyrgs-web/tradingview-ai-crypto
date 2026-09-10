-- Production migration already applied to Supabase project dxgksvzibucwuzmppoqy.
-- Keep horizon values explicit so immutable forecast windows cannot drift to arbitrary labels.

alter table public.crypto_opportunities
    drop constraint if exists crypto_opportunities_horizon_check;

alter table public.crypto_opportunities
    add constraint crypto_opportunities_horizon_check
    check (horizon = any (array[
        '6h'::text,
        '12h'::text,
        '24h'::text,
        '48h'::text,
        '72h'::text,
        '7d'::text
    ]));

alter table public.prediction_ledger
    drop constraint if exists prediction_ledger_horizon_check;

alter table public.prediction_ledger
    add constraint prediction_ledger_horizon_check
    check (horizon = any (array[
        '6h'::text,
        '12h'::text,
        '24h'::text,
        '48h'::text,
        '72h'::text,
        '7d'::text
    ]));
