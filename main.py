"""
Earning Hub Number Bot - Python Version
All features: Numbers, WhatsApp Check, OTP, Earnings, Withdraw, 2FA, TempMail, Admin, Referral
"""

import os
import json
import re
import time
import asyncio
import logging
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

import pyotp
from aiohttp import web as aio_web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton
from telegram.error import RetryAfter, TimedOut, NetworkError
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)


# тФАтФАтФА Premium Emoji (ржмрж╛ржЯржирзЗ Custom Emoji) тФАтФАтФА
# settings["premiumEmoji"] = {"enabled": bool, "map": {рж╕рж╛ржзрж╛рж░ржг_ржЗржорзЛржЬрж┐: custom_emoji_id}}
# ON ржерж╛ржХрж▓рзЗ ржмрж╛ржЯржирзЗрж░ рж╢рзБрж░рзБрж░ ржЗржорзЛржЬрж┐ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржжрж┐ржпрж╝рзЗ ржмржжрж▓рзЗ ржпрж╛ржмрзЗ, OFF рж╣рж▓рзЗ ржЖржЧрзЗрж░ ржорждрзЛржЗред
# ржЬрж░рзБрж░рж┐ ржмржирзНржз ржХрж░рждрзЗ: Railway Variables ржП PREMIUM_EMOJI_OFF=1 ржжрж┐ржи, ржЕржержмрж╛ ржЕрзНржпрж╛ржбржорж┐ржи рж╣рж┐рж╕рзЗржмрзЗ /pe_off ржкрж╛ржарж╛ржиред
_RealInlineKeyboardButton = InlineKeyboardButton
_RealKeyboardButton = KeyboardButton

def _pe_cfg() -> dict:
    try:
        cfg = settings.get("premiumEmoji")
    except NameError:
        return {}
    return cfg if isinstance(cfg, dict) else {}

def _pe_active() -> bool:
    if os.environ.get("PREMIUM_EMOJI_OFF") == "1":
        return False
    cfg = _pe_cfg()
    return bool(cfg.get("enabled")) and bool(cfg.get("map"))

def _pe_split(text):
    """ржмрж╛ржЯржирзЗрж░ рж▓рзЗржЦрж╛рж░ рж╢рзБрж░рзБрждрзЗ map-ржПрж░ ржЗржорзЛржЬрж┐ ржерж╛ржХрж▓рзЗ (custom_emoji_id, ржмрж╛ржХрж┐ рж▓рзЗржЦрж╛) ржлрзЗрж░ржд ржжрзЗржпрж╝ред"""
    if not isinstance(text, str):
        return None, text
    emap = _pe_cfg().get("map") or {}
    for key in sorted(emap, key=len, reverse=True):
        eid = emap.get(key)
        if not eid:
            continue
        for prefix in (key + "\ufe0f", key):
            if text.startswith(prefix):
                rest = text[len(prefix):].lstrip()
                if rest:
                    return eid, rest
    return None, text

def _pe_make(real_cls, text, args, kwargs):
    if "icon_custom_emoji_id" not in kwargs and _pe_active():
        eid, new_text = _pe_split(text)
        if eid:
            try:
                return real_cls(new_text, *args, icon_custom_emoji_id=eid, **kwargs)
            except TypeError:
                ak = dict(kwargs.pop("api_kwargs", None) or {})
                ak["icon_custom_emoji_id"] = eid
                return real_cls(new_text, *args, api_kwargs=ak, **kwargs)
    return real_cls(text, *args, **kwargs)

def InlineKeyboardButton(text, *args, **kwargs):
    return _pe_make(_RealInlineKeyboardButton, text, args, kwargs)

def KeyboardButton(text, *args, **kwargs):
    return _pe_make(_RealKeyboardButton, text, args, kwargs)

# тФАтФАтФА Logging тФАтФАтФА
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# тФАтФАтФА Configuration тФАтФАтФА
BOT_TOKEN = "7907217678:AAHAmCLtMKr0JLK4g0b0cNX965nFtsBMXy8"
ADMIN_PASSWORD = "sadhin232134"

MAIN_CHANNEL     = "@earning_hub_official_channel"
MAIN_CHANNEL_URL = "https://t.me/earning_hub_official_channel"
MAIN_CHANNEL_ID  = -1003543718769
CHAT_GROUP       = "https://t.me/earning_hub_number_channel"
CHAT_GROUP_ID    = -1003875142184
OTP_GROUP        = "https://t.me/EarningHub_otp"
OTP_GROUP_ID     = -1003247504066

# тФАтФАтФА Baileys API (WhatsApp) тФАтФАтФА
BAILEYS_URL = os.environ.get("BAILEYS_URL", "http://localhost:3000")

# тФАтФАтФА Data Directory тФАтФАтФА
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(os.path.abspath(__file__)))
logger.info(f"ЁЯУБ Data Directory: {DATA_DIR}")

# тФАтФАтФА File Paths тФАтФАтФА
NUMBERS_FILE        = os.path.join(DATA_DIR, "numbers.txt")
COUNTRIES_FILE      = os.path.join(DATA_DIR, "countries.json")
USERS_FILE          = os.path.join(DATA_DIR, "users.json")
SERVICES_FILE       = os.path.join(DATA_DIR, "services.json")
ACTIVE_NUMBERS_FILE = os.path.join(DATA_DIR, "active_numbers.json")
OTP_LOG_FILE        = os.path.join(DATA_DIR, "otp_log.json")
ADMINS_FILE         = os.path.join(DATA_DIR, "admins.json")
SETTINGS_FILE       = os.path.join(DATA_DIR, "settings.json")
TOTP_SECRETS_FILE   = os.path.join(DATA_DIR, "totp_secrets.json")
TEMP_MAILS_FILE     = os.path.join(DATA_DIR, "temp_mails.json")
EARNINGS_FILE       = os.path.join(DATA_DIR, "earnings.json")
WITHDRAW_FILE       = os.path.join(DATA_DIR, "withdrawals.json")
COUNTRY_PRICES_FILE = os.path.join(DATA_DIR, "country_prices.json")
WA_OWNER_FILE       = os.path.join(DATA_DIR, "wa_owner.json")
REFERRALS_FILE      = os.path.join(DATA_DIR, "referrals.json")
PENDING_DM_FILE      = os.path.join(DATA_DIR, "pending_dm.json")
PENDING_GROUP_FILE   = os.path.join(DATA_DIR, "pending_group.json")

# тФАтФАтФА Default Settings тФАтФАтФА
DEFAULT_SETTINGS = {
    "defaultNumberCount": 10,
    "cooldownSeconds": 5,
    "requireVerification": True,
    "minWithdraw": 50,
    "defaultOtpPrice": 0.25,
    "withdrawMethods": ["bKash", "Nagad"],
    "withdrawEnabled": True,
    "referralCommission": 10,
    "panelPollInterval": 1,     # рж╕рзЗржХрзЗржирзНржб тАФ ржкрзНржпрж╛ржирзЗрж▓ ржХржд рж╕рзЗржХрзЗржирзНржб ржкрж░ржкрж░ ржирждрзБржи SMS/OTP ржЪрзЗржХ ржХрж░ржмрзЗ
    "queueRetryInterval": 1,    # рж╕рзЗржХрзЗржирзНржб тАФ pending DM/Group queue ржХржд рж╕рзЗржХрзЗржирзНржб ржкрж░ржкрж░ ржлрзНрж▓рж╛рж╢ ржХрж░рж╛рж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░ржмрзЗ
    "queueExpiryHours": 3,      # ржШржирзНржЯрж╛ тАФ ржПрж░ ржмрзЗрж╢рж┐ ржкрзБрж░ржирзЛ рж╣рж▓рзЗ queue ржерзЗржХрзЗ entry ржмрж╛ржж ржкржбрж╝рзЗ ржпрж╛ржмрзЗ
}

# тФАтФАтФА Load/Save Helpers тФАтФАтФА
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {path}: {e}")

# тФАтФАтФА Load Data тФАтФАтФА
settings       = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
if "referralCommission" not in settings:
    settings["referralCommission"] = 10
if not isinstance(settings.get("premiumEmoji"), dict):
    settings["premiumEmoji"] = {"enabled": False, "map": {}}

users          = load_json(USERS_FILE, {})
active_numbers = load_json(ACTIVE_NUMBERS_FILE, {})
otp_log        = load_json(OTP_LOG_FILE, [])
admins         = load_json(ADMINS_FILE, [])
totp_secrets   = load_json(TOTP_SECRETS_FILE, {})
temp_mails     = load_json(TEMP_MAILS_FILE, {})
earnings       = load_json(EARNINGS_FILE, {})
withdrawals    = load_json(WITHDRAW_FILE, [])
country_prices = load_json(COUNTRY_PRICES_FILE, {})
referrals      = load_json(REFERRALS_FILE, {})
wa_sessions    = {}

# тФАтФАтФА Global WhatsApp System тФАтФАтФА
# admin ржПржХржЯрж╛ WA connect ржХрж░рж▓рзЗ рж╕ржм user ржПрж░ number check рж╣ржмрзЗ
GLOBAL_WA_FILE    = os.path.join(DATA_DIR, "global_wa.json")
global_wa_data    = load_json(GLOBAL_WA_FILE, {
    "enabled":   False,   # Global WA check on/off
    "connected": False,   # Admin WA connected ржХрж┐ржирж╛
    "phone":     "",      # Admin WA phone
    "uid":       "",      # Admin WA session uid
})

def save_global_wa():
    save_json(GLOBAL_WA_FILE, global_wa_data)
_tg_app        = None

countries = load_json(COUNTRIES_FILE, {
    "880": {"name": "Bangladesh",   "flag": "ЁЯЗзЁЯЗй"},
    "91":  {"name": "India",        "flag": "ЁЯЗоЁЯЗ│"},
    "92":  {"name": "Pakistan",     "flag": "ЁЯЗ╡ЁЯЗ░"},
    "977": {"name": "Nepal",        "flag": "ЁЯЗ│ЁЯЗ╡"},
    "94":  {"name": "Sri Lanka",    "flag": "ЁЯЗ▒ЁЯЗ░"},
    "95":  {"name": "Myanmar",      "flag": "ЁЯЗ▓ЁЯЗ▓"},
    "975": {"name": "Bhutan",       "flag": "ЁЯЗзЁЯЗ╣"},
    "960": {"name": "Maldives",     "flag": "ЁЯЗ▓ЁЯЗ╗"},
    "66":  {"name": "Thailand",     "flag": "ЁЯЗ╣ЁЯЗн"},
    "84":  {"name": "Vietnam",      "flag": "ЁЯЗ╗ЁЯЗ│"},
    "62":  {"name": "Indonesia",    "flag": "ЁЯЗоЁЯЗй"},
    "60":  {"name": "Malaysia",     "flag": "ЁЯЗ▓ЁЯЗ╛"},
    "63":  {"name": "Philippines",  "flag": "ЁЯЗ╡ЁЯЗн"},
    "65":  {"name": "Singapore",    "flag": "ЁЯЗ╕ЁЯЗм"},
    "855": {"name": "Cambodia",     "flag": "ЁЯЗ░ЁЯЗн"},
    "856": {"name": "Laos",         "flag": "ЁЯЗ▒ЁЯЗж"},
    "673": {"name": "Brunei",       "flag": "ЁЯЗзЁЯЗ│"},
    "670": {"name": "Timor-Leste",  "flag": "ЁЯЗ╣ЁЯЗ▒"},
    "86":  {"name": "China",        "flag": "ЁЯЗиЁЯЗ│"},
    "81":  {"name": "Japan",        "flag": "ЁЯЗпЁЯЗ╡"},
    "82":  {"name": "South Korea",  "flag": "ЁЯЗ░ЁЯЗ╖"},
    "886": {"name": "Taiwan",       "flag": "ЁЯЗ╣ЁЯЗ╝"},
    "852": {"name": "Hong Kong",    "flag": "ЁЯЗнЁЯЗ░"},
    "853": {"name": "Macau",        "flag": "ЁЯЗ▓ЁЯЗ┤"},
    "976": {"name": "Mongolia",     "flag": "ЁЯЗ▓ЁЯЗ│"},
    "850": {"name": "North Korea",  "flag": "ЁЯЗ░ЁЯЗ╡"},
    "7":   {"name": "Russia",       "flag": "ЁЯЗ╖ЁЯЗ║"},
    "996": {"name": "Kyrgyzstan",   "flag": "ЁЯЗ░ЁЯЗм"},
    "992": {"name": "Tajikistan",   "flag": "ЁЯЗ╣ЁЯЗп"},
    "993": {"name": "Turkmenistan", "flag": "ЁЯЗ╣ЁЯЗ▓"},
    "998": {"name": "Uzbekistan",   "flag": "ЁЯЗ║ЁЯЗ┐"},
    "7778":{"name": "Kazakhstan",   "flag": "ЁЯЗ░ЁЯЗ┐"},
    "93":  {"name": "Afghanistan",  "flag": "ЁЯЗжЁЯЗл"},
    "98":  {"name": "Iran",         "flag": "ЁЯЗоЁЯЗ╖"},
    "964": {"name": "Iraq",         "flag": "ЁЯЗоЁЯЗ╢"},
    "963": {"name": "Syria",        "flag": "ЁЯЗ╕ЁЯЗ╛"},
    "961": {"name": "Lebanon",      "flag": "ЁЯЗ▒ЁЯЗз"},
    "962": {"name": "Jordan",       "flag": "ЁЯЗпЁЯЗ┤"},
    "972": {"name": "Israel",       "flag": "ЁЯЗоЁЯЗ▒"},
    "970": {"name": "Palestine",    "flag": "ЁЯЗ╡ЁЯЗ╕"},
    "966": {"name": "Saudi Arabia", "flag": "ЁЯЗ╕ЁЯЗж"},
    "971": {"name": "UAE",          "flag": "ЁЯЗжЁЯЗк"},
    "974": {"name": "Qatar",        "flag": "ЁЯЗ╢ЁЯЗж"},
    "973": {"name": "Bahrain",      "flag": "ЁЯЗзЁЯЗн"},
    "965": {"name": "Kuwait",       "flag": "ЁЯЗ░ЁЯЗ╝"},
    "968": {"name": "Oman",         "flag": "ЁЯЗ┤ЁЯЗ▓"},
    "967": {"name": "Yemen",        "flag": "ЁЯЗ╛ЁЯЗк"},
    "994": {"name": "Azerbaijan",   "flag": "ЁЯЗжЁЯЗ┐"},
    "374": {"name": "Armenia",      "flag": "ЁЯЗжЁЯЗ▓"},
    "995": {"name": "Georgia",      "flag": "ЁЯЗмЁЯЗк"},
    "44":  {"name": "UK",           "flag": "ЁЯЗмЁЯЗз"},
    "49":  {"name": "Germany",      "flag": "ЁЯЗйЁЯЗк"},
    "33":  {"name": "France",       "flag": "ЁЯЗлЁЯЗ╖"},
    "39":  {"name": "Italy",        "flag": "ЁЯЗоЁЯЗ╣"},
    "34":  {"name": "Spain",        "flag": "ЁЯЗкЁЯЗ╕"},
    "31":  {"name": "Netherlands",  "flag": "ЁЯЗ│ЁЯЗ▒"},
    "32":  {"name": "Belgium",      "flag": "ЁЯЗзЁЯЗк"},
    "41":  {"name": "Switzerland",  "flag": "ЁЯЗиЁЯЗн"},
    "43":  {"name": "Austria",      "flag": "ЁЯЗжЁЯЗ╣"},
    "351": {"name": "Portugal",     "flag": "ЁЯЗ╡ЁЯЗ╣"},
    "353": {"name": "Ireland",      "flag": "ЁЯЗоЁЯЗк"},
    "352": {"name": "Luxembourg",   "flag": "ЁЯЗ▒ЁЯЗ║"},
    "356": {"name": "Malta",        "flag": "ЁЯЗ▓ЁЯЗ╣"},
    "357": {"name": "Cyprus",       "flag": "ЁЯЗиЁЯЗ╛"},
    "45":  {"name": "Denmark",      "flag": "ЁЯЗйЁЯЗ░"},
    "46":  {"name": "Sweden",       "flag": "ЁЯЗ╕ЁЯЗк"},
    "47":  {"name": "Norway",       "flag": "ЁЯЗ│ЁЯЗ┤"},
    "358": {"name": "Finland",      "flag": "ЁЯЗлЁЯЗо"},
    "354": {"name": "Iceland",      "flag": "ЁЯЗоЁЯЗ╕"},
    "370": {"name": "Lithuania",    "flag": "ЁЯЗ▒ЁЯЗ╣"},
    "371": {"name": "Latvia",       "flag": "ЁЯЗ▒ЁЯЗ╗"},
    "372": {"name": "Estonia",      "flag": "ЁЯЗкЁЯЗк"},
    "30":  {"name": "Greece",       "flag": "ЁЯЗмЁЯЗ╖"},
    "48":  {"name": "Poland",       "flag": "ЁЯЗ╡ЁЯЗ▒"},
    "420": {"name": "Czech Rep.",   "flag": "ЁЯЗиЁЯЗ┐"},
    "421": {"name": "Slovakia",     "flag": "ЁЯЗ╕ЁЯЗ░"},
    "36":  {"name": "Hungary",      "flag": "ЁЯЗнЁЯЗ║"},
    "40":  {"name": "Romania",      "flag": "ЁЯЗ╖ЁЯЗ┤"},
    "359": {"name": "Bulgaria",     "flag": "ЁЯЗзЁЯЗм"},
    "385": {"name": "Croatia",      "flag": "ЁЯЗнЁЯЗ╖"},
    "381": {"name": "Serbia",       "flag": "ЁЯЗ╖ЁЯЗ╕"},
    "387": {"name": "Bosnia",       "flag": "ЁЯЗзЁЯЗж"},
    "386": {"name": "Slovenia",     "flag": "ЁЯЗ╕ЁЯЗо"},
    "382": {"name": "Montenegro",   "flag": "ЁЯЗ▓ЁЯЗк"},
    "389": {"name": "N. Macedonia", "flag": "ЁЯЗ▓ЁЯЗ░"},
    "355": {"name": "Albania",      "flag": "ЁЯЗжЁЯЗ▒"},
    "373": {"name": "Moldova",      "flag": "ЁЯЗ▓ЁЯЗй"},
    "380": {"name": "Ukraine",      "flag": "ЁЯЗ║ЁЯЗж"},
    "375": {"name": "Belarus",      "flag": "ЁЯЗзЁЯЗ╛"},
    "383": {"name": "Kosovo",       "flag": "ЁЯЗ╜ЁЯЗ░"},
    "1":   {"name": "USA/Canada",   "flag": "ЁЯЗ║ЁЯЗ╕"},
    "52":  {"name": "Mexico",       "flag": "ЁЯЗ▓ЁЯЗ╜"},
    "506": {"name": "Costa Rica",   "flag": "ЁЯЗиЁЯЗ╖"},
    "502": {"name": "Guatemala",    "flag": "ЁЯЗмЁЯЗ╣"},
    "504": {"name": "Honduras",     "flag": "ЁЯЗнЁЯЗ│"},
    "503": {"name": "El Salvador",  "flag": "ЁЯЗ╕ЁЯЗ╗"},
    "505": {"name": "Nicaragua",    "flag": "ЁЯЗ│ЁЯЗо"},
    "507": {"name": "Panama",       "flag": "ЁЯЗ╡ЁЯЗж"},
    "53":  {"name": "Cuba",         "flag": "ЁЯЗиЁЯЗ║"},
    "509": {"name": "Haiti",        "flag": "ЁЯЗнЁЯЗ╣"},
    "501": {"name": "Belize",       "flag": "ЁЯЗзЁЯЗ┐"},
    "55":  {"name": "Brazil",       "flag": "ЁЯЗзЁЯЗ╖"},
    "54":  {"name": "Argentina",    "flag": "ЁЯЗжЁЯЗ╖"},
    "56":  {"name": "Chile",        "flag": "ЁЯЗиЁЯЗ▒"},
    "57":  {"name": "Colombia",     "flag": "ЁЯЗиЁЯЗ┤"},
    "51":  {"name": "Peru",         "flag": "ЁЯЗ╡ЁЯЗк"},
    "58":  {"name": "Venezuela",    "flag": "ЁЯЗ╗ЁЯЗк"},
    "593": {"name": "Ecuador",      "flag": "ЁЯЗкЁЯЗи"},
    "591": {"name": "Bolivia",      "flag": "ЁЯЗзЁЯЗ┤"},
    "595": {"name": "Paraguay",     "flag": "ЁЯЗ╡ЁЯЗ╛"},
    "598": {"name": "Uruguay",      "flag": "ЁЯЗ║ЁЯЗ╛"},
    "592": {"name": "Guyana",       "flag": "ЁЯЗмЁЯЗ╛"},
    "597": {"name": "Suriname",     "flag": "ЁЯЗ╕ЁЯЗ╖"},
    "20":  {"name": "Egypt",        "flag": "ЁЯЗкЁЯЗм"},
    "213": {"name": "Algeria",      "flag": "ЁЯЗйЁЯЗ┐"},
    "212": {"name": "Morocco",      "flag": "ЁЯЗ▓ЁЯЗж"},
    "216": {"name": "Tunisia",      "flag": "ЁЯЗ╣ЁЯЗ│"},
    "218": {"name": "Libya",        "flag": "ЁЯЗ▒ЁЯЗ╛"},
    "249": {"name": "Sudan",        "flag": "ЁЯЗ╕ЁЯЗй"},
    "234": {"name": "Nigeria",      "flag": "ЁЯЗ│ЁЯЗм"},
    "233": {"name": "Ghana",        "flag": "ЁЯЗмЁЯЗн"},
    "221": {"name": "Senegal",      "flag": "ЁЯЗ╕ЁЯЗ│"},
    "225": {"name": "C├┤te d'Ivoire","flag": "ЁЯЗиЁЯЗо"},
    "222": {"name": "Mauritania",   "flag": "ЁЯЗ▓ЁЯЗ╖"},
    "223": {"name": "Mali",         "flag": "ЁЯЗ▓ЁЯЗ▒"},
    "226": {"name": "Burkina Faso", "flag": "ЁЯЗзЁЯЗл"},
    "227": {"name": "Niger",        "flag": "ЁЯЗ│ЁЯЗк"},
    "228": {"name": "Togo",         "flag": "ЁЯЗ╣ЁЯЗм"},
    "229": {"name": "Benin",        "flag": "ЁЯЗзЁЯЗп"},
    "232": {"name": "Sierra Leone", "flag": "ЁЯЗ╕ЁЯЗ▒"},
    "231": {"name": "Liberia",      "flag": "ЁЯЗ▒ЁЯЗ╖"},
    "224": {"name": "Guinea",       "flag": "ЁЯЗмЁЯЗ│"},
    "245": {"name": "Guinea-Bissau","flag": "ЁЯЗмЁЯЗ╝"},
    "238": {"name": "Cape Verde",   "flag": "ЁЯЗиЁЯЗ╗"},
    "237": {"name": "Cameroon",     "flag": "ЁЯЗиЁЯЗ▓"},
    "243": {"name": "DR Congo",     "flag": "ЁЯЗиЁЯЗй"},
    "242": {"name": "Congo",        "flag": "ЁЯЗиЁЯЗм"},
    "240": {"name": "Eq. Guinea",   "flag": "ЁЯЗмЁЯЗ╢"},
    "241": {"name": "Gabon",        "flag": "ЁЯЗмЁЯЗж"},
    "236": {"name": "CAR",          "flag": "ЁЯЗиЁЯЗл"},
    "235": {"name": "Chad",         "flag": "ЁЯЗ╣ЁЯЗй"},
    "254": {"name": "Kenya",        "flag": "ЁЯЗ░ЁЯЗк"},
    "255": {"name": "Tanzania",     "flag": "ЁЯЗ╣ЁЯЗ┐"},
    "256": {"name": "Uganda",       "flag": "ЁЯЗ║ЁЯЗм"},
    "251": {"name": "Ethiopia",     "flag": "ЁЯЗкЁЯЗ╣"},
    "252": {"name": "Somalia",      "flag": "ЁЯЗ╕ЁЯЗ┤"},
    "253": {"name": "Djibouti",     "flag": "ЁЯЗйЁЯЗп"},
    "257": {"name": "Burundi",      "flag": "ЁЯЗзЁЯЗо"},
    "250": {"name": "Rwanda",       "flag": "ЁЯЗ╖ЁЯЗ╝"},
    "291": {"name": "Eritrea",      "flag": "ЁЯЗкЁЯЗ╖"},
    "27":  {"name": "South Africa", "flag": "ЁЯЗ┐ЁЯЗж"},
    "258": {"name": "Mozambique",   "flag": "ЁЯЗ▓ЁЯЗ┐"},
    "260": {"name": "Zambia",       "flag": "ЁЯЗ┐ЁЯЗ▓"},
    "263": {"name": "Zimbabwe",     "flag": "ЁЯЗ┐ЁЯЗ╝"},
    "267": {"name": "Botswana",     "flag": "ЁЯЗзЁЯЗ╝"},
    "264": {"name": "Namibia",      "flag": "ЁЯЗ│ЁЯЗж"},
    "266": {"name": "Lesotho",      "flag": "ЁЯЗ▒ЁЯЗ╕"},
    "268": {"name": "Eswatini",     "flag": "ЁЯЗ╕ЁЯЗ┐"},
    "244": {"name": "Angola",       "flag": "ЁЯЗжЁЯЗ┤"},
    "261": {"name": "Madagascar",   "flag": "ЁЯЗ▓ЁЯЗм"},
    "230": {"name": "Mauritius",    "flag": "ЁЯЗ▓ЁЯЗ║"},
    "248": {"name": "Seychelles",   "flag": "ЁЯЗ╕ЁЯЗи"},
    "61":  {"name": "Australia",    "flag": "ЁЯЗжЁЯЗ║"},
    "64":  {"name": "New Zealand",  "flag": "ЁЯЗ│ЁЯЗ┐"},
    "679": {"name": "Fiji",         "flag": "ЁЯЗлЁЯЗп"},
    "675": {"name": "Papua NG",     "flag": "ЁЯЗ╡ЁЯЗм"},
    "677": {"name": "Solomon Is.",  "flag": "ЁЯЗ╕ЁЯЗз"},
    "678": {"name": "Vanuatu",      "flag": "ЁЯЗ╗ЁЯЗ║"},
    "676": {"name": "Tonga",        "flag": "ЁЯЗ╣ЁЯЗ┤"},
    "685": {"name": "Samoa",        "flag": "ЁЯЗ╝ЁЯЗ╕"},
    "686": {"name": "Kiribati",     "flag": "ЁЯЗ░ЁЯЗо"},
    "688": {"name": "Tuvalu",       "flag": "ЁЯЗ╣ЁЯЗ╗"},
    "692": {"name": "Marshall Is.", "flag": "ЁЯЗ▓ЁЯЗн"},
    "691": {"name": "Micronesia",   "flag": "ЁЯЗлЁЯЗ▓"},
    "680": {"name": "Palau",        "flag": "ЁЯЗ╡ЁЯЗ╝"},
})

services = load_json(SERVICES_FILE, {
    "whatsapp":    {"name": "WhatsApp",    "icon": "ЁЯУ▒"},
    "telegram":    {"name": "Telegram",    "icon": "тЬИя╕П"},
    "facebook":    {"name": "Facebook",    "icon": "ЁЯУШ"},
    "instagram":   {"name": "Instagram",   "icon": "ЁЯУ╕"},
    "google":      {"name": "Google",      "icon": "ЁЯФН"},
    "verification":{"name": "Verification","icon": "тЬЕ"},
    "other":       {"name": "Other",       "icon": "ЁЯФз"},
})

numbers_by_cs = {}

def load_numbers():
    global numbers_by_cs
    numbers_by_cs = {}
    if not os.path.exists(NUMBERS_FILE):
        return
    try:
        with open(NUMBERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        num, cc, svc = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    elif len(parts) == 2:
                        num, cc, svc = parts[0].strip(), parts[1].strip(), "other"
                    else:
                        continue
                else:
                    num = line
                    cc  = get_country_code_from_number(num)
                    svc = "other"
                if not re.match(r"^\d{10,15}$", num):
                    continue
                if not cc:
                    continue
                numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
                if num not in numbers_by_cs[cc][svc]:
                    numbers_by_cs[cc][svc].append(num)
        total = sum(len(nums) for cc in numbers_by_cs.values() for nums in cc.values())
        logger.info(f"тЬЕ Loaded {total} numbers")
    except Exception as e:
        logger.error(f"Error loading numbers: {e}")

def save_numbers():
    try:
        lines = []
        for cc, svcs in numbers_by_cs.items():
            for svc, nums in svcs.items():
                for num in nums:
                    lines.append(f"{num}|{cc}|{svc}")
        with open(NUMBERS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logger.error(f"Error saving numbers: {e}")

load_numbers()

def save_settings():    save_json(SETTINGS_FILE, settings)
def save_referrals():   save_json(REFERRALS_FILE, referrals)

async def safe_edit(query, text, **kwargs):
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception as e:
        if "not modified" in str(e).lower():
            pass
        else:
            raise

async def async_save_numbers():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_numbers)

async def async_save_users():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_users)

async def async_save_active():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_active)

async def async_save_otp_log():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_otp_log)

async def async_save_earnings():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_earnings)

async def async_save_withdrawals():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_withdrawals)

async def async_save_referrals():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_referrals)

def save_users():       save_json(USERS_FILE, users)
def save_active():
    save_json(ACTIVE_NUMBERS_FILE, active_numbers)
    rebuild_suffix_index()
def save_otp_log():     save_json(OTP_LOG_FILE, otp_log[-1000:])
def save_admins():      save_json(ADMINS_FILE, admins)
def save_totp():        save_json(TOTP_SECRETS_FILE, totp_secrets)
def save_temp_mails():  save_json(TEMP_MAILS_FILE, temp_mails)
def save_earnings():    save_json(EARNINGS_FILE, earnings)
def save_withdrawals(): save_json(WITHDRAW_FILE, withdrawals)
def save_cp():          save_json(COUNTRY_PRICES_FILE, country_prices)
def save_countries():   save_json(COUNTRIES_FILE, countries)
def save_services():    save_json(SERVICES_FILE, services)

if not os.path.exists(SETTINGS_FILE):
    save_settings()
if not os.path.exists(COUNTRIES_FILE):
    save_countries()
if not os.path.exists(SERVICES_FILE):
    save_services()

def is_admin(user_id: str) -> bool:
    return str(user_id) in admins

def get_country_code_from_number(num: str) -> str:
    s = str(num)
    for l in [3, 2, 1]:
        if s[:l] in countries:
            return s[:l]
    return ""

def get_otp_price(cc: str) -> float:
    return country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))

def get_user_earnings(uid: str) -> dict:
    uid = str(uid)
    if uid not in earnings:
        earnings[uid] = {
            "balance": 0,
            "totalEarned": 0,
            "otpCount": 0,
            "referralEarnings": 0,
        }
    if "referralEarnings" not in earnings[uid]:
        earnings[uid]["referralEarnings"] = 0
    return earnings[uid]

