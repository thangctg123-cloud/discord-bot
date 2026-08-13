import os
import discord
from discord.ext import commands
from discord import ui
import asyncio
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_tasks = {}

class DirectLyricModal(ui.Modal, title="Nhập Tên Bài Hát Chạy Lời"):
    user_token = ui.TextInput(
        label="User Token Discord của bạn",
        placeholder="Paste token Discord vào đây...",
        style=discord.TextStyle.short,
        required=True
    )

    song_query = ui.TextInput(
        label="Tên bài hát và ca sĩ",
        placeholder="Ví dụ: toidaidot - GREY D",
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        token = self.user_token.value.strip()
        query = self.song_query.value.strip()

        await interaction.response.send_message(
            f"🎵 Đang tìm lời cho bài **{query}** và chuẩn bị chạy lên ghi chú của bạn...",
            ephemeral=True
        )

        user_id = interaction.user.id
        if user_id in active_tasks:
            active_tasks[user_id].cancel()

        task = asyncio.create_task(run_direct_sync(token, query, interaction))
        active_tasks[user_id] = task

async def run_direct_sync(discord_token, query, interaction):
    headers = {"Authorization": discord_token, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        url = f"https://lrclib.net/api/search?q={query}"
        lyrics_cache = []
        song_title = query

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        track_name = data[0].get("trackName", query)
                        artist_name = data[0].get("artistName", "")
                        song_title = f"{track_name} - {artist_name}" if artist_name else track_name
                        synced = data[0].get("syncedLyrics")

                        if synced:
                            for line in synced.split("\n"):
                                if "]" in line:
                                    try:
                                        time_part, text = line.split("]", 1)
                                        time_part = time_part.strip("[")
                                        m, s_ms = time_part.split(":")
                                        s, ms = (s_ms.split(".") + ["0"])[:2]
                                        total_ms = int(m) * 60000 + int(s) * 1000 + int(ms.ljust(3, "0")[:3])

                                        cleaned_text = text.strip()

                                        # TỰ ĐỘNG CẮT BỎ phần tên nghệ sĩ/bài hát bị dính ở đuôi câu do nguồn API
                                        if " - " in cleaned_text:
                                            cleaned_text = cleaned_text.split(" - ")[0].strip()

                                        if cleaned_text:
                                            lyrics_cache.append({"time": total_ms, "text": cleaned_text})
                                    except Exception:
                                        continue

            if not lyrics_cache:
                lyrics_cache = [
                    {"time": 0, "text": f"Đang phát: {song_title}"},
                    {"time": 5000, "text": "🎵 Lời bài hát đang chạy..."},
                    {"time": 15000, "text": song_title}
                ]

            while True:
                start_time = asyncio.get_event_loop().time() * 1000

                for lyric in lyrics_cache:
                    current_elapsed = (asyncio.get_event_loop().time() * 1000) - start_time
                    target_time = lyric["time"]

                    if target_time > current_elapsed:
                        await asyncio.sleep((target_time - current_elapsed) / 1000)

                    # Chỉ gửi thuần túy câu chữ đã được làm sạch
                    payload = {
                        "custom_status": {
                            "text": f"{lyric['text']}",
                            "emoji_name": "🎵"
                        }
                    }
                    async with session.patch("https://discord.com/api/v9/users/@me/settings", json=payload, headers=headers) as resp:
                        pass

                await asyncio.sleep(3)

        except asyncio.CancelledError:
            payload = {"custom_status": None}
            async with session.patch("https://discord.com/api/v9/users/@me/settings", json=payload, headers=headers) as resp:
                pass

class DirectView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Nhập Bài Hát Chạy Lời", style=discord.ButtonStyle.success, emoji="🎧", custom_id="unique_sing_btn_1")
    async def open_modal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(DirectLyricModal())

    @ui.button(label="Dừng Sync", style=discord.ButtonStyle.danger, emoji="🛑", custom_id="unique_stop_btn_1")
    async def stop_sync(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        if user_id in active_tasks:
            active_tasks[user_id].cancel()
            del active_tasks[user_id]
        await interaction.response.send_message("🛑 Đã dừng lyric status.", ephemeral=True)

@bot.command(name="sing")
async def sing_panel(ctx):
    embed = discord.Embed(
        title="🎧 Direct Realtime Lyrics",
        description="Nhấn nút bên dưới, nhập Token và tên bài hát bạn muốn để bot tự động chạy lời lên ghi chú!",
        color=discord.Color.green()
    )
    try:
        await ctx.message.delete()
    except Exception:
        pass

    await ctx.send(embed=embed, view=DirectView())

@bot.event
async def on_ready():
    print(f"Bot đã sẵn sàng: {bot.user}")

bot.run("MTUzNjk4MTc5ODQ5MDIxNDQwMA.GyFRLN.60hzWT7GDQ8pk-nwK8Ua_tplTyvMDg49oAxzeY")
