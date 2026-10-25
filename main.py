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


# ─── Premium Emoji (বাটনে Custom Emoji) ───
# settings["premiumEmoji"] = {"enabled": bool, "map": {সাধারণ_ইমোজি: custom_emoji_id}}
# ON থাকলে বাটনের শুরুর ইমোজি প্রিমিয়াম ইমোজি দিয়ে বদলে যাবে, OFF হলে আগের মতোই।
# জরুরি বন্ধ করতে: Railway Variables এ PREMIUM_EMOJI_OFF=1 দিন, অথবা অ্যাডমিন হিসেবে /pe_off পাঠান।
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
    """বাটনের লেখার শুরুতে map-এর ইমোজি থাকলে (custom_emoji_id, বাকি লেখা) ফেরত দেয়।"""
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

# ─── Logging ───
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Configuration ───
BOT_TOKEN = "7907217678:AAHAmCLtMKr0JLK4g0b0cNX965nFtsBMXy8"
ADMIN_PASSWORD = "sadhin232134"

MAIN_CHANNEL     = "@earning_hub_official_channel"
MAIN_CHANNEL_URL = "https://t.me/earning_hub_official_channel"
MAIN_CHANNEL_ID  = -1003543718769
CHAT_GROUP       = "https://t.me/earning_hub_number_channel"
CHAT_GROUP_ID    = -1003875142184
OTP_GROUP        = "https://t.me/EarningHub_otp"
OTP_GROUP_ID     = -1003247504066

# ─── Baileys API (WhatsApp) ───
BAILEYS_URL = os.environ.get("BAILEYS_URL", "http://localhost:3000")

# ─── Data Directory ───
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(os.path.abspath(__file__)))
logger.info(f"📁 Data Directory: {DATA_DIR}")

# ─── File Paths ───
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

# ─── Default Settings ───
DEFAULT_SETTINGS = {
    "defaultNumberCount": 10,
    "cooldownSeconds": 5,
    "requireVerification": True,
    "minWithdraw": 50,
    "defaultOtpPrice": 0.25,
    "withdrawMethods": ["bKash", "Nagad"],
    "withdrawEnabled": True,
    "referralCommission": 10,
    "panelPollInterval": 1,     # সেকেন্ড — প্যানেল কত সেকেন্ড পরপর নতুন SMS/OTP চেক করবে
    "queueRetryInterval": 1,    # সেকেন্ড — pending DM/Group queue কত সেকেন্ড পরপর ফ্লাশ করার চেষ্টা করবে
    "queueExpiryHours": 3,      # ঘন্টা — এর বেশি পুরনো হলে queue থেকে entry বাদ পড়ে যাবে
}

# ─── Load/Save Helpers ───
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

# ─── Load Data ───
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

# ─── Global WhatsApp System ───
# admin একটা WA connect করলে সব user এর number check হবে
GLOBAL_WA_FILE    = os.path.join(DATA_DIR, "global_wa.json")
global_wa_data    = load_json(GLOBAL_WA_FILE, {
    "enabled":   False,   # Global WA check on/off
    "connected": False,   # Admin WA connected কিনা
    "phone":     "",      # Admin WA phone
    "uid":       "",      # Admin WA session uid
})

def save_global_wa():
    save_json(GLOBAL_WA_FILE, global_wa_data)
_tg_app        = None

countries = load_json(COUNTRIES_FILE, {
    "880": {"name": "Bangladesh",   "flag": "🇧🇩"},
    "91":  {"name": "India",        "flag": "🇮🇳"},
    "92":  {"name": "Pakistan",     "flag": "🇵🇰"},
    "977": {"name": "Nepal",        "flag": "🇳🇵"},
    "94":  {"name": "Sri Lanka",    "flag": "🇱🇰"},
    "95":  {"name": "Myanmar",      "flag": "🇲🇲"},
    "975": {"name": "Bhutan",       "flag": "🇧🇹"},
    "960": {"name": "Maldives",     "flag": "🇲🇻"},
    "66":  {"name": "Thailand",     "flag": "🇹🇭"},
    "84":  {"name": "Vietnam",      "flag": "🇻🇳"},
    "62":  {"name": "Indonesia",    "flag": "🇮🇩"},
    "60":  {"name": "Malaysia",     "flag": "🇲🇾"},
    "63":  {"name": "Philippines",  "flag": "🇵🇭"},
    "65":  {"name": "Singapore",    "flag": "🇸🇬"},
    "855": {"name": "Cambodia",     "flag": "🇰🇭"},
    "856": {"name": "Laos",         "flag": "🇱🇦"},
    "673": {"name": "Brunei",       "flag": "🇧🇳"},
    "670": {"name": "Timor-Leste",  "flag": "🇹🇱"},
    "86":  {"name": "China",        "flag": "🇨🇳"},
    "81":  {"name": "Japan",        "flag": "🇯🇵"},
    "82":  {"name": "South Korea",  "flag": "🇰🇷"},
    "886": {"name": "Taiwan",       "flag": "🇹🇼"},
    "852": {"name": "Hong Kong",    "flag": "🇭🇰"},
    "853": {"name": "Macau",        "flag": "🇲🇴"},
    "976": {"name": "Mongolia",     "flag": "🇲🇳"},
    "850": {"name": "North Korea",  "flag": "🇰🇵"},
    "7":   {"name": "Russia",       "flag": "🇷🇺"},
    "996": {"name": "Kyrgyzstan",   "flag": "🇰🇬"},
    "992": {"name": "Tajikistan",   "flag": "🇹🇯"},
    "993": {"name": "Turkmenistan", "flag": "🇹🇲"},
    "998": {"name": "Uzbekistan",   "flag": "🇺🇿"},
    "7778":{"name": "Kazakhstan",   "flag": "🇰🇿"},
    "93":  {"name": "Afghanistan",  "flag": "🇦🇫"},
    "98":  {"name": "Iran",         "flag": "🇮🇷"},
    "964": {"name": "Iraq",         "flag": "🇮🇶"},
    "963": {"name": "Syria",        "flag": "🇸🇾"},
    "961": {"name": "Lebanon",      "flag": "🇱🇧"},
    "962": {"name": "Jordan",       "flag": "🇯🇴"},
    "972": {"name": "Israel",       "flag": "🇮🇱"},
    "970": {"name": "Palestine",    "flag": "🇵🇸"},
    "966": {"name": "Saudi Arabia", "flag": "🇸🇦"},
    "971": {"name": "UAE",          "flag": "🇦🇪"},
    "974": {"name": "Qatar",        "flag": "🇶🇦"},
    "973": {"name": "Bahrain",      "flag": "🇧🇭"},
    "965": {"name": "Kuwait",       "flag": "🇰🇼"},
    "968": {"name": "Oman",         "flag": "🇴🇲"},
    "967": {"name": "Yemen",        "flag": "🇾🇪"},
    "994": {"name": "Azerbaijan",   "flag": "🇦🇿"},
    "374": {"name": "Armenia",      "flag": "🇦🇲"},
    "995": {"name": "Georgia",      "flag": "🇬🇪"},
    "44":  {"name": "UK",           "flag": "🇬🇧"},
    "49":  {"name": "Germany",      "flag": "🇩🇪"},
    "33":  {"name": "France",       "flag": "🇫🇷"},
    "39":  {"name": "Italy",        "flag": "🇮🇹"},
    "34":  {"name": "Spain",        "flag": "🇪🇸"},
    "31":  {"name": "Netherlands",  "flag": "🇳🇱"},
    "32":  {"name": "Belgium",      "flag": "🇧🇪"},
    "41":  {"name": "Switzerland",  "flag": "🇨🇭"},
    "43":  {"name": "Austria",      "flag": "🇦🇹"},
    "351": {"name": "Portugal",     "flag": "🇵🇹"},
    "353": {"name": "Ireland",      "flag": "🇮🇪"},
    "352": {"name": "Luxembourg",   "flag": "🇱🇺"},
    "356": {"name": "Malta",        "flag": "🇲🇹"},
    "357": {"name": "Cyprus",       "flag": "🇨🇾"},
    "45":  {"name": "Denmark",      "flag": "🇩🇰"},
    "46":  {"name": "Sweden",       "flag": "🇸🇪"},
    "47":  {"name": "Norway",       "flag": "🇳🇴"},
    "358": {"name": "Finland",      "flag": "🇫🇮"},
    "354": {"name": "Iceland",      "flag": "🇮🇸"},
    "370": {"name": "Lithuania",    "flag": "🇱🇹"},
    "371": {"name": "Latvia",       "flag": "🇱🇻"},
    "372": {"name": "Estonia",      "flag": "🇪🇪"},
    "30":  {"name": "Greece",       "flag": "🇬🇷"},
    "48":  {"name": "Poland",       "flag": "🇵🇱"},
    "420": {"name": "Czech Rep.",   "flag": "🇨🇿"},
    "421": {"name": "Slovakia",     "flag": "🇸🇰"},
    "36":  {"name": "Hungary",      "flag": "🇭🇺"},
    "40":  {"name": "Romania",      "flag": "🇷🇴"},
    "359": {"name": "Bulgaria",     "flag": "🇧🇬"},
    "385": {"name": "Croatia",      "flag": "🇭🇷"},
    "381": {"name": "Serbia",       "flag": "🇷🇸"},
    "387": {"name": "Bosnia",       "flag": "🇧🇦"},
    "386": {"name": "Slovenia",     "flag": "🇸🇮"},
    "382": {"name": "Montenegro",   "flag": "🇲🇪"},
    "389": {"name": "N. Macedonia", "flag": "🇲🇰"},
    "355": {"name": "Albania",      "flag": "🇦🇱"},
    "373": {"name": "Moldova",      "flag": "🇲🇩"},
    "380": {"name": "Ukraine",      "flag": "🇺🇦"},
    "375": {"name": "Belarus",      "flag": "🇧🇾"},
    "383": {"name": "Kosovo",       "flag": "🇽🇰"},
    "1":   {"name": "USA/Canada",   "flag": "🇺🇸"},
    "52":  {"name": "Mexico",       "flag": "🇲🇽"},
    "506": {"name": "Costa Rica",   "flag": "🇨🇷"},
    "502": {"name": "Guatemala",    "flag": "🇬🇹"},
    "504": {"name": "Honduras",     "flag": "🇭🇳"},
    "503": {"name": "El Salvador",  "flag": "🇸🇻"},
    "505": {"name": "Nicaragua",    "flag": "🇳🇮"},
    "507": {"name": "Panama",       "flag": "🇵🇦"},
    "53":  {"name": "Cuba",         "flag": "🇨🇺"},
    "509": {"name": "Haiti",        "flag": "🇭🇹"},
    "501": {"name": "Belize",       "flag": "🇧🇿"},
    "55":  {"name": "Brazil",       "flag": "🇧🇷"},
    "54":  {"name": "Argentina",    "flag": "🇦🇷"},
    "56":  {"name": "Chile",        "flag": "🇨🇱"},
    "57":  {"name": "Colombia",     "flag": "🇨🇴"},
    "51":  {"name": "Peru",         "flag": "🇵🇪"},
    "58":  {"name": "Venezuela",    "flag": "🇻🇪"},
    "593": {"name": "Ecuador",      "flag": "🇪🇨"},
    "591": {"name": "Bolivia",      "flag": "🇧🇴"},
    "595": {"name": "Paraguay",     "flag": "🇵🇾"},
    "598": {"name": "Uruguay",      "flag": "🇺🇾"},
    "592": {"name": "Guyana",       "flag": "🇬🇾"},
    "597": {"name": "Suriname",     "flag": "🇸🇷"},
    "20":  {"name": "Egypt",        "flag": "🇪🇬"},
    "213": {"name": "Algeria",      "flag": "🇩🇿"},
    "212": {"name": "Morocco",      "flag": "🇲🇦"},
    "216": {"name": "Tunisia",      "flag": "🇹🇳"},
    "218": {"name": "Libya",        "flag": "🇱🇾"},
    "249": {"name": "Sudan",        "flag": "🇸🇩"},
    "234": {"name": "Nigeria",      "flag": "🇳🇬"},
    "233": {"name": "Ghana",        "flag": "🇬🇭"},
    "221": {"name": "Senegal",      "flag": "🇸🇳"},
    "225": {"name": "Côte d'Ivoire","flag": "🇨🇮"},
    "222": {"name": "Mauritania",   "flag": "🇲🇷"},
    "223": {"name": "Mali",         "flag": "🇲🇱"},
    "226": {"name": "Burkina Faso", "flag": "🇧🇫"},
    "227": {"name": "Niger",        "flag": "🇳🇪"},
    "228": {"name": "Togo",         "flag": "🇹🇬"},
    "229": {"name": "Benin",        "flag": "🇧🇯"},
    "232": {"name": "Sierra Leone", "flag": "🇸🇱"},
    "231": {"name": "Liberia",      "flag": "🇱🇷"},
    "224": {"name": "Guinea",       "flag": "🇬🇳"},
    "245": {"name": "Guinea-Bissau","flag": "🇬🇼"},
    "238": {"name": "Cape Verde",   "flag": "🇨🇻"},
    "237": {"name": "Cameroon",     "flag": "🇨🇲"},
    "243": {"name": "DR Congo",     "flag": "🇨🇩"},
    "242": {"name": "Congo",        "flag": "🇨🇬"},
    "240": {"name": "Eq. Guinea",   "flag": "🇬🇶"},
    "241": {"name": "Gabon",        "flag": "🇬🇦"},
    "236": {"name": "CAR",          "flag": "🇨🇫"},
    "235": {"name": "Chad",         "flag": "🇹🇩"},
    "254": {"name": "Kenya",        "flag": "🇰🇪"},
    "255": {"name": "Tanzania",     "flag": "🇹🇿"},
    "256": {"name": "Uganda",       "flag": "🇺🇬"},
    "251": {"name": "Ethiopia",     "flag": "🇪🇹"},
    "252": {"name": "Somalia",      "flag": "🇸🇴"},
    "253": {"name": "Djibouti",     "flag": "🇩🇯"},
    "257": {"name": "Burundi",      "flag": "🇧🇮"},
    "250": {"name": "Rwanda",       "flag": "🇷🇼"},
    "291": {"name": "Eritrea",      "flag": "🇪🇷"},
    "27":  {"name": "South Africa", "flag": "🇿🇦"},
    "258": {"name": "Mozambique",   "flag": "🇲🇿"},
    "260": {"name": "Zambia",       "flag": "🇿🇲"},
    "263": {"name": "Zimbabwe",     "flag": "🇿🇼"},
    "267": {"name": "Botswana",     "flag": "🇧🇼"},
    "264": {"name": "Namibia",      "flag": "🇳🇦"},
    "266": {"name": "Lesotho",      "flag": "🇱🇸"},
    "268": {"name": "Eswatini",     "flag": "🇸🇿"},
    "244": {"name": "Angola",       "flag": "🇦🇴"},
    "261": {"name": "Madagascar",   "flag": "🇲🇬"},
    "230": {"name": "Mauritius",    "flag": "🇲🇺"},
    "248": {"name": "Seychelles",   "flag": "🇸🇨"},
    "61":  {"name": "Australia",    "flag": "🇦🇺"},
    "64":  {"name": "New Zealand",  "flag": "🇳🇿"},
    "679": {"name": "Fiji",         "flag": "🇫🇯"},
    "675": {"name": "Papua NG",     "flag": "🇵🇬"},
    "677": {"name": "Solomon Is.",  "flag": "🇸🇧"},
    "678": {"name": "Vanuatu",      "flag": "🇻🇺"},
    "676": {"name": "Tonga",        "flag": "🇹🇴"},
    "685": {"name": "Samoa",        "flag": "🇼🇸"},
    "686": {"name": "Kiribati",     "flag": "🇰🇮"},
    "688": {"name": "Tuvalu",       "flag": "🇹🇻"},
    "692": {"name": "Marshall Is.", "flag": "🇲🇭"},
    "691": {"name": "Micronesia",   "flag": "🇫🇲"},
    "680": {"name": "Palau",        "flag": "🇵🇼"},
})

