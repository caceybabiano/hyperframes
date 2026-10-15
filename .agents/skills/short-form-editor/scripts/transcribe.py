#!/usr/bin/env python3
"""Word-level transcription with faster-whisper.

usage: transcribe.py MEDIA OUT.json [--model small.en] [--start S --end E]

Writes [{"start","end","text","words":[{"w","s","e","p"}]}] and prints one line per segment
followed by a SUSPECTS list. Suspects are where Whisper usually hides a stumble:
  - a single word lasting > 0.6s with no silence (often swallows a false start / "um")
  - low-confidence words (p < 0.4)
Always verify suspects (envelope.py / test_cut.py) instead of trusting the timestamps.
"""
import argparse, json, os, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("media"); ap.add_argument("out")
ap.add_argument("--model", default="small.en")
ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
ap.add_argument("--no-filler-prompt", action="store_true",
                help="by default a filler-word prompt is used so 'um/uh/like' are transcribed instead of silently dropped")
a = ap.parse_args()

from faster_whisper import WhisperModel

tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, "a.wav")
cmd = ["ffmpeg", "-v", "error", "-y"]
if a.start is not None: cmd += ["-ss", str(a.start)]
cmd += ["-i", a.media]
if a.end is not None: cmd += ["-t", str(a.end - (a.start or 0))]
subprocess.run(cmd + ["-vn", "-ac", "1", "-ar", "16000", wav], check=True)
off = a.start or 0.0

m = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
segs, _ = m.transcribe(wav, word_timestamps=True, beam_size=5, vad_filter=False,
                       initial_prompt=None if a.no_filler_prompt else "Umm, uh, like, you know, so, I mean.")
out, suspects = [], []
for s in segs:
    words = [{"w": w.word.strip(), "s": round(w.start + off, 3), "e": round(w.end + off, 3), "p": round(w.probability, 2)}
             for w in s.words]
    out.append({"start": round(s.start + off, 3), "end": round(s.end + off, 3), "text": s.text.strip(), "words": words})
    print(f"[{s.start + off:7.2f}-{s.end + off:7.2f}] {s.text.strip()}", flush=True)
    for w in words:
        if w["e"] - w["s"] > 0.6: suspects.append(f"long  {w['s']:.2f}-{w['e']:.2f} '{w['w']}'")
        elif w["p"] < 0.4:       suspects.append(f"lowp  {w['s']:.2f} '{w['w']}' p={w['p']}")
json.dump(out, open(a.out, "w"), indent=1)
if suspects:
    print("\nSUSPECTS (check for hidden false starts / fillers):")
    for x in suspects: print("  " + x)
