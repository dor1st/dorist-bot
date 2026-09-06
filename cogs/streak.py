from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

import config
from database import users_col
from utils import check_access_decorator, make_error_embed

# -------------------------------------------------------------
# НАСТРОЙКИ СТРИКОВ И НАГРАД ЗА РОЛИ
# -------------------------------------------------------------
STREAK_ROLE_REWARDS = {
    1437096779693686886: 7,   # Пример: роль выдается за стрикт в 7 дней
    1309460485082714144: 30,  # Пример: роль выдается за стрикт в 30 дней
}

def get_utc_today() -> str:
    """Возвращает текущую дату в формате YYYY-MM-DD по UTC."""
    return datetime.now(timezone.utc).date().isoformat()

async def check_and_update_streak(user_id: int, guild: discord.Guild = None, member: discord.Member = None) -> tuple[int, int, bool]:
    """
    Проверяет и обновляет стрик пользователя.
    Возвращает: (current_streak, max_streak, is_new_day)
    """
    today = get_utc_today()
    user_doc = users_col.find_one({"_id": user_id}) or {}
    
    streak_data = user_doc.get("streak", {})
    current_streak = streak_data.get("current", 0)
    max_streak = streak_data.get("max", 0)
    last_active_date = streak_data.get("last_date")

    is_new_day = False

    if last_active_date == today:
        # Уже активничал сегодня, стрик не меняется
        return current_streak, max_streak, False

    if last_active_date is None:
        # Первая активность вообще
        current_streak = 1
        is_new_day = True
    else:
        # Проверяем разницу дат
        try:
            last_date_obj = datetime.strptime(last_active_date, "%Y-%m-%d").date()
            today_obj = datetime.strptime(today, "%Y-%m-%d").date()
            delta_days = (today_obj - last_date_obj).days

            if delta_days == 1:
                # Ровно следующий день — стрик увеличивается
                current_streak += 1
                is_new_day = True
            elif delta_days > 1:
                # Пропущен день или более — сброс стрика
                current_streak = 1
                is_new_day = True
            else:
                # На случай рассинхронизации времени
                is_new_day = False
        except ValueError:
            current_streak = 1
            is_new_day = True

    if current_streak > max_streak:
        max_streak = current_streak

    # Сохраняем в базу
    users_col.update_one(
        {"_id": user_id},
        {
            "$set": {
                "streak.current": current_streak,
                "streak.max": max_streak,
                "streak.last_date": today
            }
        },
        upsert=True
    )

    # Проверка и выдача ролей за достижение стрика
    if is_new_day and guild and member:
        for role_id, target_days in STREAK_ROLE_REWARDS.items():
            if current_streak >= target_days:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Достигнут стрик активности: {current_streak} дней")
                    except discord.Forbidden:
                        pass

    return current_streak, max_streak, is_new_day


class StreakCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Перехватываем команды .work, .crime, .income для засчитывания стрика
        if message.author.bot or not message.guild:
            return

        ctx = await self.bot.get_context(message)
        if not ctx.valid or not ctx.command:
            return

        if ctx.command.name in ["work", "crime", "income"]:
            member = message.author if isinstance(message.author, discord.Member) else message.guild.get_member(message.author.id)
            await check_and_update_streak(message.author.id, guild=message.guild, member=member)

    @commands.command(name="streak")
    @check_access_decorator("streak")
    async def streak_cmd(self, ctx: commands.Context, target: discord.Member | discord.User = None):
        target = target or ctx.author
        user_doc = users_col.find_one({"_id": target.id}) or {}
        streak_data = user_doc.get("streak", {})
        
        current = streak_data.get("current", 0)
        max_val = streak_data.get("max", 0)

        embed = discord.Embed(
            title=f"<:sparkles:1522342290494849034> Стрик активности: {target.display_name}",
            color=config.EMBED_COLOR
        )
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
        embed.add_field(name="Текущий стрик", value=f"🔥 **{current}** дн.", inline=True)
        embed.add_field(name="Рекорд стрика", value=f"🏆 **{max_val}** дн.", inline=True)
        embed.set_footer(text=config.FOOTER_TEXT)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StreakCog(bot))