services = load_json(SERVICES_FILE, {
    "whatsapp":    {"name": "WhatsApp",    "icon": "📱"},
    "telegram":    {"name": "Telegram",    "icon": "✈️"},
    "facebook":    {"name": "Facebook",    "icon": "📘"},
    "instagram":   {"name": "Instagram",   "icon": "📸"},
    "google":      {"name": "Google",      "icon": "🔍"},
    "verification":{"name": "Verification","icon": "✅"},
    "other":       {"name": "Other",       "icon": "🔧"},
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
        logger.info(f"✅ Loaded {total} numbers")
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
            logger.info(f"💸 Referral commission {commission:.2f} taka → uid={referrer_id} (from uid={uid})")

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

# ─── Fast suffix index for active number matching ───
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
    """Panel এর number দিয়ে active_numbers এ fast match করো"""
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
    # ── Strategy 1: Full number direct match ──
    for num in list(active_numbers.keys()):
        if num in text:
            return num

    # ── Strategy 2: SPYX mask — "4917SPYX5576" (masdar OTP bot format) ──
    spyx_patterns = re.findall(r'(\d{3,})[A-Za-z]{2,8}(\d{2,})', text)
    for prefix, suffix in spyx_patterns:
        for num in list(active_numbers.keys()):
            if num.startswith(prefix) and num.endswith(suffix):
                return num

    # ── Strategy 3: *** mask — "7921***3002" ──
    masked_patterns = re.findall(r'(\d{3,})\*+(\d{2,})', text)
    for prefix, suffix in masked_patterns:
        for num in list(active_numbers.keys()):
            if num.startswith(prefix) and num.endswith(suffix):
                return num

    # ── Strategy 4: Number field prefix match ──
    num_field = re.search(r'[Nn]umber[:\s]+(\d{4,})', text)
    if num_field:
        prefix = num_field.group(1)
        for num in list(active_numbers.keys()):
            if num.startswith(prefix):
                return num

    # ── Strategy 5: Last 8/6 digits fallback ──
    for num in list(active_numbers.keys()):
        if num[-8:] in text:
            return num
    for num in list(active_numbers.keys()):
        if num[-6:] in text:
            return num

    # ── Strategy 6: Last 4 digits with any mask ──
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

# ─── HTTP OTP Server ───
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

        # active_numbers এ match খোঁজো — leading zeros ছাড়া
        matched_number = None
        if number in active_numbers:
            matched_number = number
        else:
            # OTP bot ভিন্ন format এ পাঠাতে পারে, তাই suffix match করো
            for n in active_numbers:
                if n.endswith(number[-8:]) or number.endswith(n[-8:]):
                    matched_number = n
                    break

        if not matched_number:
            logger.warning(f"⚠️ HTTP /otp: number {number} not in active_numbers")
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
        svc     = services.get(service, {"icon": "📱", "name": service.capitalize()})
        country = countries.get(cc, {"flag": "🌍", "name": cc})

        notify = (
            f"📨 *OTP Received!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"📞 *Number:* `+{matched_number}`\n"
        )
        if otp_code:
            notify += f"\n🔑 *OTP Code:* `{otp_code}`\n"
        notify += f"\n💵 *+{earned:.2f} taka earned!*\n💰 *Balance: {balance:.2f} taka*"

        if _tg_app:
            ok_dm = await send_dm_with_retry(_tg_app, uid, notify)
            if not ok_dm:
                logger.warning(f"⏳ HTTP OTP DM queued (rate-limit/network) → uid={uid}")

        # ── Telegram OTP Group এও পাঠাও ──
        if otp_code:
            group_msg = (
                f"📨 *New OTP!*\n\n"
                f"{svc['icon']} *Service:* {svc['name']}\n"
                f"{country['flag']} *Country:* {country['name']}\n"
                f"📞 *Number:* +{matched_number}\n"
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

        logger.info(f"✅ HTTP /otp processed: +{matched_number} otp={otp_code} uid={uid}")
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
    logger.info(f"🌐 HTTP OTP server started → port {HTTP_PORT}")

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

# ─── Baileys API (WhatsApp) Helpers ───
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
    logger.info("🟢 Baileys monitor started")
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
                        logger.warning(f"⚠️ Baileys: WA check fail #{fail_counts[uid]} uid={uid}")
                        if fail_counts[uid] >= 5:
                            fail_counts.pop(uid, None)
                            wa_sessions.pop(uid, None)
                            logger.warning(f"⚠️ Baileys: WhatsApp disconnected! uid={uid}")
                            try:
                                await app.bot.send_message(
                                    int(uid),
                                    "⚠️ *WhatsApp Disconnected!*\n\n"
                                    "তোমার WhatsApp থেকে bot disconnect হয়েছে।\n"
                                    "আবার connect করতে নিচের button চাপো।",
                                    parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", style="primary")
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

# ─── Pending DM Queue (rate-limit এ miss হওয়া DM পরে আবার পাঠানোর জন্য) ───
pending_dm_notifications = load_json(PENDING_DM_FILE, [])

def save_pending_dm():
    save_json(PENDING_DM_FILE, pending_dm_notifications)

async def send_dm_with_retry(app, uid: str, message: str, max_attempts: int = 3,
                              log_number: str = None, log_otp: str = None) -> bool:
    """DM পাঠানোর চেষ্টা করে; rate-limit/network error হলে সাথে সাথে কয়েকবার retry করে।
    তাও fail হলে queue তে রেখে দেয় — background worker পরে আবার পাঠাবে।"""
    tag = f"+{log_number} otp={log_otp} " if log_number else ""
    for attempt in range(max_attempts):
        try:
            await app.bot.send_message(int(uid), message, parse_mode="Markdown")
            logger.info(f"✅ OTP DM sent: {tag}→ uid={uid}")
            return True
        except RetryAfter as e:
            wait_s = float(e.retry_after) + 1
            logger.warning(f"⏳ Rate limited, DM uid={uid} — {wait_s}s পর retry")
            await asyncio.sleep(wait_s)
        except (TimedOut, NetworkError):
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"❌ DM permanent error uid={uid}: {e}")
            return False  # ব্লক/ইউজার ডিলিট হওয়ার মতো non-retryable error — queue তে রাখার দরকার নাই

    # সব চেষ্টা fail — পরে পাঠানোর জন্য queue তে রাখো
    pending_dm_notifications.append({
        "uid": uid, "message": message, "added": time.time(), "tries": 0
    })
    save_pending_dm()
    logger.warning(f"📥 OTP DM queued for later delivery: {tag}uid={uid}")
    return False

async def _retry_dm_item(app, item: dict):
    """একটা queued DM — rate limit শেষ হলেই সাথে সাথে (concurrently, অন্য item-এর জন্য অপেক্ষা না করে) পাঠায়।"""
    try:
        await app.bot.send_message(int(item["uid"]), item["message"], parse_mode="Markdown")
        logger.info(f"✅ Queued DM delivered: uid={item['uid']}")
        return
    except RetryAfter as e:
        await asyncio.sleep(float(e.retry_after) + 1)
        try:
            await app.bot.send_message(int(item["uid"]), item["message"], parse_mode="Markdown")
            logger.info(f"✅ Queued DM delivered (rate-limit শেষে সাথে সাথে): uid={item['uid']}")
            return
        except Exception:
            pass
    except (TimedOut, NetworkError):
        pass
    except Exception as e:
        logger.error(f"❌ Queued DM dropped (permanent) uid={item['uid']}: {e}")
        return

    # এখনো fail — আবার queue তে ফেরত দাও
    item["tries"] = item.get("tries", 0) + 1
    now = time.time()
    if (now - item.get("added", now)) < settings.get("queueExpiryHours", 3) * 3600 and item.get("tries", 0) < 50:
        pending_dm_notifications.append(item)
    save_pending_dm()

async def _retry_group_item(item: dict):
    """একটা queued group message — rate limit শেষ হলেই সাথে সাথে পাঠায়।"""
    ok = await _send_group_payload(item["payload"])
    if ok:
        logger.info("✅ Queued group OTP message delivered")
        return
    item["tries"] = item.get("tries", 0) + 1
    now = time.time()
    if (now - item.get("added", now)) < settings.get("queueExpiryHours", 3) * 3600 and item.get("tries", 0) < 50:
        pending_group_notifications.append(item)
    save_pending_group()

async def dm_retry_worker(app):
    """প্রতি ১ সেকেন্ডে pending queue চেক করে — প্রতিটা item স্বাধীনভাবে (concurrently) পাঠানো হয়,
    তাই rate limit শেষ হওয়ার সাথে সাথেই সেই OTP চলে যায়, অন্য কারো জন্য অপেক্ষা করে না।"""
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
    """Direct HTTP দিয়ে OTP group এ একবার পাঠানোর চেষ্টা করে — fail হলে queue তে রেখে দেয়,
    background worker পরে আবার পাঠানোর চেষ্টা করবে (বারবার সাথে সাথে retry করে না)।"""
    import aiohttp as _aiohttp
    payload = {
        "chat_id":    OTP_GROUP_ID,
        "text":       group_msg,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": str(otp_code), "copy_text": {"text": str(otp_code)}, "style": "success"}],
                [
                    {"text": "☎️ Numbers", "url": "https://t.me/EARNING_HUB_NUMBER_BOT", "style": "primary"},
                    {"text": "💬 Chats",   "url": "https://t.me/earning_hub_otp_group",   "style": "danger"},
                ]
            ]
        }
    }
    ok = await _send_group_payload(payload)
    if not ok:
        pending_group_notifications.append({"payload": payload, "added": time.time(), "tries": 0})
        save_pending_group()
        logger.warning("📥 OTP group message queued for later delivery")
    return ok

async def _send_group_payload(payload: dict) -> bool:
    import aiohttp as _aiohttp
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for attempt in range(2):  # প্রথমবার + rate-limit শেষ হলে সাথে সাথে আরেকবার
        try:
            async with _aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=15) as r:
                    if r.status == 200:
                        return True
                    elif r.status == 429:
                        data        = await r.json()
                        retry_after = data.get("parameters", {}).get("retry_after", 10)
                        logger.warning(f"⚠️ OTP Group Flood Wait {retry_after}s")
                        if attempt == 0:
                            await asyncio.sleep(retry_after + 1)
                            continue
                        return False
                    else:
                        logger.error(f"❌ OTP group send failed ({r.status})")
                        return False
        except Exception as e:
            logger.error(f"❌ OTP group send error: {e}")
            return False
    return False

# ─── Pending Group Queue ───
pending_group_notifications = load_json(PENDING_GROUP_FILE, [])

def save_pending_group():
    save_json(PENDING_GROUP_FILE, pending_group_notifications)

async def get_wa_pairing_code(phone: str, user_id: str) -> str:
    digits = re.sub(r"\D", "", phone)
    logger.info(f"📱 Baileys pairing for: +{digits} uid={user_id}")
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
        raise Exception("WhatsApp ইতিমধ্যে connected আছে।")
    if result.get("code"):
        code  = str(result["code"])
        clean = re.sub(r"[^A-Z0-9]", "", code.upper())
        if len(clean) >= 8:
            return f"{clean[:4]}-{clean[4:8]}"
        return code
    raise Exception(
        result.get("error") or
        "Pairing code পাওয়া যায়নি। Baileys server চালু আছে কিনা দেখো।"
    )

async def monitor_wa_connection(uid: str, context):
    logger.info(f"🔍 Waiting for WA auth: {uid}")
    for _ in range(60):
        await asyncio.sleep(5)
        try:
            state = await green_get_state(uid)
            if state == "authorized":
                wa_sessions[uid] = {"connected": True}
                logger.info(f"✅ WA connected: uid={uid}")
                try:
                    await context.bot.send_message(
                        int(uid),
                        "✅ *WhatsApp Connected!*\n\n"
                        "🟢 তোমার WhatsApp সফলভাবে connect হয়েছে।\n"
                        "এখন numbers assign হলে WA check দেখাবে।\n\n"
                        "Disconnect করতে নিচের বাটন চাপো:",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔴 Logout / Disconnect", callback_data="wa_disconnect", style="success")],
                            [InlineKeyboardButton("📊 Check Status", callback_data="wa_status", style="danger")],
                        ])
                    )
                except:
                    pass
                break
        except Exception as e:
            logger.warning(f"monitor_wa_connection error: {e}")

async def check_wa_number(phone: str, user_id: str):
    # ── Global WA enabled হলে admin WA দিয়ে check করো ──
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
        logger.info(f"📱 WA check +{digits}: {result}")
        results = result.get("results", {})
        val = results.get(digits)
        if val is True:  return True
        if val is False: return False
        return None
    except Exception as e:
        logger.warning(f"check_wa_number error +{digits}: {e}")
        return None

# ─── Mail.tm API ───
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

# ─── Membership Check ───
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

# ─── Keyboards ───
def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("☎️ Get Number", style="primary"), KeyboardButton("📧 Get Tempmail", style="success")],
        [KeyboardButton("🔐 2FA", style="danger"), KeyboardButton("💰 Balances", style="primary")],
        [KeyboardButton("💸 Withdraw", style="success"), KeyboardButton("👥 Referral", style="danger")],
        [KeyboardButton("💬 Support", style="primary")]
    ], resize_keyboard=True)

def verify_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ 📢 Main Channel", url=MAIN_CHANNEL_URL, style="primary")],
        [InlineKeyboardButton("2️⃣ 💬 Number Channel", url=CHAT_GROUP, style="success")],
        [InlineKeyboardButton("3️⃣ 📨 OTP Group", url=OTP_GROUP, style="danger")],
        [InlineKeyboardButton("✅ VERIFY MEMBERSHIP", callback_data="verify_user", style="primary")],
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stock Report", callback_data="admin_stock", style="primary"),
         InlineKeyboardButton("👥 User Stats", callback_data="admin_users", style="success")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast", style="danger"),
         InlineKeyboardButton("📋 OTP Log", callback_data="admin_otp_log", style="primary")],
        [InlineKeyboardButton("➕ Add Numbers", callback_data="admin_add_numbers", style="success"),
         InlineKeyboardButton("📤 Upload File", callback_data="admin_upload", style="danger")],
        [InlineKeyboardButton("🗑️ Delete Numbers", callback_data="admin_delete", style="primary"),
         InlineKeyboardButton("🔧 Manage Services", callback_data="admin_manage_services", style="success")],
        [InlineKeyboardButton("🌍 Manage Countries", callback_data="admin_manage_countries", style="danger"),
         InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings", style="primary")],
        [InlineKeyboardButton("💰 Country Prices", callback_data="admin_country_prices", style="success"),
         InlineKeyboardButton("💸 Withdrawals", callback_data="admin_withdrawals", style="danger")],
        [InlineKeyboardButton("👛 Balance Management", callback_data="admin_balance_manage", style="primary"),
         InlineKeyboardButton("👥 Referral Stats", callback_data="admin_referral_stats", style="success")],
        [InlineKeyboardButton("📡 OTP Panels", callback_data="admin_panels", style="danger"),
         InlineKeyboardButton("📱 Global WA", callback_data="admin_global_wa", style="primary")],
        [InlineKeyboardButton("🎭 Fake OTP Numbers", callback_data="fake_otp_menu", style="success")],
        [InlineKeyboardButton("✨ Premium Emoji", callback_data="pe_menu", style="primary")],
        [InlineKeyboardButton("🚪 Logout", callback_data="admin_logout", style="danger")],
    ])

# ─── User Session State ───
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

# ─── Verification Middleware ───
async def ensure_verified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    uid  = str(user.id)
    sess = get_session(uid)

    # Admin সবসময় pass
    if sess["is_admin"] or is_admin(uid):
        sess["is_admin"] = True
        return True

    # Verification বন্ধ থাকলে pass
    if not settings.get("requireVerification", True):
        return True

    # Local flag চেক — chat_member handler real-time এ update করে
    if sess.get("verified") or users.get(uid, {}).get("verified", False):
        return True

    # Verified না — rejoin করতে বলো, block না
    msg = (
        "⚠️ *Bot ব্যবহার করতে সকল গ্রুপে join করতে হবে!*\n\n"
        "নিচের সবগুলোতে join করুন, তারপর VERIFY চাপুন:"
    )
    if update.callback_query:
        await update.callback_query.answer("⛔ সব group এ join করো!", show_alert=True)
        try:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
        except:
            await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
    else:
        await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
    return False

