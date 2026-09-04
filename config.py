import discord
from datetime import timedelta

OWNER_ID = 851443344718430210
DISBOARD_BOT_ID = 302050872383242240
ALLOWED_CHANNEL_IDS = [1543958477485908048]
SETUP_CHANNEL_ID = 1543982091707093143
BONUS_TIME_ROLE_ID = 1437096779693686886

VALID_CATEGORIES = ["Помощь по серверу", "Получение призов", "Получение роли", "Покупка рекламы"]
VALID_PRIZES = ["Робуксы", "Коины", "Геймпасс", "Годли"]

GIVEAWAY_EMOJI = "<:giveaway:1522331215976206446>"
MAX_DURATION = timedelta(days=31)
SETUP_TIMEOUT = 900

LOGS_PER_PAGE = 3

LOGGABLE_COMMANDS_DEFAULT = {
    "addticket": False,
    "deleteticket": False,
    "deletelog": True,
    "resetlogs": True,
    "ticketlogs": False,
    "ticketstats": False,
    "leaderboard": False,
    "loggiveaway": True,
    "deletegiveaway": True,
    "giveawaylogs": False,
    "loginvite": True,
    "deleteinvite": True,
    "invitelogs": False,
    "validinvite": False,
    "userinfo": True,
    "inviter": True,
    "invites": False,
    "messages": False,
    "sum": False,
    "help": False,
    "config": False,
    "giveaway": False,
    "checktime": False,
    "balance": False,
    "withdraw": False,
    "deposit": False,
    "givemoney": True,
    "addmoney": True,
    "removemoney": True,
}

PERMISSION_GROUPS_DEFAULT = {
    "everyone": {
        "name": "Игроки",
        "emoji": "<:voicechat:1522332045529972838>",
        "roles": [1321481502101471232],
        "commands": [
            "help",
            "messages",
            "invites",
            "withdraw", 
            "deposit", 
            "givemoney"
        ],
    },
    "support": {
        "name": "Поддержка",
        "emoji": "<:ticket:1522343287816716379>",
        "roles": [1501507449860001853, 1322962344040464424],
        "commands": [
            "help", 
            "ticketstats", 
            "leaderboard", 
            "sum", 
            "invites", 
            "messages", 
            "userinfo", 
            "inviter", 
            "userinfo", 
            "inviter", 
            "validinvite", 
            "checktime"
        ],
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
        "commands": [
            "deleteticket",
            "deletegiveaway",
            "deleteinvite",
            "invitelogs",
            "giveawaylogs",
            "loginvite",
            "loggiveaway",
            "validinvite",
            "giveaway",
            "checktime",
        ],
    },
    "owner": {
        "name": "Владелец",
        "emoji": "<:sparkles:1522342290494849034>",
        "roles": [1322962317885046844, 1502684875868737796],
        "commands": ["deletelog", "resetlogs", "config", "addmoney", "removemoney"],
    },
}

COMMAND_USAGE_HELP = {
    # Тикеты
    "addticket": "`.addticket [ID_модератора] [ссылка] [категория]` — Внести новый обработанный тикет в базу.",
    "deleteticket": "`.deleteticket [ID_лога] [ссылка_на_транскрипт]` — Записать удаление тикета.",
    "ticketlogs": "`.ticketlogs [ID / упоминание]` — Просмотреть логи тикетов пользователя.",
    "ticketstats": "`.ticketstats [ID / упоминание]` — Просмотреть статистику тикетов пользователя.",
    "deletelog": "`.deletelog [ID_лога]` — Удалить конкретный лог тикета.",
    "resetlogs": "`.resetlogs [ID / упоминание]` — Очистить все логи модератора.",
    
    # Розыгрыши
    "giveaway": "`.giveaway` — Меню управления автоматическими розыгрышами (`create`, `end`, `reroll`, `delete`).",
    "checktime": "`.checktime [ID_розыгрыша] [ID_сообщения]` — Проверить, успел ли победитель ответить в срок.",
    "loggiveaway": "`.loggiveaway [ID_хостера] [приз] [количество] [ссылка]` — Внести новый проведенный розыгрыш в базу данных.",
    "deletegiveaway": "`.deletegiveaway [ID_лога]` — Удалить запись о розыгрыше из базы данных по её ID.",
    "giveawaylogs": "`.giveawaylogs [ID / упоминание]` — Просмотреть список логов розыгрышей указанного пользователя.",
    
    # Приглашения
    "loginvite": "`.loginvite [ID_пригласившего] [ID_приглашенного] [приз] [количество]` — Записать выданную награду за приглашение игрока.",
    "deleteinvite": "`.deleteinvite [ID_лога]` — Удалить запись об инвайте из базы данных по её ID.",
    "invitelogs": "`.invitelogs [ID / упоминание]` — Посмотреть логи приглашений конкретного пользователя.",
    "inviter": "`.inviter [ID / упоминание]` — Узнать, кто пригласил указанного пользователя и получил за него приз.",
    "invites": "`.invites [ID / упоминание]` — Посмотреть общее количество засчитанных приглашений пользователя.",
    "validinvite": "`.validinvite [ID / упоминание]` — Проверить, забирал ли кто-то уже награду за данного пользователя.",

    # Экономика
    "balance": "`.balance [ID / упоминание]` — Просмотреть баланс налички и банка.",
    "withdraw": "`.withdraw [сумма / all]` — Снять деньги из банка в наличку.",
    "deposit": "`.deposit [сумма / all]` — Положить деньги из налички в банк.",
    "givemoney": "`.givemoney [ID / упоминание] [сумма]` — Передать деньги со своей налички другому игроку.",
    "addmoney": "`.addmoney [ID / упоминание] [сумма]` — Добавить деньги на баланс пользователя (наличка).",
    "removemoney": "`.removemoney [ID / упоминание] [сумма]` — Забрать деньги у пользователя.",
    
    # Общие команды и статистика
    "messages": "`.messages [ID / упоминание]` — Просмотреть количество текстовых сообщений пользователя.",
    "userinfo": "`.userinfo [ID / упоминание]` — Показать подробную информацию об аккаунте и ролях пользователя.",
}

