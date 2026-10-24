"""Open every Commonwatt page at 1440 px and 390 px; fail on console errors or horizontal overflow.

    uv run python scripts/check_story.py            # also writes docs/<page>-1440.png and docs/<page>-390.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["index.html", "story.html", "history.html", "member.html", "about.html", "presentation/commonwatt-story.html"]
SHOTS = {"story.html": "story", "index.html": "landing", "history.html": "history", "member.html": "member",
         "about.html": "about", "presentation/commonwatt-story.html": "scenes"}


def main() -> int:
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for rel in PAGES:
            f = ROOT / "app" / rel
            if not f.exists():
                continue
            for width in (1440, 390):
                page = browser.new_page(viewport={"width": width, "height": 900})
                errors: list[str] = []
                page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
                page.goto(f.as_uri() + ("#all" if rel == "story.html" else ""))
                page.wait_for_timeout(1500)
                over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                nav = page.evaluate("!!document.querySelector('nav.cw-nav')")
                errors = [e for e in errors if "fonts.g" not in e and "net::ERR" not in e]
                tag = f"{rel} @{width}"
                if errors:
                    problems.append(f"{tag}: console errors: {errors[:3]}")
                if over > 0:
                    problems.append(f"{tag}: horizontal overflow {over}px")
                if not nav:
                    problems.append(f"{tag}: shared nav missing")
                page.screenshot(path=str(ROOT / "docs" / f"{SHOTS[rel]}-{width}.png"), full_page=width == 1440)
                print(f"{tag}: errors={len(errors)} overflow={over} nav={nav}")
                page.close()
        # replay still steps with the keyboard
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto((ROOT / "app" / "story.html").as_uri())
        page.wait_for_timeout(800)
        page.click("#bNext")
        for _ in range(8):
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(100)
        sent = page.inner_text("#hapTitle")
        print(f"replay step-through: {sent!r}")
        if not sent:
            problems.append("replay: empty panel sentence")
        browser.close()
    for pr in problems:
        print("PROBLEM", pr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