# ─── /start ───
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
            # শুধু referredBy সেট করো — verify সফল হওয়ার আগে count হবে না
            if (referrer_id != uid
                    and not users[uid].get("referredBy")
                    and referrer_id in users):
                users[uid]["referredBy"] = referrer_id
                users[uid]["referralVerified"] = False
                logger.info(f"🔗 Referral pending verify: uid={uid} referred by uid={referrer_id}")

        await async_save_users()

        sess = get_session(uid)
        sess["state"] = None
        sess["data"]  = None

        welcome = (
            f"👋 *Welcome to Earning Hub Number Bot!*\n\n"
            f"📱 Get virtual numbers for OTP verification\n"
            f"💵 Earn money from each OTP received"
        )

        if sess.get("verified") or (uid in users and users[uid].get("verified")):
            await update.message.reply_text(
                welcome + "\n\n✅ Choose an option:",
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
            await update.message.reply_text("⚠️ Error occurred. Please try again.")
        except:
            pass

# ─── Verify ───
async def cb_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Checking...")

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

            # ── Referral: শুধু প্রথমবার verify হলে count করো ──
            if not users[uid].get("referralVerified", False):
                referrer_id = users[uid].get("referredBy")
                if referrer_id and referrer_id in users:
                    users[uid]["referralVerified"] = True
                    users[referrer_id]["referralCount"] = users[referrer_id].get("referralCount", 0) + 1
                    referrals.setdefault(referrer_id, [])
                    if uid not in referrals[referrer_id]:
                        referrals[referrer_id].append(uid)
                    await async_save_referrals()
                    logger.info(f"✅ Referral confirmed: uid={uid} → referrer={referrer_id}")
                    try:
                        await context.bot.send_message(
                            int(referrer_id),
                            f"🎉 *New Referral Confirmed!*\n\n"
                            f"👤 *{user.first_name}* সব group join করে verified হয়েছে!\n"
                            f"💸 তারা OTP থেকে earn করলে তুমি *{settings.get('referralCommission', 10)}%* commission পাবে।",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            await async_save_users()

        await query.edit_message_text("✅ *VERIFICATION SUCCESSFUL!*\n\nYou can now use all features.", parse_mode="Markdown")
        await context.bot.send_message(
            user.id, "🎉 Welcome! Choose an option:",
            reply_markup=main_keyboard()
        )
    else:
        msg = "❌ *VERIFICATION FAILED*\n\n"
        if not membership["mainChannel"]: msg += "❌ 1️⃣ Main Channel\n"
        if not membership["chatGroup"]:   msg += "❌ 2️⃣ Number Channel\n"
        if not membership["otpGroup"]:    msg += "❌ 3️⃣ OTP Group\n"
        msg += "\nPlease join ALL groups and click VERIFY again."
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())

# ─── Admin Login ───
async def cmd_adminlogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 2:
        return await update.message.reply_text("❌ Usage: /adminlogin [password]")
    if parts[1] == ADMIN_PASSWORD:
        uid = str(update.effective_user.id)
        sess = get_session(uid)
        sess["is_admin"] = True
        sess["state"]    = None
        sess["data"]     = None
        if uid not in admins:
            admins.append(uid)
            save_admins()
        await update.message.reply_text("✅ *Admin Login Successful!*\nUse /admin to access panel.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Wrong password.")

# ─── Admin Panel ───
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    sess = get_session(uid)
    if not sess["is_admin"] and not is_admin(uid):
        return await update.message.reply_text("❌ Use /adminlogin [password] first.")
    sess["state"] = None
    sess["data"]  = None
    await update.message.reply_text("🛠 *Admin Dashboard*\n\nSelect an option:", parse_mode="Markdown", reply_markup=admin_keyboard())

# ─── GET NUMBERS ───
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
        return await update.message.reply_text("📭 *No Numbers Available*\n\nPlease try again later.", parse_mode="Markdown")

    # ── 3-color cycle for service buttons ──
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
        "🎯 *Select a Service*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── cb_select_service — 3-COLOR FIX ───
async def cb_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    svc    = services.get(svc_id, {"name": svc_id, "icon": "📞"})
    ccs    = sorted(get_available_countries_for_service(svc_id), key=lambda cc: get_otp_price(cc))

    if not ccs:
        return await query.answer("❌ No numbers available", show_alert=True)

    # ── 3-color cycle: primary=blue, success=green, danger=red ──
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
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_services", style="danger")])

    await query.edit_message_text(
        f"{svc['icon']} *{svc['name']}* — Select Country\n\n_(taka = earnings per OTP)_",
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
        return await query.answer(f"⏳ {remaining} সেকেন্ড অপেক্ষা করো।", show_alert=True)

    nums = await get_multiple_numbers(cc, svc_id, uid, count)
    if not nums:
        return await query.answer("❌ Not enough numbers available.", show_alert=True)

    for old in sess["current_numbers"]:
        active_numbers.pop(old, None)
    await async_save_active()

    sess["current_numbers"] = nums
    sess["current_service"] = svc_id
    sess["current_country"] = cc
    sess["last_number_time"] = now

    country = countries.get(cc, {"flag": "🌍", "name": cc})
    svc     = services.get(svc_id, {"icon": "📞", "name": svc_id})
    price   = get_otp_price(cc)
    wa_connected = wa_sessions.get(uid, {}).get("connected", False) or (global_wa_data.get("enabled") and global_wa_data.get("connected"))

    def make_msg():
        return (
            f"✅ *{len(nums)} Number(s) Assigned!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"💵 *Earnings per OTP:* {price:.2f} taka\n\n"
            f"📌 OTP automatically আসবে।"
        )

    # ── Copy buttons — ২টা করে এক row ──
    from telegram import CopyTextButton

    def make_copy_buttons(wa_result=None):
        rows = []
        for n in nums:
            if wa_result:
                status = wa_result.get(n)
                icon  = "📱" if status is True else ("❌" if status is False else "⬜")
                style = "success" if status is True else ("danger" if status is False else "primary")
            else:
                icon  = "⏳" if wa_connected else "📋"
                style = "primary"
            rows.append([InlineKeyboardButton(
                text=f"{icon} +{n}",
                copy_text=CopyTextButton(text=f"+{n}"),
                style=style
            )])
        return rows

    bottom_buttons = [
        [InlineKeyboardButton("📨 Open OTP Group", url=OTP_GROUP, style="primary")],
        [InlineKeyboardButton("🔄 Get New Numbers", callback_data=f"newnum:{svc_id}:{cc}", style="success")],
        [InlineKeyboardButton("🔙 Service List", callback_data="back_services", style="danger")],
    ]
    if not wa_connected:
        bottom_buttons.append([InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", style="primary")])

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
        return await query.answer(f"⏳ {remaining} সেকেন্ড অপেক্ষা করো।", show_alert=True)

    count = settings.get("defaultNumberCount", 10)
    nums  = await get_multiple_numbers(cc, svc_id, uid, count)
    if not nums:
        return await query.answer("❌ No numbers available.", show_alert=True)

    for old in sess["current_numbers"]:
        active_numbers.pop(old, None)
    await async_save_active()

    sess["current_numbers"] = nums
    sess["last_number_time"] = now

    country = countries.get(cc, {"flag": "🌍", "name": cc})
    svc     = services.get(svc_id, {"icon": "📞", "name": svc_id})
    price   = get_otp_price(cc)
    wa_connected = wa_sessions.get(uid, {}).get("connected", False) or (global_wa_data.get("enabled") and global_wa_data.get("connected"))

    def make_msg_new():
        return (
            f"🔄 *{len(nums)} New Number(s)!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"💵 *Earnings per OTP:* {price:.2f} taka\n\n"
            f"📌 OTP automatically আসবে।"
        )

    from telegram import CopyTextButton

    def make_copy_buttons_new(wa_result=None):
        rows = []
        for n in nums:
            if wa_result:
                status = wa_result.get(n)
                icon  = "📱" if status is True else ("❌" if status is False else "⬜")
                style = "success" if status is True else ("danger" if status is False else "primary")
            else:
                icon  = "⏳" if wa_connected else "📋"
                style = "primary"
            rows.append([InlineKeyboardButton(
                text=f"{icon} +{n}",
                copy_text=CopyTextButton(text=f"+{n}"),
                style=style
            )])
        return rows

    bottom_buttons_new = [
        [InlineKeyboardButton("📨 Open OTP Group", url=OTP_GROUP, style="primary")],
        [InlineKeyboardButton("🔄 Get New Numbers", callback_data=f"newnum:{svc_id}:{cc}", style="success")],
        [InlineKeyboardButton("🔙 Service List", callback_data="back_services", style="danger")],
    ]
    if not wa_connected:
        bottom_buttons_new.append([InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", style="primary")])

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

    # ── 3-color cycle ──
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
        "🎯 *Select a Service*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── BALANCE ───
async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    e   = get_user_earnings(uid)
    pending = [w for w in withdrawals if w["userId"] == uid and w["status"] == "pending"]
    withdrawn = sum(w["amount"] for w in withdrawals if w["userId"] == uid and w["status"] == "approved")
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = e.get("referralEarnings", 0)

    await update.message.reply_text(
        f"💰 *Your Earnings*\n\n"
        f"💵 *Current Balance:* {e['balance']:.2f} taka\n"
        f"📈 *Total Earned:* {e['totalEarned']:.2f} taka\n"
        f"📨 *Total OTPs:* {e.get('otpCount', 0)}\n"
        f"💸 *Total Withdrawn:* {withdrawn:.2f} taka\n"
        f"⏳ *Pending Withdrawals:* {len(pending)}\n\n"
        f"👥 *Referrals:* {ref_count} জন\n"
        f"🎁 *Referral Earnings:* {ref_earn:.2f} taka\n\n"
        f"📌 *Minimum Withdraw:* {settings['minWithdraw']} taka",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw", callback_data="start_withdraw", style="danger")],
            [InlineKeyboardButton("📋 Withdraw History", callback_data="withdraw_history", style="primary")],
        ])
    )

# ─── REFERRAL ───
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
            referred_text += f"  👤 {r_name} — তোমার cut: *{my_cut:.2f} taka*\n"

    msg = (
        f"👥 *Referral Program*\n\n"
        f"🔗 তোমার referral link:\n`{ref_link}`\n\n"
        f"💸 *Commission:* প্রতি OTP এর *{commission}%*\n\n"
        f"📊 *তোমার Stats:*\n"
        f"  👥 Total Referrals: *{ref_count}*\n"
        f"  💰 Total Commission Earned: *{ref_earn:.2f} taka*\n"
    )
    if referred_text:
        msg += f"\n📋 *Recent Referrals:*\n{referred_text}"

    msg += (
        f"\n📌 *How it works:*\n"
        f"  1. উপরের link share করো\n"
        f"  2. কেউ join করলে তারা OTP earn করবে\n"
        f"  3. তুমি তাদের প্রতিটা OTP income এর *{commission}%* পাবে আজীবন!\n"
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Share Referral Link", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(f'আমার referral link দিয়ে join করো এবং OTP থেকে আয় করো!')}", style="success")],
            [InlineKeyboardButton("📊 Referral Stats", callback_data="ref_stats", style="danger")],
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
        f"📊 *Referral Statistics*\n\n"
        f"👥 *Total Referred:* {ref_count}\n"
        f"💰 *Total Commission:* {ref_earn:.2f} taka\n"
        f"📌 *Commission Rate:* {commission}%\n\n"
    )

    if referred_list:
        msg += "👤 *All Referred Users:*\n"
        for r_uid in referred_list[-20:]:
            r_user = users.get(r_uid, {})
            r_name = r_user.get("first_name", "User").replace("*", "").replace("_", "")
            r_earn = get_user_earnings(r_uid)
            otps   = r_earn.get("otpCount", 0)
            my_cut = round(r_earn.get("totalEarned", 0) * commission / 100, 2)
            msg += f"  • {r_name} | OTPs: {otps} | তোমার: {my_cut:.2f}৳\n"
    else:
        msg += "এখনো কোনো referral নেই।\n"

    if len(msg) > 4000:
        msg = msg[:3950] + "\n..._truncated_"

    bot_username = context.bot.username
    ref_link = get_referral_link(uid, bot_username)

    await query.edit_message_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Share Link", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}", style="primary")],
            [InlineKeyboardButton("🔙 Back", callback_data="goto_main", style="success")],
        ])
    )

# ─── WITHDRAW ───
async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    e   = get_user_earnings(uid)
    sess = get_session(uid)
    sess["state"] = None

    if not settings.get("withdrawEnabled", True):
        return await update.message.reply_text("⏸️ *Withdrawals are currently disabled.*", parse_mode="Markdown")

    if e["balance"] < settings["minWithdraw"]:
        return await update.message.reply_text(
            f"❌ *Insufficient balance.*\n\n"
            f"💵 Balance: {e['balance']:.2f} taka\n"
            f"📌 Minimum: {settings['minWithdraw']} taka",
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        f"💸 *Withdraw*\n\n💵 Balance: *{e['balance']:.2f} taka*\n\nChoose method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 bKash", callback_data="wm:bKash", style="danger"),
             InlineKeyboardButton("🟠 Nagad", callback_data="wm:Nagad", style="primary")],
            [InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", style="success")],
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
    rows.append([InlineKeyboardButton(f"💰 All ({e['balance']:.2f} taka)", callback_data=f"wa:{method}:{e['balance']:.2f}", style="danger")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", style="primary")])

    icon = "🟣" if method == "bKash" else "🟠"
    await query.edit_message_text(
        f"{icon} *{method} Withdrawal*\n\n💵 Balance: *{e['balance']:.2f} taka*\n\nSelect amount or type in chat:",
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
        return await query.answer(f"❌ Minimum {settings['minWithdraw']} taka", show_alert=True)
    if amount > e["balance"]:
        return await query.answer("❌ Insufficient balance!", show_alert=True)

    sess["state"] = "w_account"
    sess["data"]  = {"method": method, "amount": amount}
    icon = "🟣" if method == "bKash" else "🟠"

    await query.edit_message_text(
        f"{icon} *{method} — {amount:.2f} taka*\n\n📱 Your *{method} number:*\nExample: `01712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", style="success")]])
    )

async def cb_withdraw_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None
    await query.edit_message_text("❌ *Cancelled.*", parse_mode="Markdown")

async def cb_withdraw_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = str(update.effective_user.id)
    uwith = [w for w in withdrawals if w["userId"] == uid][-10:][::-1]

    text = "📋 *Withdraw History*\n\n"
    if not uwith:
        text += "No withdrawal requests yet."
    else:
        for w in uwith:
            icon = "✅" if w["status"] == "approved" else "❌" if w["status"] == "rejected" else "⏳"
            date = w["requestedAt"][:10]
            text += f"{icon} *{w['amount']:.2f} taka* - {w['method']}\n"
            text += f"📱 `{w['account']}` | {date}\n\n"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="goto_main", style="danger")]]))

async def cb_start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    e    = get_user_earnings(uid)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None

    if not settings.get("withdrawEnabled", True):
        return await query.edit_message_text("⏸️ *Withdrawals are currently disabled.*", parse_mode="Markdown")
    if e["balance"] < settings["minWithdraw"]:
        return await query.edit_message_text(
            f"❌ *Insufficient balance.*\n💵 Balance: {e['balance']:.2f} taka\n📌 Minimum: {settings['minWithdraw']} taka",
            parse_mode="Markdown"
        )

    await query.edit_message_text(
        f"💸 *Withdraw*\n\n💵 Balance: *{e['balance']:.2f} taka*\n\nChoose method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 bKash", callback_data="wm:bKash", style="primary"),
             InlineKeyboardButton("🟠 Nagad", callback_data="wm:Nagad", style="success")],
            [InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", style="danger")],
        ])
    )

# ─── WhatsApp Connect ───
async def cb_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)

    if wa_sessions.get(uid, {}).get("connected"):
        await query.edit_message_text(
            "✅ *WhatsApp Already Connected!*\n\n"
            "🟢 WhatsApp এখন active আছে।\n"
            "Disconnect করতে নিচের বাটন চাপো:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔴 Logout / Disconnect", callback_data="wa_disconnect", style="primary")],
                [InlineKeyboardButton("📊 Check Status", callback_data="wa_status", style="success")],
            ])
        )
        return

    sess = get_session(uid)
    sess["state"] = "wa_waiting_number"
    await context.bot.send_message(
        update.effective_user.id,
        "📱 WhatsApp Connect\n\nতোমার WhatsApp নম্বর দাও (country code সহ):\nExample: 8801712345678"
    )

async def cb_wa_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Checking...")
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
        "authorized":    "✅ *WhatsApp Connected!*\n\nNumber assign হলে 📱/❌ দেখাবে।",
        "notAuthorized": "🔴 *WhatsApp connected নেই।*\n\nCode enter করলে আবার Check Status চাপো।",
    }
    text = STATE_MAP.get(state, f"❓ Unknown state: {state}")
    btns = [[InlineKeyboardButton("🔴 Disconnect", callback_data="wa_disconnect", style="danger")]] if conn else \
           [[InlineKeyboardButton("📱 Connect", callback_data="wa_connect", style="primary")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def cb_wa_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Disconnecting...")
    uid = str(update.effective_user.id)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: baileys_request("POST", "/disconnect", {"userId": uid}))
        logger.info(f"✅ Baileys logout called for uid={uid}")
    except Exception as e:
        logger.error(f"Baileys logout error: {e}")

    wa_sessions.pop(uid, None)

    await query.edit_message_text(
        "🔴 *WhatsApp Disconnected!*\n\n"
        "তোমার WhatsApp সফলভাবে logout হয়েছে।\n"
        "আবার connect করতে নিচের বাটন চাপো:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", style="success")],
        ])
    )

# ─── Temp Mail ───
async def handle_tempmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    existing = temp_mails.get(uid)

    if existing:
        await update.message.reply_text(
            f"📧 *Temporary Email*\n\n📌 Your email:\n`{existing['address']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📬 Check Inbox", callback_data="tm_inbox", style="danger")],
                [InlineKeyboardButton("📋 Show Email", callback_data="tm_show", style="primary")],
                [InlineKeyboardButton("🔄 Get New Email", callback_data="tm_create", style="success")],
                [InlineKeyboardButton("🗑️ Delete Email", callback_data="tm_delete", style="danger")],
            ])
        )
    else:
        await update.message.reply_text(
            "📧 *Temporary Email*\n\n✅ Create a new disposable email address.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🆕 Create New Email", callback_data="tm_create", style="primary")]])
        )

async def cb_tm_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Creating...")
    uid   = str(update.effective_user.id)
    loading = await context.bot.send_message(uid, "⏳ *Creating your email...*", parse_mode="Markdown")

    async def _create_task():
        try:
            new_email = await create_fresh_email()
            if not new_email:
                await context.bot.edit_message_text(
                    "❌ *Email creation failed.* Please try again.",
                    chat_id=uid, message_id=loading.message_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="tm_create", style="success")]])
                )
                return
            temp_mails[uid] = new_email
            save_temp_mails()
            await context.bot.edit_message_text(
                f"✅ *New Email Created!*\n\n📧 `{new_email['address']}`\n\n📌 Use this on any website.",
                chat_id=uid, message_id=loading.message_id,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📬 Check Inbox", callback_data="tm_inbox", style="danger")],
                    [InlineKeyboardButton("🔄 Get New Email", callback_data="tm_create", style="primary")],
                    [InlineKeyboardButton("🗑️ Delete", callback_data="tm_delete", style="success")],
                ])
            )
        except Exception as e:
            logger.error(f"cb_tm_create task error uid={uid}: {e}")
            try:
                await context.bot.edit_message_text(
                    "❌ *Error occurred.* Please try again.",
                    chat_id=uid, message_id=loading.message_id,
                    parse_mode="Markdown"
                )
            except:
                pass

    asyncio.create_task(_create_task())

async def cb_tm_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📬 Loading...")
    uid = str(update.effective_user.id)

    if uid not in temp_mails:
        return await query.edit_message_text(
            "❌ No email found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🆕 Create", callback_data="tm_create", style="danger")]])
        )

    email_obj = temp_mails[uid]

    async def _inbox_task():
        try:
            messages  = await get_email_inbox(email_obj)
            now_str   = datetime.now().strftime("%I:%M:%S %p")
            text      = f"📬 *Inbox:* `{email_obj['address']}`\n🕐 _{now_str}_\n\n"

            if not messages:
                text += "📭 *No emails yet.*"
            else:
                for msg in messages[:5]:
                    text += f"━━━━━━━━━━\n📩 *From:* {msg['from']}\n📌 *Subject:* {msg['subject']}\n"
                    body = await get_email_message(msg["id"], email_obj)
                    if body:
                        otp_m = re.findall(r"\b\d{4,8}\b", body)
                        if otp_m:
                            text += f"\n🔑 *OTP:* `{otp_m[0]}`\n"
                        text += f"\n📝 _{body[:250]}..._\n" if len(body) > 250 else f"\n📝 _{body}_\n"
                    text += "\n"

            try:
                await query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="tm_inbox", style="primary")],
                    [InlineKeyboardButton("🔄 New Email", callback_data="tm_create", style="success")],
                    [InlineKeyboardButton("🗑️ Delete", callback_data="tm_delete", style="danger")],
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
        return await query.answer("❌ No email found", show_alert=True)
    addr = temp_mails[uid]["address"]
    await query.edit_message_text(
        f"📧 *Your Temp Email:*\n\n`{addr}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📬 Check Inbox", callback_data="tm_inbox", style="primary")],
            [InlineKeyboardButton("🔄 New Email", callback_data="tm_create", style="success")],
        ])
    )

