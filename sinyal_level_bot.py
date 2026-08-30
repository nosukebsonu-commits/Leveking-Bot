"""
Bot Discord Level & Rank - "Sinyal" (Multi-Platform, Channel Lock & Strike System Edition)
=============================================================================================
Fitur Utama:
1. Sistem Level & XP Otomatis:
   - Cooldown 60 detik antar pesan
   - Anti-cheat 4 lapis: min. 5 karakter, variasi karakter unik, batas 20x XP per jam
   - Otomatis mengabaikan command bot (prefix '!') agar tidak disalahgunakan untuk spam XP
   - Tracking Total XP Lifetime (seluruh riwayat XP tersimpan aman)
2. Sistem Peringatan & Hukuman Otomatis (Progressive Punishment System):
   - Peringatan 1 & 2: Pesan dihapus + Peringatan resmi counter [X/10]
   - Peringatan 3 (dan kelipatan 3): Pesan dihapus + **AUTO MUTE (TIMEOUT) 5 MENIT**
   - Peringatan 10: Pesan dihapus + **AUTO KICK (DIKELUARKAN OTOMATIS DARI SERVER)**
   - Database peringatan permanen (warnings.json) dengan Atomic Write
   - Perintah admin: `!warnings @user`, `!resetwarn @user`, `!warn @user <alasan>`
3. Pembatasan Channel Cek Rank Khusus:
   - Perintah `!rank` dan `!leaderboard` otomatis dibatasi HANYA di channel `#rank` (atau channel yang diset admin)
   - Jika member ketik `!rank` di channel lain, bot akan memberi tahu untuk pindah ke channel `#rank` (peringatan terhapus dalam 6 detik)
   - Perintah admin `!setrankchannel #channel` / `here` / `all` untuk mengatur channel khusus
4. Auto-Moderasi & Filter Konten Komprehensif (Maximum Shield):
   - Database besar kata kunci judi online, kasino, togel, pornografi lokal & internasional, typo variants, dan scam
   - Smart Normalizer: Mendeteksi trik bypass seperti de-spacing ('x n x x', 'b o k e p'), leetspeak ('p0rn', '$lot', 'b0k3p'), dan simbol ('x.n.x.x', 's_l_o_t')
   - Filter shortlink berbahaya (bit.ly, tinyurl, cutt.ly, s.id, heylink, dll)
   - Deteksi & blokir link undangan Discord yang mengarah ke server NSFW/dewasa
   - Perintah admin `!addbanword` dan `!banwordlist` dengan penyimpanan permanen & atomic write
5. Perintah Member:
   - `!rank` / `!rank @user` — Profil level, XP, visual progress bar, ranking, & total lifetime XP
   - `!leaderboard` (atau `!top`, `!lb`) — Top 10 leaderboard server dengan medali
   - `!help` — Menu bantuan interaktif
6. Perintah Admin (Manage Server):
   - `!addxp @user <jumlah>` — Tambah XP (maks. 10.000)
   - `!setlevel @user <level>` — Set level (rentang 0-1000) dengan sinkronisasi Total XP
   - `!setrankchannel [#channel/here/all]` — Kunci command !rank hanya di channel tertentu
   - `!warnings @user` — Cek jumlah peringatan member
   - `!resetwarn @user` — Reset/hapus peringatan member ke 0
   - `!warn @user <alasan>` — Beri peringatan manual ke member
   - `!addbanword <kata>` — Tambah kata terlarang ke filter
   - `!banwordlist` — Cek jumlah kata terlarang aktif
   - `!exportdata` — (Backup) Unduh file database levels, banwords, warnings langsung di Discord
   - `!importdata` — (Restore/Migrasi) Upload file backup levels.json untuk memindahkan data antar platform
7. Kompatibilitas Multi-Platform (Railway, Render, VPS, Heroku, Docker, Local):
   - Multi-token variable support (DISCORD_TOKEN, BOT_TOKEN, TOKEN)
   - Configurable DATA_DIR untuk Persistent Volume
   - Built-in HTTP Health Check Server (otomatis aktif jika env PORT terdeteksi)
   - Atomic File Write & Concurrency Lock
"""

import discord
from discord.ext import commands
import json
import os
import random
import time
import re
import asyncio
import io
from datetime import datetime, timedelta, timezone
import aiohttp
from aiohttp import web

# Muat environment variable dari .env jika ada
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# KONFIGURASI BOT & DIREKTORI MULTI-PLATFORM
# ==========================================
TOKEN = (
    os.environ.get("DISCORD_TOKEN") or
    os.environ.get("DISCORD_BOT_TOKEN") or
    os.environ.get("BOT_TOKEN") or
    os.environ.get("TOKEN")
)

