from flask import Blueprint, request

oauth_bp = Blueprint("oauth", __name__)

@oauth_bp.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    return f"✅ OAuth successful! Copy this code into your script: {code}", 200
