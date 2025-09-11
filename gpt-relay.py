import os
import time
import smtplib
import email
import imaplib
import requests
import logging
from logging.handlers import RotatingFileHandler
from dotenv import dotenv_values

# ----------------------
# Config Loader
# ----------------------
CONFIG_PATH = "config.env"
_last_mtime = 0
_config_cache = {}

def load_config():
    """Reload config.env only if the file has changed since last load, and log changes."""
    global _last_mtime, _config_cache
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
        if mtime != _last_mtime:
            _last_mtime = mtime
            new_config = dotenv_values(CONFIG_PATH)

            if 'logger' in globals():
                if _config_cache:
                    # Compare old vs new config
                    for key, new_value in new_config.items():
                        old_value = _config_cache.get(key)
                        if old_value != new_value:
                            logger.info("Config change: %s = %s (was %s)", key, new_value, old_value)

                    # Detect removed keys
                    for key in set(_config_cache) - set(new_config):
                        logger.info("Config key removed: %s (was %s)", key, _config_cache[key])

                logger.info("Reloaded config.env due to file change.")

            _config_cache = new_config
    except Exception:
        if 'logger' in globals():
            logger.exception("Failed to reload config.env")
        _config_cache = {}
    return _config_cache

# ----------------------
# Initial config load
# ----------------------
config = load_config()

# Configurable log level (default INFO if missing/invalid)
LOG_LEVEL = config.get("LOG_LEVEL", "INFO").upper()
level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
LOG_LEVEL = level_map.get(LOG_LEVEL, logging.INFO)

# ----------------------
# Logging Configuration
# ----------------------
logger = logging.getLogger("gmail_bot")
logger.setLevel(LOG_LEVEL)

file_handler = RotatingFileHandler(
    "service.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)

# CSV format: timestamp, level, message
csv_formatter = logging.Formatter(
    '%(asctime)s,%(levelname)s,"%(message)s"', datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(csv_formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter(
    "%(levelname)s - %(message)s"
)
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ----------------------
# Core Functions
# ----------------------
def call_openai(prompt, config):
    OPENAI_KEY = config["OPENAI_API_KEY"]
    MODEL = config.get("OPENAI_MODEL", "gpt-4o-mini")

    logger.debug("Calling OpenAI with prompt length: %d", len(prompt))
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful email assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
        logger.debug("OpenAI response received (length %d).", len(answer))
        return answer
    except Exception:
        logger.exception("OpenAI API call failed.")
        raise

def process_email(msg, config, whitelist):
    from_addr = email.utils.parseaddr(msg["From"])[1].lower()
    subject = msg.get("Subject", "")
    logger.info("Processing email from %s | Subject: %s", from_addr, subject)

    if from_addr not in whitelist:
        logger.warning("Unauthorized sender: %s", from_addr)
        return f"Sender {from_addr} not authorized.", from_addr, subject

    # Extract body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
                except Exception:
                    logger.exception("Failed to decode multipart email body.")
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        except Exception:
            logger.exception("Failed to decode email body.")

    logger.debug("Email body extracted (length %d).", len(body))

    prompt = f"{config['CHATGPT_PROMPT']}\n\nFrom: {from_addr}\nSubject: {subject}\n\nBody:\n{body.strip()}"
    answer = call_openai(prompt, config)
    return answer, from_addr, subject

def send_reply(to_addr, subject, text, config):
    GMAIL_USER = config["GMAIL_USER"]
    GMAIL_PASS = config["GMAIL_PASS"]

    subj = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg = f"From: {GMAIL_USER}\r\nTo: {to_addr}\r\nSubject: {subj}\r\n\r\n{text}"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            logger.info("Logged into Gmail SMTP.")
            smtp.sendmail(GMAIL_USER, [to_addr], msg.encode("utf-8"))
            logger.info("Reply sent to %s | Subject: %s", to_addr, subj)
    except Exception:
        logger.exception("Failed to send reply to %s", to_addr)
        raise

def poll_inbox():
    config = load_config()  # reload if file changed

    # Update logger level dynamically
    log_level = config.get("LOG_LEVEL", "INFO").upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    logger.setLevel(level_map.get(log_level, logging.INFO))

    GMAIL_USER = config["GMAIL_USER"]
    GMAIL_PASS = config["GMAIL_PASS"]

    # Load whitelist each cycle (in case updated)
    try:
        with open("whitelist.txt") as f:
            WHITELIST = {line.strip().lower() for line in f if line.strip()}
    except Exception:
        WHITELIST = set()
        logger.warning("Could not load whitelist.txt")

    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(GMAIL_USER, GMAIL_PASS)
            logger.info("Logged into Gmail IMAP.")
            imap.select("INBOX")
            typ, data = imap.search(None, "UNSEEN")
            if typ != "OK":
                logger.error("Failed to search inbox.")
                return

            unseen = data[0].split()
            logger.info("Found %d unseen emails.", len(unseen))

            for num in unseen:
                try:
                    typ, msg_data = imap.fetch(num, "(RFC822)")
                    if typ != "OK":
                        logger.error("Failed to fetch message UID %s", num)
                        continue

                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    answer, from_addr, subject = process_email(msg, config, WHITELIST)
                    send_reply(from_addr, subject, answer, config)

                except Exception:
                    logger.exception("Error while processing message UID %s", num)

            imap.close()
            imap.logout()
            logger.debug("IMAP session closed.")

    except Exception:
        logger.exception("Error in poll_inbox().")

    # return current poll interval
    return int(config.get("POLL_INTERVAL", "900"))

# ----------------------
# Main Loop
# ----------------------
if __name__ == "__main__":
    while True:
        poll_interval = poll_inbox()
        logger.debug("Sleeping for %d seconds.", poll_interval)
        time.sleep(poll_interval)
