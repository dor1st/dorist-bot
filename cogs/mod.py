import discord
from discord.ext import commands
from discord.ui import View, Select

import utils
from utils import check_access_decorator, make_error_embed, make_status_embed, log_action, build_command_help_embed

import database
import config

import re
from datetime import datetime, timedelta, timezone

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

async def send_punishment_dm(user, action_title: str, guild_name: str, reason: str, duration: str = None, case_id: int = None):
    """Отправка уведомления в личные сообщения участнику"""
    try:
        case_info = f" (Дело №{case_id})" if case_id else ""
        desc = f"Вы получили **{action_title}**{case_info} на сервере **{guild_name}**."
        embed = discord.Embed(
            title="Уведомление о наказании",
            description=desc,
            color=discord.Color.red()
        )
        embed.add_field(name="Причина", value=reason, inline=False)
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
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_status_embed("Успешно", f"Варн по делу №{self.warn_data.get('case_id')} успешно удален."),
            view=self
        )

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
        database.verbal_warnings_col.delete_one({"verb_id": self.verb_data.get("verb_id")})
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=make_status_embed("Успешно", f"Вербальный варн №{self.verb_data.get('verb_id')} успешно удален."),
            view=self
        )

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

        embed = discord.Embed(
            title=f"Вербальные варны участника {target.name}",
            color=config.EMBED_COLOR
        )
        
        for v in user_verbs:
            mod = ctx.guild.get_member(v.get("moderator_id"))
            mod_text = mod.mention if mod else f"<@{v.get('moderator_id')}>"
            embed.add_field(
                name=f"Верб №{v.get('verb_id')}",
                value=f"**Модератор:** {mod_text}\n**Причина:** {v.get('reason')}",
                inline=False
            )

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

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

        await send_punishment_dm(target, "Варн", ctx.guild.name, reason, case_id=case_id)

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

        await send_punishment_dm(target, "Мьют", ctx.guild.name, reason, duration=duration, case_id=case_id)

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
    async def unmute(self, ctx: commands.Context, member_id: int = None, *, reason: str = "Снятие мьюта"):
        if member_id is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("unmute"))

        target = ctx.guild.get_member(member_id)
        if not target:
            return await ctx.send(embed=make_error_embed("Ошибка", "Участник не найден на сервере."))

        try:
            await target.timeout(None, reason=f"[{ctx.author}] {reason}")
        except discord.Forbidden:
            return await ctx.send(embed=make_error_embed("Ошибка", "У бота недостаточно прав для снятия тайм-аута."))

        embed = discord.Embed(
            title="Мьют снят",
            description=f"**Участник:** {target.mention} (`{target.id}`)\n**Модератор:** {ctx.author.mention}\n**Причина:** {reason}",
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "unmute", embed)

    @commands.command(name="ban")
    @check_access_decorator("ban")
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

        await send_punishment_dm(target, "Бан", ctx.guild.name, reason, case_id=case_id)

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
        await log_action(ctx.guild, "ban", embed)

    @commands.command(name="unban")
    @check_access_decorator("unban")
    async def unban(self, ctx: commands.Context, member_id: int = None, *, reason: str = "Разбан"):
        if member_id is None:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("unban"))

        try:
            user = await self.bot.fetch_user(member_id)
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
        await log_action(ctx.guild, "unban", embed)

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

        embed = discord.Embed(
            title=f"История нарушений: {target.name}",
            color=config.EMBED_COLOR
        )
        for c in cases:
            mod = ctx.guild.get_member(c.get("moderator_id"))
            mod_text = mod.mention if mod else f"<@{c.get('moderator_id')}>"
            duration_text = f"\n**Длительность:** {c.get('duration')}" if c.get("duration") else ""
            
            ts = c.get("timestamp")
            time_str = f"\n**Дата:** <t:{int(ts.timestamp())}:f>" if isinstance(ts, datetime) else ""

            embed.add_field(
                name=f"{c.get('type')} (Дело №{c.get('case_id')})",
                value=f"**Модератор:** {mod_text}{time_str}\n**Причина:** {c.get('reason')}{duration_text}",
                inline=False
            )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="modstats")
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

        all_cases = list(database.cases_col.find({"user_id": target.id}))
        all_verbs = list(database.verbal_warnings_col.find({"user_id": target.id}))

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
            title=f"✨ Статистика: {target.name}",
            color=config.EMBED_COLOR
        )

        categories = [
            ("⚠️ Варнов", "Варн", all_cases),
            ("🔇 Мьютов", "Мьют", all_cases),
            ("🔨 Банов", "Бан", all_cases),
            ("💬 Верб. варнов", None, all_verbs)
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

    @commands.command(name="moderations")
    @check_access_decorator("moderations")
    async def moderations(self, ctx: commands.Context, moderator_id: int = None):
        target_id = moderator_id if moderator_id else ctx.author.id
        try:
            target = await self.bot.fetch_user(target_id)
        except discord.NotFound:
            return await ctx.send(embed=make_error_embed("Ошибка", "Модератор не найден."))

        cases = list(database.cases_col.find({"moderator_id": target.id}))
        verbs = list(database.verbal_warnings_col.find({"moderator_id": target.id}))

        if not cases and not verbs:
            return await ctx.send(embed=make_error_embed("Список пуст", f"Модератор {target.mention} ещё не выдавал наказаний."))

        embed = discord.Embed(
            title=f"Наказания, выданные модератором {target.name}",
            color=config.EMBED_COLOR
        )

        for c in cases:
            user = ctx.guild.get_member(c.get("user_id"))
            user_text = user.mention if user else f"<@{c.get('user_id')}>"
            duration_text = f" | **Длит.:** {c.get('duration')}" if c.get("duration") else ""
            
            ts = c.get("timestamp")
            time_str = f" | **Дата:** <t:{int(ts.timestamp())}:f>" if isinstance(ts, datetime) else ""

            embed.add_field(
                name=f"{c.get('type')} (Дело №{c.get('case_id')})",
                value=f"**Нарушитель:** {user_text}{time_str}\n**Причина:** {c.get('reason')}{duration_text}",
                inline=False
            )

        for v in verbs:
            user = ctx.guild.get_member(v.get("user_id"))
            user_text = user.mention if user else f"<@{v.get('user_id')}>"
            embed.add_field(
                name=f"Вербальный варн №{v.get('verb_id')}",
                value=f"**Нарушитель:** {user_text}\n**Причина:** {v.get('reason')}",
                inline=False
            )

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

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
    async def addcase(
        self, 
        ctx: commands.Context, 
        user_id: int = None, 
        mod_id: int = None, 
        timestamp_val: int = None, 
        punishment_type: str = None, 
        *, 
        rest: str = None
    ):
        if not user_id or not mod_id or not timestamp_val or not punishment_type or not rest:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=build_command_help_embed("addcase"))

        p_type = punishment_type.lower().capitalize()
        allowed_types = ["Мьют", "Варн", "Бан"]
        if p_type not in allowed_types:
            return await ctx.send(embed=make_error_embed("Ошибка", "Нарушение не найдено. Допустимы только категории: `мьют`, `варн`, `бан`."))

        try:
            issue_date = datetime.fromtimestamp(timestamp_val, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return await ctx.send(embed=make_error_embed("Ошибка", "Указан некорректный UNIX timestamp."))

        duration = None
        reason = rest

        if p_type == "Мьют":
            parts = rest.split(" ", 1)
            if parse_duration(parts[0]):
                duration = parts[0]
                reason = parts[1] if len(parts) > 1 else "Не указана"

        case_id = database.get_next_sequence_value("cases")
        case_doc = {
            "case_id": case_id,
            "user_id": user_id,
            "moderator_id": mod_id,
            "type": p_type,
            "reason": reason,
            "duration": duration,
            "timestamp": issue_date
        }
        database.cases_col.insert_one(case_doc)

        ts_formatted = f"<t:{timestamp_val}:f>"
        embed = discord.Embed(
            title="Дело импортировано",
            description=(
                f"**Дело №:** `{case_id}`\n"
                f"**Нарушитель:** <@{user_id}>\n"
                f"**Модератор:** <@{mod_id}>\n"
                f"**Тип:** {p_type}\n"
                f"**Дата и время:** {ts_formatted}\n"
                f"**Причина:** {reason}"
            ),
            color=config.EMBED_COLOR
        )
        if duration:
            embed.add_field(name="Длительность", value=duration)
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

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