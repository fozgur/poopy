#!/usr/bin/env python3
"""Tek koşulabilir kontrol: aynı saniyedeki dp7/dp8 çiftinde süre doğru ziyarete
yazılıyor mu (yazılmazsa her ziyaret bir öncekinin süresini alır), ve kısa kalış
işaretleniyor mu."""
import logbook

def ev(ts, dp, old, new):
    return {"ts": ts, "dp": dp, "name": logbook.NAMES.get(dp, f"dp{dp}"),
            "old": old, "new": new}

def test_duration_lands_on_its_own_visit():
    # cihazdan gelen gerçek akış: dp7 ve dp8 aynı payload, dp8 sonra işleniyor
    evs = [ev("2026-09-14T09:36:10", 7, 0, 1), ev("2026-09-14T09:36:10", 8, 25, 26),
           ev("2026-09-14T09:39:16", 7, 1, 2), ev("2026-09-14T09:39:16", 8, 26, 92)]
    visits, _, _ = logbook.derive(evs)
    assert [v["secs"] for v in visits] == [26, 92], [v["secs"] for v in visits]

def test_short_stay_flagged_after_merge():
    evs = [ev("2026-09-14T10:00:00", 7, 0, 1), ev("2026-09-14T10:00:00", 8, 0, 4)]
    visits, _, _ = logbook.derive(evs)
    s, = logbook.sessions(visits)
    assert s["secs"] == 4 and s["short"]
    # birleşen girişlerin toplamı eşiği aşarsa kısa sayılmaz
    evs += [ev("2026-09-14T10:01:00", 7, 1, 2), ev("2026-09-14T10:01:00", 8, 4, 30)]
    s, = logbook.sessions(logbook.derive(evs)[0])
    assert s["parts"] == 2 and s["secs"] == 34 and not s["short"]

if __name__ == "__main__":
    test_duration_lands_on_its_own_visit()
    test_short_stay_flagged_after_merge()
    print("ok")