def get_referral_link(uid: str, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start=ref_{uid}"

async def add_earning(uid: str, cc: str) -> float:
    uid = str(uid)
    price = get_otp_price(cc)
    e = get_user_earnings(uid)
    e["balance"]     = round(e["balance"] + price, 2)
    e["totalEarned"] = round(e["totalEarned"] + price, 2)
    e["otpCount"]    = e.get("otpCount", 0) + 1

    referrer_id = users.get(uid, {}).get("referredBy")
    if referrer_id and str(referrer_id) != uid:
        commission_pct = settings.get("referralCommission", 10) / 100
        commission = round(price * commission_pct, 4)
        commission = round(commission, 2)
        if commission > 0:
            re_ = get_user_earnings(str(referrer_id))
            re_["balance"]          = round(re_["balance"] + commission, 2)
            re_["totalEarned"]      = round(re_["totalEarned"] + commission, 2)
            re_["referralEarnings"] = round(re_.get("referralEarnings", 0) + commission, 2)
            logger.info(f"ЁЯТ╕ Referral commission {commission:.2f} taka тЖТ uid={referrer_id} (from uid={uid})")

    await async_save_earnings()
    return price

def get_time_ago(dt_str: str) -> str:
    try:
        if not dt_str:
            return "unknown"
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        secs = int((now - dt).total_seconds())
        if secs < 0:    return "just now"
        if secs < 60:   return f"{secs} seconds ago"
        if secs < 3600: return f"{secs // 60} minutes ago"
        if secs < 86400:return f"{secs // 3600} hours ago"
        return f"{secs // 86400} days ago"
    except Exception as e:
        logger.warning(f"get_time_ago error for '{dt_str}': {e}")
        return "unknown"

def get_available_countries_for_service(svc: str) -> list:
    return [cc for cc, svcs in numbers_by_cs.items()
            if svc in svcs and svcs[svc] and cc in countries]

async def get_multiple_numbers(cc: str, svc: str, uid: str, count: int) -> list:
    if cc not in numbers_by_cs or svc not in numbers_by_cs[cc]:
        return []
    pool = numbers_by_cs[cc][svc]
    if not pool:
        return []
    give = min(count, len(pool))
    nums = pool[:give]
    numbers_by_cs[cc][svc] = pool[give:]
    now = datetime.now(timezone.utc).isoformat()
    for n in nums:
        active_numbers[n] = {
            "userId": str(uid), "countryCode": cc, "service": svc,
            "assignedAt": now, "lastOTP": None, "otpCount": 0
        }
    await async_save_numbers()
    await async_save_active()
    return nums

def extract_phone_from_text(text: str):
    m = re.search(r"\+?(\d{10,15})", text)
    return m.group(1) if m else None

# тФАтФАтФА Fast suffix index for active number matching тФАтФАтФА
_suffix_index: dict = {}  # { last_8_digits: number }

def rebuild_suffix_index():
    global _suffix_index
    _suffix_index = {}
    for n in active_numbers:
        clean = n.lstrip("0")
        for l in [8, 7, 6]:
            if len(clean) >= l:
                key = clean[-l:]
                if key not in _suffix_index:
                    _suffix_index[key] = n

def find_active_number(panel_number: str):
    """Panel ржПрж░ number ржжрж┐ржпрж╝рзЗ active_numbers ржП fast match ржХрж░рзЛ"""
    clean = re.sub(r"\D", "", panel_number).lstrip("0")
    # Direct match
    if clean in active_numbers:
        return clean
    # Suffix match via index
    for l in [8, 7, 6]:
        if len(clean) >= l:
            key = clean[-l:]
            if key in _suffix_index:
                return _suffix_index[key]
    return None
    # тФАтФА Strategy 1: Full number direct match тФАтФА
    for num in list(active_numbers.keys()):
        if num in text:
            return num

    # тФАтФА Strategy 2: SPYX mask тАФ "4917SPYX5576" (masdar OTP bot format) тФАтФА
    spyx_patterns = re.findall(r'(\d{3,})[A-Za-z]{2,8}(\d{2,})', text)
    for prefix, suffix in spyx_patterns:
        for num in list(active_numbers.keys()):
            if num.startswith(prefix) and num.endswith(suffix):
                return num

    # тФАтФА Strategy 3: *** mask тАФ "7921***3002" тФАтФА
    masked_patterns = re.findall(r'(\d{3,})\*+(\d{2,})', text)
    for prefix, suffix in masked_patterns:
        for num in list(active_numbers.keys()):
            if num.startswith(prefix) and num.endswith(suffix):
                return num

    # тФАтФА Strategy 4: Number field prefix match тФАтФА
    num_field = re.search(r'[Nn]umber[:\s]+(\d{4,})', text)
    if num_field:
        prefix = num_field.group(1)
        for num in list(active_numbers.keys()):
            if num.startswith(prefix):
                return num

    # тФАтФА Strategy 5: Last 8/6 digits fallback тФАтФА
    for num in list(active_numbers.keys()):
        if num[-8:] in text:
            return num
    for num in list(active_numbers.keys()):
        if num[-6:] in text:
            return num

    # тФАтФА Strategy 6: Last 4 digits with any mask тФАтФА
    for num in list(active_numbers.keys()):
        suffix4 = num[-4:]
        if re.search(r'[A-Za-z\*]+' + re.escape(suffix4) + r'\b', text):
            return num

    return None

def extract_otp(text: str):
    cleaned = re.sub(r'\b(19|20)\d{2}[-/]\d{2}[-/]\d{2}(?:[T\s]\d{2}:\d{2}:\d{2})?\b', '', text)
    cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned)
    patterns = [
        r'OTP\s*Code[:\s]+(\d{4,8})',
        r'\b[A-Z]-(\d{4,8})\b',
        r'(?:otp|code|pin|verification|verify|token)[^\d]{0,10}(\d{4,8})',
        r'(?:is|has|:)\s*(\d{4,8})\b',
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
    ]
    for p in patterns:
        m = re.search(p, cleaned, re.IGNORECASE)
        if m and 4 <= len(m.group(1)) <= 8:
            return m.group(1)
    return None

# тФАтФАтФА HTTP OTP Server тФАтФАтФА
HTTP_PORT = int(os.environ.get("HTTP_PORT", 8080))

async def http_otp_handler(request: aio_web.Request) -> aio_web.Response:
    global _tg_app
    try:
        data      = await request.json()
        number    = re.sub(r"\D", "", str(data.get("number", ""))).lstrip("0")
        otp_code  = str(data.get("otp", "")).strip().replace("-", "").replace(" ", "")
        service   = str(data.get("service", "other")).lower().strip()

        if not number:
            return aio_web.json_response({"ok": False, "error": "number required"}, status=400)

        # active_numbers ржП match ржЦрзЛржБржЬрзЛ тАФ leading zeros ржЫрж╛ржбрж╝рж╛
        matched_number = None
        if number in active_numbers:
            matched_number = number
        else:
            # OTP bot ржнрж┐ржирзНржи format ржП ржкрж╛ржарж╛рждрзЗ ржкрж╛рж░рзЗ, рждрж╛ржЗ suffix match ржХрж░рзЛ
            for n in active_numbers:
                if n.endswith(number[-8:]) or number.endswith(n[-8:]):
                    matched_number = n
                    break

        if not matched_number:
            logger.warning(f"тЪая╕П HTTP /otp: number {number} not in active_numbers")
            return aio_web.json_response({"ok": False, "error": "number not active"}, status=404)

        an_data = active_numbers[matched_number]
        uid     = an_data["userId"]
        cc      = an_data.get("countryCode", "")

        otp_key = f"http_{otp_code}_{matched_number}"
        if an_data.get("lastOTP") == otp_key:
            return aio_web.json_response({"ok": True, "info": "duplicate"})
        an_data["lastOTP"]  = otp_key
        an_data["otpCount"] = an_data.get("otpCount", 0) + 1
        await async_save_active()

        earned  = await add_earning(uid, cc)
        balance = get_user_earnings(uid)["balance"]
        svc     = services.get(service, {"icon": "ЁЯУ▒", "name": service.capitalize()})
        country = countries.get(cc, {"flag": "ЁЯМН", "name": cc})

        notify = (
            f"ЁЯУи *OTP Received!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"ЁЯУЮ *Number:* `+{matched_number}`\n"
        )
        if otp_code:
            notify += f"\nЁЯФС *OTP Code:* `{otp_code}`\n"
        notify += f"\nЁЯТ╡ *+{earned:.2f} taka earned!*\nЁЯТ░ *Balance: {balance:.2f} taka*"

        if _tg_app:
            ok_dm = await send_dm_with_retry(_tg_app, uid, notify)
            if not ok_dm:
                logger.warning(f"тП│ HTTP OTP DM queued (rate-limit/network) тЖТ uid={uid}")

        # тФАтФА Telegram OTP Group ржПржУ ржкрж╛ржарж╛ржУ тФАтФА
        if otp_code:
            group_msg = (
                f"ЁЯУи *New OTP!*\n\n"
                f"{svc['icon']} *Service:* {svc['name']}\n"
                f"{country['flag']} *Country:* {country['name']}\n"
                f"ЁЯУЮ *Number:* +{matched_number}\n"
            )
            asyncio.create_task(send_otp_to_group(otp_code, group_msg))

        otp_log.append({
            "phoneNumber": matched_number, "userId": uid, "countryCode": cc,
            "service": service, "otpCode": otp_code, "earned": earned,
            "messageId": None, "delivered": True,
            "source": "http_api",
            "timestamp": datetime.now().isoformat()
        })
        save_otp_log()

        logger.info(f"тЬЕ HTTP /otp processed: +{matched_number} otp={otp_code} uid={uid}")
        return aio_web.json_response({"ok": True, "earned": earned, "balance": balance})

    except Exception as e:
        logger.error(f"HTTP /otp handler error: {e}")
        return aio_web.json_response({"ok": False, "error": str(e)}, status=500)

async def start_http_server():
    http_app = aio_web.Application()
    http_app.router.add_post("/otp", http_otp_handler)
    http_app.router.add_get("/health", lambda r: aio_web.json_response({"ok": True}))
    runner = aio_web.AppRunner(http_app)
    await runner.setup()
    site = aio_web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    logger.info(f"ЁЯМР HTTP OTP server started тЖТ port {HTTP_PORT}")

def generate_totp(secret: str):
    try:
        clean = secret.replace(" ", "").replace("-", "").upper()
        missing_padding = (8 - len(clean) % 8) % 8
        if missing_padding:
            clean += "=" * missing_padding
        totp = pyotp.TOTP(clean)
        token = totp.now()
        remaining = 30 - (int(time.time()) % 30)
        return {"token": token, "timeRemaining": remaining}
    except Exception as e:
        logger.error(f"generate_totp error (secret_len={len(secret)}): {e}")
        return None

# тФАтФАтФА Baileys API (WhatsApp) Helpers тФАтФАтФА
_green_state  = {"authorized": False}
_green_owner  = load_json(WA_OWNER_FILE, {"uid": None})
_wa_pair_lock = None

def save_green_owner():
    save_json(WA_OWNER_FILE, _green_owner)

def baileys_request(method: str, path: str, body=None) -> dict:
    url     = f"{BAILEYS_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data    = json.dumps(body).encode() if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Baileys API error [{path}]: {e}")
        return {}

async def green_get_state(uid: str = None) -> str:
    loop   = asyncio.get_event_loop()
    path   = f"/status?userId={uid}" if uid else "/status?userId=global"
    result = await loop.run_in_executor(None, lambda: baileys_request("GET", path))
    if result.get("connected"):
        return "authorized"
    return "notAuthorized"


async def green_api_monitor(app):
    logger.info("ЁЯЯв Baileys monitor started")
    fail_counts = {}

    while True:
        await asyncio.sleep(30)
        try:
            for uid in list(wa_sessions.keys()):
                if not wa_sessions.get(uid, {}).get("connected"):
                    continue
                try:
                    state = await green_get_state(uid)
                    if state != "authorized":
                        fail_counts[uid] = fail_counts.get(uid, 0) + 1
                        logger.warning(f"тЪая╕П Baileys: WA check fail #{fail_counts[uid]} uid={uid}")
                        if fail_counts[uid] >= 5:
                            fail_counts.pop(uid, None)
                            wa_sessions.pop(uid, None)
                            logger.warning(f"тЪая╕П Baileys: WhatsApp disconnected! uid={uid}")
                            try:
                                await app.bot.send_message(
                                    int(uid),
                                    "тЪая╕П *WhatsApp Disconnected!*\n\n"
                                    "рждрзЛржорж╛рж░ WhatsApp ржерзЗржХрзЗ bot disconnect рж╣ржпрж╝рзЗржЫрзЗред\n"
                                    "ржЖржмрж╛рж░ connect ржХрж░рждрзЗ ржирж┐ржЪрзЗрж░ button ржЪрж╛ржкрзЛред",
                                    parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("ЁЯУ▒ Connect WhatsApp", callback_data="wa_connect", style="primary")
                                    ]])
                                )
                            except Exception as e:
                                logger.error(f"Disconnect notify error uid={uid}: {e}")
                    else:
                        fail_counts.pop(uid, None)
                except Exception as e:
                    logger.error(f"Baileys monitor error uid={uid}: {e}")
        except Exception as e:
            logger.error(f"Baileys monitor loop error: {e}")

# тФАтФАтФА Pending DM Queue (rate-limit ржП miss рж╣ржУржпрж╝рж╛ DM ржкрж░рзЗ ржЖржмрж╛рж░ ржкрж╛ржарж╛ржирзЛрж░ ржЬржирзНржп) тФАтФАтФА
pending_dm_notifications = load_json(PENDING_DM_FILE, [])

def save_pending_dm():
    save_json(PENDING_DM_FILE, pending_dm_notifications)

async def send_dm_with_retry(app, uid: str, message: str, max_attempts: int = 3,
                              log_number: str = None, log_otp: str = None) -> bool:
    """DM ржкрж╛ржарж╛ржирзЛрж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░рзЗ; rate-limit/network error рж╣рж▓рзЗ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ ржХржпрж╝рзЗржХржмрж╛рж░ retry ржХрж░рзЗред
    рждрж╛ржУ fail рж╣рж▓рзЗ queue рждрзЗ рж░рзЗржЦрзЗ ржжрзЗржпрж╝ тАФ background worker ржкрж░рзЗ ржЖржмрж╛рж░ ржкрж╛ржарж╛ржмрзЗред"""
    tag = f"+{log_number} otp={log_otp} " if log_number else ""
    for attempt in range(max_attempts):
        try:
            await app.bot.send_message(int(uid), message, parse_mode="Markdown")
            logger.info(f"тЬЕ OTP DM sent: {tag}тЖТ uid={uid}")
            return True
        except RetryAfter as e:
            wait_s = float(e.retry_after) + 1
            logger.warning(f"тП│ Rate limited, DM uid={uid} тАФ {wait_s}s ржкрж░ retry")
            await asyncio.sleep(wait_s)
        except (TimedOut, NetworkError):
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"тЭМ DM permanent error uid={uid}: {e}")
            return False  # ржмрзНрж▓ржХ/ржЗржЙржЬрж╛рж░ ржбрж┐рж▓рж┐ржЯ рж╣ржУржпрж╝рж╛рж░ ржорждрзЛ non-retryable error тАФ queue рждрзЗ рж░рж╛ржЦрж╛рж░ ржжрж░ржХрж╛рж░ ржирж╛ржЗ

    # рж╕ржм ржЪрзЗрж╖рзНржЯрж╛ fail тАФ ржкрж░рзЗ ржкрж╛ржарж╛ржирзЛрж░ ржЬржирзНржп queue рждрзЗ рж░рж╛ржЦрзЛ
    pending_dm_notifications.append({
        "uid": uid, "message": message, "added": time.time(), "tries": 0
    })
    save_pending_dm()
    logger.warning(f"ЁЯУе OTP DM queued for later delivery: {tag}uid={uid}")
    return False

async def _retry_dm_item(app, item: dict):
    """ржПржХржЯрж╛ queued DM тАФ rate limit рж╢рзЗрж╖ рж╣рж▓рзЗржЗ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ (concurrently, ржЕржирзНржп item-ржПрж░ ржЬржирзНржп ржЕржкрзЗржХрзНрж╖рж╛ ржирж╛ ржХрж░рзЗ) ржкрж╛ржарж╛ржпрж╝ред"""
    try:
        await app.bot.send_message(int(item["uid"]), item["message"], parse_mode="Markdown")
        logger.info(f"тЬЕ Queued DM delivered: uid={item['uid']}")
        return
    except RetryAfter as e:
        await asyncio.sleep(float(e.retry_after) + 1)
        try:
            await app.bot.send_message(int(item["uid"]), item["message"], parse_mode="Markdown")
            logger.info(f"тЬЕ Queued DM delivered (rate-limit рж╢рзЗрж╖рзЗ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ): uid={item['uid']}")
            return
        except Exception:
            pass
    except (TimedOut, NetworkError):
        pass
    except Exception as e:
        logger.error(f"тЭМ Queued DM dropped (permanent) uid={item['uid']}: {e}")
        return

    # ржПржЦржирзЛ fail тАФ ржЖржмрж╛рж░ queue рждрзЗ ржлрзЗрж░ржд ржжрж╛ржУ
    item["tries"] = item.get("tries", 0) + 1
    now = time.time()
    if (now - item.get("added", now)) < settings.get("queueExpiryHours", 3) * 3600 and item.get("tries", 0) < 50:
        pending_dm_notifications.append(item)
    save_pending_dm()

async def _retry_group_item(item: dict):
    """ржПржХржЯрж╛ queued group message тАФ rate limit рж╢рзЗрж╖ рж╣рж▓рзЗржЗ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ ржкрж╛ржарж╛ржпрж╝ред"""
    ok = await _send_group_payload(item["payload"])
    if ok:
        logger.info("тЬЕ Queued group OTP message delivered")
        return
    item["tries"] = item.get("tries", 0) + 1
    now = time.time()
    if (now - item.get("added", now)) < settings.get("queueExpiryHours", 3) * 3600 and item.get("tries", 0) < 50:
        pending_group_notifications.append(item)
    save_pending_group()

async def dm_retry_worker(app):
    """ржкрзНрж░рждрж┐ рзз рж╕рзЗржХрзЗржирзНржбрзЗ pending queue ржЪрзЗржХ ржХрж░рзЗ тАФ ржкрзНрж░рждрж┐ржЯрж╛ item рж╕рзНржмрж╛ржзрзАржиржнрж╛ржмрзЗ (concurrently) ржкрж╛ржарж╛ржирзЛ рж╣ржпрж╝,
    рждрж╛ржЗ rate limit рж╢рзЗрж╖ рж╣ржУржпрж╝рж╛рж░ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗржЗ рж╕рзЗржЗ OTP ржЪрж▓рзЗ ржпрж╛ржпрж╝, ржЕржирзНржп ржХрж╛рж░рзЛ ржЬржирзНржп ржЕржкрзЗржХрзНрж╖рж╛ ржХрж░рзЗ ржирж╛ред"""
    while True:
        await asyncio.sleep(settings.get("queueRetryInterval", 1))

        if pending_dm_notifications:
            items = list(pending_dm_notifications)
            pending_dm_notifications.clear()
            save_pending_dm()
            for item in items:
                asyncio.create_task(_retry_dm_item(app, item))

        if pending_group_notifications:
            items_g = list(pending_group_notifications)
            pending_group_notifications.clear()
            save_pending_group()
            for item in items_g:
                asyncio.create_task(_retry_group_item(item))

async def send_otp_to_group(otp_code: str, group_msg: str):
    """Direct HTTP ржжрж┐ржпрж╝рзЗ OTP group ржП ржПржХржмрж╛рж░ ржкрж╛ржарж╛ржирзЛрж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░рзЗ тАФ fail рж╣рж▓рзЗ queue рждрзЗ рж░рзЗржЦрзЗ ржжрзЗржпрж╝,
    background worker ржкрж░рзЗ ржЖржмрж╛рж░ ржкрж╛ржарж╛ржирзЛрж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░ржмрзЗ (ржмрж╛рж░ржмрж╛рж░ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ retry ржХрж░рзЗ ржирж╛)ред"""
    import aiohttp as _aiohttp
    payload = {
        "chat_id":    OTP_GROUP_ID,
        "text":       group_msg,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": str(otp_code), "copy_text": {"text": str(otp_code)}, "style": "success"}],
                [
                    {"text": "тШОя╕П Numbers", "url": "https://t.me/EARNING_HUB_NUMBER_BOT", "style": "primary"},
                    {"text": "ЁЯТм Chats",   "url": "https://t.me/earning_hub_otp_group",   "style": "danger"},
                ]
            ]
        }
    }
    ok = await _send_group_payload(payload)
    if not ok:
        pending_group_notifications.append({"payload": payload, "added": time.time(), "tries": 0})
        save_pending_group()
        logger.warning("ЁЯУе OTP group message queued for later delivery")
    return ok

async def _send_group_payload(payload: dict) -> bool:
    import aiohttp as _aiohttp
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for attempt in range(2):  # ржкрзНрж░ржержоржмрж╛рж░ + rate-limit рж╢рзЗрж╖ рж╣рж▓рзЗ рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ ржЖрж░рзЗржХржмрж╛рж░
        try:
            async with _aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=15) as r:
                    if r.status == 200:
                        return True
                    elif r.status == 429:
                        data        = await r.json()
                        retry_after = data.get("parameters", {}).get("retry_after", 10)
                        logger.warning(f"тЪая╕П OTP Group Flood Wait {retry_after}s")
                        if attempt == 0:
                            await asyncio.sleep(retry_after + 1)
                            continue
                        return False
                    else:
                        logger.error(f"тЭМ OTP group send failed ({r.status})")
                        return False
        except Exception as e:
            logger.error(f"тЭМ OTP group send error: {e}")
            return False
    return False

# тФАтФАтФА Pending Group Queue тФАтФАтФА
pending_group_notifications = load_json(PENDING_GROUP_FILE, [])

def save_pending_group():
    save_json(PENDING_GROUP_FILE, pending_group_notifications)

async def get_wa_pairing_code(phone: str, user_id: str) -> str:
    digits = re.sub(r"\D", "", phone)
    logger.info(f"ЁЯУ▒ Baileys pairing for: +{digits} uid={user_id}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: baileys_request("POST", "/start", {"userId": user_id})
    )
    await asyncio.sleep(3)
    result = await loop.run_in_executor(
        None,
        lambda: baileys_request("POST", "/pair", {"phone": digits, "userId": user_id})
    )
    logger.info(f"Baileys pairing result: {result}")
    if result.get("connected"):
        raise Exception("WhatsApp ржЗрждрж┐ржоржзрзНржпрзЗ connected ржЖржЫрзЗред")
    if result.get("code"):
        code  = str(result["code"])
        clean = re.sub(r"[^A-Z0-9]", "", code.upper())
        if len(clean) >= 8:
            return f"{clean[:4]}-{clean[4:8]}"
        return code
    raise Exception(
        result.get("error") or
        "Pairing code ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред Baileys server ржЪрж╛рж▓рзБ ржЖржЫрзЗ ржХрж┐ржирж╛ ржжрзЗржЦрзЛред"
    )

async def monitor_wa_connection(uid: str, context):
    logger.info(f"ЁЯФН Waiting for WA auth: {uid}")
    for _ in range(60):
        await asyncio.sleep(5)
        try:
            state = await green_get_state(uid)
            if state == "authorized":
                wa_sessions[uid] = {"connected": True}
                logger.info(f"тЬЕ WA connected: uid={uid}")
                try:
                    await context.bot.send_message(
                        int(uid),
                        "тЬЕ *WhatsApp Connected!*\n\n"
                        "ЁЯЯв рждрзЛржорж╛рж░ WhatsApp рж╕ржлрж▓ржнрж╛ржмрзЗ connect рж╣ржпрж╝рзЗржЫрзЗред\n"
                        "ржПржЦржи numbers assign рж╣рж▓рзЗ WA check ржжрзЗржЦрж╛ржмрзЗред\n\n"
                        "Disconnect ржХрж░рждрзЗ ржирж┐ржЪрзЗрж░ ржмрж╛ржЯржи ржЪрж╛ржкрзЛ:",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("ЁЯФ┤ Logout / Disconnect", callback_data="wa_disconnect", style="success")],
                            [InlineKeyboardButton("ЁЯУК Check Status", callback_data="wa_status", style="danger")],
                        ])
                    )
                except:
                    pass
                break
        except Exception as e:
            logger.warning(f"monitor_wa_connection error: {e}")

async def check_wa_number(phone: str, user_id: str):
    # тФАтФА Global WA enabled рж╣рж▓рзЗ admin WA ржжрж┐ржпрж╝рзЗ check ржХрж░рзЛ тФАтФА
    effective_uid = user_id
    if global_wa_data.get("enabled") and global_wa_data.get("connected"):
        effective_uid = global_wa_data.get("uid", user_id)

    if not wa_sessions.get(effective_uid, {}).get("connected"):
        state = await green_get_state(effective_uid)
        if state != "authorized":
            return None
        wa_sessions[effective_uid] = {"connected": True}
    digits = re.sub(r"\D", "", phone)
    loop   = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: baileys_request("POST", "/check", {"numbers": [digits], "userId": effective_uid})
        )
        logger.info(f"ЁЯУ▒ WA check +{digits}: {result}")
        results = result.get("results", {})
        val = results.get(digits)
        if val is True:  return True
        if val is False: return False
        return None
    except Exception as e:
        logger.warning(f"check_wa_number error +{digits}: {e}")
        return None

# тФАтФАтФА Mail.tm API тФАтФАтФА
def mailtm_request(method: str, path: str, body=None, token=None):
    url = f"https://api.mail.tm{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            return err
        except:
            return None
    except Exception as e:
        logger.error(f"Mail.tm error: {e}")
        return None

async def mailtm_request_async(method: str, path: str, body=None, token=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: mailtm_request(method, path, body, token)
    )

def random_str(n: int, chars="abcdefghijklmnopqrstuvwxyz0123456789") -> str:
    import random
    return "".join(random.choice(chars) for _ in range(n))

async def create_fresh_email():
    try:
        domains = await mailtm_request_async("GET", "/domains?page=1")
        domain_list = domains if isinstance(domains, list) else (domains or {}).get("hydra:member", [])
        if not domain_list:
            return None
        domain = domain_list[0]["domain"]
        username = random_str(12)
        password = random_str(16, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        address  = f"{username}@{domain}"
        account = None
        for _ in range(3):
            account = await mailtm_request_async("POST", "/accounts", {"address": address, "password": password})
            if account and account.get("id"):
                break
            await asyncio.sleep(3)
        if not account or not account.get("id"):
            return None
        token_res = await mailtm_request_async("POST", "/token", {"address": address, "password": password})
        if not token_res or not token_res.get("token"):
            return None
        return {
            "address":   address,
            "sidToken":  token_res["token"],
            "provider":  "mailtm",
            "createdAt": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"createFreshEmail error: {e}")
        return None

async def get_email_inbox(email_obj: dict):
    try:
        data = await mailtm_request_async("GET", "/messages?page=1", token=email_obj.get("sidToken"))
        msgs = data if isinstance(data, list) else (data or {}).get("hydra:member", [])
        return [{"id": m.get("id"), "from": (m.get("from") or {}).get("address", ""),
                 "subject": m.get("subject", ""), "date": m.get("createdAt", "")} for m in msgs]
    except:
        return []

async def get_email_message(msg_id: str, email_obj: dict) -> str:
    try:
        data = await mailtm_request_async("GET", f"/messages/{msg_id}", token=email_obj.get("sidToken"))
        if not data:
            return ""
        text = data.get("text", "")
        html = (data.get("html") or [""])[0]
        raw = text or re.sub(r"<[^>]*>", " ", html)
        return re.sub(r"\s+", " ", raw).strip()
    except:
        return ""

# тФАтФАтФА Membership Check тФАтФАтФА
async def check_membership(user_id: int, app) -> dict:
    result = {"mainChannel": False, "chatGroup": False, "otpGroup": False, "allJoined": False}
    try:
        m = await app.bot.get_chat_member(MAIN_CHANNEL_ID, user_id)
        result["mainChannel"] = m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Main channel check: {e}")
    try:
        m = await app.bot.get_chat_member(CHAT_GROUP_ID, user_id)
        result["chatGroup"] = m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Chat group check: {e}")
    try:
        m = await app.bot.get_chat_member(OTP_GROUP_ID, user_id)
        result["otpGroup"] = m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"OTP group check: {e}")
    result["allJoined"] = result["mainChannel"] and result["chatGroup"] and result["otpGroup"]
    return result

# тФАтФАтФА Keyboards тФАтФАтФА
def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("тШОя╕П Get Number", style="primary"), KeyboardButton("ЁЯУз Get Tempmail", style="success")],
        [KeyboardButton("ЁЯФР 2FA", style="danger"), KeyboardButton("ЁЯТ░ Balances", style="primary")],
        [KeyboardButton("ЁЯТ╕ Withdraw", style="success"), KeyboardButton("ЁЯСе Referral", style="danger")],
        [KeyboardButton("ЁЯТм Support", style="primary")]
    ], resize_keyboard=True)

def verify_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1я╕ПтГг ЁЯУв Main Channel", url=MAIN_CHANNEL_URL, style="primary")],
        [InlineKeyboardButton("2я╕ПтГг ЁЯТм Number Channel", url=CHAT_GROUP, style="success")],
        [InlineKeyboardButton("3я╕ПтГг ЁЯУи OTP Group", url=OTP_GROUP, style="danger")],
        [InlineKeyboardButton("тЬЕ VERIFY MEMBERSHIP", callback_data="verify_user", style="primary")],
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ЁЯУК Stock Report", callback_data="admin_stock", style="primary"),
         InlineKeyboardButton("ЁЯСе User Stats", callback_data="admin_users", style="success")],
        [InlineKeyboardButton("ЁЯУв Broadcast", callback_data="admin_broadcast", style="danger"),
         InlineKeyboardButton("ЁЯУЛ OTP Log", callback_data="admin_otp_log", style="primary")],
        [InlineKeyboardButton("тЮХ Add Numbers", callback_data="admin_add_numbers", style="success"),
         InlineKeyboardButton("ЁЯУд Upload File", callback_data="admin_upload", style="danger")],
        [InlineKeyboardButton("ЁЯЧСя╕П Delete Numbers", callback_data="admin_delete", style="primary"),
         InlineKeyboardButton("ЁЯФз Manage Services", callback_data="admin_manage_services", style="success")],
        [InlineKeyboardButton("ЁЯМН Manage Countries", callback_data="admin_manage_countries", style="danger"),
         InlineKeyboardButton("тЪЩя╕П Settings", callback_data="admin_settings", style="primary")],
        [InlineKeyboardButton("ЁЯТ░ Country Prices", callback_data="admin_country_prices", style="success"),
         InlineKeyboardButton("ЁЯТ╕ Withdrawals", callback_data="admin_withdrawals", style="danger")],
        [InlineKeyboardButton("ЁЯСЫ Balance Management", callback_data="admin_balance_manage", style="primary"),
         InlineKeyboardButton("ЁЯСе Referral Stats", callback_data="admin_referral_stats", style="success")],
        [InlineKeyboardButton("ЁЯУб OTP Panels", callback_data="admin_panels", style="danger"),
         InlineKeyboardButton("ЁЯУ▒ Global WA", callback_data="admin_global_wa", style="primary")],
        [InlineKeyboardButton("ЁЯОн Fake OTP Numbers", callback_data="fake_otp_menu", style="success")],
        [InlineKeyboardButton("тЬи Premium Emoji", callback_data="pe_menu", style="primary")],
        [InlineKeyboardButton("ЁЯЪк Logout", callback_data="admin_logout", style="danger")],
    ])

# тФАтФАтФА User Session State тФАтФАтФА
user_sessions = {}

def get_session(uid) -> dict:
    uid = str(uid)
    if uid not in user_sessions:
        user_sessions[uid] = {
            "verified": False, "is_admin": False,
            "state": None, "data": None,
            "current_numbers": [], "current_service": None, "current_country": None,
            "last_number_time": 0, "last_verification_check": 0,
        }
    return user_sessions[uid]

# тФАтФАтФА Verification Middleware тФАтФАтФА
async def ensure_verified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    uid  = str(user.id)
    sess = get_session(uid)

    # Admin рж╕ржмрж╕ржоржпрж╝ pass
    if sess["is_admin"] or is_admin(uid):
        sess["is_admin"] = True
        return True

    # Verification ржмржирзНржз ржерж╛ржХрж▓рзЗ pass
    if not settings.get("requireVerification", True):
        return True

    # Local flag ржЪрзЗржХ тАФ chat_member handler real-time ржП update ржХрж░рзЗ
    if sess.get("verified") or users.get(uid, {}).get("verified", False):
        return True

    # Verified ржирж╛ тАФ rejoin ржХрж░рждрзЗ ржмрж▓рзЛ, block ржирж╛
    msg = (
        "тЪая╕П *Bot ржмрзНржпржмрж╣рж╛рж░ ржХрж░рждрзЗ рж╕ржХрж▓ ржЧрзНрж░рзБржкрзЗ join ржХрж░рждрзЗ рж╣ржмрзЗ!*\n\n"
        "ржирж┐ржЪрзЗрж░ рж╕ржмржЧрзБрж▓рзЛрждрзЗ join ржХрж░рзБржи, рждрж╛рж░ржкрж░ VERIFY ржЪрж╛ржкрзБржи:"
    )
    if update.callback_query:
        await update.callback_query.answer("тЫФ рж╕ржм group ржП join ржХрж░рзЛ!", show_alert=True)
        try:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
        except:
            await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
    else:
        await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
    return False

