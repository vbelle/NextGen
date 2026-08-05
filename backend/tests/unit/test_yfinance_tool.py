"""Unit tests for Yahoo Finance Stock Quote tool."""

from unittest.mock import MagicMock, patch
import pandas as pd

from app.graph.tool_registry import get_tool_implementation, yfinance_quote


def test_yfinance_quote_success():
    tool = get_tool_implementation("yfinance_quote")
    assert tool is not None
    assert tool.args_schema.__name__ == "YahooFinanceArgs"

    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Apple Inc.",
        "currentPrice": 220.50,
        "previousClose": 218.00,
        "marketCap": 3400000000000,
        "trailingPE": 32.5,
        "fiftyTwoWeekHigh": 237.23,
        "fiftyTwoWeekLow": 164.08,
        "longBusinessSummary": "Apple designs consumer electronics...",
    }

    dates = pd.date_range("2026-01-01", periods=5)
    mock_df = pd.DataFrame(
        {
            "Open": [215.0, 217.0, 218.0, 219.0, 220.0],
            "High": [218.0, 219.0, 221.0, 222.0, 223.0],
            "Low": [214.0, 216.0, 217.0, 218.0, 219.0],
            "Close": [216.0, 218.0, 220.0, 221.0, 220.5],
            "Volume": [50000000, 52000000, 48000000, 51000000, 49000000],
        },
        index=dates,
    )
    mock_ticker.history.return_value = mock_df

    with patch("yfinance.Ticker", return_value=mock_ticker):
        res = yfinance_quote("AAPL", period="5d")
        assert "Apple Inc. (AAPL)" in res
        assert "Current Price: $220.50 (+2.50 / +1.15%)" in res
        assert "5D History Summary" in res
        assert "Start/End: $216.00 ➔ $220.50 (+2.08%)" in res
