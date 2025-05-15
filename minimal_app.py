from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Minimal home OK", 200

@app.route("/foo")
def foo():
    return "🍌 Foo endpoint OK", 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5555, debug=True)
