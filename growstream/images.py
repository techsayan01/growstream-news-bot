"""
GrowStream — Image Agent.
Fetches landscape images from Unsplash for each article.
Deduplication: accepts a set of recently-used image slugs and skips them.
"""

import random
import re
import time

import requests

from .config import MAX_RETRIES, REQUEST_TIMEOUT, RETRY_DELAY, UNSPLASH_API_KEY, log

_FALLBACK_QUERIES = ["finance technology", "business data", "digital economy"]


def _slug_from_url(url: str) -> str:
    """Extract a normalised filename slug from an Unsplash URL for dedup comparison."""
    # Unsplash URLs look like: https://images.unsplash.com/photo-XXXX?...
    # The unique part is `photo-XXXX` in the path
    slug = url.split("?")[0].split("/")[-1]  # e.g. "photo-1234567890"
    return slug.lower()


def fetch_unsplash_images(
    image_keywords: list[str],
    category_style: str,
    count: int = 3,
    used_slugs: set[str] | None = None,
) -> list[dict]:
    """Return up to *count* Unsplash image dicts for the article.

    *used_slugs* — set of photo slugs from recent posts; photos whose slug matches
    anything in this set will be skipped so we never reuse the same image.
    """
    used_slugs = used_slugs or set()
    style_words = category_style.split()
    primary_queries = [
        " ".join(image_keywords[:2]),
        image_keywords[2] if len(image_keywords) > 2 else style_words[0],
        style_words[1] if len(style_words) > 1 else image_keywords[0],
    ]

    images: list[dict] = []
    for i in range(count):
        query = primary_queries[i] if i < len(primary_queries) else _FALLBACK_QUERIES[i]
        image = _fetch_single_image(query, i, used_slugs)
        if not image:
            log.warning("  ⚠ Trying fallback image query")
            image = _fetch_single_image(_FALLBACK_QUERIES[i % len(_FALLBACK_QUERIES)], i, used_slugs)
        if image:
            images.append(image)

    log.info(f"  📸 {len(images)}/3 images fetched (deduped against last 7d)")
    return images


def _fetch_single_image(query: str, index: int, used_slugs: set[str]) -> dict | None:
    """Fetch one unique image from Unsplash.

    Fetches a larger pool of candidates (10), shuffles them, and returns the
    first one whose slug is not in *used_slugs*. Falls back to the first
    available if all candidates were recently used.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 15,          # bigger pool → more variety
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {UNSPLASH_API_KEY}"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                return None

            # Shuffle so different days don't always lead with the exact same #1 result
            random.shuffle(results)

            chosen = None
            fallback = None
            for photo in results:
                slug = _slug_from_url(photo["urls"]["regular"])
                if fallback is None:
                    fallback = photo  # keep first as safety fallback
                if slug not in used_slugs:
                    chosen = photo
                    break

            if chosen is None:
                log.warning(f"  ⚠ All candidates for '{query}' were recently used — using fallback")
                chosen = fallback

            if chosen is None:
                return None

            # Add this slug to in-memory set so other images this run don't reuse it
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
