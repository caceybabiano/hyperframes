#!/usr/bin/env python3
"""Splice source ranges together (audio only) and transcribe the result — the fastest way to
check that a candidate cut point removes a stumble cleanly without clipping a word.

usage: test_cut.py MEDIA "80.0-80.50,80.90-82.7" ["85.84-88.4" ...]
Each argument is one candidate; prints what Whisper hears for each.
"""
import os, subprocess, sys, tempfile
from faster_whisper import WhisperModel

media, cands = sys.argv[1], sys.argv[2:]
m = WhisperModel("small.en", device="cpu", compute_type="int8")
tmp = tempfile.mkdtemp()
for c in cands:
    parts = [tuple(map(float, p.split("-"))) for p in c.split(",")]
    files = []
    for i, (a, b) in enumerate(parts):
        f = os.path.join(tmp, f"p{i}.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", media,
                        "-vn", "-ac", "1", "-ar", "16000", f], check=True)
        files.append(f)
    lst = os.path.join(tmp, "l.txt")
    open(lst, "w").write("\n".join(f"file '{f}'" for f in files))
    joined = os.path.join(tmp, "j.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, joined], check=True)
    segs, _ = m.transcribe(joined, initial_prompt="Umm, uh, like, so, I mean, you know.")
    print(f"{c:40s} -> {' '.join(s.text.strip() for s in segs)}")
