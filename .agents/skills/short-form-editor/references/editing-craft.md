# Editing craft for talking-head shorts

## Picking the hook

The first 1–3 seconds decide whether anyone watches. The hook is almost never the first thing the person said; it's usually buried in the middle, said casually.

Rank candidate lines by:

1. **Specificity**: "$4,999 in three weeks" beats "I made good money". Numbers, timeframes, named things.
2. **Stakes / surprise**: a result that sounds too good, a contradiction ("I almost quit, then…"), a mistake, a confession.
3. **Self-contained**: it makes sense with zero context. "Both those videos are paying me 2K" needs setup, so it doesn't work as a hook.
4. **Clean delivery**: one breath, no stumble, energetic. If the best line has a stumble, splice its clean halves.

Stacking: if a second line sharpens the first (the result, then the effort; the claim, then the proof), put it right behind the hook. The example below opened with "$4,999 is how much I made in three weeks doing one UGC campaign", then "Bro, I spent one hour max a week for this campaign alone".

After the hook, go back to the natural story order, so the story stays easy to follow.

## What to cut

| Cut                       | Examples                                                                            |
| ------------------------- | ----------------------------------------------------------------------------------- |
| Filler reactions          | "Yeah." "I don't even know what to say." "This is like, wow." "Absolutely not bad." |
| Meta / signposting        | "All right, so just a quick rundown." "So, also to think that…"                     |
| Repeats                   | The same point made twice: keep the stronger take (usually the more specific one)   |
| Disclaimers and hedges    | "I don't want to sound braggy…", "keep in mind…" (unless it's the point)            |
| Logistics nobody needs    | "This campaign pays bi-weekly." "For some reason, for that little two-week window…" |
| False starts and restarts | "that go, that hit" → "that hit"; "Both pay, both those" → "Both those"             |
| Fillers inside sentences  | "and they, um, offered"                                                             |
| Dead air                  | Pauses ≥0.3s inside kept lines are removed automatically by `build_cut.py`          |

Keep: every distinct story beat once, the emotional line ("I was like, BS, until it actually happened to me"), and the CTA (trimmed to one clean version; the speaker often says it twice).

Keep a little personality: a "bro" that carries energy can stay; a third "like" in one sentence goes.

## Cutting cleanly

- Range = first word start → last word end from the transcript; `build_cut.py` pads 0.06s before and 0.10s after.
- A padded tail can leak the next word ("…part-time job that"). If the next word starts within ~0.1s of your end, pull the end in.
- Word timestamps are least reliable exactly where you need them: around stumbles. Use `envelope.py` to see the real dips. Cut in a dip and confirm with `test_cut.py`.
- When speech is continuous (no dip), try 2–3 candidate points 0.04s apart in `test_cut.py` and take the one that transcribes clean.

## Translating a reference style

Measure, then map:

- **Cut rhythm**: average shot length 2–6s with punch-ins means alternate zoom per group (`zoom: [1.0, 1.14]`). A slower reference → fewer, longer groups.
- **Pauses**: few surviving pauses means a tight edit (the default). Natural pauses kept means raise `--min-gap` to ~0.6.
- **Captions**: one word at a time vs phrase groups, size, position, emphasis treatment. Pick emphasis words that carry meaning: numbers, results, emotional words. Aim for roughly 1 in 6 words, not every noun.
- **Top-zone graphics**: one device per story beat, changing every 2–5s, never two competing at once. Mirror the reference's vocabulary (typed titles, arched caps, checklists, bubbles, scattered thoughts, stickers, cursor CTA) but write the words from this video's content.
- **Palette**: keep the reference's colour family but check contrast on the actual footage.
