# Autonomous GitHub Code Review Agent

An event-driven FastAPI service that reviews GitHub pull requests, detects risky code,
assigns a quality score, and posts a structured report back to the PR.

The project works without an LLM using deterministic checks and can optionally call any
OpenAI-compatible chat-completions API for deeper, context-aware review.

## Features

- Verifies GitHub webhook signatures before processing events
- Reviews PRs when they are opened, reopened, or updated
- Detects common secrets, SQL injection patterns, dynamic execution, disabled TLS,
  bare exception handlers, and unresolved implementation notes
- Tracks findings to added diff line numbers
- Optionally adds structured LLM findings
- Deduplicates findings and calculates a 0-100 quality score
- Posts a readable Markdown report directly on the pull request
- Includes unit tests, Docker packaging, and GitHub Actions CI

## Architecture

```text
GitHub pull_request webhook
          |
          v
FastAPI signature validation
          |
          v
GitHub API -> PR metadata and changed-file patches
          |
          v
Static rules + optional LLM reviewer
          |
          v
Deduplication and quality scoring
          |
          v
GitHub API -> PR review comment
```

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8765
```

Port `8765` is used to avoid conflicts with other local services commonly running on
port `8000`.

Open `http://localhost:8765/docs` for the API documentation. Verify the service with:

```bash
curl http://localhost:8765/health
```

## GitHub Setup

1. Create a fine-grained GitHub token with read access to pull requests and write access
   to issues.
2. Set `GITHUB_TOKEN` and a strong random `GITHUB_WEBHOOK_SECRET` in `.env`.
3. Expose the local server with a tunnel or deploy the container.
4. Add a repository webhook pointing to:

   `https://your-domain.example/webhook/github`

5. Use `application/json`, enter the same webhook secret, and subscribe to pull request
   events.

## Optional LLM Review

Set `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`. The configured provider must expose
an OpenAI-compatible `/chat/completions` endpoint with JSON response-format support.
Static analysis remains active if no key is configured.

## Run Tests

```bash
python -m pytest
```

## Run With Docker

```bash
docker build -t github-review-agent .
docker run --env-file .env -p 8765:8000 github-review-agent
```

## Example Review

```markdown
## Autonomous Code Review

**Quality score:** 78/100

Found 2 actionable issue(s) across the pull request.

| Severity | Category | Location | Finding |
|---|---|---|---|
| HIGH | security | `app/config.py:12` | Possible hardcoded secret |
| MEDIUM | quality | `app/service.py:31` | Bare exception handler |
```

## Resume Bullet

Built an autonomous GitHub code review service with FastAPI, GitHub webhooks, static
analysis, and optional LLM reasoning; generated scored review reports and posted
actionable findings directly to pull requests using a containerized, CI-tested workflow.

## Roadmap

- Repository-aware RAG using embeddings and a vector database
- Inline GitHub review comments rather than a single summary comment
- Language-specific AST analyzers and test generation
- GitHub App authentication for multi-repository installation
- Persistent review history and a metrics dashboard
