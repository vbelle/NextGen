# Execution mechanism: what NextGen does, and the alternatives considered

This is a record of a discussion about how workflow execution actually works today and what other mechanisms were considered for turning a canvas graph into a running flow. Written for whoever picks this project up next, so the reasoning behind sticking with the current approach isn't lost.

## Correcting a common misconception first

NextGen does **not** generate Python source and execute that generated text. `backend/app/graph/compiler.py` builds a live LangGraph `StateGraph` object directly from a workflow's `graph_json` — real `.add_node()`/`.add_edge()` calls against real function references (each node type's registered `execute()`), then `.compile()` and `.invoke()`/`.astream()`. The "View code" panel (`backend/app/graph/codegen.py`) is a separate, read-only rendering built for human inspection — it reflects what the compiler does, but it is not on the execution path. Nothing about running a workflow depends on that panel existing or being accurate.

So the actual mechanism is: **graph JSON → direct interpretation by a graph engine (LangGraph)**, not codegen-then-run. This distinction matters for the comparison below, because "generate code and run it" is a meaningfully different (and riskier) mechanism than what's actually implemented.

## The mechanisms considered

**Direct interpretation via a graph engine — what's implemented (LangGraph).** Purpose-built for LLM-agent-shaped graphs: native `interrupt()`/checkpointing gives the pause-and-wait-for-chat-input pattern (Constitution Principle II/III) for free, and state-merge reducers are what let the Merge node's fan-in work correctly with zero custom join logic. Cost: execution is bound to LangGraph's semantics (supersteps, channels) and it's Python-only. This is also the closest match to comparable tools in this space — LangFlow and Flowise both interpret their graphs directly rather than generating and running source, so this isn't an unusual choice.

**Actual codegen + subprocess/exec.** Generate real source and run it as a script or subprocess instead of interpreting the graph in-process. This would gain a genuine capability the current design doesn't have: a true "eject" story, where a user takes a generated `.py` file and runs their workflow with zero NextGen involvement. That's a different capability, not just a different implementation of the same one. Cost: the whole workflow would need Code-node-grade sandboxing (not just Code nodes), tight WebSocket streaming/pause-resume would need a new protocol to survive running out-of-process, and the compiler and the codegen output become two things that must never drift instead of one. Verdict: worth it only as an *additive* export/eject feature later, never as the primary execution path.

**A custom lightweight interpreter (no LangGraph).** Full control over scheduling, dynamic subgraph mutation, anything you want. Cost: reimplementing checkpointing and interrupt/resume from scratch — exactly the hard problem LangGraph already solved. This is the option to actively avoid; it's a lot of subtle correctness risk (of the same kind just seen with the Merge node's `__latest__` race condition, fixed this project by resolving contributing node_ids at compile time rather than at runtime) for a capability the project doesn't currently need.

**Durable-execution orchestrators (Temporal, Prefect, Dagster).** The industrial-strength answer to "pause for arbitrarily long, resume reliably, survive process crashes." Temporal's signals in particular map almost exactly onto the human-in-the-loop pattern here, plus mature observability tooling. Cost: an entire extra server + datastore to operate, which directly conflicts with Constitution Principle I ("good enough for 5 trusted users behind a shared gate," explicitly not internet-scale infra). Worth revisiting only if this ever needs to survive process crashes mid-run or scale past a small team — not a fit today.

**Actor/message-bus execution** (nodes as independent workers on a queue, e.g. Redis streams, dispatched by a scheduler). Enables distributing execution across processes or machines and more exotic scheduling policies. Solves a scaling problem the project doesn't have yet, at real complexity cost now.

## Conclusion

The current mechanism (direct interpretation on LangGraph) is the right fit for this project's actual goals, and matches the choice made by the closest comparable tools rather than being an unusual approach. The one addition worth its cost later is turning the codegen panel into a genuine **export/eject feature** — "download this workflow as a standalone script" — as a bonus on top of the current execution path, not a replacement for it. The heavier options (Temporal, a custom engine) solve problems — crash durability, massive scale — that the project's own constitution places explicitly out of scope.
