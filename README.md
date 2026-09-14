# POOPY NANO 3 — a litter box logbook

A Tuya-based cat litter box records every visit, weighs the cat on the way in,
and runs its own cleaning cycles — and then shows you almost none of it. The
vendor app gives a live status screen and no history worth the name.

This project keeps the history. It collects the device's raw datapoint changes,
derives visits, cleaning cycles and weights from them, and serves a small web
page you add to your phone's home screen.

**Live:** https://fozgur.github.io/poopy/

There is no server and no database engine. The event log is a file in this repo,
git is the storage layer, GitHub Actions is the cron, and GitHub Pages is the
host. Nothing needs to stay switched on at home.

## How it works

```
GitHub Actions (every 6 min)
        |
     poll.py  <--  Tuya Cloud API  (~4 day rolling window)
        |
   events.jsonl  +  api/data.json
        |
    git push  (only when the device actually reported something)
        |
   GitHub Pages  -->  index.html on your phone
```

`poll.py` reads the cloud's rolling window and merges it into `events.jsonl`,
an append-only log of every datapoint change. The merge is idempotent: re-reading
an overlapping window produces a byte-identical file, so a run with no new device
activity commits nothing and triggers no deploy. Deploys are proportional to how
often the cat uses the box, not to the clock.

The window is four days and the cron is six minutes, so Actions can skip a good
number of runs — it often does under load — without losing anything.

`events.jsonl` only ever grows. Tuya forgets everything older than four days;
this file does not, and neither does git. `poll.py` rewrites it whole on each
run, so it refuses to write a result with fewer events than it read — a checkout
that arrived without the file would otherwise replace the entire history with
four days of it, silently. The one real hole is a gap longer than the window: if
the workflow stays broken for more than four days, the events in between are
gone from Tuya before anything can fetch them.

### Why not just read the device directly?

The box speaks the local Tuya protocol over the LAN, so a listener has to sit on
the same network. That was the original design (`watch.py`, still here) and it
meant a laptop at home had to stay awake forever. Everything the UI shows can be
derived from the five datapoints Tuya's cloud logs, so the cloud path replaced it
and the home dependency went away.

The trade is two vendor datapoints the cloud never logs: `101 cleaning` and
`124 clean_count`. Run `watch.py` on the LAN if you want those; nothing else
depends on it.

## Setup

For your own device, you need a Tuya IoT Platform account with the device linked
to a cloud project.

1. Fork or copy this repo.
2. Add four repository secrets under **Settings → Secrets and variables → Actions**:

   | secret | value |
   |---|---|
   | `TUYA_REGION` | `eu`, `us`, `cn` … |
   | `TUYA_KEY` | cloud project access ID |
   | `TUYA_SECRET` | cloud project access secret |
   | `TUYA_DEVICE` | the device id |

3. Set `TZ` in [`.github/workflows/poll.yml`](.github/workflows/poll.yml) to your
   own zone. The cloud returns epoch milliseconds and the log stores naive local
   time; converting into the wrong zone makes every cloud row a time-shifted
   duplicate of a row you already have.
4. **Settings → Pages → Deploy from a branch → `main` / `(root)`**.
5. Open the site on your phone, Share → Add to Home Screen.

The schedule starts itself after the first push. `workflow_dispatch` runs it by
hand from the Actions tab.

## Running locally

```sh
python poll.py          # pull the cloud window, rebuild events.jsonl + api/data.json
python logbook.py       # preview at http://localhost:8420
python test_poopy.py    # self-check
python watch.py         # OPTIONAL, LAN listener, needs config.json
```

`poll.py` and `logbook.py` need only `tinytuya`.

Note that `api/data.json` is generated and rewritten by CI. If you run `poll.py`
locally you will collide with the bot on the next pull — treat the file as build
output and `git checkout -- api/data.json` before pulling.

## Files

| file | what |
|---|---|
| `poll.py` | Tuya Cloud → `events.jsonl` → `api/data.json` |
| `logbook.py` | derivation rules, event store, local preview server |
| `watch.py` | optional LAN listener, for the vendor-only datapoints |
| `test_poopy.py` | self-check for the merge and the derivation |
| `events.jsonl` | raw event log — the single source of truth |
| `api/data.json` | derived output, the only thing the page reads |
| `index.html`, `sw.js`, `manifest.json` | the UI, installable as a PWA |
| `cutout.py` | one-off: `sutlac.jpeg` → transparent `sutlac.png` / `favicon.png` |
| `config.json`, `cloud.json` | device and cloud credentials — gitignored |

## Derivation rules

| what | from |
|---|---|
| visit | every increase of `7` (`excretion_times_day`) |
| **merged visit** | consecutive entries within `MERGE_GAP` (240 s) count as one; durations add up, the entry count lands in `parts` |
| duration | `8` (`excretion_time_day`) as of that moment |
| weight | `6` (`cat_weight`) as of that moment |
| cleaning cycle | `24` (`status`) entering and then leaving `clean` |

Every number in the UI is a **merged** visit. The cat walks in, out, and back in;
the device's own counter reads that as three visits. In the duration chart a
**hollow ring marks a visit that was stitched together** from several entries.

Two subtleties that cost real debugging, in case you build something similar:

- Datapoints that belong to one event arrive with the same timestamp. `7` and `8`
  land together, and if you apply them one at a time in datapoint order, every
  visit reports the *previous* visit's duration and weight. `derive()` applies a
  whole timestamp batch before deriving anything from it.
- Two events can share a timestamp *and* a datapoint — a status flicker inside one
  second. Deduplicating those through a `set()` leaves their order up to the
  process hash seed, which rewrites the file on every run and produces an endless
  stream of empty commits.

## Known limits

- **The cloud logs five datapoints** (6/7/8/22/24) for four days. Enough for
  everything above; `101`/`124` need `watch.py` on the LAN.
- **The weight is noisy.** The same cat reads anywhere from 1.0 to 3.2 kg, so the
  headline figure is a median. `6` is a raw load-cell value and the vendor's own
  kilogram figure is wrong, so calibrate `W_SCALE` / `W_OFFSET` in `logbook.py`
  against a known weight rather than trusting either.
- **No litter weight.** No datapoint tracks the litter itself; sampling a full
  cleaning cycle at 2-second intervals moved no mass signal at all. Measuring it
  needs an external scale under the box (ESP32 + HX711).
- **Eleven vendor datapoints are still unnamed** (`102,104,105,114,117,118,121,
  123,125,126,127`). Run `watch.py`, change a setting in the app, and watch which
  number moves.
- **This repo is public, so the data is.** Making it private would take Pages with
  it — private repositories need a paid plan to publish. Cloudflare Pages deploys
  from a private repo on its free tier, but its 500-builds-per-month limit means
  the data has to be fetched from somewhere other than the build output.
