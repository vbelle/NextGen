"""Unit tests for AI Workflow Generator module."""

from unittest.mock import AsyncMock, patch

import pytest

from app.graph.ai_generator import generate_workflow_from_prompt


@pytest.mark.asyncio
async def test_generate_workflow_from_prompt():
    mock_json = """
    {
      "name": "generated_research_team",
      "graph_json": {
        "nodes": [
          {
            "id": "input-1",
            "type": "input",
            "name": "User Question",
            "config": {"prompt": "Enter request:", "required": true},
            "position": {"x": 100, "y": 100}
          },
          {
            "id": "llm-1",
            "type": "llm",
            "name": "Research Agent",
            "config": {"provider": "ollama", "model": "llama3.2", "prompt": "{{User Question}}", "timeout_seconds": 180},
            "position": {"x": 300, "y": 100}
          },
          {
            "id": "response-1",
            "type": "response",
            "name": "Display Answer",
            "config": {"content": "{{Research Agent}}"},
            "position": {"x": 500, "y": 100}
          }
        ],
        "edges": [
          {"id": "e1", "source": "input-1", "source_port": "default", "target": "llm-1"},
          {"id": "e2", "source": "llm-1", "source_port": "success", "target": "response-1"},
          {"id": "e3", "source": "llm-1", "source_port": "failure", "target": "response-1"}
        ]
      }
    }
    """

    with patch(
        "app.graph.ai_generator.OllamaProvider.generate",
        new_callable=AsyncMock,
        return_value=mock_json,
    ):
        result = await generate_workflow_from_prompt(
            "Create a single LLM research agent workflow", "generated_research_team"
        )
        assert result["name"] == "generated_research_team"
        assert len(result["graph_json"]["nodes"]) == 3
        assert result["graph_json"]["nodes"][1]["name"] == "Research Agent"