HELP_CATEGORIES = {
    "economy": {
        "name": "Экономика",
        "emoji": "<:rbx:1522327723203235971>",
        "allowed_groups": ["everyone", "support", "transcript", "admin", "owner"],
        "commands": [
            "> `.balance` — *Просмотреть свой или чужой баланс.*",
            "> `.withdraw` — *Снять деньги с банкомата в наличные.*",
            "> `.deposit` — *Положить наличные деньги в банк.*",
            "> `.givemoney` — *Перевести наличные деньги другому игроку.*",
        ]
    },
    "tickets": {
        "name": "Тикеты",
        "emoji": "<:ticket:1522343287816716379>",
        "allowed_groups": ["support", "transcript", "admin", "owner"],
        "commands": [
            "> `.ticketstats` — *Статистика тикетов модератора.*",
            "> `.addticket` — *Записать новый обработанный тикет.*",
            "> `.ticketlogs` — *Просмотреть логи тикетов пользователя.*",
            "> `.deleteticket` — *Записать удаление тикета.*",
            "> `.deletelog` — *Удалить конкретный лог тикета.*",
            "> `.resetlogs` — *Очистить все логи модератора.*",
        ]
    },
    "giveaways": {
        "name": "Розыгрыши",
        "emoji": "<:giveaway:1522331215976206446>",
        "allowed_groups": ["owner"],
        "commands": [
            "> `.giveaway` — *Меню управления автоматическими розыгрышами.*",
            "> `.checktime` — *Проверить, успел ли победитель в срок.*",
        ]
    },
    "logs": {
        "name": "Логи",
        "emoji": "<:logs:1522340749998428160>",
        "allowed_groups": ["admin", "owner"],
        "commands": [
            "> `.loggiveaway` — *Записать проведенный розыгрыш.*",
            "> `.deletegiveaway` — *Удалить лог розыгрыша.*",
            "> `.giveawaylogs` — *Просмотреть логи розыгрышей пользователя.*",
            "> `.loginvite` — *Записать выданный приз за приглашение.*",
            "> `.deleteinvite` — *Удалить лог приглашения из базы.*",
            "> `.invitelogs` — *Посмотреть логи приглашений пользователя.*",
            "> `.inviter` — *Узнать, кто пригласил участника.*",
            "> `.invites` — *Узнать количество приглашенных участников.*",
            "> `.validinvite` — *Проверить, забирали ли приз за пользователя.*",
        ]
    },
    "other": {
        "name": "Другое",
        "emoji": "<:staff:1522338131339251823>",
        "allowed_groups": ["everyone", "support", "transcript", "admin", "owner"],
        "commands": [
            "> `.messages` — *Количество отправленных сообщений.*",
            "> `.userinfo` — *Посмотреть профиль, даты и роли участника.*",
            "> `.summaries` — *Просмотреть общие итоги и сводку.*",
        ]
    }
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
    global CONFIG
    CONFIG["permission_groups"] = {k: dict(v) for k, v in PERMISSION_GROUPS_DEFAULT.items()}
    CONFIG["log_toggles"] = {**LOGGABLE_COMMANDS_DEFAULT, **CONFIG.get("log_toggles", {})}
    apply_config_globals()