#!/usr/bin/env python3
"""
IP Track Bot - Telegram-only
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  export TG_TOKEN="8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
  python3 iptrack_bot.py
"""

import logging
import os
import re
import requests
from pathlib import Path
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

# ---------- Config ----------
TG_TOKEN = os.environ.get("TG_TOKEN") or "PUT_YOUR_TOKEN_HERE"
DATA_DIR = Path("bot_data")
TARGET_WA_FILE = DATA_DIR / "target_wa.txt"
HASIL_FILE = DATA_DIR / "hasil_ip.txt"
LOGS_DIR = DATA_DIR / "uploaded_logs"
IP_API_URL = "http://ip-api.com/json/{}"
# ----------------------------

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
if not TARGET_WA_FILE.exists():
    TARGET_WA_FILE.write_text("", encoding="utf-8")
if not HASIL_FILE.exists():
    HASIL_FILE.write_text("", encoding="utf-8")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(
    STATE_AWAIT_IP,
    STATE_AWAIT_IPFILE,
    STATE_AWAIT_LOGFILE_FOR_AUTOSCAN,
    STATE_AWAIT_WA_NUMBER,
    STATE_AWAIT_LOGFILE_FOR_SCAN_WA,
    STATE_AWAIT_MANUAL_TRACK
) = range(6)


def build_menu_keyboard():
    buttons = [
        [InlineKeyboardButton("1. Cek IP manual", callback_data="menu_1"),
         InlineKeyboardButton("2. Cek IP dari file", callback_data="menu_2")],
        [InlineKeyboardButton("3. Auto-scan dari log", callback_data="menu_3"),
         InlineKeyboardButton("4. Lihat hasil sebelumnya", callback_data="menu_4")],
        [InlineKeyboardButton("5. Tambah nomor WhatsApp", callback_data="menu_5"),
         InlineKeyboardButton("6. Scan log untuk nomor WA", callback_data="menu_6")],
        [InlineKeyboardButton("7. Track manual (Nomor + IP)", callback_data="menu_7"),
         InlineKeyboardButton("8. Keluar", callback_data="menu_8")],
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📍 *TOOLS IP TRACK - EDITION ANGKASA*\n\n"
        "Pilih salah satu menu di bawah (gunakan tombol)."
    )
    await update.message.reply_text(text, reply_markup=build_menu_keyboard(), parse_mode="Markdown")


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_1":
        await query.message.reply_text("Ketik IP yang ingin dicek, atau /cancel untuk batal:")
        return STATE_AWAIT_IP

    if data == "menu_2":
        await query.message.reply_text(
            "Kirim file teks (.txt) berisi daftar IP (1 IP per baris). Atau gunakan /cancel."
        )
        return STATE_AWAIT_IPFILE

    if data == "menu_3":
        await query.message.reply_text(
            "Kirim file log server (upload) untuk auto-scan IP, atau ketik nama file jika sudah di-upload sebelumnya."
        )
        return STATE_AWAIT_LOGFILE_FOR_AUTOSCAN

    if data == "menu_4":
        if HASIL_FILE.exists() and HASIL_FILE.stat().st_size > 0:
            await query.message.reply_document(document=InputFile(str(HASIL_FILE)), filename="hasil_ip.txt")
        else:
            await query.message.reply_text("⚠️ Belum ada hasil disimpan.")
        return ConversationHandler.END

    if data == "menu_5":
        await query.message.reply_text("Ketik nomor WhatsApp target (format internasional tanpa +, contoh: 6281234567890):")
        return STATE_AWAIT_WA_NUMBER

    if data == "menu_6":
        await query.message.reply_text("Upload file log server (yang akan discan untuk nomor WA target):")
        return STATE_AWAIT_LOGFILE_FOR_SCAN_WA

    if data == "menu_7":
        await query.message.reply_text("Kirim data dalam format: nomor|ip (contoh: 6281234567890|1.2.3.4)")
        return STATE_AWAIT_MANUAL_TRACK

    if data == "menu_8":
        await query.message.reply_text("👋 Keluar. Gunakan /start lagi jika perlu.")
        return ConversationHandler.END

    await query.message.reply_text("Pilihan tidak dikenali.")
    return ConversationHandler.END


