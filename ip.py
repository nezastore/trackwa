#!/usr/bin/env python3
"""
IP Track Bot (Clean UI, Reverse DNS & Timezone)
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  python3 iptrack_bot.py
"""

import logging, re, requests, ipaddress, secrets, string
from requests.utils import requote_uri
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ---------- Config ----------
TG_TOKEN = "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
IP_API_URL = (
    "http://ip-api.com/json/{}"
    "?fields=status,message,query,country,city,isp,as,lat,lon,reverse,timezone"
)
DEFAULT_PASSLEN = 24
# ----------------------------

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("iptrack")

# ---------- Utility ----------
def tg_escape(text: str) -> str:
    """Escape karakter MarkdownV2 agar aman dikirim ke Telegram."""
    return re.sub(r'([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.\!])', r'\\\1', text)

def generate_password_strict(length=DEFAULT_PASSLEN) -> str:
    uppers, lowers, digits = string.ascii_uppercase, string.ascii_lowercase, string.digits
    symbols = "!@#$%^&*()-_=+[]{}:;,.?/<>"
    if length < 8: length = 8
    base = [
        secrets.choice(uppers),
        secrets.choice(lowers),
        secrets.choice(digits),
        secrets.choice(symbols),
        secrets.choice(symbols),
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
        if "%" in t: t = t.split("%", 1)[0]
        try:
            found.add(str(ipaddress.ip_address(t)))
        except Exception:
            pass
    return sorted(found)

def query_ip_api(ip: str) -> str:
    try:
        r = requests.get(requote_uri(IP_API_URL.format(ip)), timeout=8).json()
    except Exception as e:
        logger.error("API error: %s", e)
        return f"❌ Error koneksi API untuk {ip}"
    if r.get("status") != "success":
        return f"❌ Gagal cek IP {ip}: {r.get('message','unknown')}"
    return (
        f"📍 *Hasil untuk IP:* `{r.get('query')}`\n\n"
        f"🏳️ *Negara:* {r.get('country')}\n"
        f"🏙️ *Kota:* {r.get('city','-')}\n"
        f"🏢 *ISP:* {r.get('isp','-')}\n"
        f"📡 *ASN:* {r.get('as','-')}\n"
        f"🖥️ *Reverse DNS:* `{r.get('reverse','-')}`\n"
        f"🕓 *Timezone:* `{r.get('timezone','-')}`\n"
        f"🧭 *Koordinat:* {r.get('lat')}, {r.get('lon')}"
    )

# ---------- Text ----------
HELP_TEXT = (
    "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
    "  🚀 *IP TRACK – ANGKASA EDITION*\n"
    "┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
    "✨ *Cara Pakai:*\n"
    "• Paste IP (IPv4/IPv6) atau baris log berisi IP.\n"
    "• Bot akan otomatis menampilkan detail lengkap:\n"
    "  Negara, Kota, ISP, ASN, Reverse DNS, Timezone, dan Koordinat.\n"
    "• Setiap kali Anda paste IP, bot juga membuat *Password acak & kuat*.\n\n"
    "💡 *Tips:* Bisa kirim beberapa IP sekaligus (mis. potongan log)."
)

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tg_escape(HELP_TEXT), parse_mode="MarkdownV2")

async def auto_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text(tg_escape("⚠️ Tidak ada IP valid ditemukan."), parse_mode="MarkdownV2")
        return

    results = []
    for ip in ips:
        info = query_ip_api(ip)
        passwd = generate_password_strict()
        # tampil elegan seperti kartu
        block = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{tg_escape(info)}\n\n"
            "🔐 *Password (copy 1x)*:\n"
            f"╔══════════════════════╗\n"
            f"║ `{passwd}` ║\n"
            f"╚══════════════════════╝"
        )
        results.append(block)

    await update.message.reply_text("\n\n".join(results), parse_mode="MarkdownV2")

# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process))
    print("✅ Bot berjalan (auto on paste). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
