#!/usr/bin/env python3
"""Generate the HyperFrames captions + graphics layer from cut-timeline words and a beats file.

usage: gen_overlay.py --words cut_words.json --beats beats.json --video cut.mp4 --out PROJECT_DIR

Writes two HyperFrames projects:
  PROJECT_DIR/overlay/index.html  graphics only, transparent canvas -> render to MOV (alpha), composite with ffmpeg
  PROJECT_DIR/preview/index.html  same layer over the A-roll, for Studio preview (`hyperframes preview`)

The words file MUST be a transcription of cut.mp4 itself (transcribe.py cut.mp4 ...), not of the
source — source timestamps drift around cuts and stumbles. See references/beats.md for the schema.
"""
import argparse, html, json, os, re, shutil, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--words", required=True); ap.add_argument("--beats", required=True)
ap.add_argument("--video", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = json.load(open(a.beats))
DUR = round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "csv=p=0", a.video])), 3)

# ---------------- caption tokens ----------------
capcfg = B.get("captions", {})
_wj = json.load(open(a.words))
raw = [w for seg in _wj for w in seg["words"]] if _wj and "words" in _wj[0] else _wj   # transcribe.py segments, or a flat word list
drops = capcfg.get("drop", [])  # [{"w": "But", "t": 26.54}] — Whisper hallucinations at cut joins
FIX = capcfg.get("fix", {})     # {"$4,390": "$4,399"} — display corrections
toks = []
for w in raw:
    t = w["w"].strip()
    if not t: continue
    if any(d["w"] == t and abs(d["t"] - w["s"]) < 0.5 for d in drops): continue
    # re-join tokens Whisper splits: "$4" ",999" / "10" "-15k" / "y" "'all" / "part" "time"
    if toks and (re.match(r"^[,'\-–]", t) or (t.lower() == "time" and toks[-1]["w"].lower() == "part")):
        toks[-1]["w"] += ("-" if t.lower() == "time" else "") + t; toks[-1]["e"] = w["e"]; continue
    toks.append({"w": t, "s": float(w["s"]), "e": float(w["e"])})
NUM = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
def key(word):
    """match key: lowercase, no quotes/trailing punctuation, number words == digits (Whisper flips between them)"""
    k = re.sub(r"[“”\"]", "", re.sub(r"[.,?!;:]+$", "", word)).lower()
    return NUM.get(k, k)

for t in toks:
    d = re.sub(r"[.,?!;:]+$", "", t["w"])
    d = FIX.get(d, d)
    d = re.sub(r"(\d)k$", r"\1K", d)
    t["d"] = d; t["k"] = key(d)

def find(word, after=0.0):
    word = key(word)
    for exact in (True, False):   # exact first, then containment ("15k" finds "$10–15k" when Whisper merged the range)
        for t in toks:
            if t["s"] >= after - 1e-6 and (t["k"] == word if exact else word in t["k"]):
                return t["s"]
    raise SystemExit(f"anchor word '{word}' not found after {after}s — check the cut transcript")

def at(spec, default=None):
    """number | "word" | "word@after" | any of those + "~offset"  (e.g. "million~-0.15", "my@22.6")"""
    if spec is None: return default
    if isinstance(spec, (int, float)): return float(spec)
    off = 0.0
    if "~" in spec: spec, o = spec.rsplit("~", 1); off = float(o)
    after = 0.0
    if "@" in spec: spec, af = spec.rsplit("@", 1); after = float(af)
    return round(find(spec, after) + off, 3)

EMPH = {key(e) for e in capcfg.get("emphasis", [])}
cap_html, cap_js = [], []
for i, t in enumerate(toks):
    nxt = toks[i + 1]["s"] if i + 1 < len(toks) else DUR
    off = min(nxt, t["e"] + 0.45, DUR - 0.02)
    em = t["k"] in EMPH
    cap_html.append(f'<span class="w{" em" if em else ""}" id="w{i}">{html.escape(t["d"])}</span>')
    cap_js.append(f"[{t['s']:.3f},{off:.3f},{1 if em else 0}]")

