#!/usr/bin/env python3
"""Print the loudness envelope (dB, 20ms hops) of a source window so you can cut on the
real gap between words when Whisper's word timestamps are wrong (they often are around
stumbles). Dips of ~10 dB below the surrounding speech are word boundaries.

usage: envelope.py MEDIA START END
"""
import array, math, subprocess, sys

media, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
sr = 16000
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", media,
                               "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"])
a = array.array("h", raw)
hop = int(0.02 * sr)
row = []
for i in range(0, len(a) - hop, hop):
    seg = a[i:i + hop]
    db = int(20 * math.log10(math.sqrt(sum(x * x for x in seg) / len(seg)) + 1))
    row.append(f"{t0 + i / sr:.2f}:{db}")
for i in range(0, len(row), 10):
    print("  ".join(row[i:i + 10]))
