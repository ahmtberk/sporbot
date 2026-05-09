# Telegram-Controlled Spor Istanbul Bot

## Architecture

The remote version is split into small service layers:

- `app.py`: process entrypoint for cloud/Docker.
- `telegram_service.py`: Telegram command handlers and background task lifecycle.
- `checker.py`: async Playwright flow that logs in, opens the session page, applies filters when present, and returns available slots.
- `runtime_config.py`: JSON-backed runtime settings changed from Telegram.
- `runtime_config.json`: generated at runtime and ignored by git.

The old `bot.py` is left in place for local/manual use. The deployable service starts with:

```bash
python app.py
```

## Telegram Commands

```text
/startbot
/stopbot
/runfor 120
/status
/setfacility HALIC SU SPORLARI MERKEZI
/setbranch FITNESS
/setinterval 15 20
/stopafterfound on
/stopafterfound off
```

Only `TELEGRAM_CHAT_ID` is authorized when that environment variable is set.

## Local Run

```bash
pip install -r requirements.txt
playwright install chromium
python app.py
```

Send `/startbot` to your Telegram bot after the service starts.

For a fixed short run:

```text
/runfor 180
```

This starts checking and automatically stops after 180 minutes.

## Docker Run

```bash
docker build -t sporbot .
docker run -d --name sporbot --restart unless-stopped --env-file .env sporbot
```

For Docker Compose:

```bash
docker compose up -d --build
docker compose logs -f
```

## Required Environment Variables

Use `.env.example` as the template:

```text
SPOR_TC=
SPOR_SIFRE=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DEFAULT_FACILITY_NAME=HALIC SU SPORLARI MERKEZI
DEFAULT_BRANCH_NAME=FITNESS
CHECK_INTERVAL_MIN_SECONDS=900
CHECK_INTERVAL_MAX_SECONDS=1200
STOP_AFTER_FOUND=false
PLAYWRIGHT_HEADLESS=true
```

## Recommended Free Deployment

If you want true 24/7 operation, a real always-running VM is better than a free web app platform. Playwright launches Chromium, needs memory, and the Telegram bot uses long polling. Many free web-service platforms sleep when there is no inbound HTTP traffic, which breaks continuous checking.

For short 2-3 hour runs, use the manual GitHub Actions workflow in `.github/workflows/run-bot.yml`. It starts a fresh cloud runner, runs the Telegram-controlled bot for the requested duration, then exits.

GitHub Actions setup:

1. Push the project to a private GitHub repository.
2. Add repository secrets: `SPOR_TC`, `SPOR_SIFRE`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. Open GitHub on your phone.
4. Go to Actions -> Run Sporbot On Demand -> Run workflow.
5. Choose `duration_minutes`, for example `180`.
6. The bot auto-starts and sends Telegram updates.

Best zero-monthly-cost path:

1. For on-demand only: use GitHub Actions manual workflow.
2. For always-on capability: create an Oracle Cloud Always Free VM.
3. Install Docker and Docker Compose on the VM.
4. Copy this project to the VM.
5. Create `.env` on the VM.
6. Run `docker compose up -d --build`.

Render free web services are okay for demos, but not ideal for this bot because free services spin down after idle inbound traffic. Railway is easier than a VPS, but its free plan is credit-based and not a strong always-on guarantee for a Chromium worker.

## VPS Setup Example

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker

git clone <your-repo-url> sporbot
cd sporbot
nano .env
docker compose up -d --build
docker compose logs -f
```

## Notes

- `/stopbot` cancels the running async Playwright check and closes the browser in `finally`.
- Duplicate starts are blocked by the Telegram service task guard.
- Runtime settings are persisted in `runtime_config.json`.
- Keep `.env` private. It contains your Spor Istanbul credentials and Telegram token.
