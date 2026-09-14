import discord
import math
from discord.ext import commands
from discord.ui import View, Select

import utils
from utils import check_access_decorator, make_error_embed, make_status_embed, log_action, log_mod_action, build_command_help_embed

import database
import config

import re
from datetime import datetime, timedelta, timezone

SENIOR_MOD_ROLE_ID = config.SENIOR_MOD_ROLE_ID if hasattr(config, "SENIOR_MOD_ROLE_ID") else 1501500735316164710
LOGS_PER_PAGE = config.LOGS_PER_PAGE if hasattr(config, "LOGS_PER_PAGE") else 3
ALERT_EMOJI = config.ALERT_EMOJI if hasattr(config, "ALERT_EMOJI") else "<a:alert:1544047350345891851>"

def parse_duration(time_str: str) -> timedelta | None:
    """Парсер длительности вида 10m, 2h, 1d, 7d"""
    if not time_str:
        return None
    match = re.match(r"^(\d+)([smhd])$", time_str.lower())
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    units = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
    return timedelta(**{units[unit]: val})

def check_senior_mod():
    async def predicate(ctx):
        if not isinstance(ctx.author, discord.Member):
            return False
        if ctx.author.id == config.OWNER_ID or ctx.author.guild_permissions.administrator:
            return True
        role = ctx.guild.get_role(SENIOR_MOD_ROLE_ID)
        if role and role in ctx.author.roles:
            return True
        raise commands.CheckFailure("Эта команда доступна только старшим модераторам.")
    return commands.check(predicate)

async def send_punishment_dm(user, action_title: str, guild_name: str, reason: str, duration: str = None):
    """Отправка уведомления в личные сообщения участнику"""
    try:
        desc = f"Вы получили **{action_title}** на сервере **{guild_name}**."
        embed = discord.Embed(
            title="Уведомление о наказании",
            description=desc,
            color=config.EMBED_COLOR
        )
        if duration:
            embed.add_field(name="Длительность", value=duration, inline=False)
        embed.set_footer(text=f"Сообщение от сервера: {guild_name}")
        await user.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass

class DeleteWarnSelect(Select):
    def __init__(self, warn_list):
        options = []
        for warn in warn_list:
            case_id = warn.get("case_id")
            reason = warn.get("reason", "Без причины")
            truncated_reason = reason if len(reason) <= 90 else reason[:87] + "..."
            options.append(
                discord.SelectOption(
                    label=f"Варн (Дело №{case_id})",
                    description=truncated_reason,
                    value=str(case_id)
                )
            )
        super().__init__(placeholder="Выберите варн для удаления...", min_values=1, max_values=1, options=options)
        self.warn_list = warn_list

    async def callback(self, interaction: discord.Interaction):
        selected_case_id = int(self.values[0])
        selected_warn = next((w for w in self.warn_list if w.get("case_id") == selected_case_id), None)
        
        if not selected_warn:
            await interaction.response.send_message(embed=make_error_embed("Ошибка", "Выбранное предупреждение не найдено."), ephemeral=True)
            return

        view = DeleteWarnConfirmView(selected_warn)
        await interaction.response.send_message(
            embed=make_status_embed(
                "Подтверждение удаления",
                f"Вы уверены, что хотите удалить предупреждение?\n\n**Дело №:** `{selected_warn.get('case_id')}`\n**Причина:** {selected_warn.get('reason')}"
            ),
            view=view,
            ephemeral=True
        )

