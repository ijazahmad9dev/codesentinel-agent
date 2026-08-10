# CodeSentinel

A self-healing coding agent built with LangChain. It takes a natural-language task, writes code, executes it inside an isolated per-project Docker container, and — if execution fails — reads the real error, fixes the code, and retries, up to a hard safety limit. Supports Python and Node.js/JavaScript projects.

---

## How it works

1. You give it a task (and optionally a project name and language).
2. The agent decides what files are needed and writes them with `write_code_to_file`, following a modular structure (separate files for logic, entry point, and tests — not one giant script).
3. It verifies the code with `execute_project_command`, running the real command for that stack (`python3 main.py`, `npm install && npm run build`, etc.) inside a dedicated, isolated Docker container for that project.
4. If it fails, the real stderr is fed back to the model, which fixes the specific file that's broken and retries.
5. Retries stop automatically when either:
   - The *same* error occurs 3 times in a row, or
   - The project hits 6 total execution attempts, regardless of whether the errors differ.
6. On success, the agent reports which files were saved and how to run them.

Every project gets its **own container**, created once and reused across the whole task. Files and error logs live inside that container — nothing is written to your host filesystem — so you can inspect exactly what the agent produced with plain `docker` commands at any time.

---

## Architecture

```
┌─────────────────────┐        ┌──────────────────────┐        ┌─────────────────────────┐
│  codesentinel        │  HTTP  │  executor              │ docker │  codesentinel-proj-<name> │
│  (agent, LangChain,  │ ─────► │  (FastAPI, owns the    │ ─────► │  (one persistent          │
│  Ollama LLM)         │        │  Docker socket)         │        │  container per project)   │
└─────────────────────┘        └──────────────────────┘        └─────────────────────────┘
```

