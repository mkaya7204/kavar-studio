"""D-67 (2026-11-12, the user asked for a full check of the system): two risks open in RISKS.md since 10-24.
- A news story is marked used when its carousel is rendered, before the editor. When the editor gave no answer
  (Claude usage limit: 11-10 had 43 unanswered Claude calls) a good story was used up for nothing.
- cron-job.org starts the day with its own GitHub token; when it stops, nothing fails, the day just starts
  ~7 h late on GitHub's own crons (11-05: 13:54 TRT). `fetch` now says so.
- The cloud installs its Python packages at the versions in constraints.txt, in every workflow."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import daily  # noqa: E402
import news_fetcher  # noqa: E402

from test_daily import sandbox  # noqa: E402,F401  (fixture)

NO_ANSWER = ["editor gave no verdict (success, is_error=True: You've hit your limit · resets 11:30am)"]


def _one_story(monkeypatch, sandbox, tmp_path, problems):  # noqa: F811
    hist, titles = tmp_path / "news_history.json", tmp_path / "news_titles.json"
    monkeypatch.setattr(news_fetcher, "HISTORY_PATH", hist)
    monkeypatch.setattr(news_fetcher, "TITLES_PATH", titles)
    item = {"title": "Meta Teen Accounts", "url": "https://about.fb.com/teen", "source": "Meta"}
    monkeypatch.setattr(daily, "fetch_news", lambda n: [item])
    monkeypatch.setattr(daily, "testable_first", lambda c: c)
    recorded = []
    monkeypatch.setattr(daily.failures, "record", lambda *a, **k: recorded.append(k.get("rendered", True)))

    def produce_news(it):  # what carousel.produce_news does: render, then mark the story used
        news_fetcher.mark_used(it["url"], it["title"])
        return sandbox / "folder"

    monkeypatch.setattr(daily, "produce_news", produce_news)
    monkeypatch.setattr(daily, "_reviewed_news", lambda folder: (False, problems))
    assert daily.produce_news_items(1) == []
    return json.loads(hist.read_text(encoding="utf-8")), json.loads(titles.read_text(encoding="utf-8")), recorded


def test_a_story_the_editor_never_answered_stays_unused(monkeypatch, sandbox, tmp_path):  # noqa: F811
    urls, titles, recorded = _one_story(monkeypatch, sandbox, tmp_path, NO_ANSWER)
    assert urls == [] and titles == []
    assert recorded == [False]  # not a content failure: it never pauses or blocks anything (D-39)


def test_a_story_the_editor_rejected_stays_used(monkeypatch, sandbox, tmp_path):  # noqa: F811
    urls, titles, recorded = _one_story(monkeypatch, sandbox, tmp_path, ["Kapak kaynakta olmayan bir iddia taşıyor"])
    assert urls == ["https://about.fb.com/teen"] and titles == ["meta teen accounts"]
    assert recorded == [True]


# the real run list of 2026-11-12 (gh run list --workflow produce.yml), and 11-05's late day without its 03:17 start
RUNS_1112 = [{"createdAt": "2026-11-12T05:02:59Z", "event": "workflow_dispatch"},
             {"createdAt": "2026-11-12T03:17:11Z", "event": "workflow_dispatch"},
             {"createdAt": "2026-11-11T14:31:51Z", "event": "schedule"}]
RUNS_LATE = [{"createdAt": "2026-11-05T14:45:42Z", "event": "schedule"},
             {"createdAt": "2026-11-05T12:45:15Z", "event": "schedule"},
             {"createdAt": "2026-11-05T10:54:16Z", "event": "schedule"},
             {"createdAt": "2026-11-04T03:17:10Z", "event": "workflow_dispatch"}]


def test_fetch_warns_when_cron_job_org_did_not_start_the_day():
    at = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)  # noqa: E731
    assert daily.morning_start_warning(RUNS_1112, at("2026-11-12T08:00:00")) == ""
    assert "cron-job.org" in daily.morning_start_warning(RUNS_LATE, at("2026-11-05T15:00:00"))
    # before 04:00 UTC the morning in question is yesterday's
    assert daily.morning_start_warning(RUNS_1112, at("2026-11-13T02:00:00")) == ""
    import inspect
    assert "morning_start_warning(runs)" in inspect.getsource(daily.fetch)


def test_every_workflow_installs_the_pinned_packages():
    pins = [line.split("==") for line in (ROOT / "constraints.txt").read_text(encoding="utf-8").split()
            if line and not line.startswith("#")]
    assert len(pins) > 20 and all(len(p) == 2 and p[1] for p in pins)  # exact versions only
    names = {p[0].lower().replace("_", "-") for p in pins}
    for need in (ROOT / "requirements.txt").read_text(encoding="utf-8").split():
        assert need.lower().replace("_", "-") in names, f"{need} has no pinned version"
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in wf.read_text(encoding="utf-8").splitlines():
            if "-r requirements.txt" in line:
                assert "-c constraints.txt" in line, f"{wf.name}: {line.strip()}"
