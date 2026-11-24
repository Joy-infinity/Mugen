"""
Generate a realistic sample Mugen log, so you can try the dashboard without
running a live server and waiting for bots.

    python examples/generate_sample_log.py > mugen.log
    python -m mugen.dashboard --log mugen.log

Then open http://127.0.0.1:8090
"""

import json
import random
import sys
import time

AGENTS = ["gptbot", "claudebot", "perplexitybot", "bytespider", "ccbot"]
BOT_UAS = ["python-requests/2.31", "curl/8.4", "Scrapy/2.11", "Go-http-client/2.0"]
HUMAN_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121 Safari/537.36")
REASONS = [
    ["automation user-agent", "missing browser headers: accept-language"],
    ["hit honeypot link"],
    ["rate 61/10s far over limit"],
    ["AI agent: gptbot", "automation user-agent"],
]
PATHS = ["/", "/login", "/api/users", "/products", "/wp-admin", "/.env", "/admin"]
BOT_IPS = ["45.148.10.7", "103.74.19.2", "185.220.101.44", "45.148.10.7",
           "209.141.33.9", "103.74.19.2", "45.148.10.7"]


def main():
    now = time.time()
    lines = []
    lines.append({"ts": round(now - 1800, 3), "event": "start",
                  "host": "0.0.0.0", "port": 8080})
    # 30 minutes of mixed traffic, mostly bots (that's the point of a tarpit).
    for _ in range(420):
        ts = round(now - random.uniform(0, 1800), 3)
        if random.random() < 0.78:  # bot
            rec = {"ts": ts, "event": "trapped", "ip": random.choice(BOT_IPS),
                   "path": random.choice(PATHS), "score": random.randint(5, 12),
                   "reasons": random.choice(REASONS)}
            if random.random() < 0.4:
                rec["ua"] = "compatible; " + random.choice(AGENTS).upper()
                rec["ai_agent"] = random.choice(AGENTS)
            else:
                rec["ua"] = random.choice(BOT_UAS)
                rec["ai_agent"] = None
        else:  # human
            rec = {"ts": ts, "event": "pass", "ip": f"82.14.{random.randint(1,254)}.{random.randint(1,254)}",
                   "ua": HUMAN_UA, "path": random.choice(PATHS[:4]),
                   "score": 0, "allowlisted": False}
        lines.append(rec)
    lines.sort(key=lambda r: r["ts"])
    for rec in lines:
        sys.stdout.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