# ---------------- beats ----------------
beats = B.get("beats", [])
for i, bt in enumerate(beats):
    bt["_s"] = at(bt["start"])
for i, bt in enumerate(beats):
    nxt = beats[i + 1]["_s"] - 0.05 if i + 1 < len(beats) else DUR
    bt["_e"] = min(at(bt.get("end"), nxt), DUR)
    bt["_id"] = f"b{i}"

js = []
def typein(sel, t, per=0.045):
    js.append(f'tl.fromTo("{sel} .ch", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.01, stagger: {per} }}, {t:.3f});')
def pop(sel, t, dur=0.32):
    js.append(f'tl.fromTo("{sel}", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {dur}, ease: "back.out(2.2)" }}, {t:.3f});')
def rise(sel, t, dur=0.28):
    js.append(f'tl.fromTo("{sel}", {{ y: 22, opacity: 0 }}, {{ y: 0, opacity: 1, duration: {dur}, ease: "power3.out" }}, {t:.3f});')
def slide(sel, t, dur=0.3):
    js.append(f'tl.fromTo("{sel}", {{ x: 60, opacity: 0 }}, {{ x: 0, opacity: 1, duration: {dur}, ease: "power3.out" }}, {t:.3f});')
def out(sel, t):
    js.append(f'tl.to("{sel}", {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, {t:.3f});')
def count(span, to, t, dur=0.7):
    dec = 1 if float(to) != int(float(to)) else 0
    js.append(f'(() => {{ const o = {{ v: 0 }}; tl.to(o, {{ v: {to}, duration: {dur}, ease: "power2.out", onUpdate: () => {{ '
              f'document.getElementById("{span}").textContent = o.v.toLocaleString("en-US", {{ minimumFractionDigits: {dec}, maximumFractionDigits: {dec} }}); }} }}, {t:.3f}); }})();')

def typed(tid, text, cls):
    spans = "".join(f'<span class="ch">{html.escape(c) if c != " " else "&nbsp;"}</span>' for c in text)
    return f'<div id="{tid}" class="{cls}">{spans}</div>'

def arc_svg(aid, text, bend=120, y=300, w=1000):
    x0, x1 = (1080 - w) / 2, (1080 + w) / 2
    return (f'<svg class="arc" viewBox="0 0 1080 420" width="1080" height="420"><path id="{aid}" d="M {x0} {y} Q 540 {y - 2 * bend} {x1} {y}" fill="none"/>'
            f'<text><textPath href="#{aid}" startOffset="50%" text-anchor="middle">{html.escape(text)}</textPath></text></svg>')

def emoji(bid, bt, s, default_xy=(850, 290)):
    if not bt.get("emoji"): return ""
    x, y = bt.get("emoji_xy", default_xy)
    pop(f"#{bid}-emo", at(bt.get("emoji_at"), s + 0.3))
    return f'<div id="{bid}-emo" class="emo" style="left:{x}px;top:{y}px">{bt["emoji"]}</div>'

def sub(bid, bt, s, top=330):
    if not bt.get("sub"): return ""
    rise(f"#{bid}-sub", at(bt.get("sub_at"), s + 0.3))
    return f'<div id="{bid}-sub" class="sub small" style="top:{bt.get("sub_top", top)}px">{bt["sub"]}</div>'

THOUGHT_XY = [(110, 150), (620, 110), (360, 300), (700, 330), (80, 360)]
DOLLAR_XY = [(70, 210, 64), (960, 190, 80), (40, 440, 46), (990, 450, 50), (250, 455, 52), (790, 460, 58)]

