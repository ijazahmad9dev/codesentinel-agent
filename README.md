# CodeSentinel

A self-healing, multi-agent coding pipeline built with LangChain and LangGraph. Describe what you want in plain language — no file names, no folder structure, no technical detail required — and a team of specialized agents plans it, builds it, tests it, and reviews it against what you actually asked for. Supports Python and JavaScript/TypeScript (Node, Next.js, Express, etc.), auto-detected from your request.

---

## How it works

1. You describe what you want: *"I want a REST API for a small library where I can add books, search them, check them out, and return them."*
2. A **Planner** agent decides whether this is simple (one step) or complex (broken into 2-6 concrete, sequential steps) — you never name files, frameworks, or steps yourself.
3. A **Coding Agent** works through the plan, one step at a time, in the same project sandbox — building incrementally on what earlier steps already created.
4. A **Tester** agent writes a real test suite (happy-path *and* edge cases — empty input, not-found, invalid input, boundary conditions) into `tests/`, then the actual test command is run and its real exit code decides pass/fail — never the model's own self-report.
5. A **Reviewer** agent checks the finished, tested project against what you *originally* asked for — not just "does it run," but "does it do what was requested" — and can actually execute the code to confirm real behavior, not just read it.
6. If either the tester or reviewer finds a real problem, the Coding Agent is invoked again with the exact failure output, fixes it, and the loop re-verifies — routing back through the tester after any fix, before ever reaching the reviewer again.
7. Retries stop automatically when either the same error repeats 3 times, or a shared, configurable total-attempt ceiling is reached — whichever comes first — across the *entire* pipeline, not per-agent.
8. If the local Ollama model is unreachable, every agent falls back to a hosted Groq model automatically, mid-conversation.
9. The terminal shows live progress — which agent is currently working, which step/round it's on, and the running attempt count — so you can watch it work and know it's making progress, not stuck.

---

## Architecture

```
┌─────────┐     ┌──────────────┐     ┌─────────┐     ┌──────────┐
│ Planner   │ ──► │ Coding Agent  │ ──► │ Tester    │ ──► │ Reviewer  │ ──► done
└─────────┘     │ (loops per    │     └────┬────┘     └────┬─────┘
                  │  subtask)     │          │ fail          │ fail
                  └───────▲──────┘          ▼               ▼
                          │            ┌─────────┐    ┌──────────┐
                          └─────────── │ Fix (test) │  │ Fix (review)│
                                       └─────────┘    └──────────┘
```

All agents are LangGraph nodes sharing one state object and one project sandbox (E2B). Each agent wraps a LangChain `create_agent` instance (Ollama primary, Groq fallback via `ModelFallbackMiddleware`) with its own system prompt and tool access — the Coding Agent has full read/write/execute tools, the Reviewer has read/execute only (it cannot modify code; a fix always goes back through the Coding Agent).

Code execution happens in a remote E2B cloud sandbox — one per project, created on first use and reconnected to across the whole pipeline run. There is no local Docker orchestration for code execution; Docker is only used to run the agent app itself.

Inside each project's sandbox:
- `/home/user/project/` — the generated code
- `/home/user/project/tests/` — the tester agent's test suite
- `/home/user/project/PLAN.md` — the plan, with checkboxes ticked as steps complete
- `/home/user/project/TESTS.md` — latest test round, status, and real output
- `/home/user/project/REVIEW.md` — latest review round, status, and notes
- `/home/user/.codesentinel/errors.json` — the shared attempt budget and error-tracking log for the whole pipeline

---

## Directory structure

