"""CLI: python -m call_summary samples/call_upset_client.txt [--demo] [--now ISO] [--webhook URL]"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .redact import redact
from .summarize import ClaudeSummarizer, DemoSummarizer

BUSINESS_TZ = ZoneInfo("Asia/Jerusalem")


def main() -> None:
    p = argparse.ArgumentParser(description="Turn a call transcript into a structured CRM note.")
    p.add_argument("transcript", help="Path to a .txt transcript")
    p.add_argument("--demo", action="store_true", help="Use the offline rule-based engine (no API key)")
    p.add_argument("--now", help="Treat this ISO datetime as 'now' (for resolving 'tomorrow')")
    p.add_argument("--webhook", help="POST the result to a CRM / automation webhook")
    p.add_argument("--json", action="store_true", help="Print JSON instead of a readable note")
    args = p.parse_args()

    text = Path(args.transcript).read_text(encoding="utf-8")
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(BUSINESS_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=BUSINESS_TZ)
    use_demo = args.demo or not os.environ.get("ANTHROPIC_API_KEY")
    engine = DemoSummarizer() if use_demo else ClaudeSummarizer()

    _, removed = redact(text)
    result = engine.summarize(text, now)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        engine_name = "demo" if use_demo else "claude"
        print(f"[engine: {engine_name} · redacted before sending: {removed or 'nothing'}]\n")
        print(result.to_crm_note())

    if args.webhook:
        req = urllib.request.Request(
            args.webhook,
            data=json.dumps({"summary": result.to_dict(), "note": result.to_crm_note()}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"\nWebhook responded {r.status}")


if __name__ == "__main__":
    main()
