import discord
from database import settings_col

OWNER_ID = 851443344718430210
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
        "commands": ["addticket", "deleteticket", "ticketlogs"],
    },
    "admin": {
        "name": "Администрация",
        "emoji": "<:mod:1522343179205087363>",
        "roles": [1322962317885046844, 1502684875868737796],
        "commands": ["deletelog", "resetlogs"],
    },
}

COMMAND_USAGE_HELP = {
    "addticket": "`.addticket [ID_модератора] [ссылка] [категория]` — Внести новый обработанный тикет в базу.",
    "deleteticket": "`.deleteticket [ID_лога] [ссылка_на_транскрипт]` — Записать удаление тикета.",
    "ticketlogs": "`.ticketlogs [ID / упоминание]` — Просмотреть логи тикетов пользователя.",
    "ticketstats": "`.ticketstats [ID / упоминание]` — Просмотреть статистику тикетов пользователя.",
    "deletelog": "`.deletelog [ID_лога]` — Удалить конкретный лог тикета.",
    "resetlogs": "`.resetlogs [ID / упоминание]` — Очистить все логи модератора.",
}

CONFIG = {}
EMBED_COLOR = discord.Color(0x212121)
FOOTER_TEXT = "ТУСОВКА ДОРИСТА"


def apply_config_globals():
    global EMBED_COLOR, FOOTER_TEXT
    EMBED_COLOR = discord.Color(CONFIG["embed_color"])
    FOOTER_TEXT = CONFIG["footer_text"]


def load_config():
    global CONFIG
    defaults = {
        "_id": "config",
        "embed_color": 0x212121,
        "footer_text": "ТУСОВКА ДОРИСТА",
        "log_channel_id": 1543903998677876836,
        "log_toggles": dict(LOGGABLE_COMMANDS_DEFAULT),
        "counting_channel_id": 1323344709724405782,
        "bump_channel_id": 1467961847511781386,
        "permission_groups": {k: dict(v) for k, v in PERMISSION_GROUPS_DEFAULT.items()},
    }

    doc = settings_col.find_one({"_id": "config"})
    if doc is None:
        settings_col.insert_one(defaults)
        doc = defaults
    else:
        updated = False
        for key, value in defaults.items():
            if key not in doc:
                doc[key] = value
                updated = True
            if updated:
                settings_col.update_one({"_id": "config"}, {"$set": doc}, upsert=True)

    CONFIG = doc
    apply_config_globals()


def update_config(patch: dict):
    global CONFIG
    settings_col.update_one({"_id": "config"}, {"$set": patch}, upsert=True)
    for key, value in patch.items():
        CONFIG[key] = value
    apply_config_globals()

# Загружаем настройки при импорте модуля
load_config()
