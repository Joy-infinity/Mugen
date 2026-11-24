"""
Tests for Mugen. Run with:  python -m pytest   (or)   python tests/test_mugen.py
Pure standard library -- no pytest required to run the __main__ path below.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json                                     # noqa: E402
import tempfile                                  # noqa: E402

from mugen.dashboard import aggregate            # noqa: E402
from mugen.detector import Detector            # noqa: E402
from mugen.labyrinth import (                   # noqa: E402
    generate_json_page, generate_page, is_trap_path,
)

BROWSER = {"accept": "text/html", "accept-language": "en", "accept-encoding": "gzip"}
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def test_real_browser_passes():
    d = Detector()
    v = d.inspect("1.2.3.4", BROWSER_UA, BROWSER, "/", hit_honeypot=False)
    assert not v.is_bot, v


def test_curl_like_client_trapped():
    d = Detector()
    v = d.inspect("1.2.3.4", "python-requests/2.31", {}, "/", hit_honeypot=False)
    assert v.is_bot, v


def test_honeypot_is_decisive():
    d = Detector()
    v = d.inspect("9.9.9.9", BROWSER_UA, BROWSER, "/trap/x-1", hit_honeypot=True)
    assert v.is_bot, v


def test_allowlisted_googlebot_never_trapped():
    d = Detector()
    ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    # Even with no browser headers and a honeypot hit, allowlist wins.
    v = d.inspect("66.249.0.1", ua, {}, "/trap/x-1", hit_honeypot=True)
    assert not v.is_bot and v.allowlisted, v


def test_rate_limit_trips():
    d = Detector(rate_limit=5, rate_window_seconds=100.0)
    # A browser-looking client that hammers the server (well past 2x the limit)
    # still gets caught on rate alone.
    last = None
    for _ in range(15):
        last = d.inspect("5.5.5.5", BROWSER_UA, BROWSER, "/", hit_honeypot=False)
    assert last.is_bot, last


def test_ai_agent_trapped_by_name():
    d = Detector()  # trap_ai_agents=True by default
    ua = "Mozilla/5.0 (compatible; GPTBot/1.1; +https://openai.com/gptbot)"
    v = d.inspect("2.2.2.2", ua, BROWSER, "/", hit_honeypot=False)
    assert v.is_bot and v.ai_agent == "gptbot", v


def test_ai_agent_can_be_allowed():
    d = Detector(allow_ai_agents=("gptbot",))
    ua = "Mozilla/5.0 (compatible; GPTBot/1.1; +https://openai.com/gptbot)"
    v = d.inspect("2.2.2.2", ua, BROWSER, "/", hit_honeypot=False)
    assert not v.is_bot and v.ai_agent == "gptbot", v


def test_claudebot_recognized():
    d = Detector()
    ua = "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"
    v = d.inspect("3.3.3.3", ua, BROWSER, "/", hit_honeypot=False)
    assert v.is_bot and v.ai_agent == "claudebot", v


def test_json_maze_is_valid_json_with_links():
    import json
    raw = generate_json_page("/api/items")
    data = json.loads(raw)                    # must parse
    assert data["records"] and data["next"]   # has content and onward links
    assert any("/trap/" in link for link in data["next"])


def test_labyrinth_is_deterministic():
    assert generate_page("/a") == generate_page("/a")
    assert generate_page("/a") != generate_page("/b")


def test_labyrinth_has_links_and_trap():
    page = generate_page("/start")
    assert "<a href=" in page
    assert "/trap/" in page          # a honeypot link is embedded
    assert is_trap_path("/trap/foo") and not is_trap_path("/real")


def _write_log(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8")
    for rec in lines:
        f.write(json.dumps(rec) + "\n")
    f.write("{ this is a broken line\n")  # must be skipped, not crash
    f.close()
    return f.name


def test_dashboard_aggregates_counts():
    import time
    now = time.time()
    path = _write_log([
        {"ts": now, "event": "start"},
        {"ts": now, "event": "trapped", "ip": "1.1.1.1", "path": "/",
         "score": 6, "reasons": ["automation user-agent"], "ai_agent": "gptbot"},
        {"ts": now, "event": "trapped", "ip": "1.1.1.1", "path": "/x",
         "score": 7, "reasons": ["automation user-agent"]},
        {"ts": now, "event": "pass", "ip": "2.2.2.2", "path": "/", "score": 0},
    ])
    s = aggregate(path)
    assert s["total"] == 3 and s["trapped"] == 2 and s["passed"] == 1
    assert s["trap_rate"] == round(100 * 2 / 3, 1)
    assert s["top_ips"][0] == {"label": "1.1.1.1", "count": 2}
    assert s["ai_agents"][0] == {"label": "gptbot", "count": 1}
    assert s["reasons"][0]["label"] == "automation user-agent"
    assert len(s["timeline"]) == 30
    assert s["recent"][0]["event"] == "pass"  # most recent first


def test_dashboard_missing_file_is_safe():
    s = aggregate("/nonexistent/path/mugen.log")
    assert s["total"] == 0 and s["trapped"] == 0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