class VerbalsView(View):
    """Пагинация для списка вербальных варнов участника."""

    def __init__(self, target, verbs: list, guild: discord.Guild, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.target = target
        self.verbs = verbs
        self.guild = guild
        self.current_page = 0
        self.total_pages = math.ceil(len(verbs) / LOGS_PER_PAGE)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def build_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"Вербальные варны участника {self.target.name}",
            color=config.EMBED_COLOR,
        )

        start_idx = self.current_page * LOGS_PER_PAGE
        end_idx = start_idx + LOGS_PER_PAGE
        page_verbs = self.verbs[start_idx:end_idx]

        for v in page_verbs:
            mod = self.guild.get_member(v.get("moderator_id"))
            mod_text = mod.mention if mod else f"<@{v.get('moderator_id')}>"
            embed.add_field(
                name=f"Верб №{v.get('verb_id')}",
                value=f"**Модератор:** {mod_text}\n**Причина:** {v.get('reason')}",
                inline=False,
            )

        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.verbs)} варнов) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(
        emoji="<:darkleft:1543989641751957565>",
        style=discord.ButtonStyle.secondary,
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
        emoji="<:darkright:1543990036129783948>",
        style=discord.ButtonStyle.secondary,
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


class ModLogsView(View):
    """Пагинация для истории нарушений участника."""

    def __init__(self, target, cases: list, guild: discord.Guild, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.target = target
        self.cases = cases
        self.guild = guild
        self.current_page = 0
        self.total_pages = math.ceil(len(cases) / LOGS_PER_PAGE)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def build_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"История нарушений: {self.target.name}",
            color=config.EMBED_COLOR,
        )

        start_idx = self.current_page * LOGS_PER_PAGE
        end_idx = start_idx + LOGS_PER_PAGE
        page_cases = self.cases[start_idx:end_idx]

        for c in page_cases:
            mod = self.guild.get_member(c.get("moderator_id"))
            mod_text = mod.mention if mod else f"<@{c.get('moderator_id')}>"
            duration_text = (
                f"\n**Длительность:** {c.get('duration')}"
                if c.get("duration")
                else ""
            )

            ts = c.get("timestamp")
            time_str = (
                f"\n**Дата:** <t:{int(ts.timestamp())}:f>"
                if isinstance(ts, datetime)
                else ""
            )

            embed.add_field(
                name=f"{c.get('type')} (Дело №{c.get('case_id')})",
                value=f"**Модератор:** {mod_text}{time_str}\n**Причина:** {c.get('reason')}{duration_text}",
                inline=False,
            )

        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.cases)} нарушений) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(
        emoji="<:darkleft:1543989641751957565>",
        style=discord.ButtonStyle.secondary,
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
        emoji="<:darkright:1543990036129783948>",
        style=discord.ButtonStyle.secondary,
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

class ModerationsView(View):
    """Пагинация для выданных модератором наказаний (cases + verbs)."""

    def __init__(self, target: discord.User, items: list, guild: discord.Guild, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.target = target
        # Сортируем наказания по убыванию даты (свежие вверху)
        self.items = sorted(
            items,
            key=lambda x: x.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        self.guild = guild
        self.current_page = 0
        self.total_pages = math.ceil(len(self.items) / LOGS_PER_PAGE)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def build_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"Наказания, выданные модератором {self.target.name}",
            color=config.EMBED_COLOR,
        )

        start_idx = self.current_page * LOGS_PER_PAGE
        end_idx = start_idx + LOGS_PER_PAGE
        page_items = self.items[start_idx:end_idx]

        for item in page_items:
            user = self.guild.get_member(item.get("user_id"))
            user_text = user.mention if user else f"<@{item.get('user_id')}>"

            ts = item.get("timestamp")
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                time_str = f" | **Дата:** <t:{int(ts.timestamp())}:f>"
            else:
                time_str = ""

            if "case_id" in item:
                duration_text = (
                    f" | **Длительность:** {item.get('duration')}"
                    if item.get("duration")
                    else ""
                )
                embed.add_field(
                    name=f"{item.get('type')} (Дело №{item.get('case_id')})",
                    value=f"**Нарушитель:** {user_text}{time_str}\n**Причина:** {item.get('reason')}{duration_text}",
                    inline=False,
                )
            else:
                embed.add_field(
                    name=f"Вербальный варн №{item.get('verb_id')}",
                    value=f"**Нарушитель:** {user_text}{time_str}\n**Причина:** {item.get('reason')}",
                    inline=False,
                )

        embed.set_footer(
            text=f"Страница {self.current_page + 1}/{self.total_pages} ({len(self.items)} выданных) • {config.FOOTER_TEXT}"
        )
        return embed

    @discord.ui.button(
        emoji="<:darkleft:1543989641751957565>",
        style=discord.ButtonStyle.secondary,
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
        emoji="<:darkright:1543990036129783948>",
        style=discord.ButtonStyle.secondary,
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

class DeleteWarnView(View):
    def __init__(self, warn_list):
        super().__init__(timeout=60)
        self.add_item(DeleteWarnSelect(warn_list))

class DeleteWarnConfirmView(View):
    def __init__(self, warn_data):
        super().__init__(timeout=60)
        self.warn_data = warn_data

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        database.cases_col.delete_one({"case_id": self.warn_data.get("case_id")})
        
        # Уведомление в ЛС
        user_id = self.warn_data.get("user_id")
        user = interaction.guild.get_member(user_id)
        if user:
            await send_punishment_dm(user, "Снятие варна", interaction.guild.name, "Ваше предупреждение было удалено модератором.")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_status_embed("Успешно", f"Варн по делу №{self.warn_data.get('case_id')} успешно удален."),
            view=self
        )
        
        log_embed = discord.Embed(
            title="Варн удален",
            description=f"**Модератор:** {interaction.user.mention}\n**Дело №:** `{self.warn_data.get('case_id')}`",
            color=config.EMBED_COLOR
        )
        await log_mod_action(interaction.guild, "delwarn", log_embed)

    @discord.ui.button(label="Отменить", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_status_embed("Отменено", "Действие отменено."),
            view=self
        )

class DeleteVerbSelect(Select):
    def __init__(self, verb_list):
        options = []
        for verb in verb_list:
            verb_id = verb.get("verb_id")
            reason = verb.get("reason", "Без причины")
            truncated_reason = reason if len(reason) <= 90 else reason[:87] + "..."
            options.append(
                discord.SelectOption(
                    label=f"Вербальный варн №{verb_id}",
                    description=truncated_reason,
                    value=str(verb_id)
                )
            )
        super().__init__(placeholder="Выберите вербальный варн для удаления...", min_values=1, max_values=1, options=options)
        self.verb_list = verb_list

    async def callback(self, interaction: discord.Interaction):
        selected_verb_id = int(self.values[0])
        selected_verb = next((v for v in self.verb_list if v.get("verb_id") == selected_verb_id), None)
        
        if not selected_verb:
            await interaction.response.send_message(embed=make_error_embed("Ошибка", "Выбранный вербальный варн не найден."), ephemeral=True)
            return

        view = DeleteVerbConfirmView(selected_verb)
        await interaction.response.send_message(
            embed=make_status_embed(
                "Подтверждение удаления",
                f"Вы уверены, что хотите удалить вербальный варн?\n\n**Номер:** `{selected_verb.get('verb_id')}`\n**Причина:** {selected_verb.get('reason')}"
            ),
            view=view,
            ephemeral=True
        )

class DeleteVerbView(View):
    def __init__(self, verb_list):
        super().__init__(timeout=60)
        self.add_item(DeleteVerbSelect(verb_list))

class DeleteVerbConfirmView(View):
    def __init__(self, verb_data):
        super().__init__(timeout=60)
        self.verb_data = verb_data

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        database.cases_col.delete_one({"case_id": self.warn_data.get("case_id")})
        
        # Уведомление в ЛС
        user_id = self.warn_data.get("user_id")
        user = interaction.guild.get_member(user_id)
        if user:
            await send_punishment_dm(user, "Снятие варна", interaction.guild.name, "Ваше предупреждение было удалено модератором.")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_status_embed("Успешно", f"Варн по делу №{self.warn_data.get('case_id')} успешно удален."),
            view=self
        )
        
        log_embed = discord.Embed(
            title="Варн удален",
            description=f"**Модератор:** {interaction.user.mention}\n**Дело №:** `{self.warn_data.get('case_id')}`",
            color=config.EMBED_COLOR
        )
        await log_mod_action(interaction.guild, "delwarn", log_embed)

    @discord.ui.button(label="Отменить", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_status_embed("Отменено", "Действие отменено."),
            view=self
        )

class ModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="verbalwarn", aliases=["verb"])
    @check_access_decorator("verbalwarn")
    async def verbalwarn(self, ctx: commands.Context, member_id: int = None, *, reason: str = None):
        if member_id is None or reason is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("verbalwarn"))

        target = ctx.guild.get_member(member_id)
        if not target:
            try:
                target = await self.bot.fetch_user(member_id)
            except discord.NotFound:
                await ctx.send(embed=make_error_embed("Ошибка", "Участник с таким ID не найден."))
                return

        verb_id = database.get_next_sequence_value("verbal_warns")
        
        warn_doc = {
            "verb_id": verb_id,
            "user_id": target.id,
            "moderator_id": ctx.author.id,
            "reason": reason
        }
        
        database.verbal_warnings_col.insert_one(warn_doc)

        embed = discord.Embed(
            title="Вербальное предупреждение выдано",
            description=f"**Участник:** {target.mention} (`{target.id}`)\n**Модератор:** {ctx.author.mention}\n**Причина:** {reason}\n**ID варна:** `{verb_id}`",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "verbalwarn", embed)

    @commands.command(name="verbals", aliases=["verbs"])
    @check_access_decorator("verbals")
    async def verbals(self, ctx: commands.Context, member_id: int = None):
        if member_id is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("verbals"))

        target = ctx.guild.get_member(member_id)
        if not target:
            try:
                target = await self.bot.fetch_user(member_id)
            except discord.NotFound:
                await ctx.send(embed=make_error_embed("Ошибка", "Участник с таким ID не найден."))
                return

        user_verbs = list(database.verbal_warnings_col.find({"user_id": target.id}))

        if not user_verbs:
            await ctx.send(embed=make_error_embed("Список пуст", f"У участника {target.mention} нет вербальных варнов."))
            return

        view = VerbalsView(target=target, verbs=user_verbs, guild=ctx.guild)
        embed = view.build_page_embed()

        if len(user_verbs) <= LOGS_PER_PAGE:
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="deleteverb")
    @check_access_decorator("deleteverb")
    async def deleteverb(self, ctx: commands.Context, member_id: int = None):
        if member_id is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("deleteverb"))

        user_verbs = list(database.verbal_warnings_col.find({"user_id": member_id}))

        if not user_verbs:
            await ctx.send(embed=make_error_embed("Ошибка", "У данного участника нет вербальных варнов."))
            return

        view = DeleteVerbView(user_verbs)
        await ctx.send(
            embed=make_status_embed("Управление вербальными варнами", "Выберите нужный вербальный варн из выпадающего списка ниже:"),
            view=view
        )

    @commands.command(name="warn")
    @check_access_decorator("warn")
    async def warn(self, ctx: commands.Context, member_id: int = None, *, reason: str = None):
        if member_id is None or reason is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("warn"))

        target = ctx.guild.get_member(member_id)
        if not target:
            try:
                target = await self.bot.fetch_user(member_id)
            except discord.NotFound:
                return await ctx.send(embed=make_error_embed("Ошибка", "Участник с таким ID не найден."))

        case_id = database.get_next_sequence_value("cases")
        case_doc = {
            "case_id": case_id,
            "user_id": target.id,
            "moderator_id": ctx.author.id,
            "type": "Варн",
            "reason": reason,
            "duration": None,
            "timestamp": datetime.now(timezone.utc)
        }
        database.cases_col.insert_one(case_doc)

        await send_punishment_dm(target, "Варн", ctx.guild.name, reason)

        embed = discord.Embed(
            title="Выдано предупреждение",
            description=f"**Участник:** {target.mention} (`{target.id}`)\n**Модератор:** {ctx.author.mention}\n**Причина:** {reason}\n**Дело №:** `{case_id}`",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "warn", embed)

    @commands.command(name="delwarn")
    @check_access_decorator("delwarn")
    async def delwarn(self, ctx: commands.Context, member_id: int = None):
        if member_id is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("delwarn"))

        user_warns = list(database.cases_col.find({"user_id": member_id, "type": "Варн"}))
        if not user_warns:
            return await ctx.send(embed=make_error_embed("Ошибка", "У данного участника нет активных варнов."))

        view = DeleteWarnView(user_warns)
        await ctx.send(
            embed=make_status_embed("Управление предупреждениями", "Выберите нужный варн для удаления:"),
            view=view
        )

    @commands.command(name="mute")
    @check_access_decorator("mute")
    async def mute(self, ctx: commands.Context, member_id: int = None, duration: str = None, *, reason: str = None):
        if member_id is None or duration is None or reason is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("mute"))

        target = ctx.guild.get_member(member_id)
        if not target:
            return await ctx.send(embed=make_error_embed("Ошибка", "Участник не найден на сервере."))

        td = parse_duration(duration)
        if not td:
            return await ctx.send(embed=make_error_embed("Ошибка", "Неверный формат длительности (примеры: 10m, 2h, 1d)."))

        try:
            await target.timeout(td, reason=f"[{ctx.author}] {reason}")
        except discord.Forbidden:
            return await ctx.send(embed=make_error_embed("Ошибка", "У бота недостаточно прав для выдачи тайм-аута."))

        case_id = database.get_next_sequence_value("cases")
        case_doc = {
            "case_id": case_id,
            "user_id": target.id,
            "moderator_id": ctx.author.id,
            "type": "Мьют",
            "reason": reason,
            "duration": duration,
            "timestamp": datetime.now(timezone.utc)
        }
        database.cases_col.insert_one(case_doc)

        await send_punishment_dm(target, "Мьют", ctx.guild.name, reason, duration=duration)

        embed = discord.Embed(
            title="Участник отправлен в мьют",
            description=f"**Участник:** {target.mention} (`{target.id}`)\n**Модератор:** {ctx.author.mention}\n**Длительность:** {duration}\n**Причина:** {reason}\n**Дело №:** `{case_id}`",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "mute", embed)

    @commands.command(name="unmute")
    @check_access_decorator("unmute")
    async def unmute(self, ctx: commands.Context, member_id: int = None, *, reason: str = None): # Убрали дефолтную причину
        if member_id is None or reason is None: # Причина теперь обязательна
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("unmute"))

        target = ctx.guild.get_member(member_id)
        if not target:
            return await ctx.send(embed=make_error_embed("Ошибка", "Участник не найден на сервере."))

        try:
            await target.timeout(None, reason=f"[{ctx.author}] {reason}")
        except discord.Forbidden:
            return await ctx.send(embed=make_error_embed("Ошибка", "У бота недостаточно прав для снятия тайм-аута."))

        # Отправляем в ЛС уведомление
        await send_punishment_dm(target, "Снятие мьюта", ctx.guild.name, reason)

        embed = discord.Embed(
            title="Мьют снят",
            description=f"**Участник:** {target.mention} (`{target.id}`)\n**Модератор:** {ctx.author.mention}\n**Причина:** {reason}",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_mod_action(ctx.guild, "unmute", embed)

    @commands.command(name="ban")
    @check_senior_mod()
    async def ban(self, ctx: commands.Context, member_id: int = None, *, reason: str = None):
        if member_id is None or reason is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("ban"))

        first_word = reason.split()[0]
        if parse_duration(first_word):
            return await ctx.send(embed=make_error_embed("Ошибка", "Баны выдаются навсегда! Указание длительности запрещено."))

        target = ctx.guild.get_member(member_id)
        if not target:
            try:
                target = await self.bot.fetch_user(member_id)
            except discord.NotFound:
                return await ctx.send(embed=make_error_embed("Ошибка", "Участник с таким ID не найден."))

        case_id = database.get_next_sequence_value("cases")
        case_doc = {
            "case_id": case_id,
            "user_id": target.id,
            "moderator_id": ctx.author.id,
            "type": "Бан",
            "reason": reason,
            "duration": "Навсегда",
            "timestamp": datetime.now(timezone.utc)
        }

        await send_punishment_dm(target, "Бан", ctx.guild.name, reason)
        
        try:
            await ctx.guild.ban(target, reason=f"[{ctx.author}] {reason}")
        except discord.Forbidden:
            return await ctx.send(embed=make_error_embed("Ошибка", "У бота недостаточно прав для бана данного пользователя."))

        database.cases_col.insert_one(case_doc)

        embed = discord.Embed(
            title="Участник забанен",
            description=f"**Участник:** {target.mention if isinstance(target, discord.Member) else target.name} (`{target.id}`)\n**Модератор:** {ctx.author.mention}\n**Причина:** {reason}\n**Дело №:** `{case_id}`",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_mod_action(ctx.guild, "ban", embed)

    @commands.command(name="unban")
    @check_senior_mod()
    async def unban(self, ctx: commands.Context, member_id: int = None, *, reason: str = "Разбан"):
        if member_id is None or reason is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("unban"))

        try:
            user = await self.bot.fetch_user(member_id)
            
            # Уведомление в ЛС
            await send_punishment_dm(user, "Разбан", ctx.guild.name, reason)
            
            await ctx.guild.unban(user, reason=f"[{ctx.author}] {reason}")
        except discord.NotFound:
            return await ctx.send(embed=make_error_embed("Ошибка", "Пользователь с таким ID не найден."))
        except discord.HTTPException:
            return await ctx.send(embed=make_error_embed("Ошибка", "Не удалось разбанить пользователя. Проверьте, находится ли он в бане."))

        embed = discord.Embed(
            title="Участник разбанен",
            description=f"**Участник:** {user.mention} (`{user.id}`)\n**Модератор:** {ctx.author.mention}\n**Причина:** {reason}",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_mod_action(ctx.guild, "unban", embed)

    @commands.command(name="modlogs")
    @check_access_decorator("modlogs")
    async def modlogs(self, ctx: commands.Context, member_id: int = None):
        target_id = member_id if member_id else ctx.author.id
        try:
            target = await self.bot.fetch_user(target_id)
        except discord.NotFound:
            return await ctx.send(embed=make_error_embed("Ошибка", "Участник не найден."))

        cases = list(database.cases_col.find({"user_id": target.id}))
        if not cases:
            return await ctx.send(embed=make_error_embed("Список пуст", f"У участника {target.mention} нет зафиксированных нарушений."))

        view = ModLogsView(target=target, cases=cases, guild=ctx.guild)
        embed = view.build_page_embed()

        if len(cases) <= LOGS_PER_PAGE:
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="modstats", aliases=["ms"])
    @check_access_decorator("modstats")
    async def modstats(self, ctx: commands.Context, member_id: int = None):
        target_id = member_id if member_id else ctx.author.id
        try:
            target = await self.bot.fetch_user(target_id)
        except discord.NotFound:
            return await ctx.send(embed=make_error_embed("Ошибка", "Участник не найден."))

        now = datetime.now(timezone.utc)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        all_cases = list(database.cases_col.find({"moderator_id": target.id}))
        all_verbs = list(database.verbal_warnings_col.find({"moderator_id": target.id}))

        def count_items(items, item_type=None, days=None):
            cnt = 0
            for item in items:
                if item_type and item.get("type") != item_type:
                    continue
                ts = item.get("timestamp")
                if ts and days:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < days:
                        continue
                cnt += 1
            return cnt

        embed = discord.Embed(
            title=f"<:sparkles:1522342290494849034> Статистика: {target.name}",
            color=config.EMBED_COLORs
        )

        categories = [
            (f"{ALERT_EMOJI} Варнов", "Варн", all_cases),
            ("<:timeout:1549111000437882961> Мьютов", "Мьют", all_cases),
            ("<:ban:1549111135742070926> Банов", "Бан", all_cases),
            ("<:warn:1549111094121992322> Верб. варнов", None, all_verbs)
        ]

        for label, t_type, source in categories:
            c7 = count_items(source, t_type, d7)
            c30 = count_items(source, t_type, d30)
            c_all = count_items(source, t_type, None)

            embed.add_field(name=f"{label} (7 дн.)", value=f"**{c7}**", inline=True)
            embed.add_field(name=f"{label} (30 дн.)", value=f"**{c30}**", inline=True)
            embed.add_field(name=f"{label} (Все время)", value=f"**{c_all}**", inline=True)

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="moderations", aliases=["moders"])
    @check_access_decorator("moderations")
    async def moderations(self, ctx: commands.Context, target: discord.User = None):
        target = target or ctx.author

        cases = list(database.cases_col.find({"moderator_id": target.id}))
        verbs = list(database.verbal_warnings_col.find({"moderator_id": target.id}))

        if not cases and not verbs:
            return await ctx.send(
                embed=make_error_embed(
                    "Список пуст", 
                    f"Модератор {target.mention} ещё не выдавал наказаний."
                )
            )

        all_items = cases + verbs

        view = ModerationsView(target=target, items=all_items, guild=ctx.guild)
        embed = view.build_page_embed()

        if len(all_items) <= LOGS_PER_PAGE:
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed, view=view)

    @commands.command(name="delcase")
    @check_access_decorator("delcase")
    async def delcase(self, ctx: commands.Context, case_id: int = None):
        if case_id is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("delcase"))

        case = database.cases_col.find_one({"case_id": case_id})
        if not case:
            return await ctx.send(embed=make_error_embed("Ошибка", f"Дело №{case_id} не найдено."))

        database.cases_col.delete_one({"case_id": case_id})
        await ctx.send(embed=make_status_embed("Успешно", f"Дело №{case_id} былo успешно удалено из базы данных."))

    @commands.command(name="addcase")
    @check_access_decorator("addcase")
    async def addcase(self, ctx: commands.Context, message_id: int = None):
        LOG_CHANNEL_ID = 1466886479396737024
        target_msg = None

        if message_id is None:
            if ctx.message.reference and ctx.message.reference.message_id:
                message_id = ctx.message.reference.message_id
                ref_channel_id = ctx.message.reference.channel_id
                try:
                    ref_channel = ctx.guild.get_channel(ref_channel_id) or await self.bot.fetch_channel(ref_channel_id)
                    target_msg = await ref_channel.fetch_message(message_id)
                except (discord.NotFound, discord.HTTPException):
                    pass
            else:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(embed=build_command_help_embed("addcase"))

        # Поиск сообщения по ID: сначала в канале наказаний, затем в текущем
        if not target_msg and message_id:
            log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
            if not log_channel:
                try:
                    log_channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
                except (discord.NotFound, discord.HTTPException):
                    log_channel = None

            if log_channel:
                try:
                    target_msg = await log_channel.fetch_message(message_id)
                except (discord.NotFound, discord.HTTPException):
                    pass

            if not target_msg:
                try:
                    target_msg = await ctx.channel.fetch_message(message_id)
                except (discord.NotFound, discord.HTTPException):
                    pass

        if not target_msg:
            return await ctx.send(embed=make_error_embed("Ошибка", "Сообщение с таким ID не найдено ни в канале наказаний, ни в текущем канале."))

        content = target_msg.content.strip()
        if not content:
            return await ctx.send(embed=make_error_embed("Ошибка", "Выбранное сообщение не содержит текста."))

        parts = content.split()
        if len(parts) < 3:
            return await ctx.send(embed=make_error_embed("Ошибка", "Не удалось распознать формат команды в сообщении."))

        cmd_raw = parts[0].lower()
        cmd_clean = re.sub(r"^[^\w]+", "", cmd_raw)

        type_map = {
            "warn": "Варн",
            "warning": "Варн",
            "mute": "Мьют",
            "timeout": "Мьют",
            "ban": "Бан"
        }

        p_type = type_map.get(cmd_clean)
        if not p_type:
            return await ctx.send(embed=make_error_embed("Ошибка", f"Не удалось определить тип наказания из команды `{parts[0]}`. Допустимы команды: warn, mute, ban."))

        user_id_match = re.search(r"\d+", parts[1])
        if not user_id_match:
            return await ctx.send(embed=make_error_embed("Ошибка", "Не удалось найти ID нарушителя в сообщении."))
        user_id = int(user_id_match.group(0))

        rest_parts = parts[2:]
        duration = None

        if p_type == "Мьют" and rest_parts:
            if parse_duration(rest_parts[0]):
                duration = rest_parts[0]
                rest_parts = rest_parts[1:]

        reason = " ".join(rest_parts) if rest_parts else "Причина не указана"
        issue_date = target_msg.created_at
        case_id = database.get_next_sequence_value("cases")

        case_doc = {
            "case_id": case_id,
            "user_id": user_id,
            "moderator_id": target_msg.author.id,
            "type": p_type,
            "reason": reason,
            "duration": duration,
            "timestamp": issue_date
        }
        database.cases_col.insert_one(case_doc)

        ts_int = int(issue_date.timestamp())
        embed = discord.Embed(
            title="Дело импортировано",
            description=(
                f"**Дело №:** `{case_id}`\n"
                f"**Нарушитель:** <@{user_id}>\n"
                f"**Модератор:** {target_msg.author.mention}\n"
                f"**Тип:** {p_type}\n"
                f"**Дата и время:** <t:{ts_int}:f>\n"
                f"**Причина:** {reason}"
            ),
            color=config.EMBED_COLOR
        )
        if duration:
            embed.add_field(name="Длительность", value=duration)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

        log_embed = discord.Embed(
            title="Дело удалено",
            description=f"**Модератор:** {ctx.author.mention}\n**Дело №:** `{case_id}`",
            color=config.EMBED_COLOR
        )
        await log_mod_action(ctx.guild, "delcase", log_embed)

async def setup(bot):
    if "verbal_warnings" not in database.db.list_collection_names():
        database.db.create_collection("verbal_warnings")
    database.verbal_warnings_col = database.db["verbal_warnings"]
    database.verbal_warnings_col.create_index("verb_id", unique=True)
    database.verbal_warnings_col.create_index("user_id")

    if "cases" not in database.db.list_collection_names():
        database.db.create_collection("cases")
    database.cases_col = database.db["cases"]
    database.cases_col.create_index("case_id", unique=True)
    database.cases_col.create_index("user_id")
    database.cases_col.create_index("moderator_id")

    await bot.add_cog(ModCog(bot))