"""
Command-line entry point:  python -m mugen [options]
"""

from __future__ import annotations

import argparse
import sys

from .detector import Detector
from .server import Config, serve


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="mugen",
        description="Mugen -- an infinite maze tarpit for hostile bots.",
    )
    p.add_argument("--host", default="127.0.0.1", help="bind address")
    p.add_argument("--port", type=int, default=8080, help="bind port")
    p.add_argument("--threshold", type=int, default=5,
                   help="suspicion score at which a visitor is trapped")
    p.add_argument("--rate-limit", type=int, default=20,
                   help="requests per window before rate counts as bot-like")
    p.add_argument("--rate-window", type=float, default=10.0,
                   help="rate window in seconds")
    p.add_argument("--drip-delay", type=float, default=0.4,
                   help="seconds between chunks when dripping to a bot")
    p.add_argument("--drip-bytes", type=int, default=64,
                   help="bytes per chunk when dripping")
    p.add_argument("--max-drips", type=int, default=50,
                   help="max simultaneous slow responses (resource cap)")
    p.add_argument("--allow-ip", action="append", default=[],
                   help="IP to never trap (repeatable)")
    p.add_argument("--allow-ai-agent", action="append", default=[],
                   help="AI agent to allow, e.g. gptbot (repeatable)")
    p.add_argument("--no-trap-ai-agents", action="store_true",
                   help="don't trap self-identified AI agents on sight; "
                        "let the other signals decide instead")
    p.add_argument("--log-file", default=None,
                   help="append JSON logs to this file (for the dashboard)")
    args = p.parse_args(argv)

    detector = Detector(
        threshold=args.threshold,
        rate_window_seconds=args.rate_window,
        rate_limit=args.rate_limit,
        allow_ips=tuple(args.allow_ip),
        trap_ai_agents=not args.no_trap_ai_agents,
        allow_ai_agents=tuple(args.allow_ai_agent),
    )
    log_stream = sys.stdout
    if args.log_file:
        # Line-buffered append so the dashboard can tail it live.
        log_stream = open(args.log_file, "a", buffering=1, encoding="utf-8")

    cfg = Config(
        host=args.host,
        port=args.port,
        drip_delay=args.drip_delay,
        drip_bytes=args.drip_bytes,
        max_concurrent_drips=args.max_drips,
        detector=detector,
        log_stream=log_stream,
    )
    try:
        serve(cfg)
    finally:
        if log_stream is not sys.stdout:
            log_stream.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
