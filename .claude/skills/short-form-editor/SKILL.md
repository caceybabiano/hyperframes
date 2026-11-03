---
name: short-form-editor
description: Edit raw talking-head footage into a finished TikTok / Reels / Shorts video in the style of a reference video. Cuts unnecessary dialogue, filler, false starts and dead air, moves the strongest hook line to the first seconds, adds jump-cut punch-ins, one-word captions, and animated titles / stickers / callouts, then renders a 1080x1920 MP4. Use this whenever someone wants a short-form edit, wants their video "edited like this one", sends a TikTok/IG/YouTube link as a style reference, asks to "cut the unnecessary parts", "find a hook", "make this a short / reel / TikTok", or uploads a vlog / talking-head / podcast clip and wants it social-ready, even if they never say "skill" or "short-form".
metadata:
  internal: true
---

# Short-form editor

Turn a long, rambly talking-head recording into a tight 9:16 short that opens on its strongest line and looks like the user's reference video.

The pipeline is: **fetch → study the reference → transcribe → choose the hook and the cuts → build the cut → verify the cut by ear (Whisper) → captions + graphics in HyperFrames → render, composite, deliver**. Scripts in `scripts/` do the mechanical work; your judgment goes into the edit decisions, the beats, and the visual QA. Every script prints `--help`-style usage in its docstring.

Work in a fresh directory (e.g. `./edit/`). `SK=<path to this skill>`.

## 0. Setup

```bash
bash $SK/scripts/setup.sh
```

Installs faster-whisper, yt-dlp, `curl_cffi==0.15.0` (TikTok/IG need browser impersonation, and yt-dlp rejects curl_cffi ≥0.16), Pillow, and finds the HyperFrames CLI. Export `HYPERFRAMES_CLI` as it tells you. If `npx hyperframes` is unavailable but a checkout is, `bun install && bun run build` at the repo root (the CLI alone fails to build without its sibling packages), then `HYPERFRAMES_CLI="node <repo>/packages/cli/dist/cli.js"`.

## 1. Get the footage

```bash
python3 $SK/scripts/fetch.py "<source url>" edit/src --name src
python3 $SK/scripts/fetch.py "<reference url>" edit/ref --name ref
```

Works for TikTok short links, IG, YouTube and Google Drive share links. If the user says they "attached" a file but nothing is on disk, search the filesystem for recent video files, and if it's truly missing, say so and ask for a link — don't stall. While waiting, start on the reference.

## 2. Study the reference

```bash
python3 $SK/scripts/analyze_reference.py edit/ref/ref.mp4 edit/ref
```

Then **read every contact sheet image**. Numbers tell you rhythm (cut frequency, whether pauses survive, punch-in jump cuts); only the images tell you caption style, title treatments, stickers, palette and where things sit in the frame. Write a short `edit/style-profile.md`: pacing, caption model, top-zone graphics, sticker vocabulary, palette, audio. Map each reference device onto a beat type you can build (table in `references/beats.md`).

## 3. Transcribe the source

```bash
python3 $SK/scripts/transcribe.py edit/src/src.mp4 edit/transcript.json
```

Also make a contact sheet of the source (every 3s) and look at it: framing, where the face sits, whether it's one continuous shot, whether there's screen recording or B-roll worth keeping.

## 4. Decide the edit — this is the job

Read `references/editing-craft.md` before deciding. In short:

- **Hook**: the most specific, surprising, high-stakes line in the whole recording — usually a number, a result, or a contradiction — moved to second 0. Stack a second line right behind it if one makes the hook land harder (result → how little effort it took).
- **Keep** each beat of the story once, in its best take. **Cut** filler reactions ("yeah", "wow", "I don't even know what to say"), meta-talk ("quick rundown"), repeats of a point already made, disclaimers, logistics nobody needs, rambling tangents, and every false start.
- Target length: what the content earns. 45–75s is typical for a 3–4 min ramble; don't pad to a number.

Write `edit/edl.json` (schema in `scripts/build_cut.py`): groups in output order, each with source ranges taken from word timestamps. Split a range wherever a stumble sits inside it.

**Whisper hides stumbles.** It routinely merges a false start into the next words ("this might be something — this might be scalable" came out as one long "be"). Every word `transcribe.py` flags as a SUSPECT (long duration / low confidence) inside a kept range must be checked:

```bash
python3 $SK/scripts/envelope.py edit/src/src.mp4 117.5 121.9     # find the real word gaps (dB dips)
python3 $SK/scripts/test_cut.py edit/src/src.mp4 "79.6-80.50,80.90-82.7" "79.6-80.50,80.92-82.7"
```

`test_cut.py` splices candidate ranges and tells you what they sound like — pick the clean one.

## 5. Build and verify the cut

```bash
python3 $SK/scripts/build_cut.py edit/src/src.mp4 edit/edl.json edit
python3 $SK/scripts/transcribe.py edit/cut.mp4 edit/cut_words.json
```

Read the cut transcript top to bottom as if you were the viewer. It must read like a clean script: no "that go, that hit", no "both pay, both those", no "um", no clipped first/last words, no orphan fragments. Fix the EDL and rebuild until it does — this second listen always finds something the first pass missed. Whisper also _invents_ small words at cut joins (a stray "But"/"And"); if the source transcript doesn't have it there, it's a hallucination — drop it from captions via `captions.drop`, don't recut for it.

`cut_words.json` (the transcript of the **cut**, not the source) is the timeline for everything that follows.

## 6. Captions + graphics

Write `edit/beats.json` — palette, caption emphasis words/fixes, and one beat per story moment. Schema, beat types and anchor syntax: `references/beats.md`. Anchor beats to words (`"million~-0.15"`), not hand-typed seconds, so they survive re-cuts.

Sample the frame before choosing colours: text in the top zone sits on whatever is behind the head (often a bright wall → dark inks), captions sit on the body/chest (usually darker → white). Keep the reference's palette _family_ but make it legible on this footage.

```bash
python3 $SK/scripts/gen_overlay.py --words edit/cut_words.json --beats edit/beats.json --video edit/cut.mp4 --out edit/hf
```

## 7. Render, composite, QA, deliver

```bash
bash $SK/scripts/finish.sh edit short_final
```

It runs `hyperframes check` on the overlay (fix any layout overlap it reports — move the element, regenerate, re-run), renders the transparent overlay, composites onto the cut, makes a <28 MB share copy, and a 20-frame `review_sheet.jpg`. **Look at the review sheet** and fix anything that clips, crowds the face, wraps badly or is hard to read, then re-run `gen_overlay.py` + `finish.sh`. (Odd numbers mid count-up are normal.)

Deliver the share copy inline (chat upload limits are ~30 MB); the master is the one to post. Report back concisely:

- before → after length, and the hook you chose (quoted)
- what was cut, grouped (filler, repeats, tangents, stumbles)
- how the reference style was translated
- anything the user should confirm — especially numbers, claims, or words Whisper may have misheard (e.g. "$4,390 vs $4,399")
- easy next tweaks (shorter version, different hook, colours)

Never put the user's footage in a git repo or any third-party host without asking — it's personal media. If they want it in Drive/Dropbox and no connector is available, say so and offer options.

## Hard-won gotchas

- One `filter_complex` with dozens of trims on 1080x1920 gets OOM-killed — `build_cut.py` renders segments separately; keep it that way.
- `hyperframes check` on a project that loads the full A-roll can time out; check/render the overlay-only project.
- Rounding segment lengths to frames drifts the timeline ~0.1s by the end — that's why captions come from transcribing the cut, never from source timestamps.
- Avoid `cd dir && rm …/*` style cleanup; overwrite outputs instead.