def query_ip_api(ip: str):
    try:
        r = requests.get(IP_API_URL.format(ip), timeout=8).json()
    except Exception as e:
        logger.error("IP API error: %s", e)
        return None
    if r.get("status") == "success":
        hasil = (
            f"🌐 IP: {r.get('query')}\n"
            f"🏳 Negara: {r.get('country')}\n"
            f"🏙 Kota: {r.get('city','-')}\n"
            f"🏢 ISP: {r.get('isp','-')}\n"
            f"📡 ASN: {r.get('as','-')}\n"
            f"📍 Koordinat: {r.get('lat')},{r.get('lon')}\n"
            "---------------------------"
        )
        # simpan
        with open(HASIL_FILE, "a", encoding="utf-8") as f:
            f.write(hasil + "\n")
        return hasil
    else:
        return f"❌ Gagal cek IP {ip} (status: {r.get('message','unknown')})"


# ----------------- Handlers for conversation states -----------------

async def handle_manual_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Input kosong. Batal.")
        return ConversationHandler.END
    # basic IP validation
    m = re.match(r'^\s*(\d{1,3}(?:\.\d{1,3}){3})\s*$', text)
    if not m:
        await update.message.reply_text("Format IP tidak valid. Coba lagi atau /cancel.")
        return STATE_AWAIT_IP
    ip = m.group(1)
    hasil = query_ip_api(ip)
    await update.message.reply_text(hasil)
    return ConversationHandler.END


async def handle_ipfile_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # expects a document upload of a text file with IPs
    doc = update.message.document
    if not doc:
        await update.message.reply_text("Tolong upload file teks (.txt) yang berisi IP.")
        return STATE_AWAIT_IPFILE
    fpath = LOGS_DIR / doc.file_name
    await doc.get_file().download_to_drive(custom_path=str(fpath))
    # read and process
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        ips = [line.strip() for line in f if line.strip()]
    if not ips:
        await update.message.reply_text("File kosong atau tidak ada IP.")
        return ConversationHandler.END
    msg_chunks = []
    for ip in ips:
        # basic ip extraction (in case file has extras)
        m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', ip)
        if m:
            hasil = query_ip_api(m.group(1))
            msg_chunks.append(hasil)
    await update.message.reply_text("\n".join(msg_chunks[:10]) + ("\n... (lainnya disimpan ke hasil_ip.txt)" if len(msg_chunks) > 10 else ""))
    return ConversationHandler.END


