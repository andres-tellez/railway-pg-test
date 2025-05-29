from flask import Blueprint

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin/ping")
def ping():
    return "pong from admin"
