from flask import Blueprint

web_bp = Blueprint("web", __name__)

@web_bp.route("/web/ping")
def ping():
    return "pong from web"
