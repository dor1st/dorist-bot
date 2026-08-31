import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import config
from utils import make_error_embed

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)

# Перелік модулів для завантаження
INITIAL_EXTENSIONS = [
    "cogs.tickets",
    "cogs.stats",
    "cogs.admin",
    "cogs.help",
]

@bot.event
async def setup_hook():
    for ext in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(ext)
            print(f"Модуль {ext} успішно завантажено.")
        except Exception as e:
            print(f"Помилка завантаження модуля {ext}: {e}")
    await bot.tree.sync()

@bot.event
async def on_ready():
    print(f"Бот успішно авторизувався як {bot.user}")

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        cmd_help = config.COMMAND_USAGE_HELP.get(ctx.command.name, f"`.{ctx.command.name}`")
        embed = make_error_embed(
            "Недостатньо аргументів",
            f"Ви не вказали обов'язковий аргумент **{error.param.name}**!\n\n**Використання:**\n{cmd_help}"
        )
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.BadArgument):
        cmd_help = config.COMMAND_USAGE_HELP.get(ctx.command.name, f"`.{ctx.command.name}`")
        embed = make_error_embed(
            "Невірний аргумент",
            f"Один із переданих аргументів вказано невірно.\n\n**Використання:**\n{cmd_help}"
        )
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.CheckFailure):
        embed = make_error_embed("Відмова у доступі", str(error))
        await ctx.send(embed=embed)
        return

    embed = make_error_embed("Помилка під час виконання", str(error))
    await ctx.send(embed=embed)

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("Помилка: DISCORD_TOKEN не знайдено в змінних середовища Railway")
    bot.run(BOT_TOKEN)