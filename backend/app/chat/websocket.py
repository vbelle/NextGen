"""The built-in chat — the only way workflows are invoked and interacted with
(Constitution II). See contracts/chat-websocket.md."""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

from app.auth import verify_session_token, SESSION_COOKIE
from app.db import get_engine
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.run import Run, RunStatus
from app.models.workflow import Workflow, WorkflowVersion
from app.runtime import executor, notify

router = APIRouter()


def _session_factory():
    return Session(get_engine())


async def _send(ws: WebSocket, msg_type: str, payload: dict) -> None:
    await ws.send_text(json.dumps({"type": msg_type, "payload": payload}))


def _record_message(
    session: Session, chat_session_id: str, role: ChatRole, content: str, run_id: str | None = None
) -> None:
    session.add(
        ChatMessage(chat_session_id=chat_session_id, role=role, content=content, run_id=run_id)
    )
    session.commit()


async def _run_and_relay(ws: WebSocket, chat_session_id: str, run_id: str, kickoff) -> None:
    """Registers for this run's outcome, kicks off execution, waits for the
    executor to report a result, relays it to the client, and persists it as a
    ChatMessage (matching how ChatMessage renders the transcript, per data-model.md)."""
    queue = notify.register(run_id)
    try:
        await kickoff()
        message = await queue.get()
    finally:
        notify.unregister(run_id)

    await ws.send_text(json.dumps(message))
    with Session(get_engine()) as session:
        if message["type"] == "input_request":
            _record_message(
                session, chat_session_id, ChatRole.system, message["payload"]["prompt"], run_id
            )
        elif message["type"] == "response":
            _record_message(
                session,
                chat_session_id,
                ChatRole.system,
                str(message["payload"]["content"]),
                run_id,
            )
        elif message["type"] == "run_failed":
            _record_message(
                session,
                chat_session_id,
                ChatRole.system,
                f"Run failed: {message['payload']['message']}",
                run_id,
            )


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    token = websocket.cookies.get(SESSION_COOKIE)
    if not verify_session_token(token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    session_id = websocket.query_params.get("session_id")

    with Session(get_engine()) as session:
        if session_id:
            chat_session = session.get(ChatSession, session_id)
        else:
            chat_session = None
        if chat_session is None:
            chat_session = ChatSession()
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

        history = session.exec(
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == chat_session.id)
            .order_by(ChatMessage.created_at)
        ).all()
        await _send(
            websocket,
            "history",
            {
                "session_id": chat_session.id,
                "messages": [
                    {"role": m.role, "content": m.content, "run_id": m.run_id} for m in history
                ],
            },
        )

        # Reconnect while a run tied to this session is still paused (FR-011).
        paused_run = session.exec(
            select(Run).where(
                Run.chat_session_id == chat_session.id, Run.status == RunStatus.paused
            )
        ).first()
        if paused_run and paused_run.pending_prompt:
            pending = json.loads(paused_run.pending_prompt)
            await _send(websocket, "input_request", {"run_id": paused_run.id, **pending})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            payload = msg.get("payload", {})

            if msg_type == "start_workflow":
                name = payload.get("name", "")
                with Session(get_engine()) as session:
                    workflow = session.exec(select(Workflow).where(Workflow.name == name)).first()
                    if not workflow or not workflow.active_version_id:
                        await _send(websocket, "workflow_not_found", {"name": name})
                        continue
                    version = session.get(WorkflowVersion, workflow.active_version_id)
                    graph_json = json.loads(version.graph_json)

                    run = Run(workflow_version_id=version.id, chat_session_id=chat_session.id)
                    session.add(run)
                    session.commit()
                    session.refresh(run)
                    # Pull out plain values before the Session (and therefore this
                    # ORM object) closes at the end of the `with` block.
                    run_id = run.id
                    workflow_id = workflow.id
                    version_number = version.version_number
                    _record_message(
                        session, chat_session.id, ChatRole.user, f"start {name}", run_id
                    )

                await _send(websocket, "status", {"run_id": run_id, "status": "running"})
                initial_state = {
                    "run_id": run_id,
                    "workflow_id": workflow_id,
                    "workflow_version": version_number,
                    "variables": {},
                    "node_outputs": {},
                    "retry_counts": {},
                    "last_output_port": {},
                    "pending_input_node_id": None,
                }

                async def kickoff(
                    run_id=run_id, graph_json=graph_json, initial_state=initial_state
                ):
                    await executor.start_run(
                        session_factory=_session_factory,
                        run_id=run_id,
                        graph_json=graph_json,
                        initial_state=initial_state,
                    )

                await _run_and_relay(websocket, chat_session.id, run_id, kickoff)

            elif msg_type == "provide_input":
                run_id = payload.get("run_id")
                value = payload.get("value", "")
                with Session(get_engine()) as session:
                    run = session.get(Run, run_id)
                    if not run or run.status != RunStatus.paused:
                        await _send(
                            websocket,
                            "run_failed",
                            {"run_id": run_id, "message": "This run is not waiting for input."},
                        )
                        continue
                    version = session.get(WorkflowVersion, run.workflow_version_id)
                    graph_json = json.loads(version.graph_json)
                    _record_message(session, chat_session.id, ChatRole.user, value, run_id)
                    run.status = RunStatus.running
                    session.add(run)
                    session.commit()

                async def kickoff(run_id=run_id, graph_json=graph_json, value=value):
                    await executor.resume_run(
                        session_factory=_session_factory,
                        run_id=run_id,
                        graph_json=graph_json,
                        resume_value=value,
                    )

                await _run_and_relay(websocket, chat_session.id, run_id, kickoff)

    except WebSocketDisconnect:
        pass
