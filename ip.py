#!/usr/bin/env python3
"""
Slimmed IP Track Bot - Telegram-only (updated)
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  export TG_TOKEN="your_token_here"
  python3 iptrack_bot.py

What changed:
- Removed menu items 2..7 and their handlers (file-scan, WA features)
- Bot now auto-detects IPv4/IPv6 from any pasted text and replies immediately
- Adds a password generator on each IP paste (secure, characters vary each time)
- Uses ipaddress for robust IP validation
"""

import logging
import os
import requests
import ipaddress
import secrets
import string
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
IP_API_URL = "http://ip-api.com/json/{}"
DEFAULT_PASSLEN = 16
# ----------------------------

DATA_DIR.mkdir(exist_ok=True)
if not HASIL_FILE.exists():
    HASIL_FILE.write_text("", encoding="utf-8")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def query_ip_api(ip: str):
    try:
        # safe quoting for IPv6
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
        # append to hasil file
        with open(HASIL_FILE, "a", encoding="utf-8") as f:
            f.write(hasil + "\n")
        return hasil
    else:
        return f"❌ Gagal cek IP {ip} (status: {data.get('message','unknown')})"


def generate_password(length=DEFAULT_PASSLEN):
    """
    Generate a password containing at least one char from each required set:
    - Uppercase, Lowercase, Digits, Symbols
    Uses secrets for cryptographically secure randomness.
    """
    if length < 4:
        length = 4
    sets = {
        "upper": string.ascii_uppercase,
        "lower": string.ascii_lowercase,
        "digits": string.digits,
        "symbols": "!@#$%^&*",
    }
    # ensure at least one from each
    password_chars = [
        secrets.choice(sets["upper"]),
        secrets.choice(sets["lower"]),
        secrets.choice(sets["digits"]),
        secrets.choice(sets["symbols"]),
    ]
    all_chars = "".join(sets.values())
    # fill the rest
    for _ in range(length - 4):
        password_chars.append(secrets.choice(all_chars))
    # shuffle securely
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


def extract_ips_from_text(text: str):
    """
    Extract tokens that may be IP addresses, validate with ipaddress.ip_address.
    Returns list of valid IP strings (unique, in original textual form).
    """
    candidates = set()
    # quick tokenization: split on whitespace and punctuation that commonly separates tokens
    raw_tokens = []
    for tok in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        raw_tokens.append(tok.strip())
    # also check tokens that include ':' (likely IPv6)
    # attempt validation via ipaddress
    for tok in raw_tokens:
        # remove surrounding brackets (common for IPv6 in text) and strip scope id (%...)
        t = tok.strip("[]")
        if "%" in t:  # remove zone id like fe80::1%eth0
            t = t.split("%", 1)[0]
        # sometimes t may include trailing punctuation
        t = t.rstrip(".,:;")
        try:
            ipobj = ipaddress.ip_address(t)
            candidates.add(str(ipobj))
        except Exception:
            # not an IP
            continue
    return sorted(candidates)


# ---- Telegram handlers ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📍 *TOOLS IP TRACK - EDITION ANGKASA (SLIM)*\n\n"
        "Cara pakai:\n"
        "• Cukup *paste* IP (IPv4 atau IPv6) atau baris log yang berisi IP ke chat — bot akan otomatis mendeteksi dan menampilkan hasil.\n"
        "• Bot juga akan menghasilkan satu *password* baru setiap kali Anda paste IP.\n\n"
        "Perintah:\n"
        "/start - tampilkan pesan ini\n"
        "/hasil - unduh file hasil_ip.txt\n"
        "/cancel - batal (tidak ada percakapan aktif)\n"
        "\nContoh: `1.2.3.4`  atau `2001:0db8:85a3:0000:0000:8a2e:0370:7334`"
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
    """
    Main auto handler: if the message contains any valid IPv4/IPv6, process them.
    Otherwise, prompt user to paste IP.
    """
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text("Tidak ada IP valid ditemukan. Paste IP (IPv4/IPv6) atau baris log yang berisi IP.")
        return

    # For each IP, query and append password
    reply_parts = []
    for ip in ips:
        hasil = query_ip_api(ip)
        if hasil is None:
            hasil = f"❌ Error saat cek IP {ip}"
        # generate password for this IP (length default)
        password = generate_password()
        reply_parts.append(f"{hasil}\n🔐 Generated password: `{password}`")
    # send combined reply (markdown for password code)
    # limit message length: if too long, send as file
    full_reply = "\n\n".join(reply_parts)
    if len(full_reply) > 3500:
        temp = DATA_DIR / "ip_query_result.txt"
        temp.write_text(full_reply, encoding="utf-8")
        await update.message.reply_document(document=InputFile(str(temp)), filename="ip_query_result.txt")
    else:
        await update.message.reply_text(full_reply, parse_mode="Markdown")


async def text_default(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # fallback for other texts (shouldn't be necessary because auto_process_text handles text)
    await update.message.reply_text("Paste an IP (IPv4 or IPv6) and I'll check it automatically.")


def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hasil", send_hasil_file))
    app.add_handler(CommandHandler("cancel", cancel))

    # auto IP detection handler: any text message will be checked for IPs
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process_text))

    print("Bot berjalan (slim). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()


if __name__ == "__main__":
    main()
