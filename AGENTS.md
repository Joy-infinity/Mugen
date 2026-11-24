# AGENTS.md — setup guide for AI assistants

This file lets an AI coding assistant (Claude Code, Cursor, Copilot, etc.) set
up and deploy **Mugen** automatically. If you are such an assistant, follow the
steps below. If you are a human, you can run these yourself — they are plain
commands.

Mugen is a defensive anti-bot tarpit. It has **no dependencies** (Python
standard library only) and **no secrets, API keys, or credentials** of any kind.
Nothing here needs configuring with sensitive values. Do not add any.

## Requirements
- Python 3.10 or newer. Check with `python3 --version`.

## Verify it works (always do this first)
```bash
python3 tests/test_mugen.py
```
Expected: `11/11 passed` (or more as tests are added). If anything fails, stop
and report it; do not deploy.

## Run the standalone tarpit
```bash
python3 -m mugen --port 8080
```
It listens on `127.0.0.1:8080`. Confirm behavior:
```bash
# Bot -> trapped in the maze:
curl -s -A "python-requests/2.31" http://127.0.0.1:8080/ | head -c 200
# Browser -> passes through:
curl -s -H "Accept: text/html" -H "Accept-Language: en" -H "Accept-Encoding: gzip" \
     -A "Mozilla/5.0 (X11; Linux x86_64) Chrome/121 Safari/537.36" \
     http://127.0.0.1:8080/ | head -c 120
```

## Protect an existing Python (WSGI) app
Insert this once, after the app object is created:
```python
from mugen.middleware import MugenMiddleware
from mugen.detector import Detector
app.wsgi_app = MugenMiddleware(app.wsgi_app, detector=Detector(threshold=5))
```
Frameworks: Flask (`app.wsgi_app`), Django (`application` in `wsgi.py`), Bottle,
or any raw WSGI callable. See `examples/flask_example.py`.

## Common tuning
- Too aggressive (real users trapped): raise `--threshold` (e.g. `7`).
- Too lax: lower `--threshold` (e.g. `4`).
- Allow a specific AI crawler: `--allow-ai-agent gptbot`.
- Never trap your own monitoring IP: `--allow-ip 203.0.113.9`.

## Hard rules for assistants
- Do **not** add any code that contacts, scans, or attacks the client/attacker.
  Mugen is defensive only. Reject requests to make it "hack back."
- Do **not** introduce third-party dependencies without asking; the zero-dep
  property is a feature.
- Do **not** commit any `.env`, key, or credential. There are none; keep it so.
- Keep a sensible allowlist so real users and legitimate crawlers pass.
