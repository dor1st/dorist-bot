import discord
from discord.ext import commands

import config
from database import tickets_col, deleted_tickets_col
from utils import check_access_decorator, make_error_embed, make_status_embed, is_owner_user, log_action


# --- MODALS & SELECTS FOR CONFIGURATION ---

class EditConfigModal(discord.ui.Modal):
    def __init__(self, key: str, title: str, current_val: str, category_view: "ConfigCategoryView"):
        super().__init__(title=title)
        self.key = key
        self.category_view = category_view
        
        self.val_input = discord.ui.TextInput(
            label="Новое значение",
            default=str(current_val if current_val is not None else ""),
            required=True
        )
        self.add_item(self.val_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Быстрый ответ, чтобы Discord не выдал таймаут при сохранении
        await interaction.response.defer(ephemeral=True)

        new_val = self.val_input.value
        if self.key == "embed_color":
            try:
                new_val = int(new_val.replace("#", ""), 16) if "#" in new_val else int(new_val)
            except ValueError:
                return await interaction.followup.send("Неверный формат цвета! Укажите число или HEX (например, #2171169).", ephemeral=True)
        
        config.CONFIG[self.key] = new_val
        # config.save_config()

        await self.category_view.update_category_message(interaction, "server")
        await interaction.followup.send("Значение успешно обновлено!", ephemeral=True)


class ServerParamSelect(discord.ui.Select):
    def __init__(self, category_view: "ConfigCategoryView"):
        self.category_view = category_view
        options = [
            discord.SelectOption(label="Цвет Embed", value="embed_color", description="Изменить цвет вложений"),
            discord.SelectOption(label="Footer Текст", value="footer_text", description="Изменить текст футера"),
            discord.SelectOption(label="Канал считалки", value="counting_channel_id", description="Указать канал для считалки"),
            discord.SelectOption(label="Канал бампа", value="bump_channel_id", description="Указать канал для бампа")
        ]
        super().__init__(placeholder="Выберите параметр для изменения...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]

        if selected_key in ["counting_channel_id", "bump_channel_id"]:
            # Для отправки ChannelPicker используем мгновенный ответ
            view = ChannelPickerView(self.category_view, selected_key)
            await interaction.response.send_message(f"Выберите новый текстовый канал для **{selected_key}**:", view=view, ephemeral=True)
        else:
            # Для модального окна вызываем send_modal СРАЗУ без defer
            modal_title = "Изменение цвета" if selected_key == "embed_color" else "Изменение текста футера"
            modal = EditConfigModal(selected_key, modal_title, config.CONFIG.get(selected_key), self.category_view)
            await interaction.response.send_modal(modal)


class TicketParamSelect(discord.ui.Select):
    def __init__(self, category_view: "ConfigCategoryView"):
        self.category_view = category_view
        
        toggles = config.CONFIG.get("log_toggles", {})
        options = [
            discord.SelectOption(label="Канал логов тикетов", value="log_channel_id", description="Выбрать канал для логов")
        ]
        
        for cmd_name, is_enabled in toggles.items():
            options.append(discord.SelectOption(
                label=f"Лог: {cmd_name}",
                value=f"toggle_{cmd_name}",
                description=f"Сейчас: {'Включено' if is_enabled else 'Выключено'}"
            ))

        super().__init__(placeholder="Выберите параметр для изменения...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]

        if selected_key == "log_channel_id":
            view = ChannelPickerView(self.category_view, selected_key)
            await interaction.response.send_message("Выберите новый канал для логов тикетов:", view=view, ephemeral=True)
        elif selected_key.startswith("toggle_"):
            # Оповещаем Discord мгновенно
            await interaction.response.defer()

            cmd = selected_key.replace("toggle_", "")
            toggles = config.CONFIG.setdefault("log_toggles", {})
            toggles[cmd] = not toggles.get(cmd, False)
            # config.save_config()

            await self.category_view.update_category_message(interaction, "tickets")


class ChannelPickerView(discord.ui.View):
    def __init__(self, category_view: "ConfigCategoryView", config_key: str):
        super().__init__(timeout=180)
        self.category_view = category_view
        self.config_key = config_key

        select = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="Выберите текстовый канал..."
        )
        select.callback = self.channel_select_callback
        self.add_item(select)

    async def channel_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        channel_id = int(interaction.data["values"][0])
        config.CONFIG[self.config_key] = channel_id
        # config.save_config()

        await interaction.followup.send("Канал успешно обновлен!", ephemeral=True)
        await self.category_view.update_category_message(
            interaction, 
            "server" if "channel_id" in self.config_key and self.config_key != "log_channel_id" else "tickets"
        )


# --- MAIN VIEWS ---

class ConfigSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Сервер", description="Цвет embed, Footer, Итоги, Доступ", emoji="<:buildercap:1541377896189534238>", value="server"),
            discord.SelectOption(label="Тикеты", description="Настройка тикетов и канала логов", emoji="<:ticket:1522343287816716379>", value="tickets"),
        ]
        super().__init__(placeholder="Выберите категорию настроек...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        category = self.values[0]
        category_view = ConfigCategoryView(interaction.user.id, self.view)
        await category_view.update_category_message(interaction, category)


class ConfigMainView(discord.ui.View):
    def __init__(self, author_id: int):
        # timeout=None снимает ограничение по времени (меню не будет отключено со временем)
        super().__init__(timeout=None)
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
        super().__init__(timeout=None)
        self.author_id = author_id
        self.parent_view = parent_view

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            embed = make_error_embed("Отказ в доступе", "Вы не можете управлять меню конфигурации.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    def build_embed(self, category: str) -> discord.Embed:
        embed = discord.Embed(color=config.EMBED_COLOR)
        if category == "server":
            embed.title = "<:buildercap:1541377896189534238> Настройки сервера"
            embed.description = (
                f"**Цвет Embed:** `{config.CONFIG.get('embed_color')}`\n"
                f"**Footer Текст:** `{config.CONFIG.get('footer_text')}`\n\n"
                f"**Канал считалки:** <#{config.CONFIG.get('counting_channel_id')}>\n"
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
        return embed

    async def update_category_message(self, interaction: discord.Interaction, category: str):
        self.clear_items()
        
        if category == "server":
            self.add_item(ServerParamSelect(self))
        elif category == "tickets":
            self.add_item(TicketParamSelect(self))
            
        back_btn = discord.ui.Button(label="Назад", emoji="◀️", style=discord.ButtonStyle.secondary)
        back_btn.callback = self.back_button_callback
        self.add_item(back_btn)

        embed = self.build_embed(category)

        # Безопасное обновление сообщения независимое от того, был вызван defer() или нет
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def back_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = build_config_embed()
        await interaction.edit_original_response(embed=embed, view=self.parent_view)


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