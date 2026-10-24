"""Screenshot app/story.html at 1440 px and 390 px, and fail on console errors or horizontal overflow.

    uv run python scripts/check_story.py            # writes docs/story-1440.png, docs/story-390.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = (ROOT / "app" / "story.html").as_uri()


def main() -> int:
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, hash_ in ((1440, "#all"), (390, "#all"), (1440, "")):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors: list[str] = []
            page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
            page.goto(URL + hash_)
            page.wait_for_timeout(1500)
            over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            tag = f"{width}{'-start' if not hash_ else ''}"
            if errors:
                problems.append(f"{tag}: console errors: {errors}")
            if over > 0:
                wide = page.evaluate("""() => [...document.querySelectorAll('body *')]
                  .filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
                  .slice(0, 6).map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))""")
                problems.append(f"{tag}: horizontal overflow {over}px: {wide}")
            if hash_:
                page.screenshot(path=str(ROOT / "docs" / f"story-{width}.png"), full_page=True)
            else:
                page.click("#bNext")
                page.wait_for_timeout(300)
                for _ in range(8):
                    page.keyboard.press("ArrowRight")
                    page.wait_for_timeout(120)
                sent = page.inner_text("#hapTitle")
                if not sent:
                    problems.append("step-through: empty panel sentence")
                print(f"step-through ok: {sent!r}")
            print(f"{tag}: errors={len(errors)} overflow={over}")
            page.close()
        browser.close()
    for pr in problems:
        print("PROBLEM", pr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
