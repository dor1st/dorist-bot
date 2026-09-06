import asyncio
import math
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands

import config
from database import (
    bump_stats_col,
    deleted_tickets_col,
    invites_col,
    message_stats_col,
    tickets_col,
    users_col,
    giveaways_col,
    get_next_sequence_value,
)
from utils import check_access_decorator, make_error_embed, make_status_embed, log_action

BUMP_REMINDER_MESSAGE = "**<a:gifclock:1544347190984441858> <@&1501943871960125461> Пришло время бампа! (/bump)**"


def utc_day(dt=None):
    dt = dt or datetime.now(timezone.utc)
    return dt.date().isoformat()

class InviteTrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites_cache = {}
        self.bot.loop.create_task(self.cache_invites())

    async def cache_invites(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                self.invites_cache[guild.id] = await guild.invites()
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if guild.id not in self.invites_cache:
            return

        old_invites = self.invites_cache[guild.id]
        try:
            new_invites = await guild.invites()
        except discord.Forbidden:
            return

        self.invites_cache[guild.id] = new_invites  # Обновляем кэш

        used_invite = None
        for old_inv in old_invites:
            for new_inv in new_invites:
                if old_inv.code == new_inv.code and new_inv.uses > old_inv.uses:
                    used_invite = new_inv
                    break
            if used_invite:
                break

        if used_invite and used_invite.inviter:
            invites_col.update_one(
                {"invited_id": member.id},
                {
                    "$set": {
                        "inviter_id": used_invite.inviter.id,
                        "invite_code": used_invite.code,
                        "joined_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def schedule_bump_reminder(self, channel: discord.TextChannel):
        """Отправляет напоминание через 2 часа (7200 секунд)."""
        await asyncio.sleep(7200)
        try:
            await channel.send(BUMP_REMINDER_MESSAGE)
        except discord.DiscordException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        if not message.author.bot:
            users_col.update_one(
                {"_id": message.author.id},
                {"$inc": {"messages_count": 1}},
                upsert=True
            )

            counting_channel_id = config.CONFIG.get("counting_channel_id")
            if counting_channel_id and message.channel.id == counting_channel_id:
                message_stats_col.update_one(
                    {"channel_id": counting_channel_id, "user_id": message.author.id, "day": utc_day()},
                    {"$inc": {"count": 1}},
                    upsert=True,
                )

        bump_channel_id = config.CONFIG.get("bump_channel_id")
        if bump_channel_id and message.channel.id == bump_channel_id:
            if message.author.id != config.DISBOARD_BOT_ID:
                return

            user = None
            if hasattr(message, "interaction_metadata") and message.interaction_metadata:
                user = message.interaction_metadata.user
            elif hasattr(message, "interaction") and message.interaction:
                user = message.interaction.user

            if not user or user.bot:
                return

            bump_success = False
            for embed in message.embeds:
                text_to_check = f"{embed.title or ''} {embed.description or ''}".lower()
                
                if "bump done" in text_to_check or "успешно" in text_to_check or "bumped" in text_to_check:
                    bump_success = True
                    break

            if bump_success:
                bump_stats_col.update_one(
                    {"channel_id": bump_channel_id, "user_id": user.id, "day": utc_day()},
                    {"$inc": {"count": 1}, "$set": {"last_command": "bump"}},
                    upsert=True,
                )
                
                # Запускаем фоновую задачу с задержкой 2 часа 5 минут
                asyncio.create_task(self.schedule_bump_reminder(message.channel))

    @commands.command(name="summaries", aliases=["sum"])
    @check_access_decorator("sum")
    async def summaries_cmd(self, ctx: commands.Context, mode: str = None):
        limit = 10 if mode and mode.lower() in ["ex", "extended"] else 3

        now = datetime.now(timezone.utc)
        d7 = (now - timedelta(days=7)).date().isoformat()
        d30 = (now - timedelta(days=30)).date().isoformat()

        def top_stats(collection, start_day, channel_id):
            if not channel_id:
                return []
            pipeline = []
            if start_day:
                pipeline.append({"$match": {"channel_id": channel_id, "day": {"$gte": start_day}}})
            else:
                pipeline.append({"$match": {"channel_id": channel_id}})
            pipeline.extend([
                {"$group": {"_id": "$user_id", "count": {"$sum": "$count"}}},
                {"$sort": {"count": -1}},
                {"$limit": limit},
            ])
            return [(doc["_id"], doc["count"]) for doc in collection.aggregate(pipeline)]

        def fmt(rows):
            lines = []
            for i in range(1, limit + 1):
                if i <= len(rows):
                    uid, count = rows[i - 1]
                    lines.append(f"`{i}.` <@{uid}> - **{count}**")
                else:
                    lines.append(f"`{i}.` —")
            return "\n".join(lines)

        embed_title = "<:leaderboard:1544301200894070844> Подсчет (Расширенный топ-10)" if limit == 10 else "<:leaderboard:1544301200894070844> Подсчет"
        embed = discord.Embed(title=embed_title, color=config.EMBED_COLOR)

        embed.add_field(name="🧮 Считалка: 7 дней", value=fmt(top_stats(message_stats_col, d7, config.CONFIG.get("counting_channel_id"))), inline=True)
        embed.add_field(name="<:bump:1522334649580392518> Bump: 7 дней", value=fmt(top_stats(bump_stats_col, d7, config.CONFIG.get("bump_channel_id"))), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="🧮 Считалка: 30 дней", value=fmt(top_stats(message_stats_col, d30, config.CONFIG.get("counting_channel_id"))), inline=True)
        embed.add_field(name="<:bump:1522334649580392518> Bump: 30 дней", value=fmt(top_stats(bump_stats_col, d30, config.CONFIG.get("bump_channel_id"))), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="🧮 Считалка: Все время", value=fmt(top_stats(message_stats_col, None, config.CONFIG.get("counting_channel_id"))), inline=True)
        embed.add_field(name="<:bump:1522334649580392518> Bump: Все время", value=fmt(top_stats(bump_stats_col, None, config.CONFIG.get("bump_channel_id"))), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        count_channel = config.CONFIG.get("counting_channel_id")
        bump_channel = config.CONFIG.get("bump_channel_id")
        embed.add_field(name="Канал для считалки", value=f"<#{count_channel}>" if count_channel else "Не установлен", inline=True)
        embed.add_field(name="Канал для бампа", value=f"<#{bump_channel}>" if bump_channel else "Не установлен", inline=True)

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="userinfo", aliases=["ui"])
    @check_access_decorator("userinfo")
    async def userinfo_cmd(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        
        user_doc = users_col.find_one({"_id": member.id}) or {}
        
        messages_count = user_doc.get("messages_count", 0)
        
        real_inv = user_doc.get("real_invites", 0)
        bonus_inv = user_doc.get("bonus_invites", 0)
        total_invites = real_inv + bonus_inv
        
        cash = user_doc.get("cash", 0)
        bank = user_doc.get("bank", 0)

        created_at_discord = discord.utils.format_dt(member.created_at, "R")
        created_at_full = discord.utils.format_dt(member.created_at, "F")
        
        joined_at_discord = discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "Неизвестно"
        joined_at_full = discord.utils.format_dt(member.joined_at, "F") if member.joined_at else "Неизвестно"

        roles = [role.mention for role in reversed(member.roles) if role.id != ctx.guild.default_role.id]
        roles_str = ", ".join(roles) if roles else "Нет ролей"
        if len(roles_str) > 1024:
            roles_str = "Слишком много ролей для отображения"

        embed = discord.Embed(
            title=f"<:info:1522329987514892398> Информация: {member.display_name}",
            color=config.EMBED_COLOR
        )
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        embed.add_field(
            name="Упоминание / Имя пользователя / ID",
            value=f"{member.mention} | `{member.name}` | `{member.id}`",
            inline=False
        )
        
        embed.add_field(
            name="Создание аккаунта",
            value=f"{created_at_discord} ({created_at_full})",
            inline=False
        )
        
        embed.add_field(
            name="Вход на сервер",
            value=f"{joined_at_discord} ({joined_at_full})",
            inline=False
        )

        embed.add_field(
            name=f"Роли [{len(roles)}]",
            value=f"{roles_str}",
            inline=False
        )

        embed.add_field(
            name="<:pin:1522341130019143880> Статистика и Экономика",
            value=(
                f"• Сообщений: **{messages_count:,}**\n"
                f"• Инвайтов: **{total_invites}**\n"
                f"• Наличные: **{cash:,}**\n"
                f"• Банк: **{bank:,}**"
            ),
            inline=False
        )

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="inviter")
    @check_access_decorator("inviter")
    async def inviter_cmd(self, ctx: commands.Context, target: discord.User = None):
        target = target or ctx.author
        doc = invites_col.find_one({"invited_id": target.id})
        
        if not doc or "inviter_id" not in doc:
            return await ctx.send(
                embed=make_error_embed("Информация", f"Не удалось определить, кто пригласил пользователя <@!{target.id}> (возможно, он зашел по ссылке-приглашению ванна/другому способу без трекинга).")
            )

        inviter_id = doc["inviter_id"]
        embed = discord.Embed(
            title="<:info:1522329987514892398> Информация об инвайте",
            color=config.EMBED_COLOR
        )
        embed.add_field(name="Пользователь", value=f"<@!{target.id}> (`{target.id}`)", inline=False)
        embed.add_field(name="Кто пригласил", value=f"<@!{inviter_id}> (`{inviter_id}`)", inline=False)
        if "invite_code" in doc:
            embed.add_field(name="Код приглашения", value=f"`{doc['invite_code']}`", inline=True)
        
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="loginvite")
    @check_access_decorator("loginvite")
    async def loginvite_cmd(
        self, 
        ctx: commands.Context, 
        inviter_id: int, 
        invited_id: int, 
        prize: str, 
        amount: int
    ):
        if prize not in config.VALID_PRIZES:
            cats = ", ".join(f"`{c}`" for c in config.VALID_PRIZES)
            return await ctx.send(embed=make_error_embed("Ошибка", f"Неверная категория приза. Допустимые: {cats}"))

        existing = invites_col.find_one({"invited_id": invited_id})
        if existing:
            return await ctx.send(embed=make_error_embed("Ошибка", f"За пользователя <@!{invited_id}> уже забирали награду."))

        log_id = get_next_sequence_value("invites_seq")
        now = datetime.now(timezone.utc)

        invites_col.insert_one({
            "_id": log_id,
            "inviter_id": inviter_id,
            "invited_id": invited_id,
            "prize": prize,
            "amount": amount,
            "staff_id": ctx.author.id,
            "created_at": now
        })

        embed = discord.Embed(
            title=f"<:logs:1522340749998428160> Инвайт No{log_id} — {ctx.author.name}",
            color=config.EMBED_COLOR
        )
        embed.add_field(name="Дата записи", value=discord.utils.format_dt(now, "f"), inline=False)
        embed.add_field(name="Пригласил", value=f"{inviter_id} (<@!{inviter_id}>)", inline=False)
        embed.add_field(name="Приглашённый", value=f"{invited_id} (<@!{invited_id}>)", inline=False)
        embed.add_field(name="Приз", value=prize, inline=False)
        embed.add_field(name="Количество", value=str(amount), inline=False)
        embed.add_field(name="Внёс в базу", value=ctx.author.mention, inline=False)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "loginvite", embed)

    @commands.command(name="validinvite")
    @check_access_decorator("validinvite")
    async def validinvite_cmd(self, ctx: commands.Context, invited_id: int):
        doc = invites_col.find_one({"invited_id": invited_id})
        if not doc:
            embed = discord.Embed(
                title="<:verify:1522329028420173976> Приз еще не получен",
                description=f"За пользователя <@!{invited_id}> (`{invited_id}`) никто еще не забирал награду.",
                color=discord.Color.green()
            )
            embed.set_footer(text=config.FOOTER_TEXT)
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="<:logs:1522340749998428160> Приз уже был получен",
            description=f"За пользователя <@!{invited_id}> (`{invited_id}`) **уже забирали награду**.",
            color=discord.Color.red()
        )
        embed.add_field(name="Пригласивший (Кто забрал приз)", value=f"<@!{doc['inviter_id']}> (`{doc['inviter_id']}`)", inline=False)
        embed.add_field(name="Полученный приз", value=f"{doc['prize']} ({doc['amount']} шт.)", inline=True)
        embed.add_field(name="Кто внес запись", value=f"<@!{doc['staff_id']}>", inline=True)
        embed.add_field(name="Дата записи", value=discord.utils.format_dt(doc['created_at'], "f"), inline=False)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="loggiveaway")
    @check_access_decorator("loggiveaway")
    async def loggiveaway_cmd(self, ctx: commands.Context, hoster_id: int, prize: str, amount: int):
        if prize not in config.VALID_PRIZES:
            cats = ", ".join(f"`{c}`" for c in config.VALID_PRIZES)
            return await ctx.send(embed=make_error_embed("Ошибка", f"Неверная категория приза. Допустимые: {cats}"))

        log_id = get_next_sequence_value("giveaways_seq")
        now = datetime.now(timezone.utc)

        giveaways_col.insert_one({
            "_id": log_id,
            "hoster_id": hoster_id,
            "prize": prize,
            "amount": amount,
            "staff_id": ctx.author.id,
            "created_at": now
        })

        embed = discord.Embed(
            title=f"<:giveaway:1522331215976206446> Розыгрыш No{log_id}: {ctx.author.name}",
            color=config.EMBED_COLOR
        )
        embed.add_field(name="Дата записи", value=discord.utils.format_dt(now, "f"), inline=False)
        embed.add_field(name="Хостер розыгрыша", value=f"{hoster_id} (<@!{hoster_id}>)", inline=False)
        embed.add_field(name="Тип приза", value=prize, inline=False)
        embed.add_field(name="Количество", value=str(amount), inline=False)
        embed.add_field(name="Внёс в базу", value=ctx.author.mention, inline=False)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "loggiveaway", embed)

    @commands.command(name="giveawaylogs")
    @check_access_decorator("giveawaylogs")
    async def giveawaylogs_id(self, ctx: commands.Context, user_id: int):
        docs = list(giveaways_col.find({"hoster_id": user_id}).sort("created_at", 1))
        if not docs:
            return await ctx.send(embed=make_error_embed("Логи", "У этого пользователя нет проведенных розыгрышей."))

        embed = discord.Embed(title=f"<:giveaway:1522331215976206446> Розыгрыши: хостер", color=config.EMBED_COLOR)
        embed.description = f"`{user_id}`\n" + "----------------------------------------"
        for doc in docs:
            dt_str = discord.utils.format_dt(doc['created_at'], "f")
            embed.add_field(
                name=f"Розыгрыш No{doc['_id']} (Лог No{doc['_id']})",
                value=f"**Хостер:** <@!{doc['hoster_id']}>\n**Приз:** {doc['prize']}\n**Количество:** {doc['amount']}\n**Внёс в базу:** <@!{doc['staff_id']}>\n{dt_str}",
                inline=False
            )
        embed.set_footer(text=f"Страница 1/1 ({len(docs)} логов) • {config.FOOTER_TEXT}")
        await ctx.send(embed=embed)

    @commands.command(name="invitelogs")
    @check_access_decorator("invitelogs")
    async def invitelogs_id(self, ctx: commands.Context, user_id: int):
        docs = list(invites_col.find({"inviter_id": user_id}).sort("created_at", 1))
        if not docs:
            return await ctx.send(embed=make_error_embed("Логи", "У этого пользователя нет записанных приглашений."))

        embed = discord.Embed(title=f"<:logs:1522340749998428160> Приглашения", color=config.EMBED_COLOR)
        embed.description = f"`{user_id}`\n" + "----------------------------------------"
        for idx, doc in enumerate(docs, 1):
            dt_str = discord.utils.format_dt(doc['created_at'], "f")
            embed.add_field(
                name=f"Приглашение No{idx} (Лог No{doc['_id']})",
                value=f"**Пригласил:** <@!{doc['inviter_id']}>\n**Приглашённый:** <@!{doc['invited_id']}>\n**Приз:** {doc['prize']}\n**Количество:** {doc['amount']}\n{dt_str}",
                inline=False
            )
        embed.set_footer(text=f"Страница 1/1 ({len(docs)} логов) • {config.FOOTER_TEXT}")
        await ctx.send(embed=embed)

    @commands.command(name="deletegiveaway")
    @check_access_decorator("deletegiveaway")
    async def deletegiveaway_cmd(self, ctx: commands.Context, log_id: int):
        doc = giveaways_col.find_one_and_delete({"_id": log_id})
        if not doc:
            return await ctx.send(embed=make_error_embed("Ошибка", f"Розыгрыш с ID No{log_id} не найден в базе."))

        embed = discord.Embed(
            title="Удаление розыгрыша",
            description=f"Лог розыгрыша **No{log_id}** успешно удалён из базы данных.",
            color=discord.Color.red()
        )
        embed.add_field(name="Хостер", value=f"<@!{doc['hoster_id']}> (`{doc['hoster_id']}`)", inline=False)
        embed.add_field(name="Приз", value=f"{doc['prize']} ({doc['amount']} шт.)", inline=True)
        embed.add_field(name="Удалил", value=ctx.author.mention, inline=True)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="deleteinvite")
    @check_access_decorator("deleteinvite")
    async def deleteinvite_cmd(self, ctx: commands.Context, log_id: int):
        doc = invites_col.find_one_and_delete({"_id": log_id})
        if not doc:
            return await ctx.send(embed=make_error_embed("Ошибка", f"Инвайт с ID No{log_id} не найден в базе."))

        embed = discord.Embed(
            title="Удаление инвайта",
            description=f"Лог инвайта **No{log_id}** успешно удалён из базы данных.",
            color=discord.Color.red()
        )
        embed.add_field(name="Пригласивший", value=f"<@!{doc['inviter_id']}>", inline=False)
        embed.add_field(name="Приглашённый", value=f"<@!{doc['invited_id']}>", inline=False)
        embed.add_field(name="Приз", value=f"{doc['prize']} ({doc['amount']} шт.)", inline=True)
        embed.add_field(name="Удалил", value=ctx.author.mention, inline=True)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    

    # ==========================================
    # ГРУППА КОМАНД LEADERBOARD / LB
    # ==========================================
    @commands.group(name="leaderboard", aliases=["lb"], invoke_without_command=True)
    async def leaderboard_group(self, ctx: commands.Context, category: str = None):
        if category in ["messages", "m", "msgs", "сообщения"]:
            return await ctx.invoke(self.lb_messages)
        elif category in ["invites", "i", "приглашения"]:
            return await ctx.invoke(self.lb_invites)
        elif category in ["tickets", "t", "тикеты"]:
            return await ctx.invoke(self.lb_tickets)
        elif category in ["economy", "ec", "bal", "coins", "экономика"]:
            return await ctx.invoke(self.lb_economy)

        embed = discord.Embed(
            title="<:trophy:1522340749998428160> Меню таблиц лидеров",
            description=(
                "Укажите категорию лидерборда:\n\n"
                "• `.lb messages` - Топ 5 по сообщениям\n"
                "• `.lb invites` - Топ 5 по приглашениям\n"
                "• `.lb tickets` - Лидерборд тикетов, транскриптов и удалений\n"
                "• `.lb economy` - Топ 5 самых богатых участников"
            ),
            color=config.EMBED_COLOR,
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @leaderboard_group.command(name="messages", aliases=["m"])
    @check_access_decorator("leaderboard")
    async def lb_messages(self, ctx: commands.Context):
        pipeline = [
            {"$match": {"messages_count": {"$gt": 0}}},
            {"$sort": {"messages_count": -1}},
            {"$limit": 5},
            {"$project": {"_id": "$_id", "count": "$messages_count"}}
        ]
        top_data = list(users_col.aggregate(pipeline))

        embed = discord.Embed(
            title="<:leaderboard:1544301200894070844> Топ 5 по сообщениям",
            color=config.EMBED_COLOR
        )

        lines = []
        for i in range(1, 6):
            if i <= len(top_data):
                doc = top_data[i - 1]
                lines.append(f"`{i}.` <@{doc['_id']}> - **{doc['count']}** сообщ.")
            else:
                lines.append(f"`{i}.` -")

        embed.description = "\n".join(lines)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @leaderboard_group.command(name="invites", aliases=["i"])
    @check_access_decorator("leaderboard")
    async def lb_invites(self, ctx: commands.Context):
        query = {
            "$or": [
                {"real_invites": {"$gt": 0}},
                {"bonus_invites": {"$gt": 0}}
            ]
        }
        users = list(users_col.find(query))

        leaderboard_data = []
        for user in users:
            real = user.get("real_invites", 0)
            bonus = user.get("bonus_invites", 0)
            total = real + bonus
            if total > 0:
                leaderboard_data.append({"_id": user["_id"], "count": total})

        leaderboard_data.sort(key=lambda x: x["count"], reverse=True)
        top_data = leaderboard_data[:5]

        embed = discord.Embed(
            title="<:leaderboard:1544301200894070844> Топ 5 по приглашениям",
            color=config.EMBED_COLOR
        )

        lines = []
        for i in range(1, 6):
            if i <= len(top_data):
                doc = top_data[i - 1]
                lines.append(f"`{i}.` <@{doc['_id']}> - **{doc['count']}** приглашений")
            else:
                lines.append(f"`{i}.` —")

        embed.description = "\n".join(lines)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @leaderboard_group.command(name="tickets", aliases=["t"])
    @check_access_decorator("ticketstats")
    async def lb_tickets(self, ctx: commands.Context):
        now = datetime.now(timezone.utc)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        def get_top(collection, field: str, min_date=None, exclude_zero=False):
            match_stage = {}
            if min_date:
                match_stage["created_at"] = {"$gte": min_date}
            if exclude_zero:
                match_stage[field] = {"$ne": 0}

            pipeline = []
            if match_stage:
                pipeline.append({"$match": match_stage})

            pipeline.extend([
                {"$group": {"_id": f"${field}", "cnt": {"$sum": 1}}},
                {"$sort": {"cnt": -1}},
                {"$limit": 3}
            ])
            return [(doc["_id"], doc["cnt"]) for doc in collection.aggregate(pipeline)]

        def format_top_with_dashes(top_list, unit_label="тикетов"):
            lines = []
            for i in range(1, 4):
                if i <= len(top_list):
                    u_id, count = top_list[i - 1]
                    lines.append(f"`{i}.` <@{u_id}> - **{count}** {unit_label}")
                else:
                    lines.append(f"`{i}.` —")
            return "\n".join(lines)

        embed = discord.Embed(title="<:leaderboard:1544301200894070844> Лидерборд тикетов и транскриптов", color=config.EMBED_COLOR)

        embed.add_field(name="<:ticket:1522343287816716379> Тикетов (7 дн.)", value=format_top_with_dashes(get_top(tickets_col, "staff_id", d7)), inline=True)
        embed.add_field(name="<:ticket:1522343287816716379> Тикетов (30 дн.)", value=format_top_with_dashes(get_top(tickets_col, "staff_id", d30)), inline=True)
        embed.add_field(name="<:ticket:1522343287816716379> Тикетов (Все время)", value=format_top_with_dashes(get_top(tickets_col, "staff_id")), inline=True)

        embed.add_field(name="<:logs:1522340749998428160> Транскриптов (7 дн.)", value=format_top_with_dashes(get_top(tickets_col, "author_id", d7, True), "транскриптов"), inline=True)
        embed.add_field(name="<:logs:1522340749998428160> Транскриптов (30 дн.)", value=format_top_with_dashes(get_top(tickets_col, "author_id", d30, True), "транскриптов"), inline=True)
        embed.add_field(name="<:logs:1522340749998428160> Транскриптов (Все время)", value=format_top_with_dashes(get_top(tickets_col, "author_id", exclude_zero=True), "транскриптов"), inline=True)

        embed.add_field(name="<:staff:1522338131339251823> Удалено (7 дн.)", value=format_top_with_dashes(get_top(deleted_tickets_col, "staff_id", d7), "удалений"), inline=True)
        embed.add_field(name="<:staff:1522338131339251823> Удалено (30 дн.)", value=format_top_with_dashes(get_top(deleted_tickets_col, "staff_id", d30), "удалений"), inline=True)
        embed.add_field(name="<:staff:1522338131339251823> Удалено (Все время)", value=format_top_with_dashes(get_top(deleted_tickets_col, "staff_id"), "удалений"), inline=True)

        embed.set_footer(text=f"Сегодня в {now.strftime('%H:%M')} • {config.FOOTER_TEXT}")
        await ctx.send(embed=embed)

    @leaderboard_group.command(name="economy", aliases=["e"])
    @check_access_decorator("leaderboard")
    async def lb_economy(self, ctx: commands.Context):
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
            {"$sort": {"total": -1}},
            {"$limit": 10}
        ]
        top_data = list(users_col.aggregate(pipeline))

        embed = discord.Embed(
            title="<:leaderboard:1544301200894070844> Топ 10 по балансу",
            color=config.EMBED_COLOR
        )

        lines = []
        for i in range(1, 11):
            if i <= len(top_data):
                doc = top_data[i - 1]
                lines.append(f"`{i}.` <@{doc['_id']}> - **{doc['total']:,}** коинов")
            else:
                lines.append(f"`{i}.` -")

        embed.description = "\n".join(lines)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @leaderboard_group.command(name="streak", aliases=["st", " стрики"])
    @check_access_decorator("leaderboard")
    async def lb_streak(self, ctx: commands.Context):
        pipeline = [
            {"$match": {"streak.current": {"$gt": 0}}},
            {"$sort": {"streak.current": -1}},
            {"$limit": 5},
            {"$project": {"_id": "$_id", "current": "$streak.current"}}
        ]
        top_data = list(users_col.aggregate(pipeline))

        embed = discord.Embed(
            title="<:leaderboard:1544301200894070844> Топ 5 по стрику активности",
            color=config.EMBED_COLOR
        )

        lines = []
        for i in range(1, 6):
            if i <= len(top_data):
                doc = top_data[i - 1]
                lines.append(f"`{i}.` <@{doc['_id']}> - **{doc['current']}** дн.")
            else:
                lines.append(f"`{i}.` —")

        embed.description = "\n".join(lines)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))