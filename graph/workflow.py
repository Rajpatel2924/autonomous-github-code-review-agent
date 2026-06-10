from __future__ import annotations

import logging
from typing import Any

from agents.aggregator_agent import AggregatorAgent
from agents.performance_agent import PerformanceAgent
from agents.quality_agent import CodeQualityAgent
from agents.security_agent import SecurityAgent
from app.config import Settings
from app.github_client import GitHubClient
from graph.state import ReviewState
from rag.retriever import CodeRetriever
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ReviewWorkflow:
    def __init__(
        self,
        settings: Settings,
        github: GitHubClient | None = None,
        retriever: CodeRetriever | None = None,
    ) -> None:
        self.settings = settings
        self.github = github or GitHubClient(settings)
        self.retriever = retriever or CodeRetriever(VectorStore(settings))
        self.security_agent = SecurityAgent(settings)
        self.performance_agent = PerformanceAgent(settings)
        self.quality_agent = CodeQualityAgent(settings)
        self.aggregator = AggregatorAgent()

    async def close(self) -> None:
        await self.github.close()

    async def run(self, owner: str, repo: str, pull_number: int) -> ReviewState:
        state: ReviewState = {"owner": owner, "repo": repo, "pull_number": pull_number}
        state = await self.get_pr_data(state)
        state = await self.retrieve_relevant_code_context(state)
        state = await self.run_security_review_agent(state)
        state = await self.run_performance_review_agent(state)
        state = await self.run_code_quality_review_agent(state)
        state = await self.aggregate_findings(state)
        state = await self.generate_final_review_report(state)
        state = await self.post_github_comment(state)
        return state

    async def get_pr_data(self, state: ReviewState) -> ReviewState:
        state["pr_context"] = await self.github.get_pull_request(
            state["owner"], state["repo"], state["pull_number"]
        )
        return state

    async def retrieve_relevant_code_context(self, state: ReviewState) -> ReviewState:
        try:
            state["retrieved_context"] = self.retriever.retrieve_for_pr(
                state["pr_context"], self.settings.max_context_chunks
            )
        except Exception as exc:
            logger.warning("RAG retrieval skipped: %s", exc)
            state["retrieved_context"] = []
        return state

    async def run_security_review_agent(self, state: ReviewState) -> ReviewState:
        state["security_review"] = await self.security_agent.review(
            state["pr_context"], state["retrieved_context"]
        )
        return state

    async def run_performance_review_agent(self, state: ReviewState) -> ReviewState:
        state["performance_review"] = await self.performance_agent.review(
            state["pr_context"], state["retrieved_context"]
        )
        return state

    async def run_code_quality_review_agent(self, state: ReviewState) -> ReviewState:
        state["quality_review"] = await self.quality_agent.review(
            state["pr_context"], state["retrieved_context"]
        )
        return state

    async def aggregate_findings(self, state: ReviewState) -> ReviewState:
        state["report"] = self.aggregator.aggregate(
            [state["security_review"], state["performance_review"], state["quality_review"]]
        )
        return state

    async def generate_final_review_report(self, state: ReviewState) -> ReviewState:
        state["markdown"] = self.aggregator.render_markdown(state["report"])
        return state

    async def post_github_comment(self, state: ReviewState) -> ReviewState:
        await self.github.post_review_comment(state["pr_context"], state["markdown"])
        state["posted"] = True
        return state


def build_langgraph_workflow(workflow: ReviewWorkflow) -> Any:
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("Install langgraph to build a compiled LangGraph workflow.") from exc

    graph = StateGraph(ReviewState)
    graph.add_node("get_pr_data", workflow.get_pr_data)
    graph.add_node("retrieve_relevant_code_context", workflow.retrieve_relevant_code_context)
    graph.add_node("run_security_review_agent", workflow.run_security_review_agent)
    graph.add_node("run_performance_review_agent", workflow.run_performance_review_agent)
    graph.add_node("run_code_quality_review_agent", workflow.run_code_quality_review_agent)
    graph.add_node("aggregate_findings", workflow.aggregate_findings)
    graph.add_node("generate_final_review_report", workflow.generate_final_review_report)
    graph.add_node("post_github_comment", workflow.post_github_comment)
    graph.add_edge(START, "get_pr_data")
    graph.add_edge("get_pr_data", "retrieve_relevant_code_context")
    graph.add_edge("retrieve_relevant_code_context", "run_security_review_agent")
    graph.add_edge("run_security_review_agent", "run_performance_review_agent")
    graph.add_edge("run_performance_review_agent", "run_code_quality_review_agent")
    graph.add_edge("run_code_quality_review_agent", "aggregate_findings")
    graph.add_edge("aggregate_findings", "generate_final_review_report")
    graph.add_edge("generate_final_review_report", "post_github_comment")
    graph.add_edge("post_github_comment", END)
    return graph.compile()
