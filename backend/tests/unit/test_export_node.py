"""Unit tests for Export node (Slack, Email, File destinations)."""

import pytest
from unittest.mock import MagicMock, patch

from app.graph.nodes import export_node
from app.graph.state import GraphState


def _state(node_outputs=None):
    return GraphState(
        run_id="run-1",
        workflow_id="wf-1",
        workflow_version=1,
        variables={},
        node_outputs=node_outputs or {},
        retry_counts={},
        last_output_port={},
        pending_input_node_id=None,
    )


@pytest.mark.asyncio
async def test_export_file_destination(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTGEN_EXPORTS_PATH", str(tmp_path))
    state = _state(node_outputs={"__latest__": "Report content summary"})

    config = {
        "destination": "file",
        "content": "{{previous}}",
        "file_format": "markdown",
    }
    result = await export_node.execute("export1", config, state)

    assert result["last_output_port"]["export1"] == "success"
    written_files = list(tmp_path.glob("export_export1.md"))
    assert len(written_files) == 1
    assert written_files[0].read_text(encoding="utf-8") == "Report content summary"


@pytest.mark.asyncio
async def test_export_slack_destination():
    state = _state(node_outputs={"__latest__": "Slack alert payload"})

    config = {
        "destination": "slack",
        "slack_webhook_url": "https://hooks.slack.com/services/test",
        "content": "{{previous}}",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        result = await export_node.execute("export1", config, state)

        assert result["last_output_port"]["export1"] == "success"
        assert "Slack message sent" in result["node_outputs"]["export1"]["message"]
        mock_post.assert_called_once_with(
            "https://hooks.slack.com/services/test",
            json={"text": "Slack alert payload"},
            timeout=10,
        )


@pytest.mark.asyncio
async def test_export_slack_missing_url():
    state = _state()
    config = {"destination": "slack", "slack_webhook_url": ""}

    result = await export_node.execute("export1", config, state)
    assert result["last_output_port"]["export1"] == "failure"
    assert "slack_webhook_url is required" in result["node_outputs"]["export1"]["error"]


@pytest.mark.asyncio
async def test_export_email_destination():
    state = _state(node_outputs={"__latest__": "Email report body"})
    config = {
        "destination": "email",
        "email_recipient": "user@example.com",
        "email_subject": "Test Report",
        "smtp_host": "localhost",
        "smtp_port": 25,
    }

    with patch("smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = instance

        result = await export_node.execute("export1", config, state)

        assert result["last_output_port"]["export1"] == "success"
        assert instance.send_message.called
