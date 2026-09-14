#!/usr/bin/env python3
"""Tuya Cloud -> events.jsonl -> api/data.json.  Runs on GitHub Actions; no LAN.

The cloud serves the five official DPs (6/7/8/22/24), which is everything
logbook.derive() needs. Vendor DPs (101/124) only ever come from a local watch.py
run and are left untouched here.

Tuya's retention is unmeasured: as of 2026-09-14 it returns everything since the
device was paired, but the device is only four days old, so a rolling window can
neither be confirmed nor ruled out. The default lookback is a week, well past the
six-minute cron, so a lost run repairs itself; pass a bigger number to repair a
longer outage (python poll.py 120).
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
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7


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
    for l in sorted(r["result"].get("logs", []), key=lambda l: int(l["event_time"])):
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


def rebuild(known, cloud):
    """Union the two sources and rebuild the old->new chain. Each dp's chain is
    independent, so replayed cloud rows collapse into the local ones instead of
    duplicating."""
    # ponytail: dedupe in a fixed order, never through set(). Two events can
    # share a (ts, dp) — a status flicker inside one second — and set iteration
    # order varies per process, which flipped them and churned a commit per run.
    seen, ordered = set(), []
    for i, t in enumerate(known + cloud):
        if t not in seen:
            seen.add(t)
            ordered.append((t, i))
    merged = [t for t, _ in sorted(ordered, key=lambda x: (x[0][0], x[0][1], x[1]))]

    rows, state = [], {}
    for ts, dp, val in merged:
        if dp in state and state[dp] == val:
            continue
        rows.append({"ts": ts, "dp": dp, "name": NAMES.get(dp, f"dp{dp}"),
                     "old": state.get(dp), "new": val})
        state[dp] = val
    return rows


def main():
    known = logbook.rows()
    rows = rebuild([(e["ts"], e["dp"], e["new"]) for e in known], fetch())

    # The log only ever grows: the cloud window is 4 days, the file is forever.
    # write_rows() truncates, so a checkout that lost events.jsonl would quietly
    # replace years of history with four days of it. Refuse instead.
    if len(rows) < len(known):
        sys.exit(f"olay sayısı düştü ({len(known)} -> {len(rows)}), yazılmadı")

    logbook.write_rows(rows)
    os.makedirs("api", exist_ok=True)
    with open("api/data.json", "w") as f:
        json.dump(logbook.payload(), f, ensure_ascii=False)
    print(f"{len(rows)} olay  ({rows[0]['ts']} -> {rows[-1]['ts']})")


if __name__ == "__main__":
    main()
