import pytest

from agents.aggregator_agent import AggregatorAgent
from agents.security_agent import SecurityAgent
from app.config import Settings
from app.models import PullRequestContext, PullRequestFile, Severity


@pytest.mark.asyncio
async def test_security_agent_detects_secret_and_tracks_diff_line() -> None:
    context = PullRequestContext(
        owner="octo",
        repo="demo",
        number=1,
        title="Add configuration",
        files=[
            PullRequestFile(
                filename="app.py",
                status="modified",
                patch='@@ -4,2 +4,3 @@\n existing = True\n+API_KEY = "123456789"\n+safe = True',
            )
        ],
    )

    review = await SecurityAgent(Settings()).review(context, [])

    assert len(review.findings) == 1
    assert review.findings[0].severity == Severity.high
    assert review.findings[0].line == 5


def test_aggregator_score_and_markdown() -> None:
    context = PullRequestContext(
        owner="octo",
        repo="demo",
        number=1,
        title="Risky change",
        files=[
            PullRequestFile(
                filename="query.py",
                status="modified",
                patch='@@ -0,0 +1 @@\n+query = f"SELECT * FROM users WHERE id={user_id}"',
            )
        ],
    )
    review = SecurityAgent(Settings()).fallback_review(context)
    report = AggregatorAgent().aggregate([review])
    markdown = AggregatorAgent().render_markdown(report)

    assert report.score == 85
    assert "Possible SQL injection" in markdown
    assert "`query.py:1`" in markdown


def test_clean_diff_scores_100() -> None:
    context = PullRequestContext(
        owner="octo",
        repo="demo",
        number=1,
        title="Clean change",
        files=[
            PullRequestFile(
                filename="math.py",
                status="modified",
                patch="@@ -0,0 +1 @@\n+answer = 42",
            )
        ],
    )

    report = AggregatorAgent().aggregate([SecurityAgent(Settings()).fallback_review(context)])

    assert report.score == 100
    assert report.findings == []
