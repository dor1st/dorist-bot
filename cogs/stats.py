from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

import config
from database import message_stats_col, bump_stats_col, tickets_col, deleted_tickets_col
from utils import check_access_decorator


def utc_day(dt=None):
    dt = dt or datetime.now(timezone.utc)
    return dt.date().isoformat()


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        channel_id = config.CONFIG.get("counting_channel_id")
        if not channel_id or message.channel.id != channel_id or message.author.bot:
            return
        message_stats_col.update_one(
            {"channel_id": channel_id, "user_id": message.author.id, "day": utc_day()},
            {"$inc": {"count": 1}},
            upsert=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        print(f"[ANY MSG] channel={message.channel.id} author={message.author.id} ({message.author.name})")

        counting_channel_id = config.CONFIG.get("counting_channel_id")
        if counting_channel_id and message.channel.id == counting_channel_id and not message.author.bot:
            message_stats_col.update_one(
                {"channel_id": counting_channel_id, "user_id": message.author.id, "day": utc_day()},
                {"$inc": {"count": 1}},
                upsert=True,
            )

        bump_channel_id = config.CONFIG.get("bump_channel_id")
        if bump_channel_id and message.channel.id == bump_channel_id:
            print("=== DEBUG BUMP MESSAGE ===")
            print("author:", message.author.id, message.author.name)
            print("interaction_metadata:", getattr(message, "interaction_metadata", None))
            print("interaction:", getattr(message, "interaction", None))
            for embed in message.embeds:
                print("embed title:", embed.title)
                print("embed description:", embed.description)
            print("===========================")

        if bump_channel_id and message.channel.id == bump_channel_id:
            if message.author.id != config.DISBOARD_BOT_ID:
                return

            interaction_info = getattr(message, "interaction_metadata", None) or getattr(message, "interaction", None)
            if interaction_info:
                command_name = getattr(interaction_info, "name", "") or ""
                user = getattr(interaction_info, "user", None)

                if user and not user.bot and "bump" in command_name.lower():
                    bump_success = any(
                        "bump done" in (embed.description or "").lower()
                        or "bump done" in (embed.title or "").lower()
                        for embed in message.embeds
                    )
                    if bump_success:
                        bump_stats_col.update_one(
                            {"channel_id": bump_channel_id, "user_id": user.id, "day": utc_day()},
                            {"$inc": {"count": 1}, "$set": {"last_command": command_name}},
                            upsert=True,
                        )

    @commands.command(name="sumarries", aliases=["sum"])
    @check_access_decorator("sum")
    async def summaries_cmd(self, ctx: commands.Context):
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
                {"$limit": 3},   # было 10
            ])
            return [(doc["_id"], doc["count"]) for doc in collection.aggregate(pipeline)]

        def fmt(rows):
            if not rows:
                return "— *Нет данных*"
            return "\n".join(f"`{i}.` <@{uid}> — **{count}**" for i, (uid, count) in enumerate(rows, 1))

        embed = discord.Embed(title=f"<:info:1522329987514892398> Подсчет", color=config.EMBED_COLOR)

        embed.add_field(name="🧮 Сообщения — 7 дней", value=fmt(top_stats(message_stats_col, d7, config.CONFIG.get("counting_channel_id"))), inline=True)
        embed.add_field(name="<:bump:1522334649580392518> Bump — 7 дней", value=fmt(top_stats(bump_stats_col, d7, config.CONFIG.get("bump_channel_id"))), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="🧮 Сообщения — 30 дней", value=fmt(top_stats(message_stats_col, d30, config.CONFIG.get("counting_channel_id"))), inline=True)
        embed.add_field(name="<:bump:1522334649580392518> Bump — 30 дней", value=fmt(top_stats(bump_stats_col, d30, config.CONFIG.get("bump_channel_id"))), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="🧮 Сообщения — Все время", value=fmt(top_stats(message_stats_col, None, config.CONFIG.get("counting_channel_id"))), inline=True)
        embed.add_field(name="<:bump:1522334649580392518> Bump — Все время", value=fmt(top_stats(bump_stats_col, None, config.CONFIG.get("bump_channel_id"))), inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        count_channel = config.CONFIG.get("counting_channel_id")
        bump_channel = config.CONFIG.get("bump_channel_id")
        embed.add_field(name="Канал для считалки", value=f"<#{count_channel}>" if count_channel else "Не установлен", inline=True)
        embed.add_field(name="Канал для бампа", value=f"<#{bump_channel}>" if bump_channel else "Не установлен", inline=True)

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb"])
    @check_access_decorator("leaderboard")
    async def leaderboard_cmd(self, ctx: commands.Context):
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

        embed = discord.Embed(title="<:sparkles:1522342290494849034> Лидерборд тикетов и транскриптов", color=config.EMBED_COLOR)

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


async def setup(bot):
    await bot.add_cog(StatsCog(bot))