DATA_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "levels.json")
BANWORDS_FILE = os.path.join(DATA_DIR, "banned_words.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
WARNINGS_FILE = os.path.join(DATA_DIR, "warnings.json")
COMMAND_PREFIX = "!"
PORT = os.environ.get("PORT")  # Mendeteksi port dari Railway/Render

# Konfigurasi XP & Anti-Cheat
XP_COOLDOWN_SECONDS = 60  # Jeda minimal antar XP per user (detik)
XP_MIN = 15               # XP minimal per pesan
XP_MAX = 25               # XP maksimal per pesan
MIN_MESSAGE_LENGTH = 5    # Panjang pesan minimal untuk dapat XP
MAX_XP_PER_HOUR = 20      # Batas maksimal user dapat XP per jam

# Kunci async lock untuk mencegah race condition penulisan file
db_lock = asyncio.Lock()

# ==========================================
# DATABASE FILTER KONTEN TERLARANG LENGKAP
# ==========================================
DEFAULT_BANNED_KEYWORDS = [
    # 1. JUDI ONLINE, SLOT, TOGEL, KASINO
    "slot gacor", "situs slot", "judi online", "judol", "bandar togel", "agen togel",
    "togel online", "toto gelap", "situs toto", "toto macau", "maxwin", "slot88",
    "slot777", "gacor88", "bo slot", "rtp slot", "rtp live", "scatter hitam",
    "scatter merah", "deposit pulsa slot", "depo slot", "depo pulsa", "link alternatif slot",
    "zeus slot", "pragmatic play", "olympus slot", "gates of olympus", "mahjong ways",
    "spaceman slot", "rajatogel", "indotogel", "live casino", "baccarat online",
    "roulette online", "judi bola", "sbobet", "link gacor", "idn poker",
    "poker online uang asli", "agen judi", "bandar judi", "jackpot slot", "freechip slot",
    "situs judi", "judi slot", "agen slot",

    # 2. PORNOGRAFI & SITUS DEWASA (INTERNASIONAL & TYPO)
    "bokep", "porn", "pron", "porno", "pornography", "xnxx", "xxnx", "xnx", "xxnxx",
    "xnxxcom", "xvideos", "xvideo", "xhamster", "pornhub", "phub", "redtube",
    "youporn", "brazzers", "onlyfans", "onlyfans leak", "nude leak", "doodstream",
    "terabox nsfw", "spankbang", "eporner", "beeg", "chaturbate", "stripchat",
    "bongacams", "camwhores", "leak girls", "leaked nudes", "jav", "javhd",
    "javsubindo", "avgle", "lustcinema", "xlecx", "multporn",

    # 3. KONTEN DEWASA LOKAL, ANIME NSFW & SLANG
    "video mesum", "vidio bokep", "link bokep", "bokep indo", "pemersatu bangsa nsfw",
    "pemersatu bangsa", "hentai", "doujin", "doujinshi", "nekopoi", "nhentai",
    "hanime", "hentaihaven", "rule34", "r34", "e621", "vcs", "vcs murah", "vcs real",
    "open bo", "openbo", "cewek bispak", "cewe bispak", "bispak", "colmek", "ngocok",
    "sange", "video viral mesum", "link video viral", "pap tt", "pap bugil",
    "bokep jepang", "bokep viral", "bokep bocil", "tobrut nsfw",

    # 4. SCAM & PHISHING DISCORD
    "free discord nitro", "free nitro", "discord-nitro", "steam gift card free",
    "claim nitro", "nitro generator", "free robux"
]

# Pola domain link pemendek & platform redirect berbahaya
SUSPICIOUS_SHORTLINK_PATTERNS = [
    r"https?://(?:www\.)?bit\.ly/\S+",
    r"https?://(?:www\.)?tinyurl\.com/\S+",
    r"https?://(?:www\.)?cutt\.ly/\S+",
    r"https?://(?:www\.)?s\.id/\S+",
    r"https?://(?:www\.)?shorturl\.at/\S+",
    r"https?://(?:www\.)?heylink\.me/\S+",
    r"https?://(?:www\.)?biolink\.to/\S+",
    r"\bbit\.ly/\S+",
    r"\btinyurl\.com/\S+",
    r"\bcutt\.ly/\S+",
    r"\bs\.id/\S+",
    r"\bshorturl\.at/\S+",
    r"\bheylink\.me/\S+"
]

# Pola link undangan server Discord
DISCORD_INVITE_PATTERNS = [
    "discord.gg/", "discord.com/invite/", "discordapp.com/invite/"
]

# Kata kunci NSFW yang menyertai link undangan Discord
DISCORD_INVITE_NSFW_KEYWORDS = [
    "nsfw", "18+", "hentai", "ecchi", "lewd", "nude", "hot girl", "onlyfans",
    "bokep", "porn", "xxx", "sange", "cewek bispak", "cewe bispak", "vcs", "open bo", "jav"
]

# Setup Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Cache memori untuk proteksi rate-limit & anti-cheat
last_xp_time = {}           # {user_id: timestamp_terakhir}
xp_history_per_hour = {}    # {user_id: [timestamp_1, timestamp_2, ...]}


# ==========================================
# MANAJEMEN DATABASE (ATOMIC WRITE)
# ==========================================
def load_warnings() -> dict:
    """Memuat data peringatan/strike dari warnings.json."""
    if os.path.exists(WARNINGS_FILE):
        try:
            with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_warnings(warnings_data: dict):
    """Menyimpan data peringatan menggunakan teknik Atomic Write."""
    tmp_file = f"{WARNINGS_FILE}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(warnings_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, WARNINGS_FILE)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan warnings ke {WARNINGS_FILE}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass


def load_config() -> dict:
    """Memuat konfigurasi server (seperti channel rank yang diizinkan)."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config_data: dict):
    """Menyimpan konfigurasi server menggunakan Atomic Write."""
    tmp_file = f"{CONFIG_FILE}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, CONFIG_FILE)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan config ke {CONFIG_FILE}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass


def load_banned_words() -> list:
    """Memuat daftar kata terlarang dari file JSON agar tersimpan permanen."""
    words = list(DEFAULT_BANNED_KEYWORDS)
    if os.path.exists(BANWORDS_FILE):
        try:
            with open(BANWORDS_FILE, "r", encoding="utf-8") as f:
                custom_words = json.load(f)
                if isinstance(custom_words, list):
                    for w in custom_words:
                        clean_w = str(w).strip().lower()
                        if clean_w and clean_w not in words:
                            words.append(clean_w)
        except Exception as e:
            print(f"[WARN] Gagal memuat {BANWORDS_FILE}: {e}")
    return words


def save_banned_words(words_list: list):
    """Menyimpan custom banned words ke file JSON menggunakan teknik Atomic Write."""
    tmp_file = f"{BANWORDS_FILE}.tmp"
    try:
        clean_list = [w.strip().lower() for w in words_list if str(w).strip()]
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(clean_list, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, BANWORDS_FILE)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan custom banwords ke {BANWORDS_FILE}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass


BANNED_KEYWORDS = load_banned_words()


# ==========================================
# SISTEM HUKUMAN BERTINGKAT (STRIKE SYSTEM)
# ==========================================
async def apply_warning_punishment(message: discord.Message, reason: str):
    """
    Menambahkan peringatan ke user dan menerapkan hukuman otomatis:
    - 1 & 2 Peringatan: Peringatan tertulis [X/10]
    - 3 Peringatan (dan kelipatan 3): Mute (Timeout) 5 Menit
    - 10 Peringatan: Kick (Dikeluarkan dari Server)
    """
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    member = message.author

    async with db_lock:
        warns_data = load_warnings()
        if guild_id not in warns_data:
            warns_data[guild_id] = {}

        current_warns = warns_data[guild_id].get(user_id, 0) + 1
        warns_data[guild_id][user_id] = current_warns
        save_warnings(warns_data)

    if current_warns >= 10:
        # 1. KIRIM DIRECT MESSAGE (DM) PRIBADI SEBELUM DI-KICK
        try:
            guild_icon_url = message.guild.icon.url if message.guild.icon else None
            dm_embed = discord.Embed(
                title=f"⛔ PEMBERITAHUAN PENGELUARAN DARI SERVER: {message.guild.name} ⛔",
                description=(
                    f"Halo **{member.name}**,\n\n"
                    f"Anda telah **DIKELUARKAN (KICK)** dari server **{message.guild.name}** secara otomatis.\n\n"
                    f"📌 **Penyebab:** Anda telah mencapai batas maksimal **10/10 Peringatan Pelanggaran**.\n"
                    f"🚨 **Pelanggaran Terakhir:** {reason}\n\n"
                    f"Harap patuhi tata tertib dan peraturan komunitas jika Anda bergabung kembali di masa mendatang."
                ),
                color=discord.Color.red()
            )
            if guild_icon_url:
                dm_embed.set_thumbnail(url=guild_icon_url)
            dm_embed.set_footer(text=f"Sistem Keamanan Server {message.guild.name}")
            await member.send(embed=dm_embed)
        except Exception:
            # Member mungkin menutup DM dari server
            pass

        # 2. EKSEKUSI KICK DARI SERVER
        try:
            await member.kick(reason=f"Otomatis: Mencapai {current_warns}x Peringatan ({reason})")
            embed = discord.Embed(
                title="⛔ MEMBER DIKELUARKAN (KICK) ⛔",
                description=(
                    f"{member.mention} telah **DIKELUARKAN DARI SERVER**!\n\n"
                    f"📊 **Total Peringatan:** **{current_warns}/10**\n"
                    f"📌 **Pelanggaran Terakhir:** {reason}\n"
                    f"📩 *Pesan alasan pengeluaran telah dikirimkan via DM ke member.*"
                ),
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)
        except discord.Forbidden:
            await message.channel.send(
                f"⚠️ {member.mention} telah mencapai **10/10 Peringatan**, tetapi bot tidak memiliki izin (Kick Members) untuk mengeluarkannya."
            )
        except Exception as e:
            print(f"[ERROR KICK] {e}")

    elif current_warns == 3 or (current_warns > 3 and current_warns % 3 == 0):
        # 1. KIRIM DIRECT MESSAGE (DM) PRIBADI SAAT DI-MUTE
        try:
            guild_icon_url = message.guild.icon.url if message.guild.icon else None
            dm_mute = discord.Embed(
                title=f"🔇 PEMBERITAHUAN MUTE: {message.guild.name} 🔇",
                description=(
                    f"Halo **{member.name}**,\n\n"
                    f"Anda telah **DI-MUTE (TIMEOUT) SELAMA 5 MENIT** di server **{message.guild.name}**.\n\n"
                    f"📊 **Status Peringatan Anda:** **{current_warns}/10**\n"
                    f"📌 **Alasan:** Mengirim konten terlarang ({reason})\n\n"
                    f"⚠️ *Perhatian: Jika Anda mencapai 10x peringatan, Anda akan otomatis dikeluarkan (KICK) dari server!*"
                ),
                color=discord.Color.orange()
            )
            if guild_icon_url:
                dm_mute.set_thumbnail(url=guild_icon_url)
            dm_mute.set_footer(text=f"Sistem Keamanan Server {message.guild.name}")
            await member.send(embed=dm_mute)
        except Exception:
            pass

        # 2. EKSEKUSI TIMEOUT 5 MENIT
        try:
            timeout_until = datetime.now(timezone.utc) + timedelta(minutes=5)
            await member.timeout(timeout_until, reason=f"Peringatan ke-{current_warns}: {reason}")
            embed = discord.Embed(
                title="🔇 MEMBER DI-MUTE (TIMEOUT 5 MENIT) 🔇",
                description=(
                    f"{member.mention} telah **DI-MUTE selama 5 Menit**!\n\n"
                    f"📊 **Total Peringatan:** **{current_warns}/10**\n"
                    f"📌 **Alasan:** Mengirim konten terlarang ({reason})\n\n"
                    f"⚠️ *Perhatian: Jika mencapai 10x peringatan, member akan otomatis dikeluarkan dari server!*"
                ),
                color=discord.Color.orange()
            )
            await message.channel.send(embed=embed)
        except discord.Forbidden:
            await message.channel.send(
                f"⚠️ {member.mention} mencapai **{current_warns}/10 Peringatan**, tetapi bot memerlukan izin `Moderate Members (Timeout)` untuk me-mute."
            )
        except Exception as e:
            print(f"[ERROR TIMEOUT] {e}")

    else:
        # PERINGATAN STANDAR (1, 2, 4, 5, dst)
        embed = discord.Embed(
            title="⚠️ PERINGATAN PELANGGARAN ⚠️",
            description=(
                f"{member.mention}, pesanmu dihapus karena mengandung **{reason}**.\n\n"
                f"📊 **Status Peringatan Anda:** **{current_warns}/10**\n"
                f"• *3x Peringatan*: Auto-Mute (Timeout) 5 Menit\n"
                f"• *10x Peringatan*: Dikeluarkan Otomatis (Kick)"
            ),
            color=discord.Color.gold()
        )
        try:
            warn_msg = await message.channel.send(embed=embed)
            await warn_msg.delete(delay=10)
        except Exception:
            pass


# ==========================================
# NORMALISASI TEKS ANTI-BYPASS & AUTO-MOD
# ==========================================
def normalize_text_variants(text: str) -> list:
    """
    Menghasilkan variasi bentuk teks untuk mendeteksi berbagai teknik bypass:
    1. Menghapus Zero-Width Space & Karakter Tak Terlihat (ZWSP, ZWNJ, ZWJ, soft hyphen, dll)
    2. Mengubah Homoglyphs Cyrillic/Greek ke Latin (misal: 'х' cyrillic -> 'x', 'а' -> 'a', 'о' -> 'o', 'р' -> 'p')
    3. Menghilangkan simbol pemisah (misal: 'x.n.x.x' -> 'x n x x')
    4. De-spacing: menghapus spasi di antara huruf tunggal (misal: 'x n x x' -> 'xnxx')
    5. Alphanumeric only (misal: 'b_o_k_e_p' -> 'bokep')
    6. Leetspeak: mengubah @->a, 0->o, 1/!->i, $->s, 3->e, 4->a, 5->s, 7->t, 8->b
    """
    if not text:
        return []

    # 1. Bersihkan invisible unicode characters
    clean_invisible = re.sub(r"[\u200B-\u200D\uFEFF\u00AD\u2060\u180E\u2000-\u200A\u034F]", "", str(text))

    # 2. Homoglyph mapping (Cyrillic & Greek lookalikes to Latin)
    homoglyph_map = str.maketrans({
        "а": "a", "о": "o", "е": "e", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s",
        "п": "n", "н": "n", "т": "t", "к": "k", "м": "m", "в": "b",
        "А": "a", "О": "o", "Е": "e", "Р": "p", "С": "c", "Х": "x", "У": "y", "І": "i", "Ј": "j", "Ѕ": "s",
        "П": "n", "Н": "n", "Т": "t", "К": "k", "М": "m", "В": "b"
    })
    lowered = clean_invisible.translate(homoglyph_map).lower()
    variants = [lowered]

    # 3. Simbol pemisah -> spasi
    no_symbols = re.sub(r"[\_\-\.\,\;\|\/\\\*\~\#\+\=\:\(\)\[\]\{\}\?\<\>\!]", " ", lowered)
    variants.append(no_symbols)
    clean_spaces = re.sub(r"\s+", " ", no_symbols).strip()
    variants.append(clean_spaces)

    # 4. De-spacing (mengubah 'x n x x' -> 'xnxx')
    despaced = re.sub(r"(?<=\b\w)\s+(?=\w\b)", "", clean_spaces)
    variants.append(despaced)

    # 5. Alphanumeric only (menghilangkan semua non-huruf angka)
    alphanumeric_only = re.sub(r"[^a-z0-9]", "", lowered)
    variants.append(alphanumeric_only)

    # 6. Leetspeak mapping
    leetspeak_map = str.maketrans({
        "@": "a", "4": "a", "0": "o", "1": "i", "!": "i", "3": "e", "$": "s", "5": "s", "7": "t", "8": "b"
    })
    for v in list(variants):
        variants.append(v.translate(leetspeak_map))

    return list(set(variants))


def contains_banned_content(content: str) -> bool:
    """Mengecek apakah pesan mengandung konten terlarang (Judi/NSFW/Scam)."""
    if not content:
        return False

    variants = normalize_text_variants(content)

    for keyword in BANNED_KEYWORDS:
        kw = keyword.lower().strip()
        if not kw:
            continue

        if " " in kw:
            kw_nospaces = kw.replace(" ", "")
            for var in variants:
                if kw in var or kw_nospaces in var.replace(" ", ""):
                    return True
        else:
            pattern = r'\b' + re.escape(kw) + r'\b'
            for var in variants:
                if re.search(pattern, var):
                    return True

    return False


def contains_discord_invite(content: str) -> bool:
    """Mengecek apakah pesan mengandung link undangan server Discord."""
    if not content:
        return False
    lowered = content.lower()
    return any(pattern in lowered for pattern in DISCORD_INVITE_PATTERNS)


def is_suspicious_discord_invite(content: str) -> bool:
    """Mengecek apakah link undangan Discord disertai kata kunci NSFW."""
    if not contains_discord_invite(content):
        return False

    variants = normalize_text_variants(content)
    for keyword in DISCORD_INVITE_NSFW_KEYWORDS:
        kw = keyword.lower().strip()
        pattern = r'\b' + re.escape(kw) + r'\b' if " " not in kw else kw
        for var in variants:
            if (" " in kw and kw in var) or (" " not in kw and re.search(pattern, var)):
                return True
    return False


def contains_suspicious_shortlink(content: str) -> bool:
    """Mengecek apakah pesan mengandung domain pemendek URL berbahaya."""
    if not content:
        return False
    lowered = content.lower()
    for pattern in SUSPICIOUS_SHORTLINK_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


# ==========================================
# LOGIKA PEMBATASAN CHANNEL RANK
# ==========================================
def is_rank_channel_allowed(ctx) -> tuple:
    """Mengecek apakah perintah !rank diizinkan di channel ini."""
    if ctx.author.guild_permissions.manage_guild:
        return True, None

    config = load_config()
    guild_id = str(ctx.guild.id)
    guild_conf = config.get(guild_id, {})

    locked_channel_id = guild_conf.get("rank_channel_id")
    if locked_channel_id == "all":
        return True, None

    if locked_channel_id:
        if ctx.channel.id == int(locked_channel_id):
            return True, None
        return False, f"<#{locked_channel_id}>"

    rank_channel = discord.utils.get(ctx.guild.text_channels, name="rank")
    if rank_channel:
        if ctx.channel.id == rank_channel.id:
            return True, None
        return False, rank_channel.mention

    return True, None


# ==========================================
# LOGIKA KEKEBALAN / FREEDOM AUTO-MOD
# ==========================================
def has_automod_immunity(member: discord.Member) -> bool:
    """
    Mengecek apakah member memiliki kekebalan (immunity/freedom) dari Auto-Mod:
    HANYA member yang memiliki role bernama 'Fredom' atau 'Freedom' (atau role yang didaftarkan via !addbypassrole).
    """
    if not isinstance(member, discord.Member):
        return False

    # 1. Cek nama role 'Fredom' atau 'Freedom'
    for role in member.roles:
        clean_name = role.name.lower().strip()
        if clean_name in ["fredom", "freedom", "bypass", "immune"]:
            return True

    # 2. Cek ID role yang didaftarkan via konfigurasi
    config = load_config()
    guild_id = str(member.guild.id)
    bypass_role_ids = config.get(guild_id, {}).get("bypass_roles", [])
    for role in member.roles:
        if role.id in bypass_role_ids or str(role.id) in bypass_role_ids:
            return True

    return False


# ==========================================
# LOGIKA ANTI-CHEAT XP
# ==========================================
def is_message_valid_for_xp(content: str) -> bool:
    """Mengecek apakah pesan layak dapat XP."""
    if not content:
        return False

    stripped = content.strip()

    if stripped.startswith(COMMAND_PREFIX):
        return False

    if len(stripped) < MIN_MESSAGE_LENGTH:
        return False

    unique_chars = set(stripped.lower().replace(" ", ""))
    if len(unique_chars) <= 2:
        return False

    return True


def can_gain_xp_this_hour(user_id: str) -> bool:
    """Mengecek batas maksimal 20x XP per jam per user."""
    now = time.time()
    one_hour_ago = now - 3600

    if user_id not in xp_history_per_hour:
        xp_history_per_hour[user_id] = []

    xp_history_per_hour[user_id] = [
        t for t in xp_history_per_hour[user_id] if t > one_hour_ago
    ]

    return len(xp_history_per_hour[user_id]) < MAX_XP_PER_HOUR


def record_xp_gain(user_id: str):
    """Mencatat waktu user mendapatkan XP."""
    xp_history_per_hour.setdefault(user_id, []).append(time.time())


# ==========================================
# HELPER DATABASE & ATOMIC WRITE
# ==========================================
def load_data() -> dict:
    """Membaca data level dari file JSON."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_data(data: dict):
    """Menyimpan data level ke file JSON menggunakan teknik Atomic Write."""
    tmp_file = f"{DATA_FILE}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, DATA_FILE)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan data level ke {DATA_FILE}: {e}")
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass


