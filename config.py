# ==========================================
# DOR'S STORE TICKET BOT - CONFIG
# ==========================================


# ================= STORE ================= #

STORE_NAME = "Dor`s STORE"


# ================= STAFF ================= #

STAFF_ROLE_IDS = [
    1515801878749904927,  # Owner
    1515808352847007863,  # Mod
]


# ================= CHANNEL ================= #

# Channel tempat panel ticket dikirim
CHANNEL_PANEL_ID = 1515799628686032907

# Channel tempat private thread ticket dibuat
TICKET_PARENT_ID = 1515799628686032907

# Channel log ticket
CHANNEL_TICKET_LOG_ID = 1539794462090203287

# Channel vouch
VOUCH_CHANNEL_ID = 1515942022651973763


# ================= BRANDING ================= #

# Logo DOR HELPER
#
# Ganti URL di bawah dengan Media Link
# logo yang kamu upload ke Discord.
#
# Contoh:
# LOGO_URL = (
#     "https://cdn.discordapp.com/"
#     "attachments/"
#     "ID_CHANNEL/"
#     "ID_FILE/"
#     "dor-helper.png"
# )

LOGO_URL = "https://cdn.discordapp.com/attachments/1515821738263445585/1541804517035737098/ChatGPT_Image_25_Agu_2026_20.12.15.png?ex=6a8eecda&is=6a8d9b5a&hm=20b31dcae35a24b01e264be0dd23bac354deac2eb628371957f601f04720148e&"


# Banner DOR HELPER / Vouch
GIF_BANNER_URL = (
    "https://media.discordapp.net/"
    "attachments/"
    "1515821738263445585/"
    "1516284932912320572/"
    "standard.gif"
)


# ================= QRIS ================= #

# Pilihan QRIS yang ditampilkan pada menu Payment.
# Jika link CDN Discord kedaluwarsa, unggah ulang gambar QRIS
# dan ganti URL di sini.

QRIS_OPTIONS = {
    "pikri": {
        "label": "QRIS Pikri",
        "description": "Bayar menggunakan QRIS Pikri",
        "emoji": "💳",
        "url": (
            "https://media.discordapp.net/attachments/"
            "1562777566299951154/1563522138210836561/"
            "IMG_2904.jpg?ex=6ae334f6&is=6ae1e376"
            "&hm=c248ceb6f7d74aec0e0eea0aeebb608a6"
            "edf952c030f740f241d437889b7e9e5&="
            "&format=webp&width=721&height=1024"
        ),
    },
    "epen": {
        "label": "QRIS Epen",
        "description": "Bayar menggunakan QRIS Epen",
        "emoji": "💳",
        "url": (
            "https://cdn.discordapp.com/attachments/"
            "1562777566299951154/1564710435242909707/"
            "IMG_1316.jpg?ex=6ae2ea66&is=6ae198e6"
            "&hm=a52d0fe89cab1aa82e54157c97ca933a"
            "57e5b46fdc1644593565e248d1cdd334&"
        ),
    },
    "pincen": {
        "label": "QRIS Pincen",
        "description": "Bayar menggunakan QRIS Pincen",
        "emoji": "💳",
        "url": (
            "https://cdn.discordapp.com/attachments/"
            "1562777566299951154/1564775737695666247/"
            "qr_ID1026626250470_28.10.26_1793130786_"
            "1793130786890.jpg?ex=6ae32737&is=6ae1d5b7"
            "&hm=3a7284cdf747bc7084a01f92ca9f150a"
            "f15bfc0e1e6a111105c5c75af2e386ac&"
        ),
    },
}


# ================= TICKET SETTINGS ================= #

# Maksimal ticket aktif per customer
MAX_ACTIVE_TICKETS = 1


# ================= VOUCH SETTINGS ================= #

# Rating minimum dan maksimum
MIN_RATING = 1
MAX_RATING = 5