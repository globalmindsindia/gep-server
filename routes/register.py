# routes/register.py
from flask import Blueprint, request, jsonify, current_app
from controllers.register_controller import process_registration, RegisterSchema
from pydantic import ValidationError
from db.database import init_db

bp = Blueprint('register', __name__)

# ensure DB tables exist
init_db()

@bp.route("/register", methods=["POST"])
def register():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"detail": "Invalid JSON"}), 400

    try:
        result = process_registration(payload, current_app)
    except ValidationError as ve:
        # Return pydantic validation errors in a simple format
        return jsonify({"detail": ve.errors()}), 422
    except Exception as e:
        current_app.logger.exception("Registration failed")
        return jsonify({"detail": "Registration failed"}), 500

    # If created_new is False -> duplicate email
    if not result.get("created_new", False):
        return jsonify({"detail": "Email already registered"}), 409

    # success - new user created
    return jsonify({
        "id": result["user"]["id"],
        "name": result["user"]["name"],
        "email": result["user"]["email"],
        "mobile": result["user"]["mobile"],
        "qualification": result["user"]["qualification"],
        "experience": result["user"]["experience"],
        "created_at": result["user"]["created_at"],
        "message": "Registered successfully. Confirmation sent to your email."
    }), 201