async def cb_tm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    temp_mails.pop(uid, None)
    save_temp_mails()
    await query.edit_message_text("✅ *Email deleted.*", parse_mode="Markdown")

# ─── 2FA/TOTP ───
async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    sess = get_session(str(update.effective_user.id))
    sess["state"] = None
    await update.message.reply_text(
        "🔐 *2-Step Verification Code Generator*\n\nSelect a service:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📘 Facebook 2FA", callback_data="totp:facebook", style="danger")],
            [InlineKeyboardButton("📸 Instagram 2FA", callback_data="totp:instagram", style="primary")],
            [InlineKeyboardButton("🔍 Google 2FA", callback_data="totp:google", style="success")],
            [InlineKeyboardButton("⚙️ Other 2FA", callback_data="totp:other", style="danger")],
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

    icons = {"facebook": "📘", "instagram": "📸", "google": "🔍", "other": "⚙️"}
    names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "Other"}
    icon  = icons.get(svc, "🔐")
    name  = names.get(svc, svc)

    await query.edit_message_text(
        f"{icon} *{name} Secret Key*\n\n"
        f"Send your Authenticator Secret Key.\n\n"
        f"🔑 It looks like: `JBSWY3DPEHPK3PXP`\n\n"
        f"Type /cancel to cancel",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="totp_back", style="primary")]])
    )

async def cb_totp_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔐 *2FA Code Generator*\n\nSelect a service:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📘 Facebook 2FA", callback_data="totp:facebook", style="success")],
            [InlineKeyboardButton("📸 Instagram 2FA", callback_data="totp:instagram", style="danger")],
            [InlineKeyboardButton("🔍 Google 2FA", callback_data="totp:google", style="primary")],
            [InlineKeyboardButton("⚙️ Other 2FA", callback_data="totp:other", style="success")],
        ])
    )

async def cb_totp_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Refreshing...")
    _, svc, secret_enc = query.data.split(":", 2)

    if secret_enc == "TOOLONG":
        await query.edit_message_text(
            "⚠️ Secret key টি অনেক বড়। Refresh করতে আবার 🔐 2FA বাটন চাপুন।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="totp_back", style="danger")]]))
        return

    secret = urllib.parse.unquote(secret_enc)
    result = generate_totp(secret)

    icons = {"facebook": "📘", "instagram": "📸", "google": "🔍", "other": "⚙️"}
    names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "2FA"}
    icon  = icons.get(svc, "🔐")
    name  = names.get(svc, svc)

    if not result:
        return await query.edit_message_text("❌ Invalid secret key.", parse_mode="Markdown")

    cb_data = f"totp_r:{svc}:{secret_enc}"

    try:
        await query.edit_message_text(
            f"{icon} *{name} 2FA Code*\n\n"
            f"🔑 *Code:* `{result['token']}`\n\n"
            f"⏰ *{result['timeRemaining']} seconds remaining*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Code", callback_data=cb_data, style="primary")],
                [InlineKeyboardButton("🔙 Back", callback_data="totp_back", style="success")],
            ])
        )
    except:
        pass

# ─── Support ───
async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 *Support*\n\nContact admin:\n📌 @sadhin8miya",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact", url="https://t.me/sadhin8miya", style="danger")]])
    )

# ─── Admin Callbacks ───
async def cb_admin_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    report = "📊 *Stock Report*\n\n"
    total_all = 0
    for cc, svcs in numbers_by_cs.items():
        country = countries.get(cc, {"flag": "🏴", "name": cc})
        report += f"\n{country['flag']} {country['name']} (+{cc}):\n"
        ct = 0
        for svc_id, nums in svcs.items():
            svc = services.get(svc_id, {"icon": "📞", "name": svc_id})
            if nums:
                report += f"  {svc['icon']} {svc['name']}: *{len(nums)}*\n"
                ct += len(nums)
        report += f"  *Total:* {ct}\n"
        total_all += ct

    report += f"\n📈 *Grand Total:* {total_all}\n"
    report += f"👥 *Active:* {len(active_numbers)}\n"
    report += f"📨 *OTPs:* {len(otp_log)}"

    if len(report) > 4000:
        report = report[:3950] + "\n..._truncated_"

    await safe_edit(query, report, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stock", style="primary")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="success")],
    ]))

