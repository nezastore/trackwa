#!/usr/bin/env python3
"""
IP Track Bot (auto-password, reverse DNS & timezone, polished UI)
Deps:
  pip install python-telegram-bot==20.4 requests
Run:
  export TG_TOKEN="8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
  python3 iptrack_bot.py
"""

import logging, os, requests, ipaddress, secrets, string
from pathlib import Path
from requests.utils import requote_uri
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ====== Config ======
TG_TOKEN = os.environ.get("TG_TOKEN") or ""
DATA_DIR = Path("bot_data")
HASIL_FILE = DATA_DIR / "hasil_ip.txt"
# minta reverse DNS & timezone juga (gratis di ip-api.com)
IP_API_URL = (
    "http://ip-api.com/json/{}"
    "?fields=status,message,query,country,city,isp,as,lat,lon,reverse,timezone"
)
DEFAULT_PASSLEN = 24  # password kuat
# ====================

DATA_DIR.mkdir(exist_ok=True)
if not HASIL_FILE.exists():
    HASIL_FILE.write_text("", encoding="utf-8")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------- Core helpers ----------
def query_ip_api(ip: str):
    """Query ip-api (gratis) + reverse DNS + timezone, aman untuk IPv6."""
    try:
        url = requote_uri(IP_API_URL.format(ip))
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error("IP API error: %s", e)
        return None

    if data.get("status") != "success":
        return f"❌ Gagal cek IP {ip} (status: {data.get('message','unknown')})"

    # tampilan rapi + emoji
    hasil = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 **IP**: `{data.get('query')}`\n"
        f"🏳️ **Negara**: {data.get('country')}\n"
        f"🏙️ **Kota**: {data.get('city','-')}\n"
        f"🏢 **ISP**: {data.get('isp','-')}\n"
        f"📡 **ASN**: {data.get('as','-')}\n"
        f"🖥️ **Reverse DNS**: `{data.get('reverse','-')}`\n"
        f"🕓 **Timezone**: {data.get('timezone','-')}\n"
        f"📍 **Koordinat**: {data.get('lat')},{data.get('lon')}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    # simpan ringkas ke file hasil
    with open(HASIL_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"IP={data.get('query')} | Country={data.get('country')} | City={data.get('city','-')} | "
            f"ISP={data.get('isp','-')} | ASN={data.get('as','-')} | RDNS={data.get('reverse','-')} | "
            f"Tz={data.get('timezone','-')} | LatLon={data.get('lat')},{data.get('lon')}\n"
        )
    return hasil


def generate_password_strict(length=DEFAULT_PASSLEN):
    """
    Password kuat & ketat:
      - ≥1 huruf besar, ≥1 huruf kecil, ≥1 angka, ≥2 simbol
      - tanpa karakter berulang berdempetan
      - cryptographically secure (secrets)
    """
    if length < 8:
        length = 8
    U, L, D = string.ascii_uppercase, string.ascii_lowercase, string.digits
    S = "!@#$%^&*()-_=+[]{}:;,.?/<>"
    pool = U + L + D + S

    base = [
        secrets.choice(U), secrets.choice(L), secrets.choice(D),
        secrets.choice(S), secrets.choice(S)
    ]
    for _ in range(length - len(base)):
        # hindari duplikasi berdempetan saat build
        for _ in range(10):
            c = secrets.choice(pool)
            if c != base[-1]:
                base.append(c)
                break
        else:
            base.append(secrets.choice(pool))

    # shuffle & cek lagi tidak ada berdempetan
    secrets.SystemRandom().shuffle(base)
    out = [base[0]]
    for ch in base[1:]:
        out.append(secrets.choice(pool.replace(out[-1], "")) if ch == out[-1] else ch)
    return "".join(out)


