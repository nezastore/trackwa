#!/usr/bin/env python3
"""
IP Track Bot (Slim, auto-password on paste)
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  export TG_TOKEN="your_token_here"
  python3 iptrack_bot.py
"""

import logging, os, requests, ipaddress, secrets, string
from pathlib import Path
from requests.utils import requote_uri
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ---------- Config ----------
TG_TOKEN = os.environ.get("TG_TOKEN") or "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
DATA_DIR = Path("bot_data")
HASIL_FILE = DATA_DIR / "hasil_ip.txt"
IP_API_URL = "http://ip-api.com/json/{}"
DEFAULT_PASSLEN = 24  # password lebih rumit & ketat
# ----------------------------

DATA_DIR.mkdir(exist_ok=True)
if not HASIL_FILE.exists():
    HASIL_FILE.write_text("", encoding="utf-8")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def query_ip_api(ip: str):
    try:
        url = requote_uri(IP_API_URL.format(ip))   # aman untuk IPv6
        r = requests.get(url, timeout=8); r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error("IP API error: %s", e); return None

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
    return f"❌ Gagal cek IP {ip} (status: {data.get('message','unknown')})"

def generate_password_strict(length=DEFAULT_PASSLEN):
    """Password kuat: ≥1 upper, ≥1 lower, ≥1 digit, ≥2 simbol, tanpa karakter berulang berdempetan."""
    if length < 8: length = 8
    uppers, lowers, digits = string.ascii_uppercase, string.ascii_lowercase, string.digits
    symbols = "!@#$%^&*()-_=+[]{}:;,.?/<>"
    base = [secrets.choice(uppers), secrets.choice(lowers), secrets.choice(digits),
            secrets.choice(symbols), secrets.choice(symbols)]
    pool = uppers + lowers + digits + symbols
    for _ in range(length - len(base)):
        for _ in range(10):
            c = secrets.choice(pool)
            if not base or c != base[-1]: base.append(c); break
        else:
            base.append(secrets.choice(pool))
    secrets.SystemRandom().shuffle(base)
    out = [base[0]]
    for ch in base[1:]:
        out.append(secrets.choice(pool.replace(out[-1], "")) if ch == out[-1] else ch)
    return "".join(out)

def extract_ips_from_text(text: str):
    """Deteksi IPv4 & IPv6 dari teks (termasuk baris log)."""
    candidates = set()
    for tok in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        t = tok.strip("[]()").rstrip(".,:;")
        if "%" in t: t = t.split("%", 1)[0]  # hapus zone id IPv6
        try:
            candidates.add(str(ipaddress.ip_address(t)))
        except Exception:
            pass
    return sorted(candidates)

# ----------------- Telegram Handlers -----------------

START_HELP_TEXT = (
    "📍 *TOOLS IP TRACK - EDITION ANGKASA (SLIM)*\n\n"
    "Cara pakai:\n"
    "• Cukup *paste* IP (IPv4/IPv6) atau baris log yang berisi IP — bot otomatis deteksi & cek.\n"
    "• Password *kompleks* akan langsung muncul di bawah hasil IP (baru setiap kali Anda paste IP).\n\n"
    "Perintah:\n"
    "• /start  — tampilkan petunjuk ini\n"
    "• /hasil  — unduh rekaman hasil (hasil_ip.txt)\n"
    "• /cancel — batal\n\n"
    "Kriteria password: panjang default 24, berisi huruf besar, huruf kecil, angka, dan simbol; "
    "acak kuat (cryptographically secure) dan diacak ulang setiap kali Anda paste IP."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_HELP_TEXT, parse_mode="Markdown")

async def send_hasil_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if HASIL_FILE.exists() and HASIL_FILE.stat().st_size > 0:
        await update.message.reply_document(document=InputFile(str(HASIL_FILE)), filename="hasil_ip.txt")
    else:
        await update.message.reply_text("⚠️ Belum ada hasil tersimpan.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Batal. Gunakan /start untuk petunjuk.")

async def auto_process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Setiap teks masuk: cari IP, cek, dan tampilkan password di bawahnya."""
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text("Tidak ada IP valid ditemukan. Paste IP (IPv4/IPv6) atau baris log yang berisi IP.")
        return

    reply_parts = []
    for ip in ips:
        hasil = query_ip_api(ip) or f"❌ Error saat cek IP {ip}"
        passwd = generate_password_strict()
        reply_parts.append(f"{hasil}\n🔐 Password (salin 1x):\n`{passwd}`")
    full = "\n\n".join(reply_parts)
    # jika terlalu panjang, tetap kirim sebagai pesan (Telegram cukup toleran); bisa diubah ke dokumen bila perlu
    await update.message.reply_text(full, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hasil", send_hasil_file))
    app.add_handler(CommandHandler("cancel", cancel))
    # auto deteksi IP dari teks biasa (tanpa tombol/menu)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process_text))
    print("Bot berjalan (auto on paste). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
