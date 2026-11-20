"""Step 2 of the pipeline: turn the cached downloads into data/derived/hazards.json (status 'real').

    python -m pipeline.build_hazards

Fails loudly, and writes nothing, if any plant has fewer than MIN_MODELS usable models.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yaml

from pipeline.indicators import days_at_or_above, mean_annual_max, summarise

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "open_meteo"
OUT = ROOT / "data" / "derived" / "hazards.json"
MIN_MODELS = 3


def build(raw_dir: Path, plants: list[dict], assumptions: dict) -> dict:
    """plants: [{'id','coastal'}]. Returns the hazards document. Raises ValueError on thin data."""
    a = {k: v["value"] for k, v in assumptions.items()}
    windows = {"today": a["A01"], "2040": a["A02"]}
    out, models_used = {}, set()
    for p in plants:
        files = sorted(raw_dir.glob(f"{p['id']}_*.json"))
        threshold = a["A04"] if p["coastal"] else a["A03"]
        per = {"heat_days": {h: [] for h in windows}, "heavy_rain_days": {h: [] for h in windows},
               "rx1day_mm": {h: [] for h in windows}}
        for f in files:
            doc = json.loads(f.read_text(encoding="utf-8"))
            models_used.add(doc["model"])
            for h, (y0, y1) in windows.items():
                per["heat_days"][h].append(days_at_or_above(doc["time"], doc["temperature_2m_max"], threshold, y0, y1))
                per["heavy_rain_days"][h].append(days_at_or_above(doc["time"], doc["precipitation_sum"], a["A06"], y0, y1))
                per["rx1day_mm"][h].append(mean_annual_max(doc["time"], doc["precipitation_sum"], y0, y1))
        rec = {"heat_threshold_c": threshold}
        for key, by_h in per.items():
            rec[key] = {}
            for h, vals in by_h.items():
                s = summarise(vals)
                if s is None or s["n_models"] < MIN_MODELS:
                    got = 0 if s is None else s["n_models"]
                    raise ValueError(f"{p['id']} {key} {h}: {got} usable models, need {MIN_MODELS}. "
                                     "Run python -m pipeline.fetch_climate again.")
                rec[key][h] = s
        out[p["id"]] = rec
    return {
        "meta": {
            "status": "real",
            "source": "Open-Meteo Climate API (CMIP6 HighResMIP, bias-corrected and downscaled with ERA5-Land)",
            "scenario": "Single pathway close to RCP8.5; the API offers no other",
            "models": sorted(models_used),
            "windows": windows,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "licence": "CC BY 4.0 (CMIP6 and Open-Meteo)",
        },
        "plants": out,
    }


def main() -> int:
    import csv
    with (ROOT / "data" / "plants.csv").open(newline="", encoding="utf-8-sig") as fh:
        plants = [{"id": r["plant_id"].strip(), "coastal": r["coastal"].strip().upper() == "Y"} for r in csv.DictReader(fh)]
    assumptions = yaml.safe_load((ROOT / "config" / "assumptions.yaml").read_text(encoding="utf-8"))["assumptions"]
    try:
        doc = build(RAW, plants, assumptions)
    except ValueError as err:
        print(f"NOT WRITTEN: {err}")
        return 1
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} from {len(doc['meta']['models'])} models: {', '.join(doc['meta']['models'])}")
    print("Next: python scripts/verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
