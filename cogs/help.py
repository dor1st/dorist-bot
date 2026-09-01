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
            value="`.help` — *Показать меню команд.*\n"
                  "`.config` — *Открыть меню настроек бота (цвет, footer, доступ).*\n",
            inline=False
        )
        embed.add_field(
            name="<:info:1522329987514892398> Доступные категории",
            value="<:ticket:1522343287816716379> **Тикеты** — Команды для работы с тикетами, логами и статистикой.\n"
                  "<:logs:1522340749998428160> **Логи** — Команды для регистрации розыгрышей и инвайтов.\n"
                  "<:staff:1522338131339251823> **Другое** — Информация о пользователях и итоговая статистика.",
            inline=False
        )

    elif category == "tickets":
        embed.title = "<:ticket:1522343287816716379> Категория: Тикеты"
        embed.description = "Используйте префикс `.` перед вызовом команды\n"

        embed.add_field(
            name="<:ticket:1522343287816716379> Статистика и логи тикетов",
            value="`.ticketstats [ID / упоминание]`\n> *Посмотреть статистику тикетов модератора.*\n\n"
                  "`.addticket [ID модератора] [ссылка] [категория]`\n> *Записать новый обработанный тикет в базу данных.*\n\n"
                  "`.ticketlogs [ID / упоминание]`\n> *Просмотреть логи тикетов пользователя.*",
            inline=False
        )
        embed.add_field(
            name="<:mod:1522343179205087363> Управление и удаление",
            value="`.deleteticket [номер лога] [ссылка на транскрипт]`\n> *Записать удаление тикета.*\n\n"
                  "`.deletelog [ID лога]`\n> *Удалить конкретный лог тикета.*\n\n"
                  "`.resetlogs [ID / упоминание]`\n> *Очистить абсолютно все логи модератора.*",
            inline=False
        )

    elif category == "logs":
        embed.title = "<:logs:1522340749998428160> Категория: Логи"
        embed.description = "Используйте префикс `.` перед вызовом команды\n"

        embed.add_field(
            name="<:sparkles:1522342290494849034> Розыгрыши",
            value="`.loggiveaway [ID хостера] [приз] [кол-во] [ссылка]`\n> *Записать проведенный розыгрыш в базу.*\n\n"
                  "`.deletegiveaway [ID лога]`\n> *Удалить лог розыгрыша из базы.*\n\n"
                  "`.giveawaylogs [ID / упоминание]`\n> *Просмотреть логи розыгрышей пользователя.*",
            inline=False
        )
        embed.add_field(
            name="<:logs:1522340749998428160> Приглашения (Инвайты)",
            value="`.loginvite [ID пригласившего] [ID приглашенного] [приз] [кол-во]`\n> *Записать выданный приз за приглашение.*\n\n"
                  "`.deleteinvite [ID лога]`\n> *Удалить лог приглашения из базы.*\n\n"
                  "`.invitelogs [ID / упоминание]`\n> *Посмотреть логи приглашений пользователя.*\n\n"
                  "`.inviter [ID / упоминание]`\n> *Узнать, кто пригласил участника и получил приз.*\n\n"
                  "`.invites [ID / упоминание]`\n> *Узнать количество приглашенных участников.*\n\n"
                  "`.validinvite [ID / упоминание]`\n> *Проверить, забирали ли уже приз за пользователя.*",
            inline=False
        )

    elif category == "other":
        embed.title = "<:staff:1522338131339251823> Категория: Другое"
        embed.description = "Используйте префикс `.` перед вызовом команды\n"

        embed.add_field(
            name="<:info:1522329987514892398> Общие и информационные команды",
            value="`.userinfo [ID / упоминание]`\n> *Посмотреть профиль, даты и роли участника.*\n\n"
                  "`.summaries`\n> *Просмотреть общие итоги и сводку.*",
            inline=False
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