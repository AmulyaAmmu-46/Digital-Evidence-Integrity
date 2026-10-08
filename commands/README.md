# Run the Project

Open PowerShell and run these first-time setup commands:

## Local Development (Windows PowerShell)

```powershell
Set-Location F:\Cyber\project
.\.venv\Scripts\Activate.ps1
python run.py
```

The `seed.py` step is for first-time setup only. It creates missing database tables. Enter the administrator email, name, and password when prompted; password input is hidden.

Open <http://127.0.0.1:5000> and sign in with the admin account you created. The dashboard is shown after login; `/health` returns HTTP 200 for service checks. Keep this terminal open while using the app; press `Ctrl+C` to stop the server. The app uses the local SQLite database by default.

### Optional Telegram security alerts

1. In Telegram, open `@BotFather`, send `/newbot`, and follow its prompts. Copy the bot token into `TELEGRAM_BOT_TOKEN` in `.env`; treat it like a password.
2. Open your new bot and send it `/start` so it can message you.
3. In PowerShell, retrieve your private chat ID (the token prompt avoids placing the token in the command history):

	```powershell
	$token = Read-Host 'Bot token'
	Invoke-RestMethod "https://api.telegram.org/bot$token/getUpdates"
	Remove-Variable token
	```

	Find `message.chat.id` in the response and set it as `TELEGRAM_CHAT_ID` in `.env`.
4. Restart the app. The bot sends alerts for login success/failure, logout, evidence access and custody changes, verification, and integrity failures. Notifications contain account, action, result, resource ID, IP address, and time; they do not include evidence contents or custody notes.

Telegram is an external notification channel, not the audit record of authority. Events are committed to the app database first, and notification failures do not interrupt app operations. Keep the bot token private; leave both Telegram settings blank to disable alerts.

### Start it again later

After setup, use these commands each time you want to run the project:

```powershell
Set-Location F:\Cyber\project
.\.venv\Scripts\Activate.ps1
python run.py
```

Run tests from another terminal in the project directory:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Stop the local server with `Ctrl+C`.

## Docker Compose

Run from the project directory. Before starting Compose, copy `.env.example` to `.env` if needed and set non-empty random values for `SECRET_KEY` and `POSTGRES_PASSWORD` in `.env`.

```powershell
Set-Location F:\Cyber\project
docker-compose up --build -d
docker-compose exec web python scripts/seed.py
```

The seed command is only for a new database or an intentional administrator password reset. Enter your administrator credentials when prompted, then open <http://localhost:5000>. For an existing database upgraded from an earlier version, run `docker-compose exec web python scripts/upgrade_case_viewer_grants.py` once instead of reseeding; it adds the Viewer-grant table and custody result column without dropping existing records.

Stop the containers while preserving database and upload volumes:

```powershell
docker-compose down
```
