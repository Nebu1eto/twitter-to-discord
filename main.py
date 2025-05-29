import logging
import sys

from discord import Intents
from discord import Interaction
from discord.app_commands import AppCommandError
from discord.ext import commands

from actions.subscribe import SubscribeCog
from models.config import read_config
from services.database import DatabaseService
from services.x import XService

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
    handlers=[logging.StreamHandler(stream=sys.stdout)],
)
log = logging.getLogger("bot")


class BotClient(commands.Bot):
    def __init__(self):
        super().__init__(
            intents=Intents.all(),
            command_prefix=".",
        )

    async def setup_hook(self):
        async for guild in self.fetch_guilds():
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)


config = read_config()

db = DatabaseService(config)
x = XService(config)
bot = BotClient()


@bot.event
async def on_tree_error(itn: Interaction, error: AppCommandError):
    log.warning(f"Error handled in tree error handler: {error}")
    await itn.response.send_message(error, ephemeral=True)


@bot.event
async def on_command_error(ctx: commands.context.Context, error: commands.errors.CommandError):
    if isinstance(error, commands.errors.CommandNotFound):
        return

    log.warning(f"Error handled in command error handler:  {error}")
    await ctx.send(error)


@bot.event
async def on_ready():
    bot.tree.on_error = on_tree_error

    subscribe_cog = SubscribeCog(bot=bot, config=config, db=db, x=x)
    await bot.add_cog(subscribe_cog)
    log.info(f"Bot {bot.user} is online.")
    await subscribe_cog.initialize()

    slash = await bot.tree.sync()
    log.info(f"{len(slash)} Slash commands synchronized.")


if __name__ == "__main__":
    db.initialize()
    bot.run(config.discord_token)
