import discord

OWNER_ID = 851443344718430210
DISBOARD_BOT_ID = 302050872383242240
ALLOWED_CHANNEL_IDS = [1543958477485908048]
SETUP_CHANNEL_ID = 1543982091707093143
VALID_CATEGORIES = ["Помощь по серверу", "Получение призов", "Получение роли", "Покупка рекламы"]

LOGS_PER_PAGE = 3

LOGGABLE_COMMANDS_DEFAULT = {
    "addticket": True,
    "deleteticket": True,
    "deletelog": True,
    "resetlogs": True,
    "ticketlogs": True,
    "ticketstats": True,
    "leaderboard": True,
    "sum": False,
    "help": False,
    "config": False,
}

PERMISSION_GROUPS_DEFAULT = {
    "support": {
        "name": "Поддержка",
        "emoji": "<:ticket:1522343287816716379>",
        "roles": [1501507449860001853, 1322962344040464424],
        "commands": ["help", "ticketstats", "leaderboard", "sum"],
    },
    "transcript": {
        "name": "Транскрипты",
        "emoji": "<:logs:1522340749998428160>",
        "roles": [1542601770461569044, 1323348388762226759],
        "commands": ["addticket", "ticketlogs"],
    },
    "admin": {
        "name": "Администрация",
        "emoji": "<:mod:1522343179205087363>",
        "roles": [1542602508252487710, 1501503300200304640],
        "commands": ["deleteticket", "deletelogs"],
    },
    "owner": {
        "name": "Владелец",
        "emoji": "<:sparkles:1522342290494849034>",
        "roles": [1322962317885046844, 1502684875868737796],
        "commands": ["deletelog", "resetlogs", "config"],
    },
}

COMMAND_USAGE_HELP = {
    "addticket": "`.addticket [ID_модератора] [ссылка] [категория]` — Внести новый обработанный тикет в базу.",
    "deleteticket": "`.deleteticket [ID_лога] [ссылка_на_транскрипт]` — Записать удаление тикета.",
    "ticketlogs": "`.ticketlogs [ID / упоминание]` — Просмотреть логи тикетов пользователя.",
    "ticketstats": "`.ticketstats [ID / упоминание]` — Просмотреть статистику тикетов пользователя.",
    "deletelog": "`.deletelog [ID_лога]` — Удалить конкретный лог тикета.",
    "resetlogs": "`.resetlogs [ID / упоминание]` — Очистить все логи модератора.",
    "loggiveaway": "`.loggiveaway [ID_хостера] [приз] [количество]` — Записать проведенный розыгрыш.",
    "giveawaylogs": "`.giveawaylogs [ID / упоминание]` — Просмотреть логи розыгрышей.",
    "loginvite": "`.loginvite [ID_пригласившего] [ID_приглашенного] [приз] [количество]` — Записать приглашение.",
    "invitelogs": "`.invitelogs [ID / упоминание]` — Просмотреть логи приглашений.",
    "userinfo": "`.userinfo [ID / упоминание]` — Посмотреть профиль и роли участника.",
    "inviter": "`.inviter [ID / упоминание]` — Узнать, кто пригласил участника.",
    "invites": "`.invites [ID / упоминание]` — Узнать кол-во приглашенных участников.",
}

CONFIG = {
    "embed_color": 0x212121,
    "footer_text": "ТУСОВКА ДОРИСТА",
    "log_channel_id": 1543903998677876836,
    "log_toggles": dict(LOGGABLE_COMMANDS_DEFAULT),
    "counting_channel_id": 1323344709724405782,
    "bump_channel_id": 1467961847511781386,
    "permission_groups": {k: dict(v) for k, v in PERMISSION_GROUPS_DEFAULT.items()},
}

EMBED_COLOR = discord.Color(CONFIG["embed_color"])
FOOTER_TEXT = CONFIG["footer_text"]


def apply_config_globals():
    global EMBED_COLOR, FOOTER_TEXT
    EMBED_COLOR = discord.Color(CONFIG["embed_color"])
    FOOTER_TEXT = CONFIG["footer_text"]


def update_config(patch: dict):
    global CONFIG
    for key, value in patch.items():
        CONFIG[key] = value
    apply_config_globals()


def load_config():
    apply_config_globals()