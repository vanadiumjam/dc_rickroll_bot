import discord
from discord.ext import commands
import re
import requests
import qrcode
from io import BytesIO
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os

# load env - 환경변수를 로드해준다
load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=None, intents=intents)

# 구글 API 키
API_KEY = os.getenv("GOOGLE_API_KEY")

# YouTube API 클라이언트 생성
youtube = build("youtube", "v3", developerKey=API_KEY)

# 조회수를 가져올 영상의 ID
video_id = "dQw4w9WgXcQ"

rickroll_detection_enabled = True # 감지 기능

# 감지된 링크 카운트 저장
rickroll_count = 0

# 사용자 지정 RickRoll 링크 감지 카운트
custom_rickroll_count = 0

# 감지된 RickRoll 링크 저장
rickroll_links = []

# 사용자별 감지한 링크 수 추적
user_rickroll_counts = {}

# 사용자 지정 RickRoll 링크 추가
rickroll_custom_links = []

# 블랙리스트 채널 저장
blacklist_channels = set()

rickroll_patterns = [
    re.compile(r"(https?://)?(www\.)?(youtube\.com/watch\?v=dQw4w9WgXcQ|youtu\.be/dQw4w9WgXcQ)")
]

async def check_rickroll(message):
    global rickroll_count, rickroll_links, user_rickroll_counts

    if message.channel.id in blacklist_channels:
        return

    if not rickroll_detection_enabled:
        return  # 감지 기능이 꺼져 있으면 아무것도 하지 않음

    # 1. 메시지 내 URL이 있는지 확인
    urls = re.findall(r"https?://\S+", message.content)

    for url in urls:
        # 2. 최종 URL 가져오기
        final_url = await get_final_url(url) or url  # 요청 실패 시 원래 URL 사용

        # 3. RickRoll 링크인지 확인
        for pattern in rickroll_patterns:
            rickroll_count += 1
            rickroll_links.append(final_url)
            user_rickroll_counts[message.author.id] = user_rickroll_counts.get(message.author.id, 0) + 1
            if pattern.search(final_url):
                await message.reply("🚨 **RickRoll Detected!**")
                return

        # 4. 사용자 지정 링크 감지
        for custom_link in rickroll_custom_links:
            if custom_link in final_url:
                custom_rickroll_count += 1
                rickroll_links.append(final_url)
                user_rickroll_counts[message.author.id] = user_rickroll_counts.get(message.author.id, 0) + 1
                await message.reply(f"🚨 **Custom Link Detected!**")
                return

async def get_final_url(short_url):
    try:
        response = requests.head(short_url, allow_redirects=True)
        return response.url
    except requests.RequestException as e:
        return f"ERR: {e}"

async def has_admin_permissions(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        await interaction.response.send_message(
            "You cannot use this command outside of a server.",
            ephemeral=True,
        )
        return False

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You must have administrator permissions to run this command.",
            ephemeral=True,
        )
        return False

    return True

# YouTube API 호출하여 비디오 정보 가져오기
def get_video_view_count(video_id):
    request = youtube.videos().list(part="statistics", id=video_id)
    response = request.execute()

    # 조회수 가져오기
    if "items" in response and len(response["items"]) > 0:
        view_count = int(response["items"][0]["statistics"]["viewCount"])
        return view_count
    else:
        return "Video not found."


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()


@bot.tree.command(name="rickroll_detection", description="Enable or disable Rickroll detection.")
async def rickroll_detection(interaction: discord.Interaction, status: str):
    global rickroll_detection_enabled
    if not await has_admin_permissions(interaction):
        return

    if status.lower() == "on":
        rickroll_detection_enabled = True
        await interaction.response.send_message("✅ **RickRoll Detection is now `ON`!**")
    elif status.lower() == "off":
        rickroll_detection_enabled = False
        await interaction.response.send_message("✅ **RickRoll Detection is now `OFF`!**")
    else:
        await interaction.response.send_message("❌ Invalid option.\nUse `/rickroll_detection on` or `/rickroll_detection off`.")

