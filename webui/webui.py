from flask import Flask, render_template, request, redirect, url_for
import os
import yaml
import shutil
import subprocess
import openai
import smtplib
from datetime import datetime
from glob import glob


app = Flask(__name__)

# File paths
WHITELIST_FILE = "../whitelist.txt"
CONFIG_FILE = "../config.env"
LOG_FILE = "../service.log"
BACKUP_DIR = "backups"
DEFAULTS_FILE = "defaults.yaml"

# Load defaults from YAML
with open(DEFAULTS_FILE, "r") as f:
    raw_defaults = yaml.safe_load(f)

# Flatten whitelist array into a string for the editor
DEFAULTS = {
    "whitelist": "\n".join(raw_defaults.get("whitelist", [])) + "\n",
    "config": raw_defaults.get("config", "")
}

def read_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)

def parse_env_file(path):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                data[key.strip()] = val.strip()
    return data

def write_env_file(path, data):
    lines = [
        "# Gmail credentials",
        f"GMAIL_USER={data.get('GMAIL_USER','')}",
        f"GMAIL_PASS={data.get('GMAIL_PASS','')}",
        "",
        "# OpenAI settings",
        f"OPENAI_API_KEY={data.get('OPENAI_API_KEY','')}",
        f"OPENAI_MODEL={data.get('OPENAI_MODEL','')}",
        "",
        "# Prompt template",
        f"CHATGPT_PROMPT={data.get('CHATGPT_PROMPT','')}",
        "",
        "# Reply options",
        f"REPLY_ALL={data.get('REPLY_ALL','false')}",
        "",
        "# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        f"LOG_LEVEL={data.get('LOG_LEVEL','INFO')}",
        "",
        "# Deeper debug options for SMTP and IMAP",
        f"SMTP_DEBUGLEVEL={data.get('SMTP_DEBUGLEVEL','0')}",
        f"IMAP_DEBUGLEVEL={data.get('IMAP_DEBUGLEVEL','0')}",
        "",
        "# Length in time (seconds) for polling.",
        "# Google recommends 15min (900sec).",
        f"POLL_INTERVAL={data.get('POLL_INTERVAL','900')}",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

def tail_file(path, lines=150):
    """Return the last N lines of a file as a list (newest first)."""
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        content = f.readlines()
    return list(reversed(content[-lines:]))  # newest first

def backup_config():
    """Keep last 20 backups of CONFIG_FILE."""
    if os.path.exists(CONFIG_FILE):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"config-{timestamp}.env"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        shutil.copy2(CONFIG_FILE, backup_path)

        # prune old backups
        backups = sorted(glob(os.path.join(BACKUP_DIR, "config-*.env")))
        if len(backups) > 20:
            for old in backups[:-20]:
                os.remove(old)

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

def get_api_key():
    config = parse_env_file(CONFIG_FILE)
    return config.get("OPENAI_API_KEY", "")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "apply" in request.form:
            backup_config()
            # Save whitelist
            write_file(WHITELIST_FILE, request.form["whitelist"])

            # Collect structured config values
            data = {
                "GMAIL_USER": request.form.get("GMAIL_USER", ""),
                "GMAIL_PASS": request.form.get("GMAIL_PASS", ""),
                "OPENAI_API_KEY": request.form.get("OPENAI_API_KEY", ""),
                "OPENAI_MODEL": request.form.get("OPENAI_MODEL", ""),
                "CHATGPT_PROMPT": request.form.get("CHATGPT_PROMPT", ""),
                "LOG_LEVEL": request.form.get("LOG_LEVEL", "INFO"),
                "SMTP_DEBUGLEVEL": request.form.get("SMTP_DEBUGLEVEL", "0"),
                "IMAP_DEBUGLEVEL": request.form.get("IMAP_DEBUGLEVEL", "0"),
                "POLL_INTERVAL": request.form.get("POLL_INTERVAL", "900"),
                "REPLY_ALL": "false"
            }
            write_env_file(CONFIG_FILE, data)

        elif "defaults" in request.form:
            write_file(WHITELIST_FILE, DEFAULTS["whitelist"])
            write_file(CONFIG_FILE, DEFAULTS["config"])

        elif "cancel" in request.form:
            # Just reload without saving
            return redirect(url_for("index"))

        return redirect(url_for("index"))

    # --- GET request: load files ---
    whitelist_content = read_file(WHITELIST_FILE)
    config_data = parse_env_file(CONFIG_FILE)

    return render_template("index.html",
                           whitelist=whitelist_content,
                           gmail_user=config_data.get("GMAIL_USER", ""),
                           gmail_pass=config_data.get("GMAIL_PASS", ""),
                           openai_key=config_data.get("OPENAI_API_KEY", ""),
                           openai_model=config_data.get("OPENAI_MODEL", ""),
                           chatgpt_prompt=config_data.get("CHATGPT_PROMPT", ""),
                           poll_interval=config_data.get("POLL_INTERVAL", "900"),
                           log_level=config_data.get("LOG_LEVEL", "INFO"),
                           smtp_debug=int(config_data.get("SMTP_DEBUGLEVEL", "0")),
                           imap_debug=int(config_data.get("IMAP_DEBUGLEVEL", "0")))

@app.route("/logs", methods=["GET"])
def logs():
    log_lines = tail_file(LOG_FILE, 150)
    return render_template("logs.html", logs=log_lines)

@app.route("/backups")
def backups():
    files = sorted(glob(os.path.join(BACKUP_DIR, "config-*.env")), reverse=True)
    file_info = [
        {
            "name": os.path.basename(f),
            "mtime": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for f in files
    ]
    return render_template("backups.html", backups=file_info)

@app.route("/backups/view/<filename>")
def view_backup(filename):
    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        return "Backup not found", 404
    with open(path) as f:
        content = f.read()
    return render_template("view_backup.html", filename=filename, content=content)

@app.route("/troubleshooting", methods=["GET", "POST"])
def troubleshooting():
    output = None
    models = []
    error = None
    output = ""

    if request.method == "POST":
        if "restart_gpt" in request.form:
            output = run_command("systemctl restart gpt-relay.service")
        elif "stop_gpt" in request.form:
            output = run_command("systemctl stop gpt-relay.service")
        elif "start_gpt" in request.form:
            output = run_command("systemctl start gpt-relay.service")
        elif "status_gpt" in request.form:
            output = run_command("systemctl status gpt-relay.service")
        elif "restart_webui" in request.form:
            output = run_command("systemctl restart webui-gpt-relay.service")
        elif "reboot" in request.form:
            output = run_command("reboot")
        elif "disk" in request.form:
            output = run_command("df -h")
        elif "memory" in request.form:
            output = run_command("free -h")
        elif "ping_gmail" in request.form:
            output = run_command("ping -c 4 smtp.gmail.com")
        elif "ping_openai" in request.form:
            output = run_command("ping -c 4 api.openai.com")

        # 🔑 Test OpenAI API Key
        elif "test_openai_auth" in request.form:
            api_key = get_api_key()
            if not api_key:
                error = "No API key found in config.env."
            else:
                try:
                    openai.api_key = api_key
                    # A cheap, safe request — list one model
                    response = openai.models.list()
                    first_model = next(iter(response)).id
                    output = f"✅ OpenAI API key is valid. Example model available: {first_model}"
                except Exception as e:
                    error = f"❌ OpenAI auth failed: {e}"

        # 📧 Test Gmail/Google App Auth
        elif "test_gmail_auth" in request.form:
            creds = parse_env_file(CONFIG_FILE)
            user = creds.get("GMAIL_USER", "")
            pw = creds.get("GMAIL_PASS", "")
            if not user or not pw:
                error = "GMAIL_USER or GMAIL_PASS missing in config.env."
            else:
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
                    server.starttls()
                    server.login(user, pw)
                    server.quit()
                    output = f"✅ Gmail authentication successful for {user}"
                except Exception as e:
                    error = f"❌ Gmail auth failed: {e}"

        elif "fetch_models" in request.form:
            api_key = get_api_key()
            if not api_key:
                error = "No API key found in config.env. Please configure one first."
            else:
                try:
                    openai.api_key = api_key
                    response = openai.models.list()
                    models = sorted([m.id for m in response])
                except Exception as e:
                    error = f"Error fetching models: {e}"

    return render_template("troubleshooting.html", output=output, models=models, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
