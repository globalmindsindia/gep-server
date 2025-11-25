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
    created_at = user.created_at.isoformat() if hasattr(user, "created_at") else datetime.utcnow().isoformat()

    # Safe-escape for HTML
    esc = lambda s: html.escape(s) if s is not None else "-"

    # --- User email ---
    user_subject = "Thank you for registering — Global Minds India"
    user_text = (
        f"Hi {name},\n\n"
        "Thank you for registering with Global Minds India.\n\n"
        "We have received your details and our team will contact you shortly.\n\n"
        f"Summary:\nName: {name}\nEmail: {email}\nMobile: {mobile or '-'}\nQualification: {qualification or '-'}\nExperience: {experience or '-'}\n\n"
        "Regards,\nGlobal Minds India Team\n"
    )
    user_html = f"""
    <html><body>
      <p>Hi {esc(name)},</p>
      <p>Thanks for registering with <strong>Global Minds India</strong>. We received your information and our team will contact you shortly.</p>
      <h4>Your submitted details</h4>
      <ul>
        <li><strong>Name:</strong> {esc(name)}</li>
        <li><strong>Email:</strong> {esc(email)}</li>
        <li><strong>Mobile:</strong> {esc(mobile or '-')}</li>
        <li><strong>Qualification:</strong> {esc(qualification or '-')}</li>
        <li><strong>Experience:</strong> {esc(experience or '-')}</li>
        <li><strong>Registered at:</strong> {esc(created_at)}</li>
      </ul>
      <p>If you do not hear from us within 1 business day, please reply to this email or contact us at <a href="mailto:{esc(flask_app.config.get('ADMIN_EMAIL') or '')}">{esc(flask_app.config.get('ADMIN_EMAIL') or '')}</a>.</p>
      <p>Regards,<br/>Global Minds India Team</p>
    </body></html>
    """

    # --- Admin email ---
    admin_email = flask_app.config.get("ADMIN_EMAIL") or "connect@globalmindsindia.com"
    admin_subject = f"New registration: {name} — follow up required"
    admin_text = (
        "New user registered on Global Minds India.\n\n"
        f"Name: {name}\nEmail: {email}\nMobile: {mobile or '-'}\nQualification: {qualification or '-'}\nExperience: {experience or '-'}\nRegistered at: {created_at}\n\n"
        "Please follow up with the user for next steps.\n"
    )
    admin_html = f"""
    <html><body>
      <p><strong>New registration — please follow up</strong></p>
      <table cellpadding="4" cellspacing="0" border="0">
        <tr><td><strong>Name</strong></td><td>{esc(name)}</td></tr>
        <tr><td><strong>Email</strong></td><td><a href="mailto:{esc(email)}">{esc(email)}</a></td></tr>
        <tr><td><strong>Mobile</strong></td><td>{esc(mobile or '-')}</td></tr>
        <tr><td><strong>Qualification</strong></td><td>{esc(qualification or '-')}</td></tr>
        <tr><td><strong>Experience</strong></td><td>{esc(experience or '-')}</td></tr>
        <tr><td><strong>Registered at</strong></td><td>{esc(created_at)}</td></tr>
      </table>
      <p>Action: Please call or email the user to follow up and update the CRM.</p>
      <p>--</p>
      <p>Automated notification from Global Minds India</p>
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
