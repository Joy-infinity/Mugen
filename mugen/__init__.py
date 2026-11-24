"""
Mugen (無限, "infinity") -- an infinite maze for hostile bots.

Mugen is a defensive tarpit. It detects automated / AI-driven traffic hitting a
website and, instead of serving the real site, feeds the bot an endless maze of
plausible-looking junk pages -- wasting the attacker's time and compute, while
everything stays on your own server.

It is NOT a counter-attack tool. It never touches the attacker's machine.
"""

from .detector import Detector, Verdict
from .labyrinth import generate_page, is_trap_path
from .middleware import MugenMiddleware
from .server import Config, serve

__version__ = "0.1.0"
__all__ = [
    "Detector",
    "Verdict",
    "generate_page",
    "is_trap_path",
    "MugenMiddleware",
    "Config",
    "serve",
]