def xp_needed_for_level(level: int) -> int:
    """Rumus XP yang dibutuhkan untuk naik ke level berikutnya."""
    safe_level = max(level, 0)
    return 5 * (safe_level ** 2) + 50 * safe_level + 100


def cumulative_xp_for_level(level: int) -> int:
    """Menghitung total XP kumulatif untuk mencapai level tertentu."""
    safe_level = max(level, 0)
    return sum(xp_needed_for_level(lvl) for lvl in range(safe_level))


def create_progress_bar(current_xp: int, needed_xp: int, bar_length: int = 10) -> str:
    """Membuat visual progress bar XP."""
    if needed_xp <= 0:
        return "▰" * bar_length
    progress = min(max(current_xp / needed_xp, 0.0), 1.0)
    filled_length = int(bar_length * progress)
    return "▰" * filled_length + "▱" * (bar_length - filled_length)


def get_user_rank_position(user_id: str, data: dict) -> int:
    """Menghitung urutan rank user di antara semua member aktif."""
    active_users = [
        item for item in data.items()
        if item[1].get("level", 0) > 0 or item[1].get("xp", 0) > 0 or item[1].get("total_xp", 0) > 0
    ]

    sorted_users = sorted(
        active_users,
        key=lambda item: (
            item[1].get("level", 0),
            item[1].get("xp", 0),
            item[1].get("total_xp", 0)
        ),
        reverse=True
    )
    for pos, (uid, _) in enumerate(sorted_users, start=1):
        if str(uid) == str(user_id):
            return pos
    return len(sorted_users) + 1


