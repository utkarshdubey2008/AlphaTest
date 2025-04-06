async def verify_user_access(message: Message) -> bool:
    """Check if user has access to use the bot"""
    if not config.TOKEN_SYSTEM:
        return True
        
    if not await token_verification.is_verified(message.from_user.id):
        buttons, _ = await token_verification.get_verification_buttons(message.from_user.id)
        await message.reply_text(
            "🔒 **Verification Required**\n\n"
            "Please verify your account to access this feature.",
            reply_markup=buttons,
            protect_content=config.PRIVACY_MODE
        )
        return False
    return True
