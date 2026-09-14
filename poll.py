#!/usr/bin/env python3
"""Tuya Cloud -> events.jsonl -> api/data.json.  Runs on GitHub Actions; no LAN.

The cloud keeps a ~4 day rolling window of the five official DPs (6/7/8/22/24),
which is everything logbook.derive() needs. Vendor DPs (101/124) only ever come
from a local watch.py run and are left untouched here.
"""
import datetime, json, os, sys, time
from zoneinfo import ZoneInfo
import tinytuya, logbook

# ponytail: cloud gives epoch ms; watch.py wrote naive *local* time, so
# convert into the same zone or every cloud row becomes a shifted duplicate.
# None = this machine's local zone (what watch.py used). Actions sets TZ.
TZ = ZoneInfo(os.environ["TZ"]) if os.environ.get("TZ") else None
CODE2DP = {"cat_weight": 6, "excretion_times_day": 7, "excretion_time_day": 8,
           "fault": 22, "status": 24}
NAMES = {v: k for k, v in CODE2DP.items()}
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 4


def secret(name, jsonfile, key):
    """Actions secret, else the local json file the Mac setup used."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        return json.load(open(jsonfile))[key]
    except (OSError, KeyError):
        sys.exit(f"missing {name} (and {jsonfile}:{key})")


def fetch():
    c = tinytuya.Cloud(apiRegion=secret("TUYA_REGION", "cloud.json", "region"),
                       apiKey=secret("TUYA_KEY", "cloud.json", "key"),
                       apiSecret=secret("TUYA_SECRET", "cloud.json", "secret"))
    end = int(time.time() * 1000)
    r = c.getdevicelog(secret("TUYA_DEVICE", "config.json", "id"),
                       start=end - DAYS * 86400 * 1000, end=end,
                       evtype="7", max_fetches=50)
    if not isinstance(r, dict) or "result" not in r:
        sys.exit("cloud error: " + json.dumps(r)[:400])
    out = []
    for l in r["result"].get("logs", []):
        dp = CODE2DP.get(l.get("code"))
        if dp is None:
            continue
        # naive local time, matching what watch.py writes
        ts = datetime.datetime.fromtimestamp(int(l["event_time"]) / 1000, TZ)
        val = l.get("value")
        if dp != 24:
            try: val = int(val)
            except (TypeError, ValueError): pass
        out.append((ts.replace(tzinfo=None).isoformat(timespec="seconds"), dp, val))
    return out


def main():
    known = [(e["ts"], e["dp"], e["new"]) for e in logbook.rows()]
    merged = sorted(set(known) | set(fetch()), key=lambda r: (r[0], r[1]))

    # rebuild the old->new chain over the union; each dp's chain is independent,
    # so replayed cloud rows collapse into the local ones instead of duplicating.
    rows, state = [], {}
    for ts, dp, val in merged:
        if dp in state and state[dp] == val:
            continue
        rows.append({"ts": ts, "dp": dp, "name": NAMES.get(dp, f"dp{dp}"),
                     "old": state.get(dp), "new": val})
        state[dp] = val

    logbook.write_rows(rows)
    os.makedirs("api", exist_ok=True)
    with open("api/data.json", "w") as f:
        json.dump(logbook.payload(), f, ensure_ascii=False)
    print(f"{len(rows)} olay  ({rows[0]['ts']} -> {rows[-1]['ts']})")


if __name__ == "__main__":
    main()