- **`codesentinel`** — the main agent app. No Docker socket access at all. Talks to the executor over plain HTTP.
- **`executor`** — the *only* component with Docker socket access. Its job is narrow: create/reuse a project's container, write files into it, run commands in it, and report results back. This isolates the one component that needs elevated Docker access from the agent's own reasoning loop.
- **`codesentinel-proj-<project>`** — a disposable-but-persistent container per project, hardened with dropped capabilities, resource limits, and a non-root user. Holds `/app/project` (the agent's code) and `/app/.codesentinel` (internal error-tracking state, kept separate from your actual code).

---

## Directory structure

```
codesentinel/
├── docker/
│   └── Dockerfile                  # main agent app image
├── executor/
│   ├── app.py                      # FastAPI service, owns the Docker socket
│   ├── Dockerfile
│   ├── requirements.txt
│   └── runner-images/
│       ├── python.Dockerfile       # pre-owned /app/project + /app/.codesentinel
│       └── node.Dockerfile
├── src/
│   ├── main.py                     # CLI entry point
│   ├── config.py
│   ├── agent/
│   │   ├── core.py                 # create_agent + ChatOllama wiring
│   │   ├── prompts.py              # system prompt (modular code rules, retry rules)
│   │   └── tools.py                # write_code_to_file, execute_project_command, list_project_files
│   ├── executor/
│   │   └── sandbox.py              # HTTP client for the executor service
│   └── utils/
│       ├── error_tracker.py        # per-project error tracking (lives inside the container)
│       ├── code_safety.py          # pre-execution AST safety check
│       └── logger.py
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .dockerignore
└── README.md
```

---

## Prerequisites

- Docker and Docker Compose
- An [Ollama](https://ollama.ai) instance reachable over HTTP — either running locally with a tunnel (e.g. Cloudflare Tunnel), or on a remote host. Ollama must be bound to `0.0.0.0`, not just `localhost`, or containers won't be able to reach it.
- A tool-calling-capable model pulled in Ollama (e.g. `qwen2.5-coder:7b`). Not every model supports reliable tool calling — verify yours does before relying on this.

---

## Setup

**1. Clone and configure environment variables**

```bash
cp .env.example .env
```

Edit `.env`:

```env
OLLAMA_BASE_URL=https://your-ollama-endpoint
MODEL_NAME=qwen2.5-coder:7b
DATA_DIR=data
WORKSPACE_DIR=workspace
EXECUTOR_URL=http://executor:8000
EXECUTION_TIMEOUT=15
MAX_AGENT_ITERATIONS=10
```

**2. Build the language runner images** (these have `/app/project` and `/app/.codesentinel` pre-owned by UID 1000, avoiding a runtime chown that would otherwise be blocked by dropped capabilities)

```bash
docker build -t codesentinel-runner-python:latest -f executor/runner-images/python.Dockerfile executor/runner-images
docker build -t codesentinel-runner-node:latest -f executor/runner-images/node.Dockerfile executor/runner-images
```

**3. Pre-pull the base images** (avoids a first-run timeout while Docker fetches them mid-execution)

```bash
docker pull python:3.11-slim
docker pull node:20-slim
```

**4. Build and start the executor**

```bash
docker compose build
docker compose up -d executor
```

---

## Running a task

```bash
docker compose run --rm codesentinel python -m src.main "write a function that reverses a string and test it" --project reverse-demo
```

Options:

| Flag | Description |
|---|---|
| `-p, --project` | Project name (namespaces the container and its files). Auto-generated from the task text if omitted. |
| `-l, --language` | `python` (default) or `node`. |

Interactive mode (no task argument) prompts for task, project, and language:

```bash
docker compose run --rm codesentinel python -m src.main
```

---

## Inspecting generated code and error logs

Every project's files live inside its own container, not on your host. Use `docker exec`/`docker cp` directly:

```bash
# List files
docker exec codesentinel-proj-<project> ls -la /app/project/

# Read a file
docker exec codesentinel-proj-<project> cat /app/project/main.py

# View the project's error log
docker exec codesentinel-proj-<project> cat /app/.codesentinel/errors.json

# Interactive shell inside the project's container
docker exec -it codesentinel-proj-<project> sh

# Pull the whole project folder onto your host (e.g. to open in an editor)
docker cp codesentinel-proj-<project>:/app/project ./inspect/<project>
```

To delete a project's container and start fresh:

```bash
docker rm -f codesentinel-proj-<project>
```

---

## Safety design

- **Per-project container isolation** — each project runs in its own container with `--cap-drop ALL`, `--security-opt no-new-privileges`, non-root user, and CPU/memory/PID limits.
- **Pre-execution AST check** (`code_safety.py`) — refuses obviously unsafe code (writes to system paths outside the project, use of `socket`/`subprocess`/`ctypes`) before it ever reaches the container.
- **Automatic, per-project error tracking** — every execution attempt is logged inside the project's own container, independent of whether the model remembers to call any logging tool.
- **Two independent retry caps**, both enforced in code, not just prompted:
  - **3 identical errors** (normalized by error signature, not exact text — so different code attempts producing the same root-cause error still count together) → `MAX_RETRIES_REACHED`.
  - **6 total execution attempts** for a project, regardless of whether errors repeat → `GLOBAL_ATTEMPT_LIMIT_REACHED`. This is the real backstop against a model that produces a different failure every retry, which would otherwise never trip the first cap.
- **Modular code generation** — the system prompt requires separating logic, entry points, and tests into distinct files, and checking existing project structure (`list_project_files`) before writing, rather than regenerating everything into one file on every change.

**Known trade-off:** project containers have network access by default (required for `pip install` / `npm install`), so they do **not** have the strong `--network none` isolation an ephemeral, single-file-only sandbox could offer. This is a deliberate choice for this architecture — see "Limitations" below.

---

## Troubleshooting

**`Recursion limit reached` crash instead of a clean stop**
Should not happen under normal operation — the global attempt cap is designed to stop the agent before LangGraph's recursion limit is hit. If it does, check `data`/`.codesentinel/errors.json` inside the project's container for what the agent was attempting; it likely means a tool call was silently failing without incrementing the tracked attempt count.

**Permission denied errors when the agent tries to write or run code**
Confirm the runner images were rebuilt after any Dockerfile change:
```bash
docker build -t codesentinel-runner-python:latest -f executor/runner-images/python.Dockerfile executor/runner-images
```
Ownership must be baked in at image build time — `chown` at runtime will fail once capabilities are dropped, even as root.

**Changes to `executor/app.py` don't seem to take effect**
`docker compose build` alone is not enough for a long-running service. Force-recreate it:
```bash
docker compose build
docker compose up -d --force-recreate executor
```

**First Node.js task times out**
The `node:20-slim` image likely wasn't pulled yet — the pull itself can exceed `EXECUTION_TIMEOUT`. Pre-pull it: `docker pull node:20-slim`.

**Ollama connection refused from inside the container**
Ollama must be bound to `0.0.0.0`, not `127.0.0.1` — `OLLAMA_HOST=0.0.0.0 ollama serve`. If running Ollama on the host with Docker on native Linux, you also need `host.docker.internal` mapped via `extra_hosts` in `docker-compose.yml`, or use a tunnel URL directly.

---

## Limitations

- Multi-file scaffolding for larger frameworks (a full Next.js app, for example) is a genuinely harder task for smaller local models and may hit the retry caps more often than single-file Python tasks — this is a model-capability ceiling, not a pipeline bug.
- Project containers have network access by default, which is necessary for dependency installation but is a real (and intentional) isolation trade-off compared to a fully network-isolated sandbox.
- The pre-execution AST safety check is a best-effort static layer, not a substitute for the container-level isolation (dropped capabilities, resource limits) — it catches obvious cases, not everything.
- `docker exec` without an explicit `--user` flag falls back to the image's configured user, not the `--user` passed at `docker run` time — every exec call in `executor/app.py` pins `--user` explicitly for this reason; keep that pattern if extending the executor further.