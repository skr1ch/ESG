"""The self-check loop. Run it after every change; it mirrors docs/CHECKLIST.md id for id.

    python scripts/verify.py                 # build checks (must all PASS)
    python scripts/verify.py --release       # also fail on the release gates that need a person
    python scripts/verify.py --url https://your-app.vercel.app    # also check the live deployment

Exit code 0 = build checks pass (and, with --release, every gate is closed).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONE_PAGE_WORDS = 620
PLACEHOLDER = "[YOUR WORDS"
results: list[tuple[str, str, str, str]] = []   # (id, status, title, detail)


def record(cid: str, ok: bool | None, title: str, detail: str = "", gate: bool = False) -> None:
    status = "PASS" if ok else ("NEEDS YOU" if gate else "FAIL")
    results.append((cid, status, title, detail))


def check(cid: str, title: str, gate: bool = False):
    def wrap(fn):
        try:
            ok, detail = fn()
        except Exception as err:  # a crashing check is a failing check
            ok, detail = False, f"{type(err).__name__}: {err}"
        record(cid, ok, title, detail, gate)
        return fn
    return wrap


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", action="store_true", help="fail if any release gate is still open")
    ap.add_argument("--url", help="live deployment to check, e.g. https://nimbus-xyz.vercel.app")
    args = ap.parse_args()

    # ---- T: tests ------------------------------------------------------------------------------
    proc = subprocess.run([sys.executable, "-m", "pytest", "-rs", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True)
    summary = (proc.stdout.strip().splitlines() or ["no output"])[-1]
    http_skipped = "test_app.py" in proc.stdout and "SKIPPED" in proc.stdout
    record("T1", proc.returncode == 0, "Unit and page tests pass", summary)
    if proc.returncode != 0:
        print(proc.stdout[-3000:])

    from app import views
    from app.core import data, network, physical
    from scripts import freeze

    ds = data.load_dataset()
    with (ROOT / "data" / "plants.csv").open(newline="", encoding="utf-8-sig") as fh:
        raw = list(csv.DictReader(fh))

    def col(name: str) -> float:
        return sum(float(r[name]) for r in raw)

    # ---- D: data reconciles to the source file (recomputed here, independently of app code) ------
    @check("D1", "Group totals on screen equal the plant file")
    def _():
        rev, s1 = col("revenue_fy2025_26_inr_cr"), col("scope1_co2_fy2025_26_kt")
        page = views.render_overview() + views.render_method()
        ok = f"₹{rev:,.0f} cr" in page and f"{s1:,.0f} kt" in page and len(raw) == len(ds.plants)
        return ok, f"{len(raw)} plants, revenue ₹{rev:,.0f} cr, Scope 1 {s1:,.0f} kt"

    @check("D2", "Clinker balance closes (produced = consumed, shipped = received)")
    def _():
        produced, shipped = col("clinker_produced_fy2025_26_mt"), col("clinker_shipped_fy2025_26_mt")
        consumed = sum(network.clinker_consumed(p, ds.flows) for p in ds.plants)
        moved = sum(f.clinker_mt for f in ds.flows)
        return abs(produced - consumed) < 0.005 and abs(shipped - moved) < 0.005, \
            f"produced {produced:.2f} Mt, consumed {consumed:.2f} Mt, shipped {shipped:.2f} Mt, flows {moved:.2f} Mt"

    @check("D3", "Emission allocation conserves the group total")
    def _():
        alloc = sum(e.allocated_kt for e in network.allocate_emissions(ds.plants, ds.flows).values())
        return abs(alloc - col("scope1_co2_fy2025_26_kt")) < 0.5, f"allocated {alloc:,.1f} kt"

    @check("D4", "Exposure never exceeds group revenue; bands add up")
    def _():
        r = physical.plant_readings(ds)
        rev = col("revenue_fy2025_26_inr_cr")
        worst = 0.0
        for hz, by_h in physical.all_exposures(ds, r).items():
            for e in by_h.values():
                if abs(sum(e.revenue_by_band) + e.unrated_cr - rev) > 0.5 or e.total_cr > rev + 0.5:
                    return False, f"{hz} {e.horizon} does not reconcile"
                worst = max(worst, e.share)
        return True, f"largest exposure share {worst:.0%}"

    # ---- V: pages --------------------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        dist = freeze.main(Path(tmp), quiet=True)
        html = {str(p.relative_to(dist)): p.read_text(encoding="utf-8") for p in dist.rglob("*.html")}

    def text_of(doc: str) -> str:
        return re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", " ", doc, flags=re.S))

    @check("V1", "Every page renders with no template leaks")
    def _():
        expected = 5 + len(ds.plants)
        leaks = [f"{name}: {tok}" for name, doc in html.items() for tok in ("None", "nan", "Undefined", "{{", "{%")
                 if tok in text_of(doc)]
        return len(html) == expected and not leaks, f"{len(html)} pages" + (f"; leaks {leaks[:3]}" if leaks else "")

    @check("V2", "Internal links resolve")
    def _():
        valid = {"/", "/carbon", "/method"} | {f"/plants/{p.id}" for p in ds.plants}
        bad = sorted({h for doc in html.values() for h in re.findall(r'href="(/[^"]*)"', doc)
                      if h.split("#")[0].split("?")[0] not in valid})
        return not bad, f"broken: {bad}" if bad else "all internal links point at a real page"

    @check("V3", "Sample data is flagged on every page, and only when data is sample")
    def _():
        is_sample = "sample" in (ds.climate_status, ds.water_status)
        wrong = [n for n, doc in html.items() if ('class="flag"' in doc) != is_sample]
        return not wrong, f"climate={ds.climate_status}, water={ds.water_status}" + (f"; wrong on {wrong}" if wrong else "")

    @check("V4", "No external scripts; pages work without JavaScript")
    def _():
        scripts = [n for n, doc in html.items() if "<script" in doc]
        return not scripts, "no <script> tags" if not scripts else f"scripts in {scripts}"

    # ---- A: assumptions --------------------------------------------------------------------------
    @check("A1", "Every assumption id used in code exists, and every assumption is shown beside a figure")
    def _():
        defined = set(ds.assumptions)
        code = "".join(p.read_text(encoding="utf-8") for d in ("app", "pipeline") for p in (ROOT / d).rglob("*")
                       if p.suffix in (".py", ".html"))
        used_in_code = set(re.findall(r"""['"](A\d{2})['"]""", code)) | set(re.findall(r"assumptions\.(A\d{2})", code))
        shown = {a for doc in html.values() for a in re.findall(r'href="/method#(A\d{2})"', doc)}
        missing, unshown = used_in_code - defined, defined - shown
        return not missing and not unshown, \
            f"{len(defined)} assumptions" + (f"; undefined {sorted(missing)}" if missing else "") + (f"; never shown {sorted(unshown)}" if unshown else "")

    # ---- P: paperwork ----------------------------------------------------------------------------
    docs = {n: (ROOT / "docs" / n) for n in ("TICKET.md", "PROCESS_NOTE.md")}

    @check("P1", "Ticket and process note exist and fit one page each")
    def _():
        counts = {n: len(p.read_text(encoding="utf-8").split()) if p.exists() else 0 for n, p in docs.items()}
        ok = all(0 < c <= ONE_PAGE_WORDS for c in counts.values())
        return ok, ", ".join(f"{n} {c} words" for n, c in counts.items()) + f" (limit {ONE_PAGE_WORDS})"

    # ---- G: release gates that need a person -----------------------------------------------------
    record("G1", ds.climate_status == "real", "Climate data is real model output, not sample",
           "run: python -m pipeline.fetch_climate, then python -m pipeline.build_hazards (needs internet)"
           if ds.climate_status != "real" else f"models: {', '.join(ds.hazards['meta']['models'])}", gate=True)
    record("G2", ds.water_status == "real", "Water-stress categories come from Aqueduct, not sample",
           "fill data/manual/aqueduct_plants.csv from the Aqueduct Water Risk Atlas and set status=real"
           if ds.water_status != "real" else "all rows marked real", gate=True)
    record("G3", proc.returncode == 0 and not http_skipped, "HTTP tests ran against FastAPI",
           "skipped here: pip install -r requirements-dev.txt, then re-run" if http_skipped else "ran", gate=True)
    open_notes = [n for n, p in docs.items() if p.exists() and PLACEHOLDER in p.read_text(encoding="utf-8")]
    record("G4", all(p.exists() for p in docs.values()) and not open_notes, "Process note is in your own words (no placeholders left)",
           f"still marked {PLACEHOLDER}...] in {open_notes}" if open_notes else "no placeholders", gate=True)
    if args.url:
        try:
            base = args.url.rstrip("/")
            with urllib.request.urlopen(f"{base}/healthz", timeout=30) as r:
                health = json.loads(r.read().decode())
            with urllib.request.urlopen(f"{base}/", timeout=30) as r:
                home_ok = r.status == 200 and b"Nimbus Cement" in r.read()
            live = home_ok and health.get("climate_data") == "real" and health.get("water_data") == "real"
            record("G5", live, "Live link opens without a login and serves real data", f"{base} -> {health}", gate=True)
        except Exception as err:
            record("G5", False, "Live link opens without a login and serves real data", f"{args.url}: {err}", gate=True)
    else:
        record("G5", False, "Live link opens without a login and serves real data",
               "deploy to Vercel, then re-run with --url <link>; also open it in a private window", gate=True)

    # ---- report ----------------------------------------------------------------------------------
    width = max(len(t) for _, _, t, _ in results)
    print("\nNimbus climate exposure: verification\n" + "=" * 38)
    for cid, status, title, detail in results:
        print(f"{cid:<3} {status:<9} {title:<{width}}  {detail}")
    failed = [c for c, s, *_ in results if s == "FAIL"]
    gates = [c for c, s, *_ in results if s == "NEEDS YOU"]
    print("=" * 38)
    print(f"Build checks: {'ALL PASS' if not failed else 'FAILED ' + ', '.join(failed)}")
    print(f"Release gates: {'ALL CLOSED - ready to submit' if not gates else 'open ' + ', '.join(gates) + ' (see docs/CHECKLIST.md)'}")
    return 1 if failed or (args.release and gates) else 0


if __name__ == "__main__":
    sys.exit(main())
