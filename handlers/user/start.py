# Copyright (c) 2021-2025 @thealphabotz - All Rights Reserved.

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from utils import ButtonManager, helper
from utils.token_verification import TokenVerification
import config
import asyncio
import logging
import base64
import re
from datetime import datetime
import pytz
from ..utils.message_delete import schedule_message_deletion

logger = logging.getLogger(__name__)
db = Database()
button_manager = ButtonManager()
token_verification = TokenVerification()

async def decode_codex_link(encoded_string: str) -> tuple:
    """Decode CodeXBotz link format"""
    try:
        string_bytes = base64.b64decode(encoded_string.encode("ascii"))
        decoded = string_bytes.decode("ascii")
        if decoded.startswith("get-"):
            parts = decoded.split("-")
            if len(parts) == 2:
                msg_id = int(parts[1]) // abs(config.DB_CHANNEL_ID)
                return False, [msg_id]
            elif len(parts) == 3:
                first_id = int(parts[1]) // abs(config.DB_CHANNEL_ID)
                last_id = int(parts[2]) // abs(config.DB_CHANNEL_ID)
                return True, list(range(first_id, last_id + 1))
        return False, []
    except Exception as e:
        logger.error(f"Error decoding CodeXBotz link: {str(e)}")
        return False, []

async def send_file_message(client: Client, chat_id: int, message_id: int, protect_content: bool = False) -> Message:
    """Send file message with auto-delete handling"""
    try:
        msg = await client.copy_message(
            chat_id=chat_id,
            from_chat_id=config.DB_CHANNEL_ID,
            message_id=message_id,
            protect_content=protect_content
        )
        
        if msg and config.AUTO_DELETE_TIME:
            delete_time = config.AUTO_DELETE_TIME
            info_msg = await msg.reply_text(
                f"⏳ **Auto Delete Information**\n\n"
                f"➜ This file will be deleted in {delete_time} minutes.\n"
                f"➜ Forward this file to your saved messages or another chat to save it permanently.",
                protect_content=protect_content
            )
            if info_msg and info_msg.id:
                asyncio.create_task(schedule_message_deletion(
                    client, chat_id, [msg.id, info_msg.id], delete_time
                ))
        return msg
    except Exception as e:
        logger.error(f"Error sending file message: {str(e)}")
        return None

