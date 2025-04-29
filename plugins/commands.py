import asyncio
import logging
import time

import telethon
from telethon import TelegramClient
import humanreadable as hr
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from config import ADMINS, BOT_USERNAME, FORCE_LINK, HOST, PASSWORD, PORT
from database import db
from send_media import VideoSender
from terabox import get_data
from tools import extract_code_from_url, get_urls_from_string

log = logging.getLogger(__name__)

def generate_shortenedUrl(
    sender_id: int,
):
    try:
        uid = str(uuid.uuid4())
        data = requests.get(
            "https://gplinks.com/member/tools/api",
            params={
                "api": GP_LINKS_API,
                "url": f"https://t.me/{BOT_USERNAME}?start=token_{uid}",
                "alias": uid.split("-", maxsplit=2)[0],
            },
        )
        data.raise_for_status()
        data_json = data.json()
        if data_json.get("status") == "success":
            url = data_json.get("shortenedUrl")
            db.set(f"token_{uid}", f"{sender_id}|{url}", ex=21600)
            return url
        else:
            return None
    except Exception as e:
        return None

async def is_user_on_chat(bot: TelegramClient, chat_id: int, user_id: int) -> bool:
    """
    Check if a user is present in a specific chat.

    Parameters:
        bot (TelegramClient): The Telegram client instance.
        chat_id (int): The ID of the chat.
        user_id (int): The ID of the user.

    Returns:
        bool: True if the user is present in the chat, False otherwise.
    """
    try:
        check = await bot.get_permissions(chat_id, user_id)
        return check
    except Exception:
        return False

def remove_all_videos():
    current_directory = os.getcwd()

    video_extensions = [".mp4", ".mkv", ".webm"]

    try:
        for file_name in os.listdir(current_directory):
            if any(file_name.lower().endswith(ext) for ext in video_extensions):
                file_path = os.path.join(current_directory, file_name)

                os.remove(file_path)

    except Exception as e:
        print(f"Error: {e}")

@Client.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    reply_text = """
Hello there! I'm your friendly video downloader bot specially designed to fetch videos from Terabox. Share the Terabox link with me, and I'll swiftly get started on downloading it for you.

Let's make your video experience even better!
"""
    await message.reply_text(
        reply_text,
        disable_web_page_preview=True,
        parse_mode="markdown"
    )


@Client.on_message(filters.command("gen") & filters.private)
async def generate_token(client: Client, message: Message):
    is_user_active = db.get(f"active_{message.from_user.id}")
    if is_user_active:
        ttl = db.ttl(f"active_{message.from_user.id}")
        t = hr.Time(str(ttl), default_unit=hr.Time.Unit.SECOND)
        return await message.reply_text(
            f"""You are already active.
Your session will expire in {t.to_humanreadable()}."""
        )
    shortenedUrl = generate_shortenedUrl(message.from_user.id)
    if not shortenedUrl:
        return await message.reply_text("Something went wrong. Please try again.")
    # if_token_avl = db.get(f"token_{message.from_user.id}")
    # if not if_token_avl:
    # else:
    #     uid, shortenedUrl = if_token_avl.split("|")
    text = f"""
Hey {message.from_user.first_name or message.from_user.username}!

It seems like your Ads token has expired. Please refresh your token and try again.

Token Timeout: 1 hour

What is a token?
This is an Ads token. After viewing 1 ad, you can utilize the bot for the next 1 hour.

Keep the interactions going smoothly! 😊
"""

    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode="markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Click here To Refresh Token", url=shortenedUrl)]]
        ),
    )

@Client.on_message(filters.command("start") & filters.private & filters.regex(r"(?!token_)([0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12})"))
async def start_ntoken(client: Client, message: Message):
    uuid_match = re.search(
        r"(?!token_)([0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12})",
        message.text,
    )
    if uuid_match:
        text = uuid_match.group(1)
    else:
        return await message.reply_text("Invalid UUID format.")

    if message.from_user.id not in ADMINS:
        is_user_active = db.get(f"active_{message.from_user.id}")
        if not is_user_active:
            return await message.reply_text(
                "Your account is deactivated. send /gen to get activate it again."
            )

    fileid = db.get_key(str(text))
    if fileid:
        return await VideoSender.forward_file(
            file_id=fileid, message=message, client=client, uid=text.strip()
        )
    else:
        return await message.reply_text("""your requested file is not available.""")


