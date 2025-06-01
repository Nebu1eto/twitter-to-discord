import json
import logging
from asyncio import sleep
from typing import TYPE_CHECKING

import pendulum
from twikit import Client
from twikit import Tweet
from twikit import User
from twikit import UserNotFound
from twikit import UserUnavailable

from models.config import Configuration

if TYPE_CHECKING:
    from pendulum import DateTime

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

    async def fetch_tweets(
        self,
        username: str,
        fetch_type: "FetchType",
        last_id: str | None = None,
        last_time: "DateTime | None" = None,
    ) -> list[Tweet]:
        logger.info(f"[Fetch:@{username}] {fetch_type}, Id - {last_id}, Time - {last_time}")
        if last_time is not None:
            last_time = pendulum.instance(last_time)

        results: list[Tweet] = []
        user = await self._client.get_user_by_screen_name(username)
        tweets = await user.get_tweets(fetch_type, count=1 if last_id is None else 40)
        results.extend(tweets)

        logger.info(f"[Fetch:@{username}]: {len(tweets)} Tweets")
        fetch_pages = 1

        if last_id is not None or last_time is not None:
            while fetch_pages != -1:
                if last_id is not None and last_id in [tweet.id for tweet in tweets]:
                    fetch_pages = -1
                    break

                if last_time is not None and any(
                    last_time.diff(tweet.created_at_datetime, abs=False).total_seconds() < 0
                    for tweet in tweets
                ):
                    fetch_pages = -1
                    break

                fetch_pages += 1
                await sleep(self._config.fetch_page_interval)

                logger.info(f"[Fetch:@{username}] Get {fetch_pages} Page")
                user = await self._client.get_user_by_screen_name(username)
                tweets = await tweets.next()
                if len(tweets) == 0:
                    break

                results.extend(tweets)

        return self._sort_and_trim(results, last_id, last_time)

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
    def _sort_and_trim(
        tweets: list[Tweet], last_id: str | None = None, last_time: "DateTime | None" = None
    ) -> list[Tweet]:
        result = sorted(tweets, key=lambda x: x.created_at_datetime, reverse=True)
        if last_id is None and last_time is None:
            return result

        for idx, tweet in enumerate(result):
            if tweet.id == last_id:
                return result[0:idx]

            if (
                last_time is not None
                and pendulum.instance(tweet.created_at_datetime).diff(last_time).total_seconds() > 0
            ):
                return result[0 : idx - 1]

        return result
