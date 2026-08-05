"""Unit tests for Webhook & Cron Triggers API."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import issue_session_token, SESSION_COOKIE
from app.db import get_engine, init_db
from app.main import app
from app.models.workflow import Workflow, WorkflowVersion

client = TestClient(app)
client.cookies.set(SESSION_COOKIE, issue_session_token())


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_trigger_crud_and_webhook():
    wf_name = f"webhook_test_wf_{uuid.uuid4().hex[:6]}"
    engine = get_engine()
    with Session(engine) as session:
        wf = Workflow(name=wf_name)
        session.add(wf)
        session.flush()

        graph_json = {
            "nodes": [
                {"id": "input-1", "type": "input", "name": "Input", "config": {"prompt": "p"}},
                {
                    "id": "response-1",
                    "type": "response",
                    "name": "Resp",
                    "config": {"content": "ok"},
                },
            ],
            "edges": [
                {"id": "e1", "source": "input-1", "source_port": "default", "target": "response-1"}
            ],
        }
        ver = WorkflowVersion(
            workflow_id=wf.id, version_number=1, graph_json=str(graph_json).replace("'", '"')
        )
        session.add(ver)
        session.flush()
        wf.active_version_id = ver.id
        session.add(wf)
        session.commit()
        wf_id = wf.id

    # 2. Create Webhook Trigger via API
    resp = client.post(
        "/api/triggers",
        json={
            "workflow_id": wf_id,
            "trigger_type": "webhook",
            "webhook_secret": "my-secret-token",
            "enabled": True,
        },
    )
    assert resp.status_code == 201
    trigger_data = resp.json()
    assert trigger_data["trigger_type"] == "webhook"
    assert trigger_data["webhook_secret"] == "my-secret-token"

    # 3. Test unauthenticated Webhook execution with invalid secret -> 401
    unauth_client = TestClient(app)
    resp_invalid = unauth_client.post(
        f"/api/triggers/webhook/{wf_name}",
        json={"question": "Hello world"},
        headers={"X-NextGen-Secret": "wrong-secret"},
    )
    assert resp_invalid.status_code == 401

    # 4. Test unauthenticated Webhook execution with valid secret -> 202 Accepted
    resp_valid = unauth_client.post(
        f"/api/triggers/webhook/{wf_name}",
        json={"question": "Hello world"},
        headers={"X-NextGen-Secret": "my-secret-token"},
    )
    assert resp_valid.status_code == 202
    res_data = resp_valid.json()
    assert "run_id" in res_data
    assert res_data["status"] == "running"