# тФАтФАтФА /start тФАтФАтФА
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        uid  = str(user.id)

        if uid not in users:
            users[uid] = {
                "id": uid, "username": user.username or "no_username",
                "first_name": user.first_name or "User",
                "last_name": user.last_name or "",
                "joined": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "verified": False,
                "referredBy": None,
                "referralCount": 0,
            }

        if context.args and context.args[0].startswith("ref_"):
            referrer_id = context.args[0][4:]
            # рж╢рзБржзрзБ referredBy рж╕рзЗржЯ ржХрж░рзЛ тАФ verify рж╕ржлрж▓ рж╣ржУржпрж╝рж╛рж░ ржЖржЧрзЗ count рж╣ржмрзЗ ржирж╛
            if (referrer_id != uid
                    and not users[uid].get("referredBy")
                    and referrer_id in users):
                users[uid]["referredBy"] = referrer_id
                users[uid]["referralVerified"] = False
                logger.info(f"ЁЯФЧ Referral pending verify: uid={uid} referred by uid={referrer_id}")

        await async_save_users()

        sess = get_session(uid)
        sess["state"] = None
        sess["data"]  = None

        welcome = (
            f"ЁЯСЛ *Welcome to Earning Hub Number Bot!*\n\n"
            f"ЁЯУ▒ Get virtual numbers for OTP verification\n"
            f"ЁЯТ╡ Earn money from each OTP received"
        )

        if sess.get("verified") or (uid in users and users[uid].get("verified")):
            await update.message.reply_text(
                welcome + "\n\nтЬЕ Choose an option:",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        else:
            await update.message.reply_text(
                welcome + "\n\nFirst, join all required groups to use the bot:",
                parse_mode="Markdown", reply_markup=verify_keyboard()
            )
    except Exception as e:
        logger.error(f"cmd_start error: {e}")
        try:
            await update.message.reply_text("тЪая╕П Error occurred. Please try again.")
        except:
            pass

# тФАтФАтФА Verify тФАтФАтФА
async def cb_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("тП│ Checking...")

    user = update.effective_user
    uid  = str(user.id)
    membership = await check_membership(user.id, context.application)

    if membership["allJoined"]:
        sess = get_session(uid)
        sess["verified"] = True
        sess["last_verification_check"] = time.time()
        if is_admin(uid):
            sess["is_admin"] = True
        if uid in users:
            users[uid]["verified"] = True

            # тФАтФА Referral: рж╢рзБржзрзБ ржкрзНрж░ржержоржмрж╛рж░ verify рж╣рж▓рзЗ count ржХрж░рзЛ тФАтФА
            if not users[uid].get("referralVerified", False):
                referrer_id = users[uid].get("referredBy")
                if referrer_id and referrer_id in users:
                    users[uid]["referralVerified"] = True
                    users[referrer_id]["referralCount"] = users[referrer_id].get("referralCount", 0) + 1
                    referrals.setdefault(referrer_id, [])
                    if uid not in referrals[referrer_id]:
                        referrals[referrer_id].append(uid)
                    await async_save_referrals()
                    logger.info(f"тЬЕ Referral confirmed: uid={uid} тЖТ referrer={referrer_id}")
                    try:
                        await context.bot.send_message(
                            int(referrer_id),
                            f"ЁЯОЙ *New Referral Confirmed!*\n\n"
                            f"ЁЯСд *{user.first_name}* рж╕ржм group join ржХрж░рзЗ verified рж╣ржпрж╝рзЗржЫрзЗ!\n"
                            f"ЁЯТ╕ рждрж╛рж░рж╛ OTP ржерзЗржХрзЗ earn ржХрж░рж▓рзЗ рждрзБржорж┐ *{settings.get('referralCommission', 10)}%* commission ржкрж╛ржмрзЗред",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            await async_save_users()

        await query.edit_message_text("тЬЕ *VERIFICATION SUCCESSFUL!*\n\nYou can now use all features.", parse_mode="Markdown")
        await context.bot.send_message(
            user.id, "ЁЯОЙ Welcome! Choose an option:",
            reply_markup=main_keyboard()
        )
    else:
        msg = "тЭМ *VERIFICATION FAILED*\n\n"
        if not membership["mainChannel"]: msg += "тЭМ 1я╕ПтГг Main Channel\n"
        if not membership["chatGroup"]:   msg += "тЭМ 2я╕ПтГг Number Channel\n"
        if not membership["otpGroup"]:    msg += "тЭМ 3я╕ПтГг OTP Group\n"
        msg += "\nPlease join ALL groups and click VERIFY again."
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())

# тФАтФАтФА Admin Login тФАтФАтФА
async def cmd_adminlogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 2:
        return await update.message.reply_text("тЭМ Usage: /adminlogin [password]")
    if parts[1] == ADMIN_PASSWORD:
        uid = str(update.effective_user.id)
        sess = get_session(uid)
        sess["is_admin"] = True
        sess["state"]    = None
        sess["data"]     = None
        if uid not in admins:
            admins.append(uid)
            save_admins()
        await update.message.reply_text("тЬЕ *Admin Login Successful!*\nUse /admin to access panel.", parse_mode="Markdown")
    else:
        await update.message.reply_text("тЭМ Wrong password.")

# тФАтФАтФА Admin Panel тФАтФАтФА
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    sess = get_session(uid)
    if not sess["is_admin"] and not is_admin(uid):
        return await update.message.reply_text("тЭМ Use /adminlogin [password] first.")
    sess["state"] = None
    sess["data"]  = None
    await update.message.reply_text("ЁЯЫа *Admin Dashboard*\n\nSelect an option:", parse_mode="Markdown", reply_markup=admin_keyboard())

# тФАтФАтФА GET NUMBERS тФАтФАтФА
async def handle_get_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context):
        return
    sess = get_session(str(update.effective_user.id))
    sess["state"] = None

    avail = []
    for svc_id, svc in services.items():
        ccs = get_available_countries_for_service(svc_id)
        if ccs:
            total = sum(len(numbers_by_cs.get(cc, {}).get(svc_id, [])) for cc in ccs)
            avail.append((svc_id, svc, total))

    if not avail:
        return await update.message.reply_text("ЁЯУн *No Numbers Available*\n\nPlease try again later.", parse_mode="Markdown")

    # тФАтФА 3-color cycle for service buttons тФАтФА
    _svc_colors = ["primary", "success", "danger"]
    buttons = []
    for i in range(0, len(avail), 2):
        row = []
        row.append(InlineKeyboardButton(
            f"{avail[i][1]['icon']} {avail[i][1]['name']}",
            callback_data=f"svc:{avail[i][0]}", style=_svc_colors[i % 3]
        ))
        if i+1 < len(avail):
            row.append(InlineKeyboardButton(
                f"{avail[i+1][1]['icon']} {avail[i+1][1]['name']}",
                callback_data=f"svc:{avail[i+1][0]}", style=_svc_colors[(i+1) % 3]
            ))
        buttons.append(row)

    await update.message.reply_text(
        "ЁЯОп *Select a Service*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# тФАтФАтФА cb_select_service тАФ 3-COLOR FIX тФАтФАтФА
async def cb_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    svc    = services.get(svc_id, {"name": svc_id, "icon": "ЁЯУЮ"})
    ccs    = sorted(get_available_countries_for_service(svc_id), key=lambda cc: get_otp_price(cc))

    if not ccs:
        return await query.answer("тЭМ No numbers available", show_alert=True)

    # тФАтФА 3-color cycle: primary=blue, success=green, danger=red тФАтФА
    _cc_colors = ["primary", "success", "danger"]
    buttons = []
    for i in range(0, len(ccs), 2):
        row = []
        cc1 = ccs[i]; c1 = countries[cc1]; p1 = get_otp_price(cc1)
        row.append(InlineKeyboardButton(
            f"{c1['flag']} {c1['name']} ({p1:.2f}TK)",
            callback_data=f"cc:{svc_id}:{cc1}",
            style=_cc_colors[i % 3]
        ))
        if i+1 < len(ccs):
            cc2 = ccs[i+1]; c2 = countries[cc2]; p2 = get_otp_price(cc2)
            row.append(InlineKeyboardButton(
                f"{c2['flag']} {c2['name']} ({p2:.2f}TK)",
                callback_data=f"cc:{svc_id}:{cc2}",
                style=_cc_colors[(i+1) % 3]
            ))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="back_services", style="danger")])

    await query.edit_message_text(
        f"{svc['icon']} *{svc['name']}* тАФ Select Country\n\n_(taka = earnings per OTP)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def cb_select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    _, svc_id, cc = query.data.split(":")
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    count = settings.get("defaultNumberCount", 10)
    now   = time.time()

    cooldown = settings.get("cooldownSeconds", 5)
    if (now - sess["last_number_time"]) < cooldown and sess["current_numbers"]:
        remaining = int(cooldown - (now - sess["last_number_time"]))
        return await query.answer(f"тП│ {remaining} рж╕рзЗржХрзЗржирзНржб ржЕржкрзЗржХрзНрж╖рж╛ ржХрж░рзЛред", show_alert=True)

    nums = await get_multiple_numbers(cc, svc_id, uid, count)
    if not nums:
        return await query.answer("тЭМ Not enough numbers available.", show_alert=True)

    for old in sess["current_numbers"]:
        active_numbers.pop(old, None)
    await async_save_active()

    sess["current_numbers"] = nums
    sess["current_service"] = svc_id
    sess["current_country"] = cc
    sess["last_number_time"] = now

    country = countries.get(cc, {"flag": "ЁЯМН", "name": cc})
    svc     = services.get(svc_id, {"icon": "ЁЯУЮ", "name": svc_id})
    price   = get_otp_price(cc)
    wa_connected = wa_sessions.get(uid, {}).get("connected", False) or (global_wa_data.get("enabled") and global_wa_data.get("connected"))

    def make_msg():
        return (
            f"тЬЕ *{len(nums)} Number(s) Assigned!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"ЁЯТ╡ *Earnings per OTP:* {price:.2f} taka\n\n"
            f"ЁЯУМ OTP automatically ржЖрж╕ржмрзЗред"
        )

    # тФАтФА Copy buttons тАФ рзиржЯрж╛ ржХрж░рзЗ ржПржХ row тФАтФА
    from telegram import CopyTextButton

    def make_copy_buttons(wa_result=None):
        rows = []
        for n in nums:
            if wa_result:
                status = wa_result.get(n)
                icon  = "ЁЯУ▒" if status is True else ("тЭМ" if status is False else "тмЬ")
                style = "success" if status is True else ("danger" if status is False else "primary")
            else:
                icon  = "тП│" if wa_connected else "ЁЯУЛ"
                style = "primary"
            rows.append([InlineKeyboardButton(
                text=f"{icon} +{n}",
                copy_text=CopyTextButton(text=f"+{n}"),
                style=style
            )])
        return rows

    bottom_buttons = [
        [InlineKeyboardButton("ЁЯУи Open OTP Group", url=OTP_GROUP, style="primary")],
        [InlineKeyboardButton("ЁЯФД Get New Numbers", callback_data=f"newnum:{svc_id}:{cc}", style="success")],
        [InlineKeyboardButton("ЁЯФЩ Service List", callback_data="back_services", style="danger")],
    ]
    if not wa_connected:
        bottom_buttons.append([InlineKeyboardButton("ЁЯУ▒ Connect WhatsApp", callback_data="wa_connect", style="primary")])

    buttons = make_copy_buttons() + bottom_buttons
    await query.edit_message_text(make_msg(), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    if wa_connected:
        chat_id = query.message.chat_id
        msg_id  = query.message.message_id
        async def do_wa_check():
            results = await asyncio.gather(
                *[check_wa_number(n, uid) for n in nums],
                return_exceptions=True
            )
            res = {n: (r if not isinstance(r, Exception) else None)
                   for n, r in zip(nums, results)}
            try:
                await context.bot.edit_message_text(
                    make_msg(), chat_id=chat_id, message_id=msg_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(make_copy_buttons(res) + bottom_buttons)
                )
            except: pass
        asyncio.create_task(do_wa_check())
        asyncio.create_task(do_wa_check())

async def cb_new_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    _, svc_id, cc = query.data.split(":")
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    now  = time.time()
    cooldown = settings.get("cooldownSeconds", 5)

    if (now - sess["last_number_time"]) < cooldown:
        remaining = int(cooldown - (now - sess["last_number_time"]))
        return await query.answer(f"тП│ {remaining} рж╕рзЗржХрзЗржирзНржб ржЕржкрзЗржХрзНрж╖рж╛ ржХрж░рзЛред", show_alert=True)

    count = settings.get("defaultNumberCount", 10)
    nums  = await get_multiple_numbers(cc, svc_id, uid, count)
    if not nums:
        return await query.answer("тЭМ No numbers available.", show_alert=True)

    for old in sess["current_numbers"]:
        active_numbers.pop(old, None)
    await async_save_active()

    sess["current_numbers"] = nums
    sess["last_number_time"] = now

    country = countries.get(cc, {"flag": "ЁЯМН", "name": cc})
    svc     = services.get(svc_id, {"icon": "ЁЯУЮ", "name": svc_id})
    price   = get_otp_price(cc)
    wa_connected = wa_sessions.get(uid, {}).get("connected", False) or (global_wa_data.get("enabled") and global_wa_data.get("connected"))

    def make_msg_new():
        return (
            f"ЁЯФД *{len(nums)} New Number(s)!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"ЁЯТ╡ *Earnings per OTP:* {price:.2f} taka\n\n"
            f"ЁЯУМ OTP automatically ржЖрж╕ржмрзЗред"
        )

    from telegram import CopyTextButton

    def make_copy_buttons_new(wa_result=None):
        rows = []
        for n in nums:
            if wa_result:
                status = wa_result.get(n)
                icon  = "ЁЯУ▒" if status is True else ("тЭМ" if status is False else "тмЬ")
                style = "success" if status is True else ("danger" if status is False else "primary")
            else:
                icon  = "тП│" if wa_connected else "ЁЯУЛ"
                style = "primary"
            rows.append([InlineKeyboardButton(
                text=f"{icon} +{n}",
                copy_text=CopyTextButton(text=f"+{n}"),
                style=style
            )])
        return rows

    bottom_buttons_new = [
        [InlineKeyboardButton("ЁЯУи Open OTP Group", url=OTP_GROUP, style="primary")],
        [InlineKeyboardButton("ЁЯФД Get New Numbers", callback_data=f"newnum:{svc_id}:{cc}", style="success")],
        [InlineKeyboardButton("ЁЯФЩ Service List", callback_data="back_services", style="danger")],
    ]
    if not wa_connected:
        bottom_buttons_new.append([InlineKeyboardButton("ЁЯУ▒ Connect WhatsApp", callback_data="wa_connect", style="primary")])

    buttons = make_copy_buttons_new() + bottom_buttons_new
    await query.edit_message_text(make_msg_new(), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    if wa_connected:
        chat_id = query.message.chat_id
        msg_id  = query.message.message_id
        async def do_wa_check_new():
            results = await asyncio.gather(
                *[check_wa_number(n, uid) for n in nums],
                return_exceptions=True
            )
            res = {n: (r if not isinstance(r, Exception) else None)
                   for n, r in zip(nums, results)}
            try:
                await context.bot.edit_message_text(
                    make_msg_new(), chat_id=chat_id, message_id=msg_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(make_copy_buttons_new(res) + bottom_buttons_new)
                )
            except: pass
        asyncio.create_task(do_wa_check_new())

async def cb_back_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    avail = []
    for svc_id, svc in services.items():
        ccs = get_available_countries_for_service(svc_id)
        if ccs:
            total = sum(len(numbers_by_cs.get(cc, {}).get(svc_id, [])) for cc in ccs)
            avail.append((svc_id, svc, total))

    # тФАтФА 3-color cycle тФАтФА
    _svc_colors = ["primary", "success", "danger"]
    buttons = []
    for i in range(0, len(avail), 2):
        row = []
        row.append(InlineKeyboardButton(
            f"{avail[i][1]['icon']} {avail[i][1]['name']}",
            callback_data=f"svc:{avail[i][0]}", style=_svc_colors[i % 3]
        ))
        if i+1 < len(avail):
            row.append(InlineKeyboardButton(
                f"{avail[i+1][1]['icon']} {avail[i+1][1]['name']}",
                callback_data=f"svc:{avail[i+1][0]}", style=_svc_colors[(i+1) % 3]
            ))
        buttons.append(row)

    await query.edit_message_text(
        "ЁЯОп *Select a Service*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# тФАтФАтФА BALANCE тФАтФАтФА
async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    e   = get_user_earnings(uid)
    pending = [w for w in withdrawals if w["userId"] == uid and w["status"] == "pending"]
    withdrawn = sum(w["amount"] for w in withdrawals if w["userId"] == uid and w["status"] == "approved")
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = e.get("referralEarnings", 0)

    await update.message.reply_text(
        f"ЁЯТ░ *Your Earnings*\n\n"
        f"ЁЯТ╡ *Current Balance:* {e['balance']:.2f} taka\n"
        f"ЁЯУИ *Total Earned:* {e['totalEarned']:.2f} taka\n"
        f"ЁЯУи *Total OTPs:* {e.get('otpCount', 0)}\n"
        f"ЁЯТ╕ *Total Withdrawn:* {withdrawn:.2f} taka\n"
        f"тП│ *Pending Withdrawals:* {len(pending)}\n\n"
        f"ЁЯСе *Referrals:* {ref_count} ржЬржи\n"
        f"ЁЯОБ *Referral Earnings:* {ref_earn:.2f} taka\n\n"
        f"ЁЯУМ *Minimum Withdraw:* {settings['minWithdraw']} taka",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯТ╕ Withdraw", callback_data="start_withdraw", style="danger")],
            [InlineKeyboardButton("ЁЯУЛ Withdraw History", callback_data="withdraw_history", style="primary")],
        ])
    )

# тФАтФАтФА REFERRAL тФАтФАтФА
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    bot_username = context.bot.username
    ref_link = get_referral_link(uid, bot_username)
    commission = settings.get("referralCommission", 10)
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = get_user_earnings(uid).get("referralEarnings", 0)

    referred_list = referrals.get(uid, [])
    referred_text = ""
    if referred_list:
        for r_uid in referred_list[-5:][::-1]:
            r_user = users.get(r_uid, {})
            r_name = r_user.get("first_name", "User")
            r_name = r_name.replace("*", "").replace("_", "")
            r_earn  = get_user_earnings(r_uid)
            my_cut  = round(r_earn.get("totalEarned", 0) * commission / 100, 2)
            referred_text += f"  ЁЯСд {r_name} тАФ рждрзЛржорж╛рж░ cut: *{my_cut:.2f} taka*\n"

    msg = (
        f"ЁЯСе *Referral Program*\n\n"
        f"ЁЯФЧ рждрзЛржорж╛рж░ referral link:\n`{ref_link}`\n\n"
        f"ЁЯТ╕ *Commission:* ржкрзНрж░рждрж┐ OTP ржПрж░ *{commission}%*\n\n"
        f"ЁЯУК *рждрзЛржорж╛рж░ Stats:*\n"
        f"  ЁЯСе Total Referrals: *{ref_count}*\n"
        f"  ЁЯТ░ Total Commission Earned: *{ref_earn:.2f} taka*\n"
    )
    if referred_text:
        msg += f"\nЁЯУЛ *Recent Referrals:*\n{referred_text}"

    msg += (
        f"\nЁЯУМ *How it works:*\n"
        f"  1. ржЙржкрж░рзЗрж░ link share ржХрж░рзЛ\n"
        f"  2. ржХрзЗржЙ join ржХрж░рж▓рзЗ рждрж╛рж░рж╛ OTP earn ржХрж░ржмрзЗ\n"
        f"  3. рждрзБржорж┐ рждрж╛ржжрзЗрж░ ржкрзНрж░рждрж┐ржЯрж╛ OTP income ржПрж░ *{commission}%* ржкрж╛ржмрзЗ ржЖржЬрзАржмржи!\n"
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯФЧ Share Referral Link", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(f'ржЖржорж╛рж░ referral link ржжрж┐ржпрж╝рзЗ join ржХрж░рзЛ ржПржмржВ OTP ржерзЗржХрзЗ ржЖржпрж╝ ржХрж░рзЛ!')}", style="success")],
            [InlineKeyboardButton("ЁЯУК Referral Stats", callback_data="ref_stats", style="danger")],
        ])
    )

async def cb_ref_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    commission = settings.get("referralCommission", 10)
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = get_user_earnings(uid).get("referralEarnings", 0)
    referred_list = referrals.get(uid, [])

    msg = (
        f"ЁЯУК *Referral Statistics*\n\n"
        f"ЁЯСе *Total Referred:* {ref_count}\n"
        f"ЁЯТ░ *Total Commission:* {ref_earn:.2f} taka\n"
        f"ЁЯУМ *Commission Rate:* {commission}%\n\n"
    )

    if referred_list:
        msg += "ЁЯСд *All Referred Users:*\n"
        for r_uid in referred_list[-20:]:
            r_user = users.get(r_uid, {})
            r_name = r_user.get("first_name", "User").replace("*", "").replace("_", "")
            r_earn = get_user_earnings(r_uid)
            otps   = r_earn.get("otpCount", 0)
            my_cut = round(r_earn.get("totalEarned", 0) * commission / 100, 2)
            msg += f"  тАв {r_name} | OTPs: {otps} | рждрзЛржорж╛рж░: {my_cut:.2f}рз│\n"
    else:
        msg += "ржПржЦржирзЛ ржХрзЛржирзЛ referral ржирзЗржЗред\n"

    if len(msg) > 4000:
        msg = msg[:3950] + "\n..._truncated_"

    bot_username = context.bot.username
    ref_link = get_referral_link(uid, bot_username)

    await query.edit_message_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯФЧ Share Link", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}", style="primary")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="goto_main", style="success")],
        ])
    )

# тФАтФАтФА WITHDRAW тФАтФАтФА
async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    e   = get_user_earnings(uid)
    sess = get_session(uid)
    sess["state"] = None

    if not settings.get("withdrawEnabled", True):
        return await update.message.reply_text("тП╕я╕П *Withdrawals are currently disabled.*", parse_mode="Markdown")

    if e["balance"] < settings["minWithdraw"]:
        return await update.message.reply_text(
            f"тЭМ *Insufficient balance.*\n\n"
            f"ЁЯТ╡ Balance: {e['balance']:.2f} taka\n"
            f"ЁЯУМ Minimum: {settings['minWithdraw']} taka",
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        f"ЁЯТ╕ *Withdraw*\n\nЁЯТ╡ Balance: *{e['balance']:.2f} taka*\n\nChoose method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯЯг bKash", callback_data="wm:bKash", style="danger"),
             InlineKeyboardButton("ЁЯЯа Nagad", callback_data="wm:Nagad", style="primary")],
            [InlineKeyboardButton("тЭМ Cancel", callback_data="w_cancel", style="success")],
        ])
    )

async def cb_withdraw_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split(":", 1)[1]
    uid    = str(update.effective_user.id)
    sess   = get_session(uid)
    e      = get_user_earnings(uid)

    sess["state"] = "w_amount"
    sess["data"]  = {"method": method}

    amounts = []
    for a in [settings["minWithdraw"], 100, 200, 500]:
        if e["balance"] >= a and a not in amounts:
            amounts.append(a)

    rows = []
    for i in range(0, len(amounts), 2):
        row = [InlineKeyboardButton(f"{amounts[i]} taka", callback_data=f"wa:{method}:{amounts[i]}", style="primary")]
        if i+1 < len(amounts):
            row.append(InlineKeyboardButton(f"{amounts[i+1]} taka", callback_data=f"wa:{method}:{amounts[i+1]}", style="success"))
        rows.append(row)
    rows.append([InlineKeyboardButton(f"ЁЯТ░ All ({e['balance']:.2f} taka)", callback_data=f"wa:{method}:{e['balance']:.2f}", style="danger")])
    rows.append([InlineKeyboardButton("тЭМ Cancel", callback_data="w_cancel", style="primary")])

    icon = "ЁЯЯг" if method == "bKash" else "ЁЯЯа"
    await query.edit_message_text(
        f"{icon} *{method} Withdrawal*\n\nЁЯТ╡ Balance: *{e['balance']:.2f} taka*\n\nSelect amount or type in chat:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, method, amt_str = query.data.split(":")
    amount = float(amt_str)
    uid    = str(update.effective_user.id)
    sess   = get_session(uid)
    e      = get_user_earnings(uid)

    if amount < settings["minWithdraw"]:
        return await query.answer(f"тЭМ Minimum {settings['minWithdraw']} taka", show_alert=True)
    if amount > e["balance"]:
        return await query.answer("тЭМ Insufficient balance!", show_alert=True)

    sess["state"] = "w_account"
    sess["data"]  = {"method": method, "amount": amount}
    icon = "ЁЯЯг" if method == "bKash" else "ЁЯЯа"

    await query.edit_message_text(
        f"{icon} *{method} тАФ {amount:.2f} taka*\n\nЁЯУ▒ Your *{method} number:*\nExample: `01712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="w_cancel", style="success")]])
    )

async def cb_withdraw_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None
    await query.edit_message_text("тЭМ *Cancelled.*", parse_mode="Markdown")

async def cb_withdraw_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = str(update.effective_user.id)
    uwith = [w for w in withdrawals if w["userId"] == uid][-10:][::-1]

    text = "ЁЯУЛ *Withdraw History*\n\n"
    if not uwith:
        text += "No withdrawal requests yet."
    else:
        for w in uwith:
            icon = "тЬЕ" if w["status"] == "approved" else "тЭМ" if w["status"] == "rejected" else "тП│"
            date = w["requestedAt"][:10]
            text += f"{icon} *{w['amount']:.2f} taka* - {w['method']}\n"
            text += f"ЁЯУ▒ `{w['account']}` | {date}\n\n"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="goto_main", style="danger")]]))

async def cb_start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    e    = get_user_earnings(uid)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None

    if not settings.get("withdrawEnabled", True):
        return await query.edit_message_text("тП╕я╕П *Withdrawals are currently disabled.*", parse_mode="Markdown")
    if e["balance"] < settings["minWithdraw"]:
        return await query.edit_message_text(
            f"тЭМ *Insufficient balance.*\nЁЯТ╡ Balance: {e['balance']:.2f} taka\nЁЯУМ Minimum: {settings['minWithdraw']} taka",
            parse_mode="Markdown"
        )

    await query.edit_message_text(
        f"ЁЯТ╕ *Withdraw*\n\nЁЯТ╡ Balance: *{e['balance']:.2f} taka*\n\nChoose method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯЯг bKash", callback_data="wm:bKash", style="primary"),
             InlineKeyboardButton("ЁЯЯа Nagad", callback_data="wm:Nagad", style="success")],
            [InlineKeyboardButton("тЭМ Cancel", callback_data="w_cancel", style="danger")],
        ])
    )

# тФАтФАтФА WhatsApp Connect тФАтФАтФА
async def cb_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)

    if wa_sessions.get(uid, {}).get("connected"):
        await query.edit_message_text(
            "тЬЕ *WhatsApp Already Connected!*\n\n"
            "ЁЯЯв WhatsApp ржПржЦржи active ржЖржЫрзЗред\n"
            "Disconnect ржХрж░рждрзЗ ржирж┐ржЪрзЗрж░ ржмрж╛ржЯржи ржЪрж╛ржкрзЛ:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ЁЯФ┤ Logout / Disconnect", callback_data="wa_disconnect", style="primary")],
                [InlineKeyboardButton("ЁЯУК Check Status", callback_data="wa_status", style="success")],
            ])
        )
        return

    sess = get_session(uid)
    sess["state"] = "wa_waiting_number"
    await context.bot.send_message(
        update.effective_user.id,
        "ЁЯУ▒ WhatsApp Connect\n\nрждрзЛржорж╛рж░ WhatsApp ржиржорзНржмрж░ ржжрж╛ржУ (country code рж╕рж╣):\nExample: 8801712345678"
    )

async def cb_wa_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("тП│ Checking...")
    uid   = str(update.effective_user.id)

    try:
        state = await green_get_state(uid)
    except:
        state = "notAuthorized"

    conn = (state == "authorized")
    if conn:
        wa_sessions[uid] = {"connected": True}
    else:
        wa_sessions.pop(uid, None)

    STATE_MAP = {
        "authorized":    "тЬЕ *WhatsApp Connected!*\n\nNumber assign рж╣рж▓рзЗ ЁЯУ▒/тЭМ ржжрзЗржЦрж╛ржмрзЗред",
        "notAuthorized": "ЁЯФ┤ *WhatsApp connected ржирзЗржЗред*\n\nCode enter ржХрж░рж▓рзЗ ржЖржмрж╛рж░ Check Status ржЪрж╛ржкрзЛред",
    }
    text = STATE_MAP.get(state, f"тЭУ Unknown state: {state}")
    btns = [[InlineKeyboardButton("ЁЯФ┤ Disconnect", callback_data="wa_disconnect", style="danger")]] if conn else \
           [[InlineKeyboardButton("ЁЯУ▒ Connect", callback_data="wa_connect", style="primary")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def cb_wa_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("тП│ Disconnecting...")
    uid = str(update.effective_user.id)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: baileys_request("POST", "/disconnect", {"userId": uid}))
        logger.info(f"тЬЕ Baileys logout called for uid={uid}")
    except Exception as e:
        logger.error(f"Baileys logout error: {e}")

    wa_sessions.pop(uid, None)

    await query.edit_message_text(
        "ЁЯФ┤ *WhatsApp Disconnected!*\n\n"
        "рждрзЛржорж╛рж░ WhatsApp рж╕ржлрж▓ржнрж╛ржмрзЗ logout рж╣ржпрж╝рзЗржЫрзЗред\n"
        "ржЖржмрж╛рж░ connect ржХрж░рждрзЗ ржирж┐ржЪрзЗрж░ ржмрж╛ржЯржи ржЪрж╛ржкрзЛ:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯУ▒ Connect WhatsApp", callback_data="wa_connect", style="success")],
        ])
    )

# тФАтФАтФА Temp Mail тФАтФАтФА
async def handle_tempmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    existing = temp_mails.get(uid)

    if existing:
        await update.message.reply_text(
            f"ЁЯУз *Temporary Email*\n\nЁЯУМ Your email:\n`{existing['address']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ЁЯУм Check Inbox", callback_data="tm_inbox", style="danger")],
                [InlineKeyboardButton("ЁЯУЛ Show Email", callback_data="tm_show", style="primary")],
                [InlineKeyboardButton("ЁЯФД Get New Email", callback_data="tm_create", style="success")],
                [InlineKeyboardButton("ЁЯЧСя╕П Delete Email", callback_data="tm_delete", style="danger")],
            ])
        )
    else:
        await update.message.reply_text(
            "ЁЯУз *Temporary Email*\n\nтЬЕ Create a new disposable email address.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯЖХ Create New Email", callback_data="tm_create", style="primary")]])
        )

async def cb_tm_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("тП│ Creating...")
    uid   = str(update.effective_user.id)
    loading = await context.bot.send_message(uid, "тП│ *Creating your email...*", parse_mode="Markdown")

    async def _create_task():
        try:
            new_email = await create_fresh_email()
            if not new_email:
                await context.bot.edit_message_text(
                    "тЭМ *Email creation failed.* Please try again.",
                    chat_id=uid, message_id=loading.message_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФД Retry", callback_data="tm_create", style="success")]])
                )
                return
            temp_mails[uid] = new_email
            save_temp_mails()
            await context.bot.edit_message_text(
                f"тЬЕ *New Email Created!*\n\nЁЯУз `{new_email['address']}`\n\nЁЯУМ Use this on any website.",
                chat_id=uid, message_id=loading.message_id,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ЁЯУм Check Inbox", callback_data="tm_inbox", style="danger")],
                    [InlineKeyboardButton("ЁЯФД Get New Email", callback_data="tm_create", style="primary")],
                    [InlineKeyboardButton("ЁЯЧСя╕П Delete", callback_data="tm_delete", style="success")],
                ])
            )
        except Exception as e:
            logger.error(f"cb_tm_create task error uid={uid}: {e}")
            try:
                await context.bot.edit_message_text(
                    "тЭМ *Error occurred.* Please try again.",
                    chat_id=uid, message_id=loading.message_id,
                    parse_mode="Markdown"
                )
            except:
                pass

    asyncio.create_task(_create_task())

async def cb_tm_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ЁЯУм Loading...")
    uid = str(update.effective_user.id)

    if uid not in temp_mails:
        return await query.edit_message_text(
            "тЭМ No email found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯЖХ Create", callback_data="tm_create", style="danger")]])
        )

    email_obj = temp_mails[uid]

    async def _inbox_task():
        try:
            messages  = await get_email_inbox(email_obj)
            now_str   = datetime.now().strftime("%I:%M:%S %p")
            text      = f"ЁЯУм *Inbox:* `{email_obj['address']}`\nЁЯХР _{now_str}_\n\n"

            if not messages:
                text += "ЁЯУн *No emails yet.*"
            else:
                for msg in messages[:5]:
                    text += f"тФБтФБтФБтФБтФБтФБтФБтФБтФБтФБ\nЁЯУй *From:* {msg['from']}\nЁЯУМ *Subject:* {msg['subject']}\n"
                    body = await get_email_message(msg["id"], email_obj)
                    if body:
                        otp_m = re.findall(r"\b\d{4,8}\b", body)
                        if otp_m:
                            text += f"\nЁЯФС *OTP:* `{otp_m[0]}`\n"
                        text += f"\nЁЯУЭ _{body[:250]}..._\n" if len(body) > 250 else f"\nЁЯУЭ _{body}_\n"
                    text += "\n"

            try:
                await query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ЁЯФД Refresh", callback_data="tm_inbox", style="primary")],
                    [InlineKeyboardButton("ЁЯФД New Email", callback_data="tm_create", style="success")],
                    [InlineKeyboardButton("ЁЯЧСя╕П Delete", callback_data="tm_delete", style="danger")],
                ]))
            except:
                pass
        except Exception as e:
            logger.error(f"cb_tm_inbox task error uid={uid}: {e}")

    asyncio.create_task(_inbox_task())

async def cb_tm_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    if uid not in temp_mails:
        return await query.answer("тЭМ No email found", show_alert=True)
    addr = temp_mails[uid]["address"]
    await query.edit_message_text(
        f"ЁЯУз *Your Temp Email:*\n\n`{addr}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯУм Check Inbox", callback_data="tm_inbox", style="primary")],
            [InlineKeyboardButton("ЁЯФД New Email", callback_data="tm_create", style="success")],
        ])
    )

async def cb_tm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    temp_mails.pop(uid, None)
    save_temp_mails()
    await query.edit_message_text("тЬЕ *Email deleted.*", parse_mode="Markdown")

# тФАтФАтФА 2FA/TOTP тФАтФАтФА
async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    sess = get_session(str(update.effective_user.id))
    sess["state"] = None
    await update.message.reply_text(
        "ЁЯФР *2-Step Verification Code Generator*\n\nSelect a service:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯУШ Facebook 2FA", callback_data="totp:facebook", style="danger")],
            [InlineKeyboardButton("ЁЯУ╕ Instagram 2FA", callback_data="totp:instagram", style="primary")],
            [InlineKeyboardButton("ЁЯФН Google 2FA", callback_data="totp:google", style="success")],
            [InlineKeyboardButton("тЪЩя╕П Other 2FA", callback_data="totp:other", style="danger")],
        ])
    )

async def cb_totp_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    svc  = query.data.split(":", 1)[1]
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = "totp_waiting_secret"
    sess["data"]  = {"service": svc}

    if uid in users:
        users[uid]["pending_totp_svc"] = svc
        await async_save_users()

    icons = {"facebook": "ЁЯУШ", "instagram": "ЁЯУ╕", "google": "ЁЯФН", "other": "тЪЩя╕П"}
    names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "Other"}
    icon  = icons.get(svc, "ЁЯФР")
    name  = names.get(svc, svc)

    await query.edit_message_text(
        f"{icon} *{name} Secret Key*\n\n"
        f"Send your Authenticator Secret Key.\n\n"
        f"ЁЯФС It looks like: `JBSWY3DPEHPK3PXP`\n\n"
        f"Type /cancel to cancel",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="totp_back", style="primary")]])
    )