async def cb_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    try:
        total = len(users)
        total_referrals = sum(u.get("referralCount", 0) for u in users.values())
        msg   = (
            f"👥 *User Statistics*\n\n"
            f"• Total Users: {total}\n"
            f"• Active Numbers: {len(active_numbers)}\n"
            f"• OTPs Processed: {len(otp_log)}\n"
            f"• Total Referrals Made: {total_referrals}\n\n"
        )

        recent = sorted(users.values(), key=lambda u: u.get("last_active",""), reverse=True)[:10]
        for u in recent:
            uid_str  = u.get('id', '?')
            fname    = u.get('first_name', '').replace('*','').replace('_','').replace('`','')
            uname    = u.get('username', 'no_username').replace('_','\\_')
            msg += f"👤 *{fname}*\n🆔 `{uid_str}` | @{uname}\n"
            msg += f"🕐 {get_time_ago(u.get('last_active', ''))}\n\n"

        if len(msg) > 4000:
            msg = msg[:3950] + "..._truncated_"

        await safe_edit(query, msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_users", style="danger")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
        ]))
    except Exception as e:
        logger.error(f"cb_admin_users error: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                f"❌ *Error loading user stats*\n\n`{str(e)[:200]}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="success")]])
            )
        except:
            pass

async def cb_admin_otp_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    msg = "📋 *Recent OTP Logs*\n\n"
    if not otp_log:
        msg += "No OTPs yet."
    else:
        for log in otp_log[-10:][::-1]:
            msg += f"📞 `{log['phoneNumber']}` → 👤 `{log['userId']}`\n"
            msg += f"🕐 {get_time_ago(log.get('timestamp',''))}\n\n"

    await safe_edit(query, msg[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_otp_log", style="danger")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
    ]))

async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_broadcast"
    await query.edit_message_text(
        "📢 *Broadcast Message*\n\nSend the message to broadcast to all users:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    commission = settings.get("referralCommission", 10)
    await query.edit_message_text(
        f"⚙️ *Bot Settings*\n\n"
        f"📞 Number Count: *{settings['defaultNumberCount']}*\n"
        f"⏱ Cooldown: *{settings['cooldownSeconds']} seconds*\n"
        f"🔐 Verification: *{'Enabled ✅' if settings['requireVerification'] else 'Disabled ❌'}*\n"
        f"💵 OTP Price: *{settings.get('defaultOtpPrice', 0.25):.2f} taka*\n"
        f"💸 Min Withdraw: *{settings['minWithdraw']} taka*\n"
        f"🏧 Withdraw: *{'Enabled ✅' if settings['withdrawEnabled'] else 'Disabled ❌'}*\n"
        f"👥 Referral Commission: *{commission}%*\n"
        f"📡 Panel Poll Interval: *{settings.get('panelPollInterval', 1)} sec*\n"
        f"📥 Queue Retry Interval: *{settings.get('queueRetryInterval', 1)} sec*\n"
        f"🗑️ Queue Expiry: *{settings.get('queueExpiryHours', 3)} hours*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 Number Count", callback_data="as_count", style="danger"),
             InlineKeyboardButton("⏱ Cooldown", callback_data="as_cooldown", style="primary")],
            [InlineKeyboardButton(f"🔐 Verification {'Disable' if settings['requireVerification'] else 'Enable'}", callback_data="as_toggle_verify", style="success")],
            [InlineKeyboardButton("💵 OTP Price", callback_data="as_price", style="danger"),
             InlineKeyboardButton("💸 Min Withdraw", callback_data="as_minw", style="primary")],
            [InlineKeyboardButton(f"🏧 Withdraw {'🔴 Disable' if settings['withdrawEnabled'] else '🟢 Enable'}", callback_data="as_toggle_withdraw", style="success")],
            [InlineKeyboardButton(f"👥 Referral Commission ({commission}%)", callback_data="as_referral_commission", style="danger")],
            [InlineKeyboardButton("📡 Panel Poll Interval", callback_data="as_panel_interval", style="primary"),
             InlineKeyboardButton("📥 Queue Retry Interval", callback_data="as_queue_interval", style="success")],
            [InlineKeyboardButton("🗑️ Queue Expiry (hours)", callback_data="as_queue_expiry", style="danger")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_admin_toggle_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    settings["requireVerification"] = not settings["requireVerification"]
    save_settings()
    await query.answer(f"✅ Verification {'Enabled' if settings['requireVerification'] else 'Disabled'}")
    await cb_admin_settings(update, context)

async def cb_admin_toggle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    settings["withdrawEnabled"] = not settings["withdrawEnabled"]
    save_settings()
    await query.answer(f"✅ Withdraw {'Enabled' if settings['withdrawEnabled'] else 'Disabled'}")
    await cb_admin_settings(update, context)

async def cb_as_referral_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_referral_commission"
    current = settings.get("referralCommission", 10)
    await query.edit_message_text(
        f"👥 *Set Referral Commission*\n\n"
        f"Current: *{current}%*\n\n"
        f"Send new commission percentage (0-50):\n"
        f"Example: `10` means 10%",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_panel_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_panel_interval"
    current = settings.get("panelPollInterval", 1)
    await query.edit_message_text(
        f"📡 *Set Panel Poll Interval*\n\n"
        f"Current: *{current} sec*\n\n"
        f"প্যানেল কত সেকেন্ড পরপর নতুন SMS/OTP চেক করবে সেই সংখ্যা দাও:\n"
        f"Example: `1`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_queue_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_queue_interval"
    current = settings.get("queueRetryInterval", 1)
    await query.edit_message_text(
        f"📥 *Set Queue Retry Interval*\n\n"
        f"Current: *{current} sec*\n\n"
        f"pending DM/Group queue কত সেকেন্ড পরপর চেক/ফ্লাশ করবে সেই সংখ্যা দাও:\n"
        f"Example: `1`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_queue_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_queue_expiry"
    current = settings.get("queueExpiryHours", 3)
    await query.edit_message_text(
        f"🗑️ *Set Queue Expiry*\n\n"
        f"Current: *{current} hours*\n\n"
        f"কতক্ষণ (ঘন্টা) চেষ্টা করার পরও না গেলে queue থেকে entry বাদ দিবে সেই সংখ্যা দাও:\n"
        f"Example: `3`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_admin_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    commission = settings.get("referralCommission", 10)
    total_referrals = sum(u.get("referralCount", 0) for u in users.values())
    total_ref_earn  = sum(e.get("referralEarnings", 0) for e in earnings.values())

    msg = (
        f"👥 *Referral System Stats*\n\n"
        f"📌 Commission Rate: *{commission}%*\n"
        f"👥 Total Referrals: *{total_referrals}*\n"
        f"💰 Total Commission Paid: *{total_ref_earn:.2f} taka*\n\n"
        f"🏆 *Top Referrers:*\n"
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
        msg += f"  👤 {r_name} | {r_count} referrals | {r_earn:.2f} taka\n"

    if len(msg) > 4000:
        msg = msg[:3950] + "\n..._truncated_"

    await query.edit_message_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚙️ Set Commission ({commission}%)", callback_data="as_referral_commission", style="danger")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_as_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_count"
    await query.edit_message_text(
        f"📞 *Set Number Count*\n\nCurrent: *{settings['defaultNumberCount']}*\n\nSend new count (1-100):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_as_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_cooldown"
    await query.edit_message_text(
        f"⏱ *Set Cooldown*\n\nCurrent: *{settings['cooldownSeconds']} seconds*\n\nSend new cooldown (1-3600):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_as_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_price"
    await query.edit_message_text(
        f"💵 *Set Default OTP Price*\n\nCurrent: *{settings.get('defaultOtpPrice', 0.25):.2f} taka*\n\nSend new price:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="primary")]])
    )

async def cb_as_minw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_minw"
    await query.edit_message_text(
        f"💸 *Set Min Withdraw*\n\nCurrent: *{settings['minWithdraw']} taka*\n\nSend new minimum:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_admin_add_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_add_numbers"
    await query.edit_message_text(
        "➕ *Add Numbers*\n\nFormat:\n`[number]|[country code]|[service]`\n\nExample:\n`8801712345678|880|whatsapp`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    pending = [w for w in withdrawals if w["status"] == "pending"]
    msg = f"💸 *Pending Withdrawals:* {len(pending)}\n\n"

    for w in pending[:10]:
        msg += f"🆔 `{w['id'][-8:]}`\n"
        msg += f"👤 {w.get('userName','')} | 💵 {w['amount']:.2f} taka\n"
        msg += f"📱 {w['method']}: `{w['account']}`\n\n"

    buttons = []
    for w in pending[:5]:
        buttons.append([
            InlineKeyboardButton(f"✅ {w['id'][-6:]}", callback_data=f"wadm_approve:{w['id']}", style="primary"),
            InlineKeyboardButton(f"❌ {w['id'][-6:]}", callback_data=f"wadm_reject:{w['id']}", style="success"),
        ])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="danger")])

    await query.edit_message_text(msg[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_withdraw_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    wid = query.data.split(":", 1)[1]
    for w in withdrawals:
        if w["id"] == wid:
            w["status"] = "approved"
            w["processedAt"] = datetime.now().isoformat()
            await async_save_withdrawals()
            await query.answer("✅ Approved!")
            try:
                await context.bot.send_message(w["userId"],
                    f"✅ *Withdrawal Approved!*\n\n💵 {w['amount']:.2f} taka → {w['method']}: `{w['account']}`",
                    parse_mode="Markdown")
            except:
                pass
            break
    await cb_admin_withdrawals(update, context)

async def cb_withdraw_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    wid = query.data.split(":", 1)[1]
    for w in withdrawals:
        if w["id"] == wid:
            w["status"] = "rejected"
            w["processedAt"] = datetime.now().isoformat()
            e = get_user_earnings(w["userId"])
            e["balance"] = round(e["balance"] + w["amount"], 2)
            await async_save_earnings()
            await async_save_withdrawals()
            await query.answer("❌ Rejected!")
            try:
                await context.bot.send_message(w["userId"],
                    f"❌ *Withdrawal Rejected.*\n\n💵 {w['amount']:.2f} taka refunded.",
                    parse_mode="Markdown")
            except:
                pass
            break
    await cb_admin_withdrawals(update, context)

async def cb_admin_balance_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await query.edit_message_text(
        "👛 *Balance Management*\n\nSelect action:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Balance", callback_data="bal_add", style="primary"),
             InlineKeyboardButton("➖ Deduct Balance", callback_data="bal_deduct", style="success")],
            [InlineKeyboardButton("🔄 Reset Balance", callback_data="bal_reset", style="danger")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_bal_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_add_balance"
    await query.edit_message_text(
        "➕ *Add Balance*\n\nFormat: `[userId] [amount]`\nExample: `123456789 50`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]])
    )

async def cb_bal_deduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_deduct_balance"
    await query.edit_message_text(
        "➖ *Deduct Balance*\n\nFormat: `[userId] [amount]`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_bal_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_reset_balance"
    await query.edit_message_text(
        "🔄 *Reset Balance*\n\nSend the userId:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="primary")]])
    )

async def cb_admin_country_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_country_price"
    text = "💰 *Country Prices*\n\nCurrent prices:\n"
    for cc, c in countries.items():
        p = country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))
        text += f"{c['flag']} +{cc}: *{p:.2f} TK*\n"
    text += "\nSend new prices (format: `880 0.50`):"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")]]))

async def cb_admin_manage_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await query.edit_message_text(
        f"🌍 *Manage Countries*\n\nTotal: *{len(countries)}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Country", callback_data="country_add", style="danger"),
             InlineKeyboardButton("📋 List Countries", callback_data="country_list", style="primary")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="success")],
        ])
    )

async def cb_country_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "🌍 *Country List*\n\n"
    for cc, c in countries.items():
        p = country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))
        text += f"{c['flag']} *{c['name']}* (+{cc}) — {p:.2f} TK/OTP\n"
    await query.edit_message_text(text[:4000], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage_countries", style="danger")]]))

async def cb_country_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "admin_add_country"
    await query.edit_message_text(
        "🌍 *Add Country*\n\nFormat: `[code] [name] [flag]`\nExample: `880 Bangladesh 🇧🇩`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="primary")]])
    )

async def cb_admin_manage_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await query.edit_message_text(
        "🔧 *Manage Services*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 List Services", callback_data="svc_list", style="success"),
             InlineKeyboardButton("➕ Add Service", callback_data="svc_add", style="danger")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_svc_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📋 *Services List*\n\n"
    for svc_id, svc in services.items():
        text += f"• {svc['icon']} *{svc['name']}* (ID: `{svc_id}`)\n"
    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage_services", style="success")]]))

async def cb_svc_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "admin_add_service"
    await query.edit_message_text(
        "🔧 *Add Service*\n\nFormat: `[id] [name] [icon]`\nExample: `facebook Facebook 📘`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_upload_select_service"

    buttons = [[InlineKeyboardButton(f"{svc['icon']} {svc['name']}", callback_data=f"upload_svc:{svc_id}", style="primary")]
               for svc_id, svc in services.items()]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="success")])
    await query.edit_message_text("📤 *Upload Numbers*\n\nSelect service:", parse_mode="Markdown",
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
        f"📤 *Upload Numbers for {svc['name']}*\n\nSend a .txt file with numbers (one per line).",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", style="danger")]])
    )

async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = None
    get_session(uid)["data"]  = None
    await query.edit_message_text("🛠 *Admin Dashboard*\n\nSelect an option:", parse_mode="Markdown", reply_markup=admin_keyboard())

async def cb_admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = None
    get_session(uid)["data"]  = None
    await query.edit_message_text("❌ *Cancelled.*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛠 Back to Admin", callback_data="admin_back", style="primary")]]))

async def cb_admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    sess = get_session(uid)
    sess["is_admin"] = False
    sess["state"]    = None
    await query.edit_message_text("🚪 *Admin Logged Out.*", parse_mode="Markdown")

async def cb_admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    buttons = []
    for cc, svcs in numbers_by_cs.items():
        for svc_id, nums in svcs.items():
            if nums:
                buttons.append([InlineKeyboardButton(
                    f"🗑️ +{cc}/{svc_id} ({len(nums)})",
                    callback_data=f"del_confirm:{cc}:{svc_id}", style="primary"
                )])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_back", style="success")])
    await query.edit_message_text("🗑️ *Delete Numbers*\n\nSelect to delete:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    _, cc, svc_id = query.data.split(":")
    count = len(numbers_by_cs.get(cc, {}).get(svc_id, []))
    await query.edit_message_text(
        f"⚠️ *Confirm Deletion*\n\nDelete {count} numbers from +{cc}/{svc_id}?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes", callback_data=f"del_exec:{cc}:{svc_id}", style="danger"),
             InlineKeyboardButton("❌ No", callback_data="admin_back", style="primary")],
        ])
    )

async def cb_del_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    _, cc, svc_id = query.data.split(":")
    count = len(numbers_by_cs.get(cc, {}).get(svc_id, []))
    if cc in numbers_by_cs and svc_id in numbers_by_cs[cc]:
        del numbers_by_cs[cc][svc_id]
        if not numbers_by_cs[cc]:
            del numbers_by_cs[cc]
    await async_save_numbers()
    await query.edit_message_text(f"✅ *Deleted {count} numbers.*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="success")]]))

async def cb_goto_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Done.", parse_mode="Markdown")

# ─── Document Handler ───
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    sess = get_session(uid)

    if sess.get("state") == "admin_fake_numbers":
        doc   = update.message.document
        fname = (doc.file_name or "").lower()
        if not (fname.endswith(".txt") or fname.endswith(".xlsx") or fname.endswith(".xls") or fname.endswith(".csv")):
            return await update.message.reply_text("❌ শুধু .txt, .csv বা .xlsx/.xls ফাইল সাপোর্ট করে এখানে।")
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
                return await update.message.reply_text(f"❌ Excel ফাইল পড়তে সমস্যা হয়েছে: {e}")
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
            return await update.message.reply_text("❌ ফাইলে কোনো ভ্যালিড নাম্বার পাওয়া যায়নি। আবার পাঠাও।")

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

        svc = services.get(batch["service"], {"icon": "📱", "name": batch["service"]})
        return await update.message.reply_text(
            f"✅ *Fake OTP Batch #{idx+1} Added & Started!*\n\n"
            f"{svc['icon']} Service: {svc['name']}\n"
            f"🔢 Digits: {batch['digits']}\n"
            f"⏱ Max Gap: {batch['max_minutes']} min\n"
            f"📋 Numbers: {len(numbers)}টা (ফাইল থেকে)",
            parse_mode="Markdown"
        )

    if sess.get("state") != "admin_upload_file":
        return

    doc   = update.message.document
    fname = (doc.file_name or "").lower()

    if not (fname.endswith(".txt") or fname.endswith(".xlsx") or fname.endswith(".xls") or fname.endswith(".csv")):
        return await update.message.reply_text("❌ Only .txt, .csv or .xlsx files are supported.")

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
            return await update.message.reply_text(f"❌ Excel file read error: {e}")
    elif fname.endswith(".csv"):
        import csv, io
        raw  = await file.download_as_bytearray()
        text = bytes(raw).decode("utf-8", errors="ignore")
        for i, row in enumerate(csv.reader(io.StringIO(text))):
            if i == 0:
                continue  # header row skip (xlsx এর মতোই)
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
    await update.message.reply_text(f"✅ *{added} numbers uploaded successfully!*", parse_mode="Markdown")

# ─── Main Text Handler ───
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
            return await update.message.reply_text("❌ Invalid number. Example: `8801712345678`", parse_mode="Markdown")

        loading = await update.message.reply_text(
            "⏳ *Pairing code নিচ্ছে...*\n\n⌛ কয়েক সেকেন্ড অপেক্ষা করো।",
            parse_mode="Markdown"
        )

        async def wa_task():
            try:
                # আগে check করো connected কিনা
                current_state = await green_get_state(uid)
                if current_state == "authorized":
                    wa_sessions[uid] = {"connected": True}
                    try: await loading.delete()
                    except: pass
                    await context.bot.send_message(
                        uid,
                        "✅ *WhatsApp Already Connected!*\n\n"
                        "🟢 তোমার WhatsApp ইতিমধ্যে connected আছে।",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔴 Logout / Disconnect", callback_data="wa_disconnect", style="danger")],
                            [InlineKeyboardButton("📊 Check Status", callback_data="wa_status", style="primary")],
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
                    f"🔑 *Pairing Code*\n\n"
                    f"`{formatted}`\n\n"
                    f"📋 *Steps:*\n"
                    f"1. WhatsApp খোলো\n"
                    f"2. Settings → Linked Devices\n"
                    f"3. Link a Device → *Link with phone number*\n"
                    f"4. উপরের code enter করো\n\n"
                    f"✅ Code enter করার পর *Check Status* চাপো।",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Check Status", callback_data="wa_status", style="danger")],
                        [InlineKeyboardButton("🔄 New Code", callback_data="wa_connect", style="primary")],
                    ])
                )
                asyncio.create_task(monitor_wa_connection(uid, context))
            except Exception as e:
                try: await loading.delete()
                except: pass
                logger.error(f"WA error: {e}", exc_info=True)
                await context.bot.send_message(
                    uid,
                    f"❌ *Connection failed:* {str(e)[:150]}\n\nকিছুক্ষণ পর আবার try করো।",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Try Again", callback_data="wa_connect", style="success")]])
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
                "❌ *Invalid secret key!*\n\n"
                "Key টি সঠিক নয়। Authenticator app থেকে exact secret key copy করো।\n"
                "Example format: `JBSWY3DPEHPK3PXP`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data=f"totp:{svc}", style="danger")],
                    [InlineKeyboardButton("🔙 Back", callback_data="totp_back", style="primary")],
                ])
            )
            return

        icons = {"facebook": "📘", "instagram": "📸", "google": "🔍", "other": "⚙️"}
        names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "2FA"}
        icon  = icons.get(svc, "🔐")
        name  = names.get(svc, svc)

        secret_quoted = urllib.parse.quote(text)
        cb_data = f"totp_r:{svc}:{secret_quoted}"
        if len(cb_data.encode()) > 62:
            cb_data = f"totp_r:{svc}:TOOLONG"

        try:
            await update.message.reply_text(
                f"{icon} *{name} 2FA Code*\n\n"
                f"🔑 *Code:* `{result['token']}`\n\n"
                f"⏰ *{result['timeRemaining']} seconds remaining*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh Code", callback_data=cb_data, style="success")],
                    [InlineKeyboardButton("🔙 Back", callback_data="totp_back", style="danger")],
                ])
            )
        except Exception as e:
            logger.error(f"TOTP reply error uid={uid}: {e}")
            await update.message.reply_text(f"✅ 2FA Code: {result['token']} (⏰ {result['timeRemaining']}s)")
        return

    if state == "w_account":
        sess["state"] = None
        data   = sess.get("data", {})
        method = data.get("method", "bKash")
        amount = data.get("amount", 0)
        e      = get_user_earnings(uid)

        if amount > e["balance"]:
            return await update.message.reply_text("❌ Insufficient balance!")

        icon = "🟣" if method == "bKash" else "🟠"
        sess["state"] = "w_confirm"
        sess["data"]  = {"method": method, "amount": amount, "account": text}

        await update.message.reply_text(
            f"{icon} *Confirm Withdrawal*\n\n"
            f"💳 Method: {method}\n"
            f"📱 Account: `{text}`\n"
            f"💵 Amount: *{amount:.2f} taka*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="w_confirm", style="primary"),
                 InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", style="success")],
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
                    f"✅ *Referral commission set to {val:.1f}%*\n\n"
                    f"এখন থেকে প্রতি OTP এর {val:.1f}% commission referrer পাবে।",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ 0 থেকে 50 এর মধ্যে দাও।")
        except:
            await update.message.reply_text("❌ Invalid number. Example: `10`", parse_mode="Markdown")
        return

    if state == "admin_set_panel_interval" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["panelPollInterval"] = val
                save_settings()
                await update.message.reply_text(
                    f"✅ *Panel Poll Interval set to {val} sec*\n\n"
                    f"এখন থেকে প্রতিটা প্যানেল প্রতি {val} সেকেন্ড পরপর নতুন SMS/OTP চেক করবে।",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ 0 এর বেশি সংখ্যা দাও।")
        except:
            await update.message.reply_text("❌ Invalid number. Example: `1`", parse_mode="Markdown")
        return

    if state == "admin_set_queue_interval" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["queueRetryInterval"] = val
                save_settings()
                await update.message.reply_text(
                    f"✅ *Queue Retry Interval set to {val} sec*\n\n"
                    f"এখন থেকে pending DM/Group queue প্রতি {val} সেকেন্ড পরপর চেক হবে।",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ 0 এর বেশি সংখ্যা দাও।")
        except:
            await update.message.reply_text("❌ Invalid number. Example: `1`", parse_mode="Markdown")
        return

    if state == "admin_set_queue_expiry" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["queueExpiryHours"] = val
                save_settings()
                await update.message.reply_text(
                    f"✅ *Queue Expiry set to {val} hours*\n\n"
                    f"এখন থেকে {val} ঘন্টার বেশি পুরনো pending entry queue থেকে বাদ পড়ে যাবে।",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ 0 এর বেশি সংখ্যা দাও।")
        except:
            await update.message.reply_text("❌ Invalid number. Example: `3`", parse_mode="Markdown")
        return

    if state == "global_wa_phone" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        phone = re.sub(r"\D", "", text.strip())
        if len(phone) < 8:
            return await update.message.reply_text("❌ নম্বর ভুল!")
        loading = await update.message.reply_text("⏳ Connecting Global WhatsApp...")
        try:
            code = await get_wa_pairing_code(phone, f"global_{uid}")
            if not code:
                await loading.delete()
                return await update.message.reply_text("❌ Pairing code পাওয়া যায়নি।")
            global_wa_data["phone"]     = phone
            global_wa_data["uid"]       = f"global_{uid}"
            global_wa_data["connected"] = False
            save_global_wa()
            await loading.delete()
            await update.message.reply_text(
                f"📱 *Global WhatsApp Pairing Code:*\n\n"
                f"`{code}`\n\n"
                f"WhatsApp → Linked Devices → Link a Device → Enter code",
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
                                "✅ *Global WhatsApp Connected!*\n\n"
                                "এখন সব user এর number এই WA দিয়ে check হবে।",
                                parse_mode="Markdown"
                            )
                        except: pass
                        return
            asyncio.create_task(verify_global_wa())
        except Exception as e:
            await loading.delete()
            await update.message.reply_text(f"❌ Error: {e}")
        return

    if state == "admin_add_panel" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.strip().split()
        if len(parts) != 3:
            return await update.message.reply_text("❌ Format ভুল!\n`URL username password`", parse_mode="Markdown")
        url, username, password = parts
        ptype  = sess.pop("panel_type", "masdar_client")
        panels = load_panels()
        panels.append({"url": url, "username": username, "password": password, "type": ptype})
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        label = PANEL_TYPE_LABEL.get(ptype, ptype)
        await update.message.reply_text(
            f"✅ *Panel Added & Started!*\n\n🔗 `{url}`\n👤 `{username}`\n🏷️ {label}",
            parse_mode="Markdown"
        )
        return

    # ── Provider 2: ধাপে ধাপে সেটআপ (Login URL → SMS URL → Username → Password → Number Col → Message Col) ──
    if state == "admin_add_p2_loginurl" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["login_url"] = text.strip()
        sess["state"] = "admin_add_p2_smsurl"
        await update.message.reply_text(
            "➕ *Add Provider 2 Panel — Step 2/6*\n\n"
            "📄 *SMS URL* দিন (panel-এর যে page-এ SMS/OTP list দেখা যায়):\n\n"
            "Example:\n`http://139.99.69.196/client/SMSCDRStats`",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_smsurl" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["sms_url"] = text.strip()
        sess["state"] = "admin_add_p2_username"
        await update.message.reply_text(
            "➕ *Add Provider 2 Panel — Step 3/6*\n\n👤 *Username* দিন:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_username" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["username"] = text.strip()
        sess["state"] = "admin_add_p2_password"
        await update.message.reply_text(
            "➕ *Add Provider 2 Panel — Step 4/6*\n\n🔑 *Password* দিন:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_password" and (sess["is_admin"] or is_admin(uid)):
        sess["p2_data"]["password"] = text.strip()
        sess["state"] = "admin_add_p2_numcol"
        await update.message.reply_text(
            "➕ *Add Provider 2 Panel — Step 5/6*\n\n"
            "🔢 Panel-এ গিয়ে দেখো *Number* কোন কলামে আছে (যেমন 2), সেই সংখ্যাটা দাও:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_numcol" and (sess["is_admin"] or is_admin(uid)):
        try:
            sess["p2_data"]["num_col_idx"] = int(text.strip())
        except ValueError:
            return await update.message.reply_text("❌ শুধু সংখ্যা দাও, যেমন: `2`")
        sess["state"] = "admin_add_p2_msgcol"
        await update.message.reply_text(
            "➕ *Add Provider 2 Panel — Step 6/6*\n\n"
            "💬 *Message/SMS* কোন কলামে আছে (যেমন 3), সেই সংখ্যাটা দাও:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p2_msgcol" and (sess["is_admin"] or is_admin(uid)):
        try:
            msg_col_idx = int(text.strip())
        except ValueError:
            return await update.message.reply_text("❌ শুধু সংখ্যা দাও, যেমন: `3`")
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
            f"✅ *Provider 2 Panel Added & Started!*\n\n"
            f"🔗 Login: `{panel_data['url']}`\n"
            f"📄 SMS URL: `{panel_data['sms_url']}`\n"
            f"👤 `{panel_data['username']}`\n"
            f"🔢 Number Col: {panel_data['num_col_idx']} | Msg Col: {panel_data['msg_col_idx']}",
            parse_mode="Markdown"
        )
        return

    # ── Provider 3: ধাপে ধাপে (URL → Username → Password) ──
    if state == "admin_add_p3_url" and (sess["is_admin"] or is_admin(uid)):
        sess["p3_data"]["url"] = text.strip()
        sess["state"] = "admin_add_p3_username"
        subtype = sess["p3_data"].get("subtype", "ints")
        await update.message.reply_text(
            f"🧩 *Add Provider 3 ({subtype}) — Step 2/3*\n\n👤 *Username* দিন:",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p3_username" and (sess["is_admin"] or is_admin(uid)):
        sess["p3_data"]["username"] = text.strip()
        sess["state"] = "admin_add_p3_password"
        subtype = sess["p3_data"].get("subtype", "ints")
        await update.message.reply_text(
            f"🧩 *Add Provider 3 ({subtype}) — Step 3/3*\n\n🔑 *Password* দিন:",
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
            f"✅ *Provider 3 ({panel_data['subtype']}) Panel Added & Started!*\n\n"
            f"🔗 `{panel_data['url']}`\n"
            f"👤 `{panel_data['username']}`",
            parse_mode="Markdown"
        )
        return

    # ── Provider 4: Base URL → API Token ──
    if state == "admin_add_p4_url" and (sess["is_admin"] or is_admin(uid)):
        sess["p4_data"]["url"] = text.strip()
        sess["state"] = "admin_add_p4_token"
        await update.message.reply_text(
            "🌐 *Add Provider 4 — Step 2/2*\n\n"
            "🔑 *API Token* দিন (Power SMS Panel এর Profile/Agent API পেজ থেকে):",
            parse_mode="Markdown"
        )
        return

    if state == "admin_add_p4_token" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        p4 = sess.pop("p4_data", {})
        panel_data = {
            "url":      p4["url"],
            "username": "api",
            "password": text.strip(),   # API token টা password field এ রাখা হয়
            "type":     "provider4",
        }
        panels = load_panels()
        panels.append(panel_data)
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        await update.message.reply_text(
            f"✅ *Provider 4 (API) Panel Added & Started!*\n\n"
            f"🔗 `{panel_data['url']}`",
            parse_mode="Markdown"
        )
        return

    # ── Provider 5: Target URL → Target Host → Session Cookie ──
    # ── Provider 5: পুরো raw HTTP request ব্লক এক ধাপেই পার্স হয় ──
    if state == "admin_add_p5_raw" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parsed = _parse_raw_http_request(text)
        if not parsed:
            sess["state"] = "admin_add_p5_raw"  # আবার চেষ্টা করার সুযোগ দাও
            return await update.message.reply_text(
                "❌ Request ব্লকটা বুঝতে পারিনি। নিশ্চিত করো যে প্রথম লাইনে `GET /...  HTTP/1.1` আছে, "
                "এবং `Host:` ও `Cookie:` লাইন দুইটাও আছে। পুরো ব্লকটা আবার পেস্ট করো।"
            )
        full_url, host, cookie = parsed
        panel_data = {
            "url":         full_url,
            "target_host": host,
            "username":    "cookie",
            "password":    cookie,   # পুরো Cookie header ভ্যালু password field এ রাখা হয়
            "type":        "provider5",
        }
        panels = load_panels()
        panels.append(panel_data)
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = make_panel_task(panels[idx], idx, context.application)
        await update.message.reply_text(
            f"✅ *Provider 5 (Cookie) Panel Added & Started!*\n\n"
            f"🔗 `{panel_data['url'][:80]}...`\n"
            f"🌐 Host: `{panel_data['target_host']}`\n\n"
            f"⚠️ কুকির মেয়াদ শেষ হয়ে গেলে প্যানেল আর ডেটা আনতে পারবে না — তখন নতুন request কপি করে আবার Provider 5 এ প্যানেল যোগ করতে হবে।",
            parse_mode="Markdown"
        )
        return


    # ── Fake OTP Batch: Digits → Max Interval → Numbers ──
    if state == "admin_fake_digits" and (sess["is_admin"] or is_admin(uid)):
        try:
            digits = int(text.strip())
            if not (3 <= digits <= 8):
                raise ValueError
        except ValueError:
            return await update.message.reply_text("❌ ৩ থেকে ৮ এর মধ্যে একটা সংখ্যা দাও, যেমন: `5`", parse_mode="Markdown")
        sess["fake_data"]["digits"] = digits
        sess["state"] = "admin_fake_interval"
        await update.message.reply_text(
            "🎭 *Add Fake OTP Batch — Step 3/4*\n\n"
            "⏱ সর্বোচ্চ কত মিনিটের মধ্যে random gap হবে? (যেমন `10` দিলে প্রতিটা OTP ০ থেকে ১০ মিনিটের মধ্যে random সময়ে যাবে):",
            parse_mode="Markdown"
        )
        return

    if state == "admin_fake_interval" and (sess["is_admin"] or is_admin(uid)):
        try:
            max_minutes = float(text.strip())
            if max_minutes <= 0:
                raise ValueError
        except ValueError:
            return await update.message.reply_text("❌ ০ এর বেশি একটা সংখ্যা দাও, যেমন: `10`", parse_mode="Markdown")
        sess["fake_data"]["max_minutes"] = max_minutes
        sess["state"] = "admin_fake_numbers"
        await update.message.reply_text(
            "🎭 *Add Fake OTP Batch — Step 4/4*\n\n"
            "📞 নাম্বারগুলো পেস্ট করো, অথবা `.txt`/`.xlsx` ফাইল আপলোড করো (Excel হলে যেকোনো কলামে নাম্বার থাকলেই চলবে, বট নিজে খুঁজে বের করে নিবে):\n\n"
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
            return await update.message.reply_text("❌ কোনো ভ্যালিড নাম্বার পাওয়া যায়নি। আবার পেস্ট করো।")

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

        svc = services.get(batch["service"], {"icon": "📱", "name": batch["service"]})
        await update.message.reply_text(
            f"✅ *Fake OTP Batch #{idx+1} Added & Started!*\n\n"
            f"{svc['icon']} Service: {svc['name']}\n"
            f"🔢 Digits: {batch['digits']}\n"
            f"⏱ Max Gap: {batch['max_minutes']} min\n"
            f"📋 Numbers: {len(numbers)}টা",
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
        await update.message.reply_text(f"✅ *Broadcast sent to {sent} users.*", parse_mode="Markdown")
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
        await update.message.reply_text(f"✅ *{added} numbers added!*", parse_mode="Markdown")
        return

    if state == "admin_set_count" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = int(text)
            if 1 <= val <= 100:
                settings["defaultNumberCount"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Number count set to {val}.*", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Enter 1-100.")
        except:
            await update.message.reply_text("❌ Invalid number.")
        return

    if state == "admin_set_cooldown" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = int(text)
            if 1 <= val <= 3600:
                settings["cooldownSeconds"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Cooldown set to {val} seconds.*", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Enter 1-3600.")
        except:
            await update.message.reply_text("❌ Invalid number.")
        return

    if state == "admin_set_price" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val >= 0:
                settings["defaultOtpPrice"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Default OTP price set to {val:.2f} taka.*", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid price.")
        return

    if state == "admin_set_minw" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["minWithdraw"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Min withdraw set to {val:.2f} taka.*", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid amount.")
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
                await update.message.reply_text(f"✅ *{amount:.2f} taka added to {target_id}.*", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Error.")
        else:
            await update.message.reply_text("❌ Format: `[userId] [amount]`", parse_mode="Markdown")
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
                await update.message.reply_text(f"✅ *{amount:.2f} taka deducted from {target_id}.*", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Error.")
        return

    if state == "admin_reset_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        target_id = text.strip()
        e = get_user_earnings(target_id)
        e["balance"] = 0
        await async_save_earnings()
        await update.message.reply_text(f"✅ *{target_id}'s balance reset to 0.*", parse_mode="Markdown")
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
        await update.message.reply_text(f"✅ *{updated} prices updated!*", parse_mode="Markdown")
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
            await update.message.reply_text(f"✅ *Country added!*\n+{cc}: {flag} {name}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Format: `[code] [name] [flag]`", parse_mode="Markdown")
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
            await update.message.reply_text(f"✅ *Service added!*\n`{svc_id}`: {icon} {svc_name}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Format: `[id] [name] [icon]`", parse_mode="Markdown")
        return

    if state == "w_amount":
        try:
            amount = float(text)
            e      = get_user_earnings(uid)
            method = (sess.get("data") or {}).get("method", "bKash")

            if amount < settings["minWithdraw"]:
                return await update.message.reply_text(f"❌ Minimum {settings['minWithdraw']} taka")
            if amount > e["balance"]:
                return await update.message.reply_text("❌ Insufficient balance!")

            sess["state"] = "w_account"
            sess["data"]  = {"method": method, "amount": amount}
            icon = "🟣" if method == "bKash" else "🟠"
            await update.message.reply_text(
                f"{icon} *{method} — {amount:.2f} taka*\n\n📱 Your {method} number:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", style="danger")]])
            )
        except:
            pass
        return

# ─── Withdraw Confirm ───
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
        return await query.edit_message_text("❌ Balance changed. Please try again.", parse_mode="Markdown")

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
        f"✅ *Withdrawal Request Submitted!*\n\n"
        f"💳 {method}\n📱 `{account}`\n💵 {amount:.2f} taka\n\n"
        f"⏳ Admin approval pending.",
        parse_mode="Markdown"
    )

# ─── OTP Group Message Handler ───
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

    logger.info(f"📨 OTP Group [{msg_id}]: {msg_text[:120]}")
    logger.info(f"🔍 Active numbers count: {len(active_numbers)}")
    matched = find_matching_active_number(msg_text)
    if not matched:
        logger.warning(f"⚠️ No active number matched for msg: {msg_text[:200]}")
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
    svc      = services.get(data.get("service",""), {"icon": "📱", "name": "Service"})
    country  = countries.get(cc, {"flag": "🌍", "name": cc})

    notify = (
        f"📨 *OTP Received!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"📞 *Number:* `+{matched}`\n"
    )
    if otp_code:
        notify += f"\n🔑 *OTP Code:* `{otp_code}`\n"
    notify += f"\n💵 *+{earned:.2f} taka earned!*\n💰 *Balance: {balance:.2f} taka*"

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

# ─── Real-time Group Member Change Handler ───
REQUIRED_GROUP_IDS = {MAIN_CHANNEL_ID, CHAT_GROUP_ID, OTP_GROUP_ID}

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কেউ group ছাড়লে বা join করলে real-time এ handle করো"""
    try:
        cm = update.chat_member
        if not cm:
            return

        chat_id = cm.chat.id
        if chat_id not in REQUIRED_GROUP_IDS:
            return

        user    = cm.new_chat_member.user
        uid     = str(user.id)
        old_status = cm.old_chat_member.status  # আগের status
        new_status = cm.new_chat_member.status  # নতুন status

        LEFT_STATUSES   = {"left", "kicked", "banned"}
        JOINED_STATUSES = {"member", "administrator", "creator"}

        # ── কেউ group ছেড়ে গেলে ──
        if old_status in JOINED_STATUSES and new_status in LEFT_STATUSES:
            logger.info(f"👋 User {uid} left chat {chat_id}")

            if uid not in users:
                return

            # verified=False করো — referral ছাড়া user হলেও
            users[uid]["verified"] = False
            sess = get_session(uid)
            sess["verified"] = False

            # referral ছিল এবং confirmed ছিল → count কমাও
            if users[uid].get("referralVerified", False):
                users[uid]["referralVerified"] = False
                referrer_id = users[uid].get("referredBy")
                if referrer_id and referrer_id in users:
                    users[referrer_id]["referralCount"] = max(0, users[referrer_id].get("referralCount", 0) - 1)
                    if referrer_id in referrals and uid in referrals[referrer_id]:
                        referrals[referrer_id].remove(uid)
                    await async_save_referrals()
                    logger.info(f"📉 Referral removed: uid={uid} left → referrer={referrer_id} count={users[referrer_id]['referralCount']}")
                    try:
                        await context.bot.send_message(
                            int(referrer_id),
                            f"⚠️ *Referral Lost!*\n\n"
                            f"তোমার একজন referred user group ছেড়ে গেছে।\n"
                            f"👥 Current Referrals: *{users[referrer_id]['referralCount']}*",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            await async_save_users()
            logger.info(f"🔒 Access revoked for uid={uid} (left chat {chat_id})")

        # ── কেউ আবার group এ join করলে — শুধু log করো, verify এ count হবে ──
        elif old_status in LEFT_STATUSES and new_status in JOINED_STATUSES:
            logger.info(f"✅ User {uid} joined chat {chat_id}")

    except Exception as e:
        logger.error(f"handle_chat_member_update error: {e}")

# ─── /cancel command ───
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None
    if is_admin(uid):
        sess["is_admin"] = True
    await update.message.reply_text("✅ Cancelled.", reply_markup=main_keyboard())

# ─── Periodic scheduled check ───
async def scheduled_membership_check(app):
    while True:
        await asyncio.sleep(30 * 60)  # ৩০ মিনিট পর পর background check
        if not settings.get("requireVerification", True):
            continue
        logger.info(f"🔄 [Scheduled] Checking {len(users)} users...")
        blocked = 0
        for uid, user in list(users.items()):
            try:
                membership = await check_membership(int(uid), app)
                if not membership["allJoined"]:
                    users[uid]["verified"] = False
                    blocked += 1
                    sess = get_session(uid)
                    sess["verified"] = False

                    # ── রেফার কাউন্ট কমাও যদি আগে verified ছিল ──
                    if users[uid].get("referralVerified", False):
                        users[uid]["referralVerified"] = False
                        referrer_id = users[uid].get("referredBy")
                        if referrer_id and referrer_id in users:
                            current_count = users[referrer_id].get("referralCount", 0)
                            users[referrer_id]["referralCount"] = max(0, current_count - 1)
                            # referrals list থেকেও সরাও
                            if referrer_id in referrals and uid in referrals[referrer_id]:
                                referrals[referrer_id].remove(uid)
                            await async_save_referrals()
                            logger.info(f"📉 Referral removed: uid={uid} left group → referrer={referrer_id} count={users[referrer_id]['referralCount']}")
                            try:
                                await app.bot.send_message(
                                    int(referrer_id),
                                    f"⚠️ *Referral Lost!*\n\n"
                                    f"তোমার একজন referred user group ছেড়ে গেছে।\n"
                                    f"👥 Current Referrals: *{users[referrer_id]['referralCount']}*",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass

                    try:
                        pass  # message পাঠানো বন্ধ
                    except:
                        pass
                else:
                    users[uid]["verified"] = True
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Scheduled check error for {uid}: {e}")
        await async_save_users()
        logger.info(f"✅ [Scheduled] {blocked} users blocked.")

# ═══════════════════════════════════════════════
# ─── OTP Panel Scraping System ───
# ═══════════════════════════════════════════════

PANELS_FILE     = os.path.join(DATA_DIR, "panels.json")
otp_panel_tasks   = {}   # { index: asyncio.Task }
otp_panel_status  = {}   # { index: "running" | "stopped" | "error" }
otp_seen_ids      = set()

def load_panels() -> list:
    return load_json(PANELS_FILE, [])

def save_panels(panels: list):
    save_json(PANELS_FILE, panels)

# ─── Fake OTP Numbers (আসল ইউজার পুল থেকে সম্পূর্ণ আলাদা — শুধু group-এ proof দেখানোর জন্য) ───
FAKE_OTP_FILE   = os.path.join(DATA_DIR, "fake_otp_batches.json")
fake_otp_batches = load_json(FAKE_OTP_FILE, [])   # [{numbers, service, digits, max_minutes, status}]
fake_otp_tasks   = {}   # { index: asyncio.Task }

def save_fake_otp_batches():
    save_json(FAKE_OTP_FILE, fake_otp_batches)

async def run_fake_otp_batch(idx: int, app):
    """একটা batch-এর নাম্বার একে একে (random gap দিয়ে) fake OTP বানিয়ে group-এ পাঠায় — নাম্বার একবার ব্যবহার হলে বাদ।"""
    import random
    try:
        while True:
            if idx >= len(fake_otp_batches):
                return
            batch = fake_otp_batches[idx]
            if not batch["numbers"]:
                batch["status"] = "completed"
                save_fake_otp_batches()
                logger.info(f"🎭 Fake OTP batch #{idx+1} completed — সব নাম্বার শেষ")
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
            svc     = services.get(svc_id, {"icon": "📱", "name": svc_id.capitalize()})
            cc      = _guess_country_by_prefix(number)
            country = countries.get(cc, {"flag": "🌍", "name": "Unknown"})

            group_msg = (
                f"📨 *New OTP!*\n\n"
                f"{svc['icon']} *Service:* {svc['name']}\n"
                f"{country['flag']} *Country:* {country['name']}\n"
                f"📞 *Number:* +{number}\n"
            )
            asyncio.create_task(send_otp_to_group(otp_code, group_msg))
            save_fake_otp_batches()
            logger.info(f"🎭 Fake OTP sent — batch #{idx+1}, +{number}, otp={otp_code}, বাকি {len(batch['numbers'])}টা")

    except asyncio.CancelledError:
        logger.info(f"⏹️ Fake OTP batch #{idx+1} stopped")
        return
    except Exception as e:
        logger.error(f"❌ Fake OTP batch #{idx+1} error: {e}")

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
        r'(?:otp|code|pin|verification|كود|رمز|কোড)[^\d]{0,15}(\d{4,8})',
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
        'whatsapp': r'whatsapp|واتساب', 'telegram': r'telegram',
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
    # ── Provider 2 (generic username/password auto-login) ──
    if ptype == "provider2":
        return await _provider2_login(session, url, username, password, check_url)
    # ── Masdar panel (ints/login) ──
    if await _masdar_login(session, url, username, password):
        return True
    # ── IMS panel (login) ──
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
                logger.info(f"✅ Masdar login OK: {url}")
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
                logger.info(f"✅ IMS login OK: {url}")
                return True
            return False
    except Exception as e:
        logger.debug(f"IMS login failed {url}: {e}")
        return False

async def _provider2_login(session, url: str, username: str, password: str, check_url: str = None) -> bool:
    """Provider 2 — generic username/password auto-login (any panel).
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

        # ── simple math captcha (e.g. "3 + 5 = ?") ──
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
            logger.info(f"✅ Provider2 login OK: {url}")
            return True
        return False
    except Exception as e:
        logger.debug(f"Provider2 login failed {url}: {e}")
        return False

async def _provider2_fetch(session, url: str, num_col_idx=None, msg_col_idx=None) -> list:
    """Provider 2 — generic SMS/CDR fetch (AJAX DataTables auto-detect, HTML table fallback).
    num_col_idx / msg_col_idx: admin-supplied 1-based column numbers (from checking the panel
    manually). If not given, defaults to column 2/3 (0-based 1/2) with header-name auto-detect."""
    try:
        from bs4 import BeautifulSoup as _BS
        check_url = url  # admin-এর দেওয়া SMS URL সরাসরি ব্যবহার হবে
        async with session.get(check_url, ssl=False, timeout=15) as r:
            if r.status != 200:
                return []
            html_text = await r.text()

        if "login" in html_text.lower() or "signin" in html_text.lower():
            return []  # session expired — re-login হবে পরের cycle এ

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
        logger.error(f"❌ provider2 fetch error {url}: {e}")
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
        logger.error(f"❌ fetch_sms error {url}: {e}")
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
    """নাম্বারের শুরুর অংশ মিলিয়ে country code বের করে (unassigned নাম্বারের জন্য) — লম্বা কোড আগে চেক করে।"""
    for code in sorted(countries.keys(), key=len, reverse=True):
        if number.startswith(code):
            return code
    return ""

async def _handle_scraped_sms(sms: dict, source_url: str, app, panel_idx: int = None):
    """একটা SMS/OTP রেকর্ড প্রসেস করে — active_numbers match, DM+Group+Log — Provider 1/2/3/4/5 সবার জন্য শেয়ার্ড।"""
    # ── প্রতিটা প্যানেলের নিজের সাম্প্রতিক লগ (admin panel থেকে দেখার জন্য) ──
    if panel_idx is not None:
        from collections import deque as _deque
        panel_recent_log.setdefault(panel_idx, _deque(maxlen=20)).appendleft({
            "time":   datetime.now().strftime("%H:%M:%S"),
            "number": sms.get("number", ""),
            "otp":    sms.get("otp", ""),
        })

    # ── active_numbers fresh reload ──
    fresh_active = load_json(ACTIVE_NUMBERS_FILE, {})
    if fresh_active and set(fresh_active.keys()) != set(active_numbers.keys()):
        active_numbers.clear()
        active_numbers.update(fresh_active)
        rebuild_suffix_index()

    number  = sms["number"].lstrip("0")
    matched = find_active_number(number)

    if not matched:
        # ── কোনো ইউজারের কাছে assign করা নাই, তবুও গ্রুপে পোস্ট হবে (proof-of-activity) ──
        svc_id  = scraper_detect_service(sms["message"], sms.get("range", ""))
        svc     = services.get(svc_id, {"icon": "📱", "name": svc_id.capitalize()})
        cc      = _guess_country_by_prefix(number)
        country = countries.get(cc, {"flag": "🌍", "name": "Unknown"})
        group_msg = (
            f"📨 *New OTP!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"📞 *Number:* +{number}\n"
        )
        asyncio.create_task(send_otp_to_group(sms["otp"], group_msg))
        return
    an   = active_numbers[matched]
    uid  = an["userId"]
    cc   = an.get("countryCode", "")
    svc_id = scraper_detect_service(sms["message"], sms.get("range", ""))

    earned  = await add_earning(uid, cc)
    balance = get_user_earnings(uid)["balance"]
    svc     = services.get(svc_id, {"icon": "📱", "name": svc_id.capitalize()})
    country = countries.get(cc, {"flag": "🌍", "name": cc})

    notify = (
        f"📨 *OTP Received!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"📞 *Number:* `+{matched}`\n"
        f"\n🔑 *OTP Code:* `{sms['otp']}`\n"
        f"\n💵 *+{earned:.2f} taka earned!*\n"
        f"💰 *Balance: {balance:.2f} taka*"
    )

    # ── DM ও Group — fire-and-forget (ব্যাচের সবগুলো একসাথে/সাথে সাথে পাঠানো হবে) ──
    asyncio.create_task(send_dm_with_retry(app, uid, notify, log_number=matched, log_otp=sms["otp"]))

    # ── Telegram OTP Group এও পাঠাও ──
    group_msg = (
        f"📨 *New OTP!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"📞 *Number:* +{matched}\n"
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
    logger.info(f"🚀 Panel #{idx+1} started: {url}")
    otp_panel_status[idx] = "running"

    async with _aio.ClientSession(
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
        cookie_jar=_aio.CookieJar(unsafe=True)
    ) as session:
        last_login    = 0
        fail_count    = 0
        previous_otps = set()  # এই run এ যা পাঠিয়েছি
        while True:
            try:
                # ── Login / Re-login ──
                if time.time() - last_login > 540:
                    ok = await panel_login(session, url, username, password, panel.get("type"), panel.get("sms_url"))
                    if not ok:
                        fail_count += 1
                        if fail_count >= 3:
                            otp_panel_status[idx] = "error"
                            logger.error(f"❌ Panel #{idx+1} login failed 3 times, stopping.")
                            return
                        await asyncio.sleep(60)
                        continue
                    last_login = time.time()
                    fail_count = 0
                    otp_panel_status[idx] = "running"

                # ── SMS Fetch ── (Provider 2 এর জন্য আলাদা sms_url ব্যবহার হবে, বাকিদের জন্য login url-ই)
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
                logger.info(f"⏹️ Panel #{idx+1} stopped")
                return
            except Exception as e:
                otp_panel_status[idx] = "error"
                logger.error(f"❌ Panel #{idx+1} error: {e}")
                await asyncio.sleep(30)

def _p3_get_fns(bn: str, url: str, ptype: str):
    """Provider 3 — panel_fetchers.py মডিউল থেকে সঠিক login/fetch ফাংশন বেছে দেয় (otp_bot_v2.py এর _get_fns অনুসারে)।"""
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
    """Provider 3 — panel_fetchers.py (sync/requests ভিত্তিক) কোড asyncio.to_thread দিয়ে চালানো হয়,
    যাতে মূল event loop ব্লক না হয়, আর কোনো লজিক পুনরায় লিখতে না হয়।"""
    bn       = f"provider3_{idx}"
    ptype    = panel.get("subtype", "ints")
    url      = panel["url"].rstrip("/")
    username = panel["username"]
    password = panel["password"]
    logger.info(f"🚀 Provider3 Panel #{idx+1} started: {url} ({ptype})")
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
                    logger.error(f"❌ Provider3 Panel #{idx+1} login failed: {e}")
                    if fail_count >= 3:
                        otp_panel_status[idx] = "error"
                        logger.error(f"❌ Provider3 Panel #{idx+1} login failed 3 times, stopping.")
                        return
                    await asyncio.sleep(60)
                    continue

            rows = await asyncio.to_thread(fetch_fn, session_info)
            if rows is None:
                # session expired — পরের loop এ re-login হবে
                session_info = None
                await asyncio.sleep(5)
                continue

            for row in rows:
                # row format: [date, id, number, cli, None, sms]  (panel_fetchers._parse এর আউটপুট)
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
            logger.info(f"⏹️ Provider3 Panel #{idx+1} stopped")
            return
        except Exception as e:
            otp_panel_status[idx] = "error"
            logger.error(f"❌ Provider3 Panel #{idx+1} error: {e}")
            await asyncio.sleep(30)

async def _provider4_fetch(base_url: str, api_token: str) -> list:
    """Provider 4 — নিজের Power SMS Panel API (base URL + API token) দিয়ে সরাসরি CDR fetch — লগইনের দরকার নাই।"""
    try:
        import aiohttp as _aiohttp
        url     = f"{base_url.rstrip('/')}/api/sms/cdr?per_page=100&sms_type=received"
        headers = {"X-API-Token": api_token}
        async with _aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, ssl=False, timeout=15) as r:
                if r.status != 200:
                    logger.error(f"❌ Provider4 fetch failed ({r.status})")
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
        logger.error(f"❌ Provider4 fetch error: {e}")
        return []

async def run_provider4_panel(panel: dict, idx: int, app):
    """Provider 4 — API-token ভিত্তিক (Power SMS Panel এর নিজের API) — লগইন/সেশনের দরকার নাই।"""
    base_url  = panel["url"].rstrip("/")
    api_token = panel["password"]  # API token টা password field এ সেভ থাকে
    logger.info(f"🚀 Provider4 Panel #{idx+1} started: {base_url}")
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
            logger.info(f"⏹️ Provider4 Panel #{idx+1} stopped")
            return
        except Exception as e:
            otp_panel_status[idx] = "error"
            logger.error(f"❌ Provider4 Panel #{idx+1} error: {e}")
            await asyncio.sleep(30)

async def _provider5_fetch(target_url: str, target_host: str, session_cookie: str) -> list:
    """Provider 5 — কুকি (PHPSESSID) দিয়ে সরাসরি DataTables AJAX endpoint fetch — লগইন করার দরকার নাই।
    admin-এর দেওয়া target_url এ যদি আগে থেকেই query params (csstr, iColumns, ইত্যাদি) থাকে,
    সেগুলো অক্ষত রেখে শুধু তারিখ (fdate1/fdate2) আজকের তারিখ দিয়ে আপডেট করা হয়।"""
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
            # admin কোনো query দেয়নি — একদম base ধরে নাও (default 7-column masdar-ইনটাইপ)
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
                    logger.error(f"❌ Provider5 fetch failed ({r.status}) — কুকি মেয়াদ শেষ হয়ে থাকতে পারে")
                    return []
                raw_text = await r.text()
                if not raw_text.strip():
                    logger.warning("⚠️ Provider5: খালি রেসপন্স এসেছে")
                    return []
                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    logger.error(f"❌ Provider5: JSON না, সম্ভবত কুকি মেয়াদ শেষ/login page এসেছে — response শুরু: {raw_text[:200]!r}")
                    return []

        all_rows = data.get("aaData", [])
        if all_rows:
            total_rec = data.get("iTotalRecords", "?")
            disp_rec  = data.get("iTotalDisplayRecords", "?")
            logger.info(f"📊 Provider5: aaData তে {len(all_rows)}টা row পাওয়া গেছে (iTotalRecords={total_rec}, iTotalDisplayRecords={disp_rec}) — sample row0: {all_rows[0]}")
        else:
            logger.info(f"📊 Provider5: aaData খালি (response keys: {list(data.keys())})")

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
            logger.warning(f"⚠️ Provider5: {len(all_rows)}টা row ছিল কিন্তু কোনোটা থেকেই valid OTP বের করা যায়নি — row format মিলছে না মনে হচ্ছে")
        return results
    except Exception as e:
        logger.error(f"❌ Provider5 fetch error: {e}")
        return []

async def run_provider5_panel(panel: dict, idx: int, app):
    """Provider 5 — session cookie (PHPSESSID) ভিত্তিক — লগইন করার দরকার নাই, কুকি মেয়াদ শেষ হলে অ্যাডমিনকে নতুন কুকি বসাতে হবে।"""
    target_url    = panel["url"]
    target_host   = panel.get("target_host", "")
    session_cookie = panel["password"]  # কুকি ভ্যালু password field এ সেভ থাকে
    logger.info(f"🚀 Provider5 Panel #{idx+1} started: {target_url}")
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
            logger.info(f"⏹️ Provider5 Panel #{idx+1} stopped")
            return
        except Exception as e:
            otp_panel_status[idx] = "error"
            logger.error(f"❌ Provider5 Panel #{idx+1} error: {e}")
            await asyncio.sleep(30)

def make_panel_task(panel: dict, idx: int, app):
    """panel এর type অনুযায়ী সঠিক runner দিয়ে task তৈরি করে।"""
    ptype = panel.get("type")
    if ptype == "provider3":
        return asyncio.create_task(run_provider3_panel(panel, idx, app))
    if ptype == "provider4":
        return asyncio.create_task(run_provider4_panel(panel, idx, app))
    if ptype == "provider5":
        return asyncio.create_task(run_provider5_panel(panel, idx, app))
    return asyncio.create_task(run_panel(panel, idx, app))

def start_all_panels(app):
    rebuild_suffix_index()  # startup এ index তৈরি করো
    panels = load_panels()
    for i, p in enumerate(panels):
        if i not in otp_panel_tasks or otp_panel_tasks[i].done():
            otp_panel_tasks[i] = make_panel_task(p, i, app)
    logger.info(f"📡 {len(panels)} panel(s) started")

# ── Admin Panel Callbacks ──
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
        return await query.answer("❌ Admin only")
    await query.answer()
    panels = load_panels()
    msg = f"📡 *OTP Panels*\n\nTotal: *{len(panels)}*\n\n"
    for i, p in enumerate(panels):
        status = otp_panel_status.get(i, "stopped")
        if status == "running":   icon = "🟢 Running"
        elif status == "error":   icon = "🔴 Login Failed"
        else:                     icon = "⚫ Stopped"
        if p.get('type') == "provider3":
            label = f"Provider 3 ({p.get('subtype', 'ints')})"
        elif p.get('type') == "provider4":
            label = "Provider 4 (API)"
        elif p.get('type') == "provider5":
            label = "Provider 5 (Cookie)"
        else:
            label = PANEL_TYPE_LABEL.get(p.get('type', ''), p.get('type', ''))
        msg += f"*{i+1}.* `{p['url']}`\n👤 `{p['username']}` | 🏷️ {label} | {icon}\n\n"
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Panel", callback_data="panel_add:auto", style="primary"),
         InlineKeyboardButton("🔑 Provider 2", callback_data="panel_add:provider2", style="success")],
        [InlineKeyboardButton("🧩 Provider 3", callback_data="panel_add_p3_menu", style="danger"),
         InlineKeyboardButton("🌐 Provider 4", callback_data="panel_add_p4_menu", style="primary")],
        [InlineKeyboardButton("🍪 Provider 5", callback_data="panel_add_p5_menu", style="success")],
        [InlineKeyboardButton("📜 View Logs", callback_data="panel_logs_menu", style="primary")],
        [InlineKeyboardButton("🗑️ Delete Panel", callback_data="panel_del", style="danger"),
         InlineKeyboardButton("🔄 Restart All",  callback_data="panel_restart", style="success")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
    ]))

async def cb_panel_logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    panels = load_panels()
    if not panels:
        return await query.edit_message_text(
            "📜 কোনো প্যানেল যোগ করা নেই।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels", style="primary")]])
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
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panels", style="primary")])
    await query.edit_message_text(
        "📜 *কোন প্যানেলের লগ দেখতে চাও?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_panel_log_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    idx    = int(query.data.split(":")[1])
    panels = load_panels()
    if idx >= len(panels):
        return await query.edit_message_text("❌ প্যানেল খুঁজে পাওয়া যায়নি।")
    p      = panels[idx]
    status = otp_panel_status.get(idx, "stopped")
    icon   = {"running": "🟢 Running", "error": "🔴 Login Failed"}.get(status, "⚫ Stopped")
    entries = list(panel_recent_log.get(idx, []))

    msg = f"📜 *Panel #{idx+1} Live Log* | {icon}\n🔗 `{p['url'][:60]}`\n\n"
    if not entries:
        msg += "এখনো কোনো OTP/নাম্বার আসেনি।"
    else:
        for e in entries:
            msg += f"⏱ `{e['time']}` | 📞 +{e['number']} | 🔑 `{e['otp']}`\n"

    kb_rows = [[InlineKeyboardButton("🔄 Refresh", callback_data=f"panel_log:{idx}", style="success")]]
    if p.get("type") == "provider5":
        kb_rows.append([InlineKeyboardButton("🔍 Check Session (Cookie)", callback_data=f"panel_check:{idx}", style="danger")])
    kb_rows.append([InlineKeyboardButton("🔙 Back", callback_data="panel_logs_menu", style="primary")])

    await query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )

