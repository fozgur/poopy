#!/usr/bin/env python3
"""POOPY logbook: derives visits/cleans from the raw DPS event log and serves
a small web UI locally. poll.py (cloud) and watch.py (LAN) are the writers."""
import datetime, http.server, json, os, socketserver
from itertools import groupby

EVENTS, PORT = "events.jsonl", 8420

NAMES = {
    6: "cat_weight", 7: "excretion_times_day", 8: "excretion_time_day",
    22: "fault", 24: "status",
    116: "weight_unit", 131: "litter_type",
    101: "cleaning", 124: "clean_count", 128: "cycle_end_flag",
}

# ponytail: dp6 is a raw load-cell reading; the app's own kg figure is wrong, so
# don't trust the vendor scaling. Tune these against a known weight.
W_SCALE, W_OFFSET = 0.1, 0.0

# ponytail: Sütlaç girip çıkıp giriyor. Bu aralıktan yakın iki giriş tek ziyaret
# sayılır, süreleri toplanır. Saniye — davranış değişirse tek yerden ayarla.
# 4 dakika: 2 dakikayla bazı girdili çıktılı seriler ayrı ziyaret olarak kalıyordu.
MERGE_GAP = 240

def rows():
    if not os.path.exists(EVENTS):
        return []
    with open(EVENTS) as f:
        return [json.loads(l) for l in f if l.strip()]

def write_rows(rs):
    with open(EVENTS, "w") as f:
        for r in rs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def append_row(r):
    with open(EVENTS, "a") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

def derive(evs):
    """visits: dp7 increments. cleans: dp24 entering/leaving "clean" — that DP is
    in the cloud history too, so cycles predate local watching (dp101/dp124 are
    local-only)."""
    visits, cleans, weights, cur, clean_start = [], [], [], {}, None
    for _, batch in groupby(evs, key=lambda e: e["ts"]):
        # ponytail: dp7 and dp8 arrive in the same second. Apply the whole
        # batch to cur before deriving, or a visit reads the *previous*
        # visit's duration and weight.
        fresh = []
        for e in batch:
            if e["old"] is None and e["dp"] in cur:   # replay after a restart
                cur[e["dp"]] = e["new"]
                continue
            cur[e["dp"]] = e["new"]
            fresh.append(e)
        for e in fresh:
            dp, new, old = e["dp"], e["new"], e["old"]
            if dp == 6 and isinstance(new, (int, float)):
                weights.append({"ts": e["ts"], "kg": round(new * W_SCALE + W_OFFSET, 2)})
            elif dp == 7 and isinstance(new, int) and isinstance(old, int) and new > old:
                visits.append({"ts": e["ts"], "n": new - old, "secs": cur.get(8),
                               "kg": round((cur.get(6) or 0) * W_SCALE + W_OFFSET, 2) or None})
            elif dp == 24:
                if new == "clean":
                    clean_start = e["ts"]
                elif old == "clean" and clean_start:
                    cleans.append({"ts": e["ts"], "start": clean_start,
                                   "count": cur.get(124)})
                    clean_start = None
    seen = set()
    weights = [w for w in weights
               if not (w["ts"] in seen or seen.add(w["ts"]))]
    return visits, cleans, weights


def sessions(visits, gap=MERGE_GAP):
    """Ard arda gelen girişleri tek ziyarete indirger: süreler toplanır,
    kaç giriş olduğu `parts` alanında durur."""
    out = []
    for v in visits:
        t = datetime.datetime.fromisoformat(v["ts"])
        if out and (t - out[-1]["_t"]).total_seconds() <= gap:
            s = out[-1]
            s["parts"] += 1
            s["secs"] = (s["secs"] or 0) + (v["secs"] or 0)
            s["end"], s["_t"] = v["ts"], t
            if v["kg"]:
                s["_kg"].append(v["kg"])
        else:
            out.append({"ts": v["ts"], "end": v["ts"], "_t": t, "parts": 1,
                        "secs": v["secs"], "_kg": [v["kg"]] if v["kg"] else []})
    for s in out:
        del s["_t"]
        s["kg"] = median(s.pop("_kg"))
    return out


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


FAULTS = ["E01", "E02", "E03", "E04", "E05"]

def payload():
    evs = rows()
    visits, cleans, weights = derive(evs)
    cur = {}
    for e in evs:
        cur[e["dp"]] = e["new"]
    fault = cur.get(22) or 0
    recent = [w["kg"] for w in weights[-12:]]
    sess = sessions(visits)
    today = datetime.date.today().isoformat()
    done = [s["secs"] for s in sess if s["secs"]]
    return {
        "device": "POOPY NANO 3",
        "now": {
            "status": cur.get(24), "cleaning": cur.get(101),
            # ponytail: a single reading swings 1.0-3.2 kg for the same cat, so the
            # headline figure is a median. Raw points still show in the chart.
            "weight_kg": median(recent),
            # arayüzün tamamı birleştirilmiş ziyaret üzerine kurulu; cihazın kendi
            # dp7 sayacı girip çıkmaları ayrı ayrı sayıyor.
            "visits_today": sum(1 for s in sess if s["ts"][:10] == today),
            "clean_count": cur.get(124),
            "median_secs": median(done[-20:]),
            "merge_gap": MERGE_GAP,
            "faults": [f for i, f in enumerate(FAULTS) if fault >> i & 1],
        },
        "visits": sess, "cleans": cleans, "weights": weights,
        "n_events": len(evs),
    }


class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/data"):
            try:
                body = json.dumps(payload()).encode()
            except OSError as ex:
                self.send_error(503, str(ex)); return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), H) as srv:
        print(f"http://localhost:{PORT}   (LAN: http://192.168.1.49:{PORT})", flush=True)
        srv.serve_forever()