async def handle_autoscan_logfile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Accept either uploaded document or text message with filename when previously uploaded
    if update.message.document:
        doc = update.message.document
        fpath = LOGS_DIR / doc.file_name
        await doc.get_file().download_to_drive(custom_path=str(fpath))
    else:
        # user typed filename
        name = (update.message.text or "").strip()
        fpath = LOGS_DIR / name
        if not fpath.exists():
            await update.message.reply_text("File tidak ditemukan di server. Upload file log terlebih dahulu.")
            return ConversationHandler.END

    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()

    ips = sorted(set(re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', data)))
    if not ips:
        await update.message.reply_text("⚠️ Tidak ada IP ditemukan di log.")
        return ConversationHandler.END

    await update.message.reply_text(f"📊 Ditemukan {len(ips)} IP unik. Mulai cek (menyimpan hasil ke hasil_ip.txt)...")
    # process but avoid flooding chat: send summary
    summary = []
    for ip in ips:
        hasil = query_ip_api(ip)
        summary.append(hasil)
    # send only first 8 entries, full file already saved in hasil_ip.txt
    await update.message.reply_text("\n\n".join(summary[:8]) + (("\n\n... hasil lengkap disimpan ke hasil_ip.txt") if len(summary) > 8 else ""))
    # optionally send hasil file
    await update.message.reply_document(document=InputFile(str(HASIL_FILE)), filename="hasil_ip.txt")
    return ConversationHandler.END


async def handle_wa_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nomor = (update.message.text or "").strip()
    if not nomor.startswith("62"):
        await update.message.reply_text("⚠️ Gunakan format internasional tanpa +. Contoh: 6281234567890")
        return STATE_AWAIT_WA_NUMBER
    # simpan
    with open(TARGET_WA_FILE, "a", encoding="utf-8") as f:
        f.write(nomor + "\n")
    await update.message.reply_text(f"✅ Nomor {nomor} disimpan.")
    return ConversationHandler.END


async def handle_scan_log_for_wa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # user must upload log (document) that will be scanned against targets
    if update.message.document:
        doc = update.message.document
        fpath = LOGS_DIR / doc.file_name
        await doc.get_file().download_to_drive(custom_path=str(fpath))
    else:
        await update.message.reply_text("Upload file log (dokumen).")
        return STATE_AWAIT_LOGFILE_FOR_SCAN_WA

    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()

    targets = [t.strip() for t in TARGET_WA_FILE.read_text(encoding="utf-8").splitlines() if t.strip()]
    if not targets:
        await update.message.reply_text("⚠️ Belum ada nomor target. Tambahkan dulu lewat menu 5.")
        return ConversationHandler.END

    found_any = False
    reply_parts = []
    for nomor in targets:
        if nomor in data:
            found_any = True
            lines = [l for l in data.splitlines() if nomor in l]
            for l in lines:
                m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', l)
                if m:
                    ip = m.group(1)
                    hasil = query_ip_api(ip)
                    reply_parts.append(f"Nomor: {nomor}\n{hasil}")

    if not found_any:
        await update.message.reply_text("⚠️ Tidak ada nomor target ditemukan di log.")
    else:
        # send as document if too long
        text_out = "\n\n".join(reply_parts)
        if len(text_out) > 3500:
            temp = DATA_DIR / "scan_wa_result.txt"
            temp.write_text(text_out, encoding="utf-8")
            await update.message.reply_document(document=InputFile(str(temp)), filename="scan_wa_result.txt")
        else:
            await update.message.reply_text(text_out)
    return ConversationHandler.END


async def handle_manual_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    # allow "nomor|ip" or "nomor ip"
    if "|" in text:
        nomor, ip = [p.strip() for p in text.split("|", 1)]
    else:
        parts = text.split()
        if len(parts) >= 2:
            nomor, ip = parts[0], parts[1]
        else:
            await update.message.reply_text("Format salah. Contoh: 6281234567890|1.2.3.4")
            return STATE_AWAIT_MANUAL_TRACK

    m = re.match(r'(\d{1,3}(?:\.\d{1,3}){3})', ip)
    if not m:
        await update.message.reply_text("Format IP tidak valid.")
        return STATE_AWAIT_MANUAL_TRACK
    ip_clean = m.group(1)
    hasil = query_ip_api(ip_clean)
    pesan = f"📱 *Track Manual*\nNomor: {nomor}\n{hasil}"
    await update.message.reply_text(pesan, parse_mode="Markdown")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Batal. Gunakan /start untuk kembali ke menu.")
    return ConversationHandler.END


# fallback: plain messages when not in conversation
async def text_handler_default(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Gunakan /start untuk membuka menu.")


def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_callback, pattern="^menu_")],
        states={
            STATE_AWAIT_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_ip)],
            STATE_AWAIT_IPFILE: [MessageHandler(filters.Document.ALL, handle_ipfile_upload)],
            STATE_AWAIT_LOGFILE_FOR_AUTOSCAN: [
                MessageHandler(filters.Document.ALL | (filters.TEXT & ~filters.COMMAND), handle_autoscan_logfile)
            ],
            STATE_AWAIT_WA_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wa_number)],
            STATE_AWAIT_LOGFILE_FOR_SCAN_WA: [
                MessageHandler(filters.Document.ALL, handle_scan_log_for_wa)
            ],
            STATE_AWAIT_MANUAL_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_track)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        persistent=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))  # buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler_default))
    app.add_handler(CommandHandler("cancel", cancel))

    print("Bot berjalan. Tekan Ctrl+C untuk berhenti.")
    app.run_polling()


if __name__ == "__main__":
    main()