@Client.on_message(filters.command("start") & filters.private & filters.regex(r"token_([0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12})"))
async def start_token(client: Client, message: Message):
    uuid_match = re.search(
        r"token_([0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12})",
        message.text,
    )
    if uuid_match:
        uuid = uuid_match.group(1).strip()
    else:
        return await message.reply_text("Invalid UUID format.")

    try:
        check_if = await is_user_on_chat(client, FORCE_LINK, message.from_user.id)
    except PeerIdInvalid:
        return await message.reply_text(
            "The bot cannot access the channel/group. Please ensure the bot is an administrator in the FORCE_LINK channel/group."
        )
          if not check_if:
        return await message.reply_text(
            "You haven't joined @AstroBotz or @AstroBotzSupport yet. Please join the channel and then send me the link again.\nThank you!",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("RoldexVerse", url="https://t.me/RoldexVerse"),
                        InlineKeyboardButton(
                            "RoldexVerseChats", url="https://t.me/RoldexVerseChats"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "ReCheck ♻️",
                            url=f"https://t.me/{BOT_USERNAME}?start=token_{uuid}",
                        ),
                    ],
                ]
            ),
        )

    is_user_active = db.get(f"active_{message.from_user.id}")
    if is_user_active:
        ttl = db.ttl(f"active_{message.from_user.id}")
        t = hr.Time(str(ttl), default_unit=hr.Time.Unit.SECOND)
        return await message.reply_text(
            f"""You are already active.
Your session will expire in {t.to_humanreadable()}."""
        )

    if_token_avl = db.get(f"token_{uuid}")
    if not if_token_avl:
        return await generate_token(client, message)

    sender_id, shortenedUrl = if_token_avl.split("|")
    if message.from_user.id != int(sender_id):
        return await message.reply_text(
            "Your token is invalid. Please try again.\n Hit /gen to get a new token."
        )

    set_user_active = db.set(f"active_{message.from_user.id}", time.time(), ex=3600)
    db.delete(f"token_{uuid}")

    if set_user_active:
        return await message.reply_text(
            "Your account is active. It will expire after 1 hour."
        )
      


@Client.on(filters.command("remove") & filters.user(ADMINS) & filters.text)
async def remove(client: Client, message: Message):
    try:
        user_id = message.text.split(" ")[1]  # Extract user ID from command
    except IndexError:
        return await message.reply_text("Please provide a user ID.")

    if db.get(f"check_{user_id}"):
        db.delete(f"check_{user_id}")
        await message.reply_text(f"Removed {user_id} from the list.")
    else:
        await message.reply_text(f"{user_id} is not in the list.")


@Client.on(filters.command("removeall") & filters.user(ADMINS))
async def removeall(client: Client, message: Message):
    remove_all_videos()
    await message.reply_text("Removed all videos from the list.")

@Client.on_message(filters.private & filters.text & lambda client, message: get_urls_from_string(message.text))
async def get_message(client: Client, message: Message):
    await handle_message(client, message)


async def handle_message(client: Client, message: Message):
    urls = get_urls_from_string(message.text)
    if not urls:
        return await message.reply_text("Please enter a valid URL.")

    url = urls[0]  # Use the first URL if multiple are found

    hm = await message.reply_text("Sending you the media, wait...")

    is_spam = db.get(message.from_user.id)
    if is_spam and message.from_user.id not in ADMINS:
        ttl = db.ttl(message.from_user.id)
        t = hr.Time(str(ttl), default_unit=hr.Time.Unit.SECOND)
        return await hm.edit_text(
            f"You are spamming.\n**Please wait {t.to_humanreadable()} and try again.**",
            parse_mode="markdown",
        )

    if_token_avl = db.get(f"active_{message.from_user.id}")
    if not if_token_avl and message.from_user.id not in ADMINS:
        return await hm.edit_text(
            "Your account is deactivated. send /gen to get activate it again."
        )

    shorturl = extract_code_from_url(url)
    if not shorturl:
        return await hm.edit_text("Seems like your link is invalid.")

    fileid = db.get_key(shorturl)
    if fileid:
        uid = db.get_key(f"mid_{fileid}")
        if uid:
            check = await VideoSender.forward_file(
                file_id=fileid, message=message, client=client, edit_message=hm, uid=uid
            )
            if check:
                return

    try:
        data = get_data(url)
    except Exception as e:
        log.exception(f"Error getting data from URL: {url}, {e}")
        return await hm.edit_text(
            "Sorry! API is dead, the link is broken, or an error occurred."
        )

    if not data:
        return await hm.edit_text("Sorry! API is dead or maybe your link is broken.")

    db.set(message.from_user.id, time.monotonic(), ex=60)

    if int(data["sizebytes"]) > 4294967296 and message.from_user.id not in ADMINS:
        return await hm.edit_text(
            f"Sorry! File is too big.\n**I can download only 4 GB and this file is of {data['size']}.**\nRather you can download this file from the link below:\n{data['url']}",
            parse_mode="markdown",
            disable_web_page_preview=True
        )

    sender = VideoSender(
        client=client,
        data=data,
        message=message,
        edit_message=hm,
        url=url,
    )
    asyncio.create_task(sender.send_video())
