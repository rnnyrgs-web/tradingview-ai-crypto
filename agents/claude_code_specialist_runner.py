from __future__ import annotations

import argparse
import json
from pathlib import Path

# Dual-import pattern kept consistent with agents/autonomous_cloud_state.py
# and agents/claude_specialist_runner.py so this module behaves identically
# whether imported as a package or executed directly as a script.
if __package__:
    from .autonomous_cloud_runner import load_config, load_coordination, load_state, plan_decision, save_state, utc_now
else:
    from autonomous_cloud_runner import load_config, load_coordination, load_state, plan_decision, save_state, utc_now

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "orchestration" / "autonomous_specialist_runner_claude_code.json"

# This module intentionally has no `execute` subcommand and no model-calling
# code. Claude Code's implementation step is the real, officially documented
# `anthropics/claude-code-action@v1` GitHub Action
# (https://code.claude.com/docs/en/github-actions), invoked directly from
# .github/workflows/autonomous_claude_code_specialist.yml against the
# already-checked-out isolated task branch. This module only provides the
# same `validate`/`plan` contract every other engine's workflow uses (task
# selection, budget gating, deterministic branch naming, durable state
# persistence) so task claiming stays uniform across engines; publication
# afterwards reuses agents/autonomous_cloud_state.py's existing
# mark-pr/mark-ci/mark-failure commands with --config pointed at this
# engine's own config and state file, exactly like the OpenAI runner.


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    plan = sub.add_parser("plan")
    plan.add_argument("--state", required=True)
    plan.add_argument("--main-sha", required=True)
    plan.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    if args.command == "validate":
        print("claude code specialist runner: valid")
        return 0

    coordination = load_coordination()
    path = Path(args.state)
    state = load_state(path)
    decision = plan_decision(config, coordination, state, args.main_sha, utc_now())
    state["last_seen_main_sha"] = args.main_sha
    save_state(path, state)
    Path(args.output).write_text(json.dumps(decision.as_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision.as_dict(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