async def cb_totp_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "ЁЯФР *2FA Code Generator*\n\nSelect a service:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯУШ Facebook 2FA", callback_data="totp:facebook", style="success")],
            [InlineKeyboardButton("ЁЯУ╕ Instagram 2FA", callback_data="totp:instagram", style="danger")],
            [InlineKeyboardButton("ЁЯФН Google 2FA", callback_data="totp:google", style="primary")],
            [InlineKeyboardButton("тЪЩя╕П Other 2FA", callback_data="totp:other", style="success")],
        ])
    )

async def cb_totp_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ЁЯФД Refreshing...")
    _, svc, secret_enc = query.data.split(":", 2)

    if secret_enc == "TOOLONG":
        await query.edit_message_text(
            "тЪая╕П Secret key ржЯрж┐ ржЕржирзЗржХ ржмржбрж╝ред Refresh ржХрж░рждрзЗ ржЖржмрж╛рж░ ЁЯФР 2FA ржмрж╛ржЯржи ржЪрж╛ржкрзБржиред",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="totp_back", style="danger")]]))
        return

    secret = urllib.parse.unquote(secret_enc)
    result = generate_totp(secret)

    icons = {"facebook": "ЁЯУШ", "instagram": "ЁЯУ╕", "google": "ЁЯФН", "other": "тЪЩя╕П"}
    names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "2FA"}
    icon  = icons.get(svc, "ЁЯФР")
    name  = names.get(svc, svc)

    if not result:
        return await query.edit_message_text("тЭМ Invalid secret key.", parse_mode="Markdown")

    cb_data = f"totp_r:{svc}:{secret_enc}"

    try:
        await query.edit_message_text(
            f"{icon} *{name} 2FA Code*\n\n"
            f"ЁЯФС *Code:* `{result['token']}`\n\n"
            f"тП░ *{result['timeRemaining']} seconds remaining*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ЁЯФД Refresh Code", callback_data=cb_data, style="primary")],
                [InlineKeyboardButton("ЁЯФЩ Back", callback_data="totp_back", style="success")],
            ])
        )
    except:
        pass

# тФАтФАтФА Support тФАтФАтФА
async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ЁЯТм *Support*\n\nContact admin:\nЁЯУМ @sadhin8miya",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯТм Contact", url="https://t.me/sadhin8miya", style="danger")]])
    )

# тФАтФАтФА Admin Callbacks тФАтФАтФА
async def cb_admin_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    report = "ЁЯУК *Stock Report*\n\n"
    total_all = 0
    for cc, svcs in numbers_by_cs.items():
        country = countries.get(cc, {"flag": "ЁЯП┤", "name": cc})
        report += f"\n{country['flag']} {country['name']} (+{cc}):\n"
        ct = 0
        for svc_id, nums in svcs.items():
            svc = services.get(svc_id, {"icon": "ЁЯУЮ", "name": svc_id})
            if nums:
                report += f"  {svc['icon']} {svc['name']}: *{len(nums)}*\n"
                ct += len(nums)
        report += f"  *Total:* {ct}\n"
        total_all += ct

    report += f"\nЁЯУИ *Grand Total:* {total_all}\n"
    report += f"ЁЯСе *Active:* {len(active_numbers)}\n"
    report += f"ЁЯУи *OTPs:* {len(otp_log)}"

    if len(report) > 4000:
        report = report[:3950] + "\n..._truncated_"

    await safe_edit(query, report, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("ЁЯФД Refresh", callback_data="admin_stock", style="primary")],
        [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="success")],
    ]))

