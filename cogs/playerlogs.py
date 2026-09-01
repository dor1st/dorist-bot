import math
from datetime import datetime, timezone
import discord
from discord.ext import commands

import config
from database import giveaways_col, invites_col, users_col, get_next_sequence_value
from utils import (
    check_access_decorator,
    make_error_embed,
    make_status_embed,
    log_action,
)

VALID_PRIZES = ["Робуксы", "Коины", "Геймпасс", "Годли"]
LOGS_PER_PAGE = config.LOGS_PER_PAGE if hasattr(config, "LOGS_PER_PAGE") else 3


def build_cmd_help(command_name: str, usage: str, description: str) -> discord.Embed:
    """Генератор полноценного эмбеда с подсказкой по использованию команды."""
    embed = discord.Embed(
        title=f"Информация о команде — .{command_name}",
        description=f"{description}\n\n**Использование:**\n`{usage}`",
        color=config.EMBED_COLOR,
    )
    prizes_str = ", ".join([f"`{p}`" for p in VALID_PRIZES])
    embed.add_field(
        name="Допустимые категории призов",
        value=prizes_str,
        inline=False
    )
    embed.set_footer(text=config.FOOTER_TEXT)
    return embed


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

            link_str = f"\n**Ссылка:** [Перейти к сообщению]({doc.get('message_url')})" if doc.get("message_url") else ""

            description_lines.append(
                f"**Розыгрыш №{index}** (Лог №{doc.get('_id')})\n"
                f"**Хостер:** {self.target.name} ({self.target.mention})\n"
                f"**Приз:** {doc.get('prize_type', '—')}\n"
                f"**Количество:** {doc.get('amount', 1)}\n"
                f"**Внёс в базу:** <@{doc.get('author_id')}>"
                f"{link_str}\n"
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

    @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            if message.author.bot or not message.guild:
                return
    
            users_col.update_one(
                {"_id": message.author.id},
                {"$inc": {"messages_count": 1}},
                upsert=True
            )
    
    @commands.command(name="messages", aliases=["msg", "msgs"])
            @check_access_decorator("messages")
            async def messages_cmd(self, ctx: commands.Context, target: discord.User = None):
                target = target or ctx.author
                user_doc = users_col.find_one({"_id": target.id})
                count = user_doc.get("messages_count", 0) if user_doc else 0
        
                embed = make_status_embed(
                    "Статистика сообщений",
                    f"Пользователь {target.mention} отправил сообщений: **{count}**",
                    "info",
                )
                await ctx.send(embed=embed)

    @commands.command(name="loggiveaway", aliases=["lg"])
    @check_access_decorator("loggiveaway")
    async def loggiveaway_cmd(
        self,
        ctx: commands.Context,
        host: discord.User = None,
        prize_type: str = None,
        amount: int = None,
        link: str = None,
    ):
        if host is None or prize_type is None or amount is None or link is None:
            embed = build_cmd_help(
                "loggiveaway",
                ".loggiveaway [ID/упоминание_хостера] [приз] [количество] [ссылка_на_сообщение]",
                "Внести новый проведенный розыгрыш в базу данных."
            )
            return await ctx.send(embed=embed)

        matched_prize = next((p for p in VALID_PRIZES if p.lower() == prize_type.lower()), None)
        if not matched_prize:
            prizes_str = ", ".join([f"`{p}`" for p in VALID_PRIZES])
            embed = make_error_embed(
                "Неверная категория приза",
                f"Вы указали недействительную категорию приза: `{prize_type}`.\n\n**Допустимые категории:**\n{prizes_str}"
            )
            return await ctx.send(embed=embed)

        log_id = get_next_sequence_value("giveaway_id")
        now = datetime.now(timezone.utc)

        doc = {
            "_id": log_id,
            "host_id": host.id,
            "author_id": ctx.author.id,
            "prize_type": matched_prize,
            "amount": amount,
            "message_url": link,
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
        embed.add_field(name="Тип приза", value=matched_prize, inline=False)
        embed.add_field(name="Количество", value=str(amount), inline=False)
        embed.add_field(name="Ссылка на розыгрыш", value=f"[Перейти к сообщению]({link})", inline=False)
        embed.add_field(
            name="Внёс в базу", value=ctx.author.mention, inline=False
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "loggiveaway", embed)

    @commands.command(name="deletegiveaway", aliases=["delgiveaway", "dlg"])
    @check_access_decorator("deletegiveaway")
    async def deletegiveaway_cmd(self, ctx: commands.Context, log_id: int = None):
        if log_id is None:
            embed = discord.Embed(
                title="Информация о команде — .deletegiveaway",
                description="Удалить лог розыгрыша из базы данных по его номеру.\n\n**Использование:**\n`.deletegiveaway [ID_лога]`",
                color=config.EMBED_COLOR,
            )
            embed.set_footer(text=config.FOOTER_TEXT)
            return await ctx.send(embed=embed)

        doc = giveaways_col.find_one_and_delete({"_id": log_id})
        if not doc:
            embed = make_error_embed(
                "Лог не найден",
                f"Розыгрыш с номером лога `{log_id}` не найден в базе данных."
            )
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="Удаление розыгрыша",
            description=f"Лог розыгрыша **№{log_id}** успешно удалён из базы данных.",
            color=0xe74c3c,
        )
        embed.add_field(name="Хостер", value=f"<@{doc.get('host_id')}> (`{doc.get('host_id')}`)", inline=False)
        embed.add_field(name="Приз", value=f"{doc.get('prize_type', '—')} ({doc.get('amount', 1)} шт.)", inline=True)
        embed.add_field(name="Удалил", value=ctx.author.mention, inline=True)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "deletegiveaway", embed)

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
            embed = build_cmd_help(
                "loginvite",
                ".loginvite [ID/упоминание_пригласившего] [ID/упоминание_приглашенного] [приз] [количество]",
                "Записать выданный приз за приглашение участника."
            )
            return await ctx.send(embed=embed)

        existing = invites_col.find_one({"invited_id": invited.id})
        if existing:
            created_dt = existing.get("created_at")
            time_str = f"<t:{int(created_dt.timestamp())}:f>" if isinstance(created_dt, datetime) else "—"
            embed = make_error_embed(
                "Приз уже был получен!",
                f"За участника {invited.mention} (`{invited.id}`) уже выдовали приз ранее!\n\n"
                f"**Кто получил приз:** <@{existing.get('inviter_id')}>\n"
                f"**Приз:** {existing.get('prize', '—')} ({existing.get('amount', 1)} шт.)\n"
                f"**Дата выдачи:** {time_str}"
            )
            return await ctx.send(embed=embed)

        matched_prize = next((p for p in VALID_PRIZES if p.lower() == prize.lower()), None)
        if not matched_prize:
            prizes_str = ", ".join([f"`{p}`" for p in VALID_PRIZES])
            embed = make_error_embed(
                "Неверная категория приза",
                f"Вы указали недействительную категорию приза: `{prize}`.\n\n**Допустимые категории:**\n{prizes_str}"
            )
            return await ctx.send(embed=embed)

        log_id = get_next_sequence_value("invite_id")
        now = datetime.now(timezone.utc)

        doc = {
            "_id": log_id,
            "inviter_id": inviter.id,
            "invited_id": invited.id,
            "author_id": ctx.author.id,
            "prize": matched_prize,
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
        embed.add_field(name="Приз", value=matched_prize, inline=False)
        embed.add_field(name="Количество", value=str(amount), inline=False)
        embed.add_field(
            name="Внёс в базу", value=ctx.author.mention, inline=False
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "loginvite", embed)

    @commands.command(name="deleteinvite", aliases=["delinvite", "dli"])
    @check_access_decorator("deleteinvite")
    async def deleteinvite_cmd(self, ctx: commands.Context, log_id: int = None):
        if log_id is None:
            embed = discord.Embed(
                title="Информация о команде — .deleteinvite",
                description="Удалить лог приглашения из базы данных по его номеру.\n\n**Использование:**\n`.deleteinvite [ID_лога]`",
                color=config.EMBED_COLOR,
            )
            embed.set_footer(text=config.FOOTER_TEXT)
            return await ctx.send(embed=embed)

        doc = invites_col.find_one_and_delete({"_id": log_id})
        if not doc:
            embed = make_error_embed(
                "Лог не найден",
                f"Лог приглашения с номером `{log_id}` не найден в базе данных."
            )
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="Удаление приглашения",
            description=f"Лог приглашения **№{log_id}** успешно удалён из базы данных.",
            color=0xe74c3c,
        )
        embed.add_field(name="Пригласил", value=f"<@{doc.get('inviter_id')}> (`{doc.get('inviter_id')}`)", inline=False)
        embed.add_field(name="Приглашённый", value=f"<@{doc.get('invited_id')}> (`{doc.get('invited_id')}`)", inline=False)
        embed.add_field(name="Приз", value=f"{doc.get('prize', '—')} ({doc.get('amount', 1)} шт.)", inline=True)
        embed.add_field(name="Удалил", value=ctx.author.mention, inline=True)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)
        await log_action(ctx.guild, "deleteinvite", embed)

    @commands.command(name="validinvite", aliases=["vi", "checkinvite"])
    @check_access_decorator("validinvite")
    async def validinvite_cmd(
        self, ctx: commands.Context, target: discord.User = None
    ):
        if target is None:
            embed = build_cmd_help(
                "validinvite",
                ".validinvite [ID/упоминание_приглашенного]",
                "Проверить, получал ли кто-то уже приз за приглашение этого игрока."
            )
            return await ctx.send(embed=embed)

        doc = invites_col.find_one({"invited_id": target.id})

        if not doc:
            embed = discord.Embed(
                title="<:sparkles:1522342290494849034> Доступно к получению",
                description=(
                    f"За приглашение пользователя {target.mention} (`{target.id}`) **ещё никто не получал приз**.\n\n"
                    "Вы можете зарегистрировать выдачу приза с помощью команды `.loginvite`."
                ),
                color=0x2ecc71,
            )
            embed.set_footer(text=config.FOOTER_TEXT)
            return await ctx.send(embed=embed)

        created_dt = doc.get("created_at")
        time_str = f"<t:{int(created_dt.timestamp())}:f>" if isinstance(created_dt, datetime) else "—"

        embed = discord.Embed(
            title="<:logs:1522340749998428160> Приз уже был получен",
            description=f"За пользователя {target.mention} (`{target.id}`) **уже забирали награду**.",
            color=0xe74c3c,
        )
        embed.add_field(
            name="Пригласивший (Кто забрал приз)",
            value=f"<@{doc.get('inviter_id')}> (`{doc.get('inviter_id')}`)",
            inline=False,
        )
        embed.add_field(
            name="Полученный приз",
            value=f"**{doc.get('prize', '—')}** ({doc.get('amount', 1)} шт.)",
            inline=True,
        )
        embed.add_field(
            name="Кто внес запись",
            value=f"<@{doc.get('author_id')}>",
            inline=True,
        )
        embed.add_field(
            name="Дата записи",
            value=time_str,
            inline=False,
        )
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)

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
    async def userinfo_cmd(self, ctx: commands.Context, target: discord.User = None):
        target = target or ctx.author
        member = ctx.guild.get_member(target.id) if ctx.guild else None
        created_timestamp = int(target.created_at.timestamp())

        # Статистика из БД
        user_doc = users_col.find_one({"_id": target.id})
        msg_count = user_doc.get("messages_count", 0) if user_doc else 0
        invites_count = invites_col.count_documents({"inviter_id": target.id})

        embed = discord.Embed(
            title=f"<:staff:1522338131339251823> Информация — {target.name}",
            color=config.EMBED_COLOR,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Имя пользователя", value=f"`{target.name}`", inline=True)
        embed.add_field(name="Отображаемое имя", value=f"**{target.display_name}**", inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)

        embed.add_field(
            name="Статистика активности",
            value=f"💬 Сообщений: **{msg_count}**\n📩 Приглашений: **{invites_count}**",
            inline=False,
        )

        embed.add_field(
            name="Создание аккаунта",
            value=f"<t:{created_timestamp}:R> (<t:{created_timestamp}:f>)",
            inline=False,
        )

        if member:
            if member.joined_at:
                joined_timestamp = int(member.joined_at.timestamp())
                embed.add_field(
                    name="Вход на сервер",
                    value=f"<t:{joined_timestamp}:R> (<t:{joined_timestamp}:f>)",
                    inline=False,
                )

            roles = [role.mention for role in reversed(member.roles) if not role.is_default()]
            roles_str = ", ".join(roles) if roles else "Нет ролей"
            embed.add_field(name=f"Роли [{len(roles)}]", value=roles_str, inline=False)

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

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