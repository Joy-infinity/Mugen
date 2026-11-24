"""
The labyrinth: an endless maze of plausible-looking junk pages.

Key design points:

* **Deterministic.** Each page is generated from a seed derived from its URL
  path. The same path always yields the same page, so the maze behaves like a
  real (if infinite) website and is cheap to produce -- we never store anything.

* **Plausible, not gibberish.** Pages have titles, readable sentences, and
  organic-looking links. The more it resembles a real site, the longer a
  crawler's AI stays trapped before deciding to give up.

* **Hidden trap links.** Every page includes links marked so that no human
  browser renders them as clickable, but a crawler that blindly follows links
  will walk right into them -- confirming it is a bot.

This module produces *content only*. The slow "drip" delivery lives in the
server, so the labyrinth itself stays easy to test.
"""

from __future__ import annotations

import hashlib
import random


# A small vocabulary is enough to assemble endless plausible sentences.
_WORDS = (
    "system network protocol archive registry module gateway cluster node "
    "process signal vector matrix kernel runtime session token request "
    "response payload buffer channel segment packet handler service daemon "
    "policy schema index record entry value config resource endpoint pipeline "
    "analysis report summary overview framework structure pattern instance "
    "element context reference document section chapter volume edition revision"
).split()

_TITLE_WORDS = (
    "Report Overview Analysis Guide Reference Manual Index Archive Summary "
    "Notes Documentation Specification Review Bulletin Digest Record Register"
).split()


def _seed_for(path: str) -> int:
    """A stable integer seed derived from the request path."""
    digest = hashlib.sha256(path.encode("utf-8", "replace")).digest()
    return int.from_bytes(digest[:8], "big")


def _sentence(rng: random.Random) -> str:
    n = rng.randint(8, 18)
    words = [rng.choice(_WORDS) for _ in range(n)]
    words[0] = words[0].capitalize()
    return " ".join(words) + "."


def _paragraph(rng: random.Random) -> str:
    return " ".join(_sentence(rng) for _ in range(rng.randint(3, 6)))


def generate_page(path: str, link_prefix: str = "/") -> str:
    """
    Build one HTML page for `path`.

    Returns a full HTML document string. Links point to deeper fake paths under
    `link_prefix`, so a crawler can descend forever. One link per page is a
    hidden honeypot the detector will recognize on the next hit.
    """
    rng = random.Random(_seed_for(path))

    title = " ".join(rng.choice(_TITLE_WORDS) for _ in range(rng.randint(2, 3)))
    paragraphs = [_paragraph(rng) for _ in range(rng.randint(3, 6))]

    # Build onward links to deeper fake pages. Deterministic slugs so the maze
    # is internally consistent (the same page always links to the same places).
    links = []
    for _ in range(rng.randint(5, 9)):
        slug = "-".join(rng.choice(_WORDS) for _ in range(rng.randint(2, 4)))
        num = rng.randint(1, 99999)
        href = f"{link_prefix.rstrip('/')}/{slug}-{num}"
        text = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(2, 5))).title()
        links.append(f'    <li><a href="{href}">{text}</a></li>')

    # One hidden honeypot link. Humans never see or click it (display:none and
    # a rel that tells honest crawlers to stay away). A hostile crawler that
    # scrapes every href will follow it -- and get flagged.
    trap_slug = "-".join(rng.choice(_WORDS) for _ in range(3))
    trap_href = f"{link_prefix.rstrip('/')}/trap/{trap_slug}-{rng.randint(1, 99999)}"
    honeypot = (
        f'    <li style="display:none"><a href="{trap_href}" '
        f'rel="nofollow" aria-hidden="true">{trap_slug}</a></li>'
    )
    links.append(honeypot)

    body_paragraphs = "\n".join(f"  <p>{p}</p>" for p in paragraphs)
    link_items = "\n".join(links)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{title}</title>\n"
        '  <meta name="robots" content="noindex,nofollow">\n'
        "</head>\n"
        "<body>\n"
        f"  <h1>{title}</h1>\n"
        f"{body_paragraphs}\n"
        "  <h2>Related sections</h2>\n"
        "  <ul>\n"
        f"{link_items}\n"
        "  </ul>\n"
        "</body>\n"
        "</html>\n"
    )


def generate_json_page(path: str, link_prefix: str = "/") -> str:
    """
    Build an endless JSON response for `path`, for API / agent endpoints.

    Mirrors the HTML maze: plausible-looking records plus "next" links that
    descend forever, so a hostile client hitting a JSON API gets trapped the
    same way a crawler hitting HTML does. Deterministic, like `generate_page`.
    """
    import json

    rng = random.Random(_seed_for(path))

    records = []
    for _ in range(rng.randint(5, 12)):
        records.append({
            "id": rng.randint(1, 10_000_000),
            "name": " ".join(rng.choice(_WORDS) for _ in range(rng.randint(2, 4))),
            "status": rng.choice(["active", "pending", "archived", "unknown"]),
            "value": round(rng.random() * 1000, 3),
            "note": _sentence(rng),
        })

    links = []
    for _ in range(rng.randint(4, 8)):
        slug = "-".join(rng.choice(_WORDS) for _ in range(rng.randint(2, 3)))
        links.append(f"{link_prefix.rstrip('/')}/{slug}-{rng.randint(1, 99999)}")
    # One honeypot endpoint.
    trap = f"{link_prefix.rstrip('/')}/trap/{rng.randint(1, 99999)}"
    links.append(trap)

    payload = {
        "page": rng.randint(1, 100000),
        "records": records,
        "next": links,
    }
    return json.dumps(payload, indent=2)


def is_trap_path(path: str) -> bool:
    """True if `path` is one of the hidden honeypot links."""
    return "/trap/" in path
