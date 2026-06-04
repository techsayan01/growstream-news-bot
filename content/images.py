"""
Multi-source image fetching with 7-day deduplication.

Tries sources in order: Unsplash → Pexels → Pixabay (all free/unlimited).
API keys read from environment:
  - UNSPLASH_API_KEY    (optional, recommended)
  - PEXELS_API_KEY      (optional, recommended as primary)
  - PIXABAY_API_KEY     (optional, recommended as fallback)

At least one API key should be configured for image fetching to work.
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
PEXELS_API_KEY   = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_API_KEY  = os.environ.get("PIXABAY_API_KEY", "")

_FALLBACK_QUERIES = ["finance technology", "business data", "digital economy"]


def _slug_from_url(url: str) -> str:
    return url.split("?")[0].split("/")[-1].lower()


def fetch_unsplash_images(
    image_keywords: list[str],
    category_style: str,
    count: int = 3,
    used_slugs: set[str] | None = None,
) -> list[dict]:
    """Return up to *count* deduplicated images from Unsplash → Pexels → Pixabay."""
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

        # Try sources in order: Unsplash → Pexels → Pixabay
        img = None
        if UNSPLASH_API_KEY:
            img = _fetch_from_unsplash(query, i, used_slugs)
        if not img and PEXELS_API_KEY:
            img = _fetch_from_pexels(query, i, used_slugs)
        if not img and PIXABAY_API_KEY:
            img = _fetch_from_pixabay(query, i, used_slugs)

        # Fallback queries
        if not img:
            log.warning("  ⚠ Trying fallback image query")
            fallback_query = _FALLBACK_QUERIES[i % len(_FALLBACK_QUERIES)]
            if UNSPLASH_API_KEY:
                img = _fetch_from_unsplash(fallback_query, i, used_slugs)
            if not img and PEXELS_API_KEY:
                img = _fetch_from_pexels(fallback_query, i, used_slugs)
            if not img and PIXABAY_API_KEY:
                img = _fetch_from_pixabay(fallback_query, i, used_slugs)

        if img:
            images.append(img)

    log.info(f"  📸 {len(images)}/{count} images fetched")
    return images


# ── Unsplash (highest quality, 50 req/hr free) ────────────────────────────────

def _fetch_from_unsplash(query: str, index: int, used_slugs: set[str]) -> dict | None:
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
                log.warning(f"  ⚠ Unsplash: All candidates for '{query}' recently used — using fallback")
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
                "source":           "unsplash",
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                log.warning("  ⚠ Unsplash API rate limited, trying next source")
                return None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.debug(f"  ⚠ Unsplash fetch failed: {e}")
    return None


# ── Pexels (unlimited free, great quality) ────────────────────────────────────

def _fetch_from_pexels(query: str, index: int, used_slugs: set[str]) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 15, "orientation": "landscape"},
                headers={"Authorization": PEXELS_API_KEY},
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("photos", [])
            if not results:
                return None

            random.shuffle(results)
            chosen   = None
            fallback = None
            for photo in results:
                slug = str(photo["id"])
                if fallback is None:
                    fallback = photo
                if slug not in used_slugs and not is_image_used(slug):
                    chosen = photo
                    break

            if chosen is None:
                log.warning(f"  ⚠ Pexels: All candidates for '{query}' recently used — using fallback")
                chosen = fallback
            if chosen is None:
                return None

            used_slugs.add(str(chosen["id"]))

            return {
                "url":              chosen["src"]["landscape"],  # 940x627
                "alt":              chosen.get("alt") or query,
                "photographer":     chosen["photographer"],
                "photographer_url": chosen["photographer_url"],
                "pexels_id":        str(chosen["id"]),
                "is_hero":          index == 0,
                "source":           "pexels",
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                log.warning("  ⚠ Pexels API key invalid, trying next source")
                return None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.debug(f"  ⚠ Pexels fetch failed: {e}")
    return None


# ── Pixabay (unlimited free, largest library) ──────────────────────────────────

def _fetch_from_pixabay(query: str, index: int, used_slugs: set[str]) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_API_KEY,
                    "q": query,
                    "per_page": 15,
                    "image_type": "photo",
                    "order": "popular",
                },
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            results = r.json().get("hits", [])
            if not results:
                return None

            random.shuffle(results)
            chosen   = None
            fallback = None
            for photo in results:
                slug = str(photo["id"])
                if fallback is None:
                    fallback = photo
                if slug not in used_slugs and not is_image_used(slug):
                    chosen = photo
                    break

            if chosen is None:
                log.warning(f"  ⚠ Pixabay: All candidates for '{query}' recently used — using fallback")
                chosen = fallback
            if chosen is None:
                return None

            used_slugs.add(str(chosen["id"]))

            return {
                "url":              chosen["largeImageURL"],
                "alt":              chosen.get("tags", "").split(",")[0] if chosen.get("tags") else query,
                "photographer":     chosen["user"],
                "photographer_url": f"https://pixabay.com/users/{chosen['user']}-{chosen['user_id']}/",
                "pixabay_id":       str(chosen["id"]),
                "is_hero":          index == 0,
                "source":           "pixabay",
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                log.warning("  ⚠ Pixabay API key invalid")
                return None
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.debug(f"  ⚠ Pixabay fetch failed: {e}")
    return None
