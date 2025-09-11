# GPT Relay Service

This project is a lightweight Gmail-to-OpenAI relay bot that checks a Gmail inbox, processes incoming emails, and sends AI-generated replies. It runs as a background Linux service with automatic config reloading and CSV logging for easy monitoring.

---

## ✨ Features

* Monitors a Gmail inbox for unseen emails
* Processes messages only from a configurable whitelist
* Uses OpenAI's API to generate responses
* Sends replies automatically via Gmail SMTP
* Configurable through a `config.env` file
* Supports **hot-reloading** of configuration without restart
* Rotating CSV log files (`service.log`) for easier parsing
* Runs as a **systemd service** for reliability

---

## ⚙️ Setup Instructions

### 1. Enable Gmail 2-Factor Authentication

Enable 2FA on your Gmail account:
👉 [Google 2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification)

### 2. Create a Gmail App Password

Generate an **App Password** for this service:
👉 [Google App Passwords](https://myaccount.google.com/apppasswords)

Save the generated password — this will be used in `config.env`.

### 3. Install Python Prerequisites<br>
This assume Ubuntu or debian

Ensure required packages are installed:

```bash
sudo apt update
sudo apt install python3-dotenv python3-imaplib2
```

### 4. Create a Systemd Service

Create the service definition:

```bash
sudo nano /etc/systemd/system/gpt-relay.service
```

Paste the following, replacing placeholders with your username, group, and file paths:

```ini
[Unit]
Description=GPT Relay Service
After=network.target

[Service]
User=***USERNAME_HERE***
Group=***GROUP_HERE***
WorkingDirectory=/***FILE LOCATION HERE***/gpt-smtp-relay/gpt-relay
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u /***FILE LOCATION HERE***/gpt-smtp-relay/gpt-relay.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=gpt-relay

[Install]
WantedBy=multi-user.target
```

### 5. Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable gpt-relay.service
sudo systemctl start gpt-relay.service
sudo systemctl status gpt-relay.service
```

### 6. Troubleshooting

Check logs in real time:

```bash
sudo journalctl -u gpt-relay.service -f
```

Application logs are also written to:

```
service.log
```

(in CSV format for easy parsing)

---

## 📄 Configuration

Create a `config.env` file in the working directory:

```ini
GMAIL_USER=youremail@gmail.com
GMAIL_PASS=your_app_password
OPENAI_API_KEY=sk-xxx...
OPENAI_MODEL=gpt-4o-mini
CHATGPT_PROMPT=You are a helpful email assistant.
REPLY_ALL=false
LOG_LEVEL=INFO
POLL_INTERVAL=900
```

* **LOG\_LEVEL** can be `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`
* **POLL\_INTERVAL** is in seconds (default 900s = 15 minutes)
* **config.env is hot-reloaded** — changes apply without restarting the service

Whitelist senders in `whitelist.txt` (one email per line):

```
trusted.sender@example.com
another.trusted@example.com
```

Unauthorized sender get response:<br>
(this can be edited in the gpt-relay.py)
```
Sender {from_addr} not authorized.
```

---

## 🔍 Logs

* **CSV structured logs** stored in `service.log`:

  ```csv
  2025-09-10 22:58:28,INFO,"Configuration loaded. Log level set to INFO"
  2025-09-10 22:58:28,INFO,"Reloaded config.env due to file change."
  2025-09-10 22:58:28,INFO,"Processing email from user@example.com | Subject: Hello"
  ```

* Journald logs (viewed via `journalctl`) will also show service activity.

---

## 🚀 Summary

GPT Relay Service allows you to:

* Securely connect to Gmail using an App Password
* Automatically process and reply to emails with OpenAI
* Configure and monitor behavior without restarts
* Run as a persistent Linux service with structured logging

This makes it an ideal solution for automated Gmail-driven workflows or personal AI-powered email assistants.
