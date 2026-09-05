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
    elif command_name in ("withdraw", "with"):
        embed.title = "Команда: withdraw"
        embed.description = (
            "Снять средства с банковского счёта на наличный\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите сумму числом или `all` для снятия всех средств.\n\n"
            "**Использование:**\n"
            "`.withdraw [сумма / all]`\n\n"
            "**Пример:**\n"
            "`.withdraw 500` или `.with all`"
        )
    elif command_name in ("deposit", "dep"):
        embed.title = "Команда: deposit"
        embed.description = (
            "Положить наличные средства на банковский счёт\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите сумму числом или `all` для перевода всей налички.\n\n"
            "**Использование:**\n"
            "`.deposit [сумма / all]`\n\n"
            "**Пример:**\n"
            "`.deposit 1000` или `.dep all`"
        )
    elif command_name in ("givemoney", "give"):
        embed.title = "Команда: givemoney"
        embed.description = (
            "Передать наличные средства другому пользователю\n\n"
            "**Правила аргументов:**\n"
            "1. Нельзя переводить средства самому себе или ботам.\n"
            "2. Сумма должна быть положительной и не превышать ваш баланс налички.\n\n"
            "**Использование:**\n"
            "`.givemoney [пользователь] [сумма]`\n\n"
            "**Пример:**\n"
            "`.givemoney @Пользователь 250`"
        )
    elif command_name == "rob":
        embed.title = "Команда: rob"
        embed.description = (
            "Попытаться ограбить другого пользователя\n\n"
            "**Правила аргументов:**\n"
            "1. Нельзя грабить самого себя или ботов.\n"
            "2. У жертвы должны быть наличные средства на руках.\n\n"
            "**Использование:**\n"
            "`.rob [пользователь]`\n\n"
            "**Пример:**\n"
            "`.rob @Пользователь`"
        )
    elif command_name in ("slotmachine", "slot"):
        embed.title = "Команда: slotmachine"
        embed.description = (
            "Сделать ставку в слот-машине\n\n"
            "**Правила аргументов:**\n"
            "1. Ставка должна быть положительным целым числом.\n"
            "2. Средства списываются с наличного счёта.\n\n"
            "**Использование:**\n"
            "`.slotmachine [ставка]`\n\n"
            "**Пример:**\n"
            "`.slot 100`"
        )
    elif command_name == "roll":
        embed.title = "Команда: roll"
        embed.description = (
            "Испытать удачу в игре в кости\n\n"
            "**Правила аргументов:**\n"
            "1. Ставка должна быть положительным целым числом.\n"
            "2. Число должно быть в диапазоне от 1 до 6.\n\n"
            "**Использование:**\n"
            "`.roll [ставка] [число 1-6]`\n\n"
            "**Пример:**\n"
            "`.roll 100 4`"
        )
    elif command_name == "addmoney":
        embed.title = "Команда: addmoney"
        embed.description = (
            "Выдать наличные средства пользователю (только для владельца)\n\n"
            "**Использование:**\n"
            "`.addmoney [пользователь] [сумма]`\n\n"
            "**Пример:**\n"
            "`.addmoney @Пользователь 5000`"
        )
    elif command_name == "removemoney":
        embed.title = "Команда: removemoney"
        embed.description = (
            "Забрать наличные средства у пользователя (только для владельца)\n\n"
            "**Использование:**\n"
            "`.removemoney [пользователь] [сумма]`\n\n"
            "**Пример:**\n"
            "`.removemoney @Пользователь 1000`"
        )
    elif command_name in ("messages", "msg", "msgs", "message"):
        embed.title = "Команда: messages"
        embed.description = (
            "Просмотреть количество отправленных текстовых сообщений пользователя\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите упоминание или ID пользователя (необязательно).\n"
            "2. Если аргумент не указан, выводится ваша статистика.\n\n"
            "**Использование:**\n"
            "`.messages [упоминание / ID пользователя]`\n\n"
            "**Пример:**\n"
            "`.messages @Пользователь` или `.msg 851443344718430210`"
        )
    elif command_name in ("invites", "inv"):
        embed.title = "Команда: invites"
        embed.description = (
            "Просмотреть количество приглашённых участников пользователя\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите упоминание или ID пользователя (необязательно).\n"
            "2. Если аргумент не указан, выводится ваша статистика.\n\n"
            "**Использование:**\n"
            "`.invites [упоминание / ID пользователя]`\n\n"
            "**Пример:**\n"
            "`.invites @Пользователь` или `.inv 851443344718430210`"
        )
    elif command_name in ("summaries", "sum"):
        embed.title = "Команда: summaries"
        embed.description = (
            "Просмотреть сводную статистику по считалке и бампам за разные периоды\n\n"
            "**Правила аргументов:**\n"
            "1. В качестве аргумента можно указать `ex` или `extended` для расширенного топа (топ-10 вместо топ-3).\n\n"
            "**Использование:**\n"
            "`.summaries [ex / extended]`\n\n"
            "**Пример:**\n"
            "`.sum` или `.summaries extended`"
        )
    elif command_name in ("leaderboard", "lb"):
        embed.title = "Команда: leaderboard"
        embed.description = (
            "Просмотреть лидерборд по выбранной категории\n\n"
            "**Допустимые категории:**\n"
            "• `messages` / `m` - Топ 5 по сообщениям\n"
            "• `invites` / `i` - Топ 5 по приглашениям\n"
            "• `tickets` / `t` - Лидерборд тикетов, транскриптов и удалений\n"
            "• `economy` / `ec` - Топ 5 самых богатых участников\n\n"
            "**Использование:**\n"
            "`.leaderboard [категория]`\n\n"
            "**Пример:**\n"
            "`.lb messages` или `.lb tickets`"
        )
    elif command_name == "deletelog":
        embed.title = "Команда: deletelog"
        embed.description = (
            "Удалить лог тикета из базы данных по его ID\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите числовой ID лога тикета.\n\n"
            "**Использование:**\n"
            "`.deletelog [ID лога]`\n\n"
            "**Пример:**\n"
            "`.deletelog 15`"
        )
    elif command_name == "resetlogs":
        embed.title = "Команда: resetlogs"
        embed.description = (
            "Полностью сбросить все логи тикетов и удалений конкретного модератора\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите упоминание или ID пользователя.\n\n"
            "**Использование:**\n"
            "`.resetlogs [упоминание / ID модератора]`\n\n"
            "**Пример:**\n"
            "`.resetlogs @Пользователь`"
        )
    elif command_name in ("config", "cfg"):
        embed.title = "Команда: config"
        embed.description = (
            "Открыть меню просмотра конфигурации бота (доступно только владельцу)\n\n"
            "**Использование:**\n"
            "`.config`\n\n"
            "**Пример:**\n"
            "`.cfg`"
        )
    elif command_name in ("giveaway", "giveaways", "gw", "gws"):
        embed.title = "Команда: giveaway"
        embed.description = (
            "Управление системами и проведением розыгрышей\n\n"
            "**Подкоманды:**\n"
            "• `create` / `cr` - Создать новый розыгрыш через меню настройки\n"
            "• `end` - Завершить активный розыгрыш досрочно по ID сообщения\n"
            "• `reroll` / `rr` - Перевыбрать победителя завершённого розыгрыша\n"
            "• `delete` / `del` - Удалить розыгрыш из базы данных и чата\n"
            "• `checktime` / `ct` - Проверить, успел ли победитель ответить вовремя\n\n"
            "**Использование:**\n"
            "`.giveaway create [приз] [длительность] [победители] [время на получение]`\n"
            "`.giveaway end [ID сообщения]`\n"
            "`.giveaway reroll [ID сообщения]`\n"
            "`.giveaway delete [ID сообщения]`\n\n"
            "**Пример:**\n"
            "`.gw cr 1000 Robux 7d 1 24h` или `.gw rr 134567890123456789`"
        )
    elif command_name in ("checktime", "ct"):
        embed.title = "Команда: checktime"
        embed.description = (
            "Проверить, ответил ли победитель розыгрыша в отведённые временные рамки\n\n"
            "**Правила аргументов:**\n"
            "1. Укажите ID сообщения розыгрыша.\n"
            "2. Укажите ID сообщения-ответа победителя в текущем канале.\n\n"
            "**Использование:**\n"
            "`.checktime [ID_сообщения_розыгрыша] [ID_сообщения_игрока]`\n\n"
            "**Пример:**\n"
            "`.checktime 134567890123456789 134567890987654321`"
        )

    return embed

    embed.set_footer(text=config.FOOTER_TEXT)
    return embed