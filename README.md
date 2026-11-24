<p align="center">
  <img src="assets/logo.png" alt="Mugen logo" width="180">
</p>

<h1 align="center">Mugen (無限)</h1>
<p align="center"><em>An infinite maze for hostile bots.</em></p>

> *Mugen* means "infinity." In Jujutsu Kaisen, the technique *Infinity* stops
> any attack by slowing it forever as it approaches — it never actually lands.
> This tool does the same thing to hostile bots: they approach your real site
> but never arrive, stuck crawling an endless maze instead.

Mugen is a defensive **tarpit**. It detects automated / AI-driven traffic —
scrapers, scanners, and AI agents that hammer or probe your website or server —
and, instead of serving your real content, feeds them an endless maze of
plausible-looking junk pages. The bot wastes its time and compute going nowhere.

**Everything happens on your own server.** Mugen never touches the attacker's
machine, never "hacks back," and makes no claim of being unbeatable. It is a
trap on your property, not a weapon. See [Ethics & legality](#ethics--legality).

---

## What it does

- **Detects bots with many signals, not one.** Request rate, missing browser
  headers, automation user-agents, hidden honeypot links, and named AI agents
  are each scored; the total decides. No single trick to bypass.
- **Recognizes AI agents by name** — GPTBot, ClaudeBot, PerplexityBot,
  Bytespider, CCBot and more — so you can trap, allow, or throttle each.
- **Protects web pages *and* APIs.** HTML crawlers get an HTML maze; JSON/API
  clients get an endless JSON maze. Your server endpoints are covered too.
- **Slow-drip delivery** ties up the bot's workers for as long as they'll wait.
- **Protects real users.** Google, Bing, screen readers, and any IP or AI agent
  you allowlist always pass through untouched.
- **Logs everything** as JSON so you can block offending IPs at your firewall.
- **Caps its own resource use** so the tarpit can't be turned against you.
- **Zero dependencies.** Pure Python standard library. Runs anywhere.

---

## Quick start

```bash
git clone https://github.com/Joy-infinity/Mugen.git
cd Mugen
python3 -m mugen --port 8080
```

Then, from another terminal:

```bash
# A bot-like client falls into the maze:
curl -A "python-requests/2.31" http://127.0.0.1:8080/

# A browser-like request passes through:
curl -H "Accept: text/html" -H "Accept-Language: en" -H "Accept-Encoding: gzip" \
     -A "Mozilla/5.0 ... Chrome/121 Safari/537.36" http://127.0.0.1:8080/
```

In production you point your reverse proxy (nginx, Caddy) at Mugen for paths you
want protected, or use the middleware below to guard an existing app directly.

---

## Protect an existing Python site (middleware)

Any WSGI framework — Flask, Django, Bottle — in three lines:

```python
from mugen.middleware import MugenMiddleware
from mugen.detector import Detector

app.wsgi_app = MugenMiddleware(app.wsgi_app, detector=Detector(threshold=5))
```

A complete runnable example is in [`examples/flask_example.py`](examples/flask_example.py).

---

## Options

Run `python3 -m mugen --help`. The most useful:

| Flag | Meaning | Default |
|------|---------|---------|
| `--port` / `--host` | where to listen | `8080` / `127.0.0.1` |
| `--threshold` | suspicion score at which a visitor is trapped | `5` |
| `--rate-limit` / `--rate-window` | requests per window before rate counts as bot-like | `20` / `10s` |
| `--drip-delay` / `--drip-bytes` | pace of the slow drip to trapped bots | `0.4s` / `64` |
| `--max-drips` | max simultaneous slow responses (resource cap) | `50` |
| `--allow-ip` | an IP to never trap (repeatable) | — |
| `--allow-ai-agent` | an AI agent to allow, e.g. `gptbot` (repeatable) | — |
| `--no-trap-ai-agents` | don't trap AI agents on sight; let other signals decide | off |

---

## How detection works

Each request earns a suspicion score. When it reaches the threshold, the visitor
is trapped. Signals include:

- **Named AI agent** (GPTBot, ClaudeBot, …) — decisive by default, allowlistable.
- **Hidden honeypot link** — a link no human browser shows; following it is
  near-conclusive.
- **Automation user-agent** — `python-requests`, `curl`, `scrapy`, empty UA, …
- **Missing browser headers** — real browsers send `Accept`, `Accept-Language`,
  `Accept-Encoding`.
- **Request rate** — scaled by severity, so a fast human isn't trapped but
  sustained hammering is.

Allowlisted search engines, AI agents, and IPs bypass all of this. Tune
`--threshold` to taste: lower is more aggressive (and more likely to catch a
real visitor), higher is gentler.

> **Honest limitation:** a determined attacker can forge browser headers and
> throttle their rate to look human. No tarpit stops that completely. Mugen
> raises the cost and stops the overwhelming majority of automated traffic — it
> does not promise to catch 100%. Anyone who promises that is selling something.

---

## Ethics & legality

Mugen is **purely defensive**:

- It only ever serves content from **your own server**. It does not scan,
  exploit, or send anything to the attacker's machine.
- It does **not** "hack back," damage the attacker, or exhaust their account
  beyond the compute they spend voluntarily crawling your maze.
- Wasting a bot's time by serving it pages on your own site is the same right
  any website has to decide what to serve whom.

Please still use it responsibly: keep a sensible allowlist so you don't trap
real users or legitimate services, and respect the laws of your jurisdiction.

---

## Support Mugen

Mugen is free and open source, and always will be. If it saved your server some
pain, you can fuel the infinite maze with a coffee's worth of crypto — every bit
keeps the void spinning. 🌀

- **EVM (ETH, BNB, and USDT/USDC on those networks):**
  `0x54b45AC3c26EE8C3d3823eD3B7d0AA19F7a95479`
- **Solana (SOL, and USDT/USDC on Solana):**
  `5RaSo1uZ1RyZaSq5FcMnzRFyC2KpDuRnJpVURfA8rnCV`
- **BTC:** `bc1qhecrn9glsp79scjvaxjp2cx2adn84y0w3pwu6n`

Thank you for keeping the bots lost. ∞

---

## License

MIT — see [LICENSE](LICENSE). Contributions welcome.
