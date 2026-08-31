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
        title=f"{config.get_emoji('error')} {title}",
        description=description,
        color=discord.Color.red()
    )
    embed.set_footer(text=config.FOOTER_TEXT)
    return embed


def make_status_embed(title: str, message: str, kind: str = "info") -> discord.Embed:

    embed = discord.Embed(
        title=title,
        description=f"<:imcrine:1543711667647418381> {message}",
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
