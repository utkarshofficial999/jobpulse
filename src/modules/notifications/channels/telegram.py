import os
from typing import Any
import httpx

from src.config import settings
from src.core.logging import logger


class TelegramDispatcher:
    """Dispatches formatted Markdown job alerts via Telegram Bot API."""

    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN")

    def format_message(self, recipient: str, payload: dict[str, Any]) -> str:
        matches = payload.get("matches", [])
        total = len(matches)
        user_name = payload.get("user_name") or "Candidate"

        lines = [
            f"🔔 *Pulse AI Job Alert for {user_name}*",
            f"Found *{total}* new roles matching your profile:\n",
        ]

        for idx, m in enumerate(matches, start=1):
            title = m.get("title")
            company = m.get("company")
            remote = m.get("remote_type", "unknown").capitalize()
            score = int(m.get("match_score", 0.0) * 100)
            apply_url = m.get("apply_url")
            skills = ", ".join(m.get("matched_skills", [])[:4])

            skills_line = f"\n   🛠️ _Skills:_ {skills}" if skills else ""
            lines.append(
                f"{idx}\\. *{title}* @ *{company}*\n"
                f"   📍 _{remote}_ \\| ⚡ *{score}% Match*{skills_line}\n"
                f"   [👉 Apply Now]({apply_url})\n"
            )

        return "\n".join(lines)

    def send(self, recipient: str, payload: dict[str, Any]) -> bool:
        message_text = self.format_message(recipient, payload)

        if not self.bot_token or self.bot_token.startswith("mock"):
            logger.info(
                "[DEV] Mock Telegram Alert Dispatched",
                recipient=recipient,
                message_length=len(message_text),
                matches_count=len(payload.get("matches", [])),
            )
            return True

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                url,
                json={
                    "chat_id": recipient,
                    "text": message_text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )
            resp.raise_for_status()
            logger.info("Telegram notification sent successfully", recipient=recipient)
            return True
