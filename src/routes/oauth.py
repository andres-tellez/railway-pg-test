from flask import Blueprint, request

oauth_bp = Blueprint("oauth", __name__)

@oauth_bp.route("/oauth/callback")
def oauth_callback():
    print("📥 /oauth/callback hit", flush=True)

    try:
        code = request.args.get("code")
        print("📦 Code received:", code, flush=True)

        if not code:
            return "❌ Missing `code` param in query string", 400

        return f"✅ OAuth successful! Code received: {code}", 200

    except Exception as e:
        import traceback
        print("🔥 Exception in /oauth/callback:", flush=True)
        traceback.print_exc()
        return "❌ Internal Server Error", 500
