#!/usr/bin/env python3

from flask import Flask, render_template_string, request, redirect
import threading
import json
import os

from main import run_monitor

app = Flask(__name__)

CONFIG_FILE = "config.json"


# =========================
# CONFIG
# =========================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"sections": {}}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# =========================
# MONITOR THREAD (SAFE)
# =========================
def start_monitor_safe():
    try:
        print("🚀 Iniciando monitor...")
        run_monitor()
    except Exception as e:
        print("❌ Erro no monitor:", e)


threading.Thread(target=start_monitor_safe, daemon=True).start()


# =========================
# HTML
# =========================
HTML = """
<h1>📊 Painel Monitor</h1>

<h2>➕ Adicionar setor</h2>
<form method="post" action="/add">
  Nome: <input name="name"><br><br>
  Contatos (numero:apikey,...): <input name="contacts"><br><br>
  <button type="submit">Adicionar</button>
</form>

<h2>📋 Setores</h2>
<ul>
{% for name, data in sections.items() %}
<li>
<b>{{name}}</b><br>
📱 {{data.contacts}}<br>
<a href="/delete/{{name}}">❌ Remover</a>
</li><br>
{% endfor %}
</ul>
"""


# =========================
# ROTAS
# =========================
@app.route("/")
def index():
    config = load_config()
    return render_template_string(HTML, sections=config.get("sections", {}))


@app.route("/add", methods=["POST"])
def add():
    name = request.form.get("name")
    contacts = request.form.get("contacts")

    config = load_config()
    config.setdefault("sections", {})[name] = {
        "contacts": contacts
    }

    save_config(config)
    return redirect("/")


@app.route("/delete/<name>")
def delete(name):
    config = load_config()
    config.get("sections", {}).pop(name, None)
    save_config(config)
    return redirect("/")


# =========================
# HEALTH CHECK (RAILWAY)
# =========================
@app.route("/health")
def health():
    return "OK"


# =========================
# START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Rodando na porta {port}")
    app.run(host="0.0.0.0", port=port)