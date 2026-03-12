"""
Twitter / X social posting.

Requires tweepy and Twitter API v2 credentials (add to .env when ready).
"""

from core.db import update_social_status
from core.utils import log
from social.base import SocialPoster


class TwitterPoster(SocialPoster):
    """Posts a thread to X / Twitter using the tweepy v2 client."""

    def __init__(
        self,
        api_key:       str,
        api_secret:    str,
        access_token:  str,
        access_secret: str,
    ):
        self.api_key       = api_key
        self.api_secret    = api_secret
        self.access_token  = access_token
        self.access_secret = access_secret

    @property
    def platform(self) -> str:
        return "twitter"

    def check_auth(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No credentials configured"
        try:
            import tweepy
            client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
            )
            me = client.get_me()
            if me.data:
                return True, f"Authenticated as @{me.data.username}"
            return False, "Could not verify credentials"
        except ImportError:
            return False, "tweepy not installed"
        except Exception as e:
            return False, str(e)[:80]

    def post(self, copy: dict, post: dict, db_row=None):
        if db_row and db_row["twitter_status"] not in ("pending", "failed"):
            log.info("  ⏭ X: not pending — skipping")
            return ["already_posted"]

        if not self.api_key:
            log.warning("  ⚠ Twitter credentials not set — skipping X post")
            return None

        try:
            import tweepy
            client    = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
            )
            tweets    = copy.get("twitter_thread", [])
            tweet_ids = []
            prev_id   = None
            for tweet in tweets:
                resp    = client.create_tweet(text=tweet[:280], in_reply_to_tweet_id=prev_id)
                prev_id = resp.data["id"]
                tweet_ids.append(prev_id)
            log.info(f"  ✅ X thread published ({len(tweet_ids)} tweets)")
            if db_row:
                update_social_status(db_row["wp_post_id"], "twitter", "published")
            return tweet_ids
        except ImportError:
            log.warning("  ⚠ tweepy not installed — skipping X post")
        except Exception as e:
            log.warning(f"  ⚠ X post failed: {e}")
            if db_row:
                update_social_status(db_row["wp_post_id"], "twitter", "failed")
        return None