def extract_ips_from_text(text: str):
    """
    Deteksi IPv4 & IPv6 dari teks/baris log.
    Bonus: jika ada IPv4 terselip dalam teks IPv6 (mapped), kita tangkap keduanya.
    """
    ips = set()

    # tokenisasi sederhana
    for tok in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        t = tok.strip("[]()<>").rstrip(".,:;")
        if "%" in t:  # hapus zone id IPv6
            t = t.split("%", 1)[0]
        # validasi IP umum
        try:
            ipobj = ipaddress.ip_address(t)
            ips.add(str(ipobj))
        except Exception:
            pass

        # cari IPv4 murni di dalam token (mis. log panjang)
        import re
        for m in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", t):
            try:
                ipobj = ipaddress.ip_address(m)
                ips.add(str(ipobj))
            except Exception:
                pass

    return sorted(ips)


# ---------- Telegram handlers ----------
START_HELP_TEXT = (
    "🛰️ **TOOLS IP TRACK — Edition ANGKASA**\n"
    "Mode: _Slim, Auto-Detect, Secure_\n\n"
    "🚀 **Cara Pakai Cepat**\n"
    "• Cukup **paste** IP (IPv4/IPv6) atau *baris log yang berisi IP* ke chat.\n"
    "• Bot otomatis mendeteksi IP ➜ menampilkan lokasi, ISP, **Reverse DNS**, **Timezone**, koordinat.\n"
    "• Bot juga membuat **password kompleks baru** setiap kali Anda paste IP.\n\n"
    "🧩 **Perintah**\n"
    "• `/start` atau `/help` — tampilkan panduan ini\n"
    "• `/hasil` — unduh rekaman hasil (`hasil_ip.txt`)\n"
    "• `/cancel` — batalkan (tidak ada sesi aktif)\n\n"
    "🔒 **Password**\n"
    f"• Panjang default: {DEFAULT_PASSLEN} karakter\n"
    "• Komposisi: Huruf besar, huruf kecil, angka, dan simbol (ketat, acak kuat)\n"
    "• Password **selalu baru** setiap Anda paste IP.\n"
    "—\n"
    "_Tips: Kirim beberapa IP dalam satu pesan? Bot akan memproses semuanya._"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tampil saat user tekan tombol Start ATAU kirim /start
    if update.message:
        await update.message.reply_text(START_HELP_TEXT, parse_mode="Markdown")
    else:
        # fallback seandainya someday Telegram kirim sebagai callback (jarang)
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=START_HELP_TEXT, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def send_hasil_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if HASIL_FILE.exists() and HASIL_FILE.stat().st_size > 0:
        await update.message.reply_document(document=InputFile(str(HASIL_FILE)), filename="hasil_ip.txt")
    else:
        await update.message.reply_text("⚠️ Belum ada hasil tersimpan.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Selesai. Gunakan /start untuk melihat panduan.")

async def auto_process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Setiap teks: cari IP, cek, dan tampilkan password di bawahnya."""
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text(
            "ℹ️ Tidak ada IP valid ditemukan. Paste IP (IPv4/IPv6) atau baris log yang berisi IP.",
        )
        return

    blocks = []
    for ip in ips:
        hasil = query_ip_api(ip) or f"❌ Error saat cek IP `{ip}`"
        passwd = generate_password_strict()
        blocks.append(f"{hasil}\n🔐 **Password (salin 1x)**:\n`{passwd}`")

    full = "\n\n".join(blocks)
    await update.message.reply_text(full, parse_mode="Markdown")

def main():
    if not TG_TOKEN:
        raise SystemExit("Set TG_TOKEN dulu: export TG_TOKEN='xxx:yyyy'")

    app = ApplicationBuilder().token(TG_TOKEN).build()

    # Pastikan /start SELALU bekerja (+ alias /help)
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("hasil", send_hasil_file))
    app.add_handler(CommandHandler("cancel", cancel))

    # Auto deteksi IP dari semua teks non-command
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process_text))

    print("Bot berjalan (polished). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
