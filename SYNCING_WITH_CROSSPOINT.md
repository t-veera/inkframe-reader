# Syncing INKFRAME with upstream CrossPoint

This document explains how the INKFRAME firmware relates to the CrossPoint
project it was forked from, what happens when CrossPoint releases new work, and
the exact process for pulling those updates in without breaking INKFRAME's
hardware support. Read this before attempting any upstream sync.

---

## 1. The relationship: we are a fork, not a live mirror

INKFRAME firmware is a **fork** of
[CrossPoint](https://github.com/crosspoint-reader/crosspoint-reader). A fork is a
**snapshot in time**: when we forked, we copied CrossPoint's entire commit
history up to that point. From that moment the two repositories are independent.

**New features added to CrossPoint do NOT appear in INKFRAME automatically.** Our
repo stays at the commit we forked from, plus our own changes, until we
*deliberately* pull upstream's new work in. There is no automatic flow.

```
upstream/master:  A → B → C → D → E      (CrossPoint keeps adding commits)
our branch:       A → B → [INKFRAME commits]   (frozen at B until we sync)
```

---

## 2. Why INKFRAME diverges from CrossPoint

CrossPoint targets the **ESP32-C3** with **Xteink X3/X4** hardware (SSD1677 /
UC81xx controllers, ADC resistor-ladder buttons, dedicated SD bus). INKFRAME
targets **ESP32-S3-N16R8** with a **Waveshare GDEQ0583T31 / UC8179** panel driven
through **GxEPD2**, a shared SPI bus, and a digital 5-way switch.

Because of this, INKFRAME replaces the **hardware-specific layers only**:
- display driver (`EInkDisplay`) — reimplemented as a GxEPD2 shim
- SD card (`SDCardManager`) — reconfigured for the shared SPI bus
- input (`InputManager`) — reimplemented for digital-GPIO buttons
- `platformio.ini` — S3 board + PSRAM + GxEPD2 dependency

Everything above the hardware layer — the reader engine, EPUB parsing, fonts, UI,
web/upload server, settings — is used **unchanged** from CrossPoint.

---

## 3. What this means for updates

| Area | We modified it? | What happens on sync |
|------|-----------------|----------------------|
| UI, reader, EPUB, fonts, web server, settings | No | Upstream improvements merge in **cleanly** most of the time. We get new features here. |
| Display / SD / input / platformio | Yes | Upstream changes here **conflict** and must be resolved by hand, keeping INKFRAME's hardware logic. |

So: **we get CrossPoint's new features, but only when we choose to sync, and the
sync needs manual conflict-resolution on the hardware files we own.** It is not
automatic, but it is very doable a few times a year.

---

## 4. The discipline that keeps syncing painless

The single biggest factor in how painful a sync is: **how many of CrossPoint's
original lines we modified.** Every upstream line we overwrote is a future
conflict. The goal is to change as few of their lines as possible.

Two patterns, in order of preference:

### Pattern A — new files instead of edited files (BEST)
Put INKFRAME hardware code in **new files that CrossPoint does not have**
(e.g. `EInkDisplay_inkframe.cpp`, `lib/hal/inkframe_pins.h`), selected by the
`-DINKFRAME_HW` build flag. CrossPoint's original files stay byte-for-byte
identical to upstream. **New files can never conflict** — upstream has nothing to
conflict against. This is the structure INKFRAME uses.

### Pattern B — guarded edits (only when you must touch their file)
When an upstream file genuinely must be edited, wrap the change in a marked
build-flag guard so their original lines are preserved alongside ours:

```cpp
#ifdef INKFRAME_HW
  // INKFRAME: GxEPD2 shim path
#else
  // original CrossPoint code, untouched
#endif
```

Their lines still exist exactly as upstream has them, so conflicts shrink to
near-zero.

### What to avoid
**Wholesale rewriting an upstream file.** It works, but it guarantees a conflict
on that file at every sync, forever. If you find a rewritten upstream file,
refactor it toward Pattern A before building more on top.

### Files INKFRAME intentionally owns (expect to hand-merge these)
- `platformio.ini` (our board config — unavoidable divergence)
- any `#ifdef INKFRAME_HW` guards in `EInkDisplay.*`, `SDCardManager.*`,
  `InputManager.*`
- everything in the new `*_inkframe.*` files and `lib/hal/inkframe_pins.h`
  (these are ours; upstream never touches them, so they never conflict — listed
  here only so maintainers know they are INKFRAME-specific)

---

## 5. How to sync (the process)

### One-time setup: add CrossPoint as `upstream`
Your `origin` points at the INKFRAME repo. Add CrossPoint as a second remote:

```bash
git remote add upstream https://github.com/crosspoint-reader/crosspoint-reader.git
git remote -v   # confirm: origin = INKFRAME, upstream = crosspoint
```

### Each sync: fetch then rebase
```bash
git fetch upstream                 # download CrossPoint's new commits
git checkout inkframe-s3-uc8179    # our working branch
git rebase upstream/master         # replay OUR commits on top of their newest
```

`rebase` lifts our INKFRAME commits off, fast-forwards to CrossPoint's latest,
then sets our commits back down on top:

```
before:  A → B → [our commits]
         A → B → C → D → E              (upstream moved ahead)
after:   A → B → C → D → E → [our commits]
```

Our hardware changes now sit cleanly on top of the newest CrossPoint, as if we
had just written them today.

### If conflicts appear
Rebase stops at each conflicting commit. For each:
1. Open the conflicted file. Conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
   show upstream's version vs ours.
2. Resolve by **keeping INKFRAME's hardware logic** while taking any upstream
   improvement around it. **Never blindly accept upstream's version of a
   hardware file** — it will re-break the board (wrong pins, wrong driver).
3. `git add <file>` then `git rebase --continue`.
4. To abort and return to the pre-sync state at any time: `git rebase --abort`.

### After a successful rebase
```bash
git diff --stat HEAD@{1}     # review what changed
# build and FLASH to verify hardware still works before trusting the sync
pio run
# our branch history was rewritten by rebase, so push with lease:
git push --force-with-lease origin inkframe-s3-uc8179
```

> **Always flash and verify on real hardware after a sync.** A clean rebase means
> the code merged without textual conflict — it does NOT guarantee the board still
> works. Upstream may have changed behavior the hardware layer depends on.

---

## 6. Merge vs rebase — which and why

Both pull upstream in; they differ in the shape of the result.

- **`git rebase upstream/master`** — rewrites our commits to sit on top of
  upstream's. Clean linear history, our changes always at the tip. **Use this**
  for keeping the INKFRAME fork on top of CrossPoint. Matches the "replay our
  diff on top" model.
- **`git merge upstream/master`** — keeps both histories and joins them with a
  merge commit. Messier log, our changes buried in the timeline. Use only if you
  specifically want to preserve the braided history.

Rule of thumb: **rebase to keep a small patch on top of an upstream you follow**
(our situation); merge when combining two lines of work that both matter as
history.

---

## 7. Quick reference

```bash
# one-time
git remote add upstream https://github.com/crosspoint-reader/crosspoint-reader.git

# each sync
git fetch upstream
git checkout inkframe-s3-uc8179
git rebase upstream/master
#   ...resolve conflicts on hardware files, keeping INKFRAME logic...
pio run                       # build
#   ...flash and verify on hardware...
git push --force-with-lease origin inkframe-s3-uc8179

# escape hatch
git rebase --abort            # cancel a sync, return to pre-sync state
```

**Golden rules**
1. New files over edited files — keep the upstream diff small and surgical.
2. Never blind-accept upstream's version of a hardware file during conflict
   resolution.
3. Always flash and verify after a sync; a clean rebase is not proof the board
   works.
