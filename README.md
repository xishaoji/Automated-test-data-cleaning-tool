# Agentic Test-Log Copilot

> LangGraph-based AI agent that cleans and analyzes industrial device test logs inside a **hardened Docker sandbox**.

[![CI](https://github.com/xishaoji/Automated-test-data-cleaning-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/xishaoji/Automated-test-data-cleaning-tool/actions)

## Highlights

| Feature | Description |
|---------|-------------|
| **State-machine agent** | LangGraph workflow with dynamic tool routing, circuit-breaker, and human-in-the-loop escalation |
| **Hardened sandbox** | LLM-generated Pandas code runs in a network-disabled, read-only, resource-limited Docker container |
| **Protocol decoder** | Built-in hex payload parser for heartbeat / charge / alarm frames |
| **Structured config** | `pydantic-settings` driven — every knob is an env var with validation and defaults |
| **Observability** | Rotating file + JSON structured logging; per-request trace via named loggers |
| **CI-ready** | Ruff lint + format, mypy, pytest with coverage, GitHub Actions pipeline |

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit UI (app.py)                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  LangGraph Workflow (core/agent.py)                       │   │
│  │  ┌──────────┐    ┌──────────────────────────────────┐    │   │
│  │  │ Reasoner │◄──►│ ToolNode                          │    │   │
│  │  │  (LLM)   │    │  • execute_python_code            │    │   │
│  │  │          │    │  • parse_communication_protocol   │    │   │
│  │  └──────────┘    └──────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Docker Sandbox (sandbox/container_manager.py)            │   │
│  │  • network_disabled  • read_only rootfs  • cap_drop ALL  │   │
│  │  • mem/cpu/pid limits  • wall-clock timeout              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker Desktop (for sandbox execution)

### 1. Clone & configure

```bash
git clone https://github.com/xishaoji/Automated-test-data-cleaning-tool.git
cd Automated-test-data-cleaning-tool
cp .env.example .env
# Edit .env — fill in your OPENAI_API_KEY (supports DeepSeek / Qwen / any OpenAI-compatible endpoint)
```

### 2. Build the sandbox image (first time only)

```bash
docker build -t pandas-sandbox:latest -f sandbox/Dockerfile ./sandbox
```

### 3a. Run locally (dev mode)

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### 3b. Run with Docker Compose (production-like)

```bash
docker compose up -d
# Open http://localhost:8501
```

## Development

```bash
pip install -r requirements-dev.txt

# Lint & format
ruff check . --fix
ruff format .

# Type check
mypy core tools utils

# Tests (skip Docker-dependent tests without a daemon)
pytest -m "not docker"
```

## Project Structure

```
├── app.py                     # Streamlit entry point
├── core/
│   ├── config.py              # pydantic-settings configuration
│   ├── agent.py               # LangGraph node orchestration
│   ├── prompts.py             # System prompt templates
│   ├── state.py               # TypedDict graph state
│   └── exceptions.py          # Domain exception hierarchy
├── tools/
│   ├── python_sandbox_tool.py # @tool wrapper for sandbox execution
│   └── protocol_parser.py     # Hex protocol decoder tool
├── sandbox/
│   ├── container_manager.py   # Hardened Docker sandbox driver
│   ├── Dockerfile             # Minimal pandas execution image
│   └── requirements.txt       # Sandbox-only deps
├── utils/
│   ├── logger.py              # Structured logging setup
│   └── data_profiler.py       # Data health report generator
├── tests/                     # pytest suite
├── .github/workflows/ci.yml   # GitHub Actions CI
├── docker-compose.yml         # DooD orchestration
├── Dockerfile                 # Main app image
├── pyproject.toml             # Build, ruff, mypy, pytest config
├── requirements.txt           # Production deps
├── requirements-dev.txt       # Dev/test deps
└── .env.example               # Template for secrets
```

## Security Considerations

- **Docker socket**: Mounting `/var/run/docker.sock` grants the web container host-level Docker access. In production, use a [Docker socket proxy](https://github.com/Tecnativa/docker-socket-proxy) to restrict API calls.
- **Sandbox hardening**: Containers run with `network_disabled`, `read_only` rootfs, `cap_drop=ALL`, `no-new-privileges`, and strict resource limits.
- **Secrets**: Never commit `.env`. The `.env.example` file contains only placeholder values.

## License

MIT
