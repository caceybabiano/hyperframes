#!/usr/bin/env bash
# Install / verify everything the short-form-editor pipeline needs.
# Safe to re-run. Prints the HyperFrames CLI command to use at the end.
set -u

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

echo "short-form-editor setup"

command -v ffmpeg >/dev/null && ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)" || warn "ffmpeg missing — install it (apt-get install ffmpeg / brew install ffmpeg)"

PIP="python3 -m pip install -q"
python3 -c "import faster_whisper" 2>/dev/null || $PIP faster-whisper 2>/dev/null \
  || $PIP ctranslate2 tokenizers onnxruntime av huggingface_hub   # wheel build can fail; deps + a source checkout on PYTHONPATH also works
python3 -c "import faster_whisper" 2>/dev/null && ok "faster-whisper" \
  || warn "faster-whisper not importable — if you have a source checkout, export PYTHONPATH=/path/to/faster-whisper"

python3 -c "import yt_dlp" 2>/dev/null || $PIP yt-dlp
python3 -c "import yt_dlp" 2>/dev/null && ok "yt-dlp" || warn "yt-dlp not importable — a source checkout on PYTHONPATH also works"
# TikTok needs browser impersonation. yt-dlp pins curl_cffi <0.16; 0.15.0 is known-good.
python3 -c "import curl_cffi, sys; v=curl_cffi.__version__; sys.exit(0 if v.startswith('0.15') else 1)" 2>/dev/null || $PIP 'curl_cffi==0.15.0'
ok "curl_cffi (impersonation for TikTok/IG)"
python3 -c "import PIL" 2>/dev/null || $PIP pillow

# HyperFrames CLI: prefer a local build (HYPERFRAMES_CLI), else npx.
if [ -n "${HYPERFRAMES_CLI:-}" ]; then
  ok "HyperFrames CLI: $HYPERFRAMES_CLI"
elif npx --yes hyperframes --version >/dev/null 2>&1; then
  ok "HyperFrames CLI: npx --yes hyperframes"
  echo "  export HYPERFRAMES_CLI='npx --yes hyperframes'"
else
  warn "HyperFrames CLI not reachable via npx. Build a checkout: (cd hyperframes && bun install && bun run build)"
  warn "then: export HYPERFRAMES_CLI='node /path/to/hyperframes/packages/cli/dist/cli.js'"
fi
