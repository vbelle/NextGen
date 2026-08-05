"""Unit tests for Custom Tools registry, AST parsing, and REST endpoints."""

import uuid
import pytest
from sqlmodel import Session

from app.db import get_engine, init_db
from app.graph.tool_registry import (
    build_custom_tool_schema_and_fn,
    get_tool_implementation,
    list_tool_implementations,
)
from app.models.custom_tool import CustomTool


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_build_custom_tool_schema():
    code = '''
def fetch_stock_quote(ticker: str, count: int = 5) -> str:
    """Fetches stock quote for a ticker symbol."""
    return f"Stock {ticker.upper()} has {count} entries"
'''
    impl = build_custom_tool_schema_and_fn("fetch_stock_quote", code)
    assert impl.args_schema.__name__ == "FetchStockQuoteArgs"
    assert impl.args_schema.__doc__ == "Fetches stock quote for a ticker symbol."

    schema = impl.args_schema.model_json_schema()
    assert "ticker" in schema["properties"]
    assert "count" in schema["properties"]

    res = impl.func(ticker="aapl", count=3)
    assert res == "Stock AAPL has 3 entries"


def test_custom_tool_db_registry():
    tool_name = f"calculate_tax_{uuid.uuid4().hex[:6]}"
    code = f'''
def {tool_name}(amount: float) -> str:
    """Calculates 10% tax for an amount."""
    return str(amount * 0.10)
'''
    engine = get_engine()
    with Session(engine) as session:
        tool = CustomTool(
            name=tool_name,
            description="Calculates 10% tax for an amount.",
            python_code=code,
        )
        session.add(tool)
        session.commit()

    all_tools = list_tool_implementations()
    assert tool_name in all_tools

    impl = get_tool_implementation(tool_name)
    assert impl.func(amount=100.0) == "10.0"
