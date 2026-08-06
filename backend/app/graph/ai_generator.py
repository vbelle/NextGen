"""AI Workflow Compiler: Compiles natural language prompts into valid NextGen Graph JSON."""

from __future__ import annotations

import json
from typing import Any

from app.graph.validation import validate_graph
from app.providers.ollama_provider import OllamaProvider


SYSTEM_GRAPH_COMPILER_PROMPT = """You are the NextGen AI Workflow Compiler.
Your job is to convert a user's natural language request into a valid NextGen visual workflow graph JSON.

NEXTGEN NODE TYPES & CONFIG SCHEMAS:
1. input:
   config: {"prompt": "...", "required": true}
2. decision:
   config: {"left": "{{Node Name}}", "operator": "contains|equals", "right": "exit"}
3. memory:
   config: {"vector_store_ref": "interview_vault|obsidian_vault", "query": "{{User Question}}", "top_k": 10}
4. llm:
   config: {"provider": "ollama", "model": "llama3.2", "prompt": "...", "timeout_seconds": 180}
5. response:
   config: {"content": "{{LLM Node Name}}"}
6. tool:
   config: {"function_name": "interview_search|obsidian_search", "description": "...", "implementation_ref": "interview_search"}

IMPORTANT TEMPLATING & WIRING RULES:
- Always start with an "input" node (id: "input-1", name: "User Question").
- Connect input-1 to a "decision" node (id: "decision-1", name: "Check Exit") to check if input contains "exit".
- Connect decision-1 ("true" port) to a "response" node (id: "exit-response", name: "Exit Session") with content: "👋 Session closed."
- Connect decision-1 ("false" port) to downstream worker nodes (memory, llm, etc.).
- Every LLM node MUST connect BOTH its "success" and "failure" ports to downstream nodes (e.g. both route to response node)!
- Downstream LLM nodes should reference upstream node names directly using Handlebars templates, e.g. {{User Question}}, {{Memory RAG}}, {{Architect Agent}}.
- Always end execution paths in a "response" node.

OUTPUT FORMAT:
Return ONLY valid raw JSON matching:
{
  "name": "workflow_name_slug",
  "graph_json": {
    "nodes": [
      {
        "id": "node_id",
        "type": "input|decision|memory|llm|response|tool",
        "name": "Human Readable Name",
        "config": { ... },
        "position": {"x": 100, "y": 100}
      }
    ],
    "edges": [
      {
        "id": "e1",
        "source": "source_node_id",
        "source_port": "default|true|false|success|failure",
        "target": "target_node_id"
      }
    ]
  }
}
No markdown backticks, no conversational text before or after the JSON.
"""


async def generate_workflow_from_prompt(prompt: str, name_hint: str | None = None) -> dict[str, Any]:
    provider = OllamaProvider()
    full_prompt = f"User Request: {prompt}\nWorkflow Name Hint: {name_hint or 'custom_dynamic_workflow'}"
    raw_response = await provider.generate(
        system_prompt=SYSTEM_GRAPH_COMPILER_PROMPT,
        prompt=full_prompt,
        model="llama3.2",
    )

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    parsed = json.loads(cleaned)
    graph_json = parsed.get("graph_json", parsed)
    wf_name = parsed.get("name") or name_hint or "custom_dynamic_workflow"

    validation = validate_graph(graph_json)
    if not validation.is_valid:
        issues = [i.message for i in validation.issues]
        raise ValueError(f"AI generated invalid graph: {', '.join(issues)}")

    return {"name": wf_name, "graph_json": graph_json}
