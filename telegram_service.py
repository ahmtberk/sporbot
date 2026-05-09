import asyncio
import html
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from checker import SporIstanbulChecker, random_interval
from runtime_config import ConfigStore, RuntimeConfig


log = logging.getLogger("sporbot.telegram")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
RESERVATION_URL = "https://online.spor.istanbul/uyespor"


class TelegramControlledSlotService:
    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.last_check_at: datetime | None = None
        self.last_result_text = "No checks yet."
        self._task_lock = asyncio.Lock()
        self.auto_stop_at: datetime | None = None

    def build_application(self) -> Application:
        if not TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

        app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(self._post_init).build()
        app.add_handler(CommandHandler("start", self.help_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("startbot", self.startbot))
        app.add_handler(CommandHandler("stopbot", self.stopbot))
        app.add_handler(CommandHandler("runfor", self.runfor))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("setfacility", self.setfacility))
        app.add_handler(CommandHandler("setbranch", self.setbranch))
        app.add_handler(CommandHandler("setinterval", self.setinterval))
        app.add_handler(CommandHandler("stopafterfound", self.stopafterfound))
        return app

    async def _post_init(self, app: Application) -> None:
        auto_start = os.getenv("AUTO_START", "false").lower() in {"1", "true", "yes", "on"}
        if not auto_start:
            return
        if not AUTHORIZED_CHAT_ID:
            log.warning("AUTO_START ignored because TELEGRAM_CHAT_ID is missing")
            return

        seconds = self._env_auto_stop_seconds()
        await self._start_background_loop(app.bot, int(AUTHORIZED_CHAT_ID), seconds)
        await app.bot.send_message(
            chat_id=int(AUTHORIZED_CHAT_ID),
            text=self._started_text(seconds, auto=True),
        )

    async def _authorized(self, update: Update) -> bool:
        chat_id = str(update.effective_chat.id) if update.effective_chat else ""
        if AUTHORIZED_CHAT_ID and chat_id != AUTHORIZED_CHAT_ID:
            log.warning("Unauthorized chat id: %s", chat_id)
            if update.message:
                await update.message.reply_text("Unauthorized.")
            return False
        return True

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        await update.message.reply_text(
            "Commands:\n"
            "/startbot - start checking\n"
            "/stopbot - stop checking\n"
            "/runfor <minutes> - start checking and auto-stop later\n"
            "/status - show current state\n"
            "/setfacility <name> - change facility\n"
            "/setbranch <name> - change branch\n"
            "/setinterval <min_minutes> [max_minutes] - change interval\n"
            "/stopafterfound on|off - stop or continue after a slot is found"
        )

    async def startbot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return

        async with self._task_lock:
            if self.task and not self.task.done():
                await update.message.reply_text("Bot is already running.")
                return

            chat_id = update.effective_chat.id
            await self._start_background_loop(context.bot, chat_id)
            await update.message.reply_text("Slot checking started.")

    async def runfor(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /runfor 120")
            return
        try:
            minutes = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Duration must be a number of minutes.")
            return
        if minutes < 1:
            await update.message.reply_text("Duration must be at least 1 minute.")
            return

        async with self._task_lock:
            if self.task and not self.task.done():
                await update.message.reply_text("Bot is already running.")
                return
            seconds = minutes * 60
            await self._start_background_loop(context.bot, update.effective_chat.id, seconds)
            await update.message.reply_text(self._started_text(seconds))

    async def stopbot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return

        self.stop_event.set()
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await update.message.reply_text("Slot checking stopped.")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return

        config = self.config_store.load()
        running = bool(self.task and not self.task.done())
        last_check = self.last_check_at.strftime("%d.%m.%Y %H:%M:%S") if self.last_check_at else "-"
        auto_stop = self.auto_stop_at.strftime("%d.%m.%Y %H:%M:%S") if running and self.auto_stop_at else "-"
        await update.message.reply_text(
            f"Running: {'yes' if running else 'no'}\n"
            f"Facility: {config.facility_name}\n"
            f"Branch: {config.branch_name}\n"
            f"Interval: {config.interval_min_seconds//60}-{config.interval_max_seconds//60} min\n"
            f"Stop after found: {'yes' if config.stop_after_found else 'no'}\n"
            f"Auto stop at: {auto_stop}\n"
            f"Last check: {last_check}\n"
            f"Last result: {self.last_result_text}"
        )

    async def setfacility(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        value = " ".join(context.args).strip()
        if not value:
            await update.message.reply_text("Usage: /setfacility HALIC SU SPORLARI MERKEZI")
            return
        config = self.config_store.update(facility_name=value)
        await update.message.reply_text(f"Facility updated: {config.facility_name}")

    async def setbranch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        value = " ".join(context.args).strip()
        if not value:
            await update.message.reply_text("Usage: /setbranch FITNESS")
            return
        config = self.config_store.update(branch_name=value)
        await update.message.reply_text(f"Branch updated: {config.branch_name}")

    async def setinterval(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if not context.args:
            await update.message.reply_text("Usage: /setinterval 15 or /setinterval 15 20")
            return
        try:
            min_minutes = int(context.args[0])
            max_minutes = int(context.args[1]) if len(context.args) > 1 else min_minutes
        except ValueError:
            await update.message.reply_text("Interval must be a number of minutes.")
            return

        config = self.config_store.update(
            interval_min_seconds=min_minutes * 60,
            interval_max_seconds=max_minutes * 60,
        )
        await update.message.reply_text(
            f"Interval updated: {config.interval_min_seconds//60}-{config.interval_max_seconds//60} min"
        )

    async def stopafterfound(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if not context.args or context.args[0].lower() not in {"on", "off"}:
            await update.message.reply_text("Usage: /stopafterfound on or /stopafterfound off")
            return
        config = self.config_store.update(stop_after_found=context.args[0].lower() == "on")
        await update.message.reply_text(f"Stop after found: {'on' if config.stop_after_found else 'off'}")

    async def _start_background_loop(self, bot, chat_id: int, auto_stop_seconds: int | None = None) -> None:
        self.stop_event = asyncio.Event()
        self.auto_stop_at = None
        if auto_stop_seconds:
            self.auto_stop_at = datetime.now() + timedelta(seconds=auto_stop_seconds)
        self.task = asyncio.create_task(self._run_loop(bot, chat_id))

    def _env_auto_stop_seconds(self) -> int | None:
        raw = os.getenv("AUTO_STOP_AFTER_SECONDS", "").strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value > 0 else None

    def _started_text(self, seconds: int | None = None, auto: bool = False) -> str:
        prefix = "Auto-started" if auto else "Slot checking started"
        if not seconds:
            return f"{prefix}."
        return f"{prefix} for {seconds // 60} minute(s)."

    async def _run_loop(self, bot, chat_id: int) -> None:
        log.info("Background checking loop started")
        try:
            while not self.stop_event.is_set():
                if self.auto_stop_at and datetime.now() >= self.auto_stop_at:
                    await bot.send_message(chat_id=chat_id, text="Auto stop time reached. Slot checking stopped.")
                    break

                config = self.config_store.load()
                self.last_check_at = datetime.now()
                await bot.send_message(chat_id=chat_id, text="Checking slots now...")

                result = await SporIstanbulChecker(config).run_once()
                if not result.ok:
                    self.last_result_text = f"Error: {result.error}"
                    log.error("Check error: %s", result.error)
                    await bot.send_message(chat_id=chat_id, text=f"Check failed:\n{result.error}")
                    await self._send_debug_image(bot, chat_id, result.debug_image_path)
                elif result.sessions:
                    self.last_result_text = f"Found {len(result.sessions)} available session(s)."
                    await bot.send_message(
                        chat_id=chat_id,
                        text=self._format_found_message(config, result.sessions),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                    if config.stop_after_found:
                        break
                else:
                    self.last_result_text = "No available sessions."
                    log.info("No available sessions")

                delay = random_interval(config)
                if self.auto_stop_at:
                    remaining = max(0, int((self.auto_stop_at - datetime.now()).total_seconds()))
                    delay = min(delay, remaining)
                    if delay == 0:
                        continue
                log.info("Next check in %s seconds", delay)
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            log.info("Background checking loop cancelled")
            raise
        finally:
            self.auto_stop_at = None
            log.info("Background checking loop stopped")

    async def _send_debug_image(self, bot, chat_id: int, image_path: str | None) -> None:
        if not image_path:
            return
        path = Path(image_path)
        if not path.exists():
            return
        try:
            with path.open("rb") as image:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image,
                    caption="Debug screenshot from failed check",
                )
        except Exception:
            log.warning("Could not send debug screenshot", exc_info=True)

    def _format_found_message(self, config: RuntimeConfig, sessions: list[dict]) -> str:
        title = f"{html.escape(config.facility_name)} - {html.escape(config.branch_name)}"
        lines = [
            f"<b>{title}</b>",
            f"Check: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            f"<b>{len(sessions)} available session(s)</b>",
            "",
        ]
        for index, session in enumerate(sessions[:10], 1):
            lines.extend(
                [
                    f"<b>#{index} {html.escape(session.get('gun', ''))} {html.escape(session.get('tarih', ''))}</b>",
                    f"Time: <code>{html.escape(session.get('saat', ''))}</code>",
                    f"Quota: <b>{html.escape(str(session.get('sayi', '?')))}</b>",
                    f"{html.escape(session.get('ozet', ''))}",
                    "",
                ]
            )
        lines.append(f"<a href='{RESERVATION_URL}'><b>Open reservation page</b></a>")
        return "\n".join(lines)