def add_xp(user_id: str, amount: int, data: dict) -> bool:
    """Menambah XP ke user dan menghitung kenaikan level."""
    if user_id not in data:
        data[user_id] = {"xp": 0, "level": 0, "total_xp": 0}

    data[user_id]["xp"] = data[user_id].get("xp", 0) + amount
    data[user_id]["total_xp"] = data[user_id].get("total_xp", 0) + amount
    leveled_up = False

    while True:
        needed = xp_needed_for_level(data[user_id].get("level", 0))
        if data[user_id]["xp"] >= needed:
            data[user_id]["xp"] -= needed
            data[user_id]["level"] = data[user_id].get("level", 0) + 1
            leveled_up = True
        else:
            break

    return leveled_up


# ==========================================
# LIGHTWEIGHT HTTP SERVER (UNTUK WEB HOSTING)
# ==========================================
async def start_web_health_server():
    """Menjalankan web server mini jika platform hosting memerlukan port terbuka (Health Check)."""
    if not PORT:
        return

    app = web.Application()

    async def handle_health(request):
        return web.json_response({
            "status": "online",
            "bot": str(bot.user) if bot.user else "Starting...",
            "database_file": DATA_FILE,
            "total_users": len(load_data()),
            "banned_keywords_count": len(BANNED_KEYWORDS)
        })

    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(PORT))
    await site.start()
    print(f"[HTTP] Health-check server aktif di port {PORT}")


