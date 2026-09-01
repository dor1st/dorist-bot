import math
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

import config
from database import tickets_col, deleted_tickets_col, get_next_sequence_value
from utils import check_access_decorator, make_error_embed, make_status_embed, log_action, build_command_help_embed

LOGS_PER_PAGE = config.LOGS_PER_PAGE if hasattr(config, "LOGS_PER_PAGE") else 3


class TicketLogsView(discord.ui.View):
    """Пагинация для обычных логов тикетов."""

    def __init__(self, target: discord.User, logs: list, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.target = target
        self.logs = logs
        self.current_page = 0
        self.total_pages = math.ceil(len(logs) / LOGS_PER_PAGE)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def build_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"<:ticket:1522343287816716379> Тикеты — {self.target.name}",
            color=config.EMBED_COLOR,
        )

        start_idx = self.current_page * LOGS_PER_PAGE
        end_idx = start_idx + LOGS_PER_PAGE
        page_logs = self.logs[start_idx:end_idx]

        description_lines = [
            f"`{self.target.id}`",
            "--------------------------------------------------\n",
        ]

        for index, doc in enumerate(page_logs, start=start_idx + 1):
            created_dt = doc.get("created_at")
            if isinstance(created_dt, datetime):
                timestamp = int(created_dt.timestamp())
                time_str = f"<t:{timestamp}:f>"
            else:
                time_str = "—"

            transcript_url = doc.get("transcript_url", "—")

            description_lines.append(
                f"**Тикет №{index}**\n"
                f"**Модератор:** {self.target.name} ({self.target.mention})\n"
                f"**Категория:** {doc.get('category', 'Не указана')}\n"
                f"**Транскрипт:** {transcript_url}\n"
                f"{time_str}\n"
            )

        embed.description = "\n".join(description_lines)
        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.logs)} логов) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(emoji="<:darkleft:1543989641751957565>", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )

    @discord.ui.button(emoji="<:darkright:1543990036129783948>", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )


class DeletedTicketLogsView(discord.ui.View):
    """Пагинация для логов удаленных тикетов."""

    def __init__(self, target: discord.User, logs: list, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.target = target
        self.logs = logs
        self.current_page = 0
        self.total_pages = math.ceil(len(logs) / LOGS_PER_PAGE)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def build_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"<:staff:1522338131339251823> Удаленные тикеты — {self.target.name}",
            color=config.EMBED_COLOR,
        )

        start_idx = self.current_page * LOGS_PER_PAGE
        end_idx = start_idx + LOGS_PER_PAGE
        page_logs = self.logs[start_idx:end_idx]

        description_lines = [
            f"`{self.target.id}`",
            "--------------------------------------------------\n",
        ]

        for index, doc in enumerate(page_logs, start=start_idx + 1):
            created_dt = doc.get("created_at")
            if isinstance(created_dt, datetime):
                timestamp = int(created_dt.timestamp())
                time_str = f"<t:{timestamp}:f>"
            else:
                time_str = "—"

            original_id = doc.get("original_log_id", "—")
            transcript_url = doc.get("transcript_url", "—")

            description_lines.append(
                f"**Удаление №{index}** (Лог №{original_id})\n"
                f"**Модератор:** {self.target.name} ({self.target.mention})\n"
                f"**Транскрипт:** {transcript_url}\n"
                f"**Дата удаления:** {time_str}\n"
            )

        embed.description = "\n".join(description_lines)
        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.logs)} удалений) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(emoji="<:darkleft:1543989641751957565>", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )

    @discord.ui.button(emoji="<:darkright:1543990036129783948>", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )


class TicketsCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ticketleaderboard", aliases=["tlb"])
    @check_access_decorator("ticketleaderboard")
    async def ticketleaderboard_cmd(self, ctx: commands.Context):
        pipeline = [
            {"$group": {"_id": "$staff_id", "tickets_count": {"$sum": 1}}},
            {"$sort": {"tickets_count": -1}},
            {"$limit": 10}
        ]
        top_staff = list(tickets_col.aggregate(pipeline))

        if not top_staff:
            embed = make_status_embed(
                "Лидерборд тикетов",
                "В базе данных пока нет записанных тикетов.",
                "info",
            )
            return await ctx.send(embed=embed)

        lines = []
        for index, item in enumerate(top_staff, start=1):
            staff_id = item["_id"]
            tickets_cnt = item["tickets_count"]
            deleted_cnt = deleted_tickets_col.count_documents({"staff_id": staff_id})

            lines.append(
                f"**{index}.** <@{staff_id}>\n"
                f"└ Обработано тикетов: **{tickets_cnt}** | Удалений: **{deleted_cnt}**"
            )

        embed = discord.Embed(
            title="<:ticket:1522343287816716379> Лидерборд — Тикеты",
            description="\n\n".join(lines),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="addticket", aliases=["t"])
    @check_access_decorator("addticket")
    async def addticket_cmd(
        self,
        ctx: commands.Context,
        staff: discord.User = None,
        transcript_url: str = None,
        *,
        category: str = None,
    ):
        if staff is None or transcript_url is None or category is None:
            return await ctx.send(embed=build_command_help_embed("addticket"))

        if staff.id == ctx.author.id:
            embed = make_error_embed(
                "Ошибка аргумента",
                "Вы **не можете** указать свой собственный ID / аккаунт!"
            )
            return await ctx.send(embed=embed)

        if not transcript_url.startswith("https://discord.com/"):
            embed = make_error_embed(
                "Неверная ссылка",
                "Ссылка на транскрипт должна начинаться с `https://discord.com/`!"
            )
            return await ctx.send(embed=embed)

        if tickets_col.find_one({"transcript_url": transcript_url}):
            embed = make_error_embed(
                "Дубликат транскрипта",
                "Этот транскрипт уже был внесен в базу данных ранее!"
            )
            return await ctx.send(embed=embed)

        if category not in config.VALID_CATEGORIES:
            cats = ", ".join([f"`{c}`" for c in config.VALID_CATEGORIES])
            embed = make_error_embed(
                "Неверная категория",
                f"Вы указали недействительную категорию: `{category}`.\n\n**Допустимые категории:**\n{cats}"
            )
            return await ctx.send(embed=embed)

        log_id = get_next_sequence_value("ticket_id")
        now = datetime.now(timezone.utc)

        doc = {
            "_id": log_id,
            "staff_id": staff.id,
            "author_id": ctx.author.id,
            "category": category,
            "transcript_url": transcript_url,
            "created_at": now,
        }
        tickets_col.insert_one(doc)

        embed = discord.Embed(
            title=f"<:ticket:1522343287816716379> Тикет №{log_id} — {staff.name}",
            color=config.EMBED_COLOR,
        )
        embed.add_field(name="Дата записи", value=f"<t:{int(now.timestamp())}:f>", inline=False)
        embed.add_field(name="Модератор", value=f"{staff.id} ({staff.mention})", inline=False)
        embed.add_field(name="Категория", value=category, inline=False)
        embed.add_field(name="Транскрипт", value=f"[Перейти к транскрипту]({transcript_url})", inline=False)
        embed.add_field(name="Внёс в базу", value=ctx.author.mention, inline=False)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "addticket", embed)


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))