"""Sends email through SMTP (Gmail works for free with an app password).

Without SMTP settings the email is printed in the backend terminal, so sign-up
and password reset can be tested on a laptop with no email setup.
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger("mail")


def _send_sync(to: str, subject: str, text: str, html: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = f"Hostel/PG Life <{s.smtp_from or s.smtp_user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)


async def send_email(to: str, subject: str, text: str, html: str) -> bool:
    """Returns True if really sent, False if printed to the terminal (dev mode)."""
    if not get_settings().email_enabled:
        log.warning("DEV MODE (no SMTP configured): email to %s | %s\n%s", to, subject, text)
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, text, html)
        return True
    except Exception as exc:  # bad password, network, Gmail limits
        log.error("Email to %s failed: %s", to, exc)
        raise


def code_email(name: str, code: str, purpose: str) -> tuple[str, str, str]:
    what = "verify your email" if purpose == "verify" else "reset your password"
    subject = f"{code} is your Hostel/PG Life code"
    text = f"Hi {name},\n\nUse this code to {what}: {code}\n\nIt expires in 10 minutes. If you didn't ask for it, ignore this email."
    digits = "".join(
        f'<span style="display:inline-block;width:40px;height:48px;line-height:48px;margin:0 3px;border-radius:10px;'
        f'background:#f5f3ff;color:#1a1638;font-size:24px;font-weight:700;text-align:center">{d}</span>'
        for d in code
    )
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;color:#1a1638">
  <div style="height:6px;border-radius:6px;background:linear-gradient(90deg,#3523c9,#8a3ffc,#ff5f8f,#ffb43d)"></div>
  <h2 style="margin:24px 0 8px">Hi {name},</h2>
  <p style="color:#4b4769">Use this code to {what}:</p>
  <p style="margin:20px 0">{digits}</p>
  <p style="color:#6b6789;font-size:13px">It expires in 10 minutes. If you didn't ask for it, you can ignore this email.</p>
  <p style="color:#6b6789;font-size:13px">Hostel/PG Life</p>
</div>"""
    return subject, text, html
