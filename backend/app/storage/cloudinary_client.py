"""Cloudinary client for rendered PNGs — upload + URL resolution.

Credentials from env vars:
  CLOUDINARY_CLOUD_NAME
  CLOUDINARY_API_KEY
  CLOUDINARY_API_SECRET

Gracefully handles missing/empty credentials: upload is skipped and "" is
returned, so callers can fall back to local file path without crashing.
"""

from __future__ import annotations

import os
from pathlib import Path


def _is_configured() -> bool:
    return bool(os.getenv("CLOUDINARY_CLOUD_NAME") and os.getenv("CLOUDINARY_API_KEY") and os.getenv("CLOUDINARY_API_SECRET"))


def _configure():
    """Configure cloudinary global state from env vars. No-op if missing."""
    if not _is_configured():
        return False
    try:
        import cloudinary
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True,
        )
        return True
    except Exception:
        return False


def upload_image(local_path: Path, public_id: str) -> str:
    """Upload a local PNG to Cloudinary and return the secure CDN URL.

    Returns "" if Cloudinary is not configured or the upload fails — caller
    should treat empty string as 'no cloud_url' and fall back to local path.
    """
    if not _is_configured():
        return ""
    if not Path(local_path).exists():
        return ""
    try:
        import cloudinary
        import cloudinary.uploader
        _configure()
        result = cloudinary.uploader.upload(
            str(local_path),
            public_id=public_id,
            overwrite=True,
            resource_type="image",
        )
        # secure_url is https, url is http fallback
        return result.get("secure_url") or result.get("url") or ""
    except Exception as exc:
        # Graceful fallback — don't crash render/publish pipeline
        print(f"[cloudinary] upload failed for {local_path} (public_id={public_id}): {exc}")
        return ""


def get_image_url(public_id: str) -> str:
    """Return the Cloudinary CDN URL for a public_id without uploading.

    Useful for building expected URLs. Returns "" if not configured.
    """
    if not _is_configured():
        return ""
    try:
        import cloudinary
        import cloudinary.utils
        _configure()
        url, _ = cloudinary.utils.cloudinary_url(public_id, secure=True)
        return url
    except Exception:
        # Fallback manual URL construction
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "")
        if cloud_name:
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}"
        return ""
