import discord
from discord.ext import commands

import config
from database import tickets_col, deleted_tickets_col
from utils import check_access_decorator, make_error_embed, make_status_embed, is_owner_user, log_action


class ConfigSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Сервер", description="Цвет embed, Footer, Итоги, Доступ", emoji="<:buildercap:1541377896189534238>", value="server"),
            discord.SelectOption(label="Тикеты", description="Настройка тикетов и канала логов", emoji="<:ticket:1522343287816716379>", value="tickets"),
        ]
        super().__init__(placeholder="Выберите категорию настроек...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = discord.Embed(color=config.EMBED_COLOR)

        if category == "server":
            embed.title = "<:buildercap:1541377896189534238> Настройки сервера"
            embed.description = (
                f"**Цвет Embed:** `{config.CONFIG.get('embed_color')}`\n"
                f"**Footer Текст:** `{config.CONFIG.get('footer_text')}`\n\n"
                f"**Канал считалки:** <#{config.CONFIG.get('counting_channel_id')}> \n"
                f"**Канал бампа:** <#{config.CONFIG.get('bump_channel_id')}>\n\n"
                f"**Права и доступ:** Управляются через конфиг."
            )
        elif category == "tickets":
            log_chan = config.CONFIG.get('log_channel_id')
            toggles = config.CONFIG.get("log_toggles", {})
            toggles_fmt = "\n".join([f"`{cmd}`: {'<:verify:1522329028420173976>' if val else '<:imcrine:1543711667647418381>'}" for cmd, val in toggles.items()])
            embed.title = "<:ticket:1522343287816716379> Настройки тикетов"
            embed.description = (
                f"**Канал логов тикетов:** <#{log_chan}>\n\n"
                f"**Логирование команд:**\n{toggles_fmt}"
            )

        embed.set_footer(text=config.FOOTER_TEXT)
        view = ConfigCategoryView(interaction.user.id, self.view)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigMainView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.add_item(ConfigSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            embed = make_error_embed("Отказ в доступе", "Вы не можете управлять меню конфигурации.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True


class ConfigCategoryView(discord.ui.View):
    def __init__(self, author_id: int, parent_view: ConfigMainView):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.parent_view = parent_view

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            embed = make_error_embed("Отказ в доступе", "Вы не можете управлять меню конфигурации.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Назад", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_config_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


def build_config_embed() -> discord.Embed:
    embed = discord.Embed(
        title="<:buildercap:1541377896189534238> Настройки бота",
        description="Выберите категорию в выпадающем меню ниже для перехода к настройкам.",
        color=config.EMBED_COLOR
    )
    embed.add_field(name="<:buildercap:1541377896189534238> Сервер", value="Настройка цвета, футера, каналов итогов и прав доступа.", inline=False)
    embed.add_field(name="<:ticket:1522343287816716379> Тикеты", value="Настройка тикетов и каналов логирования.", inline=False)
    embed.set_footer(text=config.FOOTER_TEXT)
    return embed


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="deletelog", aliases=["del"])
    @check_access_decorator("deletelog")
    async def deletelog_cmd(self, ctx: commands.Context, log_id: int = None):
        if log_id is None:
            embed = make_error_embed("Недостаточно аргументов", config.COMMAND_USAGE_HELP["deletelog"])
            return await ctx.send(embed=embed)

        res = tickets_col.delete_one({"_id": log_id})
        if res.deleted_count > 0:
            embed = make_status_embed("Удаление лога", f"Лог тикета **№{log_id}** успешно удален из базы данных.", "success")
            await ctx.send(embed=embed)
            await log_action(ctx.guild, "deletelog", embed)
        else:
            embed = make_error_embed("Ошибка", f"Лог с номером **№{log_id}** не найден.")
            await ctx.send(embed=embed)

    @commands.command(name="resetlogs")
    @check_access_decorator("resetlogs")
    async def resetlogs_cmd(self, ctx: commands.Context, target: discord.User = None):
        if not target:
            embed = make_error_embed("Недостаточно аргументов", config.COMMAND_USAGE_HELP["resetlogs"])
            return await ctx.send(embed=embed)

        res1 = tickets_col.delete_many({"staff_id": target.id})
        res2 = deleted_tickets_col.delete_many({"staff_id": target.id})

        embed = make_status_embed(
            "Сброс логов",
            f"Все логи пользователя {target.mention} очищены.\nУдалено тикетов: **{res1.deleted_count}**, удалено записей удалений: **{res2.deleted_count}**.",
            "success"
        )
        await ctx.send(embed=embed)
        await log_action(ctx.guild, "resetlogs", embed)

    @commands.command(name="config", aliases=["cfg"])
    async def config_cmd(self, ctx: commands.Context):
        if not is_owner_user(ctx.author):
            embed = make_error_embed("Недостаточно прав", "Эта команда доступна только владельцу бота.")
            return await ctx.send(embed=embed)

        embed = build_config_embed()
        view = ConfigMainView(ctx.author.id)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))