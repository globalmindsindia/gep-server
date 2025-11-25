# utils/email_service.py
from flask_mail import Mail, Message
from flask import current_app
from threading import Thread
import traceback
import datetime

mail = Mail()

def init_mail(app):
    mail.init_app(app)

def _send_async_email(app, msg: Message):
    """
    Runs in a background thread. Logs success or full exception to both app logger and a file.
    """
    with app.app_context():
        try:
            mail.send(msg)
            app.logger.info("Email sent to %s (subject=%s)", msg.recipients, msg.subject)
        except Exception as e:
            # Log to Flask logger
            app.logger.exception("Failed to send email to %s (subject=%s): %s", msg.recipients, msg.subject, e)
            # Append full traceback to a log file for deeper inspection
            try:
                tb = traceback.format_exc()
                timestamp = datetime.datetime.utcnow().isoformat()
                with open("email_send_error.log", "a", encoding="utf-8") as f:
                    f.write(f"--- {timestamp} ---\n")
                    f.write(f"Recipients: {msg.recipients}\n")
                    f.write(f"Subject: {msg.subject}\n")
                    f.write(tb + "\n\n")
            except Exception:
                # If writing fails, still do not crash the thread
                app.logger.exception("Failed to write to email_send_error.log")

def send_email_async(app, subject: str, recipients: list, html_body: str, text_body: str = None, sender: str = None, reply_to: str = None):
    """
    Fire-and-forget email using a thread. Use a task queue (Celery) in production.
    Returns the Thread object in case caller wants to join/check it in tests.
    """
    # Prefer an explicit sender argument, then MAIL_DEFAULT_SENDER, then FROM_EMAIL, then NO_REPLY_EMAIL
    default_sender = (
        current_app.config.get("MAIL_DEFAULT_SENDER")
        or current_app.config.get("FROM_EMAIL")
        or current_app.config.get("NO_REPLY_EMAIL")
    )
    msg = Message(
        subject=subject,
        recipients=recipients,
        sender=sender or default_sender,
    )
    if text_body:
        msg.body = text_body
    # If NO_REPLY_EMAIL is configured, set reply-to to it for outbound messages
    # Allow passing reply_to explicitly for special cases; otherwise use NO_REPLY_EMAIL
    try:
        configured_reply_to = reply_to or current_app.config.get("NO_REPLY_EMAIL")
        if configured_reply_to:
            msg.reply_to = configured_reply_to
    except Exception:
        # Be permissive if reply_to can't be set
        pass
    msg.html = html_body

    # Log configured mail username and the msg sender for troubleshooting provider rewrites
    try:
        app_mail_user = current_app.config.get("MAIL_USERNAME")
        current_app.logger.debug(
            "Preparing email send: sender=%s mail_username=%s reply_to=%s recipients=%s subject=%s",
            msg.sender,
            app_mail_user,
            getattr(msg, 'reply_to', None),
            recipients,
            subject,
        )
    except Exception:
        pass

    thr = Thread(target=_send_async_email, args=(current_app._get_current_object(), msg))
    thr.daemon = True
    thr.start()
    return thr
