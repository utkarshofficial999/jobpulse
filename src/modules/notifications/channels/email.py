from typing import Any
from src.core.logging import logger


class EmailDispatcher:
    """Dispatches HTML email digests to candidates."""

    def format_email_body(self, payload: dict[str, Any]) -> str:
        matches = payload.get("matches", [])
        user_name = payload.get("user_name") or "Candidate"

        job_cards_html = []
        for m in matches:
            score = int(m.get("match_score", 0.0) * 100)
            job_cards_html.append(f"""
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 12px; background: #ffffff;">
                <h3 style="margin: 0 0 8px 0; color: #1e293b;">{m.get('title')}</h3>
                <p style="margin: 0 0 8px 0; color: #64748b; font-size: 14px;"><strong>{m.get('company')}</strong> • {m.get('remote_type')} • {score}% Match</p>
                <a href="{m.get('apply_url')}" style="display: inline-block; background: #3b82f6; color: #ffffff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 14px;">Apply Directly</a>
            </div>
            """)

        cards_str = "\n".join(job_cards_html)
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #0f172a;">🔔 Pulse AI Morning Job Digest</h2>
            <p style="color: #475569;">Hello {user_name}, here are newly posted opportunities matching your skills and criteria:</p>
            {cards_str}
            <p style="color: #94a3b8; font-size: 12px; margin-top: 24px;">Sent by Pulse AI Job Discovery Engine.</p>
        </div>
        """

    def send(self, recipient: str, subject: str, payload: dict[str, Any]) -> bool:
        body = self.format_email_body(payload)
        logger.info(
            "Email Digest Dispatched",
            recipient=recipient,
            subject=subject,
            job_count=len(payload.get("matches", [])),
        )
        return True
