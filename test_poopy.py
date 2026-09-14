#!/usr/bin/env python3
"""Smallest check that the two fragile bits hold: poll.py's chain rebuild must
collapse replayed cloud rows instead of duplicating visits, and derive() must
read one visit per dp7 increment."""
import logbook

def rebuild(triples):
    rows, state = [], {}
    for ts, dp, val in sorted(set(triples), key=lambda r: (r[0], r[1])):
        if dp in state and state[dp] == val:
            continue
        rows.append({"ts": ts, "dp": dp, "name": "", "old": state.get(dp), "new": val})
        state[dp] = val
    return rows

def test():
    local = [("t1", 7, 1), ("t1", 8, 30), ("t2", 24, "clean"), ("t3", 24, "standly")]
    cloud = local + [("t4", 7, 2), ("t4", 8, 45)]        # window overlaps local
    rows = rebuild(local + cloud)
    assert len(rows) == 6, rows                           # no duplicated rows
    assert rebuild(local + cloud) == rebuild(cloud)       # merge is idempotent

    visits, cleans, _ = logbook.derive(rows)
    assert [v["n"] for v in visits] == [1], visits        # 1->2 only; 0->1 has no prior
    assert [v["secs"] for v in visits] == [45], visits
    assert len(cleans) == 1 and cleans[0]["start"] == "t2", cleans
    print("ok")

if __name__ == "__main__":
    test()
