import discord
from discord.ext import commands

import config
from database import users_col
from utils import check_access_decorator, is_owner_user, make_error_embed, make_status_embed


def get_user_balance(user_id: int) -> tuple[int, int]:
    """Возвращает (cash, bank) пользователя из базы данных."""
    doc = users_col.find_one({"_id": user_id}) or {}
    cash = doc.get("cash", 0)
    bank = doc.get("bank", 0)
    return cash, bank


def update_user_balance(user_id: int, cash: int = None, bank: int = None):
    """Обновляет баланс наличных и/или банка у пользователя."""
    update_data = {}
    if cash is not None:
        update_data["cash"] = max(0, cash)
    if bank is not None:
        update_data["bank"] = max(0, bank)

    if update_data:
        users_col.update_one(
            {"_id": user_id},
            {"$set": update_data},
            upsert=True
        )


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------------------
    # Команды для всех игроков
    # -------------------------------------------------------------

    @commands.command(name="balance", aliases=["bal"])
    @check_access_decorator("balance")
    async def balance(self, ctx: commands.Context, target: discord.Member | discord.User = None):
        target = target or ctx.author
        cash, bank = get_user_balance(target.id)
        total = cash + bank

        embed = discord.Embed(
            title=f"Финансовый профиль — {target.display_name}",
            color=config.EMBED_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💵 Наличные", value=f"`{cash:,}` коинов", inline=True)
        embed.add_field(name="💳 Банковский счёт", value=f"`{bank:,}` коинов", inline=True)
        embed.add_field(name="💰 Всего средств", value=f"`{total:,}` коинов", inline=False)
        embed.set_footer(text=getattr(config, "FOOTER_TEXT", "Экономика"))

        await ctx.send(embed=embed)

    @commands.command(name="withdraw", aliases=["with"])
    @check_access_decorator("withdraw")
    async def withdraw(self, ctx: commands.Context, amount: str = None):
        if not amount:
            await ctx.send(embed=make_error_embed("Ошибка", "Укажите сумму или `all` для снятия."))
            return

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
        update_user_balance(ctx.author.id, cash=new_cash, bank=new_bank)

        embed = make_status_embed(
            "Операция выполнена",
            f"Вы успешно сняли **{withdraw_amount:,}** коинов с банка на наличный счёт.\n\n"
            f"💵 Наличка: `{new_cash:,}` | 💳 Банк: `{new_bank:,}`",
            "success"
        )
        await ctx.send(embed=embed)

    @commands.command(name="deposit", aliases=["dep"])
    @check_access_decorator("deposit")
    async def deposit(self, ctx: commands.Context, amount: str = None):
        if not amount:
            await ctx.send(embed=make_error_embed("Ошибка", "Укажите сумму или `all` для пополнения."))
            return

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
        update_user_balance(ctx.author.id, cash=new_cash, bank=new_bank)

        embed = make_status_embed(
            "Операция выполнена",
            f"Вы успешно положили **{deposit_amount:,}** коинов на свой банковский счёт.\n\n"
            f"💵 Наличка: `{new_cash:,}` | 💳 Банк: `{new_bank:,}`",
            "success"
        )
        await ctx.send(embed=embed)

    @commands.command(name="givemoney", aliases=["give"])
    @check_access_decorator("givemoney")
    async def givemoney(self, ctx: commands.Context, target: discord.Member | discord.User = None, amount: int = None):
        if not target or amount is None:
            await ctx.send(embed=make_error_embed("Ошибка", "Использование: `.givemoney [упоминание / ID] [сумма]`"))
            return

        if target.id == ctx.author.id:
            await ctx.send(embed=make_error_embed("Ошибка", "Вы не можете переводить деньги самому себе."))
            return

        if target.bot:
            await ctx.send(embed=make_error_embed("Ошибка", "Нельзя переводить деньги ботам."))
            return

        if amount <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "Сумма перевода должна быть больше 0."))
            return

        sender_cash, _ = get_user_balance(ctx.author.id)

        if sender_cash < amount:
            await ctx.send(embed=make_error_embed("Ошибка", "У вас недостаточно наличных средств для перевода."))
            return

        target_cash, _ = get_user_balance(target.id)

        update_user_balance(ctx.author.id, cash=sender_cash - amount)
        update_user_balance(target.id, cash=target_cash + amount)

        embed = make_status_embed(
            "Перевод выполнен",
            f"Вы перевели **{amount:,}** коинов пользователю {target.mention} с ваших наличных средств.",
            "success"
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

        if not target or amount is None:
            await ctx.send(embed=make_error_embed("Ошибка", "Использование: `.addmoney [упоминание / ID] [сумма]`"))
            return

        if amount <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "Сумма должна быть положительной."))
            return

        cash, bank = get_user_balance(target.id)
        new_cash = cash + amount
        update_user_balance(target.id, cash=new_cash)

        embed = make_status_embed(
            "Баланс пополнен",
            f"Вы успешно добавили **{amount:,}** коинов на наличный счёт {target.mention}.\n"
            f"Новый баланс налички: `{new_cash:,}`",
            "success"
        )
        await ctx.send(embed=embed)

    @commands.command(name="removemoney")
    @check_access_decorator("removemoney")
    async def removemoney(self, ctx: commands.Context, target: discord.Member | discord.User = None, amount: int = None):
        if not is_owner_user(ctx.author):
            await ctx.send(embed=make_error_embed("Отказ в доступе", "Эта команда доступна только владельцу."))
            return

        if not target or amount is None:
            await ctx.send(embed=make_error_embed("Ошибка", "Использование: `.removemoney [упоминание / ID] [сумма]`"))
            return

        if amount <= 0:
            await ctx.send(embed=make_error_embed("Ошибка", "Сумма должна быть положительной."))
            return

        cash, bank = get_user_balance(target.id)
        new_cash = max(0, cash - amount)
        update_user_balance(target.id, cash=new_cash)

        embed = make_status_embed(
            "Баланс уменьшен",
            f"Вы списали **{amount:,}** коинов с наличного счёта {target.mention}.\n"
            f"Новый баланс налички: `{new_cash:,}`",
            "success"
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))