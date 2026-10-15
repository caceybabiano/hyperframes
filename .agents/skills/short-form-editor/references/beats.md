# beats.json: captions and graphics spec

`gen_overlay.py` turns this file + `cut_words.json` into a HyperFrames layer. The canvas is 1080x1920. Graphics live in the **top zone** (y 0–520, above the head). Captions sit at `captions.top` (default y 1300, over the chest).

## Anchors (any time field)

| Form              | Meaning                                                               |
| ----------------- | --------------------------------------------------------------------- |
| `12.4`            | seconds on the cut timeline                                           |
| `"million"`       | start of the first caption word "million"                             |
| `"my@22.6"`       | first "my" starting at or after 22.6s                                 |
| `"million~-0.15"` | 0.15s before "million" (offsets work with every form: `"and@29~0.2"`) |

Words are matched lowercase with trailing punctuation stripped, **after** fixes and joins (so `"$4,399"`, `"part-time"`, `"10k"`). If there is no exact match, the first word _containing_ the anchor is used (`"15k"` finds `"$10–15K"`). Number words and digits are interchangeable (`"2"` matches "two"), because Whisper writes them differently from run to run. Anchor to plain spoken words, not display formatting. An unknown anchor stops the script and names the word; check `cut_words.json`.

Every beat needs `start`. `end` defaults to 0.05s before the next beat's start (the last beat runs to the end), so usually leave it out.

## Top level

```json
{
  "palette": {"lav": "#6B46D9", "lavSoft": "#C9B8FF", "accent": "#2E8B3E", "ink": "#1E1B2E", "alert": "#E5484D"},
  "captions": {
    "top": 1300, "size": 62,
    "emphasis": ["$4,999", "hour", "million", "nuts"],
    "fix": {"$4,390": "$4,399", "It": "I"},
    "drop": [{"w": "But", "t": 26.54}]
  },
  "beats": [ ... ]
}
```

- `lav`: titles and serif text. `lavSoft`: emphasised caption words (on dark clothing). `accent`: arched caps, money, ticks. `ink`: small sans text and outlines. `alert`: stamps.
- `emphasis`: caption words rendered big, italic serif and coloured. Match them as displayed, lowercase-insensitive.
- `fix`: display corrections for misheard words. `drop`: hallucinated words (word + approx time, ±0.5s). These differ between transcription runs, so build the list from _this_ run's `cut_words.json`.

## Beat types

Shared optional fields: `sub` (small HTML line, `sub_at`, `sub_top`), `emoji` (`emoji_at`, `emoji_xy: [x, y]`), `y` (shift the whole beat down N px).

| type        | Use for                                                     | Fields                                                                                                                                                         |
| ----------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`     | the hook: typed hero text + sparkle marks                   | `text` (≤8 chars renders huge, longer renders mid), `sub`, `sub_at`, `rain` (a character like `"$"` or an emoji that pops and floats), `rain_at`, `type_speed` |
| `arc`       | big curved caps phrase ("1 HOUR / WEEK", "ZERO EXPERIENCE") | `text`, `at`, `bend` (default 120)                                                                                                                             |
| `checklist` | points that tick off as they're said                        | `items: [{"text", "at", "tick"}]`                                                                                                                              |
| `counter`   | series badge + number counting up                           | `label` (serif), `caps`, `prefix`, `value`, `suffix`, `at` (count start), `count_dur`, `top`                                                                   |
| `bubble`    | callout card; `style: "chat"` (bold) or `"quote"` (serif)   | `html`, `at`, `stamp` ("BS 🙄"), `stamp_at`                                                                                                                    |
| `thoughts`  | 2–5 scattered inner-monologue lines                         | `items: [..]`, `at: [anchors]` (optional, else staggered)                                                                                                      |
| `boxes`     | "1 of 4" tally                                              | `label` (HTML), `count`, `filled`, `at`, `rest_at`, `fill_at` (light up the rest)                                                                              |
| `typed`     | serif line typed on ("until it happened to me")             | `text`, `at`                                                                                                                                                   |
| `badge`     | series card ("UGC Diaries / DAY 1")                         | `label`, `caps`, `at`                                                                                                                                          |
| `cta`       | typed CTA + cursor clicking it                              | `text`, `click_at`, `sub` ("see you in the next one <3")                                                                                                       |

## Reference device → beat type

| Seen in reference                           | Build with                           |
| ------------------------------------------- | ------------------------------------ |
| Typed title + white subtitle + doodle marks | `title`                              |
| Arched big caps phrase                      | `arc`                                |
| Floating $ / emoji stickers                 | `title.rain`, or `emoji` on any beat |
| Checklist ticking                           | `checklist`                          |
| "UGC Diaries · DAY 1" series badge          | `badge` / `counter`                  |
| Speech / chat bubble ("become rich???")     | `bubble` style chat                  |
| Quoted claim being debunked                 | `bubble` style quote + `stamp`       |
| "what am I doing???" scatter                | `thoughts`                           |
| Cursor clicking "follow along!!"            | `cta`                                |

## Pacing rules

- One beat per story moment, roughly every 2–5s. Back-to-back beats with no gap are fine; overlapping beats are not.
- Enter on the word that motivates it (anchor to it, often with `~-0.1` to `~-0.25` so it lands with the word).
- Keep anything under ~1s simple (a `thoughts` flash or one `bubble`); anything with a count-up needs ~2s.
- Don't repeat the same type three times in a row; alternate between text, numbers and stickers.

See `example/beats.json` and `example/edl.json` for a complete 65s edit.