async def _provider5_check_session(panel: dict) -> str:
    """Provider 5 এর কুকি/সেশন এখনো ভ্যালিড কিনা সরাসরি চেক করে human-readable status রিটার্ন করে।"""
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
            return f"❌ *Session Invalid* — HTTP {status_code} এসেছে। কুকি expire হয়ে গেছে, নতুন request কপি করে আবার Provider 5 এ panel add করো।"
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            return f"❌ *Session Invalid* — JSON এর বদলে HTML/login page এসেছে (কুকি expire)।\n\nResponse শুরু:\n`{raw_text[:150]}`"

        total = data.get("iTotalRecords", "N/A")
        rows  = len(data.get("aaData", []))
        return f"✅ *Session Valid!*\n\nসার্ভার থেকে ঠিকঠাক JSON রেসপন্স এসেছে।\niTotalRecords: `{total}`\naaData rows: `{rows}`"
    except Exception as e:
        return f"⚠️ চেক করতে গিয়ে error হয়েছে: `{e}`"

async def cb_panel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer("🔍 চেক করা হচ্ছে...")
    idx    = int(query.data.split(":")[1])
    panels = load_panels()
    if idx >= len(panels):
        return await query.edit_message_text("❌ প্যানেল খুঁজে পাওয়া যায়নি।")
    p = panels[idx]
    if p.get("type") != "provider5":
        return await query.answer("এই চেক শুধু Provider 5 (Cookie) প্যানেলের জন্য।", show_alert=True)

    result = await _provider5_check_session(p)
    await query.edit_message_text(
        f"🔍 *Panel #{idx+1} Session Check*\n🔗 `{p['url'][:60]}`\n\n{result}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 আবার চেক করো", callback_data=f"panel_check:{idx}", style="danger")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"panel_log:{idx}", style="primary")],
        ])
    )

