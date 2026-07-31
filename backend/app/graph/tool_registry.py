"""Backend registry of built-in tools a Tool node's `implementation_ref` can
resolve to.

2026-07-30 design decision (asked, not guessed — contracts/graph-schema.md's
`implementation_ref: "string, maps to a registered backend tool"` doesn't say
what a "registered backend tool" actually is): a small, fixed registry of
pre-written Python functions shipped with the app, rather than user-authored
code (that's the Code node's job — a Tool node config has no snippet field)
or an HTTP call (that's the API node's job — this would just duplicate it).

Each entry pairs a Pydantic args schema — needed because the Tool node's own
config carries no parameter schema, only a name/description/ref — with a
plain, synchronous, side-effect-free Python callable. LangChain's tool
wrapper (built in app/graph/nodes/llm_node.py, since that's where a run_id
is available for audit logging) runs sync callables like these in a thread
automatically when awaited, so there's no need for these to be async."""

from __future__ import annotations

import ast
import operator
import os
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, Field


class CalculatorArgs(BaseModel):
    expression: str = Field(description="An arithmetic expression, e.g. '2 * (3 + 4)'")


class DatetimeArgs(BaseModel):
    pass


class WordCountArgs(BaseModel):
    text: str = Field(description="The text to count words in")


class WeatherArgs(BaseModel):
    city: str = Field(description="City name, e.g. 'London' or 'San Francisco'")


class GoogleSearchArgs(BaseModel):
    query: str = Field(description="The search query to look up on Google")
    num_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of organic results to return (1–10, default 5)",
    )


# Open-Meteo, not a weather.com/OpenWeatherMap-style API: no API key or signup
# required (a Tool implementation here has no credential_id field to plug one
# into anyway — that's the API node's job, per this module's docstring), and
# both of its endpoints used below are free with no rate-limit key. WMO
# weather codes per https://open-meteo.com/en/docs — condensed to the ones
# actually likely to come back for a current-conditions lookup.
_WMO_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def get_weather(city: str) -> str:
    # Open-Meteo has no built-in city-name search on the forecast endpoint
    # itself, so this is two calls: geocode the city to lat/lon, then fetch
    # current conditions for that point.
    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    )
    geo.raise_for_status()
    results = geo.json().get("results")
    if not results:
        return f"Could not find a location named '{city}'."
    place = results[0]
    lat, lon = place["latitude"], place["longitude"]

    forecast = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": lat, "longitude": lon, "current_weather": True},
        timeout=10,
    )
    forecast.raise_for_status()
    current = forecast.json().get("current_weather", {})
    condition = _WMO_CODES.get(current.get("weathercode"), "unknown conditions")
    resolved_name = ", ".join(part for part in [place.get("name"), place.get("country")] if part)
    return (
        f"{resolved_name}: {condition}, {current.get('temperature')}°C, "
        f"wind {current.get('windspeed')} km/h"
    )


_ALLOWED_BIN_OPS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARY_OPS: dict[type, Callable] = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    # Whitelist-based arithmetic evaluator (no eval()/exec()) — same spirit as
    # the Code node's RestrictedPython sandboxing, scoped down to arithmetic
    # since that's all a calculator tool needs.
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
        return _ALLOWED_BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
        return _ALLOWED_UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression element: {ast.dump(node)}")


def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_safe_eval(tree.body))
    except Exception as exc:
        raise ValueError(f"Could not evaluate '{expression}': {exc}") from exc


def current_datetime() -> str:
    # timezone.utc, not the datetime.UTC alias, to match every other
    # started_at/ended_at timestamp in this codebase (e.g. app/runtime/audit.py).
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def word_count(text: str) -> str:
    return str(len(text.split()))


def google_search(query: str, num_results: int = 5) -> str:
    """Search Google via SerpAPI and return the top organic results as plain text.

    Requires SERPAPI_KEY in the environment (set it in .env — get a free key
    at https://serpapi.com). Never put the key directly in a workflow or tool
    config; read it here from the environment so it stays out of graph JSON.
    """
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "SERPAPI_KEY environment variable is not set. "
            "Get a free API key at https://serpapi.com and add it to your .env file, "
            "then rebuild the container."
        )
    response = httpx.get(
        "https://serpapi.com/search.json",
        params={"q": query, "api_key": api_key, "engine": "google", "num": num_results},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    # SerpAPI surfaces a top-level error field on bad keys / quota exceeded.
    if "error" in data:
        raise ValueError(f"SerpAPI error: {data['error']}")

    results = data.get("organic_results", [])
    if not results:
        return f"No results found for '{query}'."

    parts: list[str] = []
    for i, r in enumerate(results[:num_results], 1):
        title = r.get("title", "(no title)")
        snippet = r.get("snippet", "")
        link = r.get("link", "")
        parts.append(f"{i}. {title}\n   {snippet}\n   {link}")
    return "\n\n".join(parts)


class ToolImplementation:
    def __init__(self, args_schema: type[BaseModel], func: Callable[..., str]):
        self.args_schema = args_schema
        self.func = func


_REGISTRY: dict[str, ToolImplementation] = {
    "calculator": ToolImplementation(CalculatorArgs, calculator),
    "current_datetime": ToolImplementation(DatetimeArgs, current_datetime),
    "word_count": ToolImplementation(WordCountArgs, word_count),
    "get_weather": ToolImplementation(WeatherArgs, get_weather),
    "google_search": ToolImplementation(GoogleSearchArgs, google_search),
}


class UnknownToolImplementationError(Exception):
    def __init__(self, ref: str):
        self.ref = ref
        super().__init__(
            f"'{ref}' is not a registered tool implementation. Known: {sorted(_REGISTRY)}"
        )


def get_tool_implementation(ref: str) -> ToolImplementation:
    if ref not in _REGISTRY:
        raise UnknownToolImplementationError(ref)
    return _REGISTRY[ref]


def list_tool_implementations() -> list[str]:
    return sorted(_REGISTRY)
