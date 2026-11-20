"""Writes LABELLED SAMPLE hazard data so the app and tests can run before the real pipeline has.

The numbers are placeholders typed in by hand. They are not model output. The app shows a banner
and scripts/verify.py --release fails while meta.status is 'sample'.

    python -m pipeline.sample_data            # restore data/derived + data/manual sample files
    python -m pipeline.sample_data --fixtures # also refresh tests/fixtures
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# plant: (heat today, heat 2040, heavy-rain days today, 2040, rx1day today, 2040, aqueduct baseline, 2030, 2050)
SAMPLE = {
    "P01": (55, 72, 1.2, 1.6, 78, 88, 4, 4, 4),
    "P02": (60, 78, 2.4, 3.1, 96, 108, 3, 3, 4),
    "P03": (75, 92, 2.8, 3.5, 104, 118, 2, 3, 3),
    "P04": (50, 68, 1.5, 2.0, 84, 95, 3, 4, 4),
    "P05": (28, 45, 2.0, 2.4, 92, 101, 4, 4, 4),
    "P06": (62, 80, 3.2, 4.1, 110, 126, 2, 2, 3),
    "P07": (40, 58, 0.8, 1.2, 70, 82, 4, 4, 4),
    "P08": (12, 22, 5.5, 6.8, 142, 160, 1, 1, 2),
    "P09": (25, 38, 3.4, 4.2, 112, 127, 2, 3, 3),
}
COASTAL = {"P07", "P08"}


def _cell(v: float, spread: float = 0.15) -> dict:
    return {"median": round(v, 1), "min": round(v * (1 - spread), 1), "max": round(v * (1 + spread), 1)}


def hazards_doc() -> dict:
    plants = {}
    for pid, (h0, h1, r0, r1, x0, x1, *_water) in SAMPLE.items():
        plants[pid] = {
            "heat_threshold_c": 37 if pid in COASTAL else 40,
            "heat_days": {"today": _cell(h0), "2040": _cell(h1)},
            "heavy_rain_days": {"today": _cell(r0, 0.3), "2040": _cell(r1, 0.3)},
            "rx1day_mm": {"today": _cell(x0, 0.2), "2040": _cell(x1, 0.2)},
        }
    return {
        "meta": {
            "status": "sample",
            "note": "Hand-typed placeholder values. Not model output. Run the pipeline to replace.",
            "source": "none (sample)",
            "scenario": "n/a",
            "models": [],
            "windows": {"today": [2006, 2025], "2040": [2030, 2049]},
            "generated_at": "sample",
        },
        "plants": plants,
    }


def write(hazards_path: Path, aqueduct_path: Path) -> None:
    hazards_path.parent.mkdir(parents=True, exist_ok=True)
    hazards_path.write_text(json.dumps(hazards_doc(), indent=2) + "\n", encoding="utf-8")
    aqueduct_path.parent.mkdir(parents=True, exist_ok=True)
    with aqueduct_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["plant_id", "baseline_cat", "bau30_cat", "bau50_cat", "status", "source", "looked_up_on"])
        for pid, row in SAMPLE.items():
            w.writerow([pid, *row[6:], "sample", "placeholder - replace from wri.org/aqueduct", ""])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixtures", action="store_true", help="also refresh tests/fixtures")
    args = ap.parse_args()
    write(ROOT / "data" / "derived" / "hazards.json", ROOT / "data" / "manual" / "aqueduct_plants.csv")
    print("Wrote SAMPLE data/derived/hazards.json and data/manual/aqueduct_plants.csv")
    if args.fixtures:
        write(ROOT / "tests" / "fixtures" / "hazards_sample.json", ROOT / "tests" / "fixtures" / "aqueduct_sample.csv")
        print("Wrote tests/fixtures")


if __name__ == "__main__":
    main()
