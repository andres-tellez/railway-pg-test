from flask import Blueprint, request

oauth_bp = Blueprint("oauth", __name__)

@oauth_bp.route("/oauth/callback")
def oauth_callback():
    try:
        print("📥 /oauth/callback hit", flush=True)
        code = request.args.get("code")
        print("📦 Code received:", code, flush=True)

        if not code:
            return "❌ Missing `code` param in query string", 400

        return f"✅ OAuth successful! Code received: {code}", 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Internal Error: {str(e)}", 500
