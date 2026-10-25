import asyncio
import base64
import time
import os
import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired, PeerIdInvalid
from pyrogram.enums import ChatMemberStatus
from aiohttp import web

from config import (
    API_ID, API_HASH, BOT_TOKEN, DB_CHANNEL_ID, ADMINS,
    FORCE_SUB_IMAGE, ABOUT_IMAGE, AUTO_DELETE_TIME
)
import database as db

if isinstance(ADMINS, str):
    ADMINS = [int(x.strip()) for x in ADMINS.split(",") if x.strip().isdigit()]
elif isinstance(ADMINS, int):
    ADMINS = [ADMINS]
elif not isinstance(ADMINS, (list, set, tuple)):
    ADMINS = []
else:
    ADMINS = [int(x) for x in ADMINS if str(x).isdigit()]

FORWARD_RESTRICTION = True

print(f"Initialized Admin IDs list: {ADMINS}")

print("Initializing Pyrogram Client...")
bot = Client("FileStoreBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def encode_data(data: str) -> str:
    return base64.urlsafe_b64encode(data.encode("ascii")).decode("ascii").strip("=")

def decode_data(data: str) -> str:
    padding = '=' * (4 - len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii")).decode("ascii")

async def check_fsub(client: Client, user_id: int):
    channels = await db.get_fsub_channels()
    unjoined = []
    joined_status = []

    for idx, ch in enumerate(channels, 1):
        try:
            member = await client.get_chat_member(ch["channel_id"], user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                unjoined.append(ch)
                joined_status.append(f"{idx}. {ch['channel_title']} - **Nᴏᴛ Jᴏɪɴᴇᴅ** ❌")
            else:
                joined_status.append(f"{idx}. {ch['channel_title']} - **Jᴏɪɴᴇᴅ** ✅")
        except UserNotParticipant:
            unjoined.append(ch)
            joined_status.append(f"{idx}. {ch['channel_title']} - **Nᴏᴛ Jᴏɪɴᴇᴅ** ❌")
        except (ChatAdminRequired, PeerIdInvalid, Exception):
            joined_status.append(f"{idx}. {ch['channel_title']} - **Jᴏɪɴᴇᴅ** ✅")

    return unjoined, joined_status

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    username = message.from_user.username
    
    await db.add_user(user_id, user_name, username)
    
    args = message.text.split(maxsplit=1)
    param = args[1] if len(args) > 1 else None

    unjoined, status_list = await check_fsub(client, user_id)

    if unjoined:
        buttons = []
        temp_row = []
        for ch in unjoined:
            temp_row.append(InlineKeyboardButton(ch["channel_title"], url=ch["invite_link"]))
            if len(temp_row) == 2:
                buttons.append(temp_row)
                temp_row = []
        if temp_row:
            buttons.append(temp_row)
        
        try_again_data = f"try_again_{param}" if param else "try_again_none"
        buttons.append([InlineKeyboardButton("• Tʀʏ Aɢᴀɪɴ •", callback_data=try_again_data)])

        text = (
            "**Hɪɪ..! ⚡**\n\n"
            "**Pʟᴇᴀsᴇ Jᴏɪɴ Aʟʟ Oғ Oᴜʀ Cʜᴀɴɴᴇʟs Fɪʀsᴛ Tʜᴇɴ Cʟɪᴄᴋ Oɴ Tʀʏ Aɢᴀɪɴ...❗️**\n\n"
            "**Cʜᴀɴɴᴇʟ Sᴜʙsᴄʀɪᴘᴛɪᴏɴ Sᴛᴀᴛᴜs:**\n\n" + "\n".join(status_list)
        )

        await message.reply_photo(
            photo=FORCE_SUB_IMAGE.strip(),
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if not param:
        text = (
            f"**Wᴇʟᴄᴏᴍᴇ {user_name}!**\n\n"
            "**I ᴀᴍ A Fɪʟᴇ Sᴛᴏʀᴇ Bᴏᴛ.**\n\n"
            "**Pᴏᴡᴇʀᴇᴅ Bʏ: @Aero_Unity**"
        )
        buttons = [
            [InlineKeyboardButton("• Aʙᴏᴜᴛ •", callback_data="about_menu"),
             InlineKeyboardButton("• Cʟᴏsᴇ •", callback_data="close")]
        ]
        await message.reply_photo(
            photo=ABOUT_IMAGE.strip(),
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    checking_msg = await message.reply_photo(
        photo=FORCE_SUB_IMAGE.strip(),
        caption="**Checking subscription...**"
    )
    
    await asyncio.sleep(1)
    try:
        await checking_msg.delete()
    except Exception:
        pass
        
    await send_stored_files(client, message.chat.id, param)

async def send_stored_files(client: Client, chat_id: int, param: str):
    try:
        data = decode_data(param)
        if data.startswith("BATCH_"):
            _, start_id, end_id = data.split("_")
            msg_ids = list(range(int(start_id), int(end_id) + 1))
        else:
            msg_ids = [int(data)]
    except Exception:
        await client.send_message(chat_id, "‼️ **Iɴᴠᴀʟɪᴅ ʟɪɴᴋ ᴏʀ ᴘᴀʀᴀᴍᴇᴛᴇʀ !**")
        return

    sent_messages = []
    file_button = InlineKeyboardMarkup([[InlineKeyboardButton("• Uᴘᴅᴀᴛᴇs •", url="https://t.me/Aero_Unity")]])

    for msg_id in msg_ids:
        try:
            msg = await client.copy_message(
                chat_id=chat_id,
                from_chat_id=DB_CHANNEL_ID,
                message_id=msg_id,
                reply_markup=file_button,
                protect_content=FORWARD_RESTRICTION
            )
            
            if msg.caption:
                try:
                    await client.edit_message_caption(
                        chat_id=chat_id,
                        message_id=msg.id,
                        caption=f"**{msg.caption}**",
                        reply_markup=file_button
                    )
                except Exception:
                    pass

            sent_messages.append(msg)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Error copying message {msg_id}: {e}")

    if sent_messages:
        last_msg = sent_messages[-1]
        warn_msg = await client.send_message(
            chat_id=chat_id,
            text=f"**Tʜɪs Fɪʟᴇ ɪs ᴅᴇʟᴇᴛɪɴɢ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ɪɴ {AUTO_DELETE_TIME // 60} ᴍɪɴᴜᴛᴇs. Fᴏʀᴡᴀʀᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ Sᴀᴠᴇᴅ Mᴇssᴀɢᴇs..!**",
            reply_to_message_id=last_msg.id
        )
        
        asyncio.create_task(delete_files_after_delay(client, chat_id, sent_messages, warn_msg, AUTO_DELETE_TIME))

async def delete_files_after_delay(client, chat_id, messages, warn_msg, delay):
    await asyncio.sleep(delay)
    for msg in messages:
        try:
            await client.delete_messages(chat_id, msg.id)
        except Exception:
            pass
    try:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=warn_msg.id,
            text="**Your files have been deleted!**"
        )
    except Exception:
        pass
        
@bot.on_callback_query(filters.regex(r"^try_again_"))
async def try_again_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    param = callback.data.split("try_again_")[1]
    param = None if param == "none" else param

    unjoined, status_list = await check_fsub(client, user_id)

    if unjoined:
        await callback.answer("›› ‼️ ʟᴏᴏᴋs ʟɪᴋᴇ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴛᴏ ᴏᴜʀ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ", show_alert=True)
        buttons = []
        temp_row = []
        for ch in unjoined:
            temp_row.append(InlineKeyboardButton(ch["channel_title"], url=ch["invite_link"]))
            if len(temp_row) == 2:
                buttons.append(temp_row)
                temp_row = []
        if temp_row:
            buttons.append(temp_row)
        
        try_again_data = f"try_again_{param}" if param else "try_again_none"
        buttons.append([InlineKeyboardButton("• Tʀʏ Aɢᴀɪɴ •", callback_data=try_again_data)])

        text = (
            "**Hɪɪ..! ⚡**\n\n"
            " **Pʟᴇᴀsᴇ Jᴏɪɴ Aʟʟ Oғ Oᴜʀ Cʜᴀɴɴᴇʟs Fɪʀsᴛ Tʜᴇɴ Cʟɪᴄᴋ Oɴ Tʀʏ Aɢᴀɪɴ...❗️**\n\n"
            "**Cʜᴀɴɴᴇʟ Sᴜʙsᴄʀɪᴘᴛɪᴏɴ Sᴛᴀᴛᴜs:**\n\n" + "\n".join(status_list)
        )
        
        try:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            pass
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    if param:
        checking_msg = await callback.message.reply_photo(
            photo=FORCE_SUB_IMAGE.strip(),
            caption="⏳ **Checking subscription...**\n\n**Wait a sec...**"
        )
        await asyncio.sleep(1)
        try:
            await checking_msg.delete()
        except Exception:
            pass
        await send_stored_files(client, callback.message.chat.id, param)
    else:
        checking_msg = await callback.message.reply_photo(
            photo=FORCE_SUB_IMAGE.strip(),
            caption="**Checking subscription...**"
        )
        await asyncio.sleep(2)
        try:
            await checking_msg.delete()
        except Exception:
            pass

        text = (
            f"**Wᴇʟᴄᴏᴍᴇ {user_name}!**\n\n"
            "**I ᴀᴍ A Fɪʟᴇ Sᴛᴏʀᴇ Bᴏᴛ.**\n\n"
            "**Pᴏᴡᴇʀᴇᴅ Bʏ: @Aero_Unity**"
        )
        buttons = [
            [InlineKeyboardButton("• Aʙᴏᴜᴛ •", callback_data="about_menu"),
             InlineKeyboardButton("• Cʟᴏsᴇ •", callback_data="close")]
        ]
        await callback.message.reply_photo(
            photo=ABOUT_IMAGE.strip(),
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@bot.on_callback_query(filters.regex("close"))
async def close_callback(client: Client, callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass

@bot.on_callback_query(filters.regex("about_menu"))
async def about_menu_callback(client: Client, callback: CallbackQuery):
    text = (
        "**Aʙᴏᴜᴛ Mᴇ...**\n\n"
        "›› **Mᴀᴅᴇ Fᴏʀ : @Ongoing_Donghua_Aero**\n"
        "›› **Oᴡɴᴇʀ : @Mr_Mohammed_29**\n"
        "›› **Pᴏᴡᴇʀᴇᴅ Bʏ : @Aero_Unity**\n"
        "›› **Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ : @Coders_Grp**\n\n"
        "**Aᴅɪᴏs !!**"
    )
    buttons = [
        [InlineKeyboardButton("• Hᴏᴍᴇ •", callback_data="about_back"),
         InlineKeyboardButton("• Cʟᴏsᴇ •", callback_data="close")]
    ]
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass

@bot.on_callback_query(filters.regex("about_back"))
async def about_back_callback(client: Client, callback: CallbackQuery):
    user_name = callback.from_user.first_name
    text = (
        f"**Wᴇʟᴄᴏᴍᴇ {user_name}!**\n\n"
        "**I ᴀᴍ A Fɪʟᴇ Sᴛᴏʀᴇ Bᴏᴛ.**\n\n"
        "**Pᴏᴡᴇʀᴇᴅ Bʏ: @Aero_Unity**"
    )
    buttons = [
        [InlineKeyboardButton("• Aʙᴏᴜᴛ •", callback_data="about_menu"),
         InlineKeyboardButton("• Cʟᴏsᴇ •", callback_data="close")]
    ]
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        pass

@bot.on_message(filters.command("restriction_on") & filters.user(ADMINS))
async def restriction_on_cmd(client: Client, message: Message):
    global FORWARD_RESTRICTION
    FORWARD_RESTRICTION = True
    await message.reply_text("🔒 **Forwarding & saving restriction has been ENABLED.**")

@bot.on_message(filters.command("restriction_off") & filters.user(ADMINS))
async def restriction_off_cmd(client: Client, message: Message):
    global FORWARD_RESTRICTION
    FORWARD_RESTRICTION = False
    await message.reply_text("🔓 **Forwarding & saving restriction has been DISABLED.**")

@bot.on_message(filters.command("genlink") & filters.user(ADMINS))
async def genlink_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to a file or message to generate a link.")
        return

    reply = message.reply_to_message
    target_msg_id = None

    if reply.forward_from_chat and reply.forward_from_chat.id == DB_CHANNEL_ID:
        target_msg_id = reply.forward_from_message_id
    elif reply.chat.id == DB_CHANNEL_ID:
        target_msg_id = reply.id
    else:
        target_msg_id = reply.id

    if not target_msg_id:
        await message.reply_text("❌ Could not determine the original database message ID.")
        return

    encoded_id = encode_data(str(target_msg_id))
    bot_username = (await client.get_me()).username
    link = f"https://t.me/{bot_username}?start={encoded_id}"

    await message.reply_text(f"🔗 **Generated File Link:**\n\n`{link}`", disable_web_page_preview=True)

@bot.on_message(filters.command("batch") & filters.user(ADMINS))
async def batch_handler(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("📌 **Usage:** `/batch [start_msg_id_or_link] [end_msg_id_or_link]`")
        return

    def extract_id(arg: str) -> str:
        # If user passed a full Telegram URL, extract the last part (message ID)
        if "t.me/" in arg:
            return arg.strip("/").split("/")[-1]
        return arg

    start_id = extract_id(args[1])
    end_id = extract_id(args[2])

    if not start_id.isdigit() or not end_id.isdigit():
        await message.reply_text("❌ **Invalid message IDs or links provided! Please use numbers or valid message URLs.**")
        return

    raw_str = f"BATCH_{start_id}_{end_id}"
    encoded = encode_data(raw_str)

    bot_username = (await client.get_me()).username
    link = f"https://t.me/{bot_username}?start={encoded}"

    await message.reply_text(f"📦 **Generated Batch Link:**\n\n`{link}`", disable_web_page_preview=True)

@bot.on_message(filters.command("addforcesub") & filters.user(ADMINS))
async def add_fsub_cmd(client: Client, message: Message):
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply_text("📌 **Usage:** `/addforcesub [Channel ID] [Invite Link] [Channel Title]`")
        return

    try:
        ch_id = int(args[1])
        invite_link = args[2]
        title = args[3]
        await db.add_fsub_channel(ch_id, title, invite_link)
        await message.reply_text(f"✅ Added Force Sub Channel: **{title}**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command("removeforcesub") & filters.user(ADMINS))
async def rm_fsub_cmd(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("📌 **Usage:** `/removeforcesub [Channel ID]`")
        return

    try:
        ch_id = int(args[1])
        await db.remove_fsub_channel(ch_id)
        await message.reply_text(f"✅ Removed channel `{ch_id}` from Force Sub list.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.command("forcesublist") & filters.user(ADMINS))
async def list_fsub_cmd(client: Client, message: Message):
    channels = await db.get_fsub_channels()
    if not channels:
        await message.reply_text("ℹ️ No force sub channels added.")
        return

    text = "📋 **Force Sub Channels List:**\n\n"
    for ch in channels:
        text += f"• **Title:** {ch['channel_title']}\n  **ID:** `{ch['channel_id']}`\n  **Link:** {ch['invite_link']}\n\n"

    await message.reply_text(text, disable_web_page_preview=True)

@bot.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_cmd(client: Client, message: Message):
    loading_msg = await message.reply_text("**Extracting stats...**")

    users_data = await db.get_all_users_data()
    total_users = len(users_data)

    stats_text = f"📊 **Bᴏᴛ Sᴛᴀᴛɪsᴛɪᴄs**\n\n👤 **Tᴏᴛᴀʟ Uꜱᴇʀꜱ:** `{total_users}`\n\n"

    for user_doc in users_data:
        uid = user_doc.get("user_id") or user_doc.get("id") or user_doc.get("_id")
        if not uid:
            continue

        u_name = user_doc.get("first_name") or "User"
        saved_username = user_doc.get("username")
        
        if saved_username:
            display_identifier = f"@{saved_username}"
        else:
            try:
                user_obj = await client.get_users(uid)
                if user_obj:
                    if user_obj.username:
                        display_identifier = f"@{user_obj.username}"
                    elif user_obj.first_name:
                        display_identifier = user_obj.first_name
                    else:
                        display_identifier = u_name
                else:
                    display_identifier = u_name
            except Exception:
                display_identifier = u_name

        joined_date = user_doc.get("date") or datetime.datetime.now().strftime("%Y-%m-%d")
        day_name = user_doc.get("day") or datetime.datetime.now().strftime("%A")

        stats_text += f"• **[{display_identifier}](tg://user?id={uid})** **[`{uid}`]** **[`{joined_date}`]** **[`{day_name}`]**\n"

    buttons = [[InlineKeyboardButton("• Cʟᴏsᴇ •", callback_data="close")]]
    
    try:
        await loading_msg.edit_text(stats_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    except Exception:
        await message.reply_text(stats_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@bot.on_message(filters.command("ping") & filters.private)
async def ping_handler(client: Client, message: Message):
    user_id = message.from_user.id

    unjoined, status_list = await check_fsub(client, user_id)
    if unjoined:
        # Do not show anything if they haven't joined yet
        return
        
    start_time = time.time()
    sent_msg = await message.reply_text("Pinging...")
    end_time = time.time()
    ping_time = round((end_time - start_time) * 1000, 2)
    await sent_msg.edit_text(f"🏓 **Pong!**\n`{ping_time}ms`")
    
@bot.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("📌 **Reply to a message with `/broadcast`, `/broadcast pin`, or `/broadcast unpin`**")
        return

    reply = message.reply_to_message
    args = message.text.lower().split()
    should_pin = "pin" in args
    should_unpin = "unpin" in args
    
    users = await db.get_all_users()
    await message.reply_text(f"📢 **Starting broadcast to `{len(users)}` users...**")

    success = 0
    failed = 0

    for user_id in users:
        try:
            # Forwarding the message preserves text, media, formatting, AND inline buttons entirely without errors
            sent_msg = await reply.forward(chat_id=user_id)
            
            if should_pin:
                await sent_msg.pin(both_sides=True)
            elif should_unpin:
                try:
                    await client.unpin_chat_message(chat_id=user_id)
                except Exception:
                    pass

            success += 1
            await asyncio.sleep(0.05)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Broadcast error for user {user_id}: {e}")
            failed += 1

    # Send completion summary in bold
    await message.reply_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"• **Successful:** `{success}`\n"
        f"• **Failed:** `{failed}`"
    )

async def handle_ping(request):
    return web.Response(text="Bot is running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_web_server())
    print("Web Server started successfully.")

    print("Testing MongoDB connection...")
    try:
        loop.run_until_complete(db.get_fsub_channels())
        print("MongoDB connection verified successfully!")
    except Exception as e:
        print(f"CRITICAL: MongoDB connection failed: {e}")

    with bot:
        me = bot.get_me()
        print(f"SUCCESS! Bot is online as: @{me.username} (ID: {me.id})")
        print(f"Authorized Admin IDs: {ADMINS}")
        print("Bot is up and running successfully!")
        idle()