async def handle_force_sub(client: Client, message: Message) -> bool:
    """Handle force subscription check"""
    try:
        if config.FORCE_SUB_CHANNEL != 0 or config.FORCE_SUB_CHANNEL_2 != 0:
            user_id = message.from_user.id
            for channel_id in [config.FORCE_SUB_CHANNEL, config.FORCE_SUB_CHANNEL_2]:
                if channel_id != 0:
                    try:
                        await client.get_chat_member(channel_id, user_id)
                    except Exception:
                        buttons = button_manager.force_sub_button()
                        await message.reply_text(
                            config.Messages.FORCE_SUB_TEXT,
                            reply_markup=buttons,
                            protect_content=config.PRIVACY_MODE
                        )
                        return False
        return True
    except Exception as e:
        logger.error(f"Error checking force subscription: {str(e)}")
        return False

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    try:
        # Add user to database
        await db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        
        user_mention = message.from_user.mention if message.from_user.username else message.from_user.first_name
        
        # Handle command parameters
        if len(message.command) > 1:
            command = message.command[1]
            
            # Handle verification links
            if command.startswith("verify_"):
                try:
                    _, user_id, token = command.split("_", 2)
                    user_id = int(user_id)
                    
                    # Verify correct user
                    if user_id != message.from_user.id:
                        await message.reply_text(
                            "❌ This verification link is for another user.\n"
                            "Please request your own verification link.",
                            protect_content=config.PRIVACY_MODE
                        )
                        return
                    
                    # Validate token
                    is_valid, response_msg = await token_verification.validate_and_verify_token(user_id, token)
                    await message.reply_text(
                        response_msg,
                        protect_content=config.PRIVACY_MODE
                    )
                    
                    if is_valid:
                        # Send welcome message
                        await message.reply_text(
                            config.Messages.START_TEXT.format(
                                bot_name=config.BOT_NAME,
                                user_mention=user_mention
                            ),
                            reply_markup=button_manager.start_button(),
                            protect_content=config.PRIVACY_MODE
                        )
                    return
                except Exception as e:
                    logger.error(f"Error in token verification: {str(e)}")
                    await message.reply_text(
                        "❌ An error occurred during verification.\n"
                        "Please try again or contact support.",
                        protect_content=config.PRIVACY_MODE
                    )
                    return
            
            # Check force subscription and verification
            if not await handle_force_sub(client, message):
                return
                
            if config.TOKEN_SYSTEM and not await token_verification.is_verified(message.from_user.id):
                buttons, _ = await token_verification.get_verification_buttons(message.from_user.id)
                await message.reply_text(
                    "🔒 **Verification Required**\n\n"
                    "Please verify your account to access files.",
                    reply_markup=buttons,
                    protect_content=config.PRIVACY_MODE
                )
                return
            
            # Handle CodeXBotz links
            try:
                is_batch, message_ids = await decode_codex_link(command)
                
                if message_ids:
                    if is_batch:
                        # Handle batch messages
                        status_msg = await message.reply_text(
                            f"🔄 **Processing Batch Download**\n\n"
                            f"📦 Total Files: {len(message_ids)}\n"
                            f"⏳ Please wait...",
                            protect_content=config.PRIVACY_MODE
                        )
                        
                        success_count = 0
                        failed_count = 0
                        sent_msgs = []
                        
                        for msg_id in message_ids:
                            msg = await send_file_message(client, message.chat.id, msg_id, config.PRIVACY_MODE)
                            if msg:
                                sent_msgs.append(msg.id)
                                success_count += 1
                            else:
                                failed_count += 1
                        
                        status_text = (
                            f"✅ **Batch Download Complete**\n\n"
                            f"📥 Successfully sent: {success_count} files\n"
                            f"❌ Failed: {failed_count} files"
                        )
                        await status_msg.edit_text(status_text)
                        return
                    else:
                        # Handle single message
                        msg = await send_file_message(client, message.chat.id, message_ids[0], config.PRIVACY_MODE)
                        if not msg:
                            await message.reply_text(
                                "❌ File not found or has been deleted!", 
                                protect_content=config.PRIVACY_MODE
                            )
                        return
                
            except Exception as e:
                logger.error(f"Error processing CodeXBotz link: {str(e)}")
                await message.reply_text(
                    "❌ Invalid or expired link!", 
                    protect_content=config.PRIVACY_MODE
                )
                return
            
            # Handle batch downloads
            if command.startswith("batch_"):
                try:
                    batch_uuid = command.replace("batch_", "")
                    batch_data = await db.get_batch(batch_uuid)
                    
                    if not batch_data:
                        await message.reply_text(
                            "❌ Batch not found or has been deleted!", 
                            protect_content=config.PRIVACY_MODE
                        )
                        return
                    
                    status_msg = await message.reply_text(
                        f"🔄 **Processing Batch Download**\n\n"
                        f"📦 Total Files: {len(batch_data['files'])}\n"
                        f"⏳ Please wait...",
                        protect_content=config.PRIVACY_MODE
                    )
                    
                    success_count = 0
                    failed_count = 0
                    sent_msgs = []
                    
                    for file_uuid in batch_data["files"]:
                        file_data = await db.get_file(file_uuid)
                        if file_data and "message_id" in file_data:
                            msg = await send_file_message(
                                client, 
                                message.chat.id, 
                                file_data["message_id"], 
                                config.PRIVACY_MODE
                            )
                            if msg:
                                sent_msgs.append(msg.id)
                                success_count += 1
                            else:
                                failed_count += 1
                    
                    if success_count > 0:
                        await db.increment_batch_downloads(batch_uuid)
                    
                    status_text = (
                        f"✅ **Batch Download Complete**\n\n"
                        f"📥 Successfully sent: {success_count} files\n"
                        f"❌ Failed: {failed_count} files"
                    )
                    await status_msg.edit_text(status_text)
                    return
                    
                except Exception as e:
                    logger.error(f"Error processing batch: {str(e)}")
                    await message.reply_text(
                        "❌ An error occurred processing the batch!", 
                        protect_content=config.PRIVACY_MODE
                    )
                    return
            
            # Handle single file downloads
            try:
                file_uuid = command
                file_data = await db.get_file(file_uuid)
                
                if not file_data:
                    await message.reply_text(
                        "❌ File not found or has been deleted!", 
                        protect_content=config.PRIVACY_MODE
                    )
                    return
                
                msg = await send_file_message(
                    client, 
                    message.chat.id, 
                    file_data["message_id"], 
                    config.PRIVACY_MODE
                )
                
                if msg:
                    await db.increment_downloads(file_uuid)
                else:
                    await message.reply_text(
                        "❌ Error sending file!", 
                        protect_content=config.PRIVACY_MODE
                    )
                    
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                await message.reply_text(
                    "❌ An error occurred processing the file!", 
                    protect_content=config.PRIVACY_MODE
                )
                
        else:
            # Regular start command
            if config.TOKEN_SYSTEM and not await token_verification.is_verified(message.from_user.id):
                buttons, token = await token_verification.get_verification_buttons(message.from_user.id)
                if buttons:
                    await message.reply_text(
                        "🔒 **Verification Required**\n\n"
                        "To access files and use this bot, please verify yourself:\n\n"
                        "1️⃣ Click the verification button below\n"
                        "2️⃣ Your verification will be valid for 12 hours\n"
                        "3️⃣ You'll need to verify again after expiration\n\n"
                        "Need help? Click the 'How to Verify?' button below.",
                        reply_markup=buttons,
                        protect_content=config.PRIVACY_MODE
                    )
                    return
            
            # Show welcome message
            await message.reply_text(
                config.Messages.START_TEXT.format(
                    bot_name=config.BOT_NAME,
                    user_mention=user_mention
                ),
                reply_markup=button_manager.start_button(),
                protect_content=config.PRIVACY_MODE
            )
            
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")
        await message.reply_text(
            "❌ An error occurred. Please try again later.",
            protect_content=config.PRIVACY_MODE
        )

# @thealphabotz | Join @thealphabotz on Telegram