# ==========================================
# BOT EVENTS
# ==========================================
@bot.event
async def on_ready():
    print("=" * 55)
    print(f"Bot Sinyal Online sebagai : {bot.user} (ID: {bot.user.id})")
    print(f"Prefix Perintah           : {COMMAND_PREFIX}")
    print(f"Penyimpanan Data          : {DATA_FILE}")
    print(f"Filter Konten Terlarang   : Aktif ({len(BANNED_KEYWORDS)} kata kunci)")
    print(f"Sistem Strike / Hukuman   : Aktif (3x Mute 5 Menit, 10x Kick)")
    print(f"Smart Bypass Normalizer   : Aktif (Leetspeak, De-spacing, Simbol)")
    print(f"Sistem Level & Anti-Cheat : 4 Lapis Aktif (Atomic Storage)")
    print("=" * 55)

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="keamanan server | Ketik !help"
        )
    )

    if PORT:
        bot.loop.create_task(start_web_health_server())


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.guild is None:
        await bot.process_commands(message)
        return

    content = message.content

    # 1. Filter Konten Terlarang & Auto-Mod dengan Sistem Strike (Dilewati jika user punya role Fredom / Kebal)
    is_immune = has_automod_immunity(message.author)
    if not is_immune:
        if contains_banned_content(content):
            print(f"[AUTO-MOD BLOCKED] Pesan terlarang dari '{message.author.name}': '{content}' -> Menghapus & memproses sanksi...")
            try:
                await message.delete()
            except discord.Forbidden:
                print(f"[PERINGATAN IZIN] Bot TIDAK BISA menghapus pesan '{message.author.name}' karena bot belum diberi izin 'Manage Messages' di Discord!")
            except Exception as e:
                print(f"[WARN] Gagal hapus pesan: {e}")

            await apply_warning_punishment(message, reason="Judi Online / Konten Dewasa / Kata Terlarang")
            return

        if is_suspicious_discord_invite(content):
            print(f"[AUTO-MOD BLOCKED] Link invite NSFW dari '{message.author.name}' -> Menghapus & memproses sanksi...")
            try:
                await message.delete()
            except discord.Forbidden:
                print(f"[PERINGATAN IZIN] Bot TIDAK BISA menghapus pesan karena bot belum diberi izin 'Manage Messages' di Discord!")
            except Exception as e:
                print(f"[WARN] Gagal hapus pesan: {e}")

            await apply_warning_punishment(message, reason="Link Undangan Server Discord NSFW/Dewasa")
            return

        if contains_suspicious_shortlink(content):
            print(f"[AUTO-MOD BLOCKED] Shortlink berbahaya dari '{message.author.name}' -> Menghapus & memproses sanksi...")
            try:
                await message.delete()
            except discord.Forbidden:
                print(f"[PERINGATAN IZIN] Bot TIDAK BISA menghapus pesan karena bot belum diberi izin 'Manage Messages' di Discord!")
            except Exception as e:
                print(f"[WARN] Gagal hapus pesan: {e}")

            await apply_warning_punishment(message, reason="Tautan Pemendek / Shortlink Berbahaya")
            return

    # 2. Proses XP dengan Anti-Cheat (XP bisa didapat dari SEMUA channel)
    user_id = str(message.author.id)
    now = time.time()

    cooldown_ok = user_id not in last_xp_time or (now - last_xp_time[user_id]) >= XP_COOLDOWN_SECONDS
    message_valid = is_message_valid_for_xp(content)
    rate_limit_ok = can_gain_xp_this_hour(user_id)

    if cooldown_ok and message_valid and rate_limit_ok:
        async with db_lock:
            data = load_data()
            xp_gained = random.randint(XP_MIN, XP_MAX)
            leveled_up = add_xp(user_id, xp_gained, data)
            save_data(data)
            
            last_xp_time[user_id] = now
            record_xp_gain(user_id)

            if leveled_up:
                new_level = data[user_id]["level"]
                embed = discord.Embed(
                    title="🎉 LEVEL UP! 🎉",
                    description=f"Selamat {message.author.mention}, kamu berhasil naik ke **Level {new_level}**! 🚀",
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                embed.set_footer(text="Terus aktif berdiskusi untuk meraih peringkat teratas!")
                try:
                    await message.channel.send(embed=embed)
                except Exception:
                    pass

    await bot.process_commands(message)


# ==========================================
# COMMANDS MEMBER (DENGAN PEMBATASAN CHANNEL)
# ==========================================
@bot.command(name="rank", aliases=["level", "xp", "lvl"])
@commands.guild_only()
async def rank(ctx, member: discord.Member = None):
    """Cek level, XP, dan rank diri sendiri atau member lain."""
    allowed, target_channel = is_rank_channel_allowed(ctx)
    if not allowed:
        try:
            warning = await ctx.send(
                f"❌ {ctx.author.mention}, perintah cek rank hanya diizinkan di channel {target_channel}!"
            )
            await warning.delete(delay=6)
        except Exception:
            pass
        return

    target = member or ctx.author
    if target.bot:
        await ctx.send("❌ Akun bot tidak memiliki profil Level dan XP.")
        return

    data = load_data()
    user_id = str(target.id)

    if user_id not in data or (data[user_id].get("level", 0) == 0 and data[user_id].get("xp", 0) == 0):
        if target == ctx.author:
            await ctx.send(f"❌ {target.mention}, kamu belum punya XP. Mulailah mengobrol di server untuk dapat XP!")
        else:
            await ctx.send(f"❌ **{target.display_name}** belum memiliki XP di server ini.")
        return

    user_data = data[user_id]
    current_level = user_data.get("level", 0)
    current_xp = user_data.get("xp", 0)
    total_xp = user_data.get("total_xp", current_xp)
    needed_xp = xp_needed_for_level(current_level)
    rank_pos = get_user_rank_position(user_id, data)
    progress_bar = create_progress_bar(current_xp, needed_xp, bar_length=12)
    percent = int((current_xp / needed_xp) * 100) if needed_xp > 0 else 100

    embed = discord.Embed(
        title=f"📊 Rank Card — {target.display_name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🏆 Peringkat", value=f"**#{rank_pos}**", inline=True)
    embed.add_field(name="⭐ Level", value=f"**{current_level}**", inline=True)
    embed.add_field(name="✨ XP Level Ini", value=f"**{current_xp:,}** / {needed_xp:,} XP", inline=True)
    embed.add_field(
        name="📈 Progress Level",
        value=f"`{progress_bar}` **{percent}%**\n*(Sisa {needed_xp - current_xp:,} XP lagi)*",
        inline=False
    )
    embed.add_field(name="🌟 Total XP Seumur Hidup", value=f"**{total_xp:,} XP**", inline=True)
    embed.set_footer(text=f"Diminta oleh {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "top"])
@commands.guild_only()
async def leaderboard(ctx):
    """Menampilkan 10 member dengan level tertinggi di server."""
    allowed, target_channel = is_rank_channel_allowed(ctx)
    if not allowed:
        try:
            warning = await ctx.send(
                f"❌ {ctx.author.mention}, perintah leaderboard hanya diizinkan di channel {target_channel}!"
            )
            await warning.delete(delay=6)
        except Exception:
            pass
        return

    data = load_data()

    if not data:
        await ctx.send("Belum ada data leaderboard. Ayo mulai chat untuk dapat XP!")
        return

    # Filter hanya member server ini yang bukan bot dan memiliki XP/Level
    active_users = []
    for uid, stats in data.items():
        if stats.get("level", 0) > 0 or stats.get("xp", 0) > 0 or stats.get("total_xp", 0) > 0:
            if str(uid).isdigit():
                m = ctx.guild.get_member(int(uid))
                if m and not m.bot:
                    active_users.append((uid, stats))

    if not active_users:
        await ctx.send("Belum ada member yang mengumpulkan XP di server ini. Ayo mulai mengobrol!")
        return

    sorted_users = sorted(
        active_users,
        key=lambda item: (
            item[1].get("level", 0),
            item[1].get("xp", 0),
            item[1].get("total_xp", 0)
        ),
        reverse=True
    )[:10]

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    leaderboard_lines = []

    for rank_idx, (uid, stats) in enumerate(sorted_users, start=1):
        lvl = stats.get("level", 0)
        xp = stats.get("xp", 0)
        needed = xp_needed_for_level(lvl)

        name = f"User ({uid})"
        member = ctx.guild.get_member(int(uid))
        if member:
            name = member.display_name

        medal = medals.get(rank_idx, f"`#{rank_idx:02d}`")
        leaderboard_lines.append(
            f"{medal} **{name}** • Level **{lvl}** ({xp:,}/{needed:,} XP)"
        )

    embed = discord.Embed(
        title=f"🏆 Top 10 Leaderboard — {ctx.guild.name}",
        description="\n".join(leaderboard_lines) if leaderboard_lines else "Tidak ada data.",
        color=discord.Color.gold()
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Ketik !rank untuk melihat peringkatmu sendiri")

    await ctx.send(embed=embed)


# ==========================================
# COMMANDS ADMIN (MANAGE GUILD & MODERASI)
# ==========================================
@bot.command(name="warnings", aliases=["cekstrike", "warns"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def warnings_cmd(ctx, member: discord.Member):
    """[ADMIN ONLY] Melihat total peringatan pelanggaran yang dimiliki member."""
    if member.bot:
        await ctx.send("❌ Akun bot tidak memiliki catatan peringatan.")
        return

    warns_data = load_warnings()
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    count = warns_data.get(guild_id, {}).get(user_id, 0)

    embed = discord.Embed(
        title=f"📋 Catatan Peringatan — {member.display_name}",
        description=(
            f"👤 **Member:** {member.mention}\n"
            f"📊 **Total Peringatan:** **{count}/10**\n\n"
            f"• *3x Peringatan*: Auto-Mute 5 Menit\n"
            f"• *10x Peringatan*: Auto-Kick dari Server"
        ),
        color=discord.Color.orange() if count > 0 else discord.Color.green()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@warnings_cmd.error
async def warnings_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Masukkan member yang ingin dicek. Contoh: `!warnings @Budi`")


@bot.command(name="resetwarn", aliases=["clearwarn", "clearwarnings"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def resetwarn_cmd(ctx, member: discord.Member):
    """[ADMIN ONLY] Menghapus/mereset seluruh peringatan member ke 0."""
    if member.bot:
        await ctx.send("❌ Akun bot tidak memiliki catatan peringatan.")
        return

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    async with db_lock:
        warns_data = load_warnings()
        if guild_id in warns_data and user_id in warns_data[guild_id]:
            warns_data[guild_id][user_id] = 0
            save_warnings(warns_data)

    await ctx.send(f"✅ Seluruh peringatan untuk {member.mention} berhasil **di-reset ke 0**!")


@resetwarn_cmd.error
async def resetwarn_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Masukkan member yang ingin di-reset. Contoh: `!resetwarn @Budi`")


@bot.command(name="warn")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def warn_cmd(ctx, member: discord.Member, *, reason: str = "Pelanggaran Aturan Server"):
    """[ADMIN ONLY] Memberikan peringatan manual ke member."""
    if member.bot:
        await ctx.send("❌ Tidak dapat memberikan peringatan ke sesama akun bot.")
        return

    mock_msg = ctx.message
    mock_msg.author = member
    await apply_warning_punishment(mock_msg, reason=f"Peringatan Manual dari Admin: {reason}")
    await ctx.send(f"✅ Peringatan manual berhasil diberikan ke {member.mention} (Alasan: {reason}).")


@warn_cmd.error
async def warn_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Format: `!warn @member <alasan>`")


@bot.command(name="addbypassrole", aliases=["setbypassrole", "kebalrole"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def addbypassrole_cmd(ctx, role: discord.Role):
    """[ADMIN ONLY] Memberikan kekebalan penuh (Freedom) dari Auto-Mod ke role tertentu."""
    config = load_config()
    guild_id = str(ctx.guild.id)
    if guild_id not in config:
        config[guild_id] = {}

    if "bypass_roles" not in config[guild_id]:
        config[guild_id]["bypass_roles"] = []

    if role.id in config[guild_id]["bypass_roles"]:
        await ctx.send(f"⚠️ Role {role.mention} sudah ada di daftar role kebal auto-mod.")
        return

    config[guild_id]["bypass_roles"].append(role.id)
    save_config(config)
    await ctx.send(f"✅ Role {role.mention} berhasil diberikan **Kekebalan Penuh (Freedom/Immunity)** dari seluruh filter Auto-Mod!")


@addbypassrole_cmd.error
async def addbypassrole_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("⚠️ Format: `!addbypassrole @NamaRole` (contoh: `!addbypassrole @Fredom`)")


@bot.command(name="removebypassrole", aliases=["delbypassrole"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def removebypassrole_cmd(ctx, role: discord.Role):
    """[ADMIN ONLY] Menghapus status kekebalan auto-mod dari suatu role."""
    config = load_config()
    guild_id = str(ctx.guild.id)
    if guild_id in config and "bypass_roles" in config[guild_id]:
        if role.id in config[guild_id]["bypass_roles"]:
            config[guild_id]["bypass_roles"].remove(role.id)
            save_config(config)
            await ctx.send(f"✅ Status kekebalan untuk role {role.mention} telah dicabut.")
            return
    await ctx.send(f"⚠️ Role {role.mention} tidak ditemukan di daftar role kebal kustom.")


@removebypassrole_cmd.error
async def removebypassrole_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("⚠️ Format: `!removebypassrole @NamaRole`")


@bot.command(name="bypassroles", aliases=["listbypassroles"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def listbypassroles_cmd(ctx):
    """[ADMIN ONLY] Melihat daftar role yang memiliki kekebalan Auto-Mod (Freedom)."""
    config = load_config()
    guild_id = str(ctx.guild.id)
    bypass_role_ids = config.get(guild_id, {}).get("bypass_roles", [])

    lines = ["• Role bernama `Fredom` atau `Freedom` *(Bawaan Otomatis Aktif)*"]
    for rid in bypass_role_ids:
        r = ctx.guild.get_role(int(rid))
        if r:
            lines.append(f"• {r.mention}")

    embed = discord.Embed(
        title="👑 Daftar Role Kebal Auto-Mod (Freedom)",
        description="\n".join(lines),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@listbypassroles_cmd.error
async def listbypassroles_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")


@bot.command(name="setrankchannel")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def setrankchannel(ctx, channel_target: str = "here"):
    """
    [ADMIN ONLY] Mengatur channel khusus untuk perintah !rank dan !leaderboard.
    Format:
    - !setrankchannel #channel (kunci ke channel tertentu)
    - !setrankchannel here (kunci ke channel saat ini)
    - !setrankchannel all (izinkan di semua channel)
    """
    config = load_config()
    guild_id = str(ctx.guild.id)
    if guild_id not in config:
        config[guild_id] = {}

    if channel_target.lower() == "all":
        config[guild_id]["rank_channel_id"] = "all"
        save_config(config)
        await ctx.send("✅ Perintah `!rank` dan `!leaderboard` sekarang **diizinkan di semua channel**.")
        return

    if channel_target.lower() == "here":
        target_ch = ctx.channel
    elif ctx.message.channel_mentions:
        target_ch = ctx.message.channel_mentions[0]
    else:
        clean_id = re.sub(r"[<#>]", "", channel_target)
        if clean_id.isdigit():
            target_ch = ctx.guild.get_channel(int(clean_id))
        else:
            target_ch = discord.utils.get(ctx.guild.text_channels, name=channel_target.lower().replace("#", ""))

    if not target_ch or not isinstance(target_ch, discord.TextChannel):
        await ctx.send("❌ Channel tidak ditemukan! Gunakan format: `!setrankchannel #rank` atau `!setrankchannel here`")
        return

    config[guild_id]["rank_channel_id"] = target_ch.id
    save_config(config)
    await ctx.send(f"✅ Perintah `!rank` dan `!leaderboard` berhasil dikunci **HANYA di channel {target_ch.mention}**!")


@setrankchannel.error
async def setrankchannel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")


@bot.command(name="addxp")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def addxp(ctx, member: discord.Member, amount: int):
    """[ADMIN ONLY] Menambah XP ke member (maksimal 10.000 XP)."""
    if member.bot:
        await ctx.send("❌ Akun bot tidak dapat diberikan XP.")
        return
    if amount <= 0:
        await ctx.send("❌ Jumlah XP harus lebih dari 0.")
        return
    if amount > 10000:
        await ctx.send("❌ Jumlah XP terlalu besar (maksimal 10.000 sekali perintah).")
        return

    async with db_lock:
        data = load_data()
        user_id = str(member.id)
        leveled_up = add_xp(user_id, amount, data)
        save_data(data)

    msg = f"✅ Berhasil menambahkan **{amount:,} XP** ke {member.mention}."
    if leveled_up:
        msg += f"\n🎉 {member.mention} langsung naik ke **Level {data[user_id]['level']}**!"

    await ctx.send(msg)


@addxp.error
async def addxp_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member tidak ditemukan. Pastikan mention member dengan benar (@user).")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("⚠️ Format salah! Gunakan: `!addxp @member <jumlah_xp>` (contoh: `!addxp @Budi 500`)")


@bot.command(name="setlevel")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def setlevel(ctx, member: discord.Member, level: int):
    """[ADMIN ONLY] Mengatur level member secara langsung (0 - 1000)."""
    if member.bot:
        await ctx.send("❌ Akun bot tidak dapat diatur levelnya.")
        return
    if level < 0 or level > 1000:
        await ctx.send("❌ Level harus berada di antara rentang 0 sampai 1000.")
        return

    async with db_lock:
        data = load_data()
        user_id = str(member.id)
        if user_id not in data:
            data[user_id] = {"xp": 0, "level": 0, "total_xp": 0}

        data[user_id]["level"] = level
        data[user_id]["xp"] = 0
        data[user_id]["total_xp"] = cumulative_xp_for_level(level)
        save_data(data)

    await ctx.send(f"✅ Level {member.mention} berhasil diatur ke **Level {level}** (XP di-reset ke 0, Total XP disinkronkan).")


@setlevel.error
async def setlevel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member tidak ditemukan. Pastikan mention member dengan benar (@user).")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("⚠️ Format salah! Gunakan: `!setlevel @member <angka_level>` (contoh: `!setlevel @Budi 5`)")


@bot.command(name="addbanword")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def addbanword(ctx, *, keyword: str):
    """[ADMIN ONLY] Menambah kata kunci baru ke daftar filter terlarang (tersimpan permanen)."""
    global BANNED_KEYWORDS
    keyword_clean = keyword.strip()
    if not keyword_clean:
        await ctx.send("❌ Kata kunci tidak boleh kosong.")
        return

    keyword_lower = keyword_clean.lower()
    if keyword_lower in BANNED_KEYWORDS:
        await ctx.send(f"⚠️ Kata kunci `{keyword_clean}` sudah ada di daftar terlarang.")
        return

    BANNED_KEYWORDS.append(keyword_lower)
    save_banned_words(BANNED_KEYWORDS)
    await ctx.send(f"✅ Kata kunci `{keyword_clean}` berhasil ditambahkan ke filter terlarang & disimpan permanen.")


@addbanword.error
async def addbanword_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Masukkan kata kunci yang ingin diblokir. Format: `!addbanword <kata>`")


@bot.command(name="banwordlist")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def banwordlist(ctx):
    """[ADMIN ONLY] Menampilkan status total kata kunci terlarang aktif."""
    await ctx.send(
        f"🛡️ Saat ini terdapat **{len(BANNED_KEYWORDS)} kata kunci terlarang** aktif yang dipantau oleh Auto-Mod. "
        f"Gunakan `!addbanword <kata>` untuk menambah filter baru."
    )


@banwordlist.error
async def banwordlist_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")


@bot.command(name="exportdata", aliases=["backupdata", "backuplevels"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def exportdata(ctx):
    """[ADMIN ONLY] Mengunduh file backup data levels.json, banned_words.json & warnings.json."""
    data = load_data()
    banwords = load_banned_words()
    warns = load_warnings()

    data_json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    banwords_json_bytes = json.dumps(banwords, indent=2, ensure_ascii=False).encode("utf-8")
    warns_json_bytes = json.dumps(warns, indent=2, ensure_ascii=False).encode("utf-8")

    file_levels = discord.File(io.BytesIO(data_json_bytes), filename="levels.json")
    file_banwords = discord.File(io.BytesIO(banwords_json_bytes), filename="banned_words.json")
    file_warns = discord.File(io.BytesIO(warns_json_bytes), filename="warnings.json")

    embed = discord.Embed(
        title="💾 Backup & Migrasi Data",
        description=(
            f"✅ Berhasil mengekspor data:\n"
            f"• **Total Member Terdata**: {len(data)} user\n"
            f"• **Total Filter Terlarang**: {len(banwords)} kata\n"
            f"• **Catatan Peringatan**: Aktif\n\n"
            f"Simpan file ini jika ingin berpindah akun Railway / platform hosting lain.\n"
            f"Gunakan perintah `!importdata` di bot baru untuk me-restore."
        ),
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed, files=[file_levels, file_banwords, file_warns])


@exportdata.error
async def exportdata_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")


@bot.command(name="importdata", aliases=["restoredata", "restorelevels"])
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def importdata(ctx):
    """
    [ADMIN ONLY] Me-restore data levels.json dari file attachment yang dikirim.
    Cara pakai: Ketik !importdata dan lampirkan file levels.json di pesan tersebut.
    """
    if not ctx.message.attachments:
        await ctx.send("⚠️ Silakan ketik `!importdata` sambil **melampirkan (attach) file `levels.json`** hasil export.")
        return

    attachment = ctx.message.attachments[0]
    if not attachment.filename.endswith(".json"):
        await ctx.send("❌ Format file harus berupa file JSON (`levels.json`).")
        return

    try:
        content_bytes = await attachment.read()
        imported_data = json.loads(content_bytes.decode("utf-8"))

        if not isinstance(imported_data, dict):
            await ctx.send("❌ Format struktur isi file JSON tidak valid.")
            return

        valid_count = 0
        cleaned_data = {}
        for uid, user_info in imported_data.items():
            if isinstance(user_info, dict):
                cleaned_data[str(uid)] = {
                    "xp": int(user_info.get("xp", 0)),
                    "level": int(user_info.get("level", 0)),
                    "total_xp": int(user_info.get("total_xp", user_info.get("xp", 0)))
                }
                valid_count += 1

        async with db_lock:
            current_data = load_data()
            current_data.update(cleaned_data)
            save_data(current_data)

        embed = discord.Embed(
            title="📥 Restore Data Berhasil!",
            description=(
                f"✅ Berhasil mengimpor **{valid_count} data member** ke database bot!\n"
                f"Seluruh level, rank, dan XP member telah dipulihkan."
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    except json.JSONDecodeError:
        await ctx.send("❌ File yang dikirim rusak atau bukan format JSON yang valid.")
    except Exception as e:
        await ctx.send(f"❌ Gagal memproses file backup: {e}")


@importdata.error
async def importdata_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ Perintah ini khusus Admin (memerlukan izin `Manage Server`).")


@bot.command(name="help", aliases=["bantuan", "info"])
async def help_cmd(ctx):
    """Menampilkan panduan perintah bot."""
    embed = discord.Embed(
        title="📖 Menu Bantuan Bot Sinyal (Level, Rank & Auto-Mod)",
        description="Berikut adalah daftar perintah yang tersedia:",
        color=discord.Color.green()
    )
    embed.add_field(
        name="👤 Perintah Member",
        value=(
            "• `!rank` — Cek level, XP, dan progress diri sendiri\n"
            "• `!rank @user` — Cek level & rank member lain\n"
            "• `!leaderboard` (atau `!top`, `!lb`) — Lihat 10 besar member teratas"
        ),
        inline=False
    )
    embed.add_field(
        name="🛡️ Perintah Admin (Izin: Manage Server)",
        value=(
            "• `!setrankchannel [#channel/here/all]` — Kunci command !rank hanya di channel tertentu\n"
            "• `!warnings @user` — Cek total peringatan pelanggaran member\n"
            "• `!resetwarn @user` — Reset peringatan member ke 0\n"
            "• `!warn @user <alasan>` — Beri peringatan manual ke member\n"
            "• `!addxp @user <jumlah>` — Tambah bonus XP (maks. 10.000)\n"
            "• `!setlevel @user <level>` — Ubah level member langsung (0 - 1000)\n"
            "• `!addbanword <kata>` — Tambahkan kata kunci ke filter terlarang\n"
            "• `!banwordlist` — Cek jumlah kata terlarang aktif\n"
            "• `!exportdata` — Unduh backup database lengkap\n"
            "• `!importdata` — Restore data backup via attachment"
        ),
        inline=False
    )
    embed.set_footer(text="Auto-Mod, Anti-Cheat, & Sistem Strike aktif melindungi server secara otomatis.")
    await ctx.send(embed=embed)


# ==========================================
# GLOBAL ERROR HANDLER
# ==========================================
@bot.event
async def on_command_error(ctx, error):
    try:
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ Perintah ini hanya bisa digunakan di dalam server Discord, bukan melalui Direct Message (DM).")
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            if not hasattr(ctx.command, 'on_error'):
                print(f"[GLOBAL COMMAND ERROR] {error}")
    except (discord.Forbidden, discord.NotFound):
        pass
    except Exception as e:
        print(f"[ERROR HANDLER EXCEPTION] {e}")


# ==========================================
# MENJALANKAN BOT
# ==========================================
if __name__ == "__main__":
    if not TOKEN or TOKEN == "MASUKKAN_TOKEN_ANDA_DI_SINI":
        print("=" * 60)
        print("[ERROR] Token bot belum diisi!")
        print("Silakan masukkan token di file .env (DISCORD_TOKEN=...)")
        print("atau tambahkan Environment Variable di platform hosting Anda.")
        print("=" * 60)
    else:
        print("[INFO] Sedang menghubungkan bot ke Discord...")
        try:
            bot.run(TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n" + "=" * 65)
            print("[PERHATIAN] Privileged Gateway Intents belum diaktifkan di Discord Portal!")
            print("Langkah mengaktifkannya:")
            print("1. Buka https://discord.com/developers/applications")
            print("2. Pilih bot Anda -> Masuk ke menu 'Bot'")
            print("3. Scroll ke bagian 'Privileged Gateway Intents'")
            print("4. Centang / Aktifkan:")
            print("   - [ON] SERVER MEMBERS INTENT")
            print("   - [ON] MESSAGE CONTENT INTENT")
            print("5. Klik 'Save Changes' di bawah")
            print("6. Jalankan kembali script ini.")
            print("=" * 65 + "\n")
        except discord.errors.LoginFailure:
            print("\n" + "=" * 65)
            print("[ERROR] Token Bot tidak valid atau sudah di-reset.")
            print("Silakan periksa kembali token bot Anda di file .env")
            print("=" * 65 + "\n")
        except Exception as e:
            print(f"[ERROR] Terjadi kendala saat koneksi: {e}")
