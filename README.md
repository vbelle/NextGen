# NextGen

Self-hosted, agentic workflow builder. Design workflows as a graph of nodes
(Input, LLM, Decision, API, Variable, Code, Retry, Loop, Memory, and more) in
a browser canvas, then run them from a chat interface. Runs entirely on your
own infrastructure — no external API calls beyond the LLM/embedding provider
you point it at (a local Ollama instance by default).

## Requirements

- Docker + Docker Compose
- ~8GB+ RAM free for Ollama if running models locally (varies by model)

## Build & run

```bash
git clone https://github.com/vbelle/NextGen.git
cd NextGen

cp .env.example .env
# edit .env — at minimum set NEXTGEN_APP_PASSWORD, and generate NEXTGEN_CREDENTIAL_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up -d --build
```

This builds and starts two containers:

- **`app`** — the NextGen backend (FastAPI) and the built frontend, served together on port `8000`.
- **`ollama`** — a bundled Ollama instance for local LLM generation and embeddings, on port `11434`.

Check both are up:

```bash
docker compose ps   # both services should show "running"/"healthy"
```

Pull at least one model before first use — the bundled Ollama service starts
empty, and pulling is a manual one-time step (models are large; auto-pulling
on every `up` would be a poor default):

```bash
docker compose exec ollama ollama pull llama3.2          # for LLM nodes
docker compose exec ollama ollama pull nomic-embed-text  # only if you'll use Memory nodes
```

If you already run Ollama elsewhere (e.g. shared team hardware, host GPU),
point at it instead of the bundled service by setting `OLLAMA_BASE_URL` in
`.env` and either removing the `ollama` service from `docker-compose.yml` or
just leaving it running unused.

## Connect from the browser

Open `http://localhost:8000` (or the host/port you've mapped it to). You'll
land on a shared password prompt — log in with the `NEXTGEN_APP_PASSWORD`
you set in `.env`. That single password gates both the workflow builder UI
and the chat runtime; there's no per-user login.

From there:

- **Builder** — the canvas where you drag out nodes, wire them together, and save/version workflows.
- **Chat** — a slide-in sidecar (toggle it from the top nav, or click "Run" next to any workflow in the list). It opens on a picker of your saved workflows; click one to start it. The chat pauses on Input nodes and resumes across reconnects/tab closes — reopening the sidecar drops you back into any run that's still waiting on you.

## Managing the Docker stack

`./nextgen.sh` wraps the common `docker compose` commands:

```bash
./nextgen.sh start          # start (builds images the first time)
./nextgen.sh stop           # stop, keep containers/volumes
./nextgen.sh restart        # restart without rebuilding
./nextgen.sh rebuild        # rebuild images from scratch and start (after pulling code changes)
./nextgen.sh down           # stop and remove containers (volumes kept)
./nextgen.sh logs           # follow the app container's logs
./nextgen.sh status         # show container status
./nextgen.sh pull qwen2.5   # download a model into the bundled ollama container
./nextgen.sh help           # list all commands
```

Typing a model name into an LLM node's `model` field doesn't download it —
Ollama only ever uses models that have already been pulled. If Ollama is
running as a container (the default, per `docker-compose.yml`) rather than
installed on your host, `./nextgen.sh pull <model>` is the way to get a new
one in (it's a thin wrapper around `docker compose exec ollama ollama pull
<model>`).

## Configuration reference

All settings are environment variables, set via `.env` (see `.env.example`
for the full annotated list):

| Variable | Purpose |
|---|---|
| `NEXTGEN_APP_PASSWORD` | Shared password gating the UI and chat |
| `NEXTGEN_CREDENTIAL_KEY` | Fernet key encrypting stored credentials at rest |
| `OLLAMA_BASE_URL` | Where the backend reaches Ollama (defaults to the bundled service) |
| `NEXTGEN_EMBEDDING_MODEL` | Embeddings model for Memory nodes (default `nomic-embed-text`) |
| `NEXTGEN_VECTOR_STORE_PATH` | Where Chroma persists vector stores (inside the same data volume as the DB) |

Data (SQLite DB, vector stores) persists in the `nextgen-data` Docker
volume; Ollama's pulled models persist in `ollama-data`. Both survive
`docker compose down` (use `down -v` to wipe them).

## Updating

```bash
git pull
docker compose up -d --build
```

## Further reading

- `specs/001-workflow-builder/quickstart.md` — a runnable end-to-end validation walkthrough (build a workflow, invoke it, verify pause/resume, retry, and sandboxing behavior)
- `specs/001-workflow-builder/spec.md` — full feature spec
- `specs/001-workflow-builder/tasks.md` — implementation task breakdown by user story
