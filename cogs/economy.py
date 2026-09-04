import random
import time
import discord
from discord.ext import commands

import config
from database import users_col
from utils import check_access_decorator, is_owner_user, make_error_embed, make_status_embed, build_command_help_embed

COIN_EMOJI = getattr(config, "COIN_EMOJI", "<:coin:1545425273686597742>")

# -------------------------------------------------------------
# НАСТРОЙКИ ЭКОНОМИКИ И ШАНСОВ
# -------------------------------------------------------------
WORK_MIN_REWARD = 100
WORK_MAX_REWARD = 300
WORK_SUCCESS_CHANCE = 0.8  # 80% шанс успеха

CRIME_MIN_REWARD = 200
CRIME_MAX_REWARD = 500
CRIME_SUCCESS_CHANCE = 0.5  # 50% шанс успеха

ROB_SUCCESS_CHANCE = 0.3  # 30% шанс успеха
ROB_STEEL_MIN_PERCENT = 30
ROB_STEEL_MAX_PERCENT = 70
ROB_FINE_PERCENT = 0.15  # 15% от наличных при провале

SLOT_WIN_CHANCE = 0.5  # 50/50 шанс
SLOT_WEIGHTS = [30, 25, 20, 15, 10]
SLOT_MULTIPLIERS = [1.2, 1.4, 1.6, 1.8, 2.0]

ROLL_WIN_CHANCE = 0.5  # 50/50 шанс
ROLL_WEIGHTS = [30, 25, 20, 15, 10]
ROLL_MULTIPLIERS = [1.2, 1.4, 1.6, 1.8, 2.0]

# -------------------------------------------------------------
# КАНАЛЫ БЕЗ НАЧИСЛЕНИЯ ДОХОДА ЗА СООБЩЕНИЯ
# -------------------------------------------------------------
DISABLED_CHANNELS_INCOME = [
    1311385104374825102,
]

# -------------------------------------------------------------
# НАСТРОЙКИ ДОХОДА С РОЛЕЙ
# -------------------------------------------------------------
# Формат: ID_РОЛИ: СУММА_ДОХОДА
ROLE_INCOME_TABLE = {
    1437096779693686886: 15,
    1323358508900417627: 20,
    1309460485082714144: 70,
    1501508956961509436: 70,
    1323359090243670088: 40,
    1484517179780104243: 30,
    1467961492275200296: 30,
    1537847767433617448: 25,
    1475808795757252609: 25,
}

# -------------------------------------------------------------
# ТАБЛИЦЫ ФРАЗ-СИТУАЦИЙ (Плейсхолдер {amount} подставляется автоматически)
# -------------------------------------------------------------
WORK_SUCCESS_PHRASES = [
    "Вы успешно выполнили работу и заработали **+{amount}** коинов!",
    "Вы стали работником месяца и получили премию размером {amount} коинов!",
    "Отличная смена! Начальник выписал вам бонус, и ваш кошелек пополнился на **+{amount}** коинов.",
    "Вы ударно потрудились сверхурочно и заработали **+{amount}** коинов.",
    "Клиент остался в восторге от вашей работы и перевел чаевые в размере **+{amount}** коинов!",
]

WORK_FAILURE_PHRASES = [
    "Произошла ошибка на работе, вы потеряли **-{amount}** коинов.",
    "Вы случайно испортили дорогое оборудование на рабочем месте и выплатили компенсацию в **-{amount}** коинов.",
    "На работе случился форс-мажор, из-за которого вы лишились **-{amount}** коинов.",
    "Ваш рабочий день не задался, и за допущенные ошибки с вас удержали **-{amount}** коинов.",
]

CRIME_SUCCESS_PHRASES = [
    "Вам удалось совершить преступление и уйти с **+{amount}** коинов!",
    "План сработал идеально! Вы провернули темное дело и обогатились на **+{amount}** коинов.",
    "Никто ничего не заметил. Вы тихо унесли с места преступления **+{amount}** коинов!",
    "Риск стоил того — ваша афера принесла вам **+{amount}** коинов.",
]

