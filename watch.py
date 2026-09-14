#!/usr/bin/env python3
"""POOPY NANO 3 -> events.jsonl. OPTIONAL: poll.py covers everything except the
vendor DPs (101 cleaning / 124 clean_count), which only exist on the LAN.
Also the DP-mapping tool: run it, poke a setting in the app, see which DP moved."""
import json, time, datetime
import tinytuya, logbook

CFG = json.load(open("config.json"))
NAMES = logbook.NAMES

def last_state():
    """Seed from the log so a restart doesn't re-log every DP as a fresh change."""
    return {e["dp"]: e["new"] for e in logbook.rows()}

def main():
    d = tinytuya.Device(CFG["id"], CFG["ip"], CFG["key"], version=CFG["version"])
    d.set_socketPersistent(True)
    d.set_socketTimeout(2)

    state = last_state()
    last_beat = last_poll = 0.0
    print(f"watching {CFG['ip']} -> {logbook.EVENTS}   (ctrl-c to stop)", flush=True)

    while True:
        data = d.receive()
        now = time.time()
        if now - last_beat > 20:
            d.heartbeat(nowait=True)
            last_beat = now
        # ponytail: device only pushes on change; poll too so we don't miss
        # fast transitions during a clean cycle.
        if now - last_poll > 2:
            last_poll = now
            polled = d.status()
            if polled and "dps" in polled:
                data = polled
        if not data or "dps" not in data:
            continue
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        for k, v in data["dps"].items():
            dp = int(k)
            if dp in state and state[dp] == v:
                continue
            old, state[dp] = state.get(dp), v
            name = NAMES.get(dp, f"dp{dp}")
            logbook.append_row({"ts": ts, "dp": dp, "name": name,
                                "old": old, "new": v})
            flag = "" if dp in NAMES else "  <-- unknown"
            print(f"{ts}  {dp:>3} {name:<20} {old!r} -> {v!r}{flag}", flush=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
