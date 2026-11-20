"""Step 1 of the pipeline: download daily climate-model output for every plant from the Open-Meteo Climate API.

Needs internet access. Standard library only. Safe to re-run: finished downloads are skipped, so you can
stop it at any time and run the same command again.

    python -m pipeline.fetch_climate
    python -m pipeline.fetch_climate --models MRI_AGCM3_2_S EC_Earth3P_HR MPI_ESM1_2_XR

The keyless endpoint counts request weight, not requests. One download here (44 years of two daily
variables) weighs about 230 against limits of 600 a minute, 5,000 an hour and 10,000 a day. That is two
downloads a minute, 21 an hour and 43 a day, so a full run of 36 pauses once on the hourly limit, for up
to an hour, and then carries on by itself.

Licence: the keyless endpoint is for non-commercial use. A production build needs a paid key (see docs/TICKET.md).
"""
from __future__ import annotations

import argparse
import csv
import http.client
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
DEFAULT_MODELS = ALL_MODELS[:4]   # 36 downloads weigh about 8,300: inside the free tier's 10,000 a day
VARIABLES = ["temperature_2m_max", "precipitation_sum"]
START, END = "2006-01-01", "2049-12-31"
# On HTTP 429, by the limit the API's message names: (seconds to wait, times to retry before giving up).
# The daily limit is left out on purpose: waiting does not clear it, so the run stops and says so.
LIMIT_WAITS = {"minutely": (65, 4), "hourly": (600, 7)}
NETWORK_RETRIES = 3


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


def limit_kind(body: str) -> str:
    """Which free-tier limit a 429 names: 'Minutely', 'Hourly' or 'Daily API request limit exceeded'."""
    text = body.lower()
    return next((kind for kind in ("daily", "hourly") if kind in text), "minutely")


def fetch(url: str, sleep=time.sleep) -> dict:
    """One download. Waits out the minute and hour limits; raises RuntimeError when waiting will not help."""
    tries = {"minutely": 0, "hourly": 0, "network": 0}
    while True:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nimbus-climate-exposure/0.1"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")[:300]
            kind = limit_kind(body) if err.code == 429 else None
            if kind not in LIMIT_WAITS or tries[kind] >= LIMIT_WAITS[kind][1]:
                raise RuntimeError(f"HTTP {err.code}: {body}") from None
            wait, limit = LIMIT_WAITS[kind]
            tries[kind] += 1
            print(f"    {kind} limit reached (429). Waiting {wait}s, retry {tries[kind]}/{limit}. {body}", flush=True)
            sleep(wait)
        except (OSError, http.client.HTTPException) as err:   # no connection, timeout, reply cut short
            reason = getattr(err, "reason", None) or str(err) or type(err).__name__
            if tries["network"] >= NETWORK_RETRIES:
                raise RuntimeError(f"network error: {reason}") from None
            tries["network"] += 1
            print(f"    network error ({reason}). Retrying in 10s.", flush=True)
            sleep(10)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS, choices=ALL_MODELS)
    ap.add_argument("--sleep", type=float, default=31.0,
                    help="seconds between requests (default 31: the free tier allows two of these downloads a minute)")
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data" / "plants.csv").open(newline="", encoding="utf-8-sig") as fh:
        plants = [(r["plant_id"].strip(), float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(fh)]

    todo = [(pid, lat, lon, m) for pid, lat, lon in plants for m in args.models
            if args.force or not cache_path(pid, m).exists()]
    total = len(plants) * len(args.models)
    print(f"{total - len(todo)} of {total} downloads already cached; {len(todo)} to fetch.", flush=True)
    for i, (pid, lat, lon, model) in enumerate(todo, start=1):
        print(f"[{i}/{len(todo)}] {pid} {model}", flush=True)
        try:
            series = parse_daily(fetch(build_url(lat, lon, model)), model)
        except (RuntimeError, ValueError) as err:
            print(f"\nSTOPPED at {pid} {model}: {err}")
            print("Nothing is lost: finished downloads are kept. Run the same command again later "
                  "(tomorrow, if the message above names the daily limit).")
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
