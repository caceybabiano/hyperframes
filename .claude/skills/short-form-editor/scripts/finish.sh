#!/usr/bin/env bash
# Check + render the overlay project, composite it over cut.mp4, and make delivery files.
#
# usage: finish.sh WORK_DIR [NAME]
#   expects WORK_DIR/cut.mp4 and WORK_DIR/hf/overlay/index.html (from gen_overlay.py)
# writes:
#   WORK_DIR/NAME.mp4          full-quality master (H.264 CRF 17)
#   WORK_DIR/NAME_share.mp4    two-pass copy under ~28 MB (chat/upload limits are often 25-30 MB)
#   WORK_DIR/review_sheet.jpg  20 evenly spaced frames — LOOK at it before delivering
set -euo pipefail
W="$(cd "$1" && pwd)"; NAME="${2:-short_final}"
HF="${HYPERFRAMES_CLI:-npx --yes hyperframes}"

echo "== check (overlay only — a check with the 1080x1920 A-roll loaded tends to time out)"
( cd "$W/hf/overlay" && $HF check --timeout 60000 --samples 18 2>&1 | sed -n '/^Lint/,/^Snapshots/p' | grep -v 'nested_structure\|Fix: Move\|t=0s$' ) || true

echo "== render overlay (ProRes 4444 with alpha)"
( cd "$W/hf/overlay" && $HF render --format mov -o "$W/overlay.mov" --quiet 2>&1 | tail -2 )

echo "== composite"
ffmpeg -v error -y -i "$W/cut.mp4" -i "$W/overlay.mov" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[v]" \
  -map "[v]" -map 0:a -c:v libx264 -preset slow -crf 17 -profile:v high -c:a copy -movflags +faststart "$W/$NAME.mp4"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$W/$NAME.mp4")
# target ~27 MB total: video bitrate = 27MB*8 / dur - 160k audio
VB=$(python3 -c "print(max(800, int(27*8*1000/float('$DUR')) - 170))")
LOG="$W/.twopass"
ffmpeg -v error -y -i "$W/$NAME.mp4" -c:v libx264 -preset slow -b:v ${VB}k -pass 1 -passlogfile "$LOG" -an -f null /dev/null
ffmpeg -v error -y -i "$W/$NAME.mp4" -c:v libx264 -preset slow -b:v ${VB}k -pass 2 -passlogfile "$LOG" \
  -c:a aac -b:a 160k -movflags +faststart "$W/${NAME}_share.mp4"

mkdir -p "$W/review"
python3 - "$W" "$NAME" "$DUR" <<'EOF'
import subprocess, sys
w, name, dur = sys.argv[1], sys.argv[2], float(sys.argv[3])
for i in range(20):
    t = dur * (i + 0.5) / 20
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", f"{w}/{name}.mp4", "-frames:v", "1", "-vf",
                    f"scale=270:-1,drawtext=text='{t:.1f}':x=5:y=5:fontsize=20:fontcolor=yellow:box=1:boxcolor=black",
                    f"{w}/review/r_{i:02d}.png"], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{w}/review/r_%02d.png", "-vf", "tile=5x4", f"{w}/review_sheet.jpg"], check=True)
EOF

ffmpeg -hide_banner -i "$W/$NAME.mp4" -af ebur128=framelog=quiet -f null - 2>&1 | grep -E '^\s+I:' | head -1 | sed 's/^ */loudness /'
ls -la "$W/$NAME.mp4" "$W/${NAME}_share.mp4" "$W/review_sheet.jpg"