async def cb_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    try:
        total = len(users)
        total_referrals = sum(u.get("referralCount", 0) for u in users.values())
        msg   = (
            f"ЁЯСе *User Statistics*\n\n"
            f"тАв Total Users: {total}\n"
            f"тАв Active Numbers: {len(active_numbers)}\n"
            f"тАв OTPs Processed: {len(otp_log)}\n"
            f"тАв Total Referrals Made: {total_referrals}\n\n"
        )

        recent = sorted(users.values(), key=lambda u: u.get("last_active",""), reverse=True)[:10]
        for u in recent:
            uid_str  = u.get('id', '?')
            fname    = u.get('first_name', '').replace('*','').replace('_','').replace('`','')
            uname    = u.get('username', 'no_username').replace('_','\\_')
            msg += f"ЁЯСд *{fname}*\nЁЯЖФ `{uid_str}` | @{uname}\n"
            msg += f"ЁЯХР {get_time_ago(u.get('last_active', ''))}\n\n"

        if len(msg) > 4000:
            msg = msg[:3950] + "..._truncated_"

        await safe_edit(query, msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯФД Refresh", callback_data="admin_users", style="danger")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
        ]))
    except Exception as e:
        logger.error(f"cb_admin_users error: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                f"тЭМ *Error loading user stats*\n\n`{str(e)[:200]}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="success")]])
            )
        except:
            pass

async def cb_admin_otp_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    msg = "ЁЯУЛ *Recent OTP Logs*\n\n"
    if not otp_log:
        msg += "No OTPs yet."
    else:
        for log in otp_log[-10:][::-1]:
            msg += f"ЁЯУЮ `{log['phoneNumber']}` тЖТ ЁЯСд `{log['userId']}`\n"
            msg += f"ЁЯХР {get_time_ago(log.get('timestamp',''))}\n\n"

    await safe_edit(query, msg[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("ЁЯФД Refresh", callback_data="admin_otp_log", style="danger")],
        [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
    ]))

async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_broadcast"
    await query.edit_message_text(
        "ЁЯУв *Broadcast Message*\n\nSend the message to broadcast to all users:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    commission = settings.get("referralCommission", 10)
    await query.edit_message_text(
        f"тЪЩя╕П *Bot Settings*\n\n"
        f"ЁЯУЮ Number Count: *{settings['defaultNumberCount']}*\n"
        f"тП▒ Cooldown: *{settings['cooldownSeconds']} seconds*\n"
        f"ЁЯФР Verification: *{'Enabled тЬЕ' if settings['requireVerification'] else 'Disabled тЭМ'}*\n"
        f"ЁЯТ╡ OTP Price: *{settings.get('defaultOtpPrice', 0.25):.2f} taka*\n"
        f"ЁЯТ╕ Min Withdraw: *{settings['minWithdraw']} taka*\n"
        f"ЁЯПз Withdraw: *{'Enabled тЬЕ' if settings['withdrawEnabled'] else 'Disabled тЭМ'}*\n"
        f"ЁЯСе Referral Commission: *{commission}%*\n"
        f"ЁЯУб Panel Poll Interval: *{settings.get('panelPollInterval', 1)} sec*\n"
        f"ЁЯУе Queue Retry Interval: *{settings.get('queueRetryInterval', 1)} sec*\n"
        f"ЁЯЧСя╕П Queue Expiry: *{settings.get('queueExpiryHours', 3)} hours*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯУЮ Number Count", callback_data="as_count", style="danger"),
             InlineKeyboardButton("тП▒ Cooldown", callback_data="as_cooldown", style="primary")],
            [InlineKeyboardButton(f"ЁЯФР Verification {'Disable' if settings['requireVerification'] else 'Enable'}", callback_data="as_toggle_verify", style="success")],
            [InlineKeyboardButton("ЁЯТ╡ OTP Price", callback_data="as_price", style="danger"),
             InlineKeyboardButton("ЁЯТ╕ Min Withdraw", callback_data="as_minw", style="primary")],
            [InlineKeyboardButton(f"ЁЯПз Withdraw {'ЁЯФ┤ Disable' if settings['withdrawEnabled'] else 'ЁЯЯв Enable'}", callback_data="as_toggle_withdraw", style="success")],
            [InlineKeyboardButton(f"ЁЯСе Referral Commission ({commission}%)", callback_data="as_referral_commission", style="danger")],
            [InlineKeyboardButton("ЁЯУб Panel Poll Interval", callback_data="as_panel_interval", style="primary"),
             InlineKeyboardButton("ЁЯУе Queue Retry Interval", callback_data="as_queue_interval", style="success")],
            [InlineKeyboardButton("ЁЯЧСя╕П Queue Expiry (hours)", callback_data="as_queue_expiry", style="danger")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_admin_toggle_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    settings["requireVerification"] = not settings["requireVerification"]
    save_settings()
    await query.answer(f"тЬЕ Verification {'Enabled' if settings['requireVerification'] else 'Disabled'}")
    await cb_admin_settings(update, context)

async def cb_admin_toggle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    settings["withdrawEnabled"] = not settings["withdrawEnabled"]
    save_settings()
    await query.answer(f"тЬЕ Withdraw {'Enabled' if settings['withdrawEnabled'] else 'Disabled'}")
    await cb_admin_settings(update, context)

async def cb_as_referral_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_referral_commission"
    current = settings.get("referralCommission", 10)
    await query.edit_message_text(
        f"ЁЯСе *Set Referral Commission*\n\n"
        f"Current: *{current}%*\n\n"
        f"Send new commission percentage (0-50):\n"
        f"Example: `10` means 10%",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_panel_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_panel_interval"
    current = settings.get("panelPollInterval", 1)
    await query.edit_message_text(
        f"ЁЯУб *Set Panel Poll Interval*\n\n"
        f"Current: *{current} sec*\n\n"
        f"ржкрзНржпрж╛ржирзЗрж▓ ржХржд рж╕рзЗржХрзЗржирзНржб ржкрж░ржкрж░ ржирждрзБржи SMS/OTP ржЪрзЗржХ ржХрж░ржмрзЗ рж╕рзЗржЗ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ:\n"
        f"Example: `1`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_queue_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_queue_interval"
    current = settings.get("queueRetryInterval", 1)
    await query.edit_message_text(
        f"ЁЯУе *Set Queue Retry Interval*\n\n"
        f"Current: *{current} sec*\n\n"
        f"pending DM/Group queue ржХржд рж╕рзЗржХрзЗржирзНржб ржкрж░ржкрж░ ржЪрзЗржХ/ржлрзНрж▓рж╛рж╢ ржХрж░ржмрзЗ рж╕рзЗржЗ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ:\n"
        f"Example: `1`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_queue_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_queue_expiry"
    current = settings.get("queueExpiryHours", 3)
    await query.edit_message_text(
        f"ЁЯЧСя╕П *Set Queue Expiry*\n\n"
        f"Current: *{current} hours*\n\n"
        f"ржХрждржХрзНрж╖ржг (ржШржирзНржЯрж╛) ржЪрзЗрж╖рзНржЯрж╛ ржХрж░рж╛рж░ ржкрж░ржУ ржирж╛ ржЧрзЗрж▓рзЗ queue ржерзЗржХрзЗ entry ржмрж╛ржж ржжрж┐ржмрзЗ рж╕рзЗржЗ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ:\n"
        f"Example: `3`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_admin_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    commission = settings.get("referralCommission", 10)
    total_referrals = sum(u.get("referralCount", 0) for u in users.values())
    total_ref_earn  = sum(e.get("referralEarnings", 0) for e in earnings.values())

    msg = (
        f"ЁЯСе *Referral System Stats*\n\n"
        f"ЁЯУМ Commission Rate: *{commission}%*\n"
        f"ЁЯСе Total Referrals: *{total_referrals}*\n"
        f"ЁЯТ░ Total Commission Paid: *{total_ref_earn:.2f} taka*\n\n"
        f"ЁЯПЖ *Top Referrers:*\n"
    )

    top_ref = sorted(
        [(uid_k, u.get("referralCount", 0)) for uid_k, u in users.items()],
        key=lambda x: x[1], reverse=True
    )[:10]

    for r_uid, r_count in top_ref:
        if r_count == 0:
            continue
        r_user = users.get(r_uid, {})
        r_name = r_user.get("first_name", "User").replace("*", "").replace("_", "")
        r_earn = earnings.get(r_uid, {}).get("referralEarnings", 0)
        msg += f"  ЁЯСд {r_name} | {r_count} referrals | {r_earn:.2f} taka\n"

    if len(msg) > 4000:
        msg = msg[:3950] + "\n..._truncated_"

    await query.edit_message_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"тЪЩя╕П Set Commission ({commission}%)", callback_data="as_referral_commission", style="danger")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_as_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_count"
    await query.edit_message_text(
        f"ЁЯУЮ *Set Number Count*\n\nCurrent: *{settings['defaultNumberCount']}*\n\nSend new count (1-100):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_cooldown"
    await query.edit_message_text(
        f"тП▒ *Set Cooldown*\n\nCurrent: *{settings['cooldownSeconds']} seconds*\n\nSend new cooldown (1-3600):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_as_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_price"
    await query.edit_message_text(
        f"ЁЯТ╡ *Set Default OTP Price*\n\nCurrent: *{settings.get('defaultOtpPrice', 0.25):.2f} taka*\n\nSend new price:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="primary")]])
    )

async def cb_as_minw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_minw"
    await query.edit_message_text(
        f"ЁЯТ╕ *Set Min Withdraw*\n\nCurrent: *{settings['minWithdraw']} taka*\n\nSend new minimum:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_admin_add_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_add_numbers"
    await query.edit_message_text(
        "тЮХ *Add Numbers*\n\nFormat:\n`[number]|[country code]|[service]`\n\nExample:\n`8801712345678|880|whatsapp`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    pending = [w for w in withdrawals if w["status"] == "pending"]
    msg = f"ЁЯТ╕ *Pending Withdrawals:* {len(pending)}\n\n"

    for w in pending[:10]:
        msg += f"ЁЯЖФ `{w['id'][-8:]}`\n"
        msg += f"ЁЯСд {w.get('userName','')} | ЁЯТ╡ {w['amount']:.2f} taka\n"
        msg += f"ЁЯУ▒ {w['method']}: `{w['account']}`\n\n"

    buttons = []
    for w in pending[:5]:
        buttons.append([
            InlineKeyboardButton(f"тЬЕ {w['id'][-6:]}", callback_data=f"wadm_approve:{w['id']}", style="primary"),
            InlineKeyboardButton(f"тЭМ {w['id'][-6:]}", callback_data=f"wadm_reject:{w['id']}", style="success"),
        ])
    buttons.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="danger")])

    await query.edit_message_text(msg[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_withdraw_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    wid = query.data.split(":", 1)[1]
    for w in withdrawals:
        if w["id"] == wid:
            w["status"] = "approved"
            w["processedAt"] = datetime.now().isoformat()
            await async_save_withdrawals()
            await query.answer("тЬЕ Approved!")
            try:
                await context.bot.send_message(w["userId"],
                    f"тЬЕ *Withdrawal Approved!*\n\nЁЯТ╡ {w['amount']:.2f} taka тЖТ {w['method']}: `{w['account']}`",
                    parse_mode="Markdown")
            except:
                pass
            break
    await cb_admin_withdrawals(update, context)

async def cb_withdraw_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    wid = query.data.split(":", 1)[1]
    for w in withdrawals:
        if w["id"] == wid:
            w["status"] = "rejected"
            w["processedAt"] = datetime.now().isoformat()
            e = get_user_earnings(w["userId"])
            e["balance"] = round(e["balance"] + w["amount"], 2)
            await async_save_earnings()
            await async_save_withdrawals()
            await query.answer("тЭМ Rejected!")
            try:
                await context.bot.send_message(w["userId"],
                    f"тЭМ *Withdrawal Rejected.*\n\nЁЯТ╡ {w['amount']:.2f} taka refunded.",
                    parse_mode="Markdown")
            except:
                pass
            break
    await cb_admin_withdrawals(update, context)

async def cb_admin_balance_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    await query.edit_message_text(
        "ЁЯСЫ *Balance Management*\n\nSelect action:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("тЮХ Add Balance", callback_data="bal_add", style="primary"),
             InlineKeyboardButton("тЮЦ Deduct Balance", callback_data="bal_deduct", style="success")],
            [InlineKeyboardButton("ЁЯФД Reset Balance", callback_data="bal_reset", style="danger")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_bal_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_add_balance"
    await query.edit_message_text(
        "тЮХ *Add Balance*\n\nFormat: `[userId] [amount]`\nExample: `123456789 50`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_bal_deduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_deduct_balance"
    await query.edit_message_text(
        "тЮЦ *Deduct Balance*\n\nFormat: `[userId] [amount]`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_bal_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_reset_balance"
    await query.edit_message_text(
        "ЁЯФД *Reset Balance*\n\nSend the userId:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="primary")]])
    )

async def cb_admin_country_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_country_price"
    text = "ЁЯТ░ *Country Prices*\n\nCurrent prices:\n"
    for cc, c in countries.items():
        p = country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))
        text += f"{c['flag']} +{cc}: *{p:.2f} TK*\n"
    text += "\nSend new prices (format: `880 0.50`):"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")]]))

async def cb_admin_manage_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    await query.edit_message_text(
        f"ЁЯМН *Manage Countries*\n\nTotal: *{len(countries)}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("тЮХ Add Country", callback_data="country_add", style="danger"),
             InlineKeyboardButton("ЁЯУЛ List Countries", callback_data="country_list", style="primary")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="success")],
        ])
    )

async def cb_country_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "ЁЯМН *Country List*\n\n"
    for cc, c in countries.items():
        p = country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))
        text += f"{c['flag']} *{c['name']}* (+{cc}) тАФ {p:.2f} TK/OTP\n"
    await query.edit_message_text(text[:4000], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_manage_countries", style="danger")]]))

async def cb_country_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "admin_add_country"
    await query.edit_message_text(
        "ЁЯМН *Add Country*\n\nFormat: `[code] [name] [flag]`\nExample: `880 Bangladesh ЁЯЗзЁЯЗй`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="primary")]])
    )

async def cb_admin_manage_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    await query.edit_message_text(
        "ЁЯФз *Manage Services*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯУЛ List Services", callback_data="svc_list", style="success"),
             InlineKeyboardButton("тЮХ Add Service", callback_data="svc_add", style="danger")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_svc_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "ЁЯУЛ *Services List*\n\n"
    for svc_id, svc in services.items():
        text += f"тАв {svc['icon']} *{svc['name']}* (ID: `{svc_id}`)\n"
    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_manage_services", style="success")]]))

async def cb_svc_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "admin_add_service"
    await query.edit_message_text(
        "ЁЯФз *Add Service*\n\nFormat: `[id] [name] [icon]`\nExample: `facebook Facebook ЁЯУШ`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_upload_select_service"

    buttons = [[InlineKeyboardButton(f"{svc['icon']} {svc['name']}", callback_data=f"upload_svc:{svc_id}", style="primary")]
               for svc_id, svc in services.items()]
    buttons.append([InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="success")])
    await query.edit_message_text("ЁЯУд *Upload Numbers*\n\nSelect service:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_upload_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    svc    = services.get(svc_id, {"name": svc_id})
    sess   = get_session(uid)
    sess["state"] = "admin_upload_file"
    sess["data"]  = {"serviceId": svc_id}
    await query.edit_message_text(
        f"ЁЯУд *Upload Numbers for {svc['name']}*\n\nSend a .txt file with numbers (one per line).",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = None
    get_session(uid)["data"]  = None
    await query.edit_message_text("ЁЯЫа *Admin Dashboard*\n\nSelect an option:", parse_mode="Markdown", reply_markup=admin_keyboard())

async def cb_admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = None
    get_session(uid)["data"]  = None
    await query.edit_message_text("тЭМ *Cancelled.*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯЫа Back to Admin", callback_data="admin_back", style="primary")]]))

async def cb_admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    sess = get_session(uid)
    sess["is_admin"] = False
    sess["state"]    = None
    await query.edit_message_text("ЁЯЪк *Admin Logged Out.*", parse_mode="Markdown")

async def cb_admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    buttons = []
    for cc, svcs in numbers_by_cs.items():
        for svc_id, nums in svcs.items():
            if nums:
                buttons.append([InlineKeyboardButton(
                    f"ЁЯЧСя╕П +{cc}/{svc_id} ({len(nums)})",
                    callback_data=f"del_confirm:{cc}:{svc_id}", style="primary"
                )])
    buttons.append([InlineKeyboardButton("тЭМ Cancel", callback_data="admin_back", style="success")])
    await query.edit_message_text("ЁЯЧСя╕П *Delete Numbers*\n\nSelect to delete:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    _, cc, svc_id = query.data.split(":")
    count = len(numbers_by_cs.get(cc, {}).get(svc_id, []))
    await query.edit_message_text(
        f"тЪая╕П *Confirm Deletion*\n\nDelete {count} numbers from +{cc}/{svc_id}?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("тЬЕ Yes", callback_data=f"del_exec:{cc}:{svc_id}", style="danger"),
             InlineKeyboardButton("тЭМ No", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_del_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    _, cc, svc_id = query.data.split(":")
    count = len(numbers_by_cs.get(cc, {}).get(svc_id, []))
    if cc in numbers_by_cs and svc_id in numbers_by_cs[cc]:
        del numbers_by_cs[cc][svc_id]
        if not numbers_by_cs[cc]:
            del numbers_by_cs[cc]
    await async_save_numbers()
    await query.edit_message_text(f"тЬЕ *Deleted {count} numbers.*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="success")]]))

async def cb_goto_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("тЬЕ Done.", parse_mode="Markdown")

# тФАтФАтФА Document Handler тФАтФАтФА
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    sess = get_session(uid)

    if sess.get("state") == "admin_fake_numbers":
        doc   = update.message.document
        fname = (doc.file_name or "").lower()
        if not (fname.endswith(".txt") or fname.endswith(".xlsx") or fname.endswith(".xls") or fname.endswith(".csv")):
            return await update.message.reply_text("тЭМ рж╢рзБржзрзБ .txt, .csv ржмрж╛ .xlsx/.xls ржлрж╛ржЗрж▓ рж╕рж╛ржкрзЛрж░рзНржЯ ржХрж░рзЗ ржПржЦрж╛ржирзЗред")
        file = await context.bot.get_file(doc.file_id)
        raw  = await file.download_as_bytearray()

        numbers = []
        if fname.endswith(".xlsx") or fname.endswith(".xls"):
            try:
                import openpyxl, io
                wb = openpyxl.load_workbook(io.BytesIO(bytes(raw)), read_only=True, data_only=True)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if cell is None:
                            continue
                        num = re.sub(r"\D", "", str(cell))
                        if re.match(r"^\d{10,15}$", num) and num not in numbers:
                            numbers.append(num)
            except Exception as e:
                return await update.message.reply_text(f"тЭМ Excel ржлрж╛ржЗрж▓ ржкржбрж╝рждрзЗ рж╕ржорж╕рзНржпрж╛ рж╣ржпрж╝рзЗржЫрзЗ: {e}")
        elif fname.endswith(".csv"):
            import csv, io
            text = bytes(raw).decode("utf-8", errors="ignore")
            for row in csv.reader(io.StringIO(text)):
                for cell in row:
                    num = re.sub(r"\D", "", str(cell))
                    if re.match(r"^\d{10,15}$", num) and num not in numbers:
                        numbers.append(num)
        else:
            text = bytes(raw).decode("utf-8", errors="ignore")
            for line in text.split("\n"):
                num = re.sub(r"\D", "", line.strip())
                if num and num not in numbers:
                    numbers.append(num)

        sess["state"] = None
        fd = sess.pop("fake_data", {})
        if not numbers:
            sess["state"] = "admin_fake_numbers"
            sess["fake_data"] = fd
            return await update.message.reply_text("тЭМ ржлрж╛ржЗрж▓рзЗ ржХрзЛржирзЛ ржнрзНржпрж╛рж▓рж┐ржб ржирж╛ржорзНржмрж╛рж░ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред ржЖржмрж╛рж░ ржкрж╛ржарж╛ржУред")

        batch = {
            "numbers":     numbers,
            "service":     fd.get("service", "other"),
            "digits":      fd.get("digits", 5),
            "max_minutes": fd.get("max_minutes", 5),
            "status":      "running",
        }
        fake_otp_batches.append(batch)
        save_fake_otp_batches()
        idx = len(fake_otp_batches) - 1
        fake_otp_tasks[idx] = asyncio.create_task(run_fake_otp_batch(idx, context.application))

        svc = services.get(batch["service"], {"icon": "ЁЯУ▒", "name": batch["service"]})
        return await update.message.reply_text(
            f"тЬЕ *Fake OTP Batch #{idx+1} Added & Started!*\n\n"
            f"{svc['icon']} Service: {svc['name']}\n"
            f"ЁЯФв Digits: {batch['digits']}\n"
            f"тП▒ Max Gap: {batch['max_minutes']} min\n"
            f"ЁЯУЛ Numbers: {len(numbers)}ржЯрж╛ (ржлрж╛ржЗрж▓ ржерзЗржХрзЗ)",
            parse_mode="Markdown"
        )

    if sess.get("state") != "admin_upload_file":
        return

    doc   = update.message.document
    fname = (doc.file_name or "").lower()

    if not (fname.endswith(".txt") or fname.endswith(".xlsx") or fname.endswith(".xls") or fname.endswith(".csv")):
        return await update.message.reply_text("тЭМ Only .txt, .csv or .xlsx files are supported.")

    svc_id = (sess.get("data") or {}).get("serviceId", "other")
    added  = 0
    file   = await context.bot.get_file(doc.file_id)

    if fname.endswith(".xlsx") or fname.endswith(".xls"):
        try:
            import openpyxl, io
            raw = await file.download_as_bytearray()
            wb  = openpyxl.load_workbook(io.BytesIO(bytes(raw)), read_only=True, data_only=True)
            ws  = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                for cell in row:
                    if cell is None:
                        continue
                    num = re.sub(r"\D", "", str(cell))
                    if not re.match(r"^\d{10,15}$", num):
                        continue
                    cc = get_country_code_from_number(num)
                    if not cc:
                        continue
                    numbers_by_cs.setdefault(cc, {}).setdefault(svc_id, [])
                    if num not in numbers_by_cs[cc][svc_id]:
                        numbers_by_cs[cc][svc_id].append(num)
                        added += 1
                    break
        except Exception as e:
            logger.error(f"XLSX parse error: {e}")
            return await update.message.reply_text(f"тЭМ Excel file read error: {e}")
    elif fname.endswith(".csv"):
        import csv, io
        raw  = await file.download_as_bytearray()
        text = bytes(raw).decode("utf-8", errors="ignore")
        for i, row in enumerate(csv.reader(io.StringIO(text))):
            if i == 0:
                continue  # header row skip (xlsx ржПрж░ ржорждрзЛржЗ)
            for cell in row:
                num = re.sub(r"\D", "", str(cell))
                if not re.match(r"^\d{10,15}$", num):
                    continue
                cc = get_country_code_from_number(num)
                if not cc:
                    continue
                numbers_by_cs.setdefault(cc, {}).setdefault(svc_id, [])
                if num not in numbers_by_cs[cc][svc_id]:
                    numbers_by_cs[cc][svc_id].append(num)
                    added += 1
                break
    else:
        raw_content = await file.download_as_bytearray()
        lines = raw_content.decode("utf-8", errors="ignore").split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                parts = line.split("|")
                num = parts[0].strip()
                cc  = parts[1].strip() if len(parts) > 1 else get_country_code_from_number(num)
                svc = parts[2].strip() if len(parts) > 2 else svc_id
            else:
                num = re.sub(r"\D", "", line)
                cc  = get_country_code_from_number(num)
                svc = svc_id
            if not re.match(r"^\d{10,15}$", num) or not cc:
                continue
            numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
            if num not in numbers_by_cs[cc][svc]:
                numbers_by_cs[cc][svc].append(num)
                added += 1

    await async_save_numbers()
    sess["state"] = None
    sess["data"]  = None
    await update.message.reply_text(f"тЬЕ *{added} numbers uploaded successfully!*", parse_mode="Markdown")

# тФАтФАтФА Main Text Handler тФАтФАтФА
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    uid  = str(user.id)
    text = update.message.text.strip()

    if uid not in users:
        users[uid] = {
            "id": uid, "username": user.username or "no_username",
            "first_name": user.first_name or "User", "last_name": user.last_name or "",
            "joined": datetime.now().isoformat(), "last_active": datetime.now().isoformat(),
            "verified": False, "referredBy": None, "referralCount": 0,
        }
    users[uid]["last_active"] = datetime.now().isoformat()
    await async_save_users()

    sess = get_session(uid)
    if not sess.get("is_admin") and is_admin(uid):
        sess["is_admin"] = True
    state = sess.get("state")

    if state in ("pe_set", "pe_bulk") and (sess.get("is_admin") or is_admin(uid)):
        return await _pe_receive(update, sess)

    if state == "wa_waiting_number":
        sess["state"] = None
        phone = re.sub(r"\D", "", text)
        if len(phone) < 10 or len(phone) > 15:
            return await update.message.reply_text("тЭМ Invalid number. Example: `8801712345678`", parse_mode="Markdown")

        loading = await update.message.reply_text(
            "тП│ *Pairing code ржирж┐ржЪрзНржЫрзЗ...*\n\nтМЫ ржХржпрж╝рзЗржХ рж╕рзЗржХрзЗржирзНржб ржЕржкрзЗржХрзНрж╖рж╛ ржХрж░рзЛред",
            parse_mode="Markdown"
        )

        async def wa_task():
            try:
                # ржЖржЧрзЗ check ржХрж░рзЛ connected ржХрж┐ржирж╛
                current_state = await green_get_state(uid)
                if current_state == "authorized":
                    wa_sessions[uid] = {"connected": True}
                    try: await loading.delete()
                    except: pass
                    await context.bot.send_message(
                        uid,
                        "тЬЕ *WhatsApp Already Connected!*\n\n"
                        "ЁЯЯв рждрзЛржорж╛рж░ WhatsApp ржЗрждрж┐ржоржзрзНржпрзЗ connected ржЖржЫрзЗред",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("ЁЯФ┤ Logout / Disconnect", callback_data="wa_disconnect", style="danger")],
                            [InlineKeyboardButton("ЁЯУК Check Status", callback_data="wa_status", style="primary")],
                        ])
                    )
                    return

                code = await get_wa_pairing_code(phone, uid)
                clean_code = re.sub(r"[^A-Z0-9]", "", code.upper())
                formatted = (clean_code[:4] + "-" + clean_code[4:8]) if len(clean_code) >= 8 else code
                try: await loading.delete()
                except: pass
                await context.bot.send_message(
                    uid,
                    f"ЁЯФС *Pairing Code*\n\n"
                    f"`{formatted}`\n\n"
                    f"ЁЯУЛ *Steps:*\n"
                    f"1. WhatsApp ржЦрзЛрж▓рзЛ\n"
                    f"2. Settings тЖТ Linked Devices\n"
                    f"3. Link a Device тЖТ *Link with phone number*\n"
                    f"4. ржЙржкрж░рзЗрж░ code enter ржХрж░рзЛ\n\n"
                    f"тЬЕ Code enter ржХрж░рж╛рж░ ржкрж░ *Check Status* ржЪрж╛ржкрзЛред",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("тЬЕ Check Status", callback_data="wa_status", style="danger")],
                        [InlineKeyboardButton("ЁЯФД New Code", callback_data="wa_connect", style="primary")],
                    ])
                )
                asyncio.create_task(monitor_wa_connection(uid, context))
            except Exception as e:
                try: await loading.delete()
                except: pass
                logger.error(f"WA error: {e}", exc_info=True)
                await context.bot.send_message(
                    uid,
                    f"тЭМ *Connection failed:* {str(e)[:150]}\n\nржХрж┐ржЫрзБржХрзНрж╖ржг ржкрж░ ржЖржмрж╛рж░ try ржХрж░рзЛред",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФД Try Again", callback_data="wa_connect", style="success")]])
                )

        asyncio.create_task(wa_task())
        return

    pending_totp_svc = users.get(uid, {}).get("pending_totp_svc")
    if state == "totp_waiting_secret" or pending_totp_svc:
        sess["state"] = None
        svc = (sess.get("data") or {}).get("service") or pending_totp_svc or "other"

        if uid in users and "pending_totp_svc" in users[uid]:
            del users[uid]["pending_totp_svc"]
            await async_save_users()

        try:
            result = generate_totp(text)
        except Exception as e:
            logger.error(f"TOTP exception uid={uid}: {e}")
            result = None

        if not result:
            await update.message.reply_text(
                "тЭМ *Invalid secret key!*\n\n"
                "Key ржЯрж┐ рж╕ржарж┐ржХ ржиржпрж╝ред Authenticator app ржерзЗржХрзЗ exact secret key copy ржХрж░рзЛред\n"
                "Example format: `JBSWY3DPEHPK3PXP`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ЁЯФД Try Again", callback_data=f"totp:{svc}", style="danger")],
                    [InlineKeyboardButton("ЁЯФЩ Back", callback_data="totp_back", style="primary")],
                ])
            )
            return

        icons = {"facebook": "ЁЯУШ", "instagram": "ЁЯУ╕", "google": "ЁЯФН", "other": "тЪЩя╕П"}
        names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "2FA"}
        icon  = icons.get(svc, "ЁЯФР")
        name  = names.get(svc, svc)

        secret_quoted = urllib.parse.quote(text)
        cb_data = f"totp_r:{svc}:{secret_quoted}"
        if len(cb_data.encode()) > 62:
            cb_data = f"totp_r:{svc}:TOOLONG"

        try:
            await update.message.reply_text(
                f"{icon} *{name} 2FA Code*\n\n"
                f"ЁЯФС *Code:* `{result['token']}`\n\n"
                f"тП░ *{result['timeRemaining']} seconds remaining*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ЁЯФД Refresh Code", callback_data=cb_data, style="success")],
                    [InlineKeyboardButton("ЁЯФЩ Back", callback_data="totp_back", style="danger")],
                ])
            )
        except Exception as e:
            logger.error(f"TOTP reply error uid={uid}: {e}")
            await update.message.reply_text(f"тЬЕ 2FA Code: {result['token']} (тП░ {result['timeRemaining']}s)")
        return

    if state == "w_account":
        sess["state"] = None
        data   = sess.get("data", {})
        method = data.get("method", "bKash")
        amount = data.get("amount", 0)
        e      = get_user_earnings(uid)

        if amount > e["balance"]:
            return await update.message.reply_text("тЭМ Insufficient balance!")

        icon = "ЁЯЯг" if method == "bKash" else "ЁЯЯа"
        sess["state"] = "w_confirm"
        sess["data"]  = {"method": method, "amount": amount, "account": text}

        await update.message.reply_text(
            f"{icon} *Confirm Withdrawal*\n\n"
            f"ЁЯТ│ Method: {method}\n"
            f"ЁЯУ▒ Account: `{text}`\n"
            f"ЁЯТ╡ Amount: *{amount:.2f} taka*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("тЬЕ Confirm", callback_data="w_confirm", style="primary"),
                 InlineKeyboardButton("тЭМ Cancel", callback_data="w_cancel", style="success")],
            ])
        )
        return

    if state == "admin_set_referral_commission" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if 0 <= val <= 50:
                settings["referralCommission"] = val
                save_settings()
                await update.message.reply_text(
                    f"тЬЕ *Referral commission set to {val:.1f}%*\n\n"
                    f"ржПржЦржи ржерзЗржХрзЗ ржкрзНрж░рждрж┐ OTP ржПрж░ {val:.1f}% commission referrer ржкрж╛ржмрзЗред",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("тЭМ 0 ржерзЗржХрзЗ 50 ржПрж░ ржоржзрзНржпрзЗ ржжрж╛ржУред")
        except:
            await update.message.reply_text("тЭМ Invalid number. Example: `10`", parse_mode="Markdown")
        return

    if state == "admin_set_panel_interval" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["panelPollInterval"] = val
                save_settings()
                await update.message.reply_text(
                    f"тЬЕ *Panel Poll Interval set to {val} sec*\n\n"
                    f"ржПржЦржи ржерзЗржХрзЗ ржкрзНрж░рждрж┐ржЯрж╛ ржкрзНржпрж╛ржирзЗрж▓ ржкрзНрж░рждрж┐ {val} рж╕рзЗржХрзЗржирзНржб ржкрж░ржкрж░ ржирждрзБржи SMS/OTP ржЪрзЗржХ ржХрж░ржмрзЗред",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("тЭМ 0 ржПрж░ ржмрзЗрж╢рж┐ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУред")
        except:
            await update.message.reply_text("тЭМ Invalid number. Example: `1`", parse_mode="Markdown")
        return

    if state == "admin_set_queue_interval" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["queueRetryInterval"] = val
                save_settings()
                await update.message.reply_text(
                    f"тЬЕ *Queue Retry Interval set to {val} sec*\n\n"
                    f"ржПржЦржи ржерзЗржХрзЗ pending DM/Group queue ржкрзНрж░рждрж┐ {val} рж╕рзЗржХрзЗржирзНржб ржкрж░ржкрж░ ржЪрзЗржХ рж╣ржмрзЗред",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("тЭМ 0 ржПрж░ ржмрзЗрж╢рж┐ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУред")
        except:
            await update.message.reply_text("тЭМ Invalid number. Example: `1`", parse_mode="Markdown")
        return

    if state == "admin_set_queue_expiry" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["queueExpiryHours"] = val
                save_settings()
                await update.message.reply_text(
                    f"тЬЕ *Queue Expiry set to {val} hours*\n\n"
                    f"ржПржЦржи ржерзЗржХрзЗ {val} ржШржирзНржЯрж╛рж░ ржмрзЗрж╢рж┐ ржкрзБрж░ржирзЛ pending entry queue ржерзЗржХрзЗ ржмрж╛ржж ржкржбрж╝рзЗ ржпрж╛ржмрзЗред",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("тЭМ 0 ржПрж░ ржмрзЗрж╢рж┐ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУред")
        except:
            await update.message.reply_text("тЭМ Invalid number. Example: `3`", parse_mode="Markdown")
        return

    if state == "global_wa_phone" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        phone = re.sub(r"\D", "", text.strip())
        if len(phone) < 8:
            return await update.message.reply_text("тЭМ ржиржорзНржмрж░ ржнрзБрж▓!")
        loading = await update.message.reply_text("тП│ Connecting Global WhatsApp...")
        try:
            code = await get_wa_pairing_code(phone, f"global_{uid}")
            if not code:
                await loading.delete()
                return await update.message.reply_text("тЭМ Pairing code ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред")
            global_wa_data["phone"]     = phone
            global_wa_data["uid"]       = f"global_{uid}"
            global_wa_data["connected"] = False
            save_global_wa()
            await loading.delete()
            await update.message.reply_text(
                f"ЁЯУ▒ *Global WhatsApp Pairing Code:*\n\n"
                f"`{code}`\n\n"
                f"WhatsApp тЖТ Linked Devices тЖТ Link a Device тЖТ Enter code",
                parse_mode="Markdown"
            )
            # verify loop
            async def verify_global_wa():
                for _ in range(20):
                    await asyncio.sleep(15)
                    state_check = await green_get_state(f"global_{uid}")
                    if state_check == "authorized":
                        wa_sessions[f"global_{uid}"] = {"connected": True}
                        global_wa_data["connected"] = True
                        global_wa_data["enabled"]   = True
                        save_global_wa()
                        try:
                            await context.bot.send_message(
                                int(uid),
                                "тЬЕ *Global WhatsApp Connected!*\n\n"
                                "ржПржЦржи рж╕ржм user ржПрж░ number ржПржЗ WA ржжрж┐ржпрж╝рзЗ check рж╣ржмрзЗред",
                                parse_mode="Markdown"
                            )
                        except: pass
                        return
            asyncio.create_task(verify_global_wa())
        except Exception as e:
            await loading.delete()
            await update.message.reply_text(f"тЭМ Error: {e}")
        return

    if state == "admin_add_panel" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.strip().split()
        if len(parts) != 3:
            return await update.message.reply_text("тЭМ Format ржнрзБрж▓!\n`URL username password`", parse_mode="Markdown")
        url, username, password = parts
        ptype  = sess.pop("panel_type", "masdar_client")
        panels = load_panels()
        panels.append({"url": url, "username": username, "password": password, "type": ptype})
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        label = PANEL_TYPE_LABEL.get(ptype, ptype)
        await update.message.reply_text(
            f"тЬЕ *Panel Added & Started!*\n\nЁЯФЧ `{url}`\nЁЯСд `{username}`\nЁЯП╖я╕П {label}",
            parse_mode="Markdown"
        )
        return

    # тФАтФА Provider 2: ржзрж╛ржкрзЗ ржзрж╛ржкрзЗ рж╕рзЗржЯржЖржк (Login URL тЖТ SMS URL тЖТ Username тЖТ Password тЖТ Number Col тЖТ Message Col) тФАтФА
    if state == "admin_add_p2_loginurl" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["login_url"] = text.strip()
        sess["state"] = "admin_add_p2_smsurl"
        await update.message.reply_text(
            "тЮХ *Add Provider 2 Panel тАФ Step 2/6*\n\n"
            "ЁЯУД *SMS URL* ржжрж┐ржи (panel-ржПрж░ ржпрзЗ page-ржП SMS/OTP list ржжрзЗржЦрж╛ ржпрж╛ржпрж╝):\n\n"
            "Example:\n`http://139.99.69.196/client/SMSCDRStats`",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_smsurl" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["sms_url"] = text.strip()
        sess["state"] = "admin_add_p2_username"
        await update.message.reply_text(
            "тЮХ *Add Provider 2 Panel тАФ Step 3/6*\n\nЁЯСд *Username* ржжрж┐ржи:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_username" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["username"] = text.strip()
        sess["state"] = "admin_add_p2_password"
        await update.message.reply_text(
            "тЮХ *Add Provider 2 Panel тАФ Step 4/6*\n\nЁЯФС *Password* ржжрж┐ржи:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_password" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["password"] = text.strip()
        sess["state"] = "admin_add_p2_numcol"
        await update.message.reply_text(
            "тЮХ *Add Provider 2 Panel тАФ Step 5/6*\n\n"
            "ЁЯФв Panel-ржП ржЧрж┐ржпрж╝рзЗ ржжрзЗржЦрзЛ *Number* ржХрзЛржи ржХрж▓рж╛ржорзЗ ржЖржЫрзЗ (ржпрзЗржоржи 2), рж╕рзЗржЗ рж╕ржВржЦрзНржпрж╛ржЯрж╛ ржжрж╛ржУ:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_numcol" and (sess["is_admin"] or is_admin(uid)):
        try:
            sess["p2_data"]["num_col_idx"] = int(text.strip())
        except ValueError:
            return await update.message.reply_text("тЭМ рж╢рзБржзрзБ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ, ржпрзЗржоржи: `2`")
        sess["state"] = "admin_add_p2_msgcol"
        await update.message.reply_text(
            "тЮХ *Add Provider 2 Panel тАФ Step 6/6*\n\n"
            "ЁЯТм *Message/SMS* ржХрзЛржи ржХрж▓рж╛ржорзЗ ржЖржЫрзЗ (ржпрзЗржоржи 3), рж╕рзЗржЗ рж╕ржВржЦрзНржпрж╛ржЯрж╛ ржжрж╛ржУ:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_msgcol" and (sess["is_admin"] or is_admin(uid)):
        try:
            msg_col_idx = int(text.strip())
        except ValueError:
            return await update.message.reply_text("тЭМ рж╢рзБржзрзБ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ, ржпрзЗржоржи: `3`")
        sess["state"] = None
        p2 = sess.pop("p2_data", {})
        p2["msg_col_idx"] = msg_col_idx
        panel_data = {
            "url":         p2["login_url"],
            "sms_url":     p2["sms_url"],
            "username":    p2["username"],
            "password":    p2["password"],
            "type":        "provider2",
            "num_col_idx": p2["num_col_idx"],
            "msg_col_idx": p2["msg_col_idx"],
        }
        panels = load_panels()
        panels.append(panel_data)
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        await update.message.reply_text(
            f"тЬЕ *Provider 2 Panel Added & Started!*\n\n"
            f"ЁЯФЧ Login: `{panel_data['url']}`\n"
            f"ЁЯУД SMS URL: `{panel_data['sms_url']}`\n"
            f"ЁЯСд `{panel_data['username']}`\n"
            f"ЁЯФв Number Col: {panel_data['num_col_idx']} | Msg Col: {panel_data['msg_col_idx']}",
            parse_mode="Markdown"
        )
        return

    # тФАтФА Provider 3: ржзрж╛ржкрзЗ ржзрж╛ржкрзЗ (URL тЖТ Username тЖТ Password) тФАтФА
    if state == "admin_add_p3_url" and (sess["is_admin"] or is_admin(uid)):
        sess["p3_data"]["url"] = text.strip()
        sess["state"] = "admin_add_p3_username"
        subtype = sess["p3_data"].get("subtype", "ints")
        await update.message.reply_text(
            f"ЁЯзй *Add Provider 3 ({subtype}) тАФ Step 2/3*\n\nЁЯСд *Username* ржжрж┐ржи:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p3_username" and (sess["is_admin"] or is_admin(uid)):
        sess["p3_data"]["username"] = text.strip()
        sess["state"] = "admin_add_p3_password"
        subtype = sess["p3_data"].get("subtype", "ints")
        await update.message.reply_text(
            f"ЁЯзй *Add Provider 3 ({subtype}) тАФ Step 3/3*\n\nЁЯФС *Password* ржжрж┐ржи:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p3_password" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        p3 = sess.pop("p3_data", {})
        p3["password"] = text.strip()
        panel_data = {
            "url":      p3["url"],
            "username": p3["username"],
            "password": p3["password"],
            "type":     "provider3",
            "subtype":  p3.get("subtype", "ints"),
        }
        panels = load_panels()
        panels.append(panel_data)
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        await update.message.reply_text(
            f"тЬЕ *Provider 3 ({panel_data['subtype']}) Panel Added & Started!*\n\n"
            f"ЁЯФЧ `{panel_data['url']}`\n"
            f"ЁЯСд `{panel_data['username']}`",
            parse_mode="Markdown"
        )
        return

    # тФАтФА Provider 4: Base URL тЖТ API Token тФАтФА
    if state == "admin_add_p4_url" and (sess["is_admin"] or is_admin(uid)):
        sess["p4_data"]["url"] = text.strip()
        sess["state"] = "admin_add_p4_token"
        await update.message.reply_text(
            "ЁЯМР *Add Provider 4 тАФ Step 2/2*\n\n"
            "ЁЯФС *API Token* ржжрж┐ржи (Power SMS Panel ржПрж░ Profile/Agent API ржкрзЗржЬ ржерзЗржХрзЗ):",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p4_token" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        p4 = sess.pop("p4_data", {})
        panel_data = {
            "url":      p4["url"],
            "username": "api",
            "password": text.strip(),   # API token ржЯрж╛ password field ржП рж░рж╛ржЦрж╛ рж╣ржпрж╝
            "type":     "provider4",
        }
        panels = load_panels()
        panels.append(panel_data)
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        await update.message.reply_text(
            f"тЬЕ *Provider 4 (API) Panel Added & Started!*\n\n"
            f"ЁЯФЧ `{panel_data['url']}`",
            parse_mode="Markdown"
        )
        return

    # тФАтФА Provider 5: Target URL тЖТ Target Host тЖТ Session Cookie тФАтФА
    # тФАтФА Provider 5: ржкрзБрж░рзЛ raw HTTP request ржмрзНрж▓ржХ ржПржХ ржзрж╛ржкрзЗржЗ ржкрж╛рж░рзНрж╕ рж╣ржпрж╝ тФАтФА
    if state == "admin_add_p5_raw" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parsed = _parse_raw_http_request(text)
        if not parsed:
            sess["state"] = "admin_add_p5_raw"  # ржЖржмрж╛рж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░рж╛рж░ рж╕рзБржпрзЛржЧ ржжрж╛ржУ
            return await update.message.reply_text(
                "тЭМ Request ржмрзНрж▓ржХржЯрж╛ ржмрзБржЭрждрзЗ ржкрж╛рж░рж┐ржирж┐ред ржирж┐рж╢рзНржЪрж┐ржд ржХрж░рзЛ ржпрзЗ ржкрзНрж░ржержо рж▓рж╛ржЗржирзЗ `GET /...  HTTP/1.1` ржЖржЫрзЗ, "
                "ржПржмржВ `Host:` ржУ `Cookie:` рж▓рж╛ржЗржи ржжрзБржЗржЯрж╛ржУ ржЖржЫрзЗред ржкрзБрж░рзЛ ржмрзНрж▓ржХржЯрж╛ ржЖржмрж╛рж░ ржкрзЗрж╕рзНржЯ ржХрж░рзЛред"
            )
        full_url, host, cookie = parsed
        panel_data = {
            "url":         full_url,
            "target_host": host,
            "username":    "cookie",
            "password":    cookie,   # ржкрзБрж░рзЛ Cookie header ржнрзНржпрж╛рж▓рзБ password field ржП рж░рж╛ржЦрж╛ рж╣ржпрж╝
            "type":        "provider5",
        }
        panels = load_panels()
        panels.append(panel_data)
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        await update.message.reply_text(
            f"тЬЕ *Provider 5 (Cookie) Panel Added & Started!*\n\n"
            f"ЁЯФЧ `{panel_data['url'][:80]}...`\n"
            f"ЁЯМР Host: `{panel_data['target_host']}`\n\n"
            f"тЪая╕П ржХрзБржХрж┐рж░ ржорзЗржпрж╝рж╛ржж рж╢рзЗрж╖ рж╣ржпрж╝рзЗ ржЧрзЗрж▓рзЗ ржкрзНржпрж╛ржирзЗрж▓ ржЖрж░ ржбрзЗржЯрж╛ ржЖржирждрзЗ ржкрж╛рж░ржмрзЗ ржирж╛ тАФ рждржЦржи ржирждрзБржи request ржХржкрж┐ ржХрж░рзЗ ржЖржмрж╛рж░ Provider 5 ржП ржкрзНржпрж╛ржирзЗрж▓ ржпрзЛржЧ ржХрж░рждрзЗ рж╣ржмрзЗред",
            parse_mode="Markdown"
        )
        return


    # тФАтФА Fake OTP Batch: Digits тЖТ Max Interval тЖТ Numbers тФАтФА
    if state == "admin_fake_digits" and (sess["is_admin"] or is_admin(uid)):
        try:
            digits = int(text.strip())
            if not (3 <= digits <= 8):
                raise ValueError
        except ValueError:
            return await update.message.reply_text("тЭМ рзй ржерзЗржХрзЗ рзо ржПрж░ ржоржзрзНржпрзЗ ржПржХржЯрж╛ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ, ржпрзЗржоржи: `5`", parse_mode="Markdown")
        sess["fake_data"]["digits"] = digits
        sess["state"] = "admin_fake_interval"
        await update.message.reply_text(
            "ЁЯОн *Add Fake OTP Batch тАФ Step 3/4*\n\n"
            "тП▒ рж╕рж░рзНржмрзЛржЪрзНржЪ ржХржд ржорж┐ржирж┐ржЯрзЗрж░ ржоржзрзНржпрзЗ random gap рж╣ржмрзЗ? (ржпрзЗржоржи `10` ржжрж┐рж▓рзЗ ржкрзНрж░рждрж┐ржЯрж╛ OTP рзж ржерзЗржХрзЗ рззрзж ржорж┐ржирж┐ржЯрзЗрж░ ржоржзрзНржпрзЗ random рж╕ржоржпрж╝рзЗ ржпрж╛ржмрзЗ):",
            parse_mode="Markdown"
        )
        return

    if state == "admin_fake_interval" and (sess["is_admin"] or is_admin(uid)):
        try:
            max_minutes = float(text.strip())
            if max_minutes <= 0:
                raise ValueError
        except ValueError:
            return await update.message.reply_text("тЭМ рзж ржПрж░ ржмрзЗрж╢рж┐ ржПржХржЯрж╛ рж╕ржВржЦрзНржпрж╛ ржжрж╛ржУ, ржпрзЗржоржи: `10`", parse_mode="Markdown")
        sess["fake_data"]["max_minutes"] = max_minutes
        sess["state"] = "admin_fake_numbers"
        await update.message.reply_text(
            "ЁЯОн *Add Fake OTP Batch тАФ Step 4/4*\n\n"
            "ЁЯУЮ ржирж╛ржорзНржмрж╛рж░ржЧрзБрж▓рзЛ ржкрзЗрж╕рзНржЯ ржХрж░рзЛ, ржЕржержмрж╛ `.txt`/`.xlsx` ржлрж╛ржЗрж▓ ржЖржкрж▓рзЛржб ржХрж░рзЛ (Excel рж╣рж▓рзЗ ржпрзЗржХрзЛржирзЛ ржХрж▓рж╛ржорзЗ ржирж╛ржорзНржмрж╛рж░ ржерж╛ржХрж▓рзЗржЗ ржЪрж▓ржмрзЗ, ржмржЯ ржирж┐ржЬрзЗ ржЦрзБржБржЬрзЗ ржмрзЗрж░ ржХрж░рзЗ ржирж┐ржмрзЗ):\n\n"
            "Example:\n`8801712345678`\n`959123456789`\n`8801812345678`",
            parse_mode="Markdown"
        )
        return

    if state == "admin_fake_numbers" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        fd = sess.pop("fake_data", {})
        numbers = []
        for line in text.split("\n"):
            num = re.sub(r"\D", "", line.strip())
            if num and num not in numbers:
                numbers.append(num)
        if not numbers:
            return await update.message.reply_text("тЭМ ржХрзЛржирзЛ ржнрзНржпрж╛рж▓рж┐ржб ржирж╛ржорзНржмрж╛рж░ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред ржЖржмрж╛рж░ ржкрзЗрж╕рзНржЯ ржХрж░рзЛред")

        batch = {
            "numbers":     numbers,
            "service":     fd.get("service", "other"),
            "digits":      fd.get("digits", 5),
            "max_minutes": fd.get("max_minutes", 5),
            "status":      "running",
        }
        fake_otp_batches.append(batch)
        save_fake_otp_batches()
        idx = len(fake_otp_batches) - 1
        fake_otp_tasks[idx] = asyncio.create_task(run_fake_otp_batch(idx, context.application))

        svc = services.get(batch["service"], {"icon": "ЁЯУ▒", "name": batch["service"]})
        await update.message.reply_text(
            f"тЬЕ *Fake OTP Batch #{idx+1} Added & Started!*\n\n"
            f"{svc['icon']} Service: {svc['name']}\n"
            f"ЁЯФв Digits: {batch['digits']}\n"
            f"тП▒ Max Gap: {batch['max_minutes']} min\n"
            f"ЁЯУЛ Numbers: {len(numbers)}ржЯрж╛",
            parse_mode="Markdown"
        )
        return

    if state == "admin_broadcast" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        sent = 0
        for target_uid in list(users.keys()):
            try:
                await context.bot.send_message(target_uid, text, parse_mode="Markdown")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await update.message.reply_text(f"тЬЕ *Broadcast sent to {sent} users.*", parse_mode="Markdown")
        return

    if state == "admin_add_numbers" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        added = 0
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                num, cc, svc = parts[0].strip(), parts[1].strip(), parts[2].strip()
            elif len(parts) == 2:
                num, cc, svc = parts[0].strip(), parts[1].strip(), "other"
            else:
                num = line
                cc  = get_country_code_from_number(num)
                svc = "other"
            if re.match(r"^\d{10,15}$", num) and cc:
                numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
                if num not in numbers_by_cs[cc][svc]:
                    numbers_by_cs[cc][svc].append(num)
                    added += 1
        await async_save_numbers()
        await update.message.reply_text(f"тЬЕ *{added} numbers added!*", parse_mode="Markdown")
        return

    if state == "admin_set_count" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = int(text)
            if 1 <= val <= 100:
                settings["defaultNumberCount"] = val
                save_settings()
                await update.message.reply_text(f"тЬЕ *Number count set to {val}.*", parse_mode="Markdown")
            else:
                await update.message.reply_text("тЭМ Enter 1-100.")
        except:
            await update.message.reply_text("тЭМ Invalid number.")
        return

    if state == "admin_set_cooldown" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = int(text)
            if 1 <= val <= 3600:
                settings["cooldownSeconds"] = val
                save_settings()
                await update.message.reply_text(f"тЬЕ *Cooldown set to {val} seconds.*", parse_mode="Markdown")
            else:
                await update.message.reply_text("тЭМ Enter 1-3600.")
        except:
            await update.message.reply_text("тЭМ Invalid number.")
        return

    if state == "admin_set_price" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val >= 0:
                settings["defaultOtpPrice"] = val
                save_settings()
                await update.message.reply_text(f"тЬЕ *Default OTP price set to {val:.2f} taka.*", parse_mode="Markdown")
        except:
            await update.message.reply_text("тЭМ Invalid price.")
        return

    if state == "admin_set_minw" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["minWithdraw"] = val
                save_settings()
                await update.message.reply_text(f"тЬЕ *Min withdraw set to {val:.2f} taka.*", parse_mode="Markdown")
        except:
            await update.message.reply_text("тЭМ Invalid amount.")
        return

    if state == "admin_add_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 2:
            try:
                target_id = parts[0]
                amount    = float(parts[1])
                e         = get_user_earnings(target_id)
                e["balance"] = round(e["balance"] + amount, 2)
                await async_save_earnings()
                await update.message.reply_text(f"тЬЕ *{amount:.2f} taka added to {target_id}.*", parse_mode="Markdown")
            except:
                await update.message.reply_text("тЭМ Error.")
        else:
            await update.message.reply_text("тЭМ Format: `[userId] [amount]`", parse_mode="Markdown")
        return

    if state == "admin_deduct_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 2:
            try:
                target_id = parts[0]
                amount    = float(parts[1])
                e         = get_user_earnings(target_id)
                e["balance"] = max(0, round(e["balance"] - amount, 2))
                await async_save_earnings()
                await update.message.reply_text(f"тЬЕ *{amount:.2f} taka deducted from {target_id}.*", parse_mode="Markdown")
            except:
                await update.message.reply_text("тЭМ Error.")
        return

    if state == "admin_reset_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        target_id = text.strip()
        e = get_user_earnings(target_id)
        e["balance"] = 0
        await async_save_earnings()
        await update.message.reply_text(f"тЬЕ *{target_id}'s balance reset to 0.*", parse_mode="Markdown")
        return

    if state == "admin_set_country_price" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        updated = 0
        for line in text.split("\n"):
            parts = re.split(r"[:\s]+", line.strip())
            if len(parts) >= 2:
                cc    = re.sub(r"\D", "", parts[0])
                try:
                    price = float(parts[1])
                    if cc and price >= 0:
                        country_prices[cc] = price
                        updated += 1
                except:
                    pass
        save_cp()
        await update.message.reply_text(f"тЬЕ *{updated} prices updated!*", parse_mode="Markdown")
        return

    if state == "admin_add_country" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 3:
            cc   = re.sub(r"\D", "", parts[0])
            name = " ".join(parts[1:-1])
            flag = parts[-1]
            countries[cc] = {"name": name, "flag": flag}
            save_countries()
            await update.message.reply_text(f"тЬЕ *Country added!*\n+{cc}: {flag} {name}", parse_mode="Markdown")
        else:
            await update.message.reply_text("тЭМ Format: `[code] [name] [flag]`", parse_mode="Markdown")
        return

    if state == "admin_add_service" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 3:
            svc_id   = parts[0].lower()
            svc_name = " ".join(parts[1:-1])
            icon     = parts[-1]
            services[svc_id] = {"name": svc_name, "icon": icon}
            save_services()
            await update.message.reply_text(f"тЬЕ *Service added!*\n`{svc_id}`: {icon} {svc_name}", parse_mode="Markdown")
        else:
            await update.message.reply_text("тЭМ Format: `[id] [name] [icon]`", parse_mode="Markdown")
        return

    if state == "w_amount":
        try:
            amount = float(text)
            e      = get_user_earnings(uid)
            method = (sess.get("data") or {}).get("method", "bKash")

            if amount < settings["minWithdraw"]:
                return await update.message.reply_text(f"тЭМ Minimum {settings['minWithdraw']} taka")
            if amount > e["balance"]:
                return await update.message.reply_text("тЭМ Insufficient balance!")

            sess["state"] = "w_account"
            sess["data"]  = {"method": method, "amount": amount}
            icon = "ЁЯЯг" if method == "bKash" else "ЁЯЯа"
            await update.message.reply_text(
                f"{icon} *{method} тАФ {amount:.2f} taka*\n\nЁЯУ▒ Your {method} number:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="w_cancel", style="danger")]])
            )
        except:
            pass
        return

# тФАтФАтФА Withdraw Confirm тФАтФАтФА
async def cb_withdraw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    if sess.get("state") != "w_confirm":
        return

    data    = sess.get("data", {})
    method  = data.get("method")
    account = data.get("account")
    amount  = data.get("amount")
    e       = get_user_earnings(uid)

    if amount > e["balance"]:
        sess["state"] = None
        return await query.edit_message_text("тЭМ Balance changed. Please try again.", parse_mode="Markdown")

    e["balance"] = round(e["balance"] - amount, 2)
    await async_save_earnings()

    wid = str(int(time.time() * 1000))
    withdrawals.append({
        "id": wid, "userId": uid,
        "userName": update.effective_user.first_name or "User",
        "userUsername": update.effective_user.username or "",
        "amount": amount, "method": method, "account": account,
        "status": "pending", "requestedAt": datetime.now().isoformat(), "processedAt": None
    })
    await async_save_withdrawals()
    sess["state"] = None
    sess["data"]  = None

    await query.edit_message_text(
        f"тЬЕ *Withdrawal Request Submitted!*\n\n"
        f"ЁЯТ│ {method}\nЁЯУ▒ `{account}`\nЁЯТ╡ {amount:.2f} taka\n\n"
        f"тП│ Admin approval pending.",
        parse_mode="Markdown"
    )

# тФАтФАтФА OTP Group Message Handler тФАтФАтФА
async def handle_otp_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    if str(chat_id) != str(OTP_GROUP_ID) and chat_id != OTP_GROUP_ID:
        return

    msg_text = update.message.text or update.message.caption or ""
    msg_id   = update.message.message_id
    if not msg_text:
        return

    logger.info(f"ЁЯУи OTP Group [{msg_id}]: {msg_text[:120]}")
    logger.info(f"ЁЯФН Active numbers count: {len(active_numbers)}")
    matched = find_matching_active_number(msg_text)
    if not matched:
        logger.warning(f"тЪая╕П No active number matched for msg: {msg_text[:200]}")
        return

    data = active_numbers[matched]
    uid  = data["userId"]
    cc   = data.get("countryCode", "")

    if data.get("lastOTP") == msg_id:
        return
    data["lastOTP"] = msg_id
    data["otpCount"] = data.get("otpCount", 0) + 1
    await async_save_active()

    otp_code = extract_otp(msg_text)
    earned   = await add_earning(uid, cc)
    balance  = get_user_earnings(uid)["balance"]
    svc      = services.get(data.get("service",""), {"icon": "ЁЯУ▒", "name": "Service"})
    country  = countries.get(cc, {"flag": "ЁЯМН", "name": cc})

    notify = (
        f"ЁЯУи *OTP Received!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"ЁЯУЮ *Number:* `+{matched}`\n"
    )
    if otp_code:
        notify += f"\nЁЯФС *OTP Code:* `{otp_code}`\n"
    notify += f"\nЁЯТ╡ *+{earned:.2f} taka earned!*\nЁЯТ░ *Balance: {balance:.2f} taka*"

    try:
        await context.bot.send_message(uid, notify, parse_mode="Markdown")
        await context.bot.forward_message(uid, OTP_GROUP_ID, msg_id)
    except Exception as e:
        logger.error(f"OTP notify error: {e}")

    otp_log.append({
        "phoneNumber": matched, "userId": uid, "countryCode": cc,
        "service": data.get("service"), "otpCode": otp_code, "earned": earned,
        "messageId": msg_id, "delivered": True,
        "timestamp": datetime.now().isoformat()
    })
    await async_save_otp_log()

# тФАтФАтФА Real-time Group Member Change Handler тФАтФАтФА
REQUIRED_GROUP_IDS = {MAIN_CHANNEL_ID, CHAT_GROUP_ID, OTP_GROUP_ID}

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ржХрзЗржЙ group ржЫрж╛ржбрж╝рж▓рзЗ ржмрж╛ join ржХрж░рж▓рзЗ real-time ржП handle ржХрж░рзЛ"""
    try:
        cm = update.chat_member
        if not cm:
            return

        chat_id = cm.chat.id
        if chat_id not in REQUIRED_GROUP_IDS:
            return

        user    = cm.new_chat_member.user
        uid     = str(user.id)
        old_status = cm.old_chat_member.status  # ржЖржЧрзЗрж░ status
        new_status = cm.new_chat_member.status  # ржирждрзБржи status

        LEFT_STATUSES   = {"left", "kicked", "banned"}
        JOINED_STATUSES = {"member", "administrator", "creator"}

        # тФАтФА ржХрзЗржЙ group ржЫрзЗржбрж╝рзЗ ржЧрзЗрж▓рзЗ тФАтФА
        if old_status in JOINED_STATUSES and new_status in LEFT_STATUSES:
            logger.info(f"ЁЯСЛ User {uid} left chat {chat_id}")

            if uid not in users:
                return

            # verified=False ржХрж░рзЛ тАФ referral ржЫрж╛ржбрж╝рж╛ user рж╣рж▓рзЗржУ
            users[uid]["verified"] = False
            sess = get_session(uid)
            sess["verified"] = False

            # referral ржЫрж┐рж▓ ржПржмржВ confirmed ржЫрж┐рж▓ тЖТ count ржХржорж╛ржУ
            if users[uid].get("referralVerified", False):
                users[uid]["referralVerified"] = False
                referrer_id = users[uid].get("referredBy")
                if referrer_id and referrer_id in users:
                    users[referrer_id]["referralCount"] = max(0, users[referrer_id].get("referralCount", 0) - 1)
                    if referrer_id in referrals and uid in referrals[referrer_id]:
                        referrals[referrer_id].remove(uid)
                    await async_save_referrals()
                    logger.info(f"ЁЯУЙ Referral removed: uid={uid} left тЖТ referrer={referrer_id} count={users[referrer_id]['referralCount']}")
                    try:
                        await context.bot.send_message(
                            int(referrer_id),
                            f"тЪая╕П *Referral Lost!*\n\n"
                            f"рждрзЛржорж╛рж░ ржПржХржЬржи referred user group ржЫрзЗржбрж╝рзЗ ржЧрзЗржЫрзЗред\n"
                            f"ЁЯСе Current Referrals: *{users[referrer_id]['referralCount']}*",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            await async_save_users()
            logger.info(f"ЁЯФТ Access revoked for uid={uid} (left chat {chat_id})")

        # тФАтФА ржХрзЗржЙ ржЖржмрж╛рж░ group ржП join ржХрж░рж▓рзЗ тАФ рж╢рзБржзрзБ log ржХрж░рзЛ, verify ржП count рж╣ржмрзЗ тФАтФА
        elif old_status in LEFT_STATUSES and new_status in JOINED_STATUSES:
            logger.info(f"тЬЕ User {uid} joined chat {chat_id}")

    except Exception as e:
        logger.error(f"handle_chat_member_update error: {e}")

# тФАтФАтФА /cancel command тФАтФАтФА
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None
    if is_admin(uid):
        sess["is_admin"] = True
    await update.message.reply_text("тЬЕ Cancelled.", reply_markup=main_keyboard())

# тФАтФАтФА Periodic scheduled check тФАтФАтФА
async def scheduled_membership_check(app):
    while True:
        await asyncio.sleep(30 * 60)  # рзйрзж ржорж┐ржирж┐ржЯ ржкрж░ ржкрж░ background check
        if not settings.get("requireVerification", True):
            continue
        logger.info(f"ЁЯФД [Scheduled] Checking {len(users)} users...")
        blocked = 0
        for uid, user in list(users.items()):
            try:
                membership = await check_membership(int(uid), app)
                if not membership["allJoined"]:
                    users[uid]["verified"] = False
                    blocked += 1
                    sess = get_session(uid)
                    sess["verified"] = False

                    # тФАтФА рж░рзЗржлрж╛рж░ ржХрж╛ржЙржирзНржЯ ржХржорж╛ржУ ржпржжрж┐ ржЖржЧрзЗ verified ржЫрж┐рж▓ тФАтФА
                    if users[uid].get("referralVerified", False):
                        users[uid]["referralVerified"] = False
                        referrer_id = users[uid].get("referredBy")
                        if referrer_id and referrer_id in users:
                            current_count = users[referrer_id].get("referralCount", 0)
                            users[referrer_id]["referralCount"] = max(0, current_count - 1)
                            # referrals list ржерзЗржХрзЗржУ рж╕рж░рж╛ржУ
                            if referrer_id in referrals and uid in referrals[referrer_id]:
                                referrals[referrer_id].remove(uid)
                            await async_save_referrals()
                            logger.info(f"ЁЯУЙ Referral removed: uid={uid} left group тЖТ referrer={referrer_id} count={users[referrer_id]['referralCount']}")
                            try:
                                await app.bot.send_message(
                                    int(referrer_id),
                                    f"тЪая╕П *Referral Lost!*\n\n"
                                    f"рждрзЛржорж╛рж░ ржПржХржЬржи referred user group ржЫрзЗржбрж╝рзЗ ржЧрзЗржЫрзЗред\n"
                                    f"ЁЯСе Current Referrals: *{users[referrer_id]['referralCount']}*",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass

                    try:
                        pass  # message ржкрж╛ржарж╛ржирзЛ ржмржирзНржз
                    except:
                        pass
                else:
                    users[uid]["verified"] = True
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Scheduled check error for {uid}: {e}")
        await async_save_users()
        logger.info(f"тЬЕ [Scheduled] {blocked} users blocked.")

# тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
# тФАтФАтФА OTP Panel Scraping System тФАтФАтФА
# тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР

PANELS_FILE     = os.path.join(DATA_DIR, "panels.json")
otp_panel_tasks   = {}   # { index: asyncio.Task }
otp_panel_status  = {}   # { index: "running" | "stopped" | "error" }
otp_seen_ids      = set()

def load_panels() -> list:
    return load_json(PANELS_FILE, [])

def save_panels(panels: list):
    save_json(PANELS_FILE, panels)

# тФАтФАтФА Fake OTP Numbers (ржЖрж╕рж▓ ржЗржЙржЬрж╛рж░ ржкрзБрж▓ ржерзЗржХрзЗ рж╕ржорзНржкрзВрж░рзНржг ржЖрж▓рж╛ржжрж╛ тАФ рж╢рзБржзрзБ group-ржП proof ржжрзЗржЦрж╛ржирзЛрж░ ржЬржирзНржп) тФАтФАтФА
FAKE_OTP_FILE   = os.path.join(DATA_DIR, "fake_otp_batches.json")
fake_otp_batches = load_json(FAKE_OTP_FILE, [])   # [{numbers, service, digits, max_minutes, status}]
fake_otp_tasks   = {}   # { index: asyncio.Task }

def save_fake_otp_batches():
    save_json(FAKE_OTP_FILE, fake_otp_batches)

async def run_fake_otp_batch(idx: int, app):
    """ржПржХржЯрж╛ batch-ржПрж░ ржирж╛ржорзНржмрж╛рж░ ржПржХрзЗ ржПржХрзЗ (random gap ржжрж┐ржпрж╝рзЗ) fake OTP ржмрж╛ржирж┐ржпрж╝рзЗ group-ржП ржкрж╛ржарж╛ржпрж╝ тАФ ржирж╛ржорзНржмрж╛рж░ ржПржХржмрж╛рж░ ржмрзНржпржмрж╣рж╛рж░ рж╣рж▓рзЗ ржмрж╛ржжред"""
    import random
    try:
        while True:
            if idx >= len(fake_otp_batches):
                return
            batch = fake_otp_batches[idx]
            if not batch["numbers"]:
                batch["status"] = "completed"
                save_fake_otp_batches()
                logger.info(f"ЁЯОн Fake OTP batch #{idx+1} completed тАФ рж╕ржм ржирж╛ржорзНржмрж╛рж░ рж╢рзЗрж╖")
                return

            max_minutes = float(batch.get("max_minutes", 5))
            gap_seconds = random.uniform(5, max(5, max_minutes * 60))
            await asyncio.sleep(gap_seconds)

            if idx >= len(fake_otp_batches) or not fake_otp_batches[idx]["numbers"]:
                continue

            batch  = fake_otp_batches[idx]
            number = batch["numbers"].pop(0)
            digits = int(batch.get("digits", 5))
            otp_code = "".join(random.choices("0123456789", k=digits))
            svc_id  = batch.get("service", "other")
            svc     = services.get(svc_id, {"icon": "ЁЯУ▒", "name": svc_id.capitalize()})
            cc      = _guess_country_by_prefix(number)
            country = countries.get(cc, {"flag": "ЁЯМН", "name": "Unknown"})

            group_msg = (
                f"ЁЯУи *New OTP!*\n\n"
                f"{svc['icon']} *Service:* {svc['name']}\n"
                f"{country['flag']} *Country:* {country['name']}\n"
                f"ЁЯУЮ *Number:* +{number}\n"
            )
            asyncio.create_task(send_otp_to_group(otp_code, group_msg))
            save_fake_otp_batches()
            logger.info(f"ЁЯОн Fake OTP sent тАФ batch #{idx+1}, +{number}, otp={otp_code}, ржмрж╛ржХрж┐ {len(batch['numbers'])}ржЯрж╛")

    except asyncio.CancelledError:
        logger.info(f"тП╣я╕П Fake OTP batch #{idx+1} stopped")
        return
    except Exception as e:
        logger.error(f"тЭМ Fake OTP batch #{idx+1} error: {e}")

def start_all_fake_otp_batches(app):
    for i, b in enumerate(fake_otp_batches):
        if b.get("status") != "completed" and b.get("numbers"):
            fake_otp_tasks[i] = asyncio.create_task(run_fake_otp_batch(i, app))

def scraper_extract_otp(message: str):
    if not message: return None
    cleaned = re.sub(r'\b(19|20)\d{2}[-/]\d{2}[-/]\d{2}\b', '', message)
    cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned)
    for p in [
        r'FB-(\d{5})', r'[Gg]-(\d{6})',
        r'(?:otp|code|pin|verification|┘Г┘И╪п|╪▒┘Е╪▓|ржХрзЛржб)[^\d]{0,15}(\d{4,8})',
        r'(?:is|has|:)\s*(\d{4,8})\b',
        r'(\d{3}[- ]\d{3})', r'\b(\d{6})\b', r'\b(\d{4,8})\b',
    ]:
        m = re.search(p, cleaned, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(' ', '').replace('-', '')
            if 4 <= len(raw) <= 8:
                return raw
    return None

def scraper_detect_service(message: str, range_name: str = "") -> str:
    combined = (message + " " + range_name).lower()
    for svc, pat in {
        'whatsapp': r'whatsapp|┘И╪з╪к╪│╪з╪и', 'telegram': r'telegram',
        'facebook': r'facebook|fb\.com', 'instagram': r'instagram',
        'google':   r'google|gmail',     'microsoft': r'microsoft|outlook',
        'twitter':  r'twitter|x\.com',   'tiktok':    r'tiktok',
        'snapchat': r'snapchat',
    }.items():
        if re.search(pat, combined, re.IGNORECASE):
            return svc
    return "other"

async def panel_login(session, url: str, username: str, password: str, ptype: str = None, check_url: str = None) -> bool:
    """Auto-detect panel type and login"""
    # тФАтФА Provider 2 (generic username/password auto-login) тФАтФА
    if ptype == "provider2":
        return await _provider2_login(session, url, username, password, check_url)
    # тФАтФА Masdar panel (ints/login) тФАтФА
    if await _masdar_login(session, url, username, password):
        return True
    # тФАтФА IMS panel (login) тФАтФА
    if await _ims_login(session, url, username, password):
        return True
    return False

async def _masdar_login(session, url: str, username: str, password: str) -> bool:
    try:
        from bs4 import BeautifulSoup as _BS
        async with session.get(f"{url}/ints/login", ssl=False, timeout=15) as r:
            if r.status != 200: return False
            soup = _BS(await r.text(), "html.parser")
            capt = "5"
            inp  = soup.find("input", {"name": "capt"})
            if inp:
                nums = re.findall(r'\d+', (inp.find_parent("div") or inp).get_text())
                if len(nums) >= 2:
                    capt = str(int(nums[0]) + int(nums[1]))

        async with session.post(
            f"{url}/ints/signin",
            data={"username": username, "password": password, "capt": capt},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": f"{url}/ints/login", "Origin": url},
            allow_redirects=True, ssl=False, timeout=15
        ) as r:
            if "login" not in str(r.url).lower():
                logger.info(f"тЬЕ Masdar login OK: {url}")
                return True
            return False
    except Exception as e:
        logger.debug(f"Masdar login failed {url}: {e}")
        return False

async def _ims_login(session, url: str, username: str, password: str) -> bool:
    try:
        from bs4 import BeautifulSoup as _BS
        login_url = f"{url}/login"
        async with session.get(login_url, ssl=False, timeout=15) as r:
            if r.status != 200: return False
            text = await r.text()
            soup = _BS(text, "html.parser")
            # captcha
            capt = "5"
            math = re.search(r'(\d+)\s*([\+\-])\s*(\d+)', text)
            if math:
                a, op, b = int(math.group(1)), math.group(2), int(math.group(3))
                capt = str(a + b) if op == '+' else str(a - b)
            # etkk token
            etkk_input = soup.find("input", {"name": "etkk"})
            etkk_val   = etkk_input.get("value", "") if etkk_input else ""

        async with session.post(
            f"{url}/signin",
            data={"etkk": etkk_val, "username": username, "password": password, "capt": capt},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": login_url},
            allow_redirects=True, ssl=False, timeout=15
        ) as r:
            text = await r.text()
            if username in text or "CDR" in text or "dashboard" in str(r.url).lower():
                logger.info(f"тЬЕ IMS login OK: {url}")
                return True
            return False
    except Exception as e:
        logger.debug(f"IMS login failed {url}: {e}")
        return False

async def _provider2_login(session, url: str, username: str, password: str, check_url: str = None) -> bool:
    """Provider 2 тАФ generic username/password auto-login (any panel).
    Auto-detects the login form's fields + solves simple math captchas."""
    try:
        from bs4 import BeautifulSoup as _BS
        from urllib.parse import urljoin as _urljoin

        login_url = url
        if not login_url.lower().endswith('/login') and not login_url.lower().endswith('.php'):
            login_url = f"{login_url.rstrip('/')}/login"

        async with session.get(login_url, ssl=False, timeout=15) as r:
            if r.status != 200:
                return False
            html_text = await r.text()

        soup = _BS(html_text, "html.parser")
        form = soup.find("form")
        if not form:
            return False

        pass_input = form.find("input", {"type": "password"})
        if not pass_input:
            return False
        user_input = form.find("input", {"type": "text"}) or form.find("input", {"type": "email"})

        action   = form.get("action", "")
        post_url = _urljoin(login_url, action) if action else login_url
        user_field = user_input.get("name") if user_input else "username"
        pass_field = pass_input.get("name") if pass_input else "password"

        form_data = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name and name not in (user_field, pass_field):
                form_data[name] = inp.get("value", "")
        form_data[user_field] = username
        form_data[pass_field] = password

        # тФАтФА simple math captcha (e.g. "3 + 5 = ?") тФАтФА
        math_match = re.search(r'(\d+)\s*([\+\-])\s*(\d+)', html_text)
        if math_match:
            a, op, b = int(math_match.group(1)), math_match.group(2), int(math_match.group(3))
            answer = a + b if op == '+' else a - b
            for key in ("capt", "captcha", "answer", "capcha"):
                if key in form_data or soup.find("input", {"name": key}):
                    form_data[key] = str(answer)

        async with session.post(
            post_url, data=form_data, allow_redirects=True, ssl=False, timeout=15,
            headers={"Referer": login_url}
        ) as login_res:
            login_text = await login_res.text()

        confirm_url = check_url or f"{url.split('/login')[0]}/client/SMSCDRStats"
        async with session.get(confirm_url, ssl=False, timeout=15) as check_res:
            check_text = await check_res.text()

        combined = (login_text + check_text).lower()
        if 'logout' in combined or 'dashboard' in combined or 'cdrs' in combined or 'sms reports' in combined:
            logger.info(f"тЬЕ Provider2 login OK: {url}")
            return True
        return False
    except Exception as e:
        logger.debug(f"Provider2 login failed {url}: {e}")
        return False

async def _provider2_fetch(session, url: str, num_col_idx=None, msg_col_idx=None) -> list:
    """Provider 2 тАФ generic SMS/CDR fetch (AJAX DataTables auto-detect, HTML table fallback).
    num_col_idx / msg_col_idx: admin-supplied 1-based column numbers (from checking the panel
    manually). If not given, defaults to column 2/3 (0-based 1/2) with header-name auto-detect."""
    try:
        from bs4 import BeautifulSoup as _BS
        check_url = url  # admin-ржПрж░ ржжрзЗржУржпрж╝рж╛ SMS URL рж╕рж░рж╛рж╕рж░рж┐ ржмрзНржпржмрж╣рж╛рж░ рж╣ржмрзЗ
        async with session.get(check_url, ssl=False, timeout=15) as r:
            if r.status != 200:
                return []
            html_text = await r.text()

        if "login" in html_text.lower() or "signin" in html_text.lower():
            return []  # session expired тАФ re-login рж╣ржмрзЗ ржкрж░рзЗрж░ cycle ржП

        soup = _BS(html_text, "html.parser")
        s_ajax_source = ""
        for script in soup.find_all("script"):
            script_text = script.string or ""
            m = re.search(r'sAjaxSource"\s*:\s*"([^"]+)"', script_text)
            if m:
                s_ajax_source = m.group(1)
                break

        manual_cols = bool(num_col_idx and msg_col_idx)
        n_idx = (int(num_col_idx) - 1) if num_col_idx else 1  # default column index (0-based): number
        m_idx = (int(msg_col_idx) - 1) if msg_col_idx else 2  # default column index (0-based): message

        results = []

        if s_ajax_source:
            base_url = url.split("/client")[0].split("/login")[0].strip()
            if s_ajax_source.startswith("http"):
                ajax_url = s_ajax_source
            elif s_ajax_source.startswith("/"):
                ajax_url = f"{base_url}{s_ajax_source}"
            else:
                current_dir = check_url[:check_url.rfind("/")]
                ajax_url = f"{current_dir}/{s_ajax_source}"
            if "iDisplayLength" not in ajax_url:
                sep = "&" if "?" in ajax_url else "?"
                ajax_url += f"{sep}sEcho=1&iColumns=7&iDisplayStart=0&iDisplayLength=100&sSearch=&iSortingCols=1&iSortCol_0=0&sSortDir_0=desc"

            async with session.get(ajax_url, ssl=False, timeout=15,
                headers={"Referer": check_url, "X-Requested-With": "XMLHttpRequest"}) as ar:
                data = json.loads(await ar.text())
            for row in data.get("aaData", []):
                if not isinstance(row, list) or len(row) <= max(n_idx, m_idx):
                    continue
                msg_val   = str(row[m_idx])
                clean_num = re.sub(r"\D", "", str(row[n_idx]))
                otp = scraper_extract_otp(msg_val)
                if clean_num and 5 <= len(clean_num) <= 18 and otp and len(msg_val) > 4:
                    results.append({
                        "timestamp": str(row[0]) if row else "",
                        "number": clean_num, "range": "",
                        "message": msg_val, "otp": otp,
                    })
        else:
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                if not rows:
                    continue
                f_n_idx, f_m_idx = n_idx, m_idx
                if not manual_cols:
                    headers = rows[0].find_all(["th", "td"])
                    for i, cell in enumerate(headers):
                        c_text = cell.get_text(strip=True).lower()
                        if "number" in c_text or "mobile" in c_text or "cli" in c_text:
                            f_n_idx = i
                        if "message" in c_text or "sms" in c_text or "content" in c_text:
                            f_m_idx = i
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    if all(c.name == "th" for c in cols):
                        continue
                    if len(cols) > max(f_n_idx, f_m_idx):
                        num_text = cols[f_n_idx].get_text(separator=" ", strip=True)
                        msg_text = cols[f_m_idx].get_text(separator=" ", strip=True)
                        clean_num = re.sub(r"\D", "", num_text)
                        otp = scraper_extract_otp(msg_text)
                        if clean_num and 5 <= len(clean_num) <= 18 and otp and len(msg_text) > 4:
                            results.append({
                                "timestamp": "", "number": clean_num,
                                "range": "", "message": msg_text, "otp": otp,
                            })
        return results
    except Exception as e:
        logger.error(f"тЭМ provider2 fetch error {url}: {e}")
        return []

async def panel_fetch_sms(session, url: str, panel_type: str = "masdar_client", panel: dict = None) -> list:
    if panel_type == "provider2":
        num_col = (panel or {}).get("num_col_idx")
        msg_col = (panel or {}).get("msg_col_idx")
        return await _provider2_fetch(session, url, num_col, msg_col)

    TYPE_MAP = {
        "masdar_client": {"path": "/ints/client/res/data_smscdr.php",
                          "ref":  "/ints/client/SMSCDRStats", "cols": 7, "idx": 4},
        "masdar_agent":  {"path": "/ints/agent/res/data_smscdr.php",
                          "ref":  "/ints/agent/SMSCDRStats",  "cols": 7, "idx": 4},
        "ims_client":    {"path": "/client/res/data_smscdr.php",
                          "ref":  "/client/SMSCDRStats",      "cols": 9, "idx": 5},
        "ims_agent":     {"path": "/agent/res/data_smscdr.php",
                          "ref":  "/agent/SMSCDRReports",     "cols": 9, "idx": 5},
    }
    cfg   = TYPE_MAP.get(panel_type, TYPE_MAP["masdar_client"])
    today = datetime.now().strftime('%Y-%m-%d')
    ts    = int(time.time() * 1000)
    params = {
        "fdate1": today + " 00:00:00",
        "fdate2": today + " 23:59:59",
        "frange": "", "fnum": "", "fcli": "", "fg": "0",
        "sEcho": "1", "iColumns": str(cfg["cols"]),
        "iDisplayStart": "0", "iDisplayLength": "100",
        "sSearch": "", "bRegex": "false",
        "iSortCol_0": "0", "sSortDir_0": "desc", "iSortingCols": "1",
        "_": ts,
    }
    for i in range(cfg["cols"]):
        params[f"mDataProp_{i}"] = str(i)
    try:
        async with session.get(
            url + cfg["path"], params=params, ssl=False, timeout=15,
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Referer": url + cfg["ref"]}
        ) as r:
            if r.status != 200: return []
            data   = json.loads(await r.text())
            result = []
            for item in data.get("aaData", []):
                if not isinstance(item, list) or len(item) <= cfg["idx"]: continue
                if isinstance(item[0], str) and item[0].startswith('0,0,0,0'): continue
                otp = scraper_extract_otp(str(item[cfg["idx"]]))
                if otp:
                    result.append({
                        "timestamp": str(item[0]),
                        "number":    re.sub(r"\D", "", str(item[2])) if len(item) > 2 else "",
                        "range":     str(item[1]) if len(item) > 1 else "",
                        "message":   str(item[cfg["idx"]]),
                        "otp":       otp,
                    })
            return result
    except Exception as e:
        logger.error(f"тЭМ fetch_sms error {url}: {e}")
        return []

async def _masdar_fetch(session, url: str):
    try:
        now  = datetime.now()
        s_dt = now.strftime('%Y-%m-%d') + '%2000:00:00'
        e_dt = now.strftime('%Y-%m-%d') + '%2023:59:59'
        ts   = int(time.time() * 1000)
        api  = (
            f"{url}/ints/client/res/data_smscdr.php?"
            f"fdate1={s_dt}&fdate2={e_dt}&frange=&fnum=&fcli=&fg=0&"
            f"sEcho=1&iColumns=7&sColumns=%2C%2C%2C%2C%2C%2C&"
            f"iDisplayStart=0&iDisplayLength=100&"
            f"mDataProp_0=0&mDataProp_1=1&mDataProp_2=2&"
            f"mDataProp_3=3&mDataProp_4=4&mDataProp_5=5&mDataProp_6=6&"
            f"sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1&_={ts}"
        )
        async with session.get(api, ssl=False, timeout=15,
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Referer": f"{url}/ints/client/SMSCDRStats"}) as r:
            if r.status != 200: return None
            data = json.loads(await r.text())
            result = []
            for item in data.get("aaData", []):
                if not isinstance(item, list) or len(item) < 5: continue
                if isinstance(item[0], str) and item[0].startswith('0,0,0,0'): continue
                otp = scraper_extract_otp(str(item[4]))
                if otp:
                    result.append({
                        "timestamp": str(item[0]),
                        "number":    re.sub(r"\D", "", str(item[2])),
                        "range":     str(item[1]),
                        "message":   str(item[4]),
                        "otp":       otp,
                    })
            return result
    except:
        return None

async def _ims_fetch(session, url: str):
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        ts    = int(time.time() * 1000)
        params = {
            "fdate1": f"{today} 00:00:00",
            "fdate2": f"{today} 23:59:59",
            "frange": "", "fnum": "", "fcli": "", "fg": "0",
            "sEcho": "1", "iColumns": "9",
            "iDisplayStart": "0", "iDisplayLength": "100",
            "mDataProp_0": "0", "mDataProp_1": "1", "mDataProp_2": "2",
            "mDataProp_3": "3", "mDataProp_4": "4", "mDataProp_5": "5",
            "mDataProp_6": "6", "mDataProp_7": "7", "mDataProp_8": "8",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "desc", "iSortingCols": "1",
            "_": ts
        }
        api = f"{url}/agent/res/data_smscdr.php"
        async with session.get(api, params=params, ssl=False, timeout=15,
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Referer": f"{url}/agent/SMSCDRReports"}) as r:
            if r.status != 200: return None
            data = json.loads(await r.text())
            result = []
            for item in data.get("aaData", []):
                if not isinstance(item, list) or len(item) < 6: continue
                otp = scraper_extract_otp(str(item[5]))
                if otp:
                    result.append({
                        "timestamp": str(item[0]),
                        "number":    re.sub(r"\D", "", str(item[2])),
                        "range":     str(item[1]),
                        "message":   str(item[5]),
                        "otp":       otp,
                    })
            return result
    except:
        return None

panel_recent_log = {}  # { panel_idx: deque of last 20 fetched entries }

def _guess_country_by_prefix(number: str) -> str:
    """ржирж╛ржорзНржмрж╛рж░рзЗрж░ рж╢рзБрж░рзБрж░ ржЕржВрж╢ ржорж┐рж▓рж┐ржпрж╝рзЗ country code ржмрзЗрж░ ржХрж░рзЗ (unassigned ржирж╛ржорзНржмрж╛рж░рзЗрж░ ржЬржирзНржп) тАФ рж▓ржорзНржмрж╛ ржХрзЛржб ржЖржЧрзЗ ржЪрзЗржХ ржХрж░рзЗред"""
    for code in sorted(countries.keys(), key=len, reverse=True):
        if number.startswith(code):
            return code
    return ""

async def _handle_scraped_sms(sms: dict, source_url: str, app, panel_idx: int = None):
    """ржПржХржЯрж╛ SMS/OTP рж░рзЗржХрж░рзНржб ржкрзНрж░рж╕рзЗрж╕ ржХрж░рзЗ тАФ active_numbers match, DM+Group+Log тАФ Provider 1/2/3/4/5 рж╕ржмрж╛рж░ ржЬржирзНржп рж╢рзЗржпрж╝рж╛рж░рзНржбред"""
    # тФАтФА ржкрзНрж░рждрж┐ржЯрж╛ ржкрзНржпрж╛ржирзЗрж▓рзЗрж░ ржирж┐ржЬрзЗрж░ рж╕рж╛ржорзНржкрзНрж░рждрж┐ржХ рж▓ржЧ (admin panel ржерзЗржХрзЗ ржжрзЗржЦрж╛рж░ ржЬржирзНржп) тФАтФА
    if panel_idx is not None:
        from collections import deque as _deque
        panel_recent_log.setdefault(panel_idx, _deque(maxlen=20)).appendleft({
            "time":   datetime.now().strftime("%H:%M:%S"),
            "number": sms.get("number", ""),
            "otp":    sms.get("otp", ""),
        })

    # тФАтФА active_numbers fresh reload тФАтФА
    fresh_active = load_json(ACTIVE_NUMBERS_FILE, {})
    if fresh_active and set(fresh_active.keys()) != set(active_numbers.keys()):
        active_numbers.clear()
        active_numbers.update(fresh_active)
        rebuild_suffix_index()

    number  = sms["number"].lstrip("0")
    matched = find_active_number(number)

    if not matched:
        # тФАтФА ржХрзЛржирзЛ ржЗржЙржЬрж╛рж░рзЗрж░ ржХрж╛ржЫрзЗ assign ржХрж░рж╛ ржирж╛ржЗ, рждржмрзБржУ ржЧрзНрж░рзБржкрзЗ ржкрзЛрж╕рзНржЯ рж╣ржмрзЗ (proof-of-activity) тФАтФА
        svc_id  = scraper_detect_service(sms["message"], sms.get("range", ""))
        svc     = services.get(svc_id, {"icon": "ЁЯУ▒", "name": svc_id.capitalize()})
        cc      = _guess_country_by_prefix(number)
        country = countries.get(cc, {"flag": "ЁЯМН", "name": "Unknown"})
        group_msg = (
            f"ЁЯУи *New OTP!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"ЁЯУЮ *Number:* +{number}\n"
        )
        asyncio.create_task(send_otp_to_group(sms["otp"], group_msg))
        return
    an   = active_numbers[matched]
    uid  = an["userId"]
    cc   = an.get("countryCode", "")
    svc_id = scraper_detect_service(sms["message"], sms.get("range", ""))

    earned  = await add_earning(uid, cc)
    balance = get_user_earnings(uid)["balance"]
    svc     = services.get(svc_id, {"icon": "ЁЯУ▒", "name": svc_id.capitalize()})
    country = countries.get(cc, {"flag": "ЁЯМН", "name": cc})

    notify = (
        f"ЁЯУи *OTP Received!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"ЁЯУЮ *Number:* `+{matched}`\n"
        f"\nЁЯФС *OTP Code:* `{sms['otp']}`\n"
        f"\nЁЯТ╡ *+{earned:.2f} taka earned!*\n"
        f"ЁЯТ░ *Balance: {balance:.2f} taka*"
    )

    # тФАтФА DM ржУ Group тАФ fire-and-forget (ржмрзНржпрж╛ржЪрзЗрж░ рж╕ржмржЧрзБрж▓рзЛ ржПржХрж╕рж╛ржерзЗ/рж╕рж╛ржерзЗ рж╕рж╛ржерзЗ ржкрж╛ржарж╛ржирзЛ рж╣ржмрзЗ) тФАтФА
    asyncio.create_task(send_dm_with_retry(app, uid, notify, log_number=matched, log_otp=sms["otp"]))

    # тФАтФА Telegram OTP Group ржПржУ ржкрж╛ржарж╛ржУ тФАтФА
    group_msg = (
        f"ЁЯУи *New OTP!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"ЁЯУЮ *Number:* +{matched}\n"
    )
    asyncio.create_task(send_otp_to_group(sms["otp"], group_msg))

    otp_log.append({
        "phoneNumber": matched, "userId": uid, "countryCode": cc,
        "service": svc_id, "otpCode": sms["otp"], "earned": earned,
        "messageId": None, "delivered": True,
        "source": f"panel_{source_url}",
        "timestamp": datetime.now().isoformat()
    })
    await async_save_otp_log()

async def run_panel(panel: dict, idx: int, app):
    import aiohttp as _aio
    url      = panel["url"].rstrip("/")
    username = panel["username"]
    password = panel["password"]
    logger.info(f"ЁЯЪА Panel #{idx+1} started: {url}")
    otp_panel_status[idx] = "running"

    async with _aio.ClientSession(
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
        cookie_jar=_aio.CookieJar(unsafe=True)
    ) as session:
        last_login    = 0
        fail_count    = 0
        previous_otps = set()  # ржПржЗ run ржП ржпрж╛ ржкрж╛ржарж┐ржпрж╝рзЗржЫрж┐
        while True:
            try:
                # тФАтФА Login / Re-login тФАтФА
                if time.time() - last_login > 540:
                    ok = await panel_login(session, url, username, password, panel.get("type"), panel.get("sms_url"))
                    if not ok:
                        fail_count += 1
                        if fail_count >= 3:
                            otp_panel_status[idx] = "error"
                            logger.error(f"тЭМ Panel #{idx+1} login failed 3 times, stopping.")
                            return
                        await asyncio.sleep(60)
                        continue
                    last_login = time.time()
                    fail_count = 0
                    otp_panel_status[idx] = "running"

                # тФАтФА SMS Fetch тФАтФА (Provider 2 ржПрж░ ржЬржирзНржп ржЖрж▓рж╛ржжрж╛ sms_url ржмрзНржпржмрж╣рж╛рж░ рж╣ржмрзЗ, ржмрж╛ржХрж┐ржжрзЗрж░ ржЬржирзНржп login url-ржЗ)
                fetch_url = panel.get("sms_url") or url
                sms_list  = await panel_fetch_sms(session, fetch_url, panel.get("type", "masdar_client"), panel)

                for sms in sms_list:
                    otp_id = f"{sms['number']}_{sms['otp']}_{sms['timestamp']}"
                    if otp_id in previous_otps:
                        continue
                    previous_otps.add(otp_id)
                    # memory limit
                    if len(previous_otps) > 50000:
                        previous_otps = set(list(previous_otps)[-20000:])

                    await _handle_scraped_sms(sms, url, app, idx)

                await asyncio.sleep(settings.get("panelPollInterval", 1))

            except asyncio.CancelledError:
                otp_panel_status[idx] = "stopped"
                logger.info(f"тП╣я╕П Panel #{idx+1} stopped")
                return
            except Exception as e:
                otp_panel_status[idx] = "error"
                logger.error(f"тЭМ Panel #{idx+1} error: {e}")
                await asyncio.sleep(30)

def _p3_get_fns(bn: str, url: str, ptype: str):
    """Provider 3 тАФ panel_fetchers.py ржоржбрж┐ржЙрж▓ ржерзЗржХрзЗ рж╕ржарж┐ржХ login/fetch ржлрж╛ржВрж╢ржи ржмрзЗржЫрзЗ ржжрзЗржпрж╝ (otp_bot_v2.py ржПрж░ _get_fns ржЕржирзБрж╕рж╛рж░рзЗ)ред"""
    from panel_fetchers import (
        ints_login, ints_fetch,
        ims_login, ims_fetch,
        konekta_login, konekta_fetch,
        panel_login as _std_login, panel_fetch as _std_fetch,
        new_panel_login, new_panel_fetch,
        timesms_login, timesms_fetch,
        proofsms_fetch,
    )
    if ptype == "timesms":
        return (lambda u, p: timesms_login(bn, u, p, url), lambda s: timesms_fetch(bn, s, url))
    if ptype == "ims":
        return (lambda u, p: ims_login(u, p, url), lambda s: ims_fetch(s, url))
    if ptype == "konekta":
        return (lambda u, p: konekta_login(u, p), lambda s: konekta_fetch(s))
    if ptype in ("roxy", "voicegate", "numberpanel"):
        return (lambda u, p: new_panel_login(bn, u, p, url), lambda s: new_panel_fetch(bn, s, url))
    if ptype == "standard":
        return (lambda u, p: _std_login(bn, u, p, url), lambda s: _std_fetch(s, url))
    if ptype == "proofsms":
        return (lambda u, p: ints_login(bn, u, p, url), lambda s: proofsms_fetch(s, url))
    # default / "ints"
    return (lambda u, p: ints_login(bn, u, p, url), lambda s: ints_fetch(bn, s, url))

async def run_provider3_panel(panel: dict, idx: int, app):
    """Provider 3 тАФ panel_fetchers.py (sync/requests ржнрж┐рждрзНрждрж┐ржХ) ржХрзЛржб asyncio.to_thread ржжрж┐ржпрж╝рзЗ ржЪрж╛рж▓рж╛ржирзЛ рж╣ржпрж╝,
    ржпрж╛рждрзЗ ржорзВрж▓ event loop ржмрзНрж▓ржХ ржирж╛ рж╣ржпрж╝, ржЖрж░ ржХрзЛржирзЛ рж▓ржЬрж┐ржХ ржкрзБржирж░рж╛ржпрж╝ рж▓рж┐ржЦрждрзЗ ржирж╛ рж╣ржпрж╝ред"""
    bn       = f"provider3_{idx}"
    ptype    = panel.get("subtype", "ints")
    url      = panel["url"].rstrip("/")
    username = panel["username"]
    password = panel["password"]
    logger.info(f"ЁЯЪА Provider3 Panel #{idx+1} started: {url} ({ptype})")
    otp_panel_status[idx] = "running"

    login_fn, fetch_fn = _p3_get_fns(bn, url, ptype)
    session_info  = None
    last_login    = 0
    fail_count    = 0
    previous_otps = set()

    while True:
        try:
            if session_info is None or time.time() - last_login > 540:
                try:
                    session_info = await asyncio.to_thread(login_fn, username, password)
                    last_login   = time.time()
                    fail_count   = 0
                    otp_panel_status[idx] = "running"
                except Exception as e:
                    session_info = None
                    fail_count += 1
                    logger.error(f"тЭМ Provider3 Panel #{idx+1} login failed: {e}")
                    if fail_count >= 3:
                        otp_panel_status[idx] = "error"
                        logger.error(f"тЭМ Provider3 Panel #{idx+1} login failed 3 times, stopping.")
                        return
                    await asyncio.sleep(60)
                    continue

            rows = await asyncio.to_thread(fetch_fn, session_info)
            if rows is None:
                # session expired тАФ ржкрж░рзЗрж░ loop ржП re-login рж╣ржмрзЗ
                session_info = None
                await asyncio.sleep(5)
                continue

            for row in rows:
                # row format: [date, id, number, cli, None, sms]  (panel_fetchers._parse ржПрж░ ржЖржЙржЯржкрзБржЯ)
                try:
                    dt, rid, number, cli, _unused, message = row[0], row[1], row[2], row[3], row[4], row[5]
                except Exception:
                    continue
                if not message:
                    continue
                otp = scraper_extract_otp(message)
                if not otp:
                    continue
                otp_id = f"{number}_{otp}_{dt}_{rid}"
                if otp_id in previous_otps:
                    continue
                previous_otps.add(otp_id)
                if len(previous_otps) > 50000:
                    previous_otps = set(list(previous_otps)[-20000:])

                sms = {"number": number, "message": message, "otp": otp, "range": cli or "", "timestamp": dt}
                await _handle_scraped_sms(sms, url, app, idx)

            await asyncio.sleep(settings.get("panelPollInterval", 1))

        except asyncio.CancelledError:
            otp_panel_status[idx] = "stopped"
            logger.info(f"тП╣я╕П Provider3 Panel #{idx+1} stopped")
            return
        except Exception as e:
            otp_panel_status[idx] = "error"
            logger.error(f"тЭМ Provider3 Panel #{idx+1} error: {e}")
            await asyncio.sleep(30)

async def _provider4_fetch(base_url: str, api_token: str) -> list:
    """Provider 4 тАФ ржирж┐ржЬрзЗрж░ Power SMS Panel API (base URL + API token) ржжрж┐ржпрж╝рзЗ рж╕рж░рж╛рж╕рж░рж┐ CDR fetch тАФ рж▓ржЧржЗржирзЗрж░ ржжрж░ржХрж╛рж░ ржирж╛ржЗред"""
    try:
        import aiohttp as _aiohttp
        url     = f"{base_url.rstrip('/')}/api/sms/cdr?per_page=100&sms_type=received"
        headers = {"X-API-Token": api_token}
        async with _aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, ssl=False, timeout=15) as r:
                if r.status != 200:
                    logger.error(f"тЭМ Provider4 fetch failed ({r.status})")
                    return []
                data = await r.json(content_type=None)

        results = []
        for item in data.get("results", []):
            message = item.get("message") or ""
            number  = re.sub(r"\D", "", str(item.get("number") or ""))
            otp     = scraper_extract_otp(message)
            if number and otp:
                results.append({
                    "timestamp": item.get("created_at", "") or "",
                    "number": number, "range": item.get("cli", "") or "",
                    "message": message, "otp": otp,
                })
        return results
    except Exception as e:
        logger.error(f"тЭМ Provider4 fetch error: {e}")
        return []

async def run_provider4_panel(panel: dict, idx: int, app):
    """Provider 4 тАФ API-token ржнрж┐рждрзНрждрж┐ржХ (Power SMS Panel ржПрж░ ржирж┐ржЬрзЗрж░ API) тАФ рж▓ржЧржЗржи/рж╕рзЗрж╢ржирзЗрж░ ржжрж░ржХрж╛рж░ ржирж╛ржЗред"""
    base_url  = panel["url"].rstrip("/")
    api_token = panel["password"]  # API token ржЯрж╛ password field ржП рж╕рзЗржн ржерж╛ржХрзЗ
    logger.info(f"ЁЯЪА Provider4 Panel #{idx+1} started: {base_url}")
    otp_panel_status[idx] = "running"
    previous_otps = set()

    while True:
        try:
            rows = await _provider4_fetch(base_url, api_token)
            otp_panel_status[idx] = "running"

            for sms in rows:
                otp_id = f"{sms['number']}_{sms['otp']}_{sms['timestamp']}"
                if otp_id in previous_otps:
                    continue
                previous_otps.add(otp_id)
                if len(previous_otps) > 50000:
                    previous_otps = set(list(previous_otps)[-20000:])
                await _handle_scraped_sms(sms, base_url, app, idx)

            await asyncio.sleep(settings.get("panelPollInterval", 1))

        except asyncio.CancelledError:
            otp_panel_status[idx] = "stopped"
            logger.info(f"тП╣я╕П Provider4 Panel #{idx+1} stopped")
            return
        except Exception as e:
            otp_panel_status[idx] = "error"
            logger.error(f"тЭМ Provider4 Panel #{idx+1} error: {e}")
            await asyncio.sleep(30)

async def _provider5_fetch(target_url: str, target_host: str, session_cookie: str) -> list:
    """Provider 5 тАФ ржХрзБржХрж┐ (PHPSESSID) ржжрж┐ржпрж╝рзЗ рж╕рж░рж╛рж╕рж░рж┐ DataTables AJAX endpoint fetch тАФ рж▓ржЧржЗржи ржХрж░рж╛рж░ ржжрж░ржХрж╛рж░ ржирж╛ржЗред
    admin-ржПрж░ ржжрзЗржУржпрж╝рж╛ target_url ржП ржпржжрж┐ ржЖржЧрзЗ ржерзЗржХрзЗржЗ query params (csstr, iColumns, ржЗрждрзНржпрж╛ржжрж┐) ржерж╛ржХрзЗ,
    рж╕рзЗржЧрзБрж▓рзЛ ржЕржХрзНрж╖ржд рж░рзЗржЦрзЗ рж╢рзБржзрзБ рждрж╛рж░рж┐ржЦ (fdate1/fdate2) ржЖржЬржХрзЗрж░ рждрж╛рж░рж┐ржЦ ржжрж┐ржпрж╝рзЗ ржЖржкржбрзЗржЯ ржХрж░рж╛ рж╣ржпрж╝ред"""
    try:
        import aiohttp as _aiohttp
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

        current_date = datetime.now().strftime("%Y-%m-%d")
        parts        = urlsplit(target_url)
        query_pairs  = parse_qsl(parts.query, keep_blank_values=True)
        has_query    = bool(query_pairs)

        query_dict = dict(query_pairs)
        query_dict["fdate1"] = f"{current_date} 00:00:00"
        query_dict["fdate2"] = f"{current_date} 23:59:59"
        if not has_query:
            # admin ржХрзЛржирзЛ query ржжрзЗржпрж╝ржирж┐ тАФ ржПржХржжржо base ржзрж░рзЗ ржирж╛ржУ (default 7-column masdar-ржЗржиржЯрж╛ржЗржк)
            query_dict.update({
                "frange": "", "fnum": "", "fcli": "",
                "fgdate": "", "fgmonth": "", "fgrange": "", "fgnumber": "", "fgcli": "", "fg": "0",
                "sEcho": "1", "iColumns": "7", "sColumns": ",,,,,,",
                "iDisplayStart": "0", "iDisplayLength": "100",
                "iSortCol_0": "0", "sSortDir_0": "desc", "iSortingCols": "1",
            })
        final_url = urlunsplit((parts.scheme or "http", parts.netloc or target_host,
                                 parts.path, urlencode(query_dict), ""))

        cookie_header = session_cookie if "=" in session_cookie else f"PHPSESSID={session_cookie}"
        headers = {
            "Host": target_host,
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"http://{target_host}/",
            "Cookie": cookie_header,
        }
        async with _aiohttp.ClientSession() as s:
            async with s.get(final_url, headers=headers, ssl=False, timeout=15) as r:
                if r.status != 200:
                    logger.error(f"тЭМ Provider5 fetch failed ({r.status}) тАФ ржХрзБржХрж┐ ржорзЗржпрж╝рж╛ржж рж╢рзЗрж╖ рж╣ржпрж╝рзЗ ржерж╛ржХрждрзЗ ржкрж╛рж░рзЗ")
                    return []
                raw_text = await r.text()
                if not raw_text.strip():
                    logger.warning("тЪая╕П Provider5: ржЦрж╛рж▓рж┐ рж░рзЗрж╕ржкржирзНрж╕ ржПрж╕рзЗржЫрзЗ")
                    return []
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    logger.error(f"тЭМ Provider5: JSON ржирж╛, рж╕ржорзНржнржмржд ржХрзБржХрж┐ ржорзЗржпрж╝рж╛ржж рж╢рзЗрж╖/login page ржПрж╕рзЗржЫрзЗ тАФ response рж╢рзБрж░рзБ: {raw_text[:200]!r}")
                    return []

        all_rows = data.get("aaData", [])
        if all_rows:
            total_rec = data.get("iTotalRecords", "?")
            disp_rec  = data.get("iTotalDisplayRecords", "?")
            logger.info(f"ЁЯУК Provider5: aaData рждрзЗ {len(all_rows)}ржЯрж╛ row ржкрж╛ржУржпрж╝рж╛ ржЧрзЗржЫрзЗ (iTotalRecords={total_rec}, iTotalDisplayRecords={disp_rec}) тАФ sample row0: {all_rows[0]}")
        else:
            logger.info(f"ЁЯУК Provider5: aaData ржЦрж╛рж▓рж┐ (response keys: {list(data.keys())})")

        results = []
        for row in all_rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            timestamp = str(row[0])
            number    = re.sub(r"\D", "", str(row[2]))
            message   = ""
            for field in row[4:]:
                if isinstance(field, str) and len(field) > 3 and field.strip() not in ("$", "", "-"):
                    message = field
                    break
            if not message and len(row) > 5:
                message = str(row[5])
            otp = scraper_extract_otp(message)
            if number and otp:
                results.append({
                    "timestamp": timestamp, "number": number,
                    "range": "", "message": message, "otp": otp,
                })
        if all_rows and not results:
            logger.warning(f"тЪая╕П Provider5: {len(all_rows)}ржЯрж╛ row ржЫрж┐рж▓ ржХрж┐ржирзНрждрзБ ржХрзЛржирзЛржЯрж╛ ржерзЗржХрзЗржЗ valid OTP ржмрзЗрж░ ржХрж░рж╛ ржпрж╛ржпрж╝ржирж┐ тАФ row format ржорж┐рж▓ржЫрзЗ ржирж╛ ржоржирзЗ рж╣ржЪрзНржЫрзЗ")
        return results
    except Exception as e:
        logger.error(f"тЭМ Provider5 fetch error: {e}")
        return []

async def run_provider5_panel(panel: dict, idx: int, app):
    """Provider 5 тАФ session cookie (PHPSESSID) ржнрж┐рждрзНрждрж┐ржХ тАФ рж▓ржЧржЗржи ржХрж░рж╛рж░ ржжрж░ржХрж╛рж░ ржирж╛ржЗ, ржХрзБржХрж┐ ржорзЗржпрж╝рж╛ржж рж╢рзЗрж╖ рж╣рж▓рзЗ ржЕрзНржпрж╛ржбржорж┐ржиржХрзЗ ржирждрзБржи ржХрзБржХрж┐ ржмрж╕рж╛рждрзЗ рж╣ржмрзЗред"""
    target_url    = panel["url"]
    target_host   = panel.get("target_host", "")
    session_cookie = panel["password"]  # ржХрзБржХрж┐ ржнрзНржпрж╛рж▓рзБ password field ржП рж╕рзЗржн ржерж╛ржХрзЗ
    logger.info(f"ЁЯЪА Provider5 Panel #{idx+1} started: {target_url}")
    otp_panel_status[idx] = "running"
    previous_otps = set()

    while True:
        try:
            rows = await _provider5_fetch(target_url, target_host, session_cookie)
            otp_panel_status[idx] = "running"

            for sms in rows:
                otp_id = f"{sms['number']}_{sms['otp']}_{sms['timestamp']}"
                if otp_id in previous_otps:
                    continue
                previous_otps.add(otp_id)
                if len(previous_otps) > 50000:
                    previous_otps = set(list(previous_otps)[-20000:])
                await _handle_scraped_sms(sms, target_url, app, idx)

            await asyncio.sleep(settings.get("panelPollInterval", 1))

        except asyncio.CancelledError:
            otp_panel_status[idx] = "stopped"
            logger.info(f"тП╣я╕П Provider5 Panel #{idx+1} stopped")
            return
        except Exception as e:
            otp_panel_status[idx] = "error"
            logger.error(f"тЭМ Provider5 Panel #{idx+1} error: {e}")
            await asyncio.sleep(30)

def make_panel_task(panel: dict, idx: int, app):
    """panel ржПрж░ type ржЕржирзБржпрж╛ржпрж╝рзА рж╕ржарж┐ржХ runner ржжрж┐ржпрж╝рзЗ task рждрзИрж░рж┐ ржХрж░рзЗред"""
    ptype = panel.get("type")
    if ptype == "provider3":
        return asyncio.create_task(run_provider3_panel(panel, idx, app))
    if ptype == "provider4":
        return asyncio.create_task(run_provider4_panel(panel, idx, app))
    if ptype == "provider5":
        return asyncio.create_task(run_provider5_panel(panel, idx, app))
    return asyncio.create_task(run_panel(panel, idx, app))

def start_all_panels(app):
    rebuild_suffix_index()  # startup ржП index рждрзИрж░рж┐ ржХрж░рзЛ
    panels = load_panels()
    for i, p in enumerate(panels):
        if i not in otp_panel_tasks or otp_panel_tasks[i].done():
            otp_panel_tasks[i] = make_panel_task(p, i, app)
    logger.info(f"ЁЯУб {len(panels)} panel(s) started")

# тФАтФА Admin Panel Callbacks тФАтФА
PANEL_TYPE_LABEL = {
    "masdar_client": "Masdar Client",
    "masdar_agent":  "Masdar Agent",
    "ims_client":    "IMS Client",
    "ims_agent":     "IMS Agent",
    "provider2":     "Provider 2 (Auto Login)",
}

async def cb_admin_panels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    panels = load_panels()
    msg = f"ЁЯУб *OTP Panels*\n\nTotal: *{len(panels)}*\n\n"
    for i, p in enumerate(panels):
        status = otp_panel_status.get(i, "stopped")
        if status == "running":   icon = "ЁЯЯв Running"
        elif status == "error":   icon = "ЁЯФ┤ Login Failed"
        else:                     icon = "тЪл Stopped"
        if p.get('type') == "provider3":
            label = f"Provider 3 ({p.get('subtype', 'ints')})"
        elif p.get('type') == "provider4":
            label = "Provider 4 (API)"
        elif p.get('type') == "provider5":
            label = "Provider 5 (Cookie)"
        else:
            label = PANEL_TYPE_LABEL.get(p.get('type', ''), p.get('type', ''))
        msg += f"*{i+1}.* `{p['url']}`\nЁЯСд `{p['username']}` | ЁЯП╖я╕П {label} | {icon}\n\n"
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("тЮХ Add Panel", callback_data="panel_add:auto", style="primary"),
         InlineKeyboardButton("ЁЯФС Provider 2", callback_data="panel_add:provider2", style="success")],
        [InlineKeyboardButton("ЁЯзй Provider 3", callback_data="panel_add_p3_menu", style="danger"),
         InlineKeyboardButton("ЁЯМР Provider 4", callback_data="panel_add_p4_menu", style="primary")],
        [InlineKeyboardButton("ЁЯНк Provider 5", callback_data="panel_add_p5_menu", style="success")],
        [InlineKeyboardButton("ЁЯУЬ View Logs", callback_data="panel_logs_menu", style="primary")],
        [InlineKeyboardButton("ЁЯЧСя╕П Delete Panel", callback_data="panel_del", style="danger"),
         InlineKeyboardButton("ЁЯФД Restart All",  callback_data="panel_restart", style="success")],
        [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
    ]))

async def cb_panel_logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    panels = load_panels()
    if not panels:
        return await query.edit_message_text(
            "ЁЯУЬ ржХрзЛржирзЛ ржкрзНржпрж╛ржирзЗрж▓ ржпрзЛржЧ ржХрж░рж╛ ржирзЗржЗред",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_panels", style="primary")]])
        )
    rows = []
    row  = []
    for i, p in enumerate(panels):
        label = PANEL_TYPE_LABEL.get(p.get('type', ''), p.get('type', ''))
        if p.get('type') == "provider3":
            label = f"P3-{p.get('subtype','ints')}"
        elif p.get('type') == "provider4":
            label = "P4-API"
        elif p.get('type') == "provider5":
            label = "P5-Cookie"
        row.append(InlineKeyboardButton(f"#{i+1} {label}", callback_data=f"panel_log:{i}", style="primary"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_panels", style="primary")])
    await query.edit_message_text(
        "ЁЯУЬ *ржХрзЛржи ржкрзНржпрж╛ржирзЗрж▓рзЗрж░ рж▓ржЧ ржжрзЗржЦрждрзЗ ржЪрж╛ржУ?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_panel_log_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    idx    = int(query.data.split(":")[1])
    panels = load_panels()
    if idx >= len(panels):
        return await query.edit_message_text("тЭМ ржкрзНржпрж╛ржирзЗрж▓ ржЦрзБржБржЬрзЗ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред")
    p      = panels[idx]
    status = otp_panel_status.get(idx, "stopped")
    icon   = {"running": "ЁЯЯв Running", "error": "ЁЯФ┤ Login Failed"}.get(status, "тЪл Stopped")
    entries = list(panel_recent_log.get(idx, []))

    msg = f"ЁЯУЬ *Panel #{idx+1} Live Log* | {icon}\nЁЯФЧ `{p['url'][:60]}`\n\n"
    if not entries:
        msg += "ржПржЦржирзЛ ржХрзЛржирзЛ OTP/ржирж╛ржорзНржмрж╛рж░ ржЖрж╕рзЗржирж┐ред"
    else:
        for e in entries:
            msg += f"тП▒ `{e['time']}` | ЁЯУЮ +{e['number']} | ЁЯФС `{e['otp']}`\n"

    kb_rows = [[InlineKeyboardButton("ЁЯФД Refresh", callback_data=f"panel_log:{idx}", style="success")]]
    if p.get("type") == "provider5":
        kb_rows.append([InlineKeyboardButton("ЁЯФН Check Session (Cookie)", callback_data=f"panel_check:{idx}", style="danger")])
    kb_rows.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="panel_logs_menu", style="primary")])

    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )

async def _provider5_check_session(panel: dict) -> str:
    """Provider 5 ржПрж░ ржХрзБржХрж┐/рж╕рзЗрж╢ржи ржПржЦржирзЛ ржнрзНржпрж╛рж▓рж┐ржб ржХрж┐ржирж╛ рж╕рж░рж╛рж╕рж░рж┐ ржЪрзЗржХ ржХрж░рзЗ human-readable status рж░рж┐ржЯрж╛рж░рзНржи ржХрж░рзЗред"""
    import aiohttp as _aiohttp
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    target_url     = panel["url"]
    target_host    = panel.get("target_host", "")
    session_cookie = panel["password"]
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        parts      = urlsplit(target_url)
        query_dict = dict(parse_qsl(parts.query, keep_blank_values=True))
        query_dict["fdate1"] = f"{current_date} 00:00:00"
        query_dict["fdate2"] = f"{current_date} 23:59:59"
        final_url = urlunsplit((parts.scheme or "http", parts.netloc or target_host,
                                 parts.path, urlencode(query_dict), ""))
        cookie_header = session_cookie if "=" in session_cookie else f"PHPSESSID={session_cookie}"
        headers = {
            "Host": target_host,
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"http://{target_host}/",
            "Cookie": cookie_header,
        }
        async with _aiohttp.ClientSession() as s:
            async with s.get(final_url, headers=headers, ssl=False, timeout=15) as r:
                status_code = r.status
                raw_text    = await r.text()

        if status_code != 200:
            return f"тЭМ *Session Invalid* тАФ HTTP {status_code} ржПрж╕рзЗржЫрзЗред ржХрзБржХрж┐ expire рж╣ржпрж╝рзЗ ржЧрзЗржЫрзЗ, ржирждрзБржи request ржХржкрж┐ ржХрж░рзЗ ржЖржмрж╛рж░ Provider 5 ржП panel add ржХрж░рзЛред"
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            return f"тЭМ *Session Invalid* тАФ JSON ржПрж░ ржмржжрж▓рзЗ HTML/login page ржПрж╕рзЗржЫрзЗ (ржХрзБржХрж┐ expire)ред\n\nResponse рж╢рзБрж░рзБ:\n`{raw_text[:150]}`"

        total = data.get("iTotalRecords", "N/A")
        rows  = len(data.get("aaData", []))
        return f"тЬЕ *Session Valid!*\n\nрж╕рж╛рж░рзНржнрж╛рж░ ржерзЗржХрзЗ ржарж┐ржХржарж╛ржХ JSON рж░рзЗрж╕ржкржирзНрж╕ ржПрж╕рзЗржЫрзЗред\niTotalRecords: `{total}`\naaData rows: `{rows}`"
    except Exception as e:
        return f"тЪая╕П ржЪрзЗржХ ржХрж░рждрзЗ ржЧрж┐ржпрж╝рзЗ error рж╣ржпрж╝рзЗржЫрзЗ: `{e}`"

async def cb_panel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer("ЁЯФН ржЪрзЗржХ ржХрж░рж╛ рж╣ржЪрзНржЫрзЗ...")
    idx    = int(query.data.split(":")[1])
    panels = load_panels()
    if idx >= len(panels):
        return await query.edit_message_text("тЭМ ржкрзНржпрж╛ржирзЗрж▓ ржЦрзБржБржЬрзЗ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред")
    p = panels[idx]
    if p.get("type") != "provider5":
        return await query.answer("ржПржЗ ржЪрзЗржХ рж╢рзБржзрзБ Provider 5 (Cookie) ржкрзНржпрж╛ржирзЗрж▓рзЗрж░ ржЬржирзНржпред", show_alert=True)

    result = await _provider5_check_session(p)
    await query.edit_message_text(
        f"ЁЯФН *Panel #{idx+1} Session Check*\nЁЯФЧ `{p['url'][:60]}`\n\n{result}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ЁЯФН ржЖржмрж╛рж░ ржЪрзЗржХ ржХрж░рзЛ", callback_data=f"panel_check:{idx}", style="danger")],
            [InlineKeyboardButton("ЁЯФЩ Back", callback_data=f"panel_log:{idx}", style="primary")],
        ])
    )

# тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР Fake OTP Numbers тАФ Admin UI тХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХРтХР
async def cb_fake_otp_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    await _render_fake_otp_menu(query)

async def _render_fake_otp_menu(query):
    msg = f"ЁЯОн *Fake OTP Numbers*\n\nTotal Batches: *{len(fake_otp_batches)}*\n\n"
    rows = []
    if not fake_otp_batches:
        msg += "_ржПржЦржирзЛ ржХрзЛржирзЛ batch ржпрзЛржЧ ржХрж░рж╛ рж╣ржпрж╝ржирж┐ред_"
    else:
        for i, b in enumerate(fake_otp_batches):
            svc    = services.get(b.get("service", "other"), {"icon": "ЁЯУ▒", "name": b.get("service", "other")})
            status = b.get("status", "running")
            icon   = "ЁЯЯв Running" if status == "running" and b.get("numbers") else ("тЪк Completed" if not b.get("numbers") else "тП╣я╕П Stopped")
            msg += (
                f"*Batch #{i+1}* тАФ {svc['icon']} {svc['name']}\n"
                f"ЁЯФв {b.get('digits')} digit | тП▒ max {b.get('max_minutes')} min | "
                f"ЁЯУЛ ржмрж╛ржХрж┐ {len(b.get('numbers', []))}ржЯрж╛ | {icon}\n\n"
            )
            rows.append([InlineKeyboardButton(f"ЁЯЧСя╕П Stop/Delete Batch #{i+1}", callback_data=f"fake_del:{i}", style="danger")])

    rows.append([InlineKeyboardButton("тЮХ Add Batch", callback_data="fake_otp_add", style="success")])
    rows.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")])
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

async def cb_fake_otp_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    rows = []
    row  = []
    for svc_id, svc in services.items():
        row.append(InlineKeyboardButton(f"{svc['icon']} {svc['name']}", callback_data=f"fake_svc:{svc_id}", style="primary"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("тЭМ Cancel", callback_data="fake_otp_menu", style="danger")])
    await query.edit_message_text(
        "ЁЯОн *Add Fake OTP Batch тАФ Step 1/4*\n\nЁЯУ▒ ржХрзЛржи Service-ржПрж░ ржирж╛ржорзЗ fake OTP ржпрж╛ржмрзЗ, ржмрзЗржЫрзЗ ржирж╛ржУ:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_fake_svc_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    sess   = get_session(uid)
    sess["state"]     = "admin_fake_digits"
    sess["fake_data"] = {"service": svc_id}
    await query.edit_message_text(
        "ЁЯОн *Add Fake OTP Batch тАФ Step 2/4*\n\n"
        "ЁЯФв OTP ржХрзЛржб ржХржд ржбрж┐ржЬрж┐ржЯрзЗрж░ рж╣ржмрзЗ? (ржпрзЗржоржи `5`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="fake_otp_menu", style="danger")]])
    )

async def cb_fake_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    idx = int(query.data.split(":")[1])
    if idx >= len(fake_otp_batches):
        return await query.edit_message_text("тЭМ Batch ржЦрзБржБржЬрзЗ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред")
    task = fake_otp_tasks.pop(idx, None)
    if task:
        task.cancel()
    fake_otp_batches.pop(idx)
    save_fake_otp_batches()
    # тФАтФА ржЗржиржбрзЗржХрзНрж╕ рж╢рж┐ржлржЯ рж╣ржУржпрж╝рж╛ржпрж╝ ржмрж╛ржХрж┐ ржЯрж╛рж╕рзНржХржЧрзБрж▓рзЛрж░ ржорзНржпрж╛ржкрж┐ржВ ржарж┐ржХ ржХрж░рж╛ тФАтФА
    new_tasks = {}
    for k, v in fake_otp_tasks.items():
        new_tasks[k - 1 if k > idx else k] = v
    fake_otp_tasks.clear()
    fake_otp_tasks.update(new_tasks)
    await _render_fake_otp_menu(query)

async def cb_admin_global_wa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()

    connected = global_wa_data.get("connected", False)
    enabled   = global_wa_data.get("enabled", False)
    phone     = global_wa_data.get("phone", "N/A")

    status_icon = "ЁЯЯв" if connected else "ЁЯФ┤"
    toggle_icon = "тЬЕ ON" if enabled else "тЭМ OFF"

    msg = (
        f"ЁЯУ▒ *Global WhatsApp System*\n\n"
        f"*Status:* {status_icon} {'Connected' if connected else 'Disconnected'}\n"
        f"*Phone:* `{phone}`\n"
        f"*WA Check:* {toggle_icon}\n\n"
        f"ржПржХржЯрж╛ WhatsApp connect ржХрж░рж▓рзЗ рж╕ржм user ржПрж░ number check рж╣ржмрзЗред"
    )

    buttons = []
    if connected:
        buttons.append([
            InlineKeyboardButton(
                f"{'ЁЯФ┤ Disable' if enabled else 'ЁЯЯв Enable'} WA Check",
                callback_data="global_wa_toggle",
                style="success" if not enabled else "danger"
            ),
            InlineKeyboardButton("ЁЯФМ Disconnect", callback_data="global_wa_disconnect", style="danger")
        ])
    else:
        buttons.append([InlineKeyboardButton("ЁЯУ▒ Connect WhatsApp", callback_data="global_wa_connect", style="primary")])

    buttons.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")])
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_global_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "global_wa_phone"
    await query.edit_message_text(
        "ЁЯУ▒ *Global WhatsApp Connect*\n\n"
        "WhatsApp ржиржорзНржмрж░ ржжрж╛ржУ (country code рж╕рж╣):\n"
        "Example: `8801712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("тЭМ Cancel", callback_data="admin_global_wa", style="danger")
        ]])
    )

