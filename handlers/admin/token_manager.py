from pyrogram import Client, filters
from pyrogram.types import Message
import config
from utils.token_verification import TokenVerification
from database import Database
from utils import is_admin
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
db = Database()
token_verification = TokenVerification()

@Client.on_message(filters.command("token_system"))
async def token_system_command(client: Client, message: Message):
    """Admin command to enable/disable token system"""
    if not await is_admin(message):
        return
        
    try:
        if len(message.command) > 1:
            param = message.command[1].lower()
            
            if param in ["on", "true", "1", "enable"]:
                config.TOKEN_SYSTEM = True
                await message.reply_text("✅ Token verification system has been **enabled**.")
            elif param in ["off", "false", "0", "disable"]:
                config.TOKEN_SYSTEM = False
                await message.reply_text("❌ Token verification system has been **disabled**.")
            else:
                await message.reply_text(
                    "❓ Invalid parameter. Use:\n"
                    "/token_system on - to enable\n"
                    "/token_system off - to disable"
                )
        else:
            status = "enabled" if config.TOKEN_SYSTEM else "disabled"
            await message.reply_text(
                f"ℹ️ Token verification system is currently **{status}**.\n\n"
                f"Use:\n"
                f"/token_system on - to enable\n"
                f"/token_system off - to disable"
            )
    except Exception as e:
        logger.error(f"Error in token_system command: {str(e)}")
        await message.reply_text("❌ An error occurred.")

@Client.on_message(filters.command("token_time"))
async def token_time_command(client: Client, message: Message):
    """Admin command to set token validity time"""
    if not await is_admin(message):
        return
        
    try:
        if len(message.command) > 1:
            try:
                hours = int(message.command[1])
                if hours < 1:
                    await message.reply_text("❌ Token time must be at least 1 hour.")
                    return
                
                config.TOKEN_TIME = hours
                await message.reply_text(f"✅ Token validity time set to **{hours} hours**.")
            except ValueError:
                await message.reply_text("❌ Please provide a valid number of hours.")
        else:
            await message.reply_text(
                f"ℹ️ Current token validity time is **{config.TOKEN_TIME} hours**.\n\n"
                f"Use /token_time <hours> to change."
            )
    except Exception as e:
        logger.error(f"Error in token_time command: {str(e)}")
        await message.reply_text("❌ An error occurred.")

@Client.on_message(filters.command("verify_user"))
async def verify_user_command(client: Client, message: Message):
    """Admin command to manually verify a user"""
    if not await is_admin(message):
        return
        
    try:
        if len(message.command) > 1:
            try:
                user_id = int(message.command[1])
                token = await token_verification.generate_token(user_id)
                
                if await token_verification.store_verification(user_id, token):
                    await message.reply_text(f"✅ User ID {user_id} has been manually verified.")
                else:
                    await message.reply_text("❌ Failed to verify user.")
            except ValueError:
                await message.reply_text("❌ Please provide a valid user ID.")
        else:
            await message.reply_text("❌ Please provide a user ID to verify.")
    except Exception as e:
        logger.error(f"Error in verify_user command: {str(e)}")
        await message.reply_text("❌ An error occurred.")

@Client.on_message(filters.command("unverify_user"))
async def unverify_user_command(client: Client, message: Message):
    """Admin command to manually unverify a user"""
    if not await is_admin(message):
        return
        
    try:
        if len(message.command) > 1:
            try:
                user_id = int(message.command[1])
                result = await token_verification.collection.delete_one({"user_id": user_id})
                
                if result.deleted_count > 0:
                    await message.reply_text(f"✅ User ID {user_id} has been unverified.")
                else:
                    await message.reply_text(f"❌ User ID {user_id} was not verified.")
            except ValueError:
                await message.reply_text("❌ Please provide a valid user ID.")
        else:
            await message.reply_text("❌ Please provide a user ID to unverify.")
    except Exception as e:
        logger.error(f"Error in unverify_user command: {str(e)}")
        await message.reply_text("❌ An error occurred.")

@Client.on_message(filters.command("verify_stats"))
async def verify_stats_command(client: Client, message: Message):
    """Admin command to get token verification statistics"""
    if not await is_admin(message):
        return
        
    try:
        total_verified = await token_verification.collection.count_documents({})
        
        now = datetime.now(pytz.UTC)
        active_verified = await token_verification.collection.count_documents({
            "expires_at": {"$gt": now}
        })
        
        await message.reply_text(
            f"📊 **Token Verification Statistics**\n\n"
            f"Total verified users: {total_verified}\n"
            f"Currently active verifications: {active_verified}\n"
            f"Verification validity: {config.TOKEN_TIME} hours\n"
            f"System status: {'Enabled' if config.TOKEN_SYSTEM else 'Disabled'}"
        )
    except Exception as e:
        logger.error(f"Error in verify_stats command: {str(e)}")
        await message.reply_text("❌ An error occurred.")
