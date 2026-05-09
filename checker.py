import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from playwright.async_api import Page, async_playwright

load_dotenv()

from runtime_config import RuntimeConfig

log = logging.getLogger("sporbot.checker")

URL_GIRIS = "https://online.spor.istanbul/uyegiris"
URL_SEANSLARIM = "https://online.spor.istanbul/uyespor"

DEFAULT_BRANCH_VALUE = os.getenv("DEFAULT_BRANCH_VALUE", "78d4463f-a8fc-497b-8e58-b4735e5846ee")
DEFAULT_FACILITY_VALUE = os.getenv("DEFAULT_FACILITY_VALUE", "7bf8dc6b-6363-489c-9664-01b98555a859")


@dataclass
class CheckResult:
    ok: bool
    sessions: list[dict[str, Any]]
    error: str | None = None
    debug_image_path: str | None = None
    debug_html_path: str | None = None


def seans_gecmis_mi(tarih_str: str, saat_str: str | None = None) -> bool:
    if not tarih_str:
        return False
    try:
        simdi = datetime.now()
        gun = datetime.strptime(tarih_str, "%d.%m.%Y")
        if gun.date() < simdi.date():
            return True
        if gun.date() == simdi.date() and saat_str:
            saat_temiz = saat_str.replace(" ", "")
            bitis_str = re.split(r"[-–]", saat_temiz)[-1].strip()
            bitis = datetime.strptime(bitis_str, "%H:%M")
            bitis_tam = simdi.replace(hour=bitis.hour, minute=bitis.minute, second=0, microsecond=0)
            return simdi >= bitis_tam
    except Exception:
        return False
    return False


def gun_adi(tarih_str: str) -> str:
    try:
        dt = datetime.strptime(tarih_str, "%d.%m.%Y")
        return ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"][dt.weekday()]
    except Exception:
        return ""