graphics = []
for bt in beats:
    bid, s, e, ty = bt["_id"], bt["_s"], bt["_e"], bt["type"]
    body = ""
    if ty == "title":            # typed hero title + subtitle + sparkle marks (+ optional floating $ / emoji rain)
        body += typed(f"{bid}-t", bt["text"], "title-serif " + ("big" if len(bt["text"]) <= 8 else "mid"))
        typein(f"#{bid}-t", s + 0.05, bt.get("type_speed", 0.07))
        body += ''.join(f'<svg id="{bid}-sp{k}" class="spark{" r" if k else ""}" viewBox="0 0 100 100"><path d="M20 30 L35 45 M50 15 L50 38 M80 30 L65 45"/></svg>' for k in (0, 1))
        pop(f"#{bid}-sp0", s + 0.5); pop(f"#{bid}-sp1", s + 0.55)
        if bt.get("sub"):
            body += f'<div id="{bid}-sub" class="sub">{bt["sub"]}</div>'; rise(f"#{bid}-sub", at(bt.get("sub_at"), s + 1.5))
        if bt.get("rain"):
            ch = html.escape(bt["rain"]); t0 = at(bt.get("rain_at"), s + 1.5)
            body += '<div class="rain">' + "".join(f'<span class="drop" style="left:{x}px;top:{y}px;font-size:{z}px">{ch}</span>' for x, y, z in DOLLAR_XY) + "</div>"
            js.append(f'tl.fromTo("#g-{bid} .drop", {{ y: 40, opacity: 0, scale: 0.3 }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.3, stagger: 0.12, ease: "back.out(2.5)" }}, {t0:.3f});')
            js.append(f'tl.to("#g-{bid} .drop", {{ y: -40, duration: 2.2, ease: "none" }}, {t0 + 0.3:.3f});')
    elif ty == "arc":            # big curved caps phrase ("ZERO EXPERIENCE", "1 HOUR / WEEK")
        body += arc_svg(f"{bid}-arc", bt["text"], bt.get("bend", 120))
        pop(f"#g-{bid} .arc", at(bt.get("at"), s), 0.4)
        body += emoji(bid, bt, s) + sub(bid, bt, s)
    elif ty == "checklist":      # right-aligned items that tick as they're said
        items = ""
        for k, it in enumerate(bt["items"]):
            items += f'<div class="item" id="{bid}-i{k}"><span class="tick">✓</span>{it["text"]}</div>'
            slide(f"#{bid}-i{k}", at(it.get("at"), s + 0.6 * k))
            pop(f"#{bid}-i{k} .tick", at(it.get("tick"), at(it.get("at"), s + 0.6 * k) + 0.4))
        body += f'<div class="checklist">{items}</div>'
    elif ty == "counter":        # series badge + number counting up ("the rundown / WEEK 1 / $600")
        if bt.get("label") or bt.get("caps"):
            body += f'<div class="badge"><span class="badge-serif">{bt.get("label", "")}</span><span class="badge-caps">{bt.get("caps", "")}</span></div>'
            pop(f"#g-{bid} .badge", s, 0.35)
        t0 = at(bt.get("at"), s + 0.2)
        body += (f'<div id="{bid}-num" class="money" style="top:{bt.get("top", 250)}px">{html.escape(bt.get("prefix", ""))}'
                 f'<span id="{bid}-val">0</span>{html.escape(bt.get("suffix", ""))}</div>')
        pop(f"#{bid}-num", t0); count(f"{bid}-val", bt["value"], t0, bt.get("count_dur", 0.7))
        body += emoji(bid, bt, t0 + 0.4, (860, 250)) + sub(bid, bt, s, 140 if not (bt.get("label") or bt.get("caps")) else 430)
    elif ty == "bubble":         # white rounded callout; style chat|quote; optional stamp below it
        style = bt.get("style", "chat")
        body += f'<div class="bubble {style}" id="{bid}-b">{bt["html"]}</div>'
        pop(f"#{bid}-b", at(bt.get("at"), s))
        if bt.get("stamp"):
            body += f'<div id="{bid}-st" class="stamp">{html.escape(bt["stamp"])}</div>'
            js.append(f'tl.fromTo("#{bid}-st", {{ scale: 2.4, opacity: 0, rotation: -30 }}, {{ scale: 1, opacity: 1, rotation: -10, duration: 0.25, ease: "power4.out" }}, {at(bt.get("stamp_at"), s + 1):.3f});')
        body += emoji(bid, bt, s) + sub(bid, bt, s)
    elif ty == "thoughts":       # scattered small inner-monologue lines ("what am I doing???")
        for k, txt in enumerate(bt["items"][:5]):
            x, y = THOUGHT_XY[k]
            body += f'<div class="thought" id="{bid}-t{k}" style="left:{x}px;top:{y}px">{html.escape(txt)}</div>'
            ats = bt.get("at") or []
            rise(f"#{bid}-t{k}", at(ats[k], s) if k < len(ats) else s + 0.25 * k, 0.2)
    elif ty == "boxes":          # "1 of 4" tally: N boxes, first `filled` lit, rest light up at fill_at
        n, f = bt.get("count", 4), bt.get("filled", 1)
        body += f'<div class="sub" id="{bid}-l" style="top:120px">{bt.get("label", "")}</div>'
        rise(f"#{bid}-l", at(bt.get("at"), s))
        body += '<div class="boxes">' + "".join(f'<span id="{bid}-x{k}" class="bx{" on" if k < f else ""}">{k + 1}</span>' for k in range(n)) + "</div>"
        lit = ", ".join(f"#{bid}-x{k}" for k in range(f)); rest = ", ".join(f"#{bid}-x{k}" for k in range(f, n))
        pop(lit, at(bt.get("at"), s) + 0.2)
        if rest:
            js.append(f'tl.fromTo("{rest}", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.25, stagger: 0.1, ease: "back.out(2)" }}, {at(bt.get("rest_at"), s + 0.8):.3f});')
            if bt.get("fill_at"):
                js.append(f'tl.to("{rest}", {{ backgroundColor: "var(--lav)", color: "#ffffff", duration: 0.15, stagger: 0.1 }}, {at(bt["fill_at"]):.3f});')
    elif ty == "typed":          # serif line typed on ("until it happened to me")
        body += typed(f"{bid}-t", bt["text"], "title-serif mid"); typein(f"#{bid}-t", at(bt.get("at"), s), bt.get("type_speed", 0.05))
        body += sub(bid, bt, s)
    elif ty == "badge":          # series card ("UGC Diaries / DAY 1", "follow the journey / GOAL ...")
        body += f'<div class="badge"><span class="badge-serif">{bt.get("label", "")}</span><span class="badge-caps">{bt.get("caps", "")}</span></div>'
        pop(f"#g-{bid} .badge", at(bt.get("at"), s), 0.35); body += sub(bid, bt, s, 300) + emoji(bid, bt, s)
    elif ty == "cta":            # typed CTA + oversized cursor flying in and clicking it
        body += typed(f"{bid}-t", bt.get("text", "follow along!!"), "title-serif mid"); typein(f"#{bid}-t", s, 0.04)
        body += '<svg id="' + bid + '-cur" class="cursor" viewBox="0 0 24 24"><path d="M3 2 L3 19 L8 14.5 L11.5 22 L14.5 20.7 L11 13.5 L17.5 13.5 Z"/></svg>'
        click = at(bt.get("click_at"), s + 0.85)
        js.append(f'tl.fromTo("#{bid}-cur", {{ x: 420, y: 360, opacity: 0 }}, {{ x: 0, y: 0, opacity: 1, duration: 0.55, ease: "power3.out" }}, {click - 0.6:.3f});')
        js.append(f'tl.to("#{bid}-cur", {{ scale: 0.8, duration: 0.08, yoyo: true, repeat: 1 }}, {click:.3f});')
        js.append(f'tl.fromTo("#{bid}-t", {{ scale: 1 }}, {{ scale: 1.08, duration: 0.1, yoyo: true, repeat: 1 }}, {click:.3f});')
        body += sub(bid, bt, s)
    else:
        raise SystemExit(f"unknown beat type {ty}")
    if e < DUR - 0.05:
        out(f"#g-{bid} > *", e - 0.16)
    graphics.append(f'<div id="g-{bid}" class="clip g" data-start="{s:.3f}" data-duration="{e - s:.3f}" data-track-index="2"'
                    f'{" style=\"top:%dpx\"" % bt["y"] if bt.get("y") else ""}>{body}</div>')

