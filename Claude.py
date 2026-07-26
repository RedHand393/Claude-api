#  ClaudeAskMod for Heroku userbot
#  Простой чат-помощник через Claude API
#
#  Команды:
#  .ask <вопрос>       — задать вопрос Claude, получить ответ
#  .claudemodel <имя>  — сменить модель (например claude-sonnet-4-6)
#  .claudekey <ключ>   — сохранить API-ключ прямо из Telegram (сообщение удалится сразу же)

import aiohttp
from hikkatl.types import Message
from .. import loader, utils

DEFAULT_MODEL = "claude-sonnet-4-6"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


@loader.tds
class ClaudeAskMod(loader.Module):
    """Чат с Claude прямо в Telegram | .ask <вопрос>"""

    strings = {
        "name": "ClaudeAsk",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "api_key",
                "",
                "API-ключ Anthropic (лучше задать командой .claudekey, а не тут)",
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "model",
                DEFAULT_MODEL,
                "Модель Claude по умолчанию",
            ),
            loader.ConfigValue(
                "max_tokens",
                1024,
                "Максимум токенов в ответе",
                validator=loader.validators.Integer(minimum=64, maximum=8192),
            ),
        )

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    async def _ask_claude(self, prompt: str) -> str:
        api_key = self.config["api_key"]
        if not api_key:
            return (
                "⚠️ API-ключ не настроен. Задай его командой:\n"
                "<code>.claudekey sk-ant-...</code>"
            )

        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self.config["model"],
            "max_tokens": self.config["max_tokens"],
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_URL, headers=headers, json=payload
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        err = data.get("error", {}).get("message", str(data))
                        return f"❌ Ошибка API ({resp.status}): {err}"

                    parts = data.get("content", [])
                    text = "\n".join(
                        block.get("text", "")
                        for block in parts
                        if block.get("type") == "text"
                    )
                    return text.strip() or "⚠️ Пустой ответ от Claude."
        except Exception as e:
            return f"❌ Ошибка соединения: {e}"

    async def askcmd(self, message: Message):
        """.ask <вопрос> — спросить у Claude"""
        prompt = utils.get_args_raw(message)
        if not prompt:
            return await utils.answer(
                message, "💬 Укажи вопрос: <code>.ask Как дела?</code>"
            )

        await utils.answer(message, "🤔 Думаю...")
        answer = await self._ask_claude(prompt)
        await utils.answer(message, f"🤖 <b>Claude:</b>\n\n{utils.escape_html(answer)}")

    async def claudemodelcmd(self, message: Message):
        """.claudemodel <имя> — сменить модель Claude"""
        model = utils.get_args_raw(message)
        if not model:
            current = self.config["model"]
            return await utils.answer(
                message, f"📦 Текущая модель: <code>{current}</code>"
            )
        self.config["model"] = model
        await utils.answer(message, f"✅ Модель установлена: <code>{model}</code>")

    async def claudekeycmd(self, message: Message):
        """.claudekey <ключ> — сохранить API-ключ Anthropic"""
        key = utils.get_args_raw(message)
        if not key:
            return await utils.answer(
                message, "⚠️ Укажи ключ: <code>.claudekey sk-ant-...</code>"
            )
        self.config["api_key"] = key
        # Сразу удаляем сообщение с ключом, чтобы он не оставался в истории чата
        await message.delete()
        await self.client.send_message(
            utils.get_chat_id(message),
            "✅ API-ключ сохранён и сообщение с ним удалено.",
        )
