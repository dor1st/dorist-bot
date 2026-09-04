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
)
from utils import check_access_decorator, make_error_embed, make_status_embed

BUMP_REMINDER_MESSAGE = "**<a:gifclock:1544347190984441858> <@&1501943871960125461> Пришло время бампа! (/bump)**"


def utc_day(dt=None):
    dt = dt or datetime.now(timezone.utc)
    return dt.date().isoformat()

def is_allowed_channel():
    async def predicate(ctx: commands.Context) -> bool:
        allowed = getattr(config, "ALLOWED_CHANNELS", [])
        if not allowed or ctx.channel.id in allowed:
            return True
        await ctx.send(
            embed=make_error_embed(
                "Ошибка доступа",
                "Эта команда недоступна в данном канале.",
            )
        )
        return False
    return commands.check(predicate)

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def schedule_bump_reminder(self, channel: discord.TextChannel):
        """Отправляет напоминание через 2 часа и 5 минут (7500 секунд)."""
        await asyncio.sleep(7500)
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
    @is_allowed_channel()
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
                    lines.append(f"`{i}.` <@{uid}> — **{count}**")
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

    # ==========================================
    # ГРУППА КОМАНД LEADERBOARD / LB
    # ==========================================
    @commands.group(name="leaderboard", aliases=["lb"], invoke_without_command=True)
    @is_allowed_channel()
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
                "• `.lb messages` — Топ 5 по сообщениям\n"
                "• `.lb invites` — Топ 5 по приглашениям\n"
                "• `.lb tickets` — Лидерборд тикетов, транскриптов и удалений\n"
                "• `.lb economy` — Топ 5 самых богатых участников"
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
                lines.append(f"`{i}.` <@{doc['_id']}> — **{doc['count']}** сообщ.")
            else:
                lines.append(f"`{i}.` —")

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
                lines.append(f"`{i}.` <@{doc['_id']}> — **{doc['count']}** приглашений")
            else:
                lines.append(f"`{i}.` —")

        embed.description = "\n".join(lines)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @leaderboard_group.command(name="tickets", aliases=["t"])
    @check_access_decorator("поддержка")
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
                    lines.append(f"`{i}.` <@{u_id}> — **{count}** {unit_label}")
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

    @leaderboard_group.command(name="economy", aliases=["ec", "bal", "coins"])
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
            {"$limit": 5}
        ]
        top_data = list(users_col.aggregate(pipeline))

        embed = discord.Embed(
            title="<:leaderboard:1544301200894070844> Топ 5 по балансу",
            color=config.EMBED_COLOR
        )

        lines = []
        for i in range(1, 6):
            if i <= len(top_data):
                doc = top_data[i - 1]
                lines.append(f"`{i}.` <@{doc['_id']}> — **{doc['total']:,}** коинов")
            else:
                lines.append(f"`{i}.` —")

        embed.description = "\n".join(lines)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StatsCog(bot))