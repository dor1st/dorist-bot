import discord
from discord.ext import commands
import config


def is_owner_user(user: discord.Member | discord.User) -> bool:
    return user.id == config.OWNER_ID


def check_access(user: discord.Member | discord.User, channel_id: int, command_name: str) -> tuple[bool, str]:
    if not isinstance(user, discord.Member):
        return False, "Команды работают только на сервере."
    if is_owner_user(user) or user.guild_permissions.administrator:
        return True, ""
    if config.ALLOWED_CHANNEL_IDS and channel_id not in config.ALLOWED_CHANNEL_IDS:
        channels_mention = ", ".join(f"<#{cid}>" for cid in config.ALLOWED_CHANNEL_IDS)
        return False, f"Эта команда доступна только в каналах: {channels_mention}"

    matched_group = False
    for group in config.CONFIG.get("permission_groups", {}).values():
        role_ids = [int(x) for x in group.get("roles", [])]
        if any(role.id in role_ids for role in user.roles):
            matched_group = True
            if command_name in group.get("commands", []):
                return True, ""
    if not matched_group:
        return False, "У вас недостаточно ролей для использования этой команды."
    return False, "Ваша группа не имеет доступа к этой команде."


def check_access_decorator(command_name: str | None = None):
    async def predicate(ctx):
        cname = command_name or ctx.command.name
        ok, msg = check_access(ctx.author, ctx.channel.id, cname)
        if not ok:
            raise commands.CheckFailure(msg)
        return True

    return commands.check(predicate)


def make_error_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"<a:alert:1544047350345891851> {title}",
        description=description,
        color=discord.Color.red()
    )
    embed.set_footer(text=config.FOOTER_TEXT)
    return embed


def make_status_embed(title: str, message: str, kind: str = "info") -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=f"<a:alert:1544047350345891851> {message}",
        color=config.EMBED_COLOR,
    )
    embed.set_footer(text=config.FOOTER_TEXT)
    return embed


async def log_action(guild: discord.Guild, command_name: str, embed: discord.Embed):
    log_toggles = config.CONFIG.get("log_toggles", config.LOGGABLE_COMMANDS_DEFAULT)
    if not log_toggles.get(command_name, False):
        return
    log_channel_id = config.CONFIG.get("log_channel_id")
    if not log_channel_id:
        return
    channel = guild.get_channel(log_channel_id)
    if channel:
        await channel.send(embed=embed)


def build_command_help_embed(command_name: str) -> discord.Embed:
    embed = discord.Embed(color=config.EMBED_COLOR)

    if command_name == "addticket":
        cats = ", ".join(f"`{c}`" for c in getattr(config, "VALID_CATEGORIES", []))
        embed.title = "Команда: addticket"
        embed.description = (
            "Добавить новый лог об обработанном тикете\n\n"
            "**Кулдаун:**\n"
            "3 секунды (Для Администрации отсутствует)\n\n"
            "**Правила аргументов:**\n"
            "1. Ссылка должна содержать: `https://discord.com/`\n"
            "2. Вы **не можете** указать свой собственный ID\n"
            "3. Один и тот же транскрипт нельзя вносить дважды\n"
            f"4. Допустимые категории: {cats}\n\n"
            "**Использование:**\n"
            "`.addticket [ID модератора] [ссылка на транскрипт] [категория]`\n\n"
            "**Пример:**\n"
            "`.addticket 851443344718430210 https://discord.com/channels/... Получение призов`"
        )
    elif command_name == "deleteticket":
        embed.title = "Команда: deleteticket"
        embed.description = (
            "Удалить запись о тикете\n\n"
            "**Правила аргументов:**\n"
            "1. Ссылка должна содержать: `https://discord.com/`\n\n"
            "**Использование:**\n"
            "`.deleteticket [ID лога] [ссылка на транскрипт]`\n\n"
            "**Пример:**\n"
            "`.deleteticket 12 https://discord.com/channels/...`"
        )
    elif command_name == "ticketlogs":
        embed.title = "Команда: ticketlogs"
        embed.description = (
            "Просмотреть список всех зафиксированных логов тикетов модератора\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите упоминание или ID модератора (необязательно).\n"
            "2. Если аргумент не указан, выводятся ваши логи.\n\n"
            "**Использование:**\n"
            "`.ticketlogs [упоминание / ID модератора]`\n\n"
            "**Пример:**\n"
            "`.ticketlogs @Пользователь` или `.tl 851443344718430210`"
        )

    embed.set_footer(text=config.FOOTER_TEXT)
    return embed