# CodeSentinel

A self-healing coding agent built with LangChain. Describe what you want in plain language — no file names, no folder structure, no technical detail required — and it writes the code, verifies it runs, and fixes it automatically if something breaks. Supports Python and JavaScript/TypeScript (Node, Next.js, Express, etc.), auto-detected from your request.

---

## How it works

1. You describe what you want: *"I want a FastAPI backend for user management"*, *"build me a to-do app in Next.js"*.
2. The agent infers the language, the project structure, and the file layout using standard professional conventions for whatever stack is implied — you never need to specify any of this yourself.
3. It writes the files, then verifies with a simple check (e.g. confirming the code imports/compiles cleanly) — it deliberately avoids complex, fragile verification like spinning up a live server and making test requests.
4. If verification fails, it reads the real error, makes a targeted fix to the specific broken part (not a full rewrite), and re-verifies.
5. Retries stop automatically when either the same error repeats 3 times, or a configurable total-attempt ceiling is reached — whichever comes first.
6. If the local Ollama model is unreachable, it falls back to a hosted Groq model automatically, mid-conversation, with no manual intervention.
7. The final answer is written for a non-technical reader: what was built, confirmation it was verified, and the one command to run it.

---

## Architecture

```
┌───────────────────────┐        ┌─────────────────────────┐
│  codesentinel           │  API  │  E2B cloud sandbox         │
│  (agent: LangChain      │ ────► │  (one per project,          │
│  create_agent, Ollama   │       │  isolated, persists          │
│  primary / Groq         │       │  across the session)         │
│  fallback)               │       │                              │
└───────────────────────┘        └─────────────────────────┘
```

There is no local Docker orchestration anymore. Each project gets its own remote E2B sandbox — an isolated cloud environment with its own filesystem — created on first use and reconnected to on subsequent calls within the same project. The agent talks to E2B directly via its SDK; there's no separate executor service or Docker socket involved.

