from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from utils.token_verification import TokenVerification
import config
import logging

logger = logging.getLogger(__name__)
token_verification = TokenVerification()

async def verify_token_access(client: Client, user_id: int, target: Union[Message, CallbackQuery]) -> bool:
    """
    Middleware to verify token access for file links
    Returns True if user has valid token or TOKEN_SYSTEM is disabled
    Returns False if verification is required
    """
    if not config.TOKEN_SYSTEM:
        return True
        
    is_verified = await token_verification.is_verified(user_id)
    
    if not is_verified:
        buttons, _ = await token_verification.get_verification_buttons(user_id)
        
        verification_text = (
            "🔒 **Verification Required**\n\n"
            "You need to verify your account to access files from this bot.\n\n"
            "Click the button below to verify your account."
        )
        
        if isinstance(target, Message):
            await target.reply_text(
                verification_text,
                reply_markup=buttons,
                protect_content=config.PRIVACY_MODE
            )
        elif isinstance(target, CallbackQuery):
            await target.answer("Verification required", show_alert=True)
            await client.send_message(
                chat_id=target.from_user.id,
                text=verification_text,
                reply_markup=buttons,
                protect_content=config.PRIVACY_MODE
            )
        
        return False
        
    return True
