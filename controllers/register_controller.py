# controllers/register_controller.py
import json
import html
from typing import Optional, Dict, Any
from datetime import datetime


from pydantic import BaseModel, EmailStr, ValidationError, Field, root_validator


from db.database import SessionLocal
from models.user import User
from utils.email_service import send_email_async
from flask import current_app


# ---- Pydantic models ----
class ExtraModel(BaseModel):
    mobile: Optional[str] = Field(None, min_length=10, max_length=20)
    qualification: Optional[str] = Field(None)
    experience: Optional[str] = Field(None)


class RegisterSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    extra: Optional[ExtraModel] = None


    # Accept legacy top-level fields as well
    mobile: Optional[str] = Field(None, min_length=10, max_length=20)
    qualification: Optional[str] = Field(None)
    experience: Optional[str] = Field(None)


    @root_validator(pre=True)
    def normalize_extra(cls, values):
        extra = values.get("extra") or {}
        for k in ("mobile", "qualification", "experience"):
            if k in values and values.get(k) is not None:
                extra.setdefault(k, values.get(k))
        if extra:
            values["extra"] = extra
        return values


# ---- DB helpers ----
def save_user(payload: dict):
    """
    Save a new user. If email exists, return (existing_user, False).
    If created, return (user, True).
    """
    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.email == payload["email"]).first()
        if existing:
            return existing, False


        extra = payload.get("extra") or {}
        mobile = extra.get("mobile") if isinstance(extra, dict) else None
        qualification = extra.get("qualification") if isinstance(extra, dict) else None
        experience = extra.get("experience") if isinstance(extra, dict) else None


        # store extra as JSON string for flexibility
        extra_str = None
        if extra:
            try:
                extra_str = json.dumps(extra, ensure_ascii=False)
            except Exception:
                extra_str = str(extra)


        user = User(
            name=payload["name"],
            email=payload["email"],
            mobile=mobile,
            qualification=qualification,
            experience=experience,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user, True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---- Main controller ----
def process_registration(payload: dict, flask_app):
    """
    Validates payload, saves user, enqueues emails.
    Returns dict with user dict and created_new flag.
    May raise pydantic.ValidationError on invalid input.
    """
    # Validate + normalize payload
    validated = RegisterSchema(**payload).dict()


    user, created_new = save_user(validated)


    # Prepare normalized fields
    name = user.name
    email = user.email
    mobile = user.mobile or (validated.get("extra") or {}).get("mobile")
    qualification = user.qualification or (validated.get("extra") or {}).get("qualification")
    experience = user.experience or (validated.get("extra") or {}).get("experience")
    # city: attempt to read from user model if exists, otherwise from extra payload
    city = getattr(user, "city", None) or (validated.get("extra") or {}).get("city")
    created_at = user.created_at.isoformat() if hasattr(user, "created_at") else datetime.utcnow().isoformat()


    # Safe-escape for HTML
    esc = lambda s: html.escape(s) if s is not None else "-"


    # --- User email ---
    user_subject = "Welcome to the Global Education Partner Programme!"

    user_text = (
        f"Dear {name},\n\n"
        "Thank you for registering for the Global Education Partner (GEP) Programme with Global Minds India!\n"
        "Your registration has been received successfully.\n\n"
        "Our team will get in touch with you shortly to explain how the programme works, the benefits, and how you can begin your journey as a GEP Partner.\n\n"
        "If you have any questions, feel free to reach out.\n\n"
        "Warm regards,\n"
        "Global Minds India Team\n"
        "📞 +91 73534 46655\n"
        "📧 connect@globalmindsindia.com\n"
    )

    user_html = f"""
    <html><body>
      <p>Dear {esc(name)},</p>
      <p>Thank you for registering for the <strong>Global Education Partner (GEP) Programme</strong> with <strong>Global Minds India</strong>!</p>
      <p>Your registration has been received successfully.</p>
      <p>Our team will get in touch with you shortly to explain how the programme works, the benefits, and how you can begin your journey as a GEP Partner.</p>
      <p>If you have any immediate questions, feel free to reach out.</p>
      <p>Warm regards,<br/>
      Global Minds India Team<br/>
      📞 +91 73534 46655<br/>
      📧 <a href="mailto:connect@globalmindsindia.com">connect@globalmindsindia.com</a></p>
    </body></html>
    """


    # --- Admin email ---
    admin_email = flask_app.config.get("ADMIN_EMAIL") or "connect@globalmindsindia.com"
    admin_subject = "New GEP Partner Registration – Please Contact the User"

    admin_text = (
        "Hello Team,\n\n"
        "A new user has registered for the Global Education Partner (GEP) Programme.\n\n"
        "User Details:\n"
        f"Name: {name}\n"
        f"Phone: {mobile or '-'}\n"
        f"Email: {email}\n"
        "Action Required:\n"
        "👉 Please contact the user and provide full details about the programme.\n"
        "👉 Assist them with onboarding and next steps.\n\n"
        "Thank you,\n"
        "System Notification – Global Minds India\n"
    )

    admin_html = f"""
    <html><body>
      <p>Hello Team,</p>
      <p>A new user has registered for the <strong>Global Education Partner (GEP) Programme</strong>.</p>
      <h4>User Details:</h4>
      <table cellpadding="4" cellspacing="0" border="0">
        <tr><td><strong>Name:</strong></td><td>{esc(name)}</td></tr>
        <tr><td><strong>Phone:</strong></td><td>{esc(mobile or '-')}</td></tr>
        <tr><td><strong>Email:</strong></td><td><a href="mailto:{esc(email)}">{esc(email)}</a></td></tr>
        <tr><td><strong>City:</strong></td><td>{esc(city or '-')}</td></tr>
      </table>
      <h4>Action Required:</h4>
      <ul>
        <li>👉 Please contact the user and provide full details about the programme.</li>
        <li>👉 Assist them with onboarding and next steps.</li>
      </ul>
      <p>Thank you,<br/>System Notification – Global Minds India</p>
    </body></html>
    """


    # Envelope sender for user email (explicit 'FROM_EMAIL' address where humans can respond)
    sender_user = flask_app.config.get("FROM_EMAIL") or flask_app.config.get("MAIL_DEFAULT_SENDER")


    # Use configured No-Reply email for admin envelope sender if provided
    sender_admin = flask_app.config.get("NO_REPLY_EMAIL") or "noreply@globalmindsindia.com"


    # Queue both emails (non-blocking)
    try:
        flask_app.logger.debug("Enqueueing registration emails: user_sender=%s admin_sender=%s admin_reply_to=%s", sender_user, sender_admin, sender_admin)
        # Make sure user-facing email is from FLO, admin email is from NO_REPLY
        send_email_async(flask_app, user_subject, [email], user_html, user_text, sender=sender_user)
        send_email_async(flask_app, admin_subject, [admin_email], admin_html, admin_text, sender=sender_admin, reply_to=sender_admin)
    except Exception:
        flask_app.logger.exception("Failed to enqueue registration emails")


    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "mobile": user.mobile,
            "qualification": user.qualification,
            "experience": user.experience,
            "created_at": created_at,
        },
        "created_new": created_new
    }
