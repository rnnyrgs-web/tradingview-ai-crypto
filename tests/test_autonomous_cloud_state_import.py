from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cloud_state_script_ignores_installed_agents_package_shadow(tmp_path: Path):
    """Failure accounting must work after openai-agents installs `agents`."""
    fake_package = tmp_path / "agents"
    fake_package.mkdir()
    (fake_package / "__init__.py").write_text("# shadows repository namespace package\n")

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(tmp_path), str(repo_root)))

    result = subprocess.run(
        [sys.executable, "agents/autonomous_cloud_state.py", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
