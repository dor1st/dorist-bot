from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

import config
from database import tickets_col, deleted_tickets_col, get_next_sequence_value
from utils import check_access_decorator, make_error_embed, make_status_embed, log_action


class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="addticket", aliases=["t"])
    @check_access_decorator("addticket")
    async def addticket_cmd(self, ctx: commands.Context, staff: discord.User = None, transcript_url: str = None, *, category: str = None):
        if not staff or not transcript_url or not category:
            embed = make_error_embed("Недостаточно аргументов", config.COMMAND_USAGE_HELP["addticket"])
            return await ctx.send(embed=embed)

        if category not in config.VALID_CATEGORIES:
            cats = ", ".join(f"`{c}`" for c in config.VALID_CATEGORIES)
            embed = make_error_embed("Неверная категория", f"Указана недопустимая категория!\nРазрешенные: {cats}")
            return await ctx.send(embed=embed)

        log_id = get_next_sequence_value("ticket_id")
        now = datetime.now(timezone.utc)

        ticket_doc = {
            "_id": log_id,
            "staff_id": staff.id,
            "author_id": ctx.author.id,
            "transcript_url": transcript_url,
            "category": category,
            "created_at": now
        }
        tickets_col.insert_one(ticket_doc)

        month_ago = now - timedelta(days=30)
        month_count = tickets_col.count_documents({"staff_id": staff.id, "created_at": {"$gte": month_ago}})

        embed = discord.Embed(title=f"📋 Лог №{log_id} — {staff.name}", color=config.EMBED_COLOR)
        embed.add_field(name="Дата транскрипта", value=f"<t:{int(now.timestamp())}:f>", inline=False)
        embed.add_field(name="Ссылка на транскрипт", value=transcript_url, inline=False)
        embed.add_field(name="Кто вёл тикет", value=f"{staff.id} ({staff.mention})", inline=False)
        embed.add_field(name="Внёс в базу", value=ctx.author.mention, inline=False)
        embed.add_field(name="Тикетов за последний месяц", value=str(month_count), inline=False)
        embed.add_field(name="Категория", value=category, inline=False)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "addticket", embed)

    @commands.command(name="deleteticket")
    @check_access_decorator("deleteticket")
    async def deleteticket_cmd(self, ctx: commands.Context, log_id: int = None, transcript_url: str = None):
        if log_id is None or transcript_url is None:
            embed = make_error_embed("Недостаточно аргументов", config.COMMAND_USAGE_HELP["deleteticket"])
            return await ctx.send(embed=embed)

        now = datetime.now(timezone.utc)
        deleted_id = get_next_sequence_value("deleted_ticket_id")

        deleted_doc = {
            "_id": deleted_id,
            "original_log_id": log_id,
            "staff_id": ctx.author.id,
            "transcript_url": transcript_url,
            "created_at": now
        }
        deleted_tickets_col.insert_one(deleted_doc)

        embed = make_status_embed(
            "Тикет удален",
            f"Удаление тикета по логу **№{log_id}** успешно зафиксировано!\nМодератору {ctx.author.mention} добавлено **+1** удаление тикета в казну.",
            "delete"
        )
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "deleteticket", embed)

    @commands.command(name="ticketlogs", aliases=["tl"])
    @check_access_decorator("ticketlogs")
    async def ticketlogs_cmd(self, ctx: commands.Context, target: discord.User = None):
        target = target or ctx.author
        logs = list(tickets_col.find({"staff_id": target.id}).sort("_id", 1))
        if not logs:
            embed = make_status_embed("Тикеты", f"У модератора {target.mention} нет логов тикетов.", "info")
            return await ctx.send(embed=embed)

        lines = [f"**Лог №{doc['_id']}** | {doc['category']} | [Ссылка]({doc['transcript_url']})" for doc in logs[:5]]

        embed = discord.Embed(title=f"📜 Логи тикетов — {target.name}", description="\n".join(lines), color=config.EMBED_COLOR)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="ticketstats", aliases=["ts"])
    @check_access_decorator("ticketstats")
    async def ticketstats_cmd(self, ctx: commands.Context, target: discord.User = None):
        target = target or ctx.author
        t_count = tickets_col.count_documents({"staff_id": target.id})
        tr_count = tickets_col.count_documents({"author_id": target.id})
        del_count = deleted_tickets_col.count_documents({"staff_id": target.id})

        embed = discord.Embed(title=f"📊 Статистика — {target.name}", color=config.EMBED_COLOR)
        embed.add_field(name="🎟️ Обработано тикетов", value=str(t_count), inline=True)
        embed.add_field(name="🧾 Занесено транскриптов", value=str(tr_count), inline=True)
        embed.add_field(name="🗑️ Удалено тикетов", value=str(del_count), inline=True)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))