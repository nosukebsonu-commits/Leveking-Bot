# 🤖 Bot Discord Sinyal (Multi-Platform & Ultra-Secure Edition)

Bot Discord Level, Rank & Auto-Mod yang dirancang **portabel, anti-crash, dan aman saat berpindah akun Railway / platform hosting lain (Render, VPS, Fly.io, Heroku, Docker, Local)**.

---

## 🔄 Fitur Migrasi & Backup Instan Antar Akun / Hosting

Jika Anda ingin berpindah akun Railway atau ganti hosting, Anda **tidak akan kehilangan data rank member**:

1. **`!exportdata` (Di Bot Lama)**:
   - Admin mengetik `!exportdata` di Discord.
   - Bot otomatis mengirimkan file `levels.json` dan `banned_words.json` sebagai lampiran file.
   - Unduh file `levels.json` tersebut ke komputer/HP Anda.

2. **`!importdata` (Di Bot Baru)**:
   - Nyalakan bot di akun Railway baru / hosting baru.
   - Ketik `!importdata` sambil **melampirkan (attach)** file `levels.json` tadi.
   - Bot akan memvalidasi data dan langsung memulihkan seluruh rank, level, dan XP member tanpa perlu akses server/terminal!

---

## 🛡️ Fitur Utama Bot

1. **Sistem Level & XP**: Rank Card dengan visual progress bar, pelacakan Total XP seumur hidup, dan Leaderboard top 10.
2. **Sistem Anti-Cheat 4 Lapis**: Cooldown 60 detik, batas minimal 5 karakter, deteksi spam berulang/monoton, dan batas perolehan XP maksimal 20 kali per jam.
3. **Auto-Moderasi Cerdas**: Filter judi online & konten dewasa (menggunakan boundary regex anti false-positive), filter shortlink berbahaya, dan deteksi link server Discord NSFW.
4. **Penyimpanan Permanen & Anti-Korupsi Data**: Menggunakan mekanisme *Atomic File Write* dan *Async Concurrency Lock*.
5. **Universal Platform Compatibility**:
   - Mendukung Environment Variable: `DISCORD_TOKEN`, `BOT_TOKEN`, `TOKEN`.
   - Mendukung `DATA_DIR` untuk persistent volume (misal `/data`).
   - Otomatis mengaktifkan HTTP health-check server jika mendeteksi variable `PORT`.

---

## 📋 Daftar Perintah

### 👤 Perintah Member
| Perintah | Deskripsi |
| :--- | :--- |
| `!rank` / `!rank @user` | Cek level, XP saat ini, total XP lifetime, progress bar, & urutan peringkat server |
| `!leaderboard` *(alias `!top`, `!lb`)* | Menampilkan 10 besar member dengan level tertinggi beserta medali |
| `!help` | Menampilkan panduan dan daftar perintah lengkap |

### 🛡️ Perintah Admin (Wajib Izin: Manage Server)
| Perintah | Deskripsi |
| :--- | :--- |
| `!addxp @user <jumlah>` | Menambahkan bonus XP ke member (maksimal 10.000 XP) |
| `!setlevel @user <level>` | Mengatur level member secara langsung (rentang 0 - 1000) |
| `!addbanword <kata>` | Menambahkan kata kunci terlarang baru (tersimpan permanen) |
| `!banwordlist` | Menampilkan total kata terlarang yang sedang aktif |
| `!exportdata` | Mengunduh file backup database (`levels.json` & `banned_words.json`) |
| `!importdata` | Memulihkan data level dari file backup yang dilampirkan |

---

## 🚀 Cara Menjalankan di Railway / Platform Lain

### 1. File yang Di-upload ke Repository GitHub:
- `sinyal_level_bot.py`
- `requirements.txt`
- `Procfile`
- `Dockerfile`
- `README.md`

*(Catatan: Jangan upload file `.env` ke GitHub demi keamanan)*

### 2. Pengaturan Environment Variable di Railway:
- **Key**: `DISCORD_TOKEN`
- **Value**: *(Token Bot Discord Anda)*
- *(Opsional)* **DATA_DIR**: `/data` (jika menggunakan Railway Persistent Volume)

### 3. Privileged Intents di Discord Portal:
Pastikan **Server Members Intent** dan **Message Content Intent** sudah aktif di [Discord Developer Portal](https://discord.com/developers/applications) pada tab **Bot**.
