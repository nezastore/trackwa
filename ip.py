#!/usr/bin/env python3
"""
IP Track Bot — Modern & Clean UI
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  python3 iptrack_bot.py
"""

import logging, re, requests, ipaddress, secrets, string
from requests.utils import requote_uri
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ========== CONFIG ==========
TG_TOKEN = "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
IP_API_URL = (
    "http://ip-api.com/json/{}"
    "?fields=status,message,query,country,regionName,city,isp,as,lat,lon,reverse,timezone"
)
DEFAULT_PASSLEN = 24
# ============================

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("iptrack")

# ---------- Utils ----------
MDV2_SPECIALS = r'([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.\!])'
def tg_escape(text: str) -> str:
    """Escape karakter spesial MarkdownV2 (pakai untuk NILAI/teks dinamis)."""
    return re.sub(MDV2_SPECIALS, r'\\\1', text)

def generate_password_strict(length=DEFAULT_PASSLEN) -> str:
    uppers, lowers, digits = string.ascii_uppercase, string.ascii_lowercase, string.digits
    symbols = "!@#$%^&*()-_=+[]{}:;,.?/<>"
    if length < 8: length = 8
    base = [
        secrets.choice(uppers), secrets.choice(lowers),
        secrets.choice(digits), secrets.choice(symbols), secrets.choice(symbols)
    ]
    pool = uppers + lowers + digits + symbols
    for _ in range(length - len(base)):
        c = secrets.choice(pool)
        base.append(c if not base or c != base[-1] else secrets.choice(pool.replace(c, "")))
    secrets.SystemRandom().shuffle(base)
    out = [base[0]]
    for ch in base[1:]:
        out.append(secrets.choice(pool.replace(out[-1], "")) if ch == out[-1] else ch)
    return "".join(out)

def extract_ips_from_text(text: str):
    found = set()
    for token in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        t = token.strip("[]()").rstrip(".,:;")
        if "%" in t: t = t.split("%", 1)[0]  # buang zone id IPv6
        try:
            found.add(str(ipaddress.ip_address(t)))
        except Exception:
            pass
    return sorted(found)

def fetch_ip(ip: str):
    try:
        r = requests.get(requote_uri(IP_API_URL.format(ip)), timeout=8).json()
    except Exception as e:
        logger.error("API error: %s", e)
        return {"error": f"Gagal koneksi API untuk {ip}"}
    if r.get("status") != "success":
        return {"error": f"{ip} → {r.get('message','unknown')}"}
    return {
        "ip": r.get("query"),
        "version": "IPv6" if ":" in (r.get("query") or "") else "IPv4",
        "country": r.get("country") or "-",
        "region": r.get("regionName") or "-",
        "city": r.get("city") or "-",
        "isp": r.get("isp") or "-",
        "asn": r.get("as") or "-",
        "reverse": r.get("reverse") or "-",
        "tz": r.get("timezone") or "-",
        "coords": f"{r.get('lat')}, {r.get('lon')}",
    }

def format_ip_message(data: dict) -> str:
    """
    Format modern & clean dengan MarkdownV2.
    Hanya nilai yang di-escape agar aman; label dibiarkan untuk styling.
    """
    ip = tg_escape(data["ip"])
    country = tg_escape(data["country"])
    region = tg_escape(data["region"])
    city = tg_escape(data["city"])
    isp = tg_escape(data["isp"])
    asn = tg_escape(data["asn"])
    reverse = tg_escape(data["reverse"])
    tz = tg_escape(data["tz"])
    coords = tg_escape(data["coords"])
    version = tg_escape(data["version"])

    return (
        f"🧭 *IP:* `{data['ip']}`  •  *{version}*\n"
        f"🏳️ *Country:* {country}\n"
        f"🗺️ *Region:* {region}\n"
        f"🏙️ *City:* {city}\n"
        f"🏢 *ISP:* {isp}\n"
        f"📡 *ASN:* {asn}\n"
        f"🖥️ *Reverse DNS:* {reverse}\n"
        f"⏱️ *Timezone:* {tz}\n"
        f"📍 *Coords:* {coords}"
    )

# ---------- Text ----------
START_TEXT = (
    "✨ *IP TRACK – ANGKASA EDITION*\n"
    "—\n"
    "• Kirim/paste IP (IPv4/IPv6) atau baris log yang berisi IP.\n"
    "• Bot menampilkan: Country, Region, City, ISP, ASN, Reverse DNS, Timezone, dan Coords.\n"
    "• Setiap IP akan dibuatkan *password kuat* di pesan terpisah agar mudah di-copy."
)

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tg_escape(START_TEXT), parse_mode="MarkdownV2")

async def auto_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text(tg_escape("⚠️ Tidak ada IP valid ditemukan."), parse_mode="MarkdownV2")
        return

    for ip in ips:
        data = fetch_ip(ip)
        if "error" in data:
            await update.message.reply_text(tg_escape("❌ " + data["error"]), parse_mode="MarkdownV2")
            continue

        # 1) INFO — modern & clean (MarkdownV2)
        msg = format_ip_message(data)
        await update.message.reply_text(msg, parse_mode="MarkdownV2")

        # 2) PASSWORD — pesan terpisah TANPA parse_mode agar bisa dicopy persis
        pwd = generate_password_strict()
        await update.message.reply_text(f"🔐 Password (copy 1x):\n{pwd}")

# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process))
    print("✅ Bot berjalan (auto on paste). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
