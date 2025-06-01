import logging
import re
from uuid import UUID

import aiocron
from discord import Colour
from discord import Embed
from discord import Interaction
from discord import TextChannel
from discord import app_commands as commands
from discord.errors import DiscordException
from discord.ext.commands import Bot
from discord.ext.commands import Cog
from pendulum import DateTime
from sqlalchemy.exc import NoResultFound
from twikit import Tweet

from exceptions import SubscriptionNotFoundError
from models.base import FetchType
from models.config import Configuration
from models.database import Subscription
from services.database import DatabaseService
from services.x import XService

logger = logging.getLogger(__name__)


def get_description(subscription: Subscription, channel: str | None = None) -> str:
    reply = "Ignore Replies" if subscription.ignore_replies else "Including Replies"
    retweet = "Ignore Retweets" if subscription.ignore_retweets else "Including Retweets"
    channel = (
        f"https://discord.com/channels/{subscription.guild_id}/{subscription.channel_id} -"
        if channel is not None
        else ""
    )

    return (
        f" - Subscribing [@{subscription.username}](https://x.com/{subscription.username})'s "
        f"{subscription.fetch_type} Tab into {channel} ({reply}, {retweet})"
    )


def get_url(tweet: Tweet) -> str:
    target_tweet = tweet.retweeted_tweet if tweet.retweeted_tweet is not None else tweet
    return f"https://x.com/{target_tweet.user.screen_name}/{target_tweet.id}"


def make_embed(tweet: Tweet) -> Embed:
    tweet_text = tweet.full_text
    action_type = "Tweet"

    if tweet.retweeted_tweet is not None:
        action_type = "Retweet"
    if tweet.quote is not None:
        action_type = "Quote"
        tweet_text = (
            f"{tweet.full_text}\n\nRT @{tweet.quote.user.screen_name}: {tweet.quote.full_text}"
        )

    embed = (
        Embed(
            title=f"New {action_type} from @{tweet.user.screen_name}",
            description=tweet_text,
            url=get_url(tweet),
            color=0x1DA0F2,
            timestamp=tweet.created_at_datetime,
        )
        .set_author(
            name=f"{tweet.user.name} (@{tweet.user.screen_name})",
            icon_url=tweet.user.profile_image_url,
            url=f"https://x.com/{tweet.user.screen_name}",
        )
        .set_thumbnail(url=re.sub(r"normal(?=\.jpg$)", "400x400", tweet.user.profile_image_url))
    )

    if len(tweet.media) >= 1:
        return embed.set_image(url=tweet.media[0].media_url)

    return embed


