#!/usr/bin/env python3
"""Smallest check that the three fragile bits hold: poll.rebuild must collapse
replayed cloud rows instead of duplicating visits, it must be deterministic when
two events share a (ts, dp), and derive() must read one visit per dp7 increment."""
import logbook, poll

def rows_to_triples(rows):
    return [(r["ts"], r["dp"], r["new"]) for r in rows]

def test():
    local = [("t1", 7, 1), ("t1", 8, 30), ("t2", 24, "clean"), ("t3", 24, "standly")]
    cloud = local + [("t4", 7, 2), ("t4", 8, 45)]        # window overlaps local
    rows = poll.rebuild(local, cloud)
    assert len(rows) == 6, rows                           # no duplicated rows
    assert poll.rebuild(rows_to_triples(rows), cloud) == rows   # idempotent

    # same (ts, dp), two values inside one second: source order must survive,
    # or every run rewrites the file and churns a commit
    flick = [("t1", 24, "level"), ("t1", 24, "test"), ("t2", 24, "standly")]
    out = poll.rebuild(flick, list(reversed(flick)))
    assert [r["new"] for r in out] == ["level", "test", "standly"], out

    visits, cleans, _ = logbook.derive(rows)
    assert [v["n"] for v in visits] == [1], visits        # 1->2 only; 0->1 has no prior
    assert [v["secs"] for v in visits] == [45], visits
    assert len(cleans) == 1 and cleans[0]["start"] == "t2", cleans
    print("ok")

if __name__ == "__main__":
    test()
