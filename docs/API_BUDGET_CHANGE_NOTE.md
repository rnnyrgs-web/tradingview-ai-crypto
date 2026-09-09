Change note for the $30/month API-budget candidate:

This candidate changes only the bounded autonomous specialist API lane. It does not raise Render compute, heavy-worker concurrency, broker authority, or live promotion authority. The software budget gate remains fail-closed and reserves a $1 monthly buffer beneath the $30 project ceiling. The external OpenAI organization hard limit should remain $30/month.

Important: other legacy/manual workflows that can call OpenAI are not automatically governed by this runner state. They should remain manual/disabled unless separately brought under a shared global ledger. This candidate therefore improves the active bounded lane but does not claim an account-wide software-enforced cap independent of the OpenAI hard limit.
