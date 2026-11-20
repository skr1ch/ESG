"""Render every page to static HTML in dist/. Two uses:

1. Fallback hosting: if the Python function misbehaves on Vercel, deploy dist/ as a static site
   (`vercel deploy dist --prod`). The custom-price form needs the live app; preset links are frozen.
2. Review: open dist/index.html offline, or let scripts/verify.py audit the output.

    python scripts/freeze.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import views  # noqa: E402
from app.core import data  # noqa: E402


def pages() -> dict[str, str]:
    ds = data.dataset()
    out = {"index.html": views.render_overview(), "method/index.html": views.render_method(),
           "carbon/index.html": views.render_carbon(), "carbon/today/index.html": views.render_carbon(None, "today"),
           "404.html": views.render_not_found()}
    out.update({f"plants/{p.id}/index.html": views.render_plant(p.id) for p in ds.plants})
    return out


def main(dist: Path | None = None, quiet: bool = False) -> Path:
    dist = dist or ROOT / "dist"
    for rel, html in pages().items():
        target = dist / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    if not quiet:
        print(f"Wrote {len(pages())} pages to {dist}")
    return dist


if __name__ == "__main__":
    main()
