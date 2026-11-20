"""Step 1 of the pipeline: download daily climate-model output for every plant from the Open-Meteo Climate API.

Needs internet access. Standard library only. Safe to re-run: finished downloads are skipped, so if the
API rate-limits you, wait and run the same command again.

    python -m pipeline.fetch_climate
    python -m pipeline.fetch_climate --models MRI_AGCM3_2_S EC_Earth3P_HR --sleep 30

Licence: the keyless endpoint is for non-commercial use. A production build needs a paid key (see docs/TICKET.md).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "open_meteo"
ENDPOINT = "https://climate-api.open-meteo.com/v1/climate"
ALL_MODELS = ["MRI_AGCM3_2_S", "EC_Earth3P_HR", "MPI_ESM1_2_XR", "CMCC_CM2_VHR4",
              "FGOALS_f3_H", "HiRAM_SIT_HR", "NICAM16_8S"]
DEFAULT_MODELS = ALL_MODELS[:4]   # four models keep the request weight inside the free tier
VARIABLES = ["temperature_2m_max", "precipitation_sum"]
START, END = "2006-01-01", "2049-12-31"


def cache_path(plant_id: str, model: str) -> Path:
    return RAW / f"{plant_id}_{model}.json"


def build_url(lat: float, lon: float, model: str) -> str:
    query = {"latitude": lat, "longitude": lon, "start_date": START, "end_date": END,
             "models": model, "daily": ",".join(VARIABLES)}
    return f"{ENDPOINT}?{urllib.parse.urlencode(query)}"


def parse_daily(payload: dict, model: str) -> dict:
    """Return {'time': [...], variable: [...]} whether or not the API suffixed the keys with the model name."""
    daily = payload.get("daily") or {}
    if "time" not in daily:
        raise ValueError(f"no daily.time in response: {str(payload)[:200]}")
    out = {"time": daily["time"]}
    for var in VARIABLES:
        series = daily.get(var, daily.get(f"{var}_{model}"))
        if series is None:
            raise ValueError(f"'{var}' missing for {model}")
        if len(series) != len(out["time"]):
            raise ValueError(f"'{var}' length differs from time for {model}")
        out[var] = series
    return out


def fetch(url: str, retries: int = 4, wait: int = 65) -> dict:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nimbus-climate-exposure/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")[:300]
            if err.code == 429 and attempt < retries:
                print(f"    rate-limited (429). Waiting {wait}s, attempt {attempt}/{retries}. {body}")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {err.code}: {body}") from None
        except urllib.error.URLError as err:
            if attempt < retries:
                print(f"    network error ({err.reason}). Retrying in 10s.")
                time.sleep(10)
                continue
            raise RuntimeError(f"network error: {err.reason}") from None
    raise RuntimeError("retries exhausted")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS, choices=ALL_MODELS)
    ap.add_argument("--sleep", type=float, default=20.0, help="seconds between requests (default 20)")
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data" / "plants.csv").open(newline="", encoding="utf-8-sig") as fh:
        plants = [(r["plant_id"].strip(), float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(fh)]

    todo = [(pid, lat, lon, m) for pid, lat, lon in plants for m in args.models
            if args.force or not cache_path(pid, m).exists()]
    total = len(plants) * len(args.models)
    print(f"{total - len(todo)} of {total} downloads already cached; {len(todo)} to fetch.")
    for i, (pid, lat, lon, model) in enumerate(todo, start=1):
        print(f"[{i}/{len(todo)}] {pid} {model}")
        try:
            series = parse_daily(fetch(build_url(lat, lon, model)), model)
        except (RuntimeError, ValueError) as err:
            print(f"\nSTOPPED at {pid} {model}: {err}")
            print("Nothing is lost. If this is a rate limit, wait an hour and run the same command again.")
            return 1
        doc = {"plant_id": pid, "model": model, "latitude": lat, "longitude": lon,
               "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": ENDPOINT, **series}
        tmp = cache_path(pid, model).with_suffix(".tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        tmp.replace(cache_path(pid, model))
        if i < len(todo):
            time.sleep(args.sleep)
    print("All downloads present. Next: python -m pipeline.build_hazards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
