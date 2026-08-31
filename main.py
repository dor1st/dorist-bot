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
    launch_timestamp = int(datetime.now(timezone.utc).timestamp())

    embed = discord.Embed(
        title="<:hacker:1543711533773885551> Бот запущен",
        description=(
            "Бот успешно перезапущен и готов к работе.\n"
            f"**Время запуска:** <t:{launch_timestamp}:f> (<t:{launch_timestamp}:R>)"
        ),
        color=config.EMBED_COLOR,
    )
    embed.set_footer(text=config.FOOTER_TEXT)

    channel = bot.get_channel(config.SETUP_CHANNEL_ID)
    await channel.send(embed=embed)
            

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        cmd_help = config.COMMAND_USAGE_HELP.get(ctx.command.name, f"`.{ctx.command.name}`")
        embed = make_error_embed(
            "Недостаточно аргументов",
            f"Вы указали неправильный аргумент **{error.param.name}**!\n\n**Использование команды:**\n{cmd_help}"
        )
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.BadArgument):
        cmd_help = config.COMMAND_USAGE_HELP.get(ctx.command.name, f"`.{ctx.command.name}`")
        embed = make_error_embed(
            "Неверный аргумент",
            f"Один из переданных аргументов указан неверно.\n\n**Использование:**\n{cmd_help}"
        )
        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.CheckFailure):
        embed = make_error_embed("Отказ в доступе", str(error))
        await ctx.send(embed=embed)
        return

    embed = make_error_embed("Ошибка при выполнении", str(error))
    await ctx.send(embed=embed)

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("Ошибка: DISCORD_TOKEN не найдено в переменных среды Railway")
    bot.run(BOT_TOKEN)