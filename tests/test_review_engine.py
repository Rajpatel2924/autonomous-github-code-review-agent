from app.models import PullRequestContext, PullRequestFile, Severity
from app.review_engine import build_report, render_markdown, run_static_review


def test_static_review_detects_secret_and_tracks_diff_line() -> None:
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

    findings = run_static_review(context)

    assert len(findings) == 1
    assert findings[0].severity == Severity.high
    assert findings[0].line == 5


def test_report_score_and_markdown() -> None:
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

    report = build_report(run_static_review(context))
    markdown = render_markdown(report)

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

    report = build_report(run_static_review(context))

    assert report.score == 100
    assert report.findings == []
