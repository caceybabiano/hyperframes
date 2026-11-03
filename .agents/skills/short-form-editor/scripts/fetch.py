#!/usr/bin/env python3
"""Download a video from a URL (TikTok, IG, YouTube, Google Drive share link, ...) with yt-dlp.

usage: fetch.py URL OUT_DIR [--name src]
Writes OUT_DIR/<name>.<ext> (+ <name>.info.json) and prints the path.
TikTok/IG need browser impersonation (curl_cffi 0.15.x); this retries with it automatically.
"""
import argparse, glob, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("out_dir"); ap.add_argument("--name", default="src")
a = ap.parse_args()
os.makedirs(a.out_dir, exist_ok=True)
tmpl = os.path.join(a.out_dir, a.name + ".%(ext)s")
url = a.url
# Google Drive "?usp=sharing/drivesdk" links work, but the bare /view URL is the most reliable form
if "drive.google.com/file/d/" in url:
    url = url.split("/view")[0] + "/view"

base = [sys.executable, "-m", "yt_dlp", "--no-update", "--no-playlist", "-o", tmpl, "--write-info-json",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4"]
for extra in ([], ["--impersonate", "chrome"]):
    r = subprocess.run(base + extra + [url], capture_output=True, text=True)
    hits = [p for p in glob.glob(os.path.join(a.out_dir, a.name + ".*")) if not p.endswith(".json") and not p.endswith(".part")]
    if r.returncode == 0 and hits:
        print(hits[0]); sys.exit(0)
    err = (r.stderr or "").strip().splitlines()[-3:]
    print(f"[fetch] attempt {'with' if extra else 'without'} impersonation failed: {' | '.join(err)}", file=sys.stderr)
print("[fetch] could not download. For private Drive files ask the user to set 'Anyone with the link', "
      "or to upload the file directly.", file=sys.stderr)
sys.exit(1)
