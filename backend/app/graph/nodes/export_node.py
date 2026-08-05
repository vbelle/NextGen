"""Export node: delivers workflow output to external channels (Slack, Email, File).

Supports dual output ports: "success" (green) and "failure" (red).
"""

from __future__ import annotations

from email.mime.text import MIMEText
import httpx
import os
from pathlib import Path
import smtplib
from typing import Literal

from pydantic import BaseModel, Field

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template
from app.logging import get_logger

logger = get_logger(__name__)


class ExportConfig(BaseModel):
    destination: Literal["slack", "email", "file"] = Field(
        default="file", description="Destination channel ('slack', 'email', 'file')"
    )
    content: str = Field(default="{{previous}}", description="Template content to export")
    slack_webhook_url: str | None = Field(default=None, description="Slack incoming webhook URL")
    email_recipient: str | None = Field(default=None, description="Recipient email address")
    email_subject: str = Field(default="NextGen Workflow Report", description="Email subject line")
    smtp_host: str = Field(default="localhost", description="SMTP server hostname")
    smtp_port: int = Field(default=25, description="SMTP server port")
    smtp_user: str | None = Field(default=None, description="SMTP username")
    smtp_password: str | None = Field(default=None, description="SMTP password")
    file_format: Literal["markdown", "html"] = Field(
        default="markdown", description="File format for disk exports ('markdown' or 'html')"
    )


def _export_slack(cfg: ExportConfig, rendered_text: str) -> str:
    url = (cfg.slack_webhook_url or "").strip()
    if not url:
        raise ValueError("slack_webhook_url is required for Slack export destination")

    resp = httpx.post(url, json={"text": rendered_text}, timeout=10)
    resp.raise_for_status()
    return f"Slack message sent successfully to webhook (status {resp.status_code})"


def _export_email(cfg: ExportConfig, rendered_text: str) -> str:
    recipient = (cfg.email_recipient or "").strip()
    if not recipient:
        raise ValueError("email_recipient is required for Email export destination")

    msg = MIMEText(rendered_text, "plain", "utf-8")
    msg["Subject"] = cfg.email_subject
    msg["To"] = recipient
    msg["From"] = cfg.smtp_user or "nextgen@localhost"

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
        if cfg.smtp_user and cfg.smtp_password:
            server.login(cfg.smtp_user, cfg.smtp_password)
        server.send_message(msg)

    return f"Email report sent successfully to '{recipient}' via {cfg.smtp_host}:{cfg.smtp_port}"


def _export_file(cfg: ExportConfig, rendered_text: str, node_id: str) -> str:
    export_dir = Path(os.environ.get("NEXTGEN_EXPORTS_PATH", "./data/exports"))
    export_dir.mkdir(parents=True, exist_ok=True)

    ext = "html" if cfg.file_format == "html" else "md"
    file_path = export_dir / f"export_{node_id}.{ext}"

    if cfg.file_format == "html":
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{cfg.email_subject}</title></head>
<body style="font-family: sans-serif; padding: 20px; line-height: 1.6;">
<div>{rendered_text.replace(chr(10), '<br>')}</div>
</body>
</html>"""
        file_path.write_text(html_content, encoding="utf-8")
    else:
        file_path.write_text(rendered_text, encoding="utf-8")

    return f"Report written to file at {file_path.resolve()}"


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = ExportConfig(**config)
    rendered = render_template(cfg.content, state)
    logger.info("Executing Export node '%s' for destination '%s'", node_id, cfg.destination)

    try:
        if cfg.destination == "slack":
            result_msg = _export_slack(cfg, rendered)
        elif cfg.destination == "email":
            result_msg = _export_email(cfg, rendered)
        else:
            result_msg = _export_file(cfg, rendered, node_id)

        logger.info("Export node '%s' succeeded: %s", node_id, result_msg)
        return {
            "node_outputs": {
                node_id: {"message": result_msg, "content": rendered},
                "__latest__": rendered,
            },
            "last_output_port": {node_id: "success"},
        }
    except Exception as exc:
        err_msg = f"Export node '{node_id}' failed: {exc}"
        logger.error(err_msg, exc_info=True)
        return {
            "node_outputs": {
                node_id: {"error": str(exc), "content": rendered},
                "__latest__": f"Export error: {exc}",
            },
            "last_output_port": {node_id: "failure"},
        }


register_node_type("export", ExportConfig, execute)