# ═══════════════════════ Fake OTP Numbers — Admin UI ═══════════════════════
async def cb_fake_otp_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await _render_fake_otp_menu(query)

async def _render_fake_otp_menu(query):
    msg = f"🎭 *Fake OTP Numbers*\n\nTotal Batches: *{len(fake_otp_batches)}*\n\n"
    rows = []
    if not fake_otp_batches:
        msg += "_এখনো কোনো batch যোগ করা হয়নি।_"
    else:
        for i, b in enumerate(fake_otp_batches):
            svc    = services.get(b.get("service", "other"), {"icon": "📱", "name": b.get("service", "other")})
            status = b.get("status", "running")
            icon   = "🟢 Running" if status == "running" and b.get("numbers") else ("⚪ Completed" if not b.get("numbers") else "⏹️ Stopped")
            msg += (
                f"*Batch #{i+1}* — {svc['icon']} {svc['name']}\n"
                f"🔢 {b.get('digits')} digit | ⏱ max {b.get('max_minutes')} min | "
                f"📋 বাকি {len(b.get('numbers', []))}টা | {icon}\n\n"
            )
            rows.append([InlineKeyboardButton(f"🗑️ Stop/Delete Batch #{i+1}", callback_data=f"fake_del:{i}", style="danger")])

    rows.append([InlineKeyboardButton("➕ Add Batch", callback_data="fake_otp_add", style="success")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")])
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))

