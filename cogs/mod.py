import discord
from discord.ext import commands
from discord.ui import View, Select
import database
import utils
from utils import check_access_decorator, make_error_embed, make_status_embed, log_action, build_command_help_embed
import config

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

async def setup(bot):
    if "verbal_warnings" not in database.db.list_collection_names():
        database.db.create_collection("verbal_warnings")
    database.verbal_warnings_col = database.db["verbal_warnings"]
    database.verbal_warnings_col.create_index("verb_id", unique=True)
    database.verbal_warnings_col.create_index("user_id")
    await bot.add_cog(ModCog(bot))