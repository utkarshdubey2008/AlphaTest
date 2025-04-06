import uuid
import aiohttp
import logging
import pytz
from datetime import datetime, timedelta
from typing import Tuple, Optional
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import Database

logger = logging.getLogger(__name__)
db = Database()

class TokenVerification:
    def __init__(self):
        self.collection = db.db.verified_users
    
    async def generate_token(self, user_id: int) -> str:
        """Generate a unique token for user verification"""
        token = str(uuid.uuid4())[:12]  # Using shorter token for better UX
        return token
    
    async def create_verification_link(self, user_id: int, token: str) -> str:
        """Create a verification link with user_id and token"""
        # Format: https://t.me/bot_username?start=verify_{user_id}_{token}
        base_link = f"https://t.me/{config.BOT_USERNAME}?start=verify_{user_id}_{token}"
        return base_link
    
    async def shorten_url(self, long_url: str) -> str:
        """Shorten URL using the configured URL shortener service"""
        shortener_url = config.SHORTENER_URL.lower()
        api_token = config.SHORTENER_API_TOKEN
        
        if not api_token or not shortener_url:
            return long_url
            
        api_url = ""
        if "modijiurl" in shortener_url:
            api_url = f"https://api.modijiurl.com/api?api={api_token}&url={long_url}&format=text"
        elif "shrinkearn" in shortener_url:
            api_url = f"https://shrinkearn.com/api?api={api_token}&url={long_url}&format=text"
        elif "indianshortner" in shortener_url:
            api_url = f"https://indianshortner.com/api?api={api_token}&url={long_url}&format=text"
        else:
            return long_url
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        shortened_url = await response.text()
                        shortened_url = shortened_url.strip()
                        if shortened_url.startswith("http"):
                            return shortened_url
                    return long_url
        except Exception as e:
            logger.error(f"Error shortening URL: {str(e)}")
            return long_url
    
    async def store_verification(self, user_id: int, token: str) -> bool:
        """Store or update user verification status in database"""
        try:
            now = datetime.now(pytz.UTC)
            expires_at = now + timedelta(hours=config.TOKEN_TIME)
            verification_data = {
                "user_id": user_id,
                "token": token,
                "created_at": now,
                "expires_at": expires_at,
                "is_verified": False,
                "verified_at": None,
                "verification_attempts": 0,
                "last_activity": now
            }
            
            await self.collection.update_one(
                {"user_id": user_id},
                {"$set": verification_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error storing verification: {str(e)}")
            return False

    async def validate_and_verify_token(self, user_id: int, token: str) -> Tuple[bool, str]:
        """Validate token and update verification status"""
        try:
            user_data = await self.collection.find_one({"user_id": user_id})
            if not user_data:
                return False, "No verification request found. Please start over."
            
            now = datetime.now(pytz.UTC)
            stored_token = user_data.get("token")
            expires_at = user_data.get("expires_at")
            is_verified = user_data.get("is_verified", False)
            
            if is_verified:
                return True, "You are already verified!"
            
            if now > expires_at:
                await self.collection.delete_one({"user_id": user_id})
                return False, "Verification link has expired. Please request a new one."
            
            if stored_token != token:
                await self.collection.update_one(
                    {"user_id": user_id},
                    {"$inc": {"verification_attempts": 1}}
                )
                return False, "Invalid verification token. Please check your link."
            
            # Update verification status
            verification_update = {
                "is_verified": True,
                "verified_at": now,
                "last_activity": now
            }
            
            await self.collection.update_one(
                {"user_id": user_id},
                {"$set": verification_update}
            )
            
            return True, f"✅ Verification successful! Your access is valid for {config.TOKEN_TIME} hours."
            
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False, "An error occurred during verification. Please try again."

    async def is_verified(self, user_id: int) -> bool:
        """Check if user is verified and token has not expired"""
        try:
            if not config.TOKEN_SYSTEM:
                return True
            
            user_data = await self.collection.find_one({"user_id": user_id})
            if not user_data:
                return False
            
            now = datetime.now(pytz.UTC)
            expires_at = user_data.get("expires_at")
            is_verified = user_data.get("is_verified", False)
            
            if not is_verified or now > expires_at:
                # Cleanup expired verification
                if now > expires_at:
                    await self.collection.delete_one({"user_id": user_id})
                return False
            
            # Update last activity
            await self.collection.update_one(
                {"user_id": user_id},
                {"$set": {"last_activity": now}}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error checking verification status: {str(e)}")
            return False
    
    async def get_verification_buttons(self, user_id: int) -> Optional[Tuple[InlineKeyboardMarkup, str]]:
        """Generate verification buttons for unverified users"""
        try:
            token = await self.generate_token(user_id)
            long_url = await self.create_verification_link(user_id, token)
            shortened_url = await self.shorten_url(long_url)
            
            if not await self.store_verification(user_id, token):
                return None, None
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Click Here to Verify", url=shortened_url)],
                [InlineKeyboardButton("📖 How to Verify?", url=config.HOW_TO_VERIFY_LINK)],
                [InlineKeyboardButton("🛠 Support", url="https://t.me/adarsh2626")]
            ])
            
            return buttons, token
        except Exception as e:
            logger.error(f"Error creating verification buttons: {str(e)}")
            return None, None

    async def cleanup_expired_verifications(self) -> int:
        """Clean up expired verifications from database"""
        try:
            now = datetime.now(pytz.UTC)
            result = await self.collection.delete_many({
                "$or": [
                    {"expires_at": {"$lt": now}},
                    {"verification_attempts": {"$gte": 5}},
                    {
                        "is_verified": True,
                        "last_activity": {"$lt": now - timedelta(hours=config.TOKEN_TIME)}
                    }
                ]
            })
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up verifications: {str(e)}")
            return 0