```
codesentinel/
├── docker/
│   └── Dockerfile
├── download_project.py          # standalone script - run on host, pulls a project to disk
├── src/
│   ├── main.py                    # CLI entry point, live progress display, --inspect mode
│   ├── config.py
│   ├── agent/
│   │   ├── core.py                 # build_chat_models, build_coding_agent, build_planner_model, build_tester_agent, build_reviewer_agent
│   │   ├── prompts.py              # Coding Agent's system prompt
│   │   ├── tools.py                # write_code_to_file, edit_code_in_file, view_file, execute_project_command, list_project_files
│   │   └── graph/
│   │       ├── state.py             # shared GraphState
│   │       ├── build.py             # graph wiring - all nodes and edges
│   │       ├── planner/
│   │       │   ├── prompt.py
│   │       │   ├── logic.py          # generate_plan, parse_subtasks
│   │       │   ├── node.py
│   │       │   └── plan_store.py     # writes PLAN.md
│   │       ├── coding/
│   │       │   └── node.py            # coding_agent_node (subtask loop) + fix_from_tests/fix_from_review
│   │       ├── tester/
│   │       │   ├── prompt.py
│   │       │   ├── node.py
│   │       │   └── test_store.py       # writes TESTS.md
│   │       ├── reviewer/
│   │       │   ├── prompt.py
│   │       │   ├── node.py
│   │       │   └── review_store.py      # writes REVIEW.md
│   │       └── common/
│   │           └── aggregate.py          # final summary + all budget-check routers
│   ├── executor/
│   │   └── sandbox.py              # E2B SDK client
│   └── utils/
│       ├── error_tracker.py         # shared attempt budget, lives inside the project's sandbox
│       ├── code_safety.py           # pre-execution AST safety check
│       ├── model_info.py            # which model (Ollama/Groq) actually handled each call
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
- An [E2B](https://e2b.dev) account and API key (free tier available)
- An [Ollama](https://ollama.ai) instance reachable over HTTP, with a tool-calling-capable model pulled
- A [Groq](https://console.groq.com) API key, used automatically as a fallback if Ollama is unreachable

---

## Setup

```bash
cp .env.example .env
```

```env
OLLAMA_BASE_URL=https://your-ollama-endpoint
MODEL_NAME=qwen3-coder-next:latest

GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL_NAME=openai/gpt-oss-120b

E2B_API_KEY=your_e2b_api_key_here
E2B_TIMEOUT_SECONDS=3600