A local file (`data/e2b_sandbox_map.json`) maps project names to their E2B sandbox IDs, so a project can be reconnected across separate CLI invocations. If a sandbox has expired or been killed (E2B's persistence/pause-resume is still public beta), a fresh one is created automatically and the project starts clean — this is a known, accepted trade-off, not a guarantee of permanent state.

Inside each sandbox:
- `/home/user/project/` — the agent's generated code
- `/home/user/.codesentinel/errors.json` — per-project error tracking and attempt counter, kept separate from your actual code

---

## Directory structure

```
codesentinel/
├── docker/
│   └── Dockerfile              # main agent app image (no Docker socket, no executor)
├── src/
│   ├── main.py                  # CLI entry point, language auto-detection, --inspect mode
│   ├── config.py
│   ├── agent/
│   │   ├── core.py              # create_agent + Ollama primary / Groq fallback wiring
│   │   ├── prompts.py           # structure conventions, verification rules, non-technical output
│   │   └── tools.py             # write_code_to_file, edit_code_in_file, execute_project_command, list_project_files
│   ├── executor/
│   │   └── sandbox.py           # E2B SDK client
│   └── utils/
│       ├── error_tracker.py     # per-project error tracking (lives inside the sandbox)
│       ├── code_safety.py       # pre-execution AST safety check
│       └── logger.py
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .dockerignore
└── README.md
```

---

## Prerequisites

- Docker and Docker Compose (used only to run the agent app itself — no longer needed for code execution)
- An [E2B](https://e2b.dev) account and API key (free tier available)
- An [Ollama](https://ollama.ai) instance reachable over HTTP, with a tool-calling-capable model pulled (e.g. `qwen2.5-coder:7b`)
- A [Groq](https://console.groq.com) API key, used automatically as a fallback if Ollama is unreachable

---

## Setup

**1. Configure environment variables**

```bash
cp .env.example .env
```

```env
OLLAMA_BASE_URL=https://your-ollama-endpoint
MODEL_NAME=qwen2.5-coder:7b

GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL_NAME=openai/gpt-oss-120b

E2B_API_KEY=your_e2b_api_key_here
E2B_TIMEOUT_SECONDS=3600

DATA_DIR=data
EXECUTION_TIMEOUT=60
MAX_AGENT_ITERATIONS=10
```

`MAX_AGENT_ITERATIONS` is the single configurable ceiling on total execution attempts per project — raise it for tasks that legitimately need more back-and-forth (larger multi-file scaffolds), lower it to fail faster during testing.

**2. Build and run**

```bash
docker compose build
```

---

## Running a task

```bash
docker compose run --rm codesentinel python -m src.main "I want a FastAPI backend for user management" --project user-mgmt
```

Language is detected automatically from the task text (mentions of Next.js, React, JavaScript, npm, etc. route to Node; everything else defaults to Python) — `--language` is optional and only needed to override the guess.

Options:

| Flag | Description |
|---|---|
| `-p, --project` | Project name. Auto-generated from the task text if omitted. |
| `-l, --language` | `python` or `node`. Auto-detected if omitted. |
| `--inspect PROJECT` | View a project's files and error log without running a new task. |

Interactive mode:

```bash
docker compose run --rm codesentinel python -m src.main
```

Just answers "what would you like built?" — no project name or language prompt, both are inferred.

---

## Inspecting generated code and error logs

Since code now lives in a remote E2B sandbox rather than a local Docker container, use the built-in inspect mode rather than `docker exec`:

```bash
docker compose run --rm codesentinel python -m src.main --inspect user-mgmt
```

This prints every file's path and full contents, plus the project's raw error-tracking log (including the total-attempt counter), pulled live from that project's sandbox.

---

## Safety design

- **Pre-execution AST check** (`code_safety.py`) — refuses obviously unsafe code (writes to system paths, use of `socket`/`subprocess`/`ctypes`) before it's written.
- **Command complexity rejection** — `execute_project_command` refuses commands that look like inline multi-line scripts (heredocs, embedded subprocess/threading wrappers) — both because they're fragile to generate correctly as structured tool-call output, and because they invite exactly the kind of unverifiable complexity the agent is instructed to avoid. The tool's schema also enforces a hard length limit on the command field itself, since structural schema constraints are respected more reliably by tool-calling models than prose instructions alone.
- **Automatic, per-project error tracking**, stored in the project's own sandbox — not dependent on the model remembering to call a logging tool.
- **Two independent retry caps**, both enforced in code:
  - **3 identical errors** (normalized by error signature, so different code attempts producing the same root-cause error still count together) → stop.
  - **`MAX_AGENT_ITERATIONS` total execution attempts** for a project, regardless of whether errors repeat → stop. This is the real backstop against a model that produces a different failure every retry.
- **Automatic model fallback** — if Ollama is unreachable, `ModelFallbackMiddleware` transparently retries the failed call against Groq mid-conversation.
- **Clean failure handling** — unexpected exceptions (including malformed tool-call generation from either model provider, and LangGraph recursion-limit exhaustion) are caught at the top level and reported plainly, rather than crashing with a raw traceback. Files already written are preserved either way.

---

## Troubleshooting

**"Failed to parse tool call arguments as JSON" / `groq.BadRequestError`**
The model generated a malformed tool call, usually while attempting an overly complex inline command. This is a known, somewhat irreducible characteristic of smaller/faster tool-calling models under complex requests — the fix is graceful failure (already handled) plus steering the model toward simpler verification via the system prompt and the command-length schema constraint, not full elimination.

**`Request too large ... tokens per minute` from Groq**
Groq's free tier caps tokens per request. This typically means Ollama has been down longer than expected and the whole task has been running on fallback, which has a lower capacity ceiling than local Ollama. Check your Ollama endpoint's health directly; this error is a symptom of that outage, not a bug in the task itself.

**`GLOBAL_ATTEMPT_LIMIT_REACHED` on a project that should be fresh**
The attempt counter is per-project and persists across separate CLI invocations, including ones that crashed for unrelated reasons (e.g. the JSON parsing bug above still increments toward the cap in some cases). If a project has accumulated attempts across multiple troubleshooting sessions, start a new project name rather than continuing to invest attempts into one that's already near its ceiling. Check with `--inspect` first.

**Ollama connection refused**
Ollama must be bound to `0.0.0.0`, not `127.0.0.1` (`OLLAMA_HOST=0.0.0.0 ollama serve`). If using a tunnel (e.g. Cloudflare), confirm the URL is still live — tunnel URLs can expire or break independently of Ollama itself.

**A project's files seem to have disappeared between sessions**
E2B sandbox persistence (pause/resume) is public beta with documented edge cases. If a sandbox expired or was killed, CodeSentinel creates a fresh one automatically and the project starts empty — this is accepted, silent-by-design behavior, not an error you'll be notified about explicitly. Use `--inspect` to check a project's actual current state before assuming prior work is still there.

---

## Limitations

- Multi-file scaffolding for larger frameworks is a genuinely harder task for smaller local/fallback models and may hit retry caps more often than single-file Python tasks — a model-capability ceiling, not a pipeline bug.
- E2B sandbox persistence is public beta; long-term project state across sessions is best-effort, not guaranteed.
- The pre-execution AST safety check and command-complexity rejection are best-effort layers, not exhaustive guarantees — they reduce risk and failure rate, they don't eliminate either category entirely.
- The Groq fallback has a materially lower per-request token capacity than local Ollama, and is intended as a stopgap for outages, not a primary driver for large multi-file tasks.