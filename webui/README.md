# WebUI for GPT Relay Configuration

A terrible, insecure, and dark-mode Flask-based web interface for managing the GPT Relay service:

- **config.env** (service configuration)
- **whitelist.txt** (allowed emails)
- **service.log** (view logs)
- **Backups** of configuration
- **Troubleshooting commands** (systemctl, connectivity tests, auth tests)

Designed for non-technical users to hopefully manage the GPT Relay service.

---

## Features

### Config Tab
- Edit: Prompt, Whitelist, Gmail, OpenAI API key/model, Polling, Logging.
- Buttons: Apply, Cancel, Reset to Defaults.

### Logs Tab
- View the last 150 lines of `service.log`.
- Refresh button.

### Backups Tab
- Stores the last 20 versions of `config.env` when Apply is pressed.
- Load a backup into the editor without applying it.

### Troubleshooting Tab
- Manage `gpt-relay.service` (start/stop/restart/status).
- Restart `webui-gpt-relay.service`.
- System diagnostics: disk space, memory, reboot.
- Connectivity tests: ping Gmail/OpenAI.
- Auth tests:
  - Validate OpenAI API key from `config.env`.
  - Validate Gmail credentials from `config.env`.
  - Fetch available OpenAI models (requires valid API key).

---

## Requirements

- Python 3.10+
- Flask
- PyYAML
- OpenAI Python client

### Install dependencies
```bash
pip3 install flask pyyaml openai
```

---

## Running

From the project root:
```bash
python3 webui.py
```

The app will listen on **port 8080** by default.

---

## Systemd Service

Create a systemd service file at `sudo nano /etc/systemd/system/webui-gpt-relay.service`:

```ini
[Unit]
Description=WebUI for GPT Relay Config
After=network.target

[Service]
User=***USERNAME_HERE***
Group=***GROUP_HERE***
WorkingDirectory=/opt/gpt-smtp-relay/webui/
ExecStart=/usr/bin/python3 /opt/gpt-smtp-relay/webui/webui.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### Notes
- Replace **webui** with the Linux user that should run the service.
- This user must have permissions to:
  - Read/write `config.env`, `whitelist.txt`, `service.log`.
  - Manage `gpt-relay.service` via `systemctl`.
  - Restart `webui-gpt-relay.service`.
  - Run system commands (`df`, `free`, `reboot`, `ping`).

Grant the user sudo permissions for these specific commands:

```bash
sudo visudo
```

Add a line like:
```bash
webui ALL=(ALL) NOPASSWD: /bin/systemctl restart gpt-relay.service, \
  /bin/systemctl stop gpt-relay.service, \
  /bin/systemctl start gpt-relay.service, \
  /bin/systemctl status gpt-relay.service, \
  /bin/systemctl restart webui-gpt-relay.service, \
  /bin/reboot, /bin/df, /usr/bin/free, /bin/ping
```

This ensures the troubleshooting tab works without requiring manual root access.

---

## Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable webui-gpt-relay
sudo systemctl start webui-gpt-relay
```

Check logs:
```bash
sudo journalctl -u webui-gpt-relay -f
```

---

## Security Notes

- Do not expose this WebUI directly to the internet without authentication.
- Consider running it behind a reverse proxy with HTTPS and authentication.
- The service user should have the minimum required privileges.

---

## File Structure

```
webui/
├── webui.py              # Flask app
├── defaults.yaml         # Default config/whitelist
├── templates/
│   ├── base.html         # Shared layout
│   ├── index.html        # Config editor
│   ├── logs.html         # Logs tab
│   ├── backups.html      # Backups tab
│   └── troubleshooting.html # Troubleshooting tab
└── static/               # Optional static assets
```
