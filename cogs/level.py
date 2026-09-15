import math
import time
import discord
from discord.ext import commands, tasks

import config
from database import users_col
from utils import check_access_decorator, make_error_embed, send_error_embed

XP_COOLDOWN = 60
_xp_cooldowns = {}

class LevelsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_xp_loop.start()

    def cog_unload(self):
        self.voice_xp_loop.cancel()

    @tasks.loop(minutes=1.0)
    async def voice_xp_loop(self):
        """Проверяет голосовые каналы каждую минуту и начисляет XP активным участникам."""
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            for voice_channel in guild.voice_channels:
                # Пропускаем заблокированные каналы
                if voice_channel.id in config.VOICE_XP_BLACKLIST_CHANNELS:
                    continue

                for member in voice_channel.members:
                    if member.bot:
                        continue

                    # Проверка микрофона и звука (должен быть размучен)
                    voice_state = member.voice
                    if not voice_state:
                        continue

                    is_muted = voice_state.self_mute or voice_state.mute
                    is_deaf = voice_state.self_deaf or voice_state.deaf

                    if not is_muted and not is_deaf:
                        multiplier = get_user_xp_multiplier(member)
                        xp_to_add = int(config.VOICE_XP_PER_MINUTE * multiplier)

                        users_col.update_one(
                            {"_id": member.id},
                            {"$inc": {"xp": xp_to_add}},
                            upsert=True
                        )

def get_user_xp_multiplier(member: discord.Member) -> float:
    """Вычисляет максимальный множитель опыта на основе ролей пользователя и глобального множителя."""
    if not isinstance(member, discord.Member):
        return config.GLOBAL_XP_MULTIPLIER

    max_role_mult = 1.0
    for role in member.roles:
        if role.id in config.ROLE_XP_MULTIPLIERS:
            if config.ROLE_XP_MULTIPLIERS[role.id] > max_role_mult:
                max_role_mult = config.ROLE_XP_MULTIPLIERS[role.id]

    return round(max_role_mult * config.GLOBAL_XP_MULTIPLIER, 2)