pal = {"lav": "#6B46D9", "lavSoft": "#C9B8FF", "accent": "#2E8B3E", "ink": "#1E1B2E", "alert": "#E5484D"}
pal.update(B.get("palette", {}))
cap_top = capcfg.get("top", 1300)
CSS = f"""
      @font-face {{ font-family: "Instrument Serif"; font-style: italic; src: url("assets/fonts/InstrumentSerif-Italic.woff2") format("woff2"); }}
      @font-face {{ font-family: "Inter"; font-weight: 100 900; src: url("assets/fonts/Inter-Variable-latin.woff2") format("woff2"); }}
      :root {{ --lav: {pal['lav']}; --lav-soft: {pal['lavSoft']}; --accent: {pal['accent']}; --ink: {pal['ink']}; --alert: {pal['alert']}; }}
      body {{ margin: 0; background: BG; font-family: "Inter", sans-serif; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: BG; }}
      #aroll {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      .g {{ position: absolute; left: 0; top: 0; width: 1080px; height: 520px; }}
      .g > * {{ position: absolute; }}
      #caps {{ position: absolute; left: 0; top: {cap_top}px; width: 1080px; height: 140px; }}
      .w {{ position: absolute; left: 0; top: 0; width: 1080px; text-align: center; opacity: 0; color: #fff; font-weight: 700;
            font-size: {capcfg.get('size', 62)}px; line-height: 140px; letter-spacing: -0.5px; text-shadow: 0 2px 10px rgba(0,0,0,0.55); }}
      .w.em {{ font-family: "Instrument Serif", serif; font-style: italic; font-weight: 400; font-size: {int(capcfg.get('size', 62) * 1.48)}px;
               color: var(--lav-soft); letter-spacing: 0; }}
      .title-serif {{ left: 0; width: 1080px; text-align: center; font-family: "Instrument Serif", serif; font-style: italic;
                      color: var(--lav); text-shadow: 0 2px 0 rgba(255,255,255,0.7); }}
      .title-serif.big {{ top: 70px; font-size: 230px; line-height: 250px; }}
      .title-serif.mid {{ top: 150px; font-size: 104px; line-height: 130px; }}
      .ch {{ display: inline-block; opacity: 0; }}
      .sub {{ left: 0; top: 330px; width: 1080px; text-align: center; color: var(--ink); font-weight: 700; font-size: 50px; letter-spacing: -0.5px; }}
      .sub b {{ color: var(--lav); font-weight: 900; }}
      .sub.small {{ font-size: 38px; font-weight: 600; }}
      .spark {{ left: 120px; top: 70px; width: 110px; height: 110px; }}
      .spark.r {{ left: 850px; transform: scaleX(-1); }}
      .spark path {{ stroke: var(--ink); stroke-width: 6; stroke-linecap: round; fill: none; }}
      .rain {{ inset: 0; }}
      .drop {{ position: absolute; display: block; color: var(--accent); font-weight: 900; }}
      .arc {{ left: 0; top: 0; }}
      .arc text {{ font-family: "Inter", sans-serif; font-weight: 900; font-size: 104px; fill: var(--accent); letter-spacing: -2px; }}
      .emo {{ font-size: 110px; line-height: 1; }}
      .checklist {{ right: 60px; top: 90px; display: flex; flex-direction: column; align-items: flex-end; gap: 18px; }}
      .item {{ font-family: "Instrument Serif", serif; font-style: italic; font-size: 76px; line-height: 1; color: var(--lav); }}
      .tick {{ display: inline-block; color: var(--accent); font-family: "Inter", sans-serif; font-weight: 900; margin-right: 14px; }}
      .badge {{ left: 0; top: 70px; width: 1080px; display: flex; flex-direction: column; align-items: center; }}
      .badge-serif {{ font-family: "Instrument Serif", serif; font-style: italic; font-size: 96px; line-height: 1; color: var(--accent); }}
      .badge-caps {{ font-weight: 900; font-size: 44px; letter-spacing: 6px; color: var(--ink); margin-top: 8px; }}
      .money {{ left: 0; width: 1080px; text-align: center; font-weight: 900; font-size: 150px; letter-spacing: -4px; color: var(--accent); }}
      .bubble {{ left: 120px; top: 150px; width: 840px; padding: 30px 40px; box-sizing: border-box; text-align: center; background: #fff;
                 border: 5px solid var(--ink); border-radius: 36px; color: var(--lav); font-weight: 700; font-size: 56px; line-height: 1.15;
                 box-shadow: 8px 8px 0 var(--lav-soft); }}
      .bubble b {{ font-weight: 900; color: var(--accent); }}
      .bubble.quote {{ top: 110px; left: 70px; width: 940px; font-size: 64px; font-family: "Instrument Serif", serif; font-style: italic;
                       font-weight: 400; color: var(--ink); }}
      .thought {{ font-family: "Instrument Serif", serif; font-style: italic; font-size: 64px; color: var(--accent); line-height: 1; }}
      .stamp {{ left: 0; top: 340px; width: 1080px; text-align: center; font-weight: 900; font-size: 120px; color: var(--alert); }}
      .boxes {{ left: 0; top: 230px; width: 1080px; display: flex; justify-content: center; gap: 28px; }}
      .bx {{ display: block; width: 130px; height: 130px; border-radius: 28px; border: 5px solid var(--lav); background: #fff; color: var(--lav);
             font-weight: 900; font-size: 70px; line-height: 120px; text-align: center; }}
      .bx.on {{ background: var(--lav); color: #fff; }}
      .cursor {{ left: 700px; top: 250px; width: 120px; height: 120px; }}
      .cursor path {{ fill: #111; stroke: #fff; stroke-width: 1.5; stroke-linejoin: round; }}
"""

