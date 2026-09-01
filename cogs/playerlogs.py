import math
from datetime import datetime, timezone
import discord
from discord.ext import commands

import config
from database import giveaways_col, invites_col, get_next_sequence_value
from utils import (
    check_access_decorator,
    make_error_embed,
    make_status_embed,
    log_action,
    build_command_help_embed,
)

LOGS_PER_PAGE = config.LOGS_PER_PAGE if hasattr(config, "LOGS_PER_PAGE") else 3


# ==========================================
# VIEWS (Пагинаторы)
# ==========================================


class GiveawayLogsView(discord.ui.View):
    """Пагинация для логов розыгрышей."""

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
            title=f"<:sparkles:1522342290494849034> Розыгрыши — {self.target.name}",
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

            description_lines.append(
                f"**Розыгрыш №{index}** (Лог №{doc.get('_id')})\n"
                f"**Хостер:** {self.target.name} ({self.target.mention})\n"
                f"**Приз:** {doc.get('prize_type', '—')}\n"
                f"**Количество:** {doc.get('amount', 1)}\n"
                f"**Внёс в базу:** <@{doc.get('author_id')}>\n"
                f"{time_str}\n"
            )

        embed.description = "\n".join(description_lines)
        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.logs)} логов) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(
        emoji="<:darkleft:1543989641751957565>", style=discord.ButtonStyle.secondary
    )
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )

    @discord.ui.button(
        emoji="<:darkright:1543990036129783948>", style=discord.ButtonStyle.secondary
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )


