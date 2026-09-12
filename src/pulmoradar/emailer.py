from __future__ import annotations

import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from .renderer import LOGO_CID


def _addresses(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_addresses(item))
        return out
    return [str(value).strip()] if str(value).strip() else []


def build_message(
    cfg: dict[str, Any],
    subject: str,
    html_body: str,
    logo_path: Path | None = None,
) -> MIMEMultipart:
    email_cfg = cfg.get("email", {})
    to_addrs = _addresses(email_cfg.get("to"))
    cc_addrs = _addresses(email_cfg.get("cc"))
    user = os.environ.get(email_cfg.get("username_env", "SMTP_USERNAME"), "").strip()
    from_name = email_cfg.get("from_name", "PulmoRadar")
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{user}>"
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)
    if logo_path and logo_path.exists():
        payload = logo_path.read_bytes()
        img = MIMEImage(payload, _subtype="png")
        img.add_header("Content-ID", f"<{LOGO_CID}>")
        img.add_header("Content-Disposition", "inline", filename=logo_path.name)
        msg.attach(img)
    return msg


def send_email(
    cfg: dict[str, Any],
    subject: str,
    html_body: str,
    logo_path: Path | None = None,
) -> None:
    email_cfg = cfg.get("email", {})
    to_addrs = _addresses(email_cfg.get("to"))
    recipients = to_addrs + _addresses(email_cfg.get("cc"))
    user = os.environ.get(email_cfg.get("username_env", "SMTP_USERNAME"), "").strip()
    password = os.environ.get(email_cfg.get("password_env", "SMTP_PASSWORD"), "").replace(" ", "").strip()
    if not to_addrs:
        raise RuntimeError("email.to is missing in config.yaml")
    if not user or not password:
        raise RuntimeError("SMTP_USERNAME / SMTP_PASSWORD are not set")
    msg = build_message(cfg, subject, html_body, logo_path=logo_path)
    host = email_cfg.get("smtp_host", "smtp.gmail.com")
    port = int(email_cfg.get("smtp_port", 587))
    last_error: Exception | None = None
    attempts = [(host, port, False)]
    if port == 587:
        attempts.append((host, 465, True))
    for host_i, port_i, ssl in attempts:
        try:
            if ssl:
                with smtplib.SMTP_SSL(host_i, port_i, timeout=45) as smtp:
                    smtp.login(user, password)
                    smtp.sendmail(user, recipients, msg.as_string())
            else:
                with smtplib.SMTP(host_i, port_i, timeout=45) as smtp:
                    smtp.starttls()
                    smtp.login(user, password)
                    smtp.sendmail(user, recipients, msg.as_string())
            return
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(f"SMTP send failed: {last_error}") from last_error
