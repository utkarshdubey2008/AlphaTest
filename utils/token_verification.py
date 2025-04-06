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
        token = str(uuid.uuid4())
        return token
    
    async def create_verification_link(self, user_id: int, token: str) -> str:
        """Create a verification link with user_id and token"""
        # Format: https://t.me/bot_username?start=user_id+token
        base_link = f"https://t.me/{config.BOT_USERNAME}?start={user_id}{token}"
        return base_link
    
    async def shorten_url(self, long_url: str) -> str:
        """Shorten URL using the configured URL shortener service"""
        shortener_url = config.SHORTENER_URL.lower()
        api_token = config.SHORTENER_API_TOKEN
        
        if not api_token or not shortener_url:
            logger.error("URL shortener configuration is missing")
            return long_url
            
        api_url = ""
        if "modijiurl" in shortener_url:
            api_url = f"https://api.modijiurl.com/api?api={api_token}&url={long_url}&format=text"
        elif "shrinkearn" in shortener_url:
            api_url = f"https://shrinkearn.com/api?api={api_token}&url={long_url}&format=text"
        elif "indianshortner" in shortener_url:
            api_url = f"https://indianshortner.com/api?api={api_token}&url={long_url}&format=text"
        else:
            logger.error(f"Unsupported URL shortener: {shortener_url}")
            return long_url
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        shortened_url = await response.text()
                        shortened_url = shortened_url.strip()
                        if not shortened_url.startswith("http"):
                            logger.error(f"Invalid shortener response: {shortened_url}")
                            return long_url
                        logger.info(f"URL shortened successfully: {shortened_url}")
                        return shortened_url
                    else:
                        logger.error(f"URL shortening failed with status {response.status}")
                        return long_url
        except Exception as e:
            logger.error(f"Error shortening URL: {str(e)}")
            return long_url
    
    async def store_verification(self, user_id: int, token: str) -> bool:
        """Store or update user verification status in database"""
        try:
            now = datetime.now(pytz.UTC)
            expires_at = now + timedelta(hours=config.TOKEN_TIME)
            
            # Check if user already exists
            existing = await self.collection.find_one({"user_id": user_id})
            
            if existing:
                # Update existing user
                await self.collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "token": token,
                            "verified_at": now,
                            "expires_at": expires_at
                        }
                    }
                )
            else:
                # Insert new user
                await self.collection.insert_one({
                    "user_id": user_id,
                    "token": token,
                    "verified_at": now,
                    "expires_at": expires_at
                })
            
            logger.info(f"User {user_id} verification stored/updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error storing verification: {str(e)}")
            return False
    
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
            
            if not expires_at or now > expires_at:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking verification status: {str(e)}")
            return False
    
    async def validate_token(self, user_id: int, token: str) -> bool:
        """Validate token for a user"""
        try:
            user_data = await self.collection.find_one({"user_id": user_id})
            if not user_data:
                return False
                
            stored_token = user_data.get("token")
            return stored_token == token
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False
    
    async def get_verification_buttons(self, user_id: int) -> InlineKeyboardMarkup:
        """Generate verification buttons for unverified users"""
        try:
            token = await self.generate_token(user_id)
            long_url = await self.create_verification_link(user_id, token)
            shortened_url = await self.shorten_url(long_url)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Click Here to Verify", url=shortened_url)],
                [InlineKeyboardButton("📖 How to Verify?", url=config.HOW_TO_VERIFY_LINK)]
            ])
            
            return buttons, token
        except Exception as e:
            logger.error(f"Error creating verification buttons: {str(e)}")
            return None, None