async def process_message_xp(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = time.time()

    if user_id in _xp_cooldowns and now - _xp_cooldowns[user_id] < XP_COOLDOWN:
        return

    _xp_cooldowns[user_id] = now

    content_len = len(message.content.strip())
    if content_len == 0:
        return
        
    base_xp = min(32, max(5, content_len // 2))
    
    # Применяем множитель
    multiplier = get_user_xp_multiplier(message.author)
    xp_to_add = int(base_xp * multiplier)

    users_col.update_one(
        {"_id": user_id},
        {"$inc": {"xp": xp_to_add}},
        upsert=True
    )

def get_xp_for_next_level(level: int) -> int:
    return -140 * (level ** 2) + 980 * level - 520

def calculate_level_from_xp(total_xp: int) -> tuple[int, int, int]:
    """
    По суммарному опыту вычисляет:
    (текущий уровень, опыт на текущем уровне, необходимо опыта для следующего уровня)
    """
    level = 1
    xp_needed = get_xp_for_next_level(level)
    
    while total_xp >= xp_needed:
        total_xp -= xp_needed
        level += 1
        xp_needed = get_xp_for_next_level(level)
        
    return level, total_xp, xp_needed

def create_progress_bar(current_xp: int, needed_xp: int, length: int = 8) -> str:
    """Генерирует бинарный прогресс-бар: зеленые (пройдено) и белые (не пройдено) квадраты."""
    if needed_xp <= 0:
        return "🟩" * length

    ratio = max(0.0, min(1.0, current_xp / needed_xp))
    
    # Округляем количество заполненных блоков
    filled_blocks = int(round(ratio * length))

    # Корректируем крайние значения для наглядности (пока < 100%, последний блок не станет зеленым)
    if ratio < 1.0 and filled_blocks == length:
        filled_blocks = length - 1

    empty_blocks = length - filled_blocks

    return ("🟩" * filled_blocks) + ("⬜" * empty_blocks)

async def process_message_xp(message: discord.Message):
    """Вызывается при отправке сообщений для начисления опыта."""
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = time.time()

    if user_id in _xp_cooldowns and now - _xp_cooldowns[user_id] < XP_COOLDOWN:
        return

    _xp_cooldowns[user_id] = now

    content_len = len(message.content.strip())
    if content_len == 0:
        return
        
    xp_to_add = min(32, max(5, content_len // 2))

    users_col.update_one(
        {"_id": user_id},
        {"$inc": {"xp": xp_to_add}},
        upsert=True
    )


class LevelsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rank", aliases=["level", "lvl"])
    @check_access_decorator("rank")
    async def rank_cmd(self, ctx: commands.Context, target: discord.Member | discord.User = None):
        target = target or ctx.author

        user_doc = users_col.find_one({"_id": target.id}) or {}
        total_xp = user_doc.get("xp", 0)

        level, current_xp, needed_xp = calculate_level_from_xp(total_xp)

        # Вычисление места в лидерборде
        pipeline = [
            {"$project": {"_id": "$_id", "xp": {"$ifNull": ["$xp", 0]}}},
            {"$sort": {"xp": -1}}
        ]
        all_users = list(users_col.aggregate(pipeline))
        
        rank_position = "—"
        for idx, u in enumerate(all_users, 1):
            if u["_id"] == target.id:
                rank_position = f"#{idx}"
                break

        progress_bar = create_progress_bar(current_xp, needed_xp)
        percent = int((current_xp / needed_xp) * 100) if needed_xp > 0 else 100

        embed = discord.Embed(
            title=f"<:pin:1522341130019143880> Уровень участника {target.display_name}",
            color=config.EMBED_COLOR
        )
        if hasattr(target, "avatar") and target.avatar:
            embed.set_thumbnail(url=target.avatar.url)

        embed.add_field(
            name="Информация",
            value=(
                f"• Уровень: **{level}**\n"
                f"• Место в топе: **{rank_position}**\n"
                f"• Всего опыта: **{total_xp:,}** XP"
            ),
            inline=False
        )
        embed.add_field(
            name="Прогресс уровня",
            value=(
                f"{progress_bar} **{percent}%**\n"
                f"`{current_xp:,}` / `{needed_xp:,}` XP (до следующего уровня: **{needed_xp - current_xp:,}** XP)"
            ),
            inline=False
        )

        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="addexp", aliases=["addxp"])
    @check_access_decorator("addexp")
    async def addexp_cmd(self, ctx: commands.Context, target: discord.Member | discord.User, amount: int):
        user_doc = users_col.find_one({"_id": target.id}) or {}
        current_xp = user_doc.get("xp", 0)

        new_xp = max(0, current_xp + amount)

        users_col.update_one(
            {"_id": target.id},
            {"$set": {"xp": new_xp}},
            upsert=True
        )

        old_lvl, _, _ = calculate_level_from_xp(current_xp)
        new_lvl, _, _ = calculate_level_from_xp(new_xp)

        embed = discord.Embed(
            title="<:success:1544301200894070844> Изменение опыта",
            description=(
                f"Участнику {target.mention} успешно изменено количество опыта.\n\n"
                f"• Выдано/Снято: **{amount:+} XP**\n"
                f"• Новый баланс XP: **{new_xp:,} XP**\n"
                f"• Уровень: **{old_lvl}** ➔ **{new_lvl}**"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)

    @commands.command(name="setrank", aliases=["setlevel", "setlvl"])
    @check_access_decorator("setrank")
    async def setrank_cmd(self, ctx: commands.Context, target: discord.Member | discord.User, target_level: int):
        if target_level < 1:
            return await send_error_embed(ctx, "Уровень не может быть меньше 1.")

        # Вычисляем минимальный XP для достижения указанного уровня
        target_xp = 0
        for lvl in range(1, target_level):
            target_xp += get_xp_for_next_level(lvl)

        users_col.update_one(
            {"_id": target.id},
            {"$set": {"xp": target_xp}},
            upsert=True
        )

        embed = discord.Embed(
            title="<:success:1544301200894070844> Изменение уровня",
            description=(
                f"Участнику {target.mention} установлен **{target_level}** уровень.\n"
                f"• Установлено опыта: **{target_xp:,} XP**"
            ),
            color=config.EMBED_COLOR
        )
        embed.set_footer(text=config.FOOTER_TEXT)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LevelsCog(bot))