async def cb_fake_otp_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
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
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="fake_otp_menu", style="danger")])
    await query.edit_message_text(
        "🎭 *Add Fake OTP Batch — Step 1/4*\n\n📱 কোন Service-এর নামে fake OTP যাবে, বেছে নাও:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_fake_svc_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    sess   = get_session(uid)
    sess["state"]     = "admin_fake_digits"
    sess["fake_data"] = {"service": svc_id}
    await query.edit_message_text(
        "🎭 *Add Fake OTP Batch — Step 2/4*\n\n"
        "🔢 OTP কোড কত ডিজিটের হবে? (যেমন `5`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="fake_otp_menu", style="danger")]])
    )

async def cb_fake_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    idx = int(query.data.split(":")[1])
    if idx >= len(fake_otp_batches):
        return await query.edit_message_text("❌ Batch খুঁজে পাওয়া যায়নি।")
    task = fake_otp_tasks.pop(idx, None)
    if task:
        task.cancel()
    fake_otp_batches.pop(idx)
    save_fake_otp_batches()
    # ── ইনডেক্স শিফট হওয়ায় বাকি টাস্কগুলোর ম্যাপিং ঠিক করা ──
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
        return await query.answer("❌ Admin only")
    await query.answer()

    connected = global_wa_data.get("connected", False)
    enabled   = global_wa_data.get("enabled", False)
    phone     = global_wa_data.get("phone", "N/A")

    status_icon = "🟢" if connected else "🔴"
    toggle_icon = "✅ ON" if enabled else "❌ OFF"

    msg = (
        f"📱 *Global WhatsApp System*\n\n"
        f"*Status:* {status_icon} {'Connected' if connected else 'Disconnected'}\n"
        f"*Phone:* `{phone}`\n"
        f"*WA Check:* {toggle_icon}\n\n"
        f"একটা WhatsApp connect করলে সব user এর number check হবে।"
    )

    buttons = []
    if connected:
        buttons.append([
            InlineKeyboardButton(
                f"{'🔴 Disable' if enabled else '🟢 Enable'} WA Check",
                callback_data="global_wa_toggle",
                style="success" if not enabled else "danger"
            ),
            InlineKeyboardButton("🔌 Disconnect", callback_data="global_wa_disconnect", style="danger")
        ])
    else:
        buttons.append([InlineKeyboardButton("📱 Connect WhatsApp", callback_data="global_wa_connect", style="primary")])

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")])
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_global_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "global_wa_phone"
    await query.edit_message_text(
        "📱 *Global WhatsApp Connect*\n\n"
        "WhatsApp নম্বর দাও (country code সহ):\n"
        "Example: `8801712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="admin_global_wa", style="danger")
        ]])
    )

async def cb_global_wa_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    global_wa_data["enabled"] = not global_wa_data.get("enabled", False)
    save_global_wa()
    status = "✅ চালু" if global_wa_data["enabled"] else "❌ বন্ধ"
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
    await query.answer("🔌 Global WA Disconnected", show_alert=True)
    await cb_admin_global_wa(update, context)

# ─── Global WA handle_text ───
# (handle_text এ state "global_wa_phone" handle করা হবে)

async def cb_panel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    await query.answer()
    ptype = query.data.split(":")[1] if ":" in query.data else "masdar_client"
    label = PANEL_TYPE_LABEL.get(ptype, ptype)
    cancel_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")
    ]])

    if ptype == "provider2":
        # ── Provider 2: ধাপে ধাপে জিজ্ঞেস করবে — Login URL → SMS URL → Username → Password → কলাম ──
        sess = get_session(uid)
        sess["state"]     = "admin_add_p2_loginurl"
        sess["p2_data"]   = {}
        await query.edit_message_text(
            f"➕ *Add {label} Panel — Step 1/6*\n\n"
            f"🔗 *Login URL* দিন (যেখানে username/password দিয়ে লগইন করবে):\n\n"
            f"Example:\n`http://139.99.69.196/login`",
            parse_mode="Markdown",
            reply_markup=cancel_kb
        )
        return

    get_session(uid)["state"]      = "admin_add_panel"
    get_session(uid)["panel_type"] = ptype
    prompt = (
        f"➕ *Add {label} Panel*\n\n"
        f"Format: `URL username password`\n\n"
        f"Example:\n`http://139.99.69.196 admin admin123`"
    )
    await query.edit_message_text(prompt, parse_mode="Markdown", reply_markup=cancel_kb)

# ── Provider 3 — Known Panels (আগে থেকে URL+Type সেট করা) + Custom Panel ──
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
        return await query.answer("❌ Admin only")
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
    rows.append([InlineKeyboardButton("✏️ Custom Panel", callback_data="panel_add_p3_custom", style="primary")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")])
    await query.edit_message_text(
        "🧩 *Add Provider 3 Panel*\n\n"
        "চেনা প্যানেল হলে নিচ থেকে নাম বেছে নাও (URL+Type আগে থেকেই সেট করা থাকবে, শুধু username/password দিতে হবে)।\n\n"
        "লিস্টে না থাকলে *✏️ Custom Panel* চাপো।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_p3_builtin_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    name = query.data.split(":", 1)[1]
    info = BUILTIN_PANELS.get(name)
    if not info:
        return await query.edit_message_text("❌ প্যানেল খুঁজে পাওয়া যায়নি।")
    sess = get_session(uid)
    sess["state"]   = "admin_add_p3_username"
    sess["p3_data"] = {"subtype": info["ptype"], "url": info["url"], "builtin_name": name}
    await query.edit_message_text(
        f"🧩 *Add {name} ({info['ptype']}) — Step 1/2*\n\n"
        f"🔗 URL: `{info['url']}` (auto)\n\n"
        f"👤 *Username* দিন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")]])
    )

async def cb_panel_add_p3_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
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
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")])
    await query.edit_message_text(
        "✏️ *Custom Panel*\n\n"
        "তোমার প্যানেলটা কোন টাইপের সেটা বেছে নাও:\n\n"
        "👉 বেশিরভাগ প্যানেল *ints* টাইপ — না জানলে প্রথমে *ints* দিয়ে ট্রাই করো।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_p3_type_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    ptype = query.data.split(":")[1]
    sess  = get_session(uid)
    sess["state"]   = "admin_add_p3_url"
    sess["p3_data"] = {"subtype": ptype}
    await query.edit_message_text(
        f"🧩 *Add Provider 3 ({ptype}) — Step 1/3*\n\n"
        f"🔗 *Panel URL* দিন:\n\n"
        f"Example:\n`http://51.77.52.79/ints`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")]])
    )

# ── Provider 4 — Power SMS Panel এর নিজস্ব API (base URL + API token, login লাগে না) ──
async def cb_panel_add_p4_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"]   = "admin_add_p4_url"
    sess["p4_data"] = {}
    await query.edit_message_text(
        "🌐 *Add Provider 4 — Step 1/2*\n\n"
        "🔗 *Base URL* দিন:\n\n"
        "Example:\n`https://your-power-sms-panel.com`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")]])
    )

# ── Provider 5 — Session Cookie (PHPSESSID) ভিত্তিক, লগইন করার দরকার নাই ──
async def cb_panel_add_p5_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_add_p5_raw"
    await query.edit_message_text(
        "🍪 *Add Provider 5 (Cookie) — Raw Request*\n\n"
        "ব্রাউজারের Network Tab থেকে পুরো রিকোয়েস্ট ব্লকটা (GET লাইন + Host + Cookie সহ) "
        "হুবহু কপি করে **একবারেই** পেস্ট করে দাও — বট নিজে থেকেই URL, Host আর Cookie বের করে নিবে।\n\n"
        "Example:\n"
        "```\n"
        "GET /ints/agent/res/data_smscdr.php?fdate1=...&csstr=... HTTP/1.1\n"
        "Host: 168.119.13.175\n"
        "...\n"
        "Cookie: PHPSESSID=abc123...\n"
        "```",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", style="danger")]])
    )

def _parse_raw_http_request(raw_text: str):
    """ব্রাউজার থেকে কপি করা raw HTTP request ব্লক থেকে URL, Host, Cookie বের করে।
    রিটার্ন করে (full_url, host, cookie_header) — কিছু না পেলে None।"""
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
        return await query.edit_message_text("❌ কোনো panel নেই।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels")]]))
    buttons = [[InlineKeyboardButton(f"🗑️ {i+1}. {p['url']}", callback_data=f"panel_del_confirm:{i}")]
               for i, p in enumerate(panels)]
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panels", style="primary")])
    await query.edit_message_text("🗑️ *কোন panel delete করবে?*", parse_mode="Markdown",
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
        await query.edit_message_text(f"✅ *Deleted:* `{removed['url']}`", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels")]]))

async def cb_panel_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Restarting...")
    for task in otp_panel_tasks.values():
        if not task.done():
            task.cancel()
    otp_panel_tasks.clear()
    start_all_panels(context.application)
    await query.edit_message_text("✅ *All panels restarted!*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels")]]))

PE_EMOJI_LIST = [
    "📱",
    "🔴",
    "📊",
    "☎",
    "📧",
    "🔐",
    "💰",
    "💸",
    "👥",
    "💬",
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "✅",
    "📢",
    "📋",
    "➕",
    "📤",
    "🗑",
    "🔧",
    "🌍",
    "⚙",
    "👛",
    "📡",
    "🎭",
    "🚪",
    "🔙",
    "📨",
    "🔄",
    "🔗",
    "🟣",
    "🟠",
    "❌",
    "📬",
    "🆕",
    "📘",
    "📸",
    "🔍",
    "📞",
    "⏱",
    "💵",
    "🏧",
    "📥",
    "➖",
    "🛠",
    "🔑",
    "🧩",
    "🌐",
    "🍪",
    "📜",
    "🔌",
    "✏",
    "✨",
    "🟢",
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
        "✨ Premium Emoji\n\n"
        f"স্ট্যাটাস: {'🟢 ON' if on else '🔴 OFF'}\n"
        f"সেট করা ইমোজি: {done}/{len(PE_EMOJI_LIST)}\n\n"
        "ON থাকলে বাটনে প্রিমিয়াম ইমোজি দেখাবে, OFF থাকলে সাধারণ ইমোজি।\n"
        "(বটের মালিকের Telegram Premium থাকতে হবে। যাদের Premium নেই তারা সাধারণ ইমোজি দেখবে।)"
    )
    if forced_off:
        text += "\n\n⚠️ PREMIUM_EMOJI_OFF=1 সেট করা আছে, তাই ON করলেও চালু হবে না।"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 বন্ধ করুন (OFF)" if on else "🟢 চালু করুন (ON)",
                              callback_data="pe_toggle", style="danger" if on else "success")],
        [InlineKeyboardButton("📋 ইমোজি সেট করুন", callback_data="pe_list:0", style="primary")],
        [InlineKeyboardButton("🗑️ সব ইমোজি মুছুন", callback_data="pe_reset", style="danger")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", style="primary")],
    ])
    await _pe_edit(query, text, kb)

async def cb_pe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
    await query.answer()
    await _pe_show_menu(query, uid)

async def cb_pe_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
    cfg = _pe_cfg_ensure()
    if not cfg["enabled"] and not cfg["map"]:
        return await query.answer("আগে অন্তত একটা ইমোজি সেট করুন।", show_alert=True)
    cfg["enabled"] = not cfg["enabled"]
    save_settings()
    await query.answer("🟢 ON" if cfg["enabled"] else "🔴 OFF")
    await _pe_show_menu(query, uid)

async def cb_pe_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
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
        mark = "✅" if cfg["map"].get(key) else "➖"
        row.append(InlineKeyboardButton(f"{key} {mark}", callback_data=f"pe_set:{start + i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"pe_list:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"pe_list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("📦 এই পেজ একসাথে সেট করুন", callback_data=f"pe_bulk:{page}", style="success")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="pe_menu", style="primary")])
    text = (
        f"✨ Premium Emoji — পেজ {page + 1}/{total_pages}\n\n"
        "✅ = সেট করা আছে, ➖ = সেট করা নেই\n"
        "যেটা সেট করতে চান তার বাটনে চাপুন।"
    )
    await _pe_edit(query, text, InlineKeyboardMarkup(rows))

async def cb_pe_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
    await query.answer()
    idx = int(query.data.split(":")[1])
    if idx < 0 or idx >= len(PE_EMOJI_LIST):
        return
    sess = get_session(uid)
    sess["state"] = "pe_set"
    sess["data"] = {"idx": idx}
    key = PE_EMOJI_LIST[idx]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"pe_list:{idx // PE_PAGE_SIZE}", style="danger")]])
    await _pe_edit(query, f"{key} এর জায়গায় যে প্রিমিয়াম ইমোজি বসাতে চান, সেটা এখন পাঠান।\n\n(শুধু একটা প্রিমিয়াম ইমোজি, সাথে অন্য কিছু লিখবেন না।)", kb)

async def cb_pe_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
    await query.answer()
    page = int(query.data.split(":")[1])
    items = PE_EMOJI_LIST[page * PE_PAGE_SIZE:(page + 1) * PE_PAGE_SIZE]
    if not items:
        return
    sess = get_session(uid)
    sess["state"] = "pe_bulk"
    sess["data"] = {"page": page}
    lines = "\n".join(f"{n}. {k}" for n, k in enumerate(items, 1))
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"pe_list:{page}", style="danger")]])
    await _pe_edit(
        query,
        f"নিচের ক্রমে {len(items)}টা প্রিমিয়াম ইমোজি একটা মেসেজে পাঠান (মাঝে লেখা বা স্পেস না দিলেও চলবে):\n\n{lines}\n\n"
        "কম পাঠালে শুরু থেকে যতগুলো পাঠাবেন ততগুলোই সেট হবে।",
        kb,
    )

async def cb_pe_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ হ্যাঁ, মুছুন", callback_data="pe_reset_yes", style="danger")],
        [InlineKeyboardButton("🔙 Back", callback_data="pe_menu", style="primary")],
    ])
    await _pe_edit(query, "সেট করা সব প্রিমিয়াম ইমোজি মুছে ফেলবেন? (ফিচারটাও OFF হয়ে যাবে)", kb)

async def cb_pe_reset_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return await query.answer("❌ Admin only", show_alert=True)
    cfg = _pe_cfg_ensure()
    cfg["map"] = {}
    cfg["enabled"] = False
    save_settings()
    await query.answer("মুছে ফেলা হয়েছে")
    await _pe_show_menu(query, uid)

async def _pe_receive(update: Update, sess: dict):
    """অ্যাডমিন প্রিমিয়াম ইমোজি পাঠালে সেটার ID সেভ করে।"""
    msg = update.message
    ents = [e for e in (msg.entities or [])
            if getattr(e, "type", None) == "custom_emoji" and getattr(e, "custom_emoji_id", None)]
    if not ents:
        return await msg.reply_text("❌ কোনো প্রিমিয়াম ইমোজি পাওয়া যায়নি। সাধারণ ইমোজি নয়, প্রিমিয়াম ইমোজি পাঠান।")
    cfg = _pe_cfg_ensure()
    data = sess.get("data") or {}
    if sess.get("state") == "pe_set":
        idx = int(data.get("idx", 0))
        key = PE_EMOJI_LIST[idx]
        cfg["map"][key] = ents[0].custom_emoji_id
        save_settings()
        sess["state"] = None
        sess["data"] = None
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data=f"pe_list:{idx // PE_PAGE_SIZE}", style="primary")]])
        return await msg.reply_text(f"✅ {key} এর প্রিমিয়াম ইমোজি সেট হয়েছে।", reply_markup=kb)
    page = int(data.get("page", 0))
    items = PE_EMOJI_LIST[page * PE_PAGE_SIZE:(page + 1) * PE_PAGE_SIZE]
    if len(ents) > len(items):
        return await msg.reply_text(f"❌ এই পেজে মাত্র {len(items)}টা ইমোজি আছে, আপনি {len(ents)}টা পাঠিয়েছেন। আবার পাঠান।")
    for key, e in zip(items, ents):
        cfg["map"][key] = e.custom_emoji_id
    save_settings()
    sess["state"] = None
    sess["data"] = None
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data=f"pe_list:{page}", style="primary")]])
    extra = "" if len(ents) == len(items) else f"\n(বাকি {len(items) - len(ents)}টা সেট করা হয়নি)"
    return await msg.reply_text(f"✅ {len(ents)}টা প্রিমিয়াম ইমোজি সেট হয়েছে।{extra}", reply_markup=kb)

async def cmd_pe_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not _pe_is_admin(uid):
        return
    cfg = _pe_cfg_ensure()
    cfg["enabled"] = False
    save_settings()
    await update.message.reply_text("✅ Premium Emoji বন্ধ (OFF) করা হয়েছে।")

# ─── Main ───
def main():
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("adminlogin", cmd_adminlogin))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("pe_off", cmd_pe_off))

    app.add_handler(MessageHandler(filters.Regex("^(?:☎️ |📞 )?Get Numbers?$"), handle_get_numbers))
    app.add_handler(MessageHandler(filters.Regex("^(?:📧.*|Get Tempmail)$"), handle_tempmail))
    app.add_handler(MessageHandler(filters.Regex("^(?:🔐.*|2FA)$"), handle_2fa))
    app.add_handler(MessageHandler(filters.Regex("^(?:💰 )?Balances$"), handle_balance))
    app.add_handler(MessageHandler(filters.Regex("^(?:💸 )?Withdraw$"), handle_withdraw))
    app.add_handler(MessageHandler(filters.Regex("^(?:👥 )?Referral$"), handle_referral))
    app.add_handler(MessageHandler(filters.Regex("^(?:💬 )?Support$"), handle_support))

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

    # ── Real-time group member change (leave/join) ──
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    async def post_init(application):
        global _tg_app
        _tg_app = application
        asyncio.create_task(scheduled_membership_check(application))
        asyncio.create_task(green_api_monitor(application))
        asyncio.create_task(dm_retry_worker(application))  # ── rate-limit এ miss হওয়া DM পরে পাঠানোর worker ──
        await start_http_server()
        start_all_panels(application)  # ── OTP Panels শুরু করো ──
        start_all_fake_otp_batches(application)  # ── Fake OTP batches শুরু করো ──

    app.post_init = post_init

    logger.info("="*50)
    logger.info("🚀 Starting Earning Hub Bot (Python)...")
    logger.info(f"📢 Main Channel: {MAIN_CHANNEL_ID}")
    logger.info(f"💬 Chat Group: {CHAT_GROUP_ID}")
    logger.info(f"📨 OTP Group: {OTP_GROUP_ID}")
    logger.info("="*50)

    app.run_polling(allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"])

if __name__ == "__main__":
    main()
