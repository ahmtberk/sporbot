# Sporbot

Telegram-controlled Spor Istanbul fitness slot checker.

Spor Istanbul shows Cloudflare human verification to GitHub Actions/cloud datacenter browsers, so the free reliable setup is local/on-demand:

Double-click one of the Windows launchers:

```text
start_sporbot_2h.bat
start_sporbot_3h.bat
start_sporbot_manual.bat
```

Then control it from Telegram:

```text
/status
/stopbot
```

See [USAGE.md](USAGE.md) for setup and daily use.

## Files

- `app.py`: Telegram service entrypoint.
- `telegram_service.py`: Telegram commands and background task control.
- `checker.py`: Playwright Spor Istanbul checker.
- `runtime_config.py`: runtime config stored in JSON.
- `bot.py`: old local loop script kept for reference.

Keep `.env` private. It contains your Spor Istanbul credentials and Telegram token.
