from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _headers() -> dict[str, str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _model() -> str:
    model = os.getenv("OPENAI_AGENT_MODEL", "").strip()
    if not model:
        raise RuntimeError("OPENAI_AGENT_MODEL is not configured")
    return model


def _response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    out: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                out.append(text)
    return "\n".join(out)


def generate_state_update(current_state: str, pr_context: str) -> str:
    prompt = f"""
You are the Lead Integrator maintaining canonical AI_STATE.md for a crypto quantitative trading/signalling system.

CURRENT AI_STATE.md:\n{current_state}

JUST-MERGED PR CONTEXT:\n{pr_context}

Return the COMPLETE replacement AI_STATE.md only, no code fences.
Rules:
- Preserve all still-true authoritative facts.
- Record the merged PR/commit and exactly what was verified.
- Never claim a workflow, backtest, artifact, deployment, or strategy result that is not explicitly present in the supplied evidence.
- Keep pending/unknown items explicitly pending/unknown.
- Maintain fail-closed rules and the prohibition on live weighting from one OOS pass.
- Add/update the autonomous development architecture facts: specialist proposals come from isolated branches; Security CI plus independent lead/security AI review gates are required; specialist agents cannot edit AI_STATE.md or orchestration safeguards.
- End with a concrete EXACT NEXT STEP based only on current evidence.
"""
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers=_headers(),
            json={"model": _model(), "input": prompt},
        )
        response.raise_for_status()
        text = _response_text(response.json()).strip()
    if not text.startswith("# AI DEVELOPMENT STATE"):
        raise RuntimeError("state updater returned malformed AI_STATE.md")
    if "## EXACT NEXT STEP" not in text:
        raise RuntimeError("state updater omitted EXACT NEXT STEP")
    if len(text) < 1000:
        raise RuntimeError("state updater returned suspiciously short state")
    return text.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-context", required=True)
    args = parser.parse_args()

    state_path = ROOT / "AI_STATE.md"
    context_path = Path(args.pr_context)
    current = state_path.read_text(encoding="utf-8")
    context = context_path.read_text(encoding="utf-8")
    if len(context) > 90_000:
        raise RuntimeError("PR context too large for autonomous state update")
    updated = generate_state_update(current, context)
    state_path.write_text(updated, encoding="utf-8")
    print("AI_STATE.md prepared by Lead Integrator state updater")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
