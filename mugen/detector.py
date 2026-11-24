"""
Bot detection for Mugen.

The philosophy here is simple and honest: there is no single signal that
perfectly separates a human from a hostile bot. So we don't rely on one.
Instead we add up many weak signals into a *suspicion score*. When the score
crosses a threshold, the visitor is treated as a bot and sent to the labyrinth.

Nothing here is "undetectable" or "impossible to dodge" -- a determined
attacker can mimic a browser. The goal is to make that mimicry expensive and
to catch the overwhelming majority of automated traffic cheaply.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock


# User-agent substrings for crawlers we never want to trap: real search
# engines, accessibility tools, uptime monitors. Lowercase.
DEFAULT_ALLOWED_UA = (
    "googlebot",
    "bingbot",
    "duckduckbot",
    "applebot",
    "slurp",            # Yahoo
    "uptimerobot",
)

# Obvious automation user-agents. Matching one is a strong (not absolute)
# signal. Lowercase.
SUSPICIOUS_UA = (
    "python-requests",
    "curl/",
    "wget/",
    "scrapy",
    "httpclient",
    "go-http-client",
    "aiohttp",
    "libwww",
    "java/",
    "node-fetch",
    "axios/",
    "headlesschrome",
    "phantomjs",
    "bot",
    "crawler",
    "spider",
)

# Known AI agents / LLM crawlers that identify themselves honestly in the
# User-Agent. Many site owners want to trap or throttle these; some want to
# allow a few. Mugen treats them as their own category so you can decide.
# Lowercase substrings.
AI_AGENT_UA = (
    "gptbot",            # OpenAI
    "oai-searchbot",     # OpenAI search
    "chatgpt-user",      # OpenAI ChatGPT browsing
    "claudebot",         # Anthropic
    "claude-web",        # Anthropic
    "anthropic-ai",      # Anthropic
    "perplexitybot",     # Perplexity
    "perplexity-user",   # Perplexity
    "ccbot",             # Common Crawl (feeds many models)
    "bytespider",        # ByteDance
    "google-extended",   # Google AI training
    "meta-externalagent",  # Meta AI
    "amazonbot",         # Amazon
    "applebot-extended",  # Apple AI
    "cohere-ai",         # Cohere
    "diffbot",           # Diffbot
    "imagesiftbot",      # ImageSift
    "omgili",            # Webz.io
    "youbot",            # You.com
)

# Headers a normal browser almost always sends. Their absence is suspicious.
BROWSER_HEADERS = ("accept", "accept-language", "accept-encoding")


@dataclass
class Verdict:
    """The result of inspecting one request."""
    is_bot: bool
    score: int
    threshold: int
    reasons: list[str] = field(default_factory=list)
    allowlisted: bool = False
    ai_agent: str | None = None  # name of the matched AI agent, if any


class Detector:
    """
    Scores requests. Thread-safe: the server is multi-threaded.

    Parameters
    ----------
    threshold:
        Score at or above which a visitor is treated as a bot.
    rate_window_seconds / rate_limit:
        If an IP makes more than `rate_limit` requests within
        `rate_window_seconds`, that is treated as a strong bot signal.
    allow_ua / allow_ips:
        Never-trap lists. Good crawlers and your own monitoring go here.
    """

    def __init__(
        self,
        threshold: int = 5,
        rate_window_seconds: float = 10.0,
        rate_limit: int = 20,
        allow_ua: tuple[str, ...] = DEFAULT_ALLOWED_UA,
        allow_ips: tuple[str, ...] = (),
        trap_ai_agents: bool = True,
        allow_ai_agents: tuple[str, ...] = (),
    ) -> None:
        self.threshold = threshold
        self.rate_window = rate_window_seconds
        self.rate_limit = rate_limit
        self.allow_ua = tuple(u.lower() for u in allow_ua)
        self.allow_ips = set(allow_ips)
        # When True, a self-identified AI agent is trapped outright. Set False
        # to merely note it and let the other signals decide. `allow_ai_agents`
        # lists AI agents you explicitly permit (e.g. "gptbot"); these pass.
        self.trap_ai_agents = trap_ai_agents
        self.allow_ai_agents = tuple(a.lower() for a in allow_ai_agents)

        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _record_and_count(self, ip: str) -> int:
        """Record a hit for this IP and return how many it made in the window."""
        now = time.monotonic()
        cutoff = now - self.rate_window
        with self._lock:
            q = self._hits[ip]
            q.append(now)
            while q and q[0] < cutoff:
                q.popleft()
            return len(q)

    def inspect(
        self,
        ip: str,
        user_agent: str,
        headers: dict[str, str],
        path: str,
        hit_honeypot: bool,
    ) -> Verdict:
        """
        Inspect one request and return a Verdict.

        `headers` keys should be lowercase. `hit_honeypot` is True when the
        requested path is one of our hidden trap links that no human would
        ever visit.
        """
        ua = (user_agent or "").lower()

        # Allowlist wins outright -- we never trap these, whatever they do.
        if ip in self.allow_ips or any(good in ua for good in self.allow_ua):
            return Verdict(
                is_bot=False, score=0, threshold=self.threshold,
                reasons=["allowlisted"], allowlisted=True,
            )

        score = 0
        reasons: list[str] = []
        ai_agent: str | None = None

        # Signal 0: self-identified AI agent / LLM crawler. Checked first so we
        # can report which agent it was regardless of the final decision.
        for name in AI_AGENT_UA:
            if name in ua:
                ai_agent = name
                if name in self.allow_ai_agents:
                    return Verdict(
                        is_bot=False, score=0, threshold=self.threshold,
                        reasons=[f"allowed AI agent: {name}"],
                        allowlisted=True, ai_agent=name,
                    )
                reasons.append(f"AI agent: {name}")
                # If configured to trap AI agents, make the score decisive on
                # its own; otherwise it is just one more signal.
                score += self.threshold if self.trap_ai_agents else 2
                break

        # Signal 1: hidden honeypot link. Enormous signal -- real users can't
        # see these links, so hitting one is almost conclusive.
        if hit_honeypot:
            score += 6
            reasons.append("hit honeypot link")

        # Signal 2: empty or obviously-automated user agent.
        if not ua:
            score += 3
            reasons.append("missing user-agent")
        elif any(bad in ua for bad in SUSPICIOUS_UA):
            score += 4
            reasons.append("automation user-agent")

        # Signal 3: missing headers a real browser sends.
        missing = [h for h in BROWSER_HEADERS if h not in headers]
        if missing:
            score += len(missing)
            reasons.append(f"missing browser headers: {', '.join(missing)}")

        # Signal 4: request rate, scaled by severity. Slightly over the limit
        # is only mildly suspicious (a real person can click fast); far over
        # the limit is strong on its own, so sustained hammering trips even a
        # client that otherwise looks like a browser.
        count = self._record_and_count(ip)
        if count > self.rate_limit * 2:
            score += 6
            reasons.append(f"rate {count}/{self.rate_window:.0f}s far over limit")
        elif count > self.rate_limit:
            score += 3
            reasons.append(f"rate {count}/{self.rate_window:.0f}s over limit")

        is_bot = score >= self.threshold
        return Verdict(
            is_bot=is_bot, score=score, threshold=self.threshold,
            reasons=reasons, ai_agent=ai_agent,
        )