class InviteLogsView(discord.ui.View):
    """Пагинация для логов приглашений."""

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
            title=f"<:logs:1522340749998428160> Приглашения — {self.target.name}",
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

            description_lines.append(
                f"**Приглашение №{index}** (Лог №{doc.get('_id')})\n"
                f"**Пригласил:** {self.target.name} ({self.target.mention})\n"
                f"**Приглашённый:** <@{doc.get('invited_id')}>\n"
                f"**Приз:** {doc.get('prize', '—')}\n"
                f"**Количество:** {doc.get('amount', 1)}\n"
                f"{time_str}\n"
            )

        embed.description = "\n".join(description_lines)
        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.logs)} логов) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(
        emoji="<:darkleft:1543989641751957565>", style=discord.ButtonStyle.secondary
    )
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )

    @discord.ui.button(
        emoji="<:darkright:1543990036129783948>", style=discord.ButtonStyle.secondary
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(
                embed=self.build_page_embed(), view=self
            )


# ==========================================
# COG CLASS
# ==========================================


class PlayerLogsCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # 1. Запись розыгрыша
    @commands.command(name="loggiveaway", aliases=["lg"])
    @check_access_decorator("loggiveaway")
    async def loggiveaway_cmd(
        self,
        ctx: commands.Context,
        host: discord.User = None,
        prize_type: str = None,
        amount: int = 1,
    ):
        if host is None or prize_type is None:
            return await ctx.send(embed=build_command_help_embed("loggiveaway"))

        log_id = get_next_sequence_value("giveaway_id")
        now = datetime.now(timezone.utc)

        doc = {
            "_id": log_id,
            "host_id": host.id,
            "author_id": ctx.author.id,
            "prize_type": prize_type,
            "amount": amount,
            "created_at": now,
        }
        giveaways_col.insert_one(doc)

        embed = discord.Embed(
            title=f"<:sparkles:1522342290494849034> Розыгрыш №{log_id} — {host.name}",
            color=config.EMBED_COLOR,
        )
        embed.add_field(
            name="Дата записи",
            value=f"<t:{int(now.timestamp())}:f>",
            inline=False,
        )
        embed.add_field(
            name="Хостер розыгрыша",
            value=f"{host.id} ({host.mention})",
            inline=False,
        )
        embed.add_field(name="Тип приза", value=prize_type, inline=False)
        embed.add_field(name="Количество", value=str(amount), inline=False)
        embed.add_field(
            name="Внёс в базу", value=ctx.author.mention, inline=False
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "loggiveaway", embed)

    @commands.command(name="giveawaylogs", aliases=["gl"])
    @check_access_decorator("giveawaylogs")
    async def giveawaylogs_cmd(
        self, ctx: commands.Context, target: discord.User = None
    ):
        target = target or ctx.author
        logs = list(giveaways_col.find({"host_id": target.id}).sort("_id", 1))

        if not logs:
            embed = make_status_embed(
                "Розыгрыши",
                f"У пользователя {target.mention} нет логов розыгрышей.",
                "info",
            )
            return await ctx.send(embed=embed)

        view = GiveawayLogsView(target=target, logs=logs)
        embed = view.build_page_embed()

        if len(logs) <= LOGS_PER_PAGE:
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="loginvite", aliases=["li"])
    @check_access_decorator("loginvite")
    async def loginvite_cmd(
        self,
        ctx: commands.Context,
        inviter: discord.User = None,
        invited: discord.User = None,
        prize: str = None,
        amount: int = 1,
    ):
        if inviter is None or invited is None or prize is None:
            return await ctx.send(embed=build_command_help_embed("loginvite"))

        log_id = get_next_sequence_value("invite_id")
        now = datetime.now(timezone.utc)

        doc = {
            "_id": log_id,
            "inviter_id": inviter.id,
            "invited_id": invited.id,
            "author_id": ctx.author.id,
            "prize": prize,
            "amount": amount,
            "created_at": now,
        }
        invites_col.insert_one(doc)

        embed = discord.Embed(
            title=f"<:logs:1522340749998428160> Инвайт №{log_id} — {inviter.name}",
            color=config.EMBED_COLOR,
        )
        embed.add_field(
            name="Дата записи",
            value=f"<t:{int(now.timestamp())}:f>",
            inline=False,
        )
        embed.add_field(
            name="Пригласил",
            value=f"{inviter.id} ({inviter.mention})",
            inline=False,
        )
        embed.add_field(
            name="Приглашённый",
            value=f"{invited.id} ({invited.mention})",
            inline=False,
        )
        embed.add_field(name="Приз", value=prize, inline=False)
        embed.add_field(name="Количество", value=str(amount), inline=False)
        embed.add_field(
            name="Внёс в базу", value=ctx.author.mention, inline=False
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "loginvite", embed)

    @commands.command(name="invitelogs", aliases=["il"])
    @check_access_decorator("invitelogs")
    async def invitelogs_cmd(
        self, ctx: commands.Context, target: discord.User = None
    ):
        target = target or ctx.author
        logs = list(invites_col.find({"inviter_id": target.id}).sort("_id", 1))

        if not logs:
            embed = make_status_embed(
                "Приглашения",
                f"У пользователя {target.mention} нет логов приглашений.",
                "info",
            )
            return await ctx.send(embed=embed)

        view = InviteLogsView(target=target, logs=logs)
        embed = view.build_page_embed()

        if len(logs) <= LOGS_PER_PAGE:
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="userinfo", aliases=["ui", "user"])
    @check_access_decorator("userinfo")
    async def userinfo_cmd(
        self, ctx: commands.Context, target: discord.Member = None
    ):
        target = target or ctx.author

        created_timestamp = int(target.created_at.timestamp())
        joined_timestamp = (
            int(target.joined_at.timestamp()) if target.joined_at else None
        )

        roles = [
            role.mention for role in reversed(target.roles) if not role.is_default()
        ]
        roles_str = ", ".join(roles) if roles else "Нет ролей"

        embed = discord.Embed(
            title=f"<:staff:1522338131339251823> Информация — {target.name}",
            color=config.EMBED_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(
            name="Имя пользователя", value=f"`{target.name}`", inline=True
        )
        embed.add_field(
            name="Отображаемое имя", value=f"**{target.display_name}**", inline=True
        )
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)

        embed.add_field(
            name="Создание аккаунта",
            value=f"<t:{created_timestamp}:R> (<t:{created_timestamp}:f>)",
            inline=False,
        )
        if joined_timestamp:
            embed.add_field(
                name="Вход на сервер",
                value=f"<t:{joined_timestamp}:R> (<t:{joined_timestamp}:f>)",
                inline=False,
            )

        embed.add_field(
            name=f"Роли [{len(roles)}]", value=roles_str, inline=False
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)

    # 6. Кто пригласил пользователя
    @commands.command(name="inviter")
    @check_access_decorator("inviter")
    async def inviter_cmd(
        self, ctx: commands.Context, target: discord.User = None
    ):
        target = target or ctx.author
        doc = invites_col.find_one({"invited_id": target.id})

        if not doc:
            embed = make_status_embed(
                "Приглашения",
                f"В базе данных нет записи о том, кто пригласил {target.mention}.",
                "info",
            )
            return await ctx.send(embed=embed)

        inviter_user = self.bot.get_user(doc["inviter_id"])
        inviter_text = (
            f"{inviter_user.name} ({inviter_user.mention})"
            if inviter_user
            else f"<@{doc['inviter_id']}>"
        )

        embed = discord.Embed(
            title=f"<:logs:1522340749998428160> Кто пригласил — {target.name}",
            color=config.EMBED_COLOR,
        )
        embed.add_field(name="Пользователь", value=target.mention, inline=False)
        embed.add_field(name="Пригласил", value=inviter_text, inline=False)
        embed.add_field(name="Приз", value=doc.get("prize", "—"), inline=False)
        embed.add_field(
            name="Дата",
            value=f"<t:{int(doc['created_at'].timestamp())}:f>",
            inline=False,
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)

    @commands.command(name="invites")
    @check_access_decorator("invites")
    async def invites_cmd(
        self, ctx: commands.Context, target: discord.User = None
    ):
        target = target or ctx.author
        count = invites_col.count_documents({"inviter_id": target.id})

        embed = make_status_embed(
            "Статистика приглашений",
            f"Пользователь {target.mention} пригласил участников: **{count}**",
            "info",
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PlayerLogsCog(bot))