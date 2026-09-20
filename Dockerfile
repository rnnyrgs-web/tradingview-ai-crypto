FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Dockerfile ./
COPY *.py ./
COPY profitability_learning/ profitability_learning/
COPY orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz orchestration/evidence/
COPY orchestration/rejected_fingerprints.py orchestration/
COPY orchestration/rejected_fingerprints.json orchestration/
COPY orchestration/signal_development_objective.json orchestration/
COPY orchestration/trusted_executor_manifest.json orchestration/
EXPOSE 8000

CMD ["uvicorn", "sentry_service:app", "--host", "0.0.0.0", "--port", "8000"]
