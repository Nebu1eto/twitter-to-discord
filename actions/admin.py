import logging
from pathlib import Path

from discord import Colour
from discord import Embed
from discord import File
from discord import Interaction
from discord import app_commands as commands
from discord.ext.commands import Bot
from discord.ext.commands import Cog

from models.config import Configuration

logger = logging.getLogger(__name__)


class AdminCog(Cog):
    def __init__(self, bot: Bot, config: Configuration):
        self._config = config
        self._bot = bot

    @commands.command(
        name="get-database",
        description="Download SQLite database file.",
    )
    async def get_database(
        self,
        interaction: Interaction,
    ):
        logger.info(f"[admin:get-database] {interaction.user.name} request database export.")
        if interaction.user.name not in self._config.discord_admin_users:
            await interaction.response.send_message(
                embed=Embed(
                    title="Error",
                    description="You are not authorized to use this command.",
                    colour=Colour.red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=Embed(
                title="Database",
                description="This is the database for the bot.",
                colour=Colour.blue(),
            ),
            file=File(Path(self._config.database_path) / "tracker.db"),
            ephemeral=True,
        )
