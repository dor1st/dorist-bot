import random
import re
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

import config
from database import giveaways_col, users_col
from utils import check_access_decorator, make_error_embed, make_status_embed


GIVEAWAY_EMOJI = getattr(config, "GIVEAWAY_EMOJI", "🎉")
MAX_DURATION = getattr(config, "MAX_DURATION", timedelta(days=31))
SETUP_TIMEOUT = getattr(config, "SETUP_TIMEOUT", 300)

GIVEAWAY_IMAGE_URL = getattr(
    config, 
    "GIVEAWAY_IMAGE_URL", 
    "https://cdn.discordapp.com/attachments/1521823293169205258/1544354921002831892/13afec33f77f8f2d.png?ex=6a983419&is=6a96e299&hm=6bc1383a8045076895f92158d8f03440c90e5c6c30cc668f76d3a7f26370d57c" 
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_duration(value: str) -> timedelta | None:
    if not value or value == "—":
        return None
    value = value.strip().lower().replace(" ", "")
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)(s|m|h|d|w|mo|month|months)",
        value,
    )
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    if amount <= 0:
        return None

    seconds = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
        "mo": 31 * 86400,
        "month": 31 * 86400,
        "months": 31 * 86400,
    }[unit]

    duration = timedelta(seconds=amount * seconds)
    return duration if duration <= MAX_DURATION else None


def format_timedelta(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "0 сек."
        
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} дн.")
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0:
        parts.append(f"{minutes} мин.")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} сек.")

    return " ".join(parts)


def format_claim_time(claim_time_raw: str) -> str:
    td = parse_duration(claim_time_raw)
    if td:
        return format_timedelta(td)
    return claim_time_raw


def role_mentions(guild: discord.Guild, role_ids: list[int]) -> str:
    roles = []
    for role_id in role_ids:
        role = guild.get_role(int(role_id))
        roles.append(role.mention if role else f"`{role_id}`")
    return ", ".join(roles) if roles else "Не установлено"


def build_giveaway_embed(
    *,
    prize: str,
    host: discord.Member | discord.User,
    ends_at: datetime,
    winners_count: int,
    participant_count: int,
    role_mode: str | None,
    required_roles: list[int],
    min_messages: int,
    min_invites: int,
    bonus_roles: dict[int, int],
    claim_time: str = "—",
    ended: bool = False,
    winner_ids: list[int] | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=prize,
        color=config.EMBED_COLOR,
    )

    formatted_claim = format_claim_time(claim_time)

    lines = [
        f"• **Розыгрыш от:** {host.mention}",
        f"• **Завершение:** <t:{int(ends_at.timestamp())}:f> (<t:{int(ends_at.timestamp())}:R>)",
        f"• **Победителей:** **{winners_count}**",
        f"• **Участников:** **{participant_count}**",
    ]

    if formatted_claim and formatted_claim != "—":
        lines.append(f"• **Время на получение:** **{formatted_claim}**")

    requirements = []
    if min_messages > 0:
        requirements.append(f"• Сообщений требуется: **{min_messages}**")
    if min_invites > 0:
        requirements.append(f"• Приглашений требуется: **{min_invites}**")
    if required_roles:
        mode_text = "все" if role_mode == "all" else "одна из"
        requirements.append(
            f"• Роли ({mode_text}): {role_mentions(host.guild, required_roles)}"
        )

    if requirements:
        lines.append("")
        lines.append("**Требования:**")
        lines.extend(requirements)

    if bonus_roles:
        lines.append("")
        lines.append("**Роли с дополнительными шансами:**")
        for role_id, entries in bonus_roles.items():
            role = host.guild.get_role(int(role_id))
            role_name = role.mention if role else f"`{role_id}`"
            lines.append(f"• {role_name} • **+{entries} доп. шансов**")

    if ended:
        lines.append("")
        if winner_ids:
            mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
            lines.append(f"**Победители:** {mentions}")
        else:
            lines.append("**Победители:** Подходящих участников не найдено.")

    embed.description = "\n".join(lines)
    if GIVEAWAY_IMAGE_URL and GIVEAWAY_IMAGE_URL != "https://example.com/banner.png":
        embed.set_image(url=GIVEAWAY_IMAGE_URL)
    embed.set_footer(text=config.FOOTER_TEXT)
    return embed


