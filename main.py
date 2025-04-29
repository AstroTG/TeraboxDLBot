import asyncio
import logging
import time

import asyncio
import logging
import time

import humanreadable as hr
from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMINS, API_HASH, API_ID, BOT_TOKEN, HOST, PASSWORD, PORT
from redis_db import db
from send_media import VideoSender
from terabox import get_data
from tools import extract_code_from_url, get_urls_from_string

log = logging.getLogger(__name__)


@bot.on_message(filters.private & filters.text & lambda client, message: get_urls_from_string(message.text))
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