class SporIstanbulChecker:
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.tc = os.getenv("SPOR_TC", "")
        self.password = os.getenv("SPOR_SIFRE", "")
        self.headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() not in {"0", "false", "no"}
        self.page_timeout_ms = int(os.getenv("PAGE_TIMEOUT_MS", "45000"))
        self.navigation_timeout_ms = int(os.getenv("NAVIGATION_TIMEOUT_MS", "120000"))

    async def run_once(self) -> CheckResult:
        if not self.tc or not self.password:
            return CheckResult(False, [], "SPOR_TC or SPOR_SIFRE is missing.")

        playwright = await async_playwright().start()
        browser = None
        page = None
        stage = "startup"
        try:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()
            page.set_default_timeout(self.page_timeout_ms)
            page.set_default_navigation_timeout(self.navigation_timeout_ms)

            stage = "login"
            await self._login(page)
            stage = "open_sessions_page"
            await self._open_sessions_page(page)
            stage = "click_session_button"
            await self._click_session_button(page)
            stage = "apply_filters"
            await self._apply_filters_if_available(page)
            stage = "collect_sessions"
            sessions = await self._collect_available_sessions(page)
            return CheckResult(True, sessions)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("Check failed")
            debug_image_path = None
            debug_html_path = None
            if page:
                debug_image_path, debug_html_path = await self._save_error_artifacts(page, stage)
            return CheckResult(False, [], f"{stage}: {exc}", debug_image_path, debug_html_path)
        finally:
            if browser:
                await browser.close()
            await playwright.stop()

    async def _save_error_artifacts(self, page: Page, stage: str) -> tuple[str | None, str | None]:
        image_path = "error_page.png"
        html_path = "error_page.html"
        try:
            await page.screenshot(path=image_path, full_page=True)
            html = await page.content()
            with open(html_path, "w", encoding="utf-8") as file:
                file.write(html)
            log.info("Saved error artifacts for stage: %s", stage)
            return image_path, html_path
        except Exception:
            log.warning("Could not save error artifacts", exc_info=True)
            return None, None

    async def _login(self, page: Page) -> None:
        log.info("Logging in to Spor Istanbul")
        await page.goto(URL_GIRIS, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
        await self._wait_for_login_form(page)
        await page.fill("#txtTCPasaport", self.tc)
        await page.fill("#txtSifre", self.password)
        await page.click("#btnGirisYap")
        try:
            await page.wait_for_url(
                lambda url: "anasayfa" in str(url) or "uyespor" in str(url),
                timeout=self.page_timeout_ms,
            )
        except Exception:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

        if "anasayfa" not in page.url and "uyespor" not in page.url:
            raise RuntimeError(f"Login failed. Current URL: {page.url}")

    async def _wait_for_login_form(self, page: Page) -> None:
        for _ in range(20):
            if await page.locator("#txtTCPasaport").count() > 0:
                await page.wait_for_selector("#txtTCPasaport", state="visible", timeout=10000)
                return
            await asyncio.sleep(1)

        title = ""
        body_text = ""
        try:
            title = await page.title()
            body_text = await page.locator("body").inner_text(timeout=3000)
            body_text = " ".join(body_text.split())[:500]
        except Exception:
            pass
        raise RuntimeError(
            "Login form did not appear. "
            f"url={page.url!r} title={title!r} body={body_text!r}"
        )

    async def _open_sessions_page(self, page: Page) -> None:
        log.info("Opening membership sessions page")
        await page.goto(URL_SEANSLARIM, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)
        await page.wait_for_selector("#dtUyeSpor", state="attached", timeout=self.page_timeout_ms)

    async def _click_session_button(self, page: Page) -> None:
        buttons = page.locator("a.btn-success")
        matches = []
        for idx in range(await buttons.count()):
            button = buttons.nth(idx)
            text = (await button.text_content() or "").strip()
            if "Seans" in text:
                matches.append(button)

        if not matches:
            raise RuntimeError("'Seans Sec' button was not found.")

        button_index = min(self.config.session_button_index, len(matches) - 1)
        log.info("Clicking session button index %s", button_index)
        await matches[button_index].click()
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(6)

    async def _apply_filters_if_available(self, page: Page) -> None:
        branch_filter = page.locator("#ddlBransFiltre")
        if await branch_filter.count() == 0:
            if await page.locator("#dvScheduler, div.well").count() > 0:
                log.info("Filter controls are absent; scheduler is already visible")
                return
            raise RuntimeError("Filters are absent and scheduler did not load.")

        await self._select_option_by_text_or_value(
            page,
            "#ddlBransFiltre",
            self.config.branch_name,
            DEFAULT_BRANCH_VALUE,
        )
        await asyncio.sleep(3)

        if await page.locator("#ddlTesisFiltre").count() > 0:
            await self._select_option_by_text_or_value(
                page,
                "#ddlTesisFiltre",
                self.config.facility_name,
                DEFAULT_FACILITY_VALUE,
            )
            await asyncio.sleep(5)

    async def _select_option_by_text_or_value(
        self,
        page: Page,
        selector: str,
        desired_text: str,
        fallback_value: str,
    ) -> None:
        selected_value = await page.evaluate(
            """({ selector, desiredText, fallbackValue }) => {
                const select = document.querySelector(selector);
                if (!select) return null;
                const normalized = (desiredText || '').toLocaleLowerCase('tr-TR').trim();
                const options = Array.from(select.options || []);
                let match = options.find(opt =>
                    (opt.textContent || '').toLocaleLowerCase('tr-TR').includes(normalized)
                );
                if (!match && fallbackValue) {
                    match = options.find(opt => opt.value === fallbackValue);
                }
                return match ? match.value : null;
            }""",
            {
                "selector": selector,
                "desiredText": desired_text,
                "fallbackValue": fallback_value,
            },
        )
        if not selected_value:
            raise RuntimeError(f"No matching option for {desired_text!r} in {selector}")

        log.info("Selecting %s for %s", selected_value, selector)
        await page.locator(selector).select_option(value=selected_value)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

    async def _collect_available_sessions(self, page: Page) -> list[dict[str, Any]]:
        await asyncio.sleep(2)
        try:
            await page.screenshot(path="son_kontrol.png", full_page=True)
        except Exception:
            log.warning("Could not save screenshot", exc_info=True)

        cards = await page.evaluate(
            """() => {
                const results = [];
                const dateRe = /\\b(\\d{2}\\.\\d{2}\\.\\d{4})\\b/;
                const columns = document.querySelectorAll('#dvScheduler > div.col-md-1, #dvScheduler div[class*="col-"]');

                for (const column of columns) {
                    const title = column.querySelector('.panel-heading .panel-title');
                    if (!title) continue;

                    const titleText = (title.innerText || title.textContent || '').trim();
                    const dateMatch = titleText.match(dateRe);
                    if (!dateMatch) continue;

                    const date = dateMatch[1];
                    const dayName = titleText.split('\\n')[0].trim();
                    const wells = column.querySelectorAll('div.well');

                    for (const well of wells) {
                        const timeEl = well.querySelector('span[id*="lblSeansSaat"]');
                        const time = timeEl ? (timeEl.innerText || timeEl.textContent || '').trim() : '';
                        if (!time) continue;

                        const quotaEl = well.querySelector('span[title="Kalan Kontenjan"]');
                        const quotaText = quotaEl ? (quotaEl.innerText || quotaEl.textContent || '').trim() : '0';
                        const quota = parseInt(quotaText, 10) || 0;

                        const genderEl = well.querySelector('label[title="Seans Cinsiyeti"]');
                        const gender = genderEl ? (genderEl.innerText || genderEl.textContent || '').trim() : '';

                        const hallEl = well.querySelector('label[title="Salon Adı"], label[title="Salon Adi"]');
                        const hall = hallEl ? (hallEl.innerText || hallEl.textContent || '').trim() : '';

                        results.push({ date, dayName, time, quota, gender, hall });
                    }
                }
                return results;
            }"""
        )

        available = []
        for card in cards:
            time_text = (card.get("time") or "").replace("–", "-")
            if int(card.get("quota") or 0) <= 0:
                continue
            if seans_gecmis_mi(card.get("date", ""), time_text):
                continue

            day_name = card.get("dayName") or gun_adi(card.get("date", ""))
            available.append(
                {
                    "tarih": card.get("date", ""),
                    "gun": day_name,
                    "saat": card.get("time", ""),
                    "sayi": int(card.get("quota") or 0),
                    "cinsiyet": card.get("gender", ""),
                    "salon": card.get("hall", ""),
                    "ozet": f"{card.get('hall', '')} {card.get('time', '')} {card.get('gender', '')}".strip(),
                }
            )

        log.info("Found %s available sessions out of %s cards", len(available), len(cards))
        return available


def random_interval(config: RuntimeConfig) -> int:
    return random.randint(config.interval_min_seconds, config.interval_max_seconds)
