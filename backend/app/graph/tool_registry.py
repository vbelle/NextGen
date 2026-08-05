"""Backend registry of built-in and user-defined custom tools a Tool node's
`implementation_ref` can resolve to."""

from __future__ import annotations

import ast
from collections.abc import Callable
from datetime import datetime, timezone
import os
import operator
from typing import Any

import httpx
from pydantic import BaseModel, Field, create_model
from sqlmodel import Session, select

from app.db import get_engine
from app.models.custom_tool import CustomTool


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
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def word_count(text: str) -> str:
    return str(len(text.split()))


def google_search(query: str, num_results: int = 5) -> str:
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


def build_custom_tool_schema_and_fn(tool_name: str, python_code: str) -> ToolImplementation:
    """Parses a Python code snippet using AST to construct a dynamic Pydantic schema
    and execution function for function-calling."""
    try:
        tree = ast.parse(python_code)
    except SyntaxError as exc:
        raise ValueError(f"Invalid Python syntax in tool '{tool_name}': {exc}") from exc

    func_def = next((node for node in tree.body if isinstance(node, ast.FunctionDef)), None)
    if not func_def:
        raise ValueError(f"No top-level function definition found in code for tool '{tool_name}'")

    docstring = ast.get_docstring(func_def) or f"Custom tool '{tool_name}'"

    fields: dict[str, Any] = {}
    args = func_def.args.args
    defaults = func_def.args.defaults
    num_defaults = len(defaults)
    num_args = len(args)

    for i, arg in enumerate(args):
        arg_name = arg.arg
        if arg_name in ("self", "cls"):
            continue

        # Type annotation mapping
        type_hint = str
        if arg.annotation:
            ann_str = ast.unparse(arg.annotation).strip().lower()
            if ann_str in ("int", "integer"):
                type_hint = int
            elif ann_str in ("float", "double", "number"):
                type_hint = float
            elif ann_str in ("bool", "boolean"):
                type_hint = bool
            elif ann_str in ("dict", "object"):
                type_hint = dict
            elif ann_str in ("list", "array"):
                type_hint = list

        default_idx = i - (num_args - num_defaults)
        if default_idx >= 0:
            default_ast = defaults[default_idx]
            try:
                default_val = ast.literal_eval(default_ast)
                fields[arg_name] = (
                    type_hint,
                    Field(default=default_val, description=f"Parameter '{arg_name}'"),
                )
            except Exception:
                fields[arg_name] = (type_hint, Field(description=f"Parameter '{arg_name}'"))
        else:
            fields[arg_name] = (type_hint, Field(description=f"Parameter '{arg_name}'"))

    schema_name = f"{tool_name.title().replace('_', '')}Args"
    args_schema = create_model(schema_name, **fields)
    args_schema.__doc__ = docstring

    def _exec(**kwargs) -> str:
        loc: dict[str, Any] = {}
        glob: dict[str, Any] = {"httpx": httpx, "json": os, "datetime": datetime, "math": ast}
        exec(python_code, glob, loc)
        fn = loc.get(func_def.name) or glob.get(func_def.name)
        if not callable(fn):
            raise ValueError(f"Function '{func_def.name}' not found in executable scope")
        res = fn(**kwargs)
        return str(res) if res is not None else ""

    return ToolImplementation(args_schema=args_schema, func=_exec)


class UnknownToolImplementationError(Exception):
    def __init__(self, ref: str):
        known = sorted(list_tool_implementations())
        super().__init__(f"'{ref}' is not a registered tool implementation. Known: {known}")


def get_tool_implementation(ref: str) -> ToolImplementation:
    if ref in _REGISTRY:
        return _REGISTRY[ref]

    # Query DB for CustomTool
    with Session(get_engine()) as session:
        tool_row = session.exec(select(CustomTool).where(CustomTool.name == ref)).first()
        if tool_row:
            return build_custom_tool_schema_and_fn(tool_row.name, tool_row.python_code)

    raise UnknownToolImplementationError(ref)


def list_tool_implementations() -> list[str]:
    builtins = set(_REGISTRY.keys())
    with Session(get_engine()) as session:
        custom_rows = session.exec(select(CustomTool)).all()
        for r in custom_rows:
            builtins.add(r.name)
    return sorted(list(builtins))
