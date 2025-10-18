#!/usr/bin/env python3
"""
Slim IP Track Bot w/ strict one-time passwords
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  export TG_TOKEN="your_token_here"
  python3 iptrack_bot.py
"""

import logging
import os
import requests
import ipaddress
import secrets
import string
import json
import time
from pathlib import Path
from requests.utils import requote_uri
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ---------- Config ----------
TG_TOKEN = os.environ.get("TG_TOKEN") or "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
DATA_DIR = Path("bot_data")
HASIL_FILE = DATA_DIR / "hasil_ip.txt"
PASSWORDS_FILE = DATA_DIR / "passwords.json"
IP_API_URL = "http://ip-api.com/json/{}"
DEFAULT_PASSLEN = 24
# ----------------------------

DATA_DIR.mkdir(exist_ok=True)
if not HASIL_FILE.exists():
    HASIL_FILE.write_text("", encoding="utf-8")
if not PASSWORDS_FILE.exists():
    PASSWORDS_FILE.write_text("{}", encoding="utf-8")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def load_password_store():
    try:
        return json.loads(PASSWORDS_FILE.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def save_password_store(d):
    PASSWORDS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def query_ip_api(ip: str):
    try:
        url = requote_uri(IP_API_URL.format(ip))
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error("IP API error: %s", e)
        return None
    if data.get("status") == "success":
        hasil = (
            f"🌐 IP: {data.get('query')}\n"
            f"🏳 Negara: {data.get('country')}\n"
            f"🏙 Kota: {data.get('city','-')}\n"
            f"🏢 ISP: {data.get('isp','-')}\n"
            f"📡 ASN: {data.get('as','-')}\n"
            f"📍 Koordinat: {data.get('lat')},{data.get('lon')}\n"
            "---------------------------"
        )
        with open(HASIL_FILE, "a", encoding="utf-8") as f:
            f.write(hasil + "\n")
        return hasil
    else:
        return f"❌ Gagal cek IP {ip} (status: {data.get('message','unknown')})"


def generate_password_strict(length=DEFAULT_PASSLEN):
    """
    Strict password generator:
      - At least 1 uppercase, 1 lowercase, 1 digit
      - At least 2 symbols
      - No immediate repeated characters
    """
    if length < 8:
        length = 8
    uppers = string.ascii_uppercase
    lowers = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*()-_=+[]{}:;,.?/<>"
    # ensure minimal required
    password_chars = [
        secrets.choice(uppers),
        secrets.choice(lowers),
        secrets.choice(digits),
        secrets.choice(symbols),
        secrets.choice(symbols),  # ensure 2 symbols
    ]
    all_chars = uppers + lowers + digits + symbols
    for _ in range(length - len(password_chars)):
        # pick ensuring not same as last to avoid immediate repeats
        for _ in range(10):
            c = secrets.choice(all_chars)
            if not password_chars or c != password_chars[-1]:
                password_chars.append(c)
                break
        else:
            password_chars.append(secrets.choice(all_chars))
    secrets.SystemRandom().shuffle(password_chars)
    passwd = "".join(password_chars)
    # final check no immediate repeats (reduce if needed)
    out = [passwd[0]]
    for ch in passwd[1:]:
        if ch == out[-1]:
            # replace with random different char
            pool = all_chars.replace(out[-1], "")
            out.append(secrets.choice(pool))
        else:
            out.append(ch)
    return "".join(out)


def extract_ips_from_text(text: str):
    candidates = set()
    tokens = []
    for tok in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        tokens.append(tok.strip())
    for tok in tokens:
        t = tok.strip("[]()")
        if "%" in t:
            t = t.split("%", 1)[0]
        t = t.rstrip(".,:;")
        try:
            ipobj = ipaddress.ip_address(t)
            candidates.add(str(ipobj))
        except Exception:
            continue
    return sorted(candidates)


# ---- Telegram handlers ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📍 *TOOLS IP TRACK - EDITION ANGKASA (SLIM & SECURE)*\n\n"
        "Cara pakai singkat:\n"
        "• Paste IP (IPv4/IPv6) atau baris log yang mengandung IP ke chat — bot otomatis deteksi IP.\n"
        "• Bot akan memeriksa IP dan *membuat password kompleks* untuk IP itu.\n"
        "• Untuk melihat & menyalin password (HANYA SEKALI), gunakan:\n"
        "    /getpass <IP>\n"
        "Contoh: /getpass 1.2.3.4\n\n"
        "Perintah:\n"
        "/start - tampilkan instruksi\n"
        "/hasil  - unduh file hasil_ip.txt (rekaman pemeriksaan)\n"
        "/getpass <IP> - tampilkan password sekali pakai untuk IP\n"
        "/cancel - batal\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def send_hasil_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if HASIL_FILE.exists() and HASIL_FILE.stat().st_size > 0:
        await update.message.reply_document(document=InputFile(str(HASIL_FILE)), filename="hasil_ip.txt")
    else:
        await update.message.reply_text("⚠️ Belum ada hasil tersimpan.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Batal. Gunakan /start untuk melihat instruksi.")


async def auto_process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text("Tidak ada IP valid ditemukan. Paste IP (IPv4/IPv6) atau baris log yang berisi IP.")
        return

    reply_parts = []
    pw_store = load_password_store()
    for ip in ips:
        hasil = query_ip_api(ip)
        if hasil is None:
            hasil = f"❌ Error saat cek IP {ip}"
        # create one-time password record if not exists or already used -> create new
        rec = pw_store.get(ip)
        if rec and not rec.get("used"):
            # there's an unused password already — keep it (inform user how to fetch)
            info = "(password sudah di-generate, gunakan /getpass untuk mengambilnya sekali)"
        else:
            newpw = generate_password_strict()
            pw_store[ip] = {"pass": newpw, "used": False, "ts": int(time.time())}
            save_password_store(pw_store)
            info = "(password baru di-generate; gunakan /getpass untuk menampilkan sekali)"
        reply_parts.append(f"{hasil}\n🔐 Password: {info}")
    await update.message.reply_text("\n\n".join(reply_parts))


async def getpass_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("Gunakan: /getpass <IP>\nContoh: /getpass 1.2.3.4")
        return
    ip = args[0].strip()
    # validate ip
    try:
        ipobj = ipaddress.ip_address(ip)
        ip = str(ipobj)
    except Exception:
        await update.message.reply_text("Format IP tidak valid.")
        return
    pw_store = load_password_store()
    rec = pw_store.get(ip)
    if not rec:
        await update.message.reply_text("Tidak ada password terdaftar untuk IP ini. Paste dulu IP ke chat untuk generate.")
        return
    if rec.get("used"):
        await update.message.reply_text("Password untuk IP ini sudah pernah diambil dan tidak berlaku lagi.")
        return
    # send password and mark used
    passwd = rec.get("pass")
    # mark used
    rec["used"] = True
    rec["used_ts"] = int(time.time())
    pw_store[ip] = rec
    save_password_store(pw_store)
    # send password as plain message (user can copy). It's one-time because we marked used.
    await update.message.reply_text(f"🔐 Password untuk {ip} (ONE-TIME):\n`{passwd}`\n\n*Ingat*: setelah pesan ini, password tidak bisa diambil lagi.", parse_mode="Markdown")


def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hasil", send_hasil_file))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("getpass", getpass_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process_text))

    print("Bot berjalan (secure). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()


if __name__ == "__main__":
    main()
