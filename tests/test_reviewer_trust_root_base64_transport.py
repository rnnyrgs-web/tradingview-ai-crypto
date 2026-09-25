from __future__ import annotations

import base64

import pytest

from orchestration import reviewer_trust_root as trust


def test_server_workflow_bytes_accepts_github_line_wrapped_base64() -> None:
    raw = b"trusted-workflow-bytes" * 8
    encoded = base64.b64encode(raw).decode("ascii")
    wrapped = "\r\n".join(encoded[i : i + 16] for i in range(0, len(encoded), 16)) + "\n"
    payload = {
        "type": "file",
        "encoding": "base64",
        "content": wrapped,
    }
    assert trust._server_workflow_bytes(payload) == raw


def test_server_workflow_bytes_rejects_non_transport_whitespace() -> None:
    raw = b"trusted-workflow-bytes"
    encoded = base64.b64encode(raw).decode("ascii")
    payload = {
        "type": "file",
        "encoding": "base64",
        "content": encoded[:4] + " " + encoded[4:],
    }
    with pytest.raises(RuntimeError, match="trusted server workflow source base64 invalid"):
        trust._server_workflow_bytes(payload)
