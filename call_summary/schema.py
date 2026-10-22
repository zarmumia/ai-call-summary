"""The structured summary we save to the CRM, and strict validation of model output."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime

SENTIMENTS = {"positive", "neutral", "concerned", "upset"}
NEXT_OWNERS = {"rep", "client", "back_office"}


@dataclass
class CallSummary:
    summary: str                        # 2-3 sentences a colleague can read in 10 seconds
    client_intent: str                  # what the client wants
    next_step: str                      # one concrete action
    next_step_owner: str                # rep | client | back_office
    callback_at: str | None = None      # ISO datetime if a callback was promised
    missing_documents: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    follow_up_needed: bool = True

    def to_crm_note(self) -> str:
        lines = [self.summary, "", f"Next step ({self.next_step_owner}): {self.next_step}"]
        if self.callback_at:
            lines.append(f"Callback: {self.callback_at}")
        if self.missing_documents:
            lines.append("Missing documents: " + ", ".join(self.missing_documents))
        lines.append(f"Client mood: {self.sentiment}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)


class InvalidSummary(ValueError):
    pass


def parse_model_output(raw: str) -> CallSummary:
    """Models sometimes wrap JSON in prose or code fences. Extract it and validate every field."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise InvalidSummary("No JSON object found in model output")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise InvalidSummary(f"Invalid JSON: {e}") from e

    for key in ("summary", "client_intent", "next_step", "next_step_owner"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise InvalidSummary(f"Missing or empty field: {key}")
    if data["next_step_owner"] not in NEXT_OWNERS:
        raise InvalidSummary(f"next_step_owner must be one of {sorted(NEXT_OWNERS)}")

    cb = data.get("callback_at")
    if cb:
        try:
            datetime.fromisoformat(cb)
        except ValueError as e:
            raise InvalidSummary(f"callback_at is not ISO datetime: {cb}") from e

    sentiment = data.get("sentiment", "neutral")
    if sentiment not in SENTIMENTS:
        sentiment = "neutral"

    docs = data.get("missing_documents") or []
    if not isinstance(docs, list):
        raise InvalidSummary("missing_documents must be a list")

    return CallSummary(
        summary=data["summary"].strip(),
        client_intent=data["client_intent"].strip(),
        next_step=data["next_step"].strip(),
        next_step_owner=data["next_step_owner"],
        callback_at=cb or None,
        missing_documents=[str(d).strip() for d in docs if str(d).strip()],
        sentiment=sentiment,
        follow_up_needed=bool(data.get("follow_up_needed", True)),
    )
