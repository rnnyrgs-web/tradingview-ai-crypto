FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY profitability_learning/ profitability_learning/
COPY orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz orchestration/evidence/

# Runtime rejection-memory import closure. Keep these explicit so the production
# image contains every module and frozen source artifact needed to authenticate
# exact + semantic rejected-design memory without copying unrelated research
# state into the container.
COPY orchestration/rejected_fingerprints.py orchestration/
COPY orchestration/rejected_fingerprints.json orchestration/
COPY orchestration/rejected_semantic_designs.json orchestration/
COPY orchestration/scientific_design_identity.py orchestration/
COPY orchestration/strategy_behavior_data_projection.py orchestration/
COPY orchestration/strategy_behavior_schema.py orchestration/
COPY orchestration/strategy_behavior_value_contract.py orchestration/
COPY orchestration/disc_vol_breakout_001.json orchestration/
COPY orchestration/disc_liquidity_meanrev_001.json orchestration/
COPY orchestration/disc_btc_leadlag_001.json orchestration/

COPY orchestration/signal_development_objective.json orchestration/
COPY orchestration/trusted_executor_manifest.json orchestration/
EXPOSE 8000

CMD ["uvicorn", "sentry_service:app", "--host", "0.0.0.0", "--port", "8000"]
