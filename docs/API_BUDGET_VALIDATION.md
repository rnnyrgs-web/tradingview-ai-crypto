# Validation checklist

Before merging this candidate:

1. Run the full repository test suite, including `tests/test_autonomous_cloud_runner.py` and `tests/test_api_budget_policy.py`.
2. Require the repository's Security and Reliability workflow on the exact candidate head SHA.
3. Confirm the autonomous runner's worst-case reserved call remains below the daily allowance.
4. Confirm `runner_monthly_api_budget_usd + pause_buffer_usd <= project_monthly_ceiling_usd`.
5. Confirm broker connection, trade authority, automatic merge, specialist main writes and Sol in the bounded lane remain disabled.
6. Do not merge merely to accelerate API availability; the external OpenAI hard limit may independently block calls until its billing period resets.
