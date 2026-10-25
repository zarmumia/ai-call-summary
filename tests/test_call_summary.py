import io
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from call_summary.redact import redact
from call_summary.schema import InvalidSummary, parse_model_output
from call_summary.summarize import ClaudeSummarizer, DemoSummarizer

SAMPLES = Path(__file__).parent.parent / "samples"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))  # a Tuesday


def test_redaction_removes_identifiers():
    text, counts = redact("Call me at 052-123-4567 or +972 54 765 4321, ID 012345678, a@b.co")
    assert "4567" not in text and "012345678" not in text and "a@b.co" not in text
    assert counts["PHONE"] == 2 and counts["ID"] == 1 and counts["EMAIL"] == 1


def test_parse_accepts_fenced_json():
    raw = 'Here you go:\n```json\n{"summary":"S","client_intent":"I","next_step":"N","next_step_owner":"rep","callback_at":"2026-10-21T10:00:00","missing_documents":["106"],"sentiment":"upset"}\n```'
    s = parse_model_output(raw)
    assert s.callback_at == "2026-10-21T10:00:00" and s.missing_documents == ["106"]


@pytest.mark.parametrize("raw", [
    "no json here",
    '{"summary":"S","client_intent":"I","next_step":"N","next_step_owner":"boss"}',
    '{"summary":"","client_intent":"I","next_step":"N","next_step_owner":"rep"}',
    '{"summary":"S","client_intent":"I","next_step":"N","next_step_owner":"rep","callback_at":"tomorrow"}',
])
def test_parse_rejects_bad_output(raw):
    with pytest.raises(InvalidSummary):
        parse_model_output(raw)


def test_unknown_sentiment_falls_back_to_neutral():
    s = parse_model_output('{"summary":"S","client_intent":"I","next_step":"N","next_step_owner":"rep","sentiment":"meh"}')
    assert s.sentiment == "neutral"


def test_demo_upset_client():
    s = DemoSummarizer().summarize((SAMPLES / "call_upset_client.txt").read_text(), NOW)
    assert s.sentiment == "upset"
    assert s.callback_at == "2026-10-21T10:00:00+03:00"
    assert "106" in s.missing_documents
    assert "052-123-4567" not in s.to_crm_note()


def test_demo_resolves_weekday():
    s = DemoSummarizer().summarize((SAMPLES / "call_new_lead.txt").read_text(), NOW)
    assert s.callback_at == "2026-10-22T17:30:00+03:00"  # Thursday


def test_claude_engine_redacts_and_retries(monkeypatch):
    sent, replies = [], iter(["not json", '{"summary":"S","client_intent":"I","next_step":"N","next_step_owner":"rep"}'])
    eng = ClaudeSummarizer(api_key="test")
    monkeypatch.setattr(eng, "_call", lambda prompt: (sent.append(prompt), next(replies))[1])
    s = eng.summarize("Client: my number is 050-111-2233", NOW)
    assert s.summary == "S" and len(sent) == 2
    assert "050-111-2233" not in sent[0] and "[PHONE]" in sent[0]


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


GOOD = (b'{"content":[{"type":"text","text":"{\\"summary\\":\\"S\\",\\"client_intent\\":\\"I\\",'
        b'\\"next_step\\":\\"N\\",\\"next_step_owner\\":\\"rep\\"}"}]}')


def test_api_rate_limit_is_retried(monkeypatch):
    import call_summary.summarize as sm
    calls = []

    def fake(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down", {}, None)
        return _Resp(GOOD)

    monkeypatch.setattr(sm.urllib.request, "urlopen", fake)
    s = ClaudeSummarizer(api_key="test", sleep=lambda x: None).summarize("Client: hi", NOW)
    assert s.next_step == "N" and len(calls) == 2


def test_api_auth_error_is_not_retried(monkeypatch):
    import call_summary.summarize as sm
    calls = []

    def fake(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 401, "bad key", {}, None)

    monkeypatch.setattr(sm.urllib.request, "urlopen", fake)
    with pytest.raises(urllib.error.HTTPError):
        ClaudeSummarizer(api_key="test", sleep=lambda x: None).summarize("Client: hi", NOW)
    assert len(calls) == 1


def test_demo_callback_keeps_timezone():
    s = DemoSummarizer().summarize("Client: call me tomorrow at 10", NOW)
    assert s.callback_at is not None and s.callback_at.endswith("+03:00")