async def cb_global_wa_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    global_wa_data["enabled"] = not global_wa_data.get("enabled", False)
    save_global_wa()
    status = "тЬЕ ржЪрж╛рж▓рзБ" if global_wa_data["enabled"] else "тЭМ ржмржирзНржз"
    await query.answer(f"Global WA Check {status}", show_alert=True)
    await cb_admin_global_wa(update, context)

async def cb_global_wa_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wa_uid = global_wa_data.get("uid", "")
    if wa_uid and wa_uid in wa_sessions:
        wa_sessions.pop(wa_uid, None)
    global_wa_data["connected"] = False
    global_wa_data["phone"]     = ""
    global_wa_data["enabled"]   = False
    save_global_wa()
    await query.answer("ЁЯФМ Global WA Disconnected", show_alert=True)
    await cb_admin_global_wa(update, context)

# тФАтФАтФА Global WA handle_text тФАтФАтФА
# (handle_text ржП state "global_wa_phone" handle ржХрж░рж╛ рж╣ржмрзЗ)

async def cb_panel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    await query.answer()
    ptype = query.data.split(":")[1] if ":" in query.data else "masdar_client"
    label = PANEL_TYPE_LABEL.get(ptype, ptype)
    cancel_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")
    ]])

    if ptype == "provider2":
        # тФАтФА Provider 2: ржзрж╛ржкрзЗ ржзрж╛ржкрзЗ ржЬрж┐ржЬрзНржЮрзЗрж╕ ржХрж░ржмрзЗ тАФ Login URL тЖТ SMS URL тЖТ Username тЖТ Password тЖТ ржХрж▓рж╛ржо тФАтФА
        sess = get_session(uid)
        sess["state"]     = "admin_add_p2_loginurl"
        sess["p2_data"]   = {}
        await query.edit_message_text(
            f"тЮХ *Add {label} Panel тАФ Step 1/6*\n\n"
            f"ЁЯФЧ *Login URL* ржжрж┐ржи (ржпрзЗржЦрж╛ржирзЗ username/password ржжрж┐ржпрж╝рзЗ рж▓ржЧржЗржи ржХрж░ржмрзЗ):\n\n"
            f"Example:\n`http://139.99.69.196/login`",
            parse_mode="Markdown",
            reply_markup=cancel_kb
        )
        return

    get_session(uid)["state"]      = "admin_add_panel"
    get_session(uid)["panel_type"] = ptype
    prompt = (
        f"тЮХ *Add {label} Panel*\n\n"
        f"Format: `URL username password`\n\n"
        f"Example:\n`http://139.99.69.196 admin admin123`"
    )
    await query.edit_message_text(prompt, parse_mode="Markdown", reply_markup=cancel_kb)