CRIME_FAILURE_PHRASES = [
    "Вас поймали при попытке совершить преступление! Штраф: **-{amount}** коинов.",
    "Ваша афера провалилась, а местная полиция/банда отобрала у вас **-{amount}** коинов.",
    "Все пошло не по плану, и вы оставили на месте преступления **-{amount}** коинов.",
    "Вас вычислили! Пришлось срочно откупаться на **-{amount}** коинов.",
]

ROB_SUCCESS_PHRASES = [
    "Вы успешно ограбили {target} и забрали **+{amount}** коинов!",
    "Операция прошла как по маслу: вы обокрали {target} на **+{amount}** коинов!",
    "Вы застали {target} врасплох и увели прямо из-под носа **+{amount}** коинов.",
    "Ловкость рук — и карман {target} опустел на **+{amount}** коинов, которые теперь ваши!",
]

ROB_FAILURE_PHRASES = [
    "Попытка ограбления {target} не удалась! Вы потеряли **-{amount}** коинов.",
    "{target} вовремя заметил неладное и дал вам отпор. Вы потеряли **-{amount}** коинов.",
    "Попытка ограбить {target} провалилась: вас заставили заплатить за дерзость **-{amount}** коинов.",
    "{target} оказался крепким орешком и отобрал у вас **-{amount}** коинов при попытке нападения.",
]


def get_user_balance(user_id: int) -> tuple[int, int]:
    """Возвращает (cash, bank) пользователя из базы данных."""
    doc = users_col.find_one({"_id": user_id}) or {}
    cash = doc.get("cash", 0)
    bank = doc.get("bank", 0)
    return cash, bank


