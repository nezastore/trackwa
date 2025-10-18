#!/usr/bin/env python3
"""
IP Track Bot (Auto IPv4/IPv6, Reverse DNS & Timezone, Fancy UI)
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  python3 iptrack_bot.py
"""

import logging, os, re, requests, ipaddress, secrets, string
from pathlib import Path
from requests.utils import requote_uri
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ---------- Config ----------
TG_TOKEN = "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
DATA_DIR = Path("bot_data")
HASIL_FILE = DATA_DIR / "hasil_ip.txt"
# minta field tambahan: reverse DNS & timezone (gratis di ip-api.com)
IP_API_URL = "http://ip-api.com/json/{}?fields=status,message,query,country,city,isp,as,lat,lon,reverse,timezone"
DEFAULT_PASSLEN = 24  # password kuat & panjang
# ----------------------------

DATA_DIR.mkdir(exist_ok=True)
if not HASIL_FILE.exists():
    HASIL_FILE.write_text("", encoding="utf-8")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Helpers ----------
MDV2_SPECIALS = r'[_*[\]()~`>#+\-=|{}.!]'

def tg_escape(text: str) -> str:
    """Escape karakter spesial MarkdownV2 supaya aman dikirim ke Telegram."""
    return re.sub(f'({MDV2_SPECIALS})', r'\\\1', text)

def generate_password_strict(length=DEFAULT_PASSLEN) -> str:
    """Password kuat: ≥1 upper, ≥1 lower, ≥1 digit, ≥2 simbol, tanpa duplikasi berdempetan."""
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
    # isi sisa
    for _ in range(length - len(base)):
        c = secrets.choice(pool)
        if not base or c != base[-1]:
            base.append(c)
        else:
            # cari alternatif cepat biar tak berdempetan
            base.append(secrets.choice(pool.replace(c, '')))
    # shuffle
    secrets.SystemRandom().shuffle(base)
    # bersihkan duplikasi berdempetan pasca-shuffle
    out = [base[0]]
    for ch in base[1:]:
        out.append(secrets.choice(pool.replace(out[-1], "")) if ch == out[-1] else ch)
    return "".join(out)

def extract_ips_from_text(text: str):
    """Deteksi IPv4 & IPv6 dari teks (termasuk baris log)."""
    candidates = set()
    for tok in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        t = tok.strip("[]()").rstrip(".,:;")
        if "%" in t:  # buang zone id IPv6
            t = t.split("%", 1)[0]
        try:
            candidates.add(str(ipaddress.ip_address(t)))
        except Exception:
            pass
    return sorted(candidates)

def query_ip_api(ip: str):
    """Ambil info IP dari ip-api (gratis). Kembalikan teks polos (tanpa Markdown)."""
    try:
        url = requote_uri(IP_API_URL.format(ip))   # aman utk IPv6
        r = requests.get(url, timeout=8); r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error("IP API error: %s", e)
        return None

    if data.get("status") != "success":
        return f"❌ Gagal cek IP {ip} (status: {data.get('message','unknown')})"

    # teks polos (nanti baru di-escape sebelum dikirim)
    hasil = (
        "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
        "  🌐 IP INSIGHT RESULT\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━┛\n"
        f"🧭 IP            : {data.get('query')}\n"
        f"🏳️ Negara       : {data.get('country')}\n"
        f"🏙️ Kota         : {data.get('city','-')}\n"
        f"🏢 ISP          : {data.get('isp','-')}\n"
        f"📡 ASN          : {data.get('as','-')}\n"
        f"🖥️ Reverse DNS  : {data.get('reverse','-')}\n"
        f"🕓 Timezone     : {data.get('timezone','-')}\n"
        f"📍 Koordinat    : {data.get('lat')},{data.get('lon')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    # simpan versi polos ke file
    with open(HASIL_FILE, "a", encoding="utf-8") as f:
        f.write(hasil + "\n")
    return hasil

# ---------- UI Text ----------
START_HELP_TEXT = (
    "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
    "  🚀 IP TRACK – ANGKASA EDITION\n"
    "┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
    "✨ Cara pakai cepat:\n"
    "• Cukup paste IP (IPv4/IPv6) atau baris log yang berisi IP.\n"
    "• Bot otomatis menampilkan detail: Negara, Kota, ISP, ASN,\n"
    "  Reverse DNS, Timezone, dan Koordinat.\n"
    "• Setiap kali Anda paste IP, bot membuat Password acak & kuat.\n\n"
    "🛠️ Perintah:\n"
    "• /start  — tampilkan panduan ini\n"
    "• /hasil  — unduh file hasil_ip.txt\n"
    "• /cancel — batalkan proses\n\n"
    "💡 Tips: Anda bisa kirim banyak IP sekaligus (mis. potongan log)."
)

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Escape lalu kirim dengan MarkdownV2 agar anti error
    await update.message.reply_text(tg_escape(START_HELP_TEXT), parse_mode="MarkdownV2")

async def send_hasil_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if HASIL_FILE.exists() and HASIL_FILE.stat().st_size > 0:
        await update.message.reply_document(document=InputFile(str(HASIL_FILE)), filename="hasil_ip.txt")
    else:
        await update.message.reply_text(tg_escape("⚠️ Belum ada hasil tersimpan."), parse_mode="MarkdownV2")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tg_escape("✅ Dibatalkan. Gunakan /start untuk melihat panduan."), parse_mode="MarkdownV2")

async def auto_process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tiap teks masuk: cari IP, cek, dan tampilkan password di bawahnya."""
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text(
            tg_escape("Tidak ada IP valid ditemukan. Paste IP (IPv4/IPv6) atau baris log yang berisi IP."),
            parse_mode="MarkdownV2"
        )
        return

    # untuk setiap IP: hasil + password (password ditaruh dalam code block agar mudah copy)
    messages = []
    for ip in ips:
        plain_result = query_ip_api(ip) or f"❌ Error saat cek IP {ip}"
        escaped_result = tg_escape(plain_result)
        passwd = generate_password_strict()
        msg = f"{escaped_result}\n🔐 {tg_escape('Password (copy 1x):')}\n```\n{passwd}\n```"
        messages.append(msg)

    final_text = "\n".join(messages)
    await update.message.reply_text(final_text, parse_mode="MarkdownV2")

# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hasil", send_hasil_file))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process_text))
    print("✅ Bot berjalan (auto on paste). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