# тФАтФА Provider 3 тАФ Known Panels (ржЖржЧрзЗ ржерзЗржХрзЗ URL+Type рж╕рзЗржЯ ржХрж░рж╛) + Custom Panel тФАтФА
BUILTIN_PANELS = {
    "ChoiceSMS":   {"url": "http://51.77.52.79/ints",          "ptype": "ints"},
    "FlynSMS":     {"url": "http://91.232.105.47/ints",        "ptype": "ints"},
    "Gaza":        {"url": "http://144.217.71.192/ints",       "ptype": "ints"},
    "GoatPanel":   {"url": "http://167.114.117.67/ints",       "ptype": "ints"},
    "HADI_SMS":    {"url": "http://2.59.169.96/ints",          "ptype": "ints"},
    "ImsPanel":    {"url": "https://www.imssms.org",           "ptype": "ims"},
    "KmSms":       {"url": "http://54.36.173.235/ints",        "ptype": "ints"},
    "Konekta":     {"url": "https://konektapremium.net",       "ptype": "konekta"},
    "MsiSMS":      {"url": "http://145.239.130.45/ints",       "ptype": "ints"},
    "NumberPanel": {"url": "http://51.89.99.105/NumberPanel",  "ptype": "numberpanel"},
    "ProofSMS":    {"url": "http://217.182.195.194/ints",      "ptype": "proofsms"},
    "PurplePanel": {"url": "http://85.195.94.50/sms",          "ptype": "standard"},
    "RoxySMS":     {"url": "http://www.roxysms.net",           "ptype": "roxy"},
    "Seven1Tel":   {"url": "http://94.23.120.156/ints",        "ptype": "ints"},
    "SharkSMS":    {"url": "http://65.109.111.158/ints",       "ptype": "ints"},
    "TrueSMS":     {"url": "https://truesms.net",              "ptype": "standard"},
    "VoiceGate":   {"url": "http://51.89.7.175/sms",           "ptype": "voicegate"},
    "Wolf":        {"url": "http://213.32.24.208/ints",        "ptype": "ints"},
    "GreenSMS":    {"url": "http://139.99.9.4/ints",           "ptype": "ints"},
    "MarkOI":      {"url": "http://51.75.144.178/ints",        "ptype": "ints"},
    "FireSMS":     {"url": "http://54.39.104.241/ints",        "ptype": "ints"},
    "SniperPanel": {"url": "http://135.125.222.224/ints",      "ptype": "ints"},
    "MAIT":        {"url": "http://168.119.13.175/ints",       "ptype": "ints"},
    "TimeSMS":     {"url": "https://www.timesms.org",          "ptype": "timesms"},
}