def update_user_balance_delta(user_id: int, cash_delta: int = 0, bank_delta: int = 0):
    inc_data = {}
    if cash_delta != 0:
        inc_data["cash"] = cash_delta
    if bank_delta != 0:
        inc_data["bank"] = bank_delta

    if inc_data:
        users_col.update_one(
            {"_id": user_id},
            {"$inc": inc_data},
            upsert=True
        )


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cooldowns = {}  # {user_id: last_timestamp}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if message.channel.id in DISABLED_CHANNELS_INCOME:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        user_id = message.author.id
        current_time = time.time()

        last_time = self.message_cooldowns.get(user_id, 0)
        if current_time - last_time < 60:
            return

        content_length = len(message.content.strip())
        if content_length == 0:
            return

        if content_length <= 5:
            reward = 2
        elif content_length <= 15:
            reward = random.randint(2, 4)
        elif content_length <= 35:
            reward = random.randint(4, 6)
        elif content_length <= 70:
            reward = random.randint(6, 8)
        else:
            reward = random.randint(8, 10)

        # Выдача награды и обновление кулдауна
        update_user_balance_delta(user_id, cash_delta=reward)
        self.message_cooldowns[user_id] = current_time

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandOnCooldown):
            unban_timestamp = int(time.time() + error.retry_after)
            relative_time = f"<t:{unban_timestamp}:R>"

            actions = {
                "work": "работать",
                "crime": "совершить преступление",
                "rob": "грабить",
                "income": "получить доход с ролей",
                "slotmachine": "играть в слот-машину",
                "roll": "бросать кости"
            }
            action_text = actions.get(ctx.command.name, f"использовать `{ctx.command.name}`")

            embed = discord.Embed(
                description=f"<a:gifclock:1544347190984441858> Вы сможете снова {action_text} {relative_time}.",
                color=config.EMBED_COLOR
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            return
        
        if isinstance(error, commands.CheckFailure):
            embed = make_error_embed("Отказ в доступе", str(error))
            await ctx.send(embed=embed)
            return

    @commands.command(name="balance", aliases=["bal"])
    @check_access_decorator("balance")
    async def balance(self, ctx: commands.Context, target: discord.Member | discord.User = None):
        target = target or ctx.author
        cash, bank = get_user_balance(target.id)
        total = cash + bank

        pipeline = [
            {
                "$project": {
                    "_id": "$_id",
                    "total": {
                        "$add": [
                            {"$ifNull": ["$cash", 0]},
                            {"$ifNull": ["$bank", 0]}
                        ]
                    }
                }
            },
            {"$match": {"total": {"$gt": 0}}},
            {"$sort": {"total": -1}}
        ]
        all_users = list(users_col.aggregate(pipeline))
        
        rank_str = "Нет в топе"
        for idx, u in enumerate(all_users, start=1):
            if u["_id"] == target.id:
                rank_str = f"{idx} место"
                break

        embed = discord.Embed(
            description=f"**Ранг в топе:** {rank_str}",
            color=config.EMBED_COLOR
        )
        
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

        embed.add_field(name="Наличные:", value=f"{COIN_EMOJI} {cash:,}", inline=True)
        embed.add_field(name="Банк:", value=f"{COIN_EMOJI} {bank:,}", inline=True)
        embed.add_field(name="Всего:", value=f"{COIN_EMOJI} {total:,}", inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="withdraw", aliases=["with"])
    @check_access_decorator("withdraw")
    async def withdraw(self, ctx: commands.Context, amount: str = None):
        if amount is None:
            return await ctx.send(embed=build_command_help_embed("withdraw"))

        cash, bank = get_user_balance(ctx.author.id)

        if bank <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "У вас нет денег на банковском счёте."))
            return

        if amount.lower() == "all":
            withdraw_amount = bank
        else:
            try:
                withdraw_amount = int(amount)
                if withdraw_amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send(embed=make_error_embed("Ошибка", "Сумма должна быть целым положительным числом."))
                return

        if withdraw_amount > bank:
            await ctx.send(embed=make_error_embed("Ошибка", "У вас недостаточно средств на банковском счёте."))
            return

        new_cash = cash + withdraw_amount
        new_bank = bank - withdraw_amount
        update_user_balance_delta(ctx.author.id, cash_delta=withdraw_amount, bank_delta=-withdraw_amount)

        embed = make_status_embed(
            "Операция выполнена",
            f"Вы успешно сняли **{withdraw_amount:,}** коинов с банка на наличный счёт.\n\n"
            f"Наличка: `{new_cash:,}` | Банк: `{new_bank:,}`",
            "success"
        )
        await ctx.send(embed=embed)

    @commands.command(name="deposit", aliases=["dep"])
    @check_access_decorator("deposit")
    async def deposit(self, ctx: commands.Context, amount: str = None):
        if amount is None:
            return await ctx.send(embed=build_command_help_embed("deposit"))

        cash, bank = get_user_balance(ctx.author.id)

        if cash <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "У вас нет наличных денег."))
            return

        if amount.lower() == "all":
            deposit_amount = cash
        else:
            try:
                deposit_amount = int(amount)
                if deposit_amount <= 0:
                    raise ValueError
            except ValueError:
                await ctx.send(embed=make_error_embed("Ошибка", "Сумма должна быть целым положительным числом."))
                return

        if deposit_amount > cash:
            await ctx.send(embed=make_error_embed("Ошибка", "У вас недостаточно наличных средств."))
            return

        new_cash = cash - deposit_amount
        new_bank = bank + deposit_amount
        update_user_balance_delta(ctx.author.id, cash_delta=-deposit_amount, bank_delta=deposit_amount)

        embed = make_status_embed(
            "Операция выполнена",
            f"Вы успешно положили **{deposit_amount:,}** коинов на свой банковский счёт.\n\n"
            f"Наличка: `{new_cash:,}` | Банк: `{new_bank:,}`",
            "success"
        )
        await ctx.send(embed=embed)

    @commands.command(name="givemoney", aliases=["give"])
    @check_access_decorator("givemoney")
    async def givemoney(self, ctx: commands.Context, target: discord.Member | discord.User = None, amount: int = None):
        if amount is None or target is None:
            return await ctx.send(embed=build_command_help_embed("givemoney"))

        if target.id == ctx.author.id:
            await ctx.send(embed=make_error_embed("Ошибка", "Вы не можете переводить деньги самому себе."))
            return

        if target.bot:
            await ctx.send(embed=make_error_embed("Ошибка", "Нельзя переводить деньги ботам."))
            return

        if amount <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "Сумма перевода должна быть больше 0."))
            return

        _, sender_bank = get_user_balance(ctx.author.id)

        if sender_bank < amount:
            await ctx.send(embed=make_error_embed("Ошибка", "У вас недостаточно средств на банковском счёте для перевода."))
            return

        update_user_balance_delta(ctx.author.id, bank_delta=-amount)
        update_user_balance_delta(target.id, bank_delta=amount)

        embed = make_status_embed(
            "Перевод выполнен",
            f"Вы перевели **{amount:,}** коинов пользователю {target.mention} с вашего банковского счёта.",
            "success"
        )
        await ctx.send(embed=embed)

    # -------------------------------------------------------------
    # Новые экономические команды и мини-игры
    # -------------------------------------------------------------

    @commands.command(name="work")
    @commands.cooldown(1, 5400, commands.BucketType.user)  # 1.5 часа (5400 сек)
    @check_access_decorator("work")
    async def work(self, ctx: commands.Context):
        amount = random.randint(WORK_MIN_REWARD, WORK_MAX_REWARD)
        is_success = random.random() < WORK_SUCCESS_CHANCE

        if is_success:
            update_user_balance_delta(ctx.author.id, cash_delta=amount)
            phrase = random.choice(WORK_SUCCESS_PHRASES).format(amount=f"{amount:,}")
            embed = make_status_embed("Работа", phrase, "success")
        else:
            # Списываем с налички (может уйти в минус)
            update_user_balance_delta(ctx.author.id, cash_delta=-amount)
            phrase = random.choice(WORK_FAILURE_PHRASES).format(amount=f"{amount:,}")
            embed = make_status_embed("Работа", phrase, "error")

        await ctx.send(embed=embed)

    @commands.command(name="crime")
    @commands.cooldown(1, 43200, commands.BucketType.user)  # 12 часов (43200 сек)
    @check_access_decorator("crime")
    async def crime(self, ctx: commands.Context):
        amount = random.randint(CRIME_MIN_REWARD, CRIME_MAX_REWARD)
        is_success = random.random() < CRIME_SUCCESS_CHANCE

        if is_success:
            update_user_balance_delta(ctx.author.id, cash_delta=amount)
            phrase = random.choice(CRIME_SUCCESS_PHRASES).format(amount=f"{amount:,}")
            embed = make_status_embed("Преступление", phrase, "success")
        else:
            # Списываем с налички (может уйти в минус)
            update_user_balance_delta(ctx.author.id, cash_delta=-amount)
            phrase = random.choice(CRIME_FAILURE_PHRASES).format(amount=f"{amount:,}")
            embed = make_status_embed("Преступление", phrase, "error")

        await ctx.send(embed=embed)

    @commands.command(name="income")
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 1 день (86400 сек)
    @check_access_decorator("income")
    async def income(self, ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=make_error_embed("Ошибка", "Эту команду можно использовать только на сервере."))
            return

        collected_roles = []
        total_income = 0
        user_role_ids = [role.id for role in ctx.author.roles]

        for role_id, reward in ROLE_INCOME_TABLE.items():
            if role_id in user_role_ids:
                total_income += reward
                collected_roles.append((role_id, reward))

        if total_income <= 0:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(embed=make_error_embed("Доход с ролей", "У вас нет ролей, приносящих доход."))
            return

        update_user_balance_delta(ctx.author.id, cash_delta=total_income)

        coin_emoji = getattr(config, "COIN_EMOJI", "<:coin:1545425273686597742>")

        role_lines = [
            f"`{idx}` - <@&{role_id}> {coin_emoji} **{reward:,}** (коинов)"
            for idx, (role_id, reward) in enumerate(collected_roles, start=1)
        ]

        description_text = "<:verify:1522329028420173976> **Вы успешно забрали доход с ролей!**\n\n" + "\n".join(role_lines)

        embed = discord.Embed(
            description=description_text,
            color=config.EMBED_COLOR
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name="rob")
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 1 день (86400 сек)
    @check_access_decorator("rob")
    async def rob(self, ctx: commands.Context, target: discord.Member | discord.User = None):

        if target is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("rob"))

        if target.id == ctx.author.id:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(embed=make_error_embed("Ошибка", "Вы не можете ограбить самого себя."))
            return

        if target.bot:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(embed=make_error_embed("Ошибка", "Нельзя грабить ботов."))
            return

        target_cash, _ = get_user_balance(target.id)

        if target_cash <= 0:
            fine = random.randint(100, 300)
            update_user_balance_delta(ctx.author.id, cash_delta=-fine)
            phrase = f"У {target.mention} нет наличных денег! Попытка не удалась, и вы потеряли **-{fine:,}** коинов."
            await ctx.send(embed=make_status_embed("Ограбление не удалось", phrase, "error"))
            return

        is_success = random.random() < ROB_SUCCESS_CHANCE

        if is_success:
            percent = random.randint(ROB_STEEL_MIN_PERCENT, ROB_STEEL_MAX_PERCENT)
            stolen_amount = int(target_cash * (percent / 100))
            if stolen_amount <= 0:
                stolen_amount = 1

            update_user_balance_delta(target.id, cash_delta=-stolen_amount)
            update_user_balance_delta(ctx.author.id, cash_delta=stolen_amount)

            phrase = random.choice(ROB_SUCCESS_PHRASES).format(
                target=target.mention,
                amount=f"{stolen_amount:,}"
            )
            embed = make_status_embed("Ограбление успешно", phrase, "success")
        else:
            author_cash, _ = get_user_balance(ctx.author.id)
            fine = int(author_cash * ROB_FINE_PERCENT)
            if fine <= 0:
                fine = random.randint(50, 150)

            update_user_balance_delta(ctx.author.id, cash_delta=-fine)

            phrase = random.choice(ROB_FAILURE_PHRASES).format(
                target=target.mention,
                amount=f"{fine:,}"
            )
            embed = make_status_embed("Ограбление не удалось", phrase, "error")

        await ctx.send(embed=embed)

    @commands.command(name="slotmachine", aliases=["slot"])
    @commands.cooldown(1, 3, commands.BucketType.user)  # 3 секунды
    @check_access_decorator("slotmachine")
    async def slotmachine(self, ctx: commands.Context, amount: int = None):
        if amount is None or amount <= 0:
            return await ctx.send(embed=build_command_help_embed("roll"))

        user_cash, _ = get_user_balance(ctx.author.id)
        if user_cash < amount:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(embed=make_error_embed("Ошибка", "У вас недостаточно **наличных** средств для этой ставки."))
            return

        is_win = random.random() < SLOT_WIN_CHANCE

        if is_win:
            mult = random.choices(SLOT_MULTIPLIERS, weights=SLOT_WEIGHTS, k=1)[0]

            total_payout = int(amount * mult)
            winnings = total_payout - amount
            update_user_balance_delta(ctx.author.id, cash_delta=winnings)

            embed = make_status_embed(
                "Слот-машина",
                f"🎰 Вы выиграли! Множитель: **x{mult}**.\nСтавка: **{amount:,}** | Выигрыш: **+{total_payout:,}** коинов.",
                "success"
            )
        else:
            update_user_balance_delta(ctx.author.id, cash_delta=-amount)
            embed = make_status_embed(
                "Слот-машина",
                f"🎰 Вы проиграли свою ставку в размере **-{amount:,}** коинов.",
                "error"
            )

        await ctx.send(embed=embed)

    @commands.command(name="roll")
    @commands.cooldown(1, 3, commands.BucketType.user)  # 3 секунды
    @check_access_decorator("roll")
    async def roll(self, ctx: commands.Context, amount: int = None, number: int = None):

        if amount is None or amount <= 0 or number is None:
            return await ctx.send(embed=build_command_help_embed("roll"))

        if number is None or number < 1 or number > 6:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(embed=make_error_embed("Ошибка", "Укажите число от 1 до 6."))
            return

        # Проверка баланса строго наличных средств (банк не учитывается)
        user_cash, _ = get_user_balance(ctx.author.id)
        if user_cash < amount:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(embed=make_error_embed("Ошибка", "У вас недостаточно **наличных** средств для этой ставки."))
            return

        is_win = random.random() < ROLL_WIN_CHANCE

        if is_win:
            dice_result = number
            mult = random.choices(ROLL_MULTIPLIERS, weights=ROLL_WEIGHTS, k=1)[0]

            total_payout = int(amount * mult)
            winnings = total_payout - amount
            update_user_balance_delta(ctx.author.id, cash_delta=winnings)

            embed = make_status_embed(
                "Кости",
                f"🎲 Выпало число **{dice_result}**! Вы угадали!\n"
                f"Множитель: **x{mult}**. Ставка: **{amount:,}** | Выигрыш: **+{total_payout:,}** коинов.",
                "success"
            )
        else:
            possible_numbers = [i for i in range(1, 7) if i != number]
            dice_result = random.choice(possible_numbers)

            update_user_balance_delta(ctx.author.id, cash_delta=-amount)
            embed = make_status_embed(
                "Кости",
                f"🎲 Выпало число **{dice_result}** (вы ставили на {number}).\n"
                f"Вы проиграли ставку: **-{amount:,}** коинов.",
                "error"
            )

        await ctx.send(embed=embed)

    # -------------------------------------------------------------
    # Команды Владельца (Owner)
    # -------------------------------------------------------------

    @commands.command(name="addmoney")
    @check_access_decorator("addmoney")
    async def addmoney(self, ctx: commands.Context, target: discord.Member | discord.User = None, amount: int = None):
        if not is_owner_user(ctx.author):
            await ctx.send(embed=make_error_embed("Отказ в доступе", "Эта команда доступна только владельцу."))
            return

        if amount is None or target is None:
            return await ctx.send(embed=build_command_help_embed("addmoney"))

        if amount <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "Сумма должна быть положительной."))
            return

        _, bank = get_user_balance(target.id)
        new_bank = bank + amount
        update_user_balance_delta(target.id, bank_delta=amount)

        embed = make_status_embed(
            "Баланс пополнен",
            f"Вы успешно добавили **{amount:,}** коинов на банковский счёт {target.mention}.\n"
            f"Новый баланс банка: `{new_bank:,}`",
            "success"
        )
        await ctx.send(embed=embed)

    @commands.command(name="removemoney")
    @check_access_decorator("removemoney")
    async def removemoney(self, ctx: commands.Context, target: discord.Member | discord.User = None, amount: int = None):
        if not is_owner_user(ctx.author):
            await ctx.send(embed=make_error_embed("Отказ в доступе", "Эта команда доступна только владельцу."))
            return

        if amount is None or target is None:
            return await ctx.send(embed=build_command_help_embed("removemoney"))

        if amount <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "Сумма должна быть положительной."))
            return

        cash, _ = get_user_balance(target.id)
        deduct_amount = min(cash, amount)
        new_cash = cash - deduct_amount
        update_user_balance_delta(target.id, cash_delta=-deduct_amount)

        embed = make_status_embed(
            "Баланс уменьшен",
            f"Вы списали **{deduct_amount:,}** коинов с наличного счёта {target.mention}.\n"
            f"Новый баланс налички: `{new_cash:,}`",
            "success"
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))