class GiveawaySetupView(discord.ui.View):
    def __init__(
        self,
        bot,
        ctx: commands.Context,
        prize: str,
        duration_text: str,
        duration: timedelta,
        winners_count: int,
        claim_time: str,
    ):
        super().__init__(timeout=SETUP_TIMEOUT)

        self.bot = bot
        self.ctx = ctx
        self.guild = ctx.guild

        self.prize = prize
        self.duration_text = duration_text
        self.duration = duration
        self.winners_count = winners_count
        self.claim_time = claim_time

        self.target_channel = ctx.channel

        self.role_mode = "all"
        self.required_roles: list[int] = []
        self.ping_roles: list[int] = []
        self.min_messages = 0
        self.min_invites = 0
        self.bonus_roles: dict[int, int] = {}

        self.setup_message: discord.Message | None = None

    async def refresh_setup_message(self):
        if self.setup_message:
            try:
                await self.setup_message.edit(
                    embed=self.setup_embed(),
                    view=self,
                )
            except discord.HTTPException:
                pass

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Только автор создания розыгрыша может менять его настройки.",
                ephemeral=True,
            )
            return False
        return True

    def setup_embed(self) -> discord.Embed:
        role_mode_text = (
            "Все из списка" if self.role_mode == "all" else "Одна из"
        )

        embed = discord.Embed(
            title="<:giveaway:1522331215976206446> Настройка розыгрыша",
            description=(
                "Заполните дополнительные параметры, "
                "после чего нажмите **«Создать розыгрыш»**.\n\n"
                f"**Приз:** {self.prize}\n"
                f"**Длительность:** {self.duration_text}\n"
                f"**Количество победителей:** {self.winners_count}\n"
                f"**Время на получение:** {format_claim_time(self.claim_time)}\n"
                f"**Канал:** {self.target_channel.mention}"
            ),
            color=config.EMBED_COLOR,
        )

        embed.add_field(
            name="1. Роли (Требования)",
            value=(
                f"**Режим:** {role_mode_text}\n"
                f"**Роли:** {role_mentions(self.guild, self.required_roles)}"
            ),
            inline=False,
        )

        embed.add_field(
            name="2. Пинги",
            value=f"**Роли для упоминания:** {role_mentions(self.guild, self.ping_roles)}",
            inline=False,
        )

        embed.add_field(
            name="3. Требования",
            value=(
                f"• Минимум сообщений: **{self.min_messages}**\n"
                f"• Минимум приглашений: **{self.min_invites}**"
            ),
            inline=False,
        )

        if self.bonus_roles:
            bonus_text = "\n".join(
                f"• {role_mentions(self.guild, [role_id])} — **+{entries}**"
                for role_id, entries in self.bonus_roles.items()
            )
        else:
            bonus_text = "Не установлены"

        embed.add_field(
            name="4. Дополнительные шансы",
            value=bonus_text,
            inline=False,
        )

        embed.set_footer(text=config.FOOTER_TEXT)
        return embed

    @discord.ui.button(
        label="Канал",
        emoji="<:textchat:1522331990517616752>",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def channel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Выберите канал для проведения розыгрыша:",
            view=ChannelSetupView(self),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Роли",
        emoji="<:roles:1522341200542044351>",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def roles_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Выберите режим проверки ролей и роли из списка.",
            view=RoleSetupView(self),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Пинги",
        emoji="🔔",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def pings_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Выберите роли, которые нужно пингануть при публикации:",
            view=PingRoleSetupView(self),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Требования",
        emoji="<:logs:1522340749998428160>",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def requirements_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(RequirementsModal(self))

    @discord.ui.button(
        label="Доп. шансы",
        emoji="<:sparkles:1522342290494849034>",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def bonus_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_message(
            "Выберите роль и укажите количество дополнительных шансов.",
            view=BonusRoleView(self),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Создать розыгрыш",
        emoji="<:verify:1522329028420173976>",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def create_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.defer(ephemeral=True)

        channel = self.target_channel
        if not hasattr(channel, "send"):
            channel = self.guild.get_channel(channel.id)

        if not channel or not hasattr(channel, "send"):
            await interaction.followup.send(
                "Не удалось найти выбранный текстовый канал. Попробуйте выбрать его заново.",
                ephemeral=True,
            )
            return

        ends_at = utcnow() + self.duration

        embed = build_giveaway_embed(
            prize=self.prize,
            host=self.ctx.author,
            ends_at=ends_at,
            winners_count=self.winners_count,
            participant_count=0,
            role_mode=self.role_mode,
            required_roles=self.required_roles,
            min_messages=self.min_messages,
            min_invites=self.min_invites,
            bonus_roles=self.bonus_roles,
            claim_time=self.claim_time,
        )

        content_ping = ""
        if self.ping_roles:
            content_ping = " ".join(f"<@&{rid}>" for rid in self.ping_roles)

        try:
            message = await channel.send(content=content_ping if content_ping else None, embed=embed)
            await message.add_reaction(GIVEAWAY_EMOJI)
        except discord.HTTPException:
            await interaction.followup.send(
                "Не удалось создать розыгрыш. "
                "Проверьте права бота на отправку сообщений и добавление реакций в указанном канале.",
                ephemeral=True,
            )
            return

        doc = {
            "type": "giveaway",
            "status": "active",
            "guild_id": self.guild.id,
            "channel_id": self.target_channel.id,
            "message_id": message.id,
            "message_url": message.jump_url,
            "host_id": self.ctx.author.id,
            "prize": self.prize,
            "duration": self.duration_text,
            "winners_count": self.winners_count,
            "claim_time": self.claim_time,
            "ends_at": ends_at,
            "participant_count": 0,
            "role_mode": self.role_mode,
            "required_roles": self.required_roles,
            "min_messages": self.min_messages,
            "min_invites": self.min_invites,
            "bonus_roles": {
                str(role_id): entries
                for role_id, entries in self.bonus_roles.items()
            },
            "eligible_user_ids": [],
        }

        result = giveaways_col.insert_one(doc)
        giveaways_col.update_one(
            {"_id": result.inserted_id},
            {"$set": {"giveaway_id": str(result.inserted_id)}},
        )

        for child in self.children:
            child.disabled = True

        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            f"🎉 **Розыгрыш успешно создан!**\nКанал: {self.target_channel.mention}\nСсылка: {message.jump_url}",
            ephemeral=True,
        )

        self.stop()


class ChannelSetupView(discord.ui.View):
    def __init__(self, setup: GiveawaySetupView):
        super().__init__(timeout=300)
        self.setup = setup
        self.add_item(ChannelSelect(setup))

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.setup.ctx.author.id:
            await interaction.response.send_message(
                "Только автор создания розыгрыша может менять его настройки.",
                ephemeral=True,
            )
            return False
        return True


class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setup: GiveawaySetupView):
        self.setup = setup
        super().__init__(
            placeholder="Выберите текстовый канал",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]

        full_channel = interaction.guild.get_channel(selected_channel.id)

        if full_channel is None:
            full_channel = await interaction.guild.fetch_channel(selected_channel.id)

        self.setup.target_channel = full_channel
        await self.setup.refresh_setup_message()
        await interaction.response.edit_message(
            content=f"Канал установлен: {self.setup.target_channel.mention}",
            view=None,
        )


class PingRoleSetupView(discord.ui.View):
    def __init__(self, setup: GiveawaySetupView):
        super().__init__(timeout=300)
        self.setup = setup
        self.add_item(PingRoleSelect(setup))

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.setup.ctx.author.id:
            await interaction.response.send_message(
                "Только автор создания розыгрыша может менять его настройки.",
                ephemeral=True,
            )
            return False
        return True


class PingRoleSelect(discord.ui.RoleSelect):
    def __init__(self, setup: GiveawaySetupView):
        self.setup = setup
        super().__init__(
            placeholder="Выберите роли для упоминания",
            min_values=0,
            max_values=25,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.setup.ping_roles = [role.id for role in self.values]
        await self.setup.refresh_setup_message()
        await interaction.response.edit_message(
            content="Роли для упоминания обновлены.",
            view=self.view,
        )


class RoleSetupView(discord.ui.View):
    def __init__(self, setup: GiveawaySetupView):
        super().__init__(timeout=300)
        self.setup = setup
        self.add_item(RoleModeSelect(setup))
        self.add_item(RequiredRoleSelect(setup))

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.setup.ctx.author.id:
            await interaction.response.send_message(
                "Только автор создания розыгрыша может менять его настройки.",
                ephemeral=True,
            )
            return False
        return True


class RoleModeSelect(discord.ui.Select):
    def __init__(self, setup: GiveawaySetupView):
        self.setup = setup
        super().__init__(
            placeholder="Режим проверки ролей",
            options=[
                discord.SelectOption(
                    label="Все из списка",
                    value="all",
                    description="Участник должен иметь все выбранные роли.",
                ),
                discord.SelectOption(
                    label="Одна из",
                    value="one",
                    description="Участнику достаточно иметь одну выбранную роль.",
                ),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.setup.role_mode = self.values[0]
        await self.setup.refresh_setup_message()
        await interaction.response.edit_message(
            content="Режим ролей обновлён. Теперь выберите роли ниже.",
            view=self.view,
        )


class RequiredRoleSelect(discord.ui.RoleSelect):
    def __init__(self, setup: GiveawaySetupView):
        self.setup = setup
        super().__init__(
            placeholder="Выберите обязательные роли",
            min_values=0,
            max_values=25,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.setup.required_roles = [role.id for role in self.values]
        await self.setup.refresh_setup_message()
        await interaction.response.edit_message(
            content="Обязательные роли обновлены.",
            view=self.view,
        )


class RequirementsModal(
    discord.ui.Modal,
    title="Требования розыгрыша",
):
    min_messages = discord.ui.TextInput(
        label="Минимальное количество сообщений",
        placeholder="0",
        required=True,
        max_length=10,
    )

    min_invites = discord.ui.TextInput(
        label="Минимальное количество приглашений",
        placeholder="0",
        required=True,
        max_length=10,
    )

    def __init__(self, setup: GiveawaySetupView):
        super().__init__()
        self.setup = setup

    async def on_submit(self, interaction: discord.Interaction):
        try:
            messages = int(str(self.min_messages.value).strip())
            invites = int(str(self.min_invites.value).strip())
            if messages < 0 or invites < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Оба значения должны быть целыми числами от 0.",
                ephemeral=True,
            )
            return

        self.setup.min_messages = messages
        self.setup.min_invites = invites
        await self.setup.refresh_setup_message()
        await interaction.response.send_message(
            "Требования сохранены.",
            ephemeral=True,
        )


class BonusRoleView(discord.ui.View):
    def __init__(self, setup: GiveawaySetupView):
        super().__init__(timeout=300)
        self.setup = setup
        self.add_item(BonusRoleSelect(setup))

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.setup.ctx.author.id:
            await interaction.response.send_message(
                "Только автор создания розыгрыша может менять его настройки.",
                ephemeral=True,
            )
            return False
        return True


class BonusRoleSelect(discord.ui.RoleSelect):
    def __init__(self, setup: GiveawaySetupView):
        self.setup = setup
        super().__init__(
            placeholder="Выберите роль для дополнительного шанса",
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        await interaction.response.send_modal(
            BonusEntriesModal(self.setup, role.id)
        )


class BonusEntriesModal(
    discord.ui.Modal,
    title="Дополнительный шанс",
):
    entries = discord.ui.TextInput(
        label="Сколько дополнительных шансов?",
        placeholder="Например: 5",
        required=True,
        max_length=5,
    )

    def __init__(self, setup: GiveawaySetupView, role_id: int):
        super().__init__()
        self.setup = setup
        self.role_id = role_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(str(self.entries.value).strip())
            if value < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Количество дополнительных шансов должно быть целым числом больше 0.",
                ephemeral=True,
            )
            return

        self.setup.bonus_roles[self.role_id] = value
        await self.setup.refresh_setup_message()
        await interaction.response.send_message(
            f"Для роли <@&{self.role_id}> установлено **+{value}** шансов.",
            ephemeral=True,
        )


class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.finish_loop.start()

    def cog_unload(self):
        self.finish_loop.cancel()

    async def _get_giveaway_message(self, doc: dict):
        channel = self.bot.get_channel(int(doc["channel_id"]))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(doc["channel_id"]))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None

        try:
            return await channel.fetch_message(int(doc["message_id"]))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _get_reaction_users(self, message: discord.Message) -> list[discord.User]:
        reaction = discord.utils.get(message.reactions, emoji=GIVEAWAY_EMOJI)
        if reaction is None:
            return []

        users = []
        async for user in reaction.users(limit=None):
            if not user.bot:
                users.append(user)
        return users

    def _is_eligible(self, member: discord.Member, doc: dict) -> bool:
        user_doc = users_col.find_one({"_id": member.id}) or {}

        if user_doc.get("messages_count", 0) < doc.get("min_messages", 0):
            return False

        total_invites = user_doc.get("real_invites", 0) + user_doc.get("bonus_invites", 0)
        if total_invites < doc.get("min_invites", 0):
            return False

        required_roles = [int(role_id) for role_id in doc.get("required_roles", [])]
        if required_roles:
            member_roles = {role.id for role in member.roles}
            if doc.get("role_mode", "all") == "all":
                if not all(role_id in member_roles for role_id in required_roles):
                    return False
            else:
                if not any(role_id in member_roles for role_id in required_roles):
                    return False

        return True

    def _weight(self, member: discord.Member, doc: dict) -> int:
        member_roles = {role.id for role in member.roles}
        bonus = 0
        for role_id, entries in doc.get("bonus_roles", {}).items():
            if int(role_id) in member_roles:
                bonus += int(entries)
        return 1 + bonus

    async def _update_participant_count(
        self,
        payload: discord.RawReactionActionEvent,
        delta: int,
    ):
        bot_user = self.bot.user
        if payload.emoji.name != GIVEAWAY_EMOJI or (bot_user and payload.user_id == bot_user.id):
            return

        doc = giveaways_col.find_one(
            {
                "type": "giveaway",
                "guild_id": payload.guild_id,
                "message_id": payload.message_id,
                "status": "active",
            }
        )

        if not doc:
            return

        giveaways_col.update_one(
            {"_id": doc["_id"]},
            {"$inc": {"participant_count": delta}},
        )

        if delta < 0:
            giveaways_col.update_one(
                {"_id": doc["_id"], "participant_count": {"$lt": 0}},
                {"$set": {"participant_count": 0}},
            )

        doc = giveaways_col.find_one({"_id": doc["_id"]})
        if not doc:
            return

        message = await self._get_giveaway_message(doc)
        if not message:
            return

        guild = self.bot.get_guild(int(doc["guild_id"]))
        if not guild:
            return

        host = guild.get_member(int(doc["host_id"])) or self.bot.user

        embed = build_giveaway_embed(
            prize=doc["prize"],
            host=host,
            ends_at=doc["ends_at"],
            winners_count=doc["winners_count"],
            participant_count=max(0, doc.get("participant_count", 0)),
            role_mode=doc.get("role_mode"),
            required_roles=doc.get("required_roles", []),
            min_messages=doc.get("min_messages", 0),
            min_invites=doc.get("min_invites", 0),
            bonus_roles={
                int(key): int(value) for key, value in doc.get("bonus_roles", {}).items()
            },
            claim_time=doc.get("claim_time", "—"),
        )

        try:
            await message.edit(embed=embed)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent,
    ):
        bot_user = self.bot.user
        if payload.emoji.name != GIVEAWAY_EMOJI or (bot_user and payload.user_id == bot_user.id):
            return

        doc = giveaways_col.find_one(
            {
                "type": "giveaway",
                "guild_id": payload.guild_id,
                "message_id": payload.message_id,
            }
        )

        if not doc:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        if doc.get("status") != "active":
            message = await self._get_giveaway_message(doc)
            if message:
                try:
                    await message.remove_reaction(payload.emoji, member)
                except discord.HTTPException:
                    pass
            return

        if not self._is_eligible(member, doc):
            message = await self._get_giveaway_message(doc)
            if message:
                try:
                    await message.remove_reaction(payload.emoji, member)
                except discord.HTTPException:
                    pass
            return

        await self._update_participant_count(payload, +1)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self,
        payload: discord.RawReactionActionEvent,
    ):
        await self._update_participant_count(payload, -1)

    async def finish_giveaway(
        self,
        doc: dict,
        *,
        forced: bool = False,
    ):
        if doc.get("status") != "active":
            return False

        message = await self._get_giveaway_message(doc)
        guild = self.bot.get_guild(int(doc["guild_id"]))

        if guild is None or message is None:
            giveaways_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "ended", "ended_at": utcnow()}},
            )
            return False

        users = await self._get_reaction_users(message)
        eligible = []
        eligible_user_ids = []

        for user in users:
            member = guild.get_member(user.id)
            if member and self._is_eligible(member, doc):
                eligible.append((member, self._weight(member, doc)))
                eligible_user_ids.append(member.id)

        winner_count = min(doc.get("winners_count", 1), len(eligible))
        winners = []
        pool = eligible[:]

        for _ in range(winner_count):
            total_weight = sum(weight for _, weight in pool)
            if total_weight <= 0:
                break

            roll = random.uniform(0, total_weight)
            current = 0
            selected_index = len(pool) - 1

            for index, (_, weight) in enumerate(pool):
                current += weight
                if roll <= current:
                    selected_index = index
                    break

            winners.append(pool.pop(selected_index)[0])

        winner_ids = [member.id for member in winners]
        host = guild.get_member(int(doc["host_id"])) or self.bot.user

        ended_embed = build_giveaway_embed(
            prize=doc["prize"],
            host=host,
            ends_at=doc["ends_at"],
            winners_count=doc["winners_count"],
            participant_count=len(users),
            role_mode=doc.get("role_mode"),
            required_roles=doc.get("required_roles", []),
            min_messages=doc.get("min_messages", 0),
            min_invites=doc.get("min_invites", 0),
            bonus_roles={
                int(key): int(value) for key, value in doc.get("bonus_roles", {}).items()
            },
            claim_time=doc.get("claim_time", "—"),
            ended=True,
            winner_ids=winner_ids,
        )

        try:
            await message.edit(embed=ended_embed)
        except discord.HTTPException:
            pass

        giveaways_col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": "ended",
                    "ended_at": utcnow(),
                    "winner_ids": winner_ids,
                    "eligible_user_ids": eligible_user_ids,
                    "participant_count": len(users),
                    "forced_end": forced,
                }
            },
        )

        if winners:
            mentions = ", ".join(member.mention for member in winners)
            await message.channel.send(f"<:giveaway:1522331215976206446> **Розыгрыш завершён!** Победители: {mentions}")
        else:
            await message.channel.send("<:giveaway:1522331215976206446> **Розыгрыш завершён!** Подходящих участников не найдено.")

        return True

    @tasks.loop(seconds=15)
    async def finish_loop(self):
        now = utcnow()
        docs = list(
            giveaways_col.find(
                {
                    "type": "giveaway",
                    "status": "active",
                    "ends_at": {"$lte": now},
                }
            )
        )

        for doc in docs:
            try:
                await self.finish_giveaway(doc)
            except Exception:
                continue

    @finish_loop.before_loop
    async def before_finish_loop(self):
        await self.bot.wait_until_ready()

    @commands.group(
        name="giveaway",
        aliases=["giveaways", "gw", "gws"],
        invoke_without_command=True,
    )
    async def giveaway_group(
        self,
        ctx: commands.Context,
    ):
        embed = discord.Embed(
            title="<:giveaway:1522331215976206446> Меню розыгрышей",
            description=(
                "Укажите команду для управления розыгрышами:\n\n"
                "• `.gw cr` — Создать новый розыгрыш\n"
                "• `.gw end [ID]` — Завершить розыгрыш\n"
                "• `.gw rr [ID]` — Перевыбрать победителя (реролл)\n"
                "• `.gw del [ID]` — Удалить розыгрыш"
            ),
            color=config.EMBED_COLOR,
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @giveaway_group.command(name="create", aliases=["cr"])
    @check_access_decorator("giveaway")
    async def giveaway_create(
        self,
        ctx: commands.Context,
        *args: str,
    ):
        if not ctx.guild:
            await ctx.send(
                embed=make_error_embed(
                    "Ошибка",
                    "Команда работает только на сервере.",
                )
            )
            return

        if len(args) < 4:
            await ctx.send(
                embed=make_error_embed(
                    "Неверное использование",
                    (
                        "Использование:\n"
                        "`.gw cr [приз] [длительность] [победители] [время на получение]`\n\n"
                        "Пример:\n"
                        "`.gw cr 1000 Robux 7d 1 24h`"
                    ),
                )
            )
            return

        prize = " ".join(args[:-3]).strip()
        duration_text = args[-3]
        winners_text = args[-2]
        claim_time = args[-1]

        if not prize:
            await ctx.send(embed=make_error_embed("Ошибка", "Укажите приз."))
            return

        duration = parse_duration(duration_text)
        if duration is None:
            await ctx.send(
                embed=make_error_embed(
                    "Ошибка",
                    (
                        "Неверная длительность. "
                        "Используйте, например: `30m`, `12h`, `7d`, `2w`, `1mo`.\n"
                        "Максимальная длительность — 31 день."
                    ),
                )
            )
            return

        try:
            winners_count = int(winners_text)
            if winners_count < 1:
                raise ValueError
        except ValueError:
            await ctx.send(
                embed=make_error_embed(
                    "Ошибка",
                    "Количество победителей должно быть целым числом больше 0.",
                )
            )
            return

        view = GiveawaySetupView(
            self.bot,
            ctx,
            prize,
            duration_text,
            duration,
            winners_count,
            claim_time,
        )

        setup_message = await ctx.send(
            embed=view.setup_embed(),
            view=view,
        )
        view.setup_message = setup_message

    @giveaway_group.command(name="end")
    @check_access_decorator("giveaway")
    async def giveaway_end(
        self,
        ctx: commands.Context,
        message_id: str,
    ):
        if not ctx.guild:
            return

        try:
            message_id_int = int(message_id)
        except ValueError:
            await ctx.send(embed=make_error_embed("Ошибка", "ID сообщения должен быть числом."))
            return

        doc = giveaways_col.find_one(
            {
                "type": "giveaway",
                "guild_id": ctx.guild.id,
                "message_id": message_id_int,
                "status": "active",
            }
        )

        if not doc:
            await ctx.send(
                embed=make_error_embed(
                    "Розыгрыш не найден",
                    "Активный розыгрыш с таким ID не найден.",
                )
            )
            return

        await self.finish_giveaway(doc, forced=True)
        await ctx.send(
            embed=make_status_embed(
                "Розыгрыш завершён",
                f"Розыгрыш `{message_id_int}` был завершён досрочно.",
                "success",
            )
        )

    @giveaway_group.command(name="reroll", aliases=["rr"])
    @check_access_decorator("giveaway")
    async def giveaway_reroll(
        self,
        ctx: commands.Context,
        message_id: str,
    ):
        if not ctx.guild:
            return

        try:
            message_id_int = int(message_id)
        except ValueError:
            await ctx.send(embed=make_error_embed("Ошибка", "ID сообщения должен быть числом."))
            return

        doc = giveaways_col.find_one(
            {
                "type": "giveaway",
                "guild_id": ctx.guild.id,
                "message_id": message_id_int,
                "status": "ended",
            }
        )

        if not doc:
            await ctx.send(
                embed=make_error_embed(
                    "Розыгрыш не найден",
                    "Завершённый розыгрыш с таким ID не найден.",
                )
            )
            return

        eligible_ids = doc.get("eligible_user_ids", [])
        if not eligible_ids:
            await ctx.send(
                embed=make_error_embed(
                    "Ошибка реролла",
                    "Среди участников, успевших войти до конца розыгрыша, нет подходящих кандидатов.",
                )
            )
            return

        pool = []
        for uid in eligible_ids:
            member = ctx.guild.get_member(uid)
            if member:
                pool.append((member, self._weight(member, doc)))

        if not pool:
            await ctx.send(
                embed=make_error_embed(
                    "Ошибка реролла",
                    "Ни один из прошлых участников больше не найден на сервере.",
                )
            )
            return

        total_weight = sum(w for _, w in pool)
        roll = random.uniform(0, total_weight)
        current = 0
        new_winner = pool[-1][0]

        for member, weight in pool:
            current += weight
            if roll <= current:
                new_winner = member
                break

        message = await self._get_giveaway_message(doc)
        target_channel = message.channel if message else ctx.channel

        await target_channel.send(
            f"<:giveaway:1522331215976206446> Новый победитель розыгрыша **{doc['prize']}**: {new_winner.mention}!"
        )

    @giveaway_group.command(name="delete", aliases=["del"])
    @check_access_decorator("giveaway")
    async def giveaway_delete(
        self,
        ctx: commands.Context,
        message_id: str,
    ):
        if not ctx.guild:
            return

        try:
            message_id_int = int(message_id)
        except ValueError:
            await ctx.send(embed=make_error_embed("Ошибка", "ID сообщения должен быть числом."))
            return

        doc = giveaways_col.find_one(
            {
                "type": "giveaway",
                "guild_id": ctx.guild.id,
                "message_id": message_id_int,
            }
        )

        if not doc:
            await ctx.send(
                embed=make_error_embed(
                    "Розыгрыш не найден",
                    "Розыгрыш с таким ID не найден.",
                )
            )
            return

        message = await self._get_giveaway_message(doc)
        if message:
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        giveaways_col.delete_one({"_id": doc["_id"]})

        await ctx.send(
            embed=make_status_embed(
                "Розыгрыш удалён",
                f"Розыгрыш `{message_id_int}` был удалён.",
                "success",
            )
        )

    @commands.command(name="checktime", aliases=["ct"])
    @check_access_decorator("giveaway")
    async def check_time(
        self,
        ctx: commands.Context,
        giveaway_msg_id: str,
        user_msg_id: str,
    ):
        if not ctx.guild:
            return

        try:
            gw_id_int = int(giveaway_msg_id)
            usr_id_int = int(user_msg_id)
        except ValueError:
            await ctx.send(
                embed=make_error_embed("Ошибка", "ID сообщений должны быть числами.")
            )
            return

        doc = giveaways_col.find_one(
            {
                "type": "giveaway",
                "guild_id": ctx.guild.id,
                "message_id": gw_id_int,
            }
        )

        if not doc:
            await ctx.send(
                embed=make_error_embed(
                    "Розыгрыш не найден",
                    "Розыгрыш с указанным ID сообщения не найден в базе данных.",
                )
            )
            return

        try:
            user_msg = await ctx.channel.fetch_message(usr_id_int)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await ctx.send(
                embed=make_error_embed(
                    "Сообщение не найдено",
                    "Не удалось найти сообщение участника в текущем канале.",
                )
            )
            return

        ends_at = doc.get("ended_at") or doc["ends_at"]
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)

        claim_time_str = doc.get("claim_time", "—")
        claim_td = parse_duration(claim_time_str) or timedelta(0)

        deadline = ends_at + claim_td
        msg_created_at = user_msg.created_at

        embed = discord.Embed(
            title="<a:gifclock:1544347190984441858> Проверка времени ответа",
            color=config.EMBED_COLOR,
        )

        embed.add_field(
            name="Время завершения розыгрыша",
            value=f"<t:{int(ends_at.timestamp())}:f>",
            inline=False,
        )
        embed.add_field(
            name="Драйвер времени на получение",
            value=format_claim_time(claim_time_str),
            inline=False,
        )
        embed.add_field(
            name="Крайний срок ответа",
            value=f"<t:{int(deadline.timestamp())}:f>",
            inline=False,
        )
        embed.add_field(
            name="Время ответа игрока",
            value=f"<t:{int(msg_created_at.timestamp())}:f> ({user_msg.author.mention})",
            inline=False,
        )

        if msg_created_at <= deadline:
            diff = deadline - msg_created_at
            formatted_diff = format_timedelta(diff)
            embed.add_field(
                name="Результат",
                value=f"<:verify:1522329028420173976> **Игрок успел!** Ответил до дедлайна (запас {formatted_diff}).",
                inline=False,
            )
        else:
            diff = msg_created_at - deadline
            formatted_diff = format_timedelta(diff)
            embed.add_field(
                name="Результат",
                value=f"<a:alert:1544047350345891851> **Игрок опоздал!** Опоздание составило: **{formatted_diff}**.",
                inline=False,
            )

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))