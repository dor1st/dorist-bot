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
COIN_EMOJI = "<:coin:1545425273686597742>"
MAX_DURATION = timedelta(days=31)
SETUP_TIMEOUT = 900

LOGS_PER_PAGE = 3

ROLE_INCOME_TABLE = {
    1437096779693686886: 15,
    1323358508900417627: 20,
    1309460485082714144: 70,
}

# Все команды распределены и разрешены для использования в целевом канале
COMMAND_ALLOWED_CHANNELS = {
    # ----------------------------------------------------
    # Экономика (Economy)
    # ----------------------------------------------------
    "balance": [1311385104374825102, 1468548307553878260],
    "withdraw": [1311385104374825102, 1468548307553878260],
    "deposit": [1311385104374825102, 1468548307553878260],
    "givemoney": [1311385104374825102, 1468548307553878260],
    "addmoney": [1311385104374825102, 1468548307553878260],
    "removemoney": [1311385104374825102, 1468548307553878260],
    "work": [1311385104374825102, 1468548307553878260],
    "crime": [1311385104374825102, 1468548307553878260],
    "income": [1311385104374825102, 1468548307553878260],
    "rob": [1311385104374825102, 1468548307553878260],
    "slotmachine": [1311385104374825102, 1468548307553878260],
    "roll": [1311385104374825102, 1468548307553878260],

    # ----------------------------------------------------
    # Тикеты (Tickets)
    # ----------------------------------------------------
    "addticket": [1543958477485908048],
    "deleteticket": [1543958477485908048],
    "ticketlogs": [1543958477485908048],
    "ticketstats": [1543958477485908048],
    "deletelog": [1543958477485908048],
    "resetlogs": [1543958477485908048],

    # ----------------------------------------------------
    # Розыгрыши (Giveaways)
    # ----------------------------------------------------
    "giveaway": [1543958477485908048],
    "checktime": [1543958477485908048],
    "loggiveaway": [1543958477485908048],
    "deletegiveaway": [1543958477485908048],
    "giveawaylogs": [1543958477485908048],

    # ----------------------------------------------------
    # Приглашения (Invites)
    # ----------------------------------------------------
    "loginvite": [1543958477485908048],
    "deleteinvite": [1543958477485908048],
    "invitelogs": [1543958477485908048],
    "inviter": [1543958477485908048],
    "invites": [1543958477485908048],
    "validinvite": [1543958477485908048],

    # ----------------------------------------------------
    # Общие команды, администрирование и статистика
    # ----------------------------------------------------
    "messages": [1311385104374825102],
    "userinfo": [1311385104374825102],
    "leaderboard": [1311385104374825102],
    "summaries": [1543958477485908048],
    "help": [1311385104374825102],
    "config": [1468548307553878260],
}

LOGGABLE_COMMANDS_DEFAULT = {
    # Тикеты
    "addticket": False,
    "deleteticket": False,
    "ticketlogs": False,
    "ticketstats": False,
    "deletelog": True,
    "resetlogs": True,

    # Розыгрыши
    "giveaway": False,
    "checktime": False,
    "loggiveaway": True,
    "deletegiveaway": True,
    "giveawaylogs": False,

    # Приглашения
    "loginvite": True,
    "deleteinvite": True,
    "invitelogs": False,
    "inviter": True,
    "invites": False,
    "validinvite": False,

    # Экономика
    "balance": False,
    "withdraw": False,
    "deposit": False,
    "givemoney": True,
    "addmoney": True,
    "removemoney": True,
    "work": False,
    "crime": False,
    "income": False,
    "rob": True,
    "slotmachine": False,
    "roll": False,

    # Общие команды и статистика
    "messages": False,
    "userinfo": True,
    "leaderboard": False,
    "sum": False,
    "help": False,
    "config": False,
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
            "balance",
            "withdraw", 
            "deposit", 
            "givemoney",
            "work",
            "crime",
            "income",
            "rob",
            "slotmachine",
            "roll",
        ],
    },
    "support": {
        "name": "Поддержка",
        "emoji": "<:ticket:1522343287816716379>",
        "roles": [1501507449860001853, 1322962344040464424],
        "commands": [
            "ticketstats",
            "leaderboard",
            "userinfo", 
            "inviter", 
            "validinvite", 
            "checktime",
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
    "work": "`.work` — Поработать и заработать наличные коины.",
    "crime": "`.crime` — Совершить преступление с риском получить штраф.",
    "income": "`.income` — Забрать ежедневный доход с ваших ролей.",
    "rob": "`.rob [ID / упоминание]` — Попытаться ограбить наличные другого игрока.",
    "slotmachine": "`.slotmachine [ставка]` — Сыграть в слот-машину на наличные.",
    "roll": "`.roll [ставка] [1-6]` — Сыграть в кости на число от 1 до 6.",
    
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
            "> `.work` — *Поработать и заработать коины.*",
            "> `.crime` — *Совершить преступление с риском.*",
            "> `.income` — *Забрать доход с ваших ролей.*",
            "> `.rob` — *Попытаться ограбить наличка другого игрока.*",
            "> `.slotmachine` — *Сыграть в слот-машину.*",
            "> `.roll` — *Сыграть в кости на число 1-6.*",
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
    "allowed_channels": list(ALLOWED_CHANNEL_IDS),
    "command_allowed_channels": dict(COMMAND_ALLOWED_CHANNELS),
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
    CONFIG["command_allowed_channels"] = {**COMMAND_ALLOWED_CHANNELS, **CONFIG.get("command_allowed_channels", {})}
    CONFIG["allowed_channels"] = CONFIG.get("allowed_channels", list(ALLOWED_CHANNEL_IDS))
    CONFIG["command_allowed_channels"] = dict(COMMAND_ALLOWED_CHANNELS)
    apply_config_globals()