def page(with_video):
    video = (f'\n      <video id="aroll" class="clip" src="assets/cut.mp4" playsinline data-has-audio="true" data-start="0" '
             f'data-duration="{DUR}" data-track-index="0" data-volume="1"></video>') if with_video else ""
    caps_loop = """CAPS.forEach(([s, e, em], i) => {
        const el = "#w" + i;
        tl.set(el, { opacity: 1 }, s);
        if (em) tl.fromTo(el, { scale: 0.82 }, { scale: 1, duration: 0.12, ease: "back.out(3)" }, s);
        tl.set(el, { opacity: 0 }, e);
      });"""
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>{"Short Preview" if with_video else "Short Overlay"}</title>
    <script src="assets/gsap.min.js"></script>
    <style>{CSS.replace("BG", "#000" if with_video else "transparent")}    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="{DUR}">{video}
      <div id="caps">{''.join(cap_html)}</div>
{chr(10).join('      ' + g for g in graphics)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      const CAPS = [{','.join(cap_js)}];
      {caps_loop}
{chr(10).join('      ' + l for l in js)}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""

def gsap_path():
    """Pinned GSAP, fetched once at build time into a local cache (render itself must not hit the network)."""
    cache = os.path.join(os.path.expanduser("~"), ".cache", "short-form-editor", "gsap-3.14.2.min.js")
    if not os.path.exists(cache):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        subprocess.run(["curl", "-fsSL", "-o", cache, "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"], check=True)
    return cache

for name, with_video in (("overlay", False), ("preview", True)):
    d = os.path.join(a.out, name)
    os.makedirs(os.path.join(d, "assets", "fonts"), exist_ok=True)
    for f in os.listdir(os.path.join(SKILL, "assets", "fonts")):
        shutil.copy(os.path.join(SKILL, "assets", "fonts", f), os.path.join(d, "assets", "fonts", f))
    shutil.copy(gsap_path(), os.path.join(d, "assets", "gsap.min.js"))
    if with_video:
        dst = os.path.join(d, "assets", "cut.mp4")
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(a.video):
            shutil.copy(a.video, dst)
    open(os.path.join(d, "index.html"), "w").write(page(with_video))

print(f"duration {DUR}s, {len(toks)} caption words, {len(beats)} beats")
for bt in beats:
    print(f"  {bt['_id']:4s} {bt['type']:9s} {bt['_s']:6.2f}-{bt['_e']:6.2f}")
print(f"overlay project: {os.path.join(a.out, 'overlay')}\npreview project: {os.path.join(a.out, 'preview')}")
