# Autonomous GitHub Code Review Agent

An AI-powered FastAPI service that reviews GitHub pull requests, retrieves repository
context with RAG, runs specialized Claude Sonnet review agents, and posts a structured
Markdown report back to the PR.

## Architecture

```text
GitHub Pull Request Webhook
          |
          v
FastAPI /webhook -> Signature + event validation
          |
          v
GitHubClient -> PR files, metadata, repository structure
          |
          v
ChromaDB RAG -> SentenceTransformer embeddings + relevant code context
          |
          v
LangGraph Workflow
  START
    -> Get PR Data
    -> Retrieve Relevant Code Context
    -> SecurityAgent / Claude Sonnet
    -> PerformanceAgent / Claude Sonnet
    -> CodeQualityAgent / Claude Sonnet
    -> AggregatorAgent
    -> Generate Final Review Report
    -> Post GitHub Comment
  END
```

## Features

- GitHub webhook endpoint for `opened`, `reopened`, and `synchronize` PR events
- Async GitHub REST API client for PR files, metadata, repository trees, and comments
- Claude Sonnet agents for security, performance, and code quality review
- Repository-aware RAG using `sentence-transformers/all-MiniLM-L6-v2` and ChromaDB
- MCP-style tool server exposing PR, search, structure, similar-file, comment, and changed-line tools
- LangGraph-compatible review workflow with a sequential fallback runner
- Markdown report with executive summary, findings, suggested fixes, and a 0-100 score
- Docker, Docker Compose, Railway config, pytest coverage, typed Pydantic models, logging, and retries

## Project Structure

```text
app/          FastAPI app, config, webhook parsing, GitHub client, shared models
agents/       SecurityAgent, PerformanceAgent, CodeQualityAgent, AggregatorAgent
rag/          Embeddings, Chroma vector store, retriever, repository indexer
mcp/          MCP-style tool definitions and stdio server
graph/        LangGraph workflow and typed state
prompts/      Claude system prompts
tests/        Unit tests
```

## Environment Variables

Copy the example file and fill in production values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `ANTHROPIC_MODEL` | Claude model, defaults to `claude-3-5-sonnet-20241022` |
| `GITHUB_TOKEN` | GitHub token with PR read and issue comment write access |
| `GITHUB_WEBHOOK_SECRET` | Shared secret for GitHub webhook signature validation |
| `CHROMA_PATH` | Persistent ChromaDB path |
| `EMBEDDING_MODEL` | SentenceTransformer model |
| `LOG_LEVEL` | Python logging level |

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Check health:

```bash
curl http://localhost:8000/health
```

Open API docs at `http://localhost:8000/docs`.

## Index a Repository

Before reviews, index repository context for better RAG results:

```bash
curl -X POST http://localhost:8000/reindex \
  -H "Content-Type: application/json" \
  -d '{"owner":"octo-org","repo":"example","branch":"main"}'
```

## GitHub Webhook Setup

1. Create a fine-grained GitHub token with pull request read access and issue comment write access.
2. Set `GITHUB_TOKEN` and `GITHUB_WEBHOOK_SECRET` in `.env` or Railway variables.
3. Expose the service with a public URL.
4. Add a repository webhook:
   - Payload URL: `https://your-domain.example/webhook`
   - Content type: `application/json`
   - Secret: same value as `GITHUB_WEBHOOK_SECRET`
   - Events: Pull requests

## Example Review Output

```markdown
# AI Review Report

Overall Score: 87/100

## Executive Summary
Found 2 actionable issue(s) across security, performance, and maintainability.

## Security
Found 1 security issue(s). Highest severity: high.

## Performance
No performance issues found.

## Code Quality
Found 1 maintainability issue(s). Highest severity: low.

## Suggested Fixes
- Move secrets to environment variables or a managed secret store.
```

Patch suggestions are included when Claude returns a `patch` field:

```diff
- password = "123"
+ password = os.getenv("PASSWORD")
```

## MCP Server

Run the lightweight stdio MCP-style server:

```bash
python -m mcp.server
```

Available tools:

- `get_pr_files`
- `search_codebase`
- `get_repo_structure`
- `get_similar_files`
- `post_review_comment`
- `get_changed_lines`

## Docker

```bash
docker build -t github-review-agent .
docker run --env-file .env -p 8000:8000 github-review-agent
```

Or with Compose:

```bash
docker compose up --build
```

## Railway Deployment

1. Create a Railway project from this repository.
2. Add the environment variables from `.env.example`.
3. Railway will use `railway.json` and the `Dockerfile`.
4. Set your GitHub webhook URL to `https://<railway-domain>/webhook`.

## Screenshots

Placeholders:

- GitHub PR review comment screenshot
- FastAPI docs screenshot
- Railway deployment dashboard screenshot
- Chroma indexing logs screenshot

## Testing

```bash
pytest
```

The tests exercise webhook validation, deterministic agent fallbacks, aggregation, and
RAG chunking without requiring live Anthropic, GitHub, or Chroma credentials.
