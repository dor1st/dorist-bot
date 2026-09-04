import discord
from discord.ext import commands

import config
from utils import make_error_embed, is_owner_user


def get_user_groups(user: discord.Member | discord.User) -> list[str]:
    """Возвращает список наименований групп доступа, к которым принадлежит пользователь."""
    groups = ["everyone"]

    if is_owner_user(user):
        groups.append("owner")

    if isinstance(user, discord.Member):
        perm_groups = config.CONFIG.get("permission_groups", {})
        user_role_ids = {r.id for r in user.roles}

        for group_key, group_data in perm_groups.items():
            required_roles = group_data.get("roles", [])
            if any(rid in user_role_ids for rid in required_roles):
                groups.append(group_key)

    return groups


def build_help_embed(category: str = "main", user: discord.Member | discord.User = None) -> discord.Embed:
    embed = discord.Embed(title="<:buildercap:1541377896189534238> Меню команд бота", color=config.EMBED_COLOR)
    user_groups = get_user_groups(user)

    if category == "main":
        embed.description = "Выберите категорию ниже, чтобы просмотреть доступные команды."
        embed.add_field(
            name="<:sparkles:1522342290494849034> Общие команды",
            value="> `.help` — *Показать меню команд.*\n> `.config` — *Открыть меню настроек бота.*\n",
            inline=False,
        )

        categories_text = []
        help_cats = getattr(config, "HELP_CATEGORIES", {})

        for cat_key, cat_data in help_cats.items():
            if any(g in user_groups for g in cat_data.get("allowed_groups", [])):
                categories_text.append(f"> {cat_data['emoji']} **{cat_data['name']}**")

        if categories_text:
            embed.add_field(
                name="<:info:1522329987514892398> Доступные вам категории",
                value="\n".join(categories_text),
                inline=False,
            )

    elif category in getattr(config, "HELP_CATEGORIES", {}):
        cat_data = config.HELP_CATEGORIES[category]
        embed.title = f"{cat_data['emoji']} Категория: {cat_data['name']}"
        embed.description = "\n".join(cat_data["commands"])

    user_group_display = "Владелец" if is_owner_user(user) else ("Участник" if "everyone" in user_groups else "Гость")
    embed.set_footer(text=f"Вызвано: {user.display_name} • Группа: {user_group_display} • {config.FOOTER_TEXT}")
    return embed


class HelpView(discord.ui.View):
    def __init__(self, author_id: int, user: discord.Member | discord.User):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.user = user
        self.user_groups = get_user_groups(user)
        self.setup_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            embed = make_error_embed("Отказ в доступе", "Вы не можете управлять этим меню, так как вызвали его не вы.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    def setup_buttons(self):
        self.clear_items()
        help_cats = getattr(config, "HELP_CATEGORIES", {})

        for cat_key, cat_data in help_cats.items():
            if any(g in self.user_groups for g in cat_data.get("allowed_groups", [])):
                btn = discord.ui.Button(
                    label=cat_data["name"],
                    emoji=cat_data["emoji"],
                    style=discord.ButtonStyle.gray,
                    custom_id=f"help_cat_{cat_key}",
                )
                btn.callback = self.make_category_callback(cat_key)
                self.add_item(btn)

    def make_category_callback(self, cat_key: str):
        async def callback(interaction: discord.Interaction):
            embed = build_help_embed(cat_key, self.user)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        return callback


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context):
        embed = build_help_embed("main", ctx.author)
        view = HelpView(ctx.author.id, ctx.author)
        await ctx.send(embed=embed, view=view)

    # -------------------------------------------------------------
    # Справка по отдельным командам экономики и мини-игр
    # -------------------------------------------------------------

    @commands.command(name="work_help")
    async def work_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Команда: work",
            description=(
                "Выполнить работу и получить заработок[cite: 2].\n\n"
                "**Кулдаун:**\n"
                "1.5 часа (5400 секунд)[cite: 2]\n\n"
                "**Основы и правила:**\n"
                "1. Шанс успеха составляет **70%**[cite: 2].\n"
                "2. При успехе вы получаете **100–300** коинов[cite: 2].\n"
                "3. При неудаче вы можете потерять коины[cite: 2].\n\n"
                "**Использование:**\n"
                "`.work`[cite: 2]"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="crime_help")
    async def crime_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Команда: crime",
            description=(
                "Попытаться совершить преступление ради выгоды[cite: 2].\n\n"
                "**Кулдаун:**\n"
                "12 часов (43200 секунд)[cite: 2]\n\n"
                "**Основы и правила:**\n"
                "1. Шанс успеха составляет **40%**[cite: 2].\n"
                "2. Выигрыш: от **200** до **500** коинов[cite: 2].\n"
                "3. При неудаче налагается штраф[cite: 2].\n\n"
                "**Использование:**\n"
                "`.crime`[cite: 2]"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="income_help")
    async def income_help(self, ctx: commands.Context):
        cats = ", ".join(f"`{role_id}`" for role_id in getattr(config, "ROLE_INCOME_TABLE", {}).keys()) if hasattr(config, "ROLE_INCOME_TABLE") else "специальные роли"
        embed = discord.Embed(
            title="Команда: income",
            description=(
                "Собрать ежедневный доход за имеющиеся роли[cite: 2].\n\n"
                "**Кулдаун:**\n"
                "24 часа (86400 секунд)[cite: 2]\n\n"
                "**Основы и правила:**\n"
                "1. Награда начисляется за каждую доходную роль в инвентаре[cite: 2].\n"
                "2. Если ролей нет, кулдаун сбрасывается автоматически[cite: 2].\n\n"
                "**Использование:**\n"
                "`.income`[cite: 2]"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="rob_help")
    async def rob_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Команда: rob",
            description=(
                "Попытаться ограбить другого участника[cite: 2].\n\n"
                "**Кулдаун:**\n"
                "24 часа (86400 секунд)[cite: 2]\n\n"
                "**Основы и правила:**\n"
                "1. Нельзя грабить ботов или самого себя[cite: 2].\n"
                "2. Шанс успешного ограбления — **30%**[cite: 2].\n"
                "3. В случае успеха вы забираете от **30%** до **70%** наличных жертвы[cite: 2].\n"
                "4. При провале вы платите штраф[cite: 2].\n\n"
                "**Использование:**\n"
                "`.rob [упоминание / ID]`[cite: 2]"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="slotmachine_help")
    async def slotmachine_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Команда: slotmachine",
            description=(
                "Сделать ставку в слот-машине[cite: 2].\n\n"
                "**Кулдаун:**\n"
                "3 секунды[cite: 2]\n\n"
                "**Основы и правила:**\n"
                "1. Шанс победы составляет **50%**[cite: 2].\n"
                "2. Случайный множитель выигрыша от **x1.2** до **x2.0**[cite: 2].\n"
                "3. Ставка списывается исключительно с **наличного** счёта[cite: 2].\n\n"
                "**Использование:**\n"
                "`.slotmachine [ставка]` или `.slot [ставка]`[cite: 2]"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="roll_help")
    async def roll_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Команда: roll",
            description=(
                "Сделать ставку на число в костях от 1 до 6[cite: 2].\n\n"
                "**Кулдаун:**\n"
                "3 секунды[cite: 2]\n\n"
                "**Основы и правила:**\n"
                "1. Выберите число от 1 до 6[cite: 2].\n"
                "2. Шанс угадать составляет **50%**[cite: 2].\n"
                "3. При угадывании выигрыш умножается на рандомный множитель до **x2.0**[cite: 2].\n\n"
                "**Использование:**\n"
                "`.roll [ставка] [число 1-6]`[cite: 2]"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))