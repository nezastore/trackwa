import os
import re
import requests

BOT_TOKEN = "7537238316:AAEqj8WcSqylacZ1YdKdA4lcDPPRBqxh_as"
CHAT_ID = "7537238316"

R = "\033[1;31m"
G = "\033[1;32m"
Y = "\033[1;33m"
B = "\033[1;34m"
C = "\033[1;36m"
W = "\033[0m"

TARGET_WA_FILE = "target_wa.txt"

def banner():
    os.system("clear")
    print(f"""{C}
=============================================
  📍{Y}TOOLS IP TRACK - EDITION ANGKASA{C}
=============================================

{G}[1]{B} Cek IP manual
{G}[2]{B} Cek IP dari file list
{G}[3]{B} Auto-scan dari log server
{G}[4]{B} Lihat hasil sebelumnya
{G}[5]{B} Tambah nomor WhatsApp target
{G}[6]{B} Scan log untuk nomor WA (lacak lokasi)
{G}[7]{B} Track manual (Nomor + IP)
{G}[8]{B} Keluar

============================================={W}
""")

def cek_ip(ip):
    url = f"http://ip-api.com/json/{ip}"
    try:
        r = requests.get(url).json()
    except:
        print(f"{R}⚠️ Tidak bisa menghubungi API!{W}")
        return None

    if r["status"] == "success":
        hasil = (
            f"{B}🌐 IP:{W} {r['query']}\n"
            f"{G}🏳 Negara:{W} {r['country']}\n"
            f"{G}🏙 Kota:{W} {r.get('city','-')}\n"
            f"{C}🏢 ISP:{W} {r.get('isp','-')}\n"
            f"{C}📡 ASN:{W} {r.get('as','-')}\n"
            f"{Y}📍 Koordinat:{W} {r['lat']},{r['lon']}\n"
            "---------------------------"
        )
        print(hasil)
        with open("hasil_ip.txt", "a") as f:
            f.write(hasil + "\n")
        return hasil
    else:
        print(f"{R}❌ Gagal cek IP {ip}{W}")
        return None

def kirim_telegram(pesan):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan}
        requests.post(url, data=data)
        print(f"{G}✅ Notifikasi terkirim ke Telegram!{W}")
    except:
        print(f"{R}⚠️ Gagal kirim notifikasi Telegram{W}")

def auto_scan_log(logfile):
    if not os.path.exists(logfile):
        print(f"{R}⚠️ File log tidak ditemukan.{W}")
        return
    
    with open(logfile, "r") as f:
        data = f.read()
    
    ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', data)
    unik = sorted(set(ips))
    
    if not unik:
        print(f"{R}⚠️ Tidak ada IP ditemukan di log.{W}")
        return
    
    print(f"{Y}📊 Ditemukan {len(unik)} IP unik. Mulai cek...{W}")
    for ip in unik:
        cek_ip(ip)

def tambah_target_wa():
    nomor = input(f"{C}Masukkan nomor WhatsApp target (format: 628xxxx):{W} ")
    if not nomor.startswith("62"):
        print(f"{R}⚠️ Gunakan format internasional, contoh: 6281234567890{W}")
        return
    with open(TARGET_WA_FILE, "a") as f:
        f.write(nomor + "\n")
    print(f"{G}✅ Nomor berhasil ditambahkan!{W}")
    kirim_telegram(f"📢 *Nomor WA Target Baru Ditambahkan:* {nomor}")

def scan_log_nomor_wa():
    if not os.path.exists(TARGET_WA_FILE):
        print(f"{R}⚠️ Belum ada nomor target. Tambahkan dulu dengan menu 5.{W}")
        return
    log = input(f"{C}Masukkan nama file log server (ex: access.log):{W} ")
    if not os.path.exists(log):
        print(f"{R}⚠️ File log tidak ditemukan.{W}")
        return

    with open(log, "r") as f:
        data = f.read()

    with open(TARGET_WA_FILE, "r") as f:
        targets = [t.strip() for t in f.readlines() if t.strip()]

    ditemukan = False
    for nomor in targets:
        if nomor in data:
            print(f"{G}✅ Nomor ditemukan di log: {nomor}{W}")
            baris = [line for line in data.splitlines() if nomor in line]
            for line in baris:
                ip_match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', line)
                if ip_match:
                    ip = ip_match.group()
                    print(f"{Y}🔎 Lacak lokasi IP: {ip}{W}")
                    hasil = cek_ip(ip)
                    if hasil:
                        kirim_telegram(f"📍 *Nomor WA {nomor} ditemukan!*\n{hasil}")
            ditemukan = True

    if not ditemukan:
        print(f"{R}⚠️ Tidak ada nomor target ditemukan di log.{W}")

def track_manual():
    nomor = input(f"{C}Masukkan nomor WhatsApp:{W} ")
    ip = input(f"{C}Masukkan IP target:{W} ")
    hasil = cek_ip(ip)
    if hasil:
        pesan = f"📱 *Track Manual*\nNomor: {nomor}\n{hasil}"
        kirim_telegram(pesan)
        print(f"{G}✅ Data manual berhasil dikirim!{W}")

def menu():
    while True:
        banner()
        pilihan = input(f"{C}Pilih menu:{W} ")

        if pilihan == "1":
            ip = input(f"{C}Masukkan IP:{W} ")
            cek_ip(ip)
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "2":
            file = input(f"{C}Masukkan nama file list IP:{W} ")
            if os.path.exists(file):
                with open(file, "r") as f:
                    for ip in f:
                        cek_ip(ip.strip())
            else:
                print(f"{R}⚠️ File tidak ditemukan.{W}")
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "3":
            log = input(f"{C}Masukkan nama file log server (ex: access.log):{W} ")
            auto_scan_log(log)
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "4":
            if os.path.exists("hasil_ip.txt"):
                with open("hasil_ip.txt") as f:
                    print(f.read())
            else:
                print(f"{R}⚠️ Belum ada hasil disimpan.{W}")
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "5":
            tambah_target_wa()
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "6":
            scan_log_nomor_wa()
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "7":
            track_manual()
            input(f"\n{Y}Enter untuk kembali ke menu...{W}")
        elif pilihan == "8":
            print(f"{G}👋 Keluar dari program...{W}")
            break
        else:
            print(f"{R}⚠️ Pilihan tidak ada!{W}")

menu()
