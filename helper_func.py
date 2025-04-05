# Copyright (c) 2025 @thealphabotz - All Rights Reserved.

import base64
import re
from typing import Union

async def encode(string: str) -> str:
    string_bytes = string.encode("ascii")
    base64_bytes = base64.b64encode(string_bytes)
    return base64_bytes.decode("ascii")

async def decode(base64_string: str) -> str:
    try:
        base64_bytes = base64_string.encode("ascii")
        string_bytes = base64.b64decode(base64_bytes)
        return string_bytes.decode("ascii")
    except:
        return ""

async def get_message_id(client, message: Union[str, int]) -> Union[int, bool]:
    if message.forward_from_chat:
        if message.forward_from_chat.id == client.db_channel.id:
            return message.forward_from_message_id
        return False
    if message.text:
        pattern = "https://t.me/(?:c/)?([^/]+)/([0-9]+)"
        matches = re.match(pattern, message.text.strip())
        if not matches:
            return False
        channel_id = matches.group(1)
        msg_id = int(matches.group(2))
        if channel_id.isdigit():
            if f"-100{channel_id}" == str(client.db_channel.id):
                return msg_id
        else:
            if channel_id == client.db_channel.username:
                return msg_id
    return False

# @thealphabotz | Join @thealphabotz on Telegram
