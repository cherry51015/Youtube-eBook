#!/usr/bin/env python3
"""
scripts/01_ingest.py  —  Stage 1: Ingestion

Fetches playlist metadata via yt-dlp and per-video transcripts via
youtube-transcript-api. Falls back to seed transcripts automatically
when YouTube is unreachable (403, SSL, network restrictions).

Output per video: data/raw/<video_id>.json
Output playlist:  data/raw/playlist_metadata.json
"""

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths
from utils.seed_data import PLAYLIST_METADATA, SEED_TRANSCRIPTS

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def fetch_playlist_metadata(url: str) -> dict | None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        log.warning("yt-dlp not installed. pip install yt-dlp")
        return None

    opts = {"quiet": True, "extract_flat": "in_playlist",
            "skip_download": True, "nocheckcertificate": True}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        videos = [
            {"id": e["id"], "index": i + 1,
             "title": e.get("title", f"Video {i+1}"),
             "url": f"https://www.youtube.com/watch?v={e['id']}"}
            for i, e in enumerate(info.get("entries", []))
        ]
        return {"playlist_id": info.get("id", ""),
                "playlist_url": url,
                "title": info.get("title", ""),
                "videos": videos}
    except Exception as e:
        log.warning("yt-dlp failed: %s", e)
        return None


def fetch_transcript(video_id: str) -> list[dict] | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        log.warning("youtube-transcript-api not installed")
        return None

    api = YouTubeTranscriptApi()
    for attempt in range(3):
        try:
            fetched = api.fetch(video_id)
            return [{"text": s.text, "start": s.start, "duration": s.duration}
                    for s in fetched]
        except Exception as e:
            log.warning("Transcript attempt %d for %s: %s", attempt + 1, video_id, e)
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def save_raw(out_dir: Path, video: dict, segments: list[dict], source: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    full_text = " ".join(s["text"] for s in segments)
    payload = {
        "video_id": video["id"],
        "video_index": video["index"],
        "title": video["title"],
        "url": video.get("url", f"https://www.youtube.com/watch?v={video['id']}"),
        "segments": segments,
        "full_text": full_text,
        "source": source,
    }
    with open(out_dir / f"{video['id']}.json", "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    raw_dir = p["raw"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    meta_file = raw_dir / "playlist_metadata.json"

    # Playlist metadata 
    if meta_file.exists():
        log.info("Loading existing playlist metadata")
        with open(meta_file) as f:
            metadata = json.load(f)
    else:
        log.info("Fetching playlist metadata via yt-dlp …")
        metadata = fetch_playlist_metadata(cfg["playlist"]["url"])
        if metadata is None:
            log.warning("yt-dlp unavailable — using seed metadata")
            metadata = PLAYLIST_METADATA
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2)
        log.info("Saved: %s", meta_file)

    log.info("Playlist: '%s'  (%d videos)", metadata["title"], len(metadata["videos"]))

    #  Transcripts 
    counts = {"fetched": 0, "seed": 0, "skipped": 0, "failed": []}

    for video in metadata["videos"]:
        vid_id = video["id"]
        out_file = raw_dir / f"{vid_id}.json"

        if out_file.exists():
            log.info("  [%02d] SKIP  %s", video["index"], video["title"])
            counts["skipped"] += 1
            continue

        log.info("  [%02d] Fetching  %s …", video["index"], video["title"])
        segments = fetch_transcript(vid_id)

        if segments:
            save_raw(raw_dir, video, segments, source="youtube")
            log.info("       ✓ %d segments", len(segments))
            counts["fetched"] += 1
        elif vid_id in SEED_TRANSCRIPTS:
            # Build segment list from seed text
            words = SEED_TRANSCRIPTS[vid_id].strip().split()
            segs, buf, t = [], [], 0.0
            for w in words:
                buf.append(w)
                if len(buf) >= 15:
                    segs.append({"text": " ".join(buf), "start": t, "duration": 4.0})
                    buf, t = [], t + 4.0
            if buf:
                segs.append({"text": " ".join(buf), "start": t, "duration": 4.0})
            save_raw(raw_dir, video, segs, source="seed")
            log.info("       ✓ seed transcript (%d segments)", len(segs))
            counts["seed"] += 1
        else:
            log.error("       ✗ No transcript available for %s", vid_id)
            counts["failed"].append(vid_id)

        time.sleep(0.5)

    log.info("\n=== Ingest complete ===")
    log.info("  YouTube: %d  |  Seed: %d  |  Skipped: %d  |  Failed: %d",
             counts["fetched"], counts["seed"], counts["skipped"], len(counts["failed"]))
    if counts["failed"]:
        log.warning("  Failed IDs: %s", counts["failed"])


if __name__ == "__main__":
    main()
