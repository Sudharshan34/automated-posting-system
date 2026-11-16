import httpx

from .base import Platform, PlatformError


class Telegram(Platform):
    name = "Telegram"
    required_settings = ["telegram_bot_token", "telegram_channel"]

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        s = self.settings
        channel = s.telegram_channel if s.telegram_channel.startswith("@") else f"@{s.telegram_channel}"
        r = await client.post(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            json={"chat_id": channel, "text": message},
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise PlatformError(data.get("description", "Telegram API error"))
        return f"https://t.me/{channel.lstrip('@')}/{data['result']['message_id']}"
