from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "OK HOME"

@app.route("/health")
def health():
    return "OK HEALTH"