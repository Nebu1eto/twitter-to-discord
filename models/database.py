import uuid

from pendulum import DateTime as PendulumDateTime
from pydantic_extra_types.pendulum_dt import DateTime
from sqlalchemy import UniqueConstraint
from sqlmodel import Field
from sqlmodel import SQLModel


class Subscription(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    channel_id: str
    guild_id: str
    last_tweet_id: str | None = Field(default=None, nullable=True)
    last_tweeted_at: DateTime | None = Field(default=None, nullable=True)
    username: str

    fetch_type: str = Field(default="Tweets")
    ignore_replies: bool = Field(default=False)
    ignore_retweets: bool = Field(default=False)

    created_at: DateTime = Field(default_factory=lambda: PendulumDateTime.now(tz="Asia/Tokyo"))

    __table_args__ = (UniqueConstraint("username", "channel_id", name="channel_subscription"),)
