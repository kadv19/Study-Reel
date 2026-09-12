"""Seed InstaClone feed with 8 hand-curated discovery posts (idempotent)."""
import json, shutil
from pathlib import Path

SEED_JSON = Path(__file__).resolve().parent / "discovery_posts.json"
INSTACLONE_DATA = Path(__file__).resolve().parents[1] / "instaclone" / "data"
POSTS_JSON = INSTACLONE_DATA / "posts.json"
SLIDES_DIR = INSTACLONE_DATA / "slides"

def seed():
    if not SEED_JSON.exists():
        print(f"Seed JSON missing: {SEED_JSON}")
        return 1
    seeds = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    existing = []
    if POSTS_JSON.exists():
        try:
            existing = json.loads(POSTS_JSON.read_text(encoding="utf-8"))
        except:
            existing = []
    # Keep non-seed posts
    keep = [p for p in existing if not str(p.get("post_id","")).startswith("seed")]
    # For seeds, ensure slides exist: seeds already have slides in /tmp/seed_renders but also need to copy from seed output if slides missing
    # Our generate_seeds already copied slides to SLIDES_DIR, so just merge
    combined = seeds + keep
    POSTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    POSTS_JSON.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(f"Seeded {len(seeds)} discovery posts + kept {len(keep)} user posts = {len(combined)} total")
    # Verify slides
    missing = []
    for p in seeds:
        pid = p["post_id"]
        for s in p["slides"]:
            path = SLIDES_DIR / pid / Path(s["image_path"]).name
            if not path.exists():
                missing.append(str(path))
    if missing:
        print(f"WARNING missing {len(missing)} slide files: {missing[:3]}")
    else:
        print("All seed slides present")
    return 0

if __name__ == "__main__":
    raise SystemExit(seed())
