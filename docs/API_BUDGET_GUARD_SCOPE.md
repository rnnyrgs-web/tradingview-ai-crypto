# API budget guard scope

`api_budget_guard.py` provides the fail-closed 3x protected prospective-call check for the autonomous API lane. The runner configuration targets about USD 1/day, USD 29/month of model spend, plus a USD 1 project buffer under the external USD 30 organization hard limit.

The guard is designed to be invoked immediately before any paid autonomous model execution. Until that invocation is wired into the workflow, the existing runner's native daily/monthly checks and the external OpenAI USD 30 hard limit remain the active enforcement backstops.
