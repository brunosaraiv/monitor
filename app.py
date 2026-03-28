from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "FUNCIONANDO 🚀"

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Rodando na porta {port}")
    app.run(host="0.0.0.0", port=port)