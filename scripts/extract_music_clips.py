"""
extract_music_clips.py
Analyses each original track, finds 3 high-energy (high octane) sections,
and exports 3 x 40-second clips per track into music/clips/.

Run once manually, or re-run whenever new original tracks are added.
Output: music/clips/boothop_clip_01.mp3 ... boothop_clip_12.mp3
"""

import subprocess, sys, json
import numpy as np
from pathlib import Path

BASE          = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
ORIGINAL_DIR  = BASE / "music" / "original"
CLIPS_DIR     = BASE / "music" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

CLIP_DURATION = 40   # seconds per clip
CLIPS_PER_TRACK = 3
MIN_GAP       = 60   # minimum seconds between clip start points


def _log(msg):
    print(f"[Clips] {msg}")


def find_peak_starts(path: Path, n: int = 3, clip_len: int = 40, min_gap: int = 60) -> list[float]:
    """
    Load audio, compute RMS energy in 1-second windows,
    find n well-separated positions with highest average energy over clip_len seconds.
    """
    import librosa
    _log(f"  Analysing {path.name}...")
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    duration = len(y) / sr

    # Need at least clip_len seconds left from any start point
    max_start = duration - clip_len
    if max_start <= 0:
        _log(f"  Track too short ({duration:.0f}s) — using t=0")
        return [0.0]

    # RMS energy in 1-second windows
    frame_len = sr  # 1 second
    num_frames = int(max_start)
    energies = np.array([
        np.sqrt(np.mean(y[i * sr: i * sr + frame_len] ** 2))
        for i in range(num_frames)
    ])

    # Smooth slightly so we don't clip mid-attack
    kernel = np.ones(3) / 3
    energies = np.convolve(energies, kernel, mode='same')

    # Pick top-n starts that are at least min_gap apart
    ranked = np.argsort(energies)[::-1]
    picks  = []
    for idx in ranked:
        t = float(idx)
        if all(abs(t - p) >= min_gap for p in picks):
            picks.append(t)
        if len(picks) == n:
            break

    # If we didn't get enough (short track), fill from start
    while len(picks) < n:
        picks.append(float(len(picks) * max(min_gap, clip_len + 5)))

    picks.sort()
    return picks[:n]


def export_clip(src: Path, start: float, duration: float, dest: Path):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t",  str(duration),
        "-i",  str(src),
        "-vn",
        "-acodec", "libmp3lame", "-b:a", "192k", "-ar", "44100",
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    return r.returncode == 0


def main():
    tracks = sorted(ORIGINAL_DIR.glob("boothop_original_*.mpeg"))
    if not tracks:
        _log("No original tracks found in music/original/")
        return

    _log(f"Found {len(tracks)} original tracks — extracting {CLIPS_PER_TRACK} clips each")

    clip_index = 1
    manifest   = []

    for track in tracks:
        _log(f"Track: {track.name}")
        starts = find_peak_starts(track, n=CLIPS_PER_TRACK, clip_len=CLIP_DURATION, min_gap=MIN_GAP)

        for j, start in enumerate(starts, 1):
            dest = CLIPS_DIR / f"boothop_clip_{clip_index:02d}.mp3"
            _log(f"  Clip {j}: t={start:.1f}s -> {dest.name}")
            ok = export_clip(track, start, CLIP_DURATION, dest)
            if ok:
                manifest.append({
                    "clip":   dest.name,
                    "source": track.name,
                    "start":  round(start, 1),
                    "dur":    CLIP_DURATION,
                })
                _log(f"    Saved {dest.name}")
            else:
                _log(f"    FAILED — skipping")
            clip_index += 1

    # Write manifest
    manifest_path = CLIPS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(f"Done — {len(manifest)} clips saved to music/clips/")
    _log(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
