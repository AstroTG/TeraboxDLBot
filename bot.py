import asyncio
import logging
import time

import humanreadable as hr
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from config import ADMINS, API_HASH, API_ID, BOT_TOKEN, BOT_USERNAME, FORCE_LINK
from redis_db import db
from send_media import VideoSender
from tools import generate_shortenedUrl, is_user_on_chat, remove_all_videos

log = logging.getLogger(__name__)

bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


@bot.on(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    reply_text = """
Hello there! I'm your friendly video downloader bot specially designed to fetch videos from Terabox. Share the Terabox link with me, and I'll swiftly get started on downloading it for you.

Let's make your video experience even better!
"""
    await message.reply_text(
        reply_text,
        disable_web_page_preview=True,
        parse_mode="markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Website Source Code",
                        url="https://github.com/r0ld3x/terabox-app",
                    ),
                    InlineKeyboardButton(
                        "Bot Source Code",
                        url="https://github.com/r0ld3x/terabox-downloader-bot",
                    ),
                ],
                [
                    InlineKeyboardButton("Channel ", url="https://t.me/RoldexVerse"),
                    InlineKeyboardButton("Group ", url="https://t.me/RoldexVerseChats"),
                ],
            ]
        ),
    )


@bot.on(filters.command("gen") & filters.private)
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

@bot.on(
    filters.command("start")
    & filters.private
    & filters.regex(
        r"(?!token_)([0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12})"
    )
)
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


@bot.on(
    filters.command("start")
    & filters.private
    & filters.regex(
        r"token_([0-9a-f]{8}-[0-9a-f]{4}-[0-5][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12})"
    )
)
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
            "You haven't joined @RoldexVerse or @RoldexVerseChats yet. Please join the channel and then send me the link again.\nThank you!",
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
      


@bot.on(
    events.NewMessage(
        pattern="/remove (.*)",
        incoming=True,
        outgoing=False,
        from_users=ADMINS,
    )
)
async def remove(m: UpdateNewMessage):
    user_id = m.pattern_match.group(1)
    if db.get(f"check_{user_id}"):
        db.delete(f"check_{user_id}")
        await m.reply(f"Removed {user_id} from the list.")
    else:
        await m.reply(f"{user_id} is not in the list.")


@bot.on(
    events.NewMessage(
        pattern="/removeall",
        incoming=True,
        outgoing=False,
        from_users=ADMINS,
    )
)
async def removeall(m: UpdateNewMessage):
    remove_all_videos()
    return await m.reply("Removed all videos from the list.")


bot.start(bot_token=BOT_TOKEN)
bot.run_until_disconnected()
