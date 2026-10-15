#!/usr/bin/env python3
"""Measure a reference short's editing rhythm and dump contact sheets to look at.

usage: analyze_reference.py REF.mp4 OUT_DIR

Prints: duration, resolution, cut times (incl. punch-in jump cuts, threshold 0.08),
average shot length, and surviving pauses. Writes OUT_DIR/sheet_NN.jpg (1 frame/sec,
6x4 grid, timestamped) — READ THESE IMAGES: caption style, title treatments, stickers,
palette and layout zones only show up visually.
"""
import json, os, re, subprocess, sys

ref, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

def probe(entries):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", ref]))

info = probe("format=duration:stream=codec_type,width,height,r_frame_rate")
dur = float(info["format"]["duration"])
v = next(s for s in info["streams"] if s["codec_type"] == "video")
print(f"duration {dur:.1f}s  {v['width']}x{v['height']}  fps {v['r_frame_rate']}")

def ff_times(vf_or_af, key, audio=False):
    args = ["ffmpeg", "-hide_banner", "-i", ref] + (["-af", vf_or_af] if audio else ["-vf", vf_or_af]) + ["-f", "null", "-"]
    err = subprocess.run(args, capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(key + r"[:=]\s*([0-9.]+)", err)]

cuts = ff_times("scale=270:-1,select='gt(scene,0.08)',showinfo", "pts_time")
cuts = [c for i, c in enumerate(cuts) if c > 0.2 and (i == 0 or c - cuts[i - 1] > 0.25)]
shots = [b - a for a, b in zip([0] + cuts, cuts + [dur])]
print(f"cuts ({len(cuts)}): " + " ".join(f"{c:.2f}" for c in cuts))
if shots:
    print(f"avg shot {sum(shots) / len(shots):.2f}s  (min {min(shots):.2f}, max {max(shots):.2f})")

ss = ff_times("silencedetect=n=-35dB:d=0.3", "silence_start", audio=True)
se = ff_times("silencedetect=n=-35dB:d=0.3", "silence_end", audio=True)
gaps = [(a, b) for a, b in zip(ss, se)]
print(f"pauses >0.3s: {len(gaps)}  " + " ".join(f"{a:.1f}({b - a:.2f}s)" for a, b in gaps))
print("tight edit (pauses removed)" if len(gaps) <= dur / 10 else "loose edit (natural pauses kept)")

subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ref, "-vf",
                "fps=1,scale=270:-1,drawtext=text='%{pts\\:hms}':x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black,tile=6x4",
                os.path.join(out, "sheet_%02d.jpg")], check=True)
sheets = sorted(f for f in os.listdir(out) if f.startswith("sheet_"))
print("contact sheets:", " ".join(os.path.join(out, s) for s in sheets))
