# Sporbot Local Telegram Usage

Spor Istanbul blocks GitHub Actions/cloud datacenter browsers with Cloudflare human verification. For this site, the reliable free setup is:

1. Run the service on your own laptop.
2. Control it from Telegram.
3. Stop it after the 2-3 hour search window.

## First Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Fill `.env` with:

```text
SPOR_TC=
SPOR_SIFRE=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## One Click Start

If you are already on the laptop and do not want to type Telegram `/runfor`, double-click one of these files:

- `start_sporbot_2h.bat`: starts checking immediately for 2 hours.
- `start_sporbot_3h.bat`: starts checking immediately for 3 hours.
- `start_sporbot_manual.bat`: only starts the Telegram service; you control it with `/runfor`.
- `start_sporbot_visible_2h.bat`: 2-hour run with the browser visible, useful for debugging.

Keep the terminal window open. Closing it stops the bot.

You can still use Telegram while it is running:

```text
/status
/stopbot
```

## Manual Terminal Start

From this folder:

```bash
python app.py
```

Then start from Telegram with `/runfor 180`.

## Phone Commands

Start for 3 hours:

```text
/runfor 180
```

Check status:

```text
/status
```

Stop immediately:

```text
/stopbot
```

Change interval:

```text
/setinterval 10 15
```

Change facility or branch:

```text
/setfacility HALIC SU SPORLARI MERKEZI
/setbranch FITNESS
```

## Daily Flow

1. Open the laptop.
2. Double-click `start_sporbot_2h.bat` or `start_sporbot_3h.bat`.
3. Check `/status` from your phone if needed.
4. Stop early with `/stopbot` if you are done.

## Optional Remote Control

If you want to start it while away from the laptop, use a remote desktop tool:

- Chrome Remote Desktop
- AnyDesk
- RustDesk

Open the laptop remotely and run `python app.py`. After that, Telegram controls the bot.
