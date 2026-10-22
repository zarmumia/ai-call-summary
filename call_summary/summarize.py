"""Summarize a call transcript into a CallSummary.

Two engines:
- `ClaudeSummarizer` calls the Anthropic Messages API (set ANTHROPIC_API_KEY).
- `DemoSummarizer` is a tiny rule-based stand-in so the project runs and is
  testable without an API key. It is NOT meant for production.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta

from .redact import redact
from .schema import CallSummary, parse_model_output

PROMPT = """You summarize sales and service phone calls for a small business CRM.
Today is {today}. Read the transcript and return ONLY a JSON object with:
- "summary": 2-3 sentences a colleague can read in 10 seconds
- "client_intent": what the client wants, in a few words
- "next_step": one concrete action
- "next_step_owner": "rep", "client" or "back_office"
- "callback_at": ISO datetime if a callback was promised, else null (resolve "tomorrow", weekdays etc. from today)
- "missing_documents": list of documents the client still needs to send (empty list if none)
- "sentiment": "positive", "neutral", "concerned" or "upset"
- "follow_up_needed": true or false
Write in the language of the transcript. Do not invent facts that are not in the call.

Transcript:
{transcript}"""


class ClaudeSummarizer:
    def __init__(self, api_key: str | None = None, model: str | None = None, max_retries: int = 2):
        self.api_key = api_key or os.environ["ANTHROPIC_API_KEY"]
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        self.max_retries = max_retries

    def _call(self, prompt: str) -> str:
        body = {"model": self.model, "max_tokens": 800, "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return "".join(block.get("text", "") for block in data["content"])

    def summarize(self, transcript: str, now: datetime) -> CallSummary:
        safe, _ = redact(transcript)
        prompt = PROMPT.format(today=now.strftime("%A %Y-%m-%d %H:%M"), transcript=safe)
        last_error = None
        for _ in range(self.max_retries + 1):
            try:
                return parse_model_output(self._call(prompt))
            except ValueError as e:      # invalid output: ask again
                last_error = e
        raise last_error


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DOC_WORDS = ["106", "payslip", "pay slip", "bank statement", "id copy", "pension statement", "tax form"]


class DemoSummarizer:
    """Keyword rules, just enough to demo the pipeline end to end."""

    def summarize(self, transcript: str, now: datetime) -> CallSummary:
        safe, _ = redact(transcript)
        low = safe.lower()

        callback = None
        m = re.search(r"(tomorrow|" + "|".join(WEEKDAYS) + r")[^\d]{0,12}(\d{1,2})(?::(\d{2}))?", low)
        if m:
            day = m.group(1)
            if day == "tomorrow":
                date = now.date() + timedelta(days=1)
            else:
                delta = (WEEKDAYS.index(day) - now.weekday()) % 7 or 7
                date = now.date() + timedelta(days=delta)
            callback = datetime(date.year, date.month, date.day, int(m.group(2)), int(m.group(3) or 0)).isoformat()

        docs = [d for d in DOC_WORDS if d in low]
        upset = any(w in low for w in ["frustrat", "angry", "third time", "nobody called"])
        lines = [l.split(":", 1)[1].strip() for l in safe.splitlines() if l.lower().startswith("client:")]
        intent = lines[0][:80] if lines else "General inquiry"

        if docs:
            step, owner = "Send the client the list of missing documents", "rep"
        elif callback:
            step, owner = "Call the client back as promised", "rep"
        else:
            step, owner = "Review the case and update the client", "rep"

        return CallSummary(
            summary=f"Client call. {'Client sounded upset. ' if upset else ''}"
                    f"{'Callback promised. ' if callback else ''}"
                    f"{'Documents still missing. ' if docs else ''}".strip(),
            client_intent=intent,
            next_step=step,
            next_step_owner=owner,
            callback_at=callback,
            missing_documents=docs,
            sentiment="upset" if upset else "neutral",
            follow_up_needed=bool(callback or docs or upset),
        )
