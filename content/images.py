"""
Unsplash image fetching with 7-day deduplication.

UNSPLASH_API_KEY is read from the environment (global across all sites).
"""

import os
import random
import time
from pathlib import Path

import requests

from core.db import is_image_used
from core.retry import MAX_RETRIES, REQUEST_TIMEOUT, RETRY_DELAY
from core.utils import log

# Load .env
try:
    from dotenv import load_dotenv
    for _p in [Path(__file__).parent.parent / ".env",
               Path(__file__).parent.parent / "growstream" / ".env"]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=True)
            break
except ImportError:
    pass

UNSPLASH_API_KEY = os.environ.get("UNSPLASH_API_KEY", "")

_FALLBACK_QUERIES = ["finance technology", "business data", "digital economy"]


def _slug_from_url(url: str) -> str:
    return url.split("?")[0].split("/")[-1].lower()


def fetch_unsplash_images(
    image_keywords: list[str],
    category_style: str,
    count: int = 3,
    used_slugs: set[str] | None = None,
) -> list[dict]:
    """Return up to *count* deduplicated Unsplash image dicts."""
    used_slugs   = used_slugs or set()
    style_words  = category_style.split()
    primary_queries = [
        " ".join(image_keywords[:2]),
        image_keywords[2] if len(image_keywords) > 2 else style_words[0],
        style_words[1] if len(style_words) > 1 else image_keywords[0],
    ]

    images: list[dict] = []
    for i in range(count):
        query = primary_queries[i] if i < len(primary_queries) else _FALLBACK_QUERIES[i]
        img   = _fetch_single_image(query, i, used_slugs)
        if not img:
            log.warning("  ⚠ Trying fallback image query")
            img = _fetch_single_image(_FALLBACK_QUERIES[i % len(_FALLBACK_QUERIES)], i, used_slugs)
        if img:
            images.append(img)

    log.info(f"  📸 {len(images)}/{count} images fetched")
    return images


def _fetch_single_image(query: str, index: int, used_slugs: set[str]) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 15, "orientation": "landscape", "content_filter": "high"},
                headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if not results:
                return None

            random.shuffle(results)
            chosen   = None
            fallback = None
            for photo in results:
                slug = _slug_from_url(photo["urls"]["regular"])
                if fallback is None:
                    fallback = photo
                if slug not in used_slugs and not is_image_used(slug):
                    chosen = photo
                    break

            if chosen is None:
                log.warning(f"  ⚠ All candidates for '{query}' recently used — using fallback")
                chosen = fallback
            if chosen is None:
                return None

            used_slugs.add(_slug_from_url(chosen["urls"]["regular"]))

            # Trigger download tracking (Unsplash API requirement)
            try:
                requests.get(
                    chosen["links"]["download_location"],
                    headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
                    timeout=5,
                )
            except Exception:
                pass

            return {
                "url":              chosen["urls"]["regular"],
                "alt":              chosen.get("alt_description") or query,
                "photographer":     chosen["user"]["name"],
                "photographer_url": chosen["user"]["links"]["html"],
                "unsplash_id":      _slug_from_url(chosen["urls"]["regular"]),
                "is_hero":          index == 0,
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                log.error("  ✗ Unsplash API key invalid or rate limited")
                return None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"  ✗ Image fetch failed: {e}")
    return None
