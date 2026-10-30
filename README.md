# AI Call Summary

[![XERJ Corpus Hub contributor](https://hub.xerj.org/contributors/zarmumia/badge.svg)](https://hub.xerj.org/contributors/zarmumia)

**Every call documented in the CRM, without the rep typing a word.**

> **About this repo:** a working demo from the [Zarmumia](https://zarmumia.co.il) portfolio. It shows the approach, not a finished product: rules a business owner can read, privacy first, and building on the tools a business already has. In client work it is adapted to the specific CRM and processes.


In small service teams, what happened on a call often lives only in the rep's memory: what the client wanted, what was promised, when to call back. This tool turns a call transcript into a short, structured CRM note with an AI model, and **removes identifying details before anything leaves your system**.

Example of the kind of note it produces from `samples/call_upset_client.txt`:

```
[engine: claude · redacted before sending: {'EMAIL': 1, 'PHONE': 1, 'ID': 1}]

Client called for the third time about a refund filed in the summer and is frustrated.
The file was submitted but the 106 form from the second employer is missing.

Next step (rep): Email the client the list of missing documents
Callback: 2026-10-21T10:00:00
Missing documents: 106 form (second employer)
Client mood: upset
```

## How it works

1. **Transcript in.** Most phone systems can export call transcripts; any text file works.
2. **Redact.** Phone numbers, ID numbers, card numbers and emails are replaced with placeholders such as `[PHONE]` *before* the model sees the text.
3. **Summarize.** Claude returns strict JSON: summary, client intent, next step and its owner, callback time, missing documents, mood. Relative dates ("tomorrow at 10", "Thursday") are resolved to real timestamps.
4. **Validate.** The output is checked field by field. If the model returns something malformed, it's asked again. Bad data never reaches the CRM.
5. **Save.** `--webhook` posts the note and the structured fields to your CRM or to Make / Zapier / n8n, where a callback task can be created automatically.

## Quick start

```bash
# Offline demo, no API key needed (simple keyword rules, for trying the pipeline)
python -m call_summary samples/call_upset_client.txt --demo --now 2026-10-20T12:00

# Real summaries with Claude
export ANTHROPIC_API_KEY=...
python -m call_summary samples/call_new_lead.txt
python -m call_summary samples/call_new_lead.txt --json --webhook https://your-hook-url
```

No dependencies beyond Python 3.10+. The model is configurable with `ANTHROPIC_MODEL`.

## Why it's built this way

- **Privacy by design:** the model gets only what it needs to write a useful note. Redaction is tested.
- **Structured, not free text:** a callback time in a field can become a task automatically. A sentence in a note can't.
- **No invented facts:** the prompt forbids it, and the schema leaves no room for extra claims.
- **Works with the tools you already have:** the output is a webhook payload, so it fits any CRM that accepts one.

## Tests

```bash
pip install pytest && pytest
```

The tests cover redaction, parsing and validating messy model output, date resolution, and the retry path, using a mocked API.

---

Built by **Fanny Rabinovitch · Zarmumia**: operations, automation and AI workflows for small and growing businesses. Sample transcripts are fictional.