class SubscribeCog(Cog):
    _subscriptions: dict[UUID, aiocron.Cron]

    def __init__(self, bot: Bot, config: Configuration, x: XService, db: DatabaseService):
        self._subscriptions = {}

        self._config = config
        self._bot = bot
        self._x_service = x
        self._db_service = db

    async def initialize(self):
        subscriptions = await self._db_service.subscriptions()
        for item in subscriptions:
            self.subscribe_item(item.id)

    def subscribe_item(self, subscription_id: UUID):
        if subscription_id not in self._subscriptions:
            self._subscriptions[subscription_id] = aiocron.crontab(
                f"*/{self._config.fetch_interval} * * * *",
                self.on_subscribe,
                kwargs={
                    "subscription_id": subscription_id,
                },
            )

    def unsubscribe_item(self, subscription_id: UUID):
        if subscription_id not in self._subscriptions:
            raise SubscriptionNotFoundError

        self._subscriptions[subscription_id].stop()
        self._subscriptions[subscription_id] = None

    async def on_subscribe(self, subscription_id: UUID):
        logger.info(f"[{subscription_id}] On subscribe")
        async with self._db_service.session() as session:
            try:
                subscription = await session.get_one(Subscription, subscription_id)
                channel_id = subscription.channel_id
                channel = self._bot.get_channel(int(channel_id))
                if channel is None:
                    logger.warn(f"[{subscription_id}] Failure to find channel: {channel_id}")
                    return

                ignore_replies = subscription.ignore_replies
                ignore_retweets = subscription.ignore_retweets
                logger.info(
                    f"[{subscription_id}] Subscription resolved: {channel.name} "
                    f"- ignore_replies: {ignore_replies}, ignore_retweets: {ignore_retweets}"
                )

                previous_latest_tweet_id = subscription.last_tweet_id
                tweets = await self._x_service.fetch_tweets(
                    subscription.username,
                    subscription.fetch_type,
                    last_id=subscription.last_tweet_id,
                    last_time=subscription.last_tweeted_at,
                )

                if len(tweets) == 0:
                    return

                subscription.last_tweet_id = tweets[0].id
                subscription.last_tweeted_at = tweets[0].created_at_datetime
                session.add(subscription)

                if previous_latest_tweet_id is None:
                    return

                tweets = self._x_service.filter(
                    tweets, ignore_replies=ignore_replies, ignore_retweets=ignore_retweets
                )

                text = f"{len(tweets)} New Activities from @{tweets[0].user.screen_name}"
                if len(tweets) == 1:
                    text = f"New Activity from @{tweets[0].user.screen_name}"
                if len(tweets) > 10:
                    text = (
                        f"{len(tweets)} New Activities from @{tweets[0].user.screen_name}"
                        "Due to Discord's API limitations, "
                        "Tweet embeds are displayed up to a maximum of 10."
                    )

                # NOTE(Haze): Discord only accepts up to 10 embeds.
                await channel.send(text, embeds=[make_embed(tweet) for tweet in tweets][:10])
                await session.commit()
            except NoResultFound:
                if (job := self._subscriptions.get(subscription_id, None)) is not None:
                    job.stop()
                    self._subscriptions[subscription_id] = None
            except DiscordException:
                await session.rollback()

    @commands.command(
        name="list",
        description="Retreive list of subscriptions. (For all subscriptions or specific channel.)",
    )
    async def list(
        self,
        interaction: Interaction,
        channel: TextChannel | None = None,
    ):
        channel_name = (
            "Total"
            if channel is None
            else f"https://discord.com/channels/{channel.guild.id}/{channel.id}"
        )
        subscriptions = await self._db_service.subscriptions(
            channel_id=channel.id if channel is not None else None
        )
        channels = [
            get_description(
                item, self._bot.get_channel(int(item.channel_id)) if channel is None else None
            )
            for item in subscriptions
        ]

        content = f"There are {len(subscriptions)} registered subscriptions.\n{'\n'.join(channels)}"
        await interaction.response.send_message(
            embed=Embed(
                title=f"Subscriptions ({channel_name})",
                description=content,
                colour=Colour.blue(),
                timestamp=DateTime.now(self._config.timezone_text),
            ),
            ephemeral=True,
        )

    @commands.command(
        name="subscribe",
        description="Subscribing specific Twitter user's new activities.",
    )
    @commands.choices(
        fetch=[
            commands.Choice(name="Tweets Tab", value="Tweets"),
            commands.Choice(name="Replies Tab", value="Replies"),
            commands.Choice(name="Media Tab", value="Media"),
        ],
    )
    @commands.rename(fetch="type")
    async def subscribe(
        self,
        interaction: Interaction,
        channel: TextChannel,
        username: str,
        fetch: FetchType = "Tweets",
        ignore_replies: bool = False,
        ignore_retweets: bool = False,
    ):
        user = await self._x_service.check_user_exists(username)
        if user is None:
            await interaction.response.send_message(
                embed=Embed(
                    title="Failure",
                    description=f"Failed to found Twitter user @{username}.",
                    colour=Colour.red(),
                    timestamp=DateTime.now(self._config.timezone_text),
                ),
                ephemeral=True,
            )
            return

        async with self._db_service.session() as session:
            tweets = await self._x_service.fetch_tweets(username, fetch)
            subscription = Subscription(
                username=username,
                channel_id=channel.id,
                guild_id=channel.guild.id,
                fetch_type=fetch,
                ignore_replies=ignore_replies,
                ignore_retweets=ignore_retweets,
                last_tweet_id=tweets[0].id if len(tweets) != 0 else None,
                last_tweeted_at=tweets[0].created_at_datetime if len(tweets) != 0 else None,
            )
            session.add(subscription)
            self.subscribe_item(subscription.id)
            await session.commit()

        await interaction.response.send_message(
            embed=Embed(
                title="Success",
                description=(
                    f"[@{username}](https://x.com/{username})'s new activities will posted into "
                    f"[#{channel.name}](https://discord.com/channels/{channel.guild.id}/{channel.id})."
                ),
                colour=Colour.green(),
                timestamp=DateTime.now(self._config.timezone_text),
            ),
        )
