"""
scripts/media_blocklist.py
Permanent blocklist for Pexels video/photo IDs that must never appear
in BootHop adverts or social content.

To ban a new ID:
    from scripts.media_blocklist import block_id
    block_id(12345678, is_video=True, note="reason here")

Or edit data/media_blocklist.json directly and add the ID to the array.
"""

import json
from pathlib import Path

BLOCKLIST_PATH = Path(__file__).parent.parent / "data" / "media_blocklist.json"


def _load() -> dict:
    try:
        return json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"blocked_video_ids": [], "blocked_photo_ids": [], "notes": {}}


def is_blocked(pexels_id: int, is_video: bool = True) -> bool:
    """Return True if this Pexels ID is on the permanent blocklist."""
    data = _load()
    key  = "blocked_video_ids" if is_video else "blocked_photo_ids"
    return int(pexels_id) in data.get(key, [])


def block_id(pexels_id: int, is_video: bool = True, note: str = "") -> None:
    """Add a Pexels ID to the permanent blocklist and save immediately."""
    data = _load()
    key  = "blocked_video_ids" if is_video else "blocked_photo_ids"
    pid  = int(pexels_id)
    if pid not in data[key]:
        data[key].append(pid)
    if note:
        data.setdefault("notes", {})[str(pid)] = note
    BLOCKLIST_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  [Blocklist] Blocked {'video' if is_video else 'photo'} ID {pid}: {note}")


def blocked_video_ids() -> set[int]:
    return set(int(x) for x in _load().get("blocked_video_ids", []))


def blocked_photo_ids() -> set[int]:
    return set(int(x) for x in _load().get("blocked_photo_ids", []))


if __name__ == "__main__":
    data = _load()
    print("Blocked video IDs:", data.get("blocked_video_ids", []))
    print("Blocked photo IDs:", data.get("blocked_photo_ids", []))
    notes = data.get("notes", {})
    for k, v in notes.items():
        print(f"  {k}: {v}")
