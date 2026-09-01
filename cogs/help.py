import discord
from discord.ext import commands

import config
from utils import make_error_embed, is_owner_user


def build_help_embed(category: str = "main", user: discord.Member | discord.User = None) -> discord.Embed:
    embed = discord.Embed(title="<:buildercap:1541377896189534238> Меню команд бота", color=config.EMBED_COLOR)

    if category == "main":
        embed.description = "Выберите категорию ниже, чтобы просмотреть доступные команды."
        embed.add_field(
            name="<:sparkles:1522342290494849034> Общие команды",
            value="> `.help` — *Показать меню команд.*\n"
                  "> `.config` — *Открыть меню настроек бота.*\n",
            inline=False
        )
        embed.add_field(
            name="<:info:1522329987514892398> Доступные категории",
            value="> <:ticket:1522343287816716379> **Тикеты** — Статистика, логи и управление тикетами.\n"
                  "> <:logs:1522340749998428160> **Логи** — Регистрация розыгрышей и инвайтов.\n"
                  "> <:staff:1522338131339251823> **Другое** — Сообщения, профили и общая статистика.",
            inline=False
        )

    elif category == "tickets":
        embed.title = "<:ticket:1522343287816716379> Категория: Тикеты"
        embed.description = (
            "> `.ticketstats` — *Статистика тикетов модератора.*\n"
            "> `.addticket` — *Записать новый обработанный тикет.*\n"
            "> `.ticketlogs` — *Просмотреть логи тикетов пользователя.*\n\n"
            "> `.deleteticket` — *Записать удаление тикета.*\n"
            "> `.deletelog` — *Удалить конкретный лог тикета.*\n"
            "> `.resetlogs` — *Очистить все логи модератора.*"
        )

    elif category == "logs":
        embed.title = "<:logs:1522340749998428160> Категория: Логи"
        embed.description = (
            "> `.loggiveaway` — *Записать проведенный розыгрыш.*\n"
            "> `.deletegiveaway` — *Удалить лог розыгрыша.*\n"
            "> `.giveawaylogs` — *Просмотреть логи розыгрышей пользователя.*\n\n"
            "> `.loginvite` — *Записать выданный приз за приглашение.*\n"
            "> `.deleteinvite` — *Удалить лог приглашения из базы.*\n"
            "> `.invitelogs` — *Посмотреть логи приглашений пользователя.*\n"
            "> `.inviter` — *Узнать, кто пригласил участника.*\n"
            "> `.invites` — *Узнать количество приглашенных участников.*\n"
            "> `.validinvite` — *Проверить, забирали ли приз за пользователя.*"
        )

    elif category == "other":
        embed.title = "<:staff:1522338131339251823> Категория: Другое"
        embed.description = (
            "> `.messages` — *Количество отправленных сообщений.*\n"
            "> `.userinfo` — *Посмотреть профиль, даты и роли участника.*\n"
            "> `.summaries` — *Просмотреть общие итоги и сводку.*"
        )

    user_group = "Владелец" if is_owner_user(user) else "Пользователь"
    embed.set_footer(text=f"Вызвано: {user.display_name} • Ваша текущая группа: {user_group} • {config.FOOTER_TEXT}")
    return embed


class HelpView(discord.ui.View):
    def __init__(self, author_id: int, user: discord.Member | discord.User):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.user = user
        self.show_main_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            embed = make_error_embed("Отказ в доступе", "Вы не можете управлять этим меню, так как вызвали его не вы.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    def show_main_buttons(self):
        self.clear_items()
        
        tickets_btn = discord.ui.Button(
            label="Тикеты", 
            emoji="<:ticket:1522343287816716379>", 
            style=discord.ButtonStyle.gray, 
            custom_id="help_tickets"
        )
        tickets_btn.callback = self.tickets_callback
        self.add_item(tickets_btn)

        logs_btn = discord.ui.Button(
            label="Логи", 
            emoji="<:logs:1522340749998428160>", 
            style=discord.ButtonStyle.gray, 
            custom_id="help_logs"
        )
        logs_btn.callback = self.logs_callback
        self.add_item(logs_btn)

        other_btn = discord.ui.Button(
            label="Другое", 
            emoji="<:staff:1522338131339251823>", 
            style=discord.ButtonStyle.gray, 
            custom_id="help_other"
        )
        other_btn.callback = self.other_callback
        self.add_item(other_btn)

    def show_back_button(self):
        self.clear_items()
        back_btn = discord.ui.Button(
            label="Назад", 
            emoji="<:darkleft:1543989641751957565>", 
            style=discord.ButtonStyle.secondary, 
            custom_id="help_back"
        )
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def tickets_callback(self, interaction: discord.Interaction):
        embed = build_help_embed("tickets", self.user)
        self.show_back_button()
        await interaction.response.edit_message(embed=embed, view=self)

    async def logs_callback(self, interaction: discord.Interaction):
        embed = build_help_embed("logs", self.user)
        self.show_back_button()
        await interaction.response.edit_message(embed=embed, view=self)

    async def other_callback(self, interaction: discord.Interaction):
        embed = build_help_embed("other", self.user)
        self.show_back_button()
        await interaction.response.edit_message(embed=embed, view=self)

    async def back_callback(self, interaction: discord.Interaction):
        embed = build_help_embed("main", self.user)
        self.show_main_buttons()
        await interaction.response.edit_message(embed=embed, view=self)


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context):
        embed = build_help_embed("main", ctx.author)
        view = HelpView(ctx.author.id, ctx.author)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))