"""Bundle the dashboard and all generated hotel data into one self-contained HTML file.

dashboard/embed.html normally loads data/hotel_index.js and data/hotels/<id>.js with script tags.
This inlines the index in place of its script tag and every hotel file right after the loader
(which defines window.HOTEL_PROFIT_LOAD), so each hotel's payload is cached before the page
boots and nothing is fetched. The output opens from anywhere, with no server or data folder.

The output contains internal hotel IDs from confidential Hilton data: share it only where the
data-rights policy allows.

Run: python -m src.build_standalone   (after python -m src.hotel_profit_export)
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard"
OUT = DASH / "hilton_dashboard_standalone.html"
INDEX_TAG = '<script src="data/hotel_index.js"></script>'
LOADER_END = "})();\n</script>"


def inline(js: str) -> str:
    # A literal "</script" inside the data would end the inline block early.
    return "<script>\n" + js.replace("</", "<\\/") + "\n</script>"


def run():
    html = (DASH / "embed.html").read_text()
    index = (DASH / "data" / "hotel_index.js").read_text()
    hotels = sorted((DASH / "data" / "hotels").glob("*.js"))
    if not hotels:
        raise SystemExit("No hotel files in dashboard/data/hotels: run python -m src.hotel_profit_export first.")
    if html.count(INDEX_TAG) != 1 or LOADER_END not in html:
        raise SystemExit("embed.html no longer has the expected index tag / loader; update build_standalone.py.")

    html = html.replace(INDEX_TAG, inline(index))
    at = html.index(LOADER_END) + len(LOADER_END)
    bundle = "\n".join(p.read_text() for p in hotels)
    html = html[:at] + "\n" + inline(bundle) + html[at:]

    OUT.write_text(html)
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(hotels)} hotels, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    run()
