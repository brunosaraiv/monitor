#!/usr/bin/env python3

import json
import os
import time
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.exceptions import ProxyError

load_dotenv()

BASE_URL = os.getenv(
    "MONITOR_URL",
    "https://armadaorganizadora.com.br/gymkhana/49a91122-5b48-41de-9c8a-a7db9d3bb22b/tasks",
)

CHECK_INTERVAL_SECONDS = float(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
SEND_DELAY_SECONDS = float(os.getenv("CALLMEBOT_SEND_DELAY_SECONDS", "0.2"))

SESSION = requests.Session()


# =========================
# CONFIG DINÂMICA (PAINEL)
# =========================
def load_config():
    if not os.path.exists("config.json"):
        return {"sections": {}}
    with open("config.json", "r") as f:
        return json.load(f)


# =========================
# HTTP
# =========================
def perform_get(url, **kwargs):
    try:
        return SESSION.get(url, **kwargs)
    except ProxyError:
        session = requests.Session()
        session.trust_env = False
        return session.get(url, **kwargs)


# =========================
# WHATSAPP
# =========================
def send_whatsapp(contacts, message):
    contacts = [c.strip() for c in contacts.split(",") if c.strip()]

    for contact in contacts:
        if ":" not in contact:
            continue

        phone, apikey = contact.split(":", 1)

        url = (
            "https://api.callmebot.com/whatsapp.php"
            f"?phone={phone}&text={urllib.parse.quote(message)}&apikey={apikey}"
        )

        try:
            r = perform_get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if r.status_code == 200:
                print(f"📩 Enviado para +{phone}")
            else:
                print(f"❌ Erro {phone}")
        except Exception as e:
            print(f"Erro envio: {e}")

        time.sleep(SEND_DELAY_SECONDS)


# =========================
# SCRAPING
# =========================
def fetch_tasks(url):
    r = perform_get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.select('a[href*="/task/"]')

    tasks = []
    for link in links:
        cols = [p.get_text(" ", strip=True) for p in link.find_all("p")]
        if len(cols) < 3:
            continue

        href = link.get("href")

        tasks.append({
            "id": href.rsplit("/", 1)[-1],
            "tarefa": cols[0],
            "setor": cols[1],
            "data": cols[2],
            "url": urllib.parse.urljoin(BASE_URL, href),
        })

    return tasks


# =========================
# STATE
# =========================
def load_state(file):
    if not os.path.exists(file):
        return []
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return []


def save_state(file, data):
    with open(file, "w") as f:
        json.dump(data, f)


# =========================
# MESSAGE
# =========================
def build_message(task):
    return f"""
🚨 NOVA TAREFA

📌 {task['tarefa']}
🏷️ {task['setor']}
📅 {task['data']}

🔗 {task['url']}
"""


# =========================
# MONITOR
# =========================
def run_monitor():
    print("🚀 Monitor iniciado")

    states = {}

    while True:
        config = load_config()

        for section, data in config.get("sections", {}).items():
            try:
                url = f"{BASE_URL}?section={urllib.parse.quote(section)}"
                contacts = data.get("contacts", "")

                tasks = fetch_tasks(url)
                current_ids = {t["id"] for t in tasks}

                state_file = f"state_{section}.json"
                known_ids = set(load_state(state_file))

                if not known_ids:
                    save_state(state_file, list(current_ids))
                    continue

                new_tasks = [t for t in tasks if t["id"] not in known_ids]

                if new_tasks:
                    print(f"🚨 {len(new_tasks)} novas em {section}")
                    for task in new_tasks:
                        send_whatsapp(contacts, build_message(task))
                else:
                    print(f"✔ {section} sem novidades")

                save_state(state_file, list(current_ids))

            except Exception as e:
                print(f"Erro {section}: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)