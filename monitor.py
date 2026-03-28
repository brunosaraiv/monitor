#!/usr/bin/env python3
"""Monitor definitivo para novas tarefas do setor Objetos com envio via WhatsApp."""

import argparse
import json
import os
import time
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.exceptions import ProxyError

load_dotenv("config.env")

BASE_URL = os.getenv(
    "MONITOR_URL",
    "https://armadaorganizadora.com.br/gymkhana/49a91122-5b48-41de-9c8a-a7db9d3bb22b/tasks",
)
MONITOR_SECTION = os.getenv("MONITOR_SECTION", "Objetos").strip() or "Objetos"
URL = f"{BASE_URL}?section={urllib.parse.quote(MONITOR_SECTION)}"
CHECK_INTERVAL_SECONDS = float(
    os.getenv("OBJECTS_CHECK_INTERVAL_SECONDS", os.getenv("CHECK_INTERVAL_SECONDS", "5"))
)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
SEND_DELAY_SECONDS = float(os.getenv("CALLMEBOT_SEND_DELAY_SECONDS", "0.2"))
STATE_FILE = os.getenv("TASKS_STATE_FILE", "tasks_state.txt")
USE_SYSTEM_PROXY = os.getenv("USE_SYSTEM_PROXY", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE")
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY")
CALLMEBOT_CONTACTS = [
    contact.strip()
    for contact in os.getenv("CALLMEBOT_CONTACTS", "").split(",")
    if contact.strip()
]

SESSION = requests.Session()
SESSION.trust_env = USE_SYSTEM_PROXY


if not (CALLMEBOT_CONTACTS or (CALLMEBOT_PHONE and CALLMEBOT_APIKEY)):
    print("❌ Configure CALLMEBOT_PHONE/CALLMEBOT_APIKEY ou CALLMEBOT_CONTACTS no config.env")
    raise SystemExit(1)



def build_contacts():
    if CALLMEBOT_CONTACTS:
        return CALLMEBOT_CONTACTS
    return [f"{CALLMEBOT_PHONE}:{CALLMEBOT_APIKEY}"]



def normalize_text(value):
    return " ".join((value or "").split()).strip().casefold()



def get_session(use_system_proxy=None):
    session = requests.Session()
    session.trust_env = USE_SYSTEM_PROXY if use_system_proxy is None else use_system_proxy
    return session



def perform_get(url, **kwargs):
    try:
        return SESSION.get(url, **kwargs)
    except ProxyError as exc:
        if USE_SYSTEM_PROXY:
            raise

        fallback_session = get_session(use_system_proxy=False)
        print("⚠️ Proxy do sistema ignorado para evitar bloqueio 403.")
        return fallback_session.get(url, **kwargs)



def send_whatsapp_callmebot(contacts, message, dry_run=False):
    if isinstance(contacts, str):
        contacts = [contacts]

    success_count = 0

    for contact in contacts:
        contact = contact.strip()
        if not contact or ":" not in contact:
            continue

        phone, api_key = contact.split(":", 1)

        if dry_run:
            print(f"🧪 DRY RUN: envio simulado para +{phone}")
            success_count += 1
            continue

        encoded_message = urllib.parse.quote(message)
        request_url = (
            "https://api.callmebot.com/whatsapp.php"
            f"?phone={phone}&text={encoded_message}&apikey={api_key}"
        )

        try:
            response = perform_get(request_url, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 200:
                print(f"📩 Enviado para +{phone}")
                success_count += 1
            else:
                print(f"❌ Erro {response.status_code} para +{phone}: {response.text}")

            if SEND_DELAY_SECONDS > 0:
                time.sleep(SEND_DELAY_SECONDS)
        except Exception as exc:
            print(f"❌ Erro envio +{phone}: {exc}")

    return success_count > 0



def fetch_tasks(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = perform_get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    task_links = soup.select('a[href*="/task/"]')

    tasks = []
    for link in task_links:
        columns = [node.get_text(" ", strip=True) for node in link.find_all("p")]
        if len(columns) < 3:
            continue

        href = link.get("href", "").strip()
        if not href:
            continue

        task = {
            "id": href.rsplit("/", 1)[-1],
            "tarefa": columns[0],
            "setor": columns[1],
            "data_publicacao": columns[2],
            "url": urllib.parse.urljoin(BASE_URL, href),
        }
        tasks.append(task)

    return tasks



def filter_tasks_by_section(tasks, section_name):
    normalized_section = normalize_text(section_name)
    return [task for task in tasks if normalize_text(task.get("setor")) == normalized_section]



def load_state(state_file):
    if not os.path.exists(state_file):
        return []

    try:
        with open(state_file, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
    except Exception:
        return []



def save_state(state_file, task_ids):
    with open(state_file, "w", encoding="utf-8") as file:
        json.dump(task_ids, file, ensure_ascii=False, indent=2)



def build_message(task):
    detected_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return (
        "🚨 *NOVA TAREFA DISPONÍVEL*\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📌 *Tarefa*\n{task['tarefa']}\n\n"
        f"🏷️ *Setor*\n{task['setor']}\n\n"
        f"📅 *Publicação*\n{task['data_publicacao']}\n\n"
        f"🔗 *Abrir tarefa*\n{task['url']}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"⏰ Detectado em {detected_at}"
    )



def build_test_task():
    return {
        "id": "teste-manual",
        "tarefa": "999 - Tarefa de teste do setor Objetos",
        "setor": MONITOR_SECTION,
        "data_publicacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "url": URL,
    }



def process_cycle(known_task_ids, contacts, dry_run=False):
    tasks = fetch_tasks(URL)
    filtered_tasks = filter_tasks_by_section(tasks, MONITOR_SECTION)
    current_task_ids = {task["id"] for task in filtered_tasks}

    if not known_task_ids:
        print(f"ℹ️ Estado inicial salvo com {len(current_task_ids)} tarefa(s) do setor {MONITOR_SECTION}")
        save_state(STATE_FILE, sorted(current_task_ids))
        return current_task_ids, 0

    new_tasks = [task for task in filtered_tasks if task["id"] not in known_task_ids]
    sent_count = 0

    if new_tasks:
        print(f"🚨 {len(new_tasks)} nova(s) tarefa(s) detectada(s) em {MONITOR_SECTION}!")
        for task in reversed(new_tasks):
            message = build_message(task)
            if send_whatsapp_callmebot(contacts, message, dry_run=dry_run):
                sent_count += 1
    else:
        print(datetime.now().isoformat(), f"- sem novas tarefas em {MONITOR_SECTION}")

    save_state(STATE_FILE, sorted(current_task_ids))
    return current_task_ids, sent_count



def reset_state():
    save_state(STATE_FILE, [])
    print(f"🗑️ Estado reiniciado em {STATE_FILE}")



def run_monitor(dry_run=False, once=False):
    print(f"🚀 Monitorando setor {MONITOR_SECTION}: {URL}")
    print(f"⚡ Intervalo entre verificações: {CHECK_INTERVAL_SECONDS}s")
    print(f"📂 Arquivo de estado: {STATE_FILE}")

    known_task_ids = set(load_state(STATE_FILE))
    contacts = build_contacts()

    while True:
        cycle_started_at = time.monotonic()
        try:
            known_task_ids, _ = process_cycle(known_task_ids, contacts, dry_run=dry_run)
        except Exception as exc:
            print("⚠️ Erro:", str(exc))

        if once:
            return

        elapsed = time.monotonic() - cycle_started_at
        remaining_sleep = max(0, CHECK_INTERVAL_SECONDS - elapsed)
        if remaining_sleep:
            time.sleep(remaining_sleep)



def main():
    parser = argparse.ArgumentParser(
        description="Monitor definitivo para novas tarefas do setor Objetos."
    )
    parser.add_argument(
        "--test-send",
        action="store_true",
        help="Envia uma mensagem de teste no formato final.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula envio sem chamar a API do WhatsApp.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa apenas uma verificação e encerra.",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Limpa o estado salvo antes de iniciar.",
    )
    args = parser.parse_args()

    if args.reset_state:
        reset_state()

    if args.test_send:
        contacts = build_contacts()
        message = build_message(build_test_task())
        print(message)
        send_whatsapp_callmebot(contacts, message, dry_run=args.dry_run)
        return

    run_monitor(dry_run=args.dry_run, once=args.once)


if __name__ == "__main__":
    main()
