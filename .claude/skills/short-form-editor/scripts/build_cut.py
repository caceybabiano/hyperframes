#!/usr/bin/env python3
"""Render the jump-cut A-roll from an edit decision list.

usage: build_cut.py SOURCE EDL.json OUT_DIR [--fps 30]

EDL.json:
{
  "zoom": [1.0, 1.14],          # punch-in levels, alternated per group (reference-style jump cuts)
  "face_y": 0.30,               # vertical crop anchor (0 = top, 0.5 = center); keep the face high
  "groups": [                   # in OUTPUT order — reorder freely (the hook goes first)
    {"label": "hook", "ranges": [[5.94, 11.14]]},
    {"label": "week23", "ranges": [[66.56, 68.04], [69.30, 70.46]]}
  ]
}
Ranges are source seconds from word timestamps (first word start -> last word end).
Inside each range, pauses >= 0.30s are removed automatically; 0.06s/0.10s of padding is
added around words; slivers that are mostly silence are dropped.

Renders each segment separately and concatenates — a single filter_complex with dozens of
trims on 1080x1920 footage gets OOM-killed. Writes:
  OUT_DIR/cut.mp4            9:16 1080x1920, loudness-normalised to -14 LUFS
  OUT_DIR/cut_segments.json  segment list with source in/out and real output start times
"""
import argparse, json, os, re, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("source"); ap.add_argument("edl"); ap.add_argument("out_dir")
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--min-gap", type=float, default=0.30)
a = ap.parse_args()
os.makedirs(os.path.join(a.out_dir, "segs"), exist_ok=True)
E = json.load(open(a.edl))
ZOOM = E.get("zoom", [1.0, 1.14]); FACE_Y = E.get("face_y", 0.30)
PRE, POST, FPS = 0.06, 0.10, a.fps

# displayed source dimensions (respect phone rotation metadata)
pj = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                         "stream=width,height:stream_side_data=rotation", "-of", "json", a.source]))
st = pj["streams"][0]; W, H = st["width"], st["height"]
rot = abs(int(next((d.get("rotation", 0) for d in st.get("side_data_list", [])), 0)))
if rot in (90, 270): W, H = H, W
# largest 9:16 window in the source, then zoom inside it
bw = min(W, H * 9 / 16); bh = bw * 16 / 9

# silence map of the whole source (once)
err = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.source, "-vn", "-af", "silencedetect=n=-38dB:d=0.25", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
sil = list(zip(map(float, re.findall(r"silence_start: ([0-9.]+)", err)), map(float, re.findall(r"silence_end: ([0-9.]+)", err))))

def split(x0, x1):
    pieces, cur = [], x0
    for s, e in sil:
        if s > cur and e < x1 and e - s >= a.min_gap:
            pieces.append((cur, s + 0.04)); cur = e - 0.04
    pieces.append((cur, x1))
    return pieces

segs = []
for gi, g in enumerate(E["groups"]):
    for r0, r1 in g["ranges"]:
        for x, y in split(r0 - PRE, r1 + POST):
            x, y = round(x * FPS) / FPS, round(y * FPS) / FPS
            if y - x < 1 / FPS: continue
            if y - x < 0.35 and any(min(y, se) - max(x, ss) > 0.5 * (y - x) for ss, se in sil):
                continue  # sliver that is mostly silence
            segs.append({"group": gi, "label": g.get("label", str(gi)), "in": x, "out": y})

lst, t = [], 0.0
for i, s in enumerate(segs):
    z = ZOOM[s["group"] % len(ZOOM)]; d = s["out"] - s["in"]
    cw, ch = bw / z, bh / z
    vf = (f"crop={cw:.1f}:{ch:.1f}:(iw-{cw:.1f})/2:(ih-{ch:.1f})*{FACE_Y},"
          f"scale=1080:1920:flags=lanczos,setsar=1,fps={FPS}")
    p = os.path.join(a.out_dir, "segs", f"{i:03d}.mov")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['in']:.4f}", "-i", a.source, "-t", f"{d:.4f}",
                    "-vf", vf, "-af", f"afade=t=in:d=0.012,afade=t=out:st={max(d - 0.015, 0):.3f}:d=0.015",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p",
                    "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", p], check=True)
    real = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                          "stream=duration", "-of", "csv=p=0", p]))
    s["t"] = round(t, 4); s["dur"] = round(real, 4); t += real
    lst.append(f"file '{os.path.abspath(p)}'")
    print(f"  seg {i:02d} {s['label']:14s} src {s['in']:7.2f}-{s['out']:7.2f}  ->  out {s['t']:6.2f}", flush=True)

open(os.path.join(a.out_dir, "segs", "list.txt"), "w").write("\n".join(lst))
out = os.path.join(a.out_dir, "cut.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(a.out_dir, "segs", "list.txt"),
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
json.dump({"duration": round(t, 3), "segments": segs}, open(os.path.join(a.out_dir, "cut_segments.json"), "w"), indent=1)
print(f"{len(segs)} segments, {t:.2f}s -> {out}")
