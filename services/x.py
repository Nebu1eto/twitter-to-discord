import json
import logging
from asyncio import sleep
from typing import TYPE_CHECKING

from twikit import Client
from twikit import Tweet
from twikit import User
from twikit import UserNotFound
from twikit import UserUnavailable

from models.config import Configuration

if TYPE_CHECKING:
    from models.base import FetchType

logger = logging.getLogger(__name__)


class XService:
    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._client = Client(language="ja-JP")
        self._client.set_cookies(json.loads(self._config.x_cookies_json), clear_cookies=True)

    async def check_user_exists(self, username: str) -> User | None:
        try:
            return await self._client.get_user_by_screen_name(username)
        except (UserNotFound, UserUnavailable):
            return None

    # TODO(250529, Haze): need to add some defense code when if latest tweet is removed.
    async def fetch_tweets(
        self, username: str, fetch_type: "FetchType", latest_id: str | None = None
    ) -> list[Tweet]:
        logger.info(f"[Fetch:@{username}] Latest Id - {latest_id}, Fetch Type - {fetch_type}")

        results: list[Tweet] = []
        user = await self._client.get_user_by_screen_name(username)
        tweets = await user.get_tweets(fetch_type, count=1 if latest_id is None else 40)
        results.extend(tweets)

        logger.info(f"[Fetch:@{username}]: {len(tweets)} Tweets")
        fetch_pages = 1

        if latest_id is not None and latest_id not in [tweet.id for tweet in tweets]:
            while fetch_pages != -1:
                if latest_id in [tweet.id for tweet in tweets]:
                    fetch_pages = -1
                    break

                await sleep(self._config.fetch_page_interval)

                logger.info(f"[Fetch:@{username}] Get {fetch_pages} Page")
                user = await self._client.get_user_by_screen_name(username)
                tweets = await tweets.next()
                if len(tweets) == 0:
                    break

                results.extend(tweets)

        return self._sort_and_trim(results, latest_id)

    @staticmethod
    def filter(tweets: list[Tweet], ignore_replies: bool = False, ignore_retweets: bool = False):
        return list(
            filter(
                lambda tweet: not (
                    (ignore_replies and tweet.in_reply_to is not None)
                    or (ignore_retweets and tweet.retweeted_tweet is not None)
                ),
                tweets,
            )
        )

    @staticmethod
    def _sort_and_trim(tweets: list[Tweet], latest_id: str | None = None) -> list[Tweet]:
        result = sorted(tweets, key=lambda x: x.created_at_datetime, reverse=True)
        if latest_id is None:
            return result

        for idx, tweet in enumerate(result):
            if tweet.id == latest_id:
                return result[0:idx]

        return result