@bot.tree.command(name="rickroll_qrcode_generator", description="Generate a QR code for a RickRoll link.")
async def rickroll_qrcode_generator(interaction: discord.Interaction, option: str = None):
    qr = qrcode.QRCode(
        version=1, box_size=10, border=5
    )
    qr.add_data("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    qr.make(fit=True)

    img = qr.make_image(fill="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(buffer, filename="rickroll_qr.png")

    if option == "dm":
        await interaction.user.send("Here is your RickRoll QR Code!", file=file)
        await interaction.response.send_message("✅ Sent QR Code to your DM!", ephemeral=True)
    elif option == "only_me":
        await interaction.response.send_message("Here is your Rickroll QR Code!", file=file, ephemeral=True)
    elif option == "immediately":
        await interaction.response.send_message("## Scan this QR code!", file=file, ephemeral=False)
    else:
        await interaction.response.send_message("❌ ## Invalid option.\n `dm` : Bot will DM you a QR code.\n `only_me` : The generated QR code will be shown here, but only you can see it.\n `immediately` : Generate QR code and send to this channel immediately.", ephemeral=True)

@bot.tree.command(name="add_link", description="Add a custom link to the detection list.")
async def rickroll_add_link(interaction: discord.Interaction, link: str):
    if not await has_admin_permissions(interaction):
        return

    if link not in rickroll_custom_links:
        rickroll_custom_links.append(link)
        await interaction.response.send_message(f"✅ Custom RickRoll link `{link}` has been added to the detection list.", ephemeral=False)
    else:
        await interaction.response.send_message(f"❌ Link `{link}` is already in the detection list.", ephemeral=False)

@bot.tree.command(name="rickroll_stats", description="Check the statistics of detected RickRoll links.")
async def rickroll_stats(interaction: discord.Interaction):
    stats_message = (
        f"✅ **Total RickRoll detections:** {rickroll_count + custom_rickroll_count}\n"
    )

    # 사용자별 통계 추가 (0번 감지한 사용자는 제외)
    user_stats = ""
    for user_id, count in user_rickroll_counts.items():
        if count > 0:  # 감지한 링크가 0인 사용자는 표시하지 않음
            user = await bot.fetch_user(user_id)  # 사용자 정보를 가져옵니다.
            user_stats += f"  - {user.name}: {count}\n"

    if user_stats:
        stats_message += "\n**User Statistics:**\n"
        stats_message += user_stats


    await interaction.response.send_message(stats_message, ephemeral=False)

@bot.tree.command(name="ping", description="Check bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Latency is {latency}ms")

@bot.tree.command(name="echo", description="Make the bot repeat your message")
async def echo(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)

@bot.tree.command(name="user_info", description="Show information about a user")
async def user_info(interaction: discord.Interaction, user: discord.Member):
    info = (
        f"**Username:** {user}\n"
        f"**ID:** {user.id}\n"
        f"**Joined Server:** {user.joined_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**Created Account:** {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"**Rickrolls:** {user_rickroll_counts.get(user.id, 0)}"
    )
    await interaction.response.send_message(info)

@bot.tree.command(name="blacklist", description="Add or remove a channel to/from the blacklist.")
async def blacklist_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not await has_admin_permissions(interaction):
        return

    if channel is None:
        await interaction.response.send_message("❌ Please specify a channel.", ephemeral=True)
        return

    if channel.id in blacklist_channels:
        blacklist_channels.remove(channel.id)
        await interaction.response.send_message(f"✅ Channel `{channel.name}` has been removed from the blacklist.", ephemeral=False)
    else:
        blacklist_channels.add(channel.id)
        await interaction.response.send_message(f"✅ Channel `{channel.name}` has been added to the blacklist.", ephemeral=False)

@bot.tree.command(name="blacklist_channels", description="Check the current blacklist channels.")
async def blacklist_stats(interaction: discord.Interaction):
    if not blacklist_channels:
        await interaction.response.send_message("❌ No channels are currently in the blacklist.", ephemeral=True)
        return

    # 블랙리스트 채널 목록 출력
    blacklist_message = "✅ **Blacklisted Channels:**\n"
    for channel_id in blacklist_channels:
        channel = await bot.fetch_channel(channel_id)
        blacklist_message += f"  - {channel.mention} (ID: `{channel.id}`)\n"

    await interaction.response.send_message(blacklist_message, ephemeral=True)

@bot.tree.command(name="worldwide_rickroll_status", description="Get Never Gonna Give You Up music video's views.")
async def vid_views(interaction: discord.Interaction):
    view_count = get_video_view_count(video_id)
    await interaction.response.send_message(f"Total **{view_count:,}** people got rickrolled. Amazing!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await check_rickroll(message)

    await bot.process_commands(message)


bot.run(discord_token)
