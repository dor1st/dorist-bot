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
        self.invites_cache = {}

    async def cog_load(self):
        """Автоматическая загрузка инвайтов при загрузке кога."""
        self.bot.loop.create_task(self.cache_all_invites())

    async def cache_all_invites(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                invs = await guild.invites()
                self.invites_cache[guild.id] = {inv.code: inv.uses for inv in invs}
            except discord.Forbidden:
                pass

    # ==========================================
    # EVENT LISTENERS FOR INVITES & MESSAGES
    # ==========================================

    @commands.Cog.listener()
    async def on_ready(self):
        await self.cache_all_invites()

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Обновляем кэш при создании новой ссылки."""
        if invite.guild.id not in self.invites_cache:
            self.invites_cache[invite.guild.id] = {}
        self.invites_cache[invite.guild.id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Удаляем ссылку из кэша при ее удалении."""
        if invite.guild.id in self.invites_cache:
            self.invites_cache[invite.guild.id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Фиксируем зашедшего игрока и выдаем +1 инвайт пригласившему."""
        if member.bot or not member.guild:
            return

        guild = member.guild
        old_invites = self.invites_cache.get(guild.id, {})
        inviter_user = None

        try:
            new_invites = await guild.invites()
            for inv in new_invites:
                # Находим ссылку, у которой увеличилось кол-во использований
                if inv.code in old_invites and inv.uses > old_invites[inv.code]:
                    inviter_user = inv.inviter
                    break
                elif inv.code not in old_invites and inv.uses > 0:
                    inviter_user = inv.inviter
                    break

            # Обновляем кэш
            self.invites_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
        except discord.Forbidden:
            return

        # Если нашли пригласившего и это не сам зашедший
        if inviter_user and inviter_user.id != member.id:
            # 1. Записываем/обновляем системное кол-во инвайтов в users_col
            users_col.update_one(
                {"_id": inviter_user.id},
                {"$inc": {"real_invites": 1}},
                upsert=True
            )
            # 2. Записываем в базу, КТО именно пригласил этого игрока
            users_col.update_one(
                {"_id": member.id},
                {"$set": {"invited_by": inviter_user.id}},
                upsert=True
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        users_col.update_one(
            {"_id": message.author.id},
            {"$inc": {"messages_count": 1}},
            upsert=True
        )

    # ==========================================
    # COMMANDS
    # ==========================================

    @commands.command(name="messages", aliases=["msg", "msgs", "message"])
    @check_access_decorator("messages")
    @is_allowed_channel()
    async def messages_cmd(self, ctx: commands.Context, target: discord.User = None):
        """Просмотреть количество текстовых сообщений пользователя."""
        target = target or ctx.author
        
        user_doc = users_col.find_one({"_id": target.id}) or {}
        messages_count = user_doc.get("messages_count", 0)

        embed = make_status_embed(
            "Статистика сообщений",
            f"Пользователь {target.mention} отправил сообщений: **{messages_count}**",
            "info",
        )
        await ctx.send(embed=embed)

    @commands.command(name="invites", aliases=["inv"])
    @check_access_decorator("invites")
    @is_allowed_channel()
    async def invites_cmd(self, ctx: commands.Context, target: discord.User = None):
        target = target or ctx.author
        
        user_doc = users_col.find_one({"_id": target.id}) or {}
        real_invites = user_doc.get("real_invites", 0)
        bonus_invites = user_doc.get("bonus_invites", 0)
        total_invites = real_invites + bonus_invites

        embed = make_status_embed(
            "Статистика приглашений",
            f"Пользователь {target.mention} пригласил участников: **{total_invites}**",
            "info",
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PlayerLogsCog(bot))