DATA_DIR=data
EXECUTION_TIMEOUT=60
MAX_AGENT_ITERATIONS=20
```

`MAX_AGENT_ITERATIONS` is the single shared budget for the **entire pipeline** for one project — every tool call across the Coding Agent's subtask loop, every tester round, and every fix round all draw from this one pool. A complex multi-step build can spend a large share of it before testing even starts; raise this for bigger tasks, lower it to fail fast while testing changes.

```bash
docker compose build
```

---

## Running a task

```bash
docker compose run --rm codesentinel python -m src.main "I want a REST API for a small library where I can add books, search them, check them out, and return them" --project library-app
```

Language is auto-detected from the task text. Interactive mode:

```bash
docker compose run --rm codesentinel python -m src.main
```

| Flag | Description |
|---|---|
| `-p, --project` | Project name. Auto-generated from the task text if omitted. |
| `-l, --language` | `python` or `node`. Auto-detected if omitted. |
| `--inspect PROJECT` | View a project's files and error/attempt log. |

To override `MAX_AGENT_ITERATIONS` for a single run without editing `.env`:

```bash
docker compose run --rm -e MAX_AGENT_ITERATIONS=8 codesentinel python -m src.main "..." --project quick-test
```

(A bare shell prefix like `MAX_AGENT_ITERATIONS=8 docker compose run ...` does **not** work — it only sets the variable on your host, not inside the container. Use `-e` as shown above.)

### Reading the terminal output

Each line shows which agent is currently working, its progress, and the running attempt count against the shared budget:

```
→ [Planner]  (total attempts so far: 0)
→ [Coding Agent] [step 2/5]  (total attempts so far: 8)
→ [Tester] [round 1]  (total attempts so far: 14)
→ [Coding Agent (fixing test failure)]  (total attempts so far: 16)
→ [Reviewer] [round 1]  (total attempts so far: 19)
```

If the budget runs out mid-pipeline, you'll see a clear stop message rather than a silent cutoff or crash:

```
⚠ STOPPED: reached the maximum attempt limit (21/20 attempts).
Completed 6 of 6 planned steps before stopping.
```

---

## Inspecting and downloading generated code

**Quick view, from inside the container:**

```bash
docker compose run --rm codesentinel python -m src.main --inspect library-app
```

**Download real files onto your machine**, run directly on your host (not through Docker — it only needs the `e2b` package and your `.env`):

```bash
pip install e2b python-dotenv
python download_project.py library-app
```

Lands at `./project/` by default. Note: downloading a second project reuses the same fixed folder name, so move or rename `./project/` between downloads if you don't want files from different projects mixing together.

---

## Safety design

- **Pre-execution AST check** — refuses code that writes to system paths or uses `socket`/`subprocess`/`ctypes`, before it's ever written.
- **Command complexity rejection** — `execute_project_command` refuses inline multi-line/heredoc-style commands via both a schema length limit and explicit checks, since these are both fragile to generate correctly as structured tool-call output and invite unverifiable complexity.
- **Deterministic pass/fail, never a model's self-report** — both the Tester and Reviewer nodes run real commands via the sandbox and check actual exit codes / a structured `REVIEW_STATUS:` marker; the agent's prose is never trusted for the routing decision.
- **One shared, code-enforced attempt budget** across the whole pipeline (`ErrorTracker`, backed by `MAX_AGENT_ITERATIONS`) — every tool call in every node (`write_code_to_file`, `edit_code_in_file`, `execute_project_command`) increments it, and every routing decision between nodes checks it *before* starting the next phase, not just after. This closes the gap where a node could otherwise start (and burn a full round of work) after the budget was already spent.
- **A same-error cap (3 identical failures)** runs alongside the global budget, using normalized error signatures so different code attempts producing the same root cause still count together.
- **Automatic model fallback** — if Ollama is unreachable, every agent (Planner, Coding Agent, Tester, Reviewer) transparently retries against Groq mid-conversation.
- **Clean failure handling** — unexpected exceptions and LangGraph recursion-limit exhaustion are caught and reported plainly; work already completed is never lost or hidden.

---

## Troubleshooting

**Attempt count overshoots the configured limit slightly**
The budget is checked *between* nodes, not inside a node's own internal tool-call loop — so a single node already in progress when the limit is crossed can finish that round before stopping. This is a bounded, expected overshoot (typically a handful of calls), not a broken cap.

**`Request too large ... tokens per minute` from Groq**
Groq's free tier caps tokens per request. Usually means Ollama has been down long enough that the whole pipeline ran on fallback, which has a materially lower capacity than local Ollama. Check your Ollama endpoint's health directly.

**"Failed to parse tool call arguments as JSON" from Groq**
The model generated a malformed tool call, typically attempting an overly complex inline command. Caught cleanly (no crash, work already done is preserved) but not fully eliminable — a known characteristic of smaller/faster tool-calling models under complex requests.

**A project's files or attempt history seem to have reset**
E2B sandbox persistence (pause/resume) is public beta. If a sandbox expired or was killed, a fresh one is created automatically and the project starts empty. Use `--inspect` to check a project's actual current state.

**`MAX_AGENT_ITERATIONS` override via shell prefix doesn't apply**
Use `docker compose run --rm -e MAX_AGENT_ITERATIONS=N codesentinel ...` — a bare `VAR=value` prefix before `docker compose run` only affects your host shell, not the container, since `docker-compose.yml` doesn't forward arbitrary host env vars by default.

---

## Limitations

- Multi-file scaffolding for larger frameworks is a genuinely harder task for smaller local/fallback models and may consume most of the shared attempt budget before testing or review even begins.
- The Reviewer's verdict is inherently the model's own judgment of "does this match intent" — there's no fully objective check for that the way there is for test pass/fail, though its output is parsed as a structured status marker rather than trusted from loose prose.
- E2B sandbox persistence is public beta; long-term project state across sessions is best-effort, not guaranteed.
- The Groq fallback has a materially lower per-request token capacity than local Ollama, and is intended as a stopgap for outages, not a primary driver for large multi-agent pipeline runs.
- A **Reviewer** agent is implemented; a further escalation/synthesis step beyond it, and a live browser frontend for watching the pipeline work in real time, are both scoped but not yet built.