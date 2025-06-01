from os import environ

import dotenv
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from exceptions import ConfigurationError


class Configuration(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_path: str
    discord_admin_users: list[str] = Field(default=[])
    discord_token: str
    fetch_interval: int = Field(default=10)
    fetch_page_interval: int = Field(default=10)
    timezone_text: str = Field(default="Asia/Tokyo")
    x_cookies_json: str


def read_config() -> Configuration:
    dotenv.load_dotenv()

    database_path = environ.get("DATABASE_PATH")
    raw_fetch_interval = environ.get("FETCH_INTERVAL", "10")
    raw_fetch_page_interval = environ.get("FETCH_PAGE_INTERVAL", "10")
    x_cookies_json = environ.get("X_COOKIES_JSON")
    raw_discord_admin_users = environ.get("DISCORD_ADMIN_USERS")
    discord_admin_users = (
        raw_discord_admin_users.split(",") if raw_discord_admin_users is not None else []
    )
    discord_token = environ.get("DISCORD_TOKEN")
    timezone_text = environ.get("TIMEZONE_TEXT", "Asia/Tokyo")

    if any(item is None for item in [x_cookies_json, database_path, discord_token]):
        raise ConfigurationError

    return Configuration(
        database_path=database_path,
        discord_admin_users=discord_admin_users,
        fetch_interval=int(raw_fetch_interval),
        fetch_page_interval=int(raw_fetch_page_interval),
        x_cookies_json=x_cookies_json,
        discord_token=discord_token,
        timezone_text=timezone_text,
    )


__all__ = ["Configuration", "ConfigurationError", "read_config"]
