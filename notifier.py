import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailConfigError(RuntimeError):
    pass


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise EmailConfigError(f"{name} environment variable is not set")
    return value


def send_notification(subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    username = _required_env("SMTP_USERNAME")
    password = _required_env("SMTP_PASSWORD")
    to_addr = os.environ.get("NOTIFY_EMAIL_TO", username)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = username
    message["To"] = to_addr
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(username, password)
        server.send_message(message)