PROVIDER3_TYPES = ["ints", "ims", "konekta", "standard", "proofsms",
                   "roxy", "voicegate", "numberpanel", "timesms"]

async def cb_panel_add_p3_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    rows = []
    row  = []
    for name in sorted(BUILTIN_PANELS.keys()):
        row.append(InlineKeyboardButton(name, callback_data=f"p3_builtin:{name}", style="success"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("тЬПя╕П Custom Panel", callback_data="panel_add_p3_custom", style="primary")])
    rows.append([InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")])
    await query.edit_message_text(
        "ЁЯзй *Add Provider 3 Panel*\n\n"
        "ржЪрзЗржирж╛ ржкрзНржпрж╛ржирзЗрж▓ рж╣рж▓рзЗ ржирж┐ржЪ ржерзЗржХрзЗ ржирж╛ржо ржмрзЗржЫрзЗ ржирж╛ржУ (URL+Type ржЖржЧрзЗ ржерзЗржХрзЗржЗ рж╕рзЗржЯ ржХрж░рж╛ ржерж╛ржХржмрзЗ, рж╢рзБржзрзБ username/password ржжрж┐рждрзЗ рж╣ржмрзЗ)ред\n\n"
        "рж▓рж┐рж╕рзНржЯрзЗ ржирж╛ ржерж╛ржХрж▓рзЗ *тЬПя╕П Custom Panel* ржЪрж╛ржкрзЛред",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_p3_builtin_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    name = query.data.split(":", 1)[1]
    info = BUILTIN_PANELS.get(name)
    if not info:
        return await query.edit_message_text("тЭМ ржкрзНржпрж╛ржирзЗрж▓ ржЦрзБржБржЬрзЗ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред")
    sess = get_session(uid)
    sess["state"]   = "admin_add_p3_username"
    sess["p3_data"] = {"subtype": info["ptype"], "url": info["url"], "builtin_name": name}
    await query.edit_message_text(
        f"ЁЯзй *Add {name} ({info['ptype']}) тАФ Step 1/2*\n\n"
        f"ЁЯФЧ URL: `{info['url']}` (auto)\n\n"
        f"ЁЯСд *Username* ржжрж┐ржи:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")]])
    )

async def cb_panel_add_p3_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    rows = []
    row  = []
    for pt in PROVIDER3_TYPES:
        row.append(InlineKeyboardButton(pt, callback_data=f"p3_type:{pt}", style="primary"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")])
    await query.edit_message_text(
        "тЬПя╕П *Custom Panel*\n\n"
        "рждрзЛржорж╛рж░ ржкрзНржпрж╛ржирзЗрж▓ржЯрж╛ ржХрзЛржи ржЯрж╛ржЗржкрзЗрж░ рж╕рзЗржЯрж╛ ржмрзЗржЫрзЗ ржирж╛ржУ:\n\n"
        "ЁЯСЙ ржмрзЗрж╢рж┐рж░ржнрж╛ржЧ ржкрзНржпрж╛ржирзЗрж▓ *ints* ржЯрж╛ржЗржк тАФ ржирж╛ ржЬрж╛ржирж▓рзЗ ржкрзНрж░ржержорзЗ *ints* ржжрж┐ржпрж╝рзЗ ржЯрзНрж░рж╛ржЗ ржХрж░рзЛред",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_p3_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    ptype = query.data.split(":")[1]
    sess  = get_session(uid)
    sess["state"]   = "admin_add_p3_url"
    sess["p3_data"] = {"subtype": ptype}
    await query.edit_message_text(
        f"ЁЯзй *Add Provider 3 ({ptype}) тАФ Step 1/3*\n\n"
        f"ЁЯФЧ *Panel URL* ржжрж┐ржи:\n\n"
        f"Example:\n`http://51.77.52.79/ints`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")]])
    )

# тФАтФА Provider 4 тАФ Power SMS Panel ржПрж░ ржирж┐ржЬрж╕рзНржм API (base URL + API token, login рж▓рж╛ржЧрзЗ ржирж╛) тФАтФА
async def cb_panel_add_p4_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"]   = "admin_add_p4_url"
    sess["p4_data"] = {}
    await query.edit_message_text(
        "ЁЯМР *Add Provider 4 тАФ Step 1/2*\n\n"
        "ЁЯФЧ *Base URL* ржжрж┐ржи:\n\n"
        "Example:\n`https://your-power-sms-panel.com`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")]])
    )

# тФАтФА Provider 5 тАФ Session Cookie (PHPSESSID) ржнрж┐рждрзНрждрж┐ржХ, рж▓ржЧржЗржи ржХрж░рж╛рж░ ржжрж░ржХрж╛рж░ ржирж╛ржЗ тФАтФА
async def cb_panel_add_p5_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("тЭМ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_add_p5_raw"
    await query.edit_message_text(
        "ЁЯНк *Add Provider 5 (Cookie) тАФ Raw Request*\n\n"
        "ржмрзНрж░рж╛ржЙржЬрж╛рж░рзЗрж░ Network Tab ржерзЗржХрзЗ ржкрзБрж░рзЛ рж░рж┐ржХрзЛржпрж╝рзЗрж╕рзНржЯ ржмрзНрж▓ржХржЯрж╛ (GET рж▓рж╛ржЗржи + Host + Cookie рж╕рж╣) "
        "рж╣рзБржмрж╣рзБ ржХржкрж┐ ржХрж░рзЗ **ржПржХржмрж╛рж░рзЗржЗ** ржкрзЗрж╕рзНржЯ ржХрж░рзЗ ржжрж╛ржУ тАФ ржмржЯ ржирж┐ржЬрзЗ ржерзЗржХрзЗржЗ URL, Host ржЖрж░ Cookie ржмрзЗрж░ ржХрж░рзЗ ржирж┐ржмрзЗред\n\n"
        "Example:\n"
        "```\n"
        "GET /ints/agent/res/data_smscdr.php?fdate1=...&csstr=... HTTP/1.1\n"
        "Host: 168.119.13.175\n"
        "...\n"
        "Cookie: PHPSESSID=abc123...\n"
        "```",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data="admin_panels", style="danger")]])
    )

def _parse_raw_http_request(raw_text: str):
    """ржмрзНрж░рж╛ржЙржЬрж╛рж░ ржерзЗржХрзЗ ржХржкрж┐ ржХрж░рж╛ raw HTTP request ржмрзНрж▓ржХ ржерзЗржХрзЗ URL, Host, Cookie ржмрзЗрж░ ржХрж░рзЗред
    рж░рж┐ржЯрж╛рж░рзНржи ржХрж░рзЗ (full_url, host, cookie_header) тАФ ржХрж┐ржЫрзБ ржирж╛ ржкрзЗрж▓рзЗ Noneред"""
    lines = raw_text.strip().splitlines()
    if not lines:
        return None
    m = re.match(r'^(?:GET|POST)\s+(\S+)\s+HTTP', lines[0].strip(), re.IGNORECASE)
    if not m:
        return None
    path = m.group(1)

    host   = None
    cookie = None
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("host:"):
            host = line.split(":", 1)[1].strip()
        elif low.startswith("cookie:"):
            cookie = line.split(":", 1)[1].strip()

    if not host or not cookie:
        return None

    full_url = f"http://{host}{path}"
    return full_url, host, cookie



async def cb_panel_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    panels = load_panels()
    if not panels:
        return await query.edit_message_text("тЭМ ржХрзЛржирзЛ panel ржирзЗржЗред",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_panels")]]))
    buttons = [[InlineKeyboardButton(f"ЁЯЧСя╕П {i+1}. {p['url']}", callback_data=f"panel_del_confirm:{i}")]
               for i, p in enumerate(panels)]
    buttons.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_panels", style="primary")])
    await query.edit_message_text("ЁЯЧСя╕П *ржХрзЛржи panel delete ржХрж░ржмрзЗ?*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_panel_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx    = int(query.data.split(":")[1])
    panels = load_panels()
    if 0 <= idx < len(panels):
        removed = panels.pop(idx)
        save_panels(panels)
        if idx in otp_panel_tasks and not otp_panel_tasks[idx].done():
            otp_panel_tasks[idx].cancel()
            otp_panel_tasks.pop(idx, None)
        await query.edit_message_text(f"тЬЕ *Deleted:* `{removed['url']}`", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_panels")]]))

async def cb_panel_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ЁЯФД Restarting...")
    for task in otp_panel_tasks.values():
        if not task.done():
            task.cancel()
    otp_panel_tasks.clear()
    start_all_panels(context.application)
    await query.edit_message_text("тЬЕ *All panels restarted!*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_panels")]]))

PE_EMOJI_LIST = [
    "ЁЯУ▒",
    "ЁЯФ┤",
    "ЁЯУК",
    "тШО",
    "ЁЯУз",
    "ЁЯФР",
    "ЁЯТ░",
    "ЁЯТ╕",
    "ЁЯСе",
    "ЁЯТм",
    "1я╕ПтГг",
    "2я╕ПтГг",
    "3я╕ПтГг",
    "тЬЕ",
    "ЁЯУв",
    "ЁЯУЛ",
    "тЮХ",
    "ЁЯУд",
    "ЁЯЧС",
    "ЁЯФз",
    "ЁЯМН",
    "тЪЩ",
    "ЁЯСЫ",
    "ЁЯУб",
    "ЁЯОн",
    "ЁЯЪк",
    "ЁЯФЩ",
    "ЁЯУи",
    "ЁЯФД",
    "ЁЯФЧ",
    "ЁЯЯг",
    "ЁЯЯа",
    "тЭМ",
    "ЁЯУм",
    "ЁЯЖХ",
    "ЁЯУШ",
    "ЁЯУ╕",
    "ЁЯФН",
    "ЁЯУЮ",
    "тП▒",
    "ЁЯТ╡",
    "ЁЯПз",
    "ЁЯУе",
    "тЮЦ",
    "ЁЯЫа",
    "ЁЯФС",
    "ЁЯзй",
    "ЁЯМР",
    "ЁЯНк",
    "ЁЯУЬ",
    "ЁЯФМ",
    "тЬП",
    "тЬи",
    "ЁЯЯв",
]
PE_PAGE_SIZE = 16

def _pe_is_admin(uid) -> bool:
    return bool(get_session(uid).get("is_admin")) or is_admin(str(uid))

def _pe_cfg_ensure() -> dict:
    cfg = settings.get("premiumEmoji")
    if not isinstance(cfg, dict):
        cfg = {"enabled": False, "map": {}}
        settings["premiumEmoji"] = cfg
    cfg.setdefault("enabled", False)
    if not isinstance(cfg.get("map"), dict):
        cfg["map"] = {}
    return cfg

async def _pe_edit(query, text, kb):
    try:
        await query.edit_message_text(text, reply_markup=kb)
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"pe edit: {e}")

async def _pe_show_menu(query, uid):
    sess = get_session(uid)
    sess["state"] = None
    sess["data"] = None
    cfg = _pe_cfg_ensure()
    done = sum(1 for k in PE_EMOJI_LIST if cfg["map"].get(k))
    on = bool(cfg["enabled"])
    forced_off = os.environ.get("PREMIUM_EMOJI_OFF") == "1"
    text = (
        "тЬи Premium Emoji\n\n"
        f"рж╕рзНржЯрзНржпрж╛ржЯрж╛рж╕: {'ЁЯЯв ON' if on else 'ЁЯФ┤ OFF'}\n"
        f"рж╕рзЗржЯ ржХрж░рж╛ ржЗржорзЛржЬрж┐: {done}/{len(PE_EMOJI_LIST)}\n\n"
        "ON ржерж╛ржХрж▓рзЗ ржмрж╛ржЯржирзЗ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржжрзЗржЦрж╛ржмрзЗ, OFF ржерж╛ржХрж▓рзЗ рж╕рж╛ржзрж╛рж░ржг ржЗржорзЛржЬрж┐ред\n"
        "(ржмржЯрзЗрж░ ржорж╛рж▓рж┐ржХрзЗрж░ Telegram Premium ржерж╛ржХрждрзЗ рж╣ржмрзЗред ржпрж╛ржжрзЗрж░ Premium ржирзЗржЗ рждрж╛рж░рж╛ рж╕рж╛ржзрж╛рж░ржг ржЗржорзЛржЬрж┐ ржжрзЗржЦржмрзЗред)"
    )
    if forced_off:
        text += "\n\nтЪая╕П PREMIUM_EMOJI_OFF=1 рж╕рзЗржЯ ржХрж░рж╛ ржЖржЫрзЗ, рждрж╛ржЗ ON ржХрж░рж▓рзЗржУ ржЪрж╛рж▓рзБ рж╣ржмрзЗ ржирж╛ред"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ЁЯФ┤ ржмржирзНржз ржХрж░рзБржи (OFF)" if on else "ЁЯЯв ржЪрж╛рж▓рзБ ржХрж░рзБржи (ON)",
                              callback_data="pe_toggle", style="danger" if on else "success")],
        [InlineKeyboardButton("ЁЯУЛ ржЗржорзЛржЬрж┐ рж╕рзЗржЯ ржХрж░рзБржи", callback_data="pe_list:0", style="primary")],
        [InlineKeyboardButton("ЁЯЧСя╕П рж╕ржм ржЗржорзЛржЬрж┐ ржорзБржЫрзБржи", callback_data="pe_reset", style="danger")],
        [InlineKeyboardButton("ЁЯФЩ Back", callback_data="admin_back", style="primary")],
    ])
    await _pe_edit(query, text, kb)

async def cb_pe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    await query.answer()
    await _pe_show_menu(query, uid)

async def cb_pe_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    cfg = _pe_cfg_ensure()
    if not cfg["enabled"] and not cfg["map"]:
        return await query.answer("ржЖржЧрзЗ ржЕржирзНрждржд ржПржХржЯрж╛ ржЗржорзЛржЬрж┐ рж╕рзЗржЯ ржХрж░рзБржиред", show_alert=True)
    cfg["enabled"] = not cfg["enabled"]
    save_settings()
    await query.answer("ЁЯЯв ON" if cfg["enabled"] else "ЁЯФ┤ OFF")
    await _pe_show_menu(query, uid)

async def cb_pe_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    await query.answer()
    sess = get_session(uid)
    sess["state"] = None
    sess["data"] = None
    cfg = _pe_cfg_ensure()
    total_pages = (len(PE_EMOJI_LIST) + PE_PAGE_SIZE - 1) // PE_PAGE_SIZE
    page = max(0, min(int(query.data.split(":")[1]), total_pages - 1))
    start = page * PE_PAGE_SIZE
    rows, row = [], []
    for i, key in enumerate(PE_EMOJI_LIST[start:start + PE_PAGE_SIZE]):
        mark = "тЬЕ" if cfg["map"].get(key) else "тЮЦ"
        row.append(InlineKeyboardButton(f"{key} {mark}", callback_data=f"pe_set:{start + i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("тЧАя╕П Prev", callback_data=f"pe_list:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next тЦ╢я╕П", callback_data=f"pe_list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("ЁЯУж ржПржЗ ржкрзЗржЬ ржПржХрж╕рж╛ржерзЗ рж╕рзЗржЯ ржХрж░рзБржи", callback_data=f"pe_bulk:{page}", style="success")])
    rows.append([InlineKeyboardButton("ЁЯФЩ Back", callback_data="pe_menu", style="primary")])
    text = (
        f"тЬи Premium Emoji тАФ ржкрзЗржЬ {page + 1}/{total_pages}\n\n"
        "тЬЕ = рж╕рзЗржЯ ржХрж░рж╛ ржЖржЫрзЗ, тЮЦ = рж╕рзЗржЯ ржХрж░рж╛ ржирзЗржЗ\n"
        "ржпрзЗржЯрж╛ рж╕рзЗржЯ ржХрж░рждрзЗ ржЪрж╛ржи рждрж╛рж░ ржмрж╛ржЯржирзЗ ржЪрж╛ржкрзБржиред"
    )
    await _pe_edit(query, text, InlineKeyboardMarkup(rows))

async def cb_pe_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    await query.answer()
    idx = int(query.data.split(":")[1])
    if idx < 0 or idx >= len(PE_EMOJI_LIST):
        return
    sess = get_session(uid)
    sess["state"] = "pe_set"
    sess["data"] = {"idx": idx}
    key = PE_EMOJI_LIST[idx]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data=f"pe_list:{idx // PE_PAGE_SIZE}", style="danger")]])
    await _pe_edit(query, f"{key} ржПрж░ ржЬрж╛ржпрж╝ржЧрж╛ржпрж╝ ржпрзЗ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржмрж╕рж╛рждрзЗ ржЪрж╛ржи, рж╕рзЗржЯрж╛ ржПржЦржи ржкрж╛ржарж╛ржиред\n\n(рж╢рзБржзрзБ ржПржХржЯрж╛ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐, рж╕рж╛ржерзЗ ржЕржирзНржп ржХрж┐ржЫрзБ рж▓рж┐ржЦржмрзЗржи ржирж╛ред)", kb)

async def cb_pe_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    await query.answer()
    page = int(query.data.split(":")[1])
    items = PE_EMOJI_LIST[page * PE_PAGE_SIZE:(page + 1) * PE_PAGE_SIZE]
    if not items:
        return
    sess = get_session(uid)
    sess["state"] = "pe_bulk"
    sess["data"] = {"page": page}
    lines = "\n".join(f"{n}. {k}" for n, k in enumerate(items, 1))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("тЭМ Cancel", callback_data=f"pe_list:{page}", style="danger")]])
    await _pe_edit(
        query,
        f"ржирж┐ржЪрзЗрж░ ржХрзНрж░ржорзЗ {len(items)}ржЯрж╛ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржПржХржЯрж╛ ржорзЗрж╕рзЗржЬрзЗ ржкрж╛ржарж╛ржи (ржорж╛ржЭрзЗ рж▓рзЗржЦрж╛ ржмрж╛ рж╕рзНржкрзЗрж╕ ржирж╛ ржжрж┐рж▓рзЗржУ ржЪрж▓ржмрзЗ):\n\n{lines}\n\n"
        "ржХржо ржкрж╛ржарж╛рж▓рзЗ рж╢рзБрж░рзБ ржерзЗржХрзЗ ржпрждржЧрзБрж▓рзЛ ржкрж╛ржарж╛ржмрзЗржи рждрждржЧрзБрж▓рзЛржЗ рж╕рзЗржЯ рж╣ржмрзЗред",
        kb,
    )

async def cb_pe_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("тЬЕ рж╣рзНржпрж╛ржБ, ржорзБржЫрзБржи", callback_data="pe_reset_yes", style="danger")],
        [InlineKeyboardButton("ЁЯФЩ Back", callback_data="pe_menu", style="primary")],
    ])
    await _pe_edit(query, "рж╕рзЗржЯ ржХрж░рж╛ рж╕ржм ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржорзБржЫрзЗ ржлрзЗрж▓ржмрзЗржи? (ржлрж┐ржЪрж╛рж░ржЯрж╛ржУ OFF рж╣ржпрж╝рзЗ ржпрж╛ржмрзЗ)", kb)

async def cb_pe_reset_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("тЭМ Admin only", show_alert=True)
    cfg = _pe_cfg_ensure()
    cfg["map"] = {}
    cfg["enabled"] = False
    save_settings()
    await query.answer("ржорзБржЫрзЗ ржлрзЗрж▓рж╛ рж╣ржпрж╝рзЗржЫрзЗ")
    await _pe_show_menu(query, uid)

async def _pe_receive(update: Update, sess: dict):
    """ржЕрзНржпрж╛ржбржорж┐ржи ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржкрж╛ржарж╛рж▓рзЗ рж╕рзЗржЯрж╛рж░ ID рж╕рзЗржн ржХрж░рзЗред"""
    msg = update.message
    ents = [e for e in (msg.entities or [])
            if getattr(e, "type", None) == "custom_emoji" and getattr(e, "custom_emoji_id", None)]
    if not ents:
        return await msg.reply_text("тЭМ ржХрзЛржирзЛ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржкрж╛ржУржпрж╝рж╛ ржпрж╛ржпрж╝ржирж┐ред рж╕рж╛ржзрж╛рж░ржг ржЗржорзЛржЬрж┐ ржиржпрж╝, ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ ржкрж╛ржарж╛ржиред")
    cfg = _pe_cfg_ensure()
    data = sess.get("data") or {}
    if sess.get("state") == "pe_set":
        idx = int(data.get("idx", 0))
        key = PE_EMOJI_LIST[idx]
        cfg["map"][key] = ents[0].custom_emoji_id
        save_settings()
        sess["state"] = None
        sess["data"] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ рждрж╛рж▓рж┐ржХрж╛ржпрж╝ ржлрж┐рж░рзБржи", callback_data=f"pe_list:{idx // PE_PAGE_SIZE}", style="primary")]])
        return await msg.reply_text(f"тЬЕ {key} ржПрж░ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ рж╕рзЗржЯ рж╣ржпрж╝рзЗржЫрзЗред", reply_markup=kb)
    page = int(data.get("page", 0))
    items = PE_EMOJI_LIST[page * PE_PAGE_SIZE:(page + 1) * PE_PAGE_SIZE]
    if len(ents) > len(items):
        return await msg.reply_text(f"тЭМ ржПржЗ ржкрзЗржЬрзЗ ржорж╛рждрзНрж░ {len(items)}ржЯрж╛ ржЗржорзЛржЬрж┐ ржЖржЫрзЗ, ржЖржкржирж┐ {len(ents)}ржЯрж╛ ржкрж╛ржарж┐ржпрж╝рзЗржЫрзЗржиред ржЖржмрж╛рж░ ржкрж╛ржарж╛ржиред")
    for key, e in zip(items, ents):
        cfg["map"][key] = e.custom_emoji_id
    save_settings()
    sess["state"] = None
    sess["data"] = None
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("ЁЯФЩ рждрж╛рж▓рж┐ржХрж╛ржпрж╝ ржлрж┐рж░рзБржи", callback_data=f"pe_list:{page}", style="primary")]])
    extra = "" if len(ents) == len(items) else f"\n(ржмрж╛ржХрж┐ {len(items) - len(ents)}ржЯрж╛ рж╕рзЗржЯ ржХрж░рж╛ рж╣ржпрж╝ржирж┐)"
    return await msg.reply_text(f"тЬЕ {len(ents)}ржЯрж╛ ржкрзНрж░рж┐ржорж┐ржпрж╝рж╛ржо ржЗржорзЛржЬрж┐ рж╕рзЗржЯ рж╣ржпрж╝рзЗржЫрзЗред{extra}", reply_markup=kb)

async def cmd_pe_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return
    cfg = _pe_cfg_ensure()
    cfg["enabled"] = False
    save_settings()
    await update.message.reply_text("тЬЕ Premium Emoji ржмржирзНржз (OFF) ржХрж░рж╛ рж╣ржпрж╝рзЗржЫрзЗред")

# тФАтФАтФА Main тФАтФАтФА
def main():
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("adminlogin", cmd_adminlogin))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("pe_off", cmd_pe_off))

    app.add_handler(MessageHandler(filters.Regex("^(?:тШОя╕П |ЁЯУЮ )?Get Numbers?$"), handle_get_numbers))
    app.add_handler(MessageHandler(filters.Regex("^(?:ЁЯУз.*|Get Tempmail)$"), handle_tempmail))
    app.add_handler(MessageHandler(filters.Regex("^(?:ЁЯФР.*|2FA)$"), handle_2fa))
    app.add_handler(MessageHandler(filters.Regex("^(?:ЁЯТ░ )?Balances$"), handle_balance))
    app.add_handler(MessageHandler(filters.Regex("^(?:ЁЯТ╕ )?Withdraw$"), handle_withdraw))
    app.add_handler(MessageHandler(filters.Regex("^(?:ЁЯСе )?Referral$"), handle_referral))
    app.add_handler(MessageHandler(filters.Regex("^(?:ЁЯТм )?Support$"), handle_support))

    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_document))

    app.add_handler(CallbackQueryHandler(cb_verify, pattern="^verify_user$"))
    app.add_handler(CallbackQueryHandler(cb_select_service, pattern="^svc:"))
    app.add_handler(CallbackQueryHandler(cb_select_country, pattern="^cc:"))
    app.add_handler(CallbackQueryHandler(cb_new_numbers, pattern="^newnum:"))
    app.add_handler(CallbackQueryHandler(cb_back_services, pattern="^back_services$"))

    app.add_handler(CallbackQueryHandler(cb_start_withdraw, pattern="^start_withdraw$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_method, pattern="^wm:"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_amount, pattern="^wa:"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_cancel, pattern="^w_cancel$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_confirm, pattern="^w_confirm$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_history, pattern="^withdraw_history$"))
    app.add_handler(CallbackQueryHandler(cb_goto_main, pattern="^goto_main$"))

    app.add_handler(CallbackQueryHandler(cb_wa_connect, pattern="^wa_connect$"))
    app.add_handler(CallbackQueryHandler(cb_wa_status, pattern="^wa_status$"))
    app.add_handler(CallbackQueryHandler(cb_wa_disconnect, pattern="^wa_disconnect$"))

    app.add_handler(CallbackQueryHandler(cb_tm_create, pattern="^tm_create$"))
    app.add_handler(CallbackQueryHandler(cb_tm_inbox, pattern="^tm_inbox$"))
    app.add_handler(CallbackQueryHandler(cb_tm_show, pattern="^tm_show$"))
    app.add_handler(CallbackQueryHandler(cb_tm_delete, pattern="^tm_delete$"))

    app.add_handler(CallbackQueryHandler(cb_totp_service, pattern="^totp:"))
    app.add_handler(CallbackQueryHandler(cb_totp_back, pattern="^totp_back$"))
    app.add_handler(CallbackQueryHandler(cb_totp_refresh, pattern="^totp_r:"))

    app.add_handler(CallbackQueryHandler(cb_ref_stats, pattern="^ref_stats$"))

    app.add_handler(CallbackQueryHandler(cb_admin_stock, pattern="^admin_stock$"))
    app.add_handler(CallbackQueryHandler(cb_admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(cb_admin_otp_log, pattern="^admin_otp_log$"))
    app.add_handler(CallbackQueryHandler(cb_admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(cb_admin_settings, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(cb_admin_toggle_verify, pattern="^as_toggle_verify$"))
    app.add_handler(CallbackQueryHandler(cb_admin_toggle_withdraw, pattern="^as_toggle_withdraw$"))
    app.add_handler(CallbackQueryHandler(cb_as_count, pattern="^as_count$"))
    app.add_handler(CallbackQueryHandler(cb_as_cooldown, pattern="^as_cooldown$"))
    app.add_handler(CallbackQueryHandler(cb_as_price, pattern="^as_price$"))
    app.add_handler(CallbackQueryHandler(cb_as_minw, pattern="^as_minw$"))
    app.add_handler(CallbackQueryHandler(cb_as_referral_commission, pattern="^as_referral_commission$"))
    app.add_handler(CallbackQueryHandler(cb_as_panel_interval, pattern="^as_panel_interval$"))
    app.add_handler(CallbackQueryHandler(cb_as_queue_interval, pattern="^as_queue_interval$"))
    app.add_handler(CallbackQueryHandler(cb_as_queue_expiry, pattern="^as_queue_expiry$"))
    app.add_handler(CallbackQueryHandler(cb_admin_referral_stats, pattern="^admin_referral_stats$"))
    app.add_handler(CallbackQueryHandler(cb_admin_add_numbers, pattern="^admin_add_numbers$"))
    app.add_handler(CallbackQueryHandler(cb_admin_withdrawals, pattern="^admin_withdrawals$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_approve, pattern="^wadm_approve:"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_reject, pattern="^wadm_reject:"))
    app.add_handler(CallbackQueryHandler(cb_admin_balance_manage, pattern="^admin_balance_manage$"))
    app.add_handler(CallbackQueryHandler(cb_bal_add, pattern="^bal_add$"))
    app.add_handler(CallbackQueryHandler(cb_bal_deduct, pattern="^bal_deduct$"))
    app.add_handler(CallbackQueryHandler(cb_bal_reset, pattern="^bal_reset$"))
    app.add_handler(CallbackQueryHandler(cb_admin_country_prices, pattern="^admin_country_prices$"))
    app.add_handler(CallbackQueryHandler(cb_admin_manage_countries, pattern="^admin_manage_countries$"))
    app.add_handler(CallbackQueryHandler(cb_country_list, pattern="^country_list$"))
    app.add_handler(CallbackQueryHandler(cb_country_add, pattern="^country_add$"))
    app.add_handler(CallbackQueryHandler(cb_admin_manage_services, pattern="^admin_manage_services$"))
    app.add_handler(CallbackQueryHandler(cb_svc_list, pattern="^svc_list$"))
    app.add_handler(CallbackQueryHandler(cb_svc_add, pattern="^svc_add$"))
    app.add_handler(CallbackQueryHandler(cb_admin_upload, pattern="^admin_upload$"))
    app.add_handler(CallbackQueryHandler(cb_upload_svc, pattern="^upload_svc:"))
    app.add_handler(CallbackQueryHandler(cb_admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(cb_del_confirm, pattern="^del_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_del_exec, pattern="^del_exec:"))
    app.add_handler(CallbackQueryHandler(cb_admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(cb_admin_cancel, pattern="^admin_cancel$"))
    app.add_handler(CallbackQueryHandler(cb_admin_logout, pattern="^admin_logout$"))
    app.add_handler(CallbackQueryHandler(cb_pe_menu, pattern="^pe_menu$"))
    app.add_handler(CallbackQueryHandler(cb_pe_toggle, pattern="^pe_toggle$"))
    app.add_handler(CallbackQueryHandler(cb_pe_list, pattern=r"^pe_list:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pe_set, pattern=r"^pe_set:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pe_bulk, pattern=r"^pe_bulk:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pe_reset, pattern="^pe_reset$"))
    app.add_handler(CallbackQueryHandler(cb_pe_reset_yes, pattern="^pe_reset_yes$"))

    app.add_handler(CallbackQueryHandler(cb_admin_global_wa, pattern="^admin_global_wa$"))
    app.add_handler(CallbackQueryHandler(cb_global_wa_connect, pattern="^global_wa_connect$"))
    app.add_handler(CallbackQueryHandler(cb_global_wa_toggle, pattern="^global_wa_toggle$"))
    app.add_handler(CallbackQueryHandler(cb_global_wa_disconnect, pattern="^global_wa_disconnect$"))
    app.add_handler(CallbackQueryHandler(cb_admin_panels, pattern="^admin_panels$"))
    app.add_handler(CallbackQueryHandler(cb_panel_add, pattern="^panel_add:"))
    app.add_handler(CallbackQueryHandler(cb_panel_add_p3_menu, pattern="^panel_add_p3_menu$"))
    app.add_handler(CallbackQueryHandler(cb_panel_add_p4_menu, pattern="^panel_add_p4_menu$"))
    app.add_handler(CallbackQueryHandler(cb_panel_add_p5_menu, pattern="^panel_add_p5_menu$"))
    app.add_handler(CallbackQueryHandler(cb_panel_logs_menu, pattern="^panel_logs_menu$"))
    app.add_handler(CallbackQueryHandler(cb_panel_log_view, pattern="^panel_log:"))
    app.add_handler(CallbackQueryHandler(cb_panel_check, pattern="^panel_check:"))
    app.add_handler(CallbackQueryHandler(cb_fake_otp_menu, pattern="^fake_otp_menu$"))
    app.add_handler(CallbackQueryHandler(cb_fake_otp_add, pattern="^fake_otp_add$"))
    app.add_handler(CallbackQueryHandler(cb_fake_svc_select, pattern="^fake_svc:"))
    app.add_handler(CallbackQueryHandler(cb_fake_del, pattern="^fake_del:"))
    app.add_handler(CallbackQueryHandler(cb_p3_builtin_select, pattern="^p3_builtin:"))
    app.add_handler(CallbackQueryHandler(cb_panel_add_p3_custom, pattern="^panel_add_p3_custom$"))
    app.add_handler(CallbackQueryHandler(cb_p3_type_select, pattern="^p3_type:"))
    app.add_handler(CallbackQueryHandler(cb_panel_del, pattern="^panel_del$"))
    app.add_handler(CallbackQueryHandler(cb_panel_del_confirm, pattern="^panel_del_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_panel_restart, pattern="^panel_restart$"))

    app.add_handler(MessageHandler(filters.Chat(OTP_GROUP_ID) & ~filters.COMMAND, handle_otp_group_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text))

    # тФАтФА Real-time group member change (leave/join) тФАтФА
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    async def post_init(application):
        global _tg_app
        _tg_app = application
        asyncio.create_task(scheduled_membership_check(application))
        asyncio.create_task(green_api_monitor(application))
        asyncio.create_task(dm_retry_worker(application))  # тФАтФА rate-limit ржП miss рж╣ржУржпрж╝рж╛ DM ржкрж░рзЗ ржкрж╛ржарж╛ржирзЛрж░ worker тФАтФА
        await start_http_server()
        start_all_panels(application)  # тФАтФА OTP Panels рж╢рзБрж░рзБ ржХрж░рзЛ тФАтФА
        start_all_fake_otp_batches(application)  # тФАтФА Fake OTP batches рж╢рзБрж░рзБ ржХрж░рзЛ тФАтФА

    app.post_init = post_init

    logger.info("="*50)
    logger.info("ЁЯЪА Starting Earning Hub Bot (Python)...")
    logger.info(f"ЁЯУв Main Channel: {MAIN_CHANNEL_ID}")
    logger.info(f"ЁЯТм Chat Group: {CHAT_GROUP_ID}")
    logger.info(f"ЁЯУи OTP Group: {OTP_GROUP_ID}")
    logger.info("="*50)

    app.run_polling(allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"])

if __name__ == "__main__":
    main()
