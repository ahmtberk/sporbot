"""
Spor Istanbul - Haliç Su Sporları Merkezi Fitness Slot Takip Botu
=================================================================
"""

import os
import sys
import time
import random
import logging
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# ============================================================
# AYARLAR
# ============================================================
load_dotenv()

TC_KIMLIK = os.getenv("SPOR_TC")
SIFRE = os.getenv("SPOR_SIFRE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL_MIN = 15 * 60
CHECK_INTERVAL_MAX = 20 * 60

URL_GIRIS = "https://online.spor.istanbul/uyegiris"
URL_SEANSLARIM = "https://online.spor.istanbul/uyespor"

SEANS_SECIM_BUTON_INDEX = 0
FITNESS_BRANS_VALUE = "78d4463f-a8fc-497b-8e58-b4735e5846ee"
HALIC_TESIS_VALUE = "7bf8dc6b-6363-489c-9664-01b98555a859"

# ============================================================
# LOGGING
# ============================================================
import io
_stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(_stdout_utf8),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
log = logging.getLogger("SporBot")

# ============================================================
# TARİH / SAAT YARDIMCI FONKSİYONLARI
# ============================================================

def seans_gecmis_mi(tarih_str, saat_str=None):
    """
    Seans tamamen geçmişte mi? Hem tarihi hem saati kontrol eder.
    tarih_str: "DD.MM.YYYY"
    saat_str : "HH:MM" ya da "HH:MM - HH:MM" formatında BİTİŞ saati kullanılır.
    """
    if not tarih_str:
        return False
    try:
        simdi = datetime.now()

        # Tarihi parse et
        gun = datetime.strptime(tarih_str, "%d.%m.%Y")

        # Eğer gün geçmişte ise kesinlikle geçmiş
        if gun.date() < simdi.date():
            return True

        # Bugünse → saate bak
        if gun.date() == simdi.date() and saat_str:
            # "HH:MM - HH:MM" veya "HH:MM-HH:MM" → bitiş saatini al
            saat_temiz = saat_str.replace(" ", "")
            parcalar = re.split(r"[-–]", saat_temiz)
            bitis_str = parcalar[-1].strip()  # son parça bitiş saati
            try:
                bitis = datetime.strptime(bitis_str, "%H:%M")
                bitis_tam = simdi.replace(
                    hour=bitis.hour, minute=bitis.minute,
                    second=0, microsecond=0
                )
                if simdi >= bitis_tam:
                    return True
            except:
                pass

        return False
    except:
        return False


def tarih_saat_ayikla(metin):
    """Metinden tarih (DD.MM.YYYY) ve saat aralığı (HH:MM-HH:MM) ayıklar."""
    tarih_re = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
    saat_re  = re.compile(r"(\d{2}:\d{2})\s*[-–]\s*(\d{2}:\d{2})")

    tarih_m = tarih_re.search(metin)
    saat_m  = saat_re.search(metin)

    tarih = tarih_m.group(1) if tarih_m else None
    saat  = f"{saat_m.group(1)}-{saat_m.group(2)}" if saat_m else None

    return tarih, saat


def gun_adi(tarih_str):
    try:
        dt = datetime.strptime(tarih_str, "%d.%m.%Y")
        return ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"][dt.weekday()]
    except:
        return ""

# ============================================================
# TELEGRAM
# ============================================================
def telegram_gonder(mesaj):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram bilgileri eksik.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code == 200:
            log.info("✅ Telegram mesajı gönderildi.")
            return True
        else:
            log.error(f"Telegram hatası: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        log.error(f"Telegram bağlantı hatası: {e}")
        return False

# ============================================================
# ANA BOT SINIFI
# ============================================================
class SporBot:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def baslat(self):
        self.playwright = sync_playwright().start()
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() not in ["0", "false", "no"]
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = context.new_page()
        self.page.set_default_timeout(45000)
        self.page.set_default_navigation_timeout(60000)
        log.info("🌐 Tarayıcı başlatıldı.")

    def kapat(self):
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        log.info("Tarayıcı kapatıldı.")

    def giris_yap(self):
        try:
            log.info("🔑 Giriş yapılıyor...")
            self.page.goto(URL_GIRIS, wait_until="domcontentloaded", timeout=60000)
            self.page.wait_for_selector("#txtTCPasaport", state="visible", timeout=45000)
            self.page.fill("#txtTCPasaport", TC_KIMLIK)
            self.page.fill("#txtSifre", SIFRE)
            self.page.click("#btnGirisYap")
            try:
                self.page.wait_for_url(
                    lambda url: "anasayfa" in str(url) or "uyespor" in str(url),
                    timeout=45000
                )
            except Exception:
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
            time.sleep(2)
            current_url = self.page.url
            if "anasayfa" in current_url or "uyespor" in current_url:
                log.info(f"✅ Giriş başarılı!")
                return True
            else:
                log.error(f"❌ Giriş başarısız! URL: {current_url}")
                return False
        except Exception as e:
            log.error(f"❌ Giriş hatası: {e}")
            return False

    def seanslarim_sayfasina_git(self):
        try:
            log.info("📋 Seanslarım sayfasına gidiliyor...")
            self.page.goto(URL_SEANSLARIM, wait_until="domcontentloaded", timeout=60000)
            self.page.wait_for_selector("#dtUyeSpor", state="attached", timeout=45000)
            time.sleep(2)
            if self.page.locator("#dtUyeSpor").count() > 0:
                log.info("✅ Üyelik tablosu yüklendi.")
                return True
            else:
                log.error("❌ Üyelik tablosu bulunamadı!")
                return False
        except Exception as e:
            log.error(f"❌ Seanslarım sayfası hatası: {e}")
            return False

    def seans_secim_butonuna_tikla(self):
        try:
            # "Seans Seç" yazısı olan btn-success butonlarını bul
            secim_butonlari = [
                btn for btn in self.page.locator("a.btn-success").all()
                if "Seans" in (btn.text_content() or "")
            ]
            if not secim_butonlari:
                log.error("❌ 'Seans Seç' butonu bulunamadı!")
                return False
            idx = min(SEANS_SECIM_BUTON_INDEX, len(secim_butonlari) - 1)
            log.info(f"🖱️ Üyelik #{idx} - 'Seans Seç' butonuna tıklanıyor...")
            secim_butonlari[idx].click()
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(8)
            log.info(f"✅ Seans seçim sayfası açıldı.")
            return True
        except Exception as e:
            log.error(f"❌ Seans seçim butonu hatası: {e}")
            return False

    def filtreleri_uygula(self):
        try:
            brans_filtre = self.page.locator("#ddlBransFiltre")

            # Yeni ekranda "Seans Sec" sonrasinda brans/tesis secimi
            # gelmeden haftalik seans takvimi dogrudan acilabiliyor.
            if brans_filtre.count() == 0:
                if self.page.locator("#dvScheduler, div.well").count() > 0:
                    log.info("Brans/tesis filtresi yok; seans takvimi dogrudan acilmis, filtre adimi atlandi.")
                    time.sleep(2)
                    return True

                log.error("Filtreler bulunamadi ve seans takvimi de yuklenmedi!")
                return False
            log.info("🏋️ FITNESS branşı seçiliyor...")
            self.page.locator("#ddlBransFiltre").select_option(value=FITNESS_BRANS_VALUE)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(4)
            log.info("🏢 Haliç seçiliyor...")
            self.page.locator("#ddlTesisFiltre").select_option(value=HALIC_TESIS_VALUE)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(6)
            log.info("✅ Filtreler uygulandı.")
            return True
        except Exception as e:
            log.error(f"❌ Filtre hatası: {e}")
            return False

    # ----------------------------------------------------------
    def seanslari_kontrol_et(self):
        """
        Sayfadaki müsait seansları tespit eder.

        Strateji (DOM yapısına dayalı):
        - Her gün bir col-md-1 kolonu içinde:
          - panel-heading > h3.panel-title → "Pazartesi\n27.04.2026" (gün adı + tarih)
          - panel-body > form-group > div.well → seans kartı
        - Her well kartında:
          - span[id*="lblSeansSaat"] → saat aralığı (ör. "17:00 - 21:00")
          - span[title="Kalan Kontenjan"] → kalan kontenjan sayısı
          - label.cinsiyetKarma → cinsiyet tipi
        - Kontenjan > 0 olan seanslar müsait kabul edilir
        - Geçmiş seanslar tarih+saat kontrolüyle elenir
        """
        try:
            log.info("🔍 Seanslar kontrol ediliyor (DOM yapı yöntemi)...")
            time.sleep(3)
            self.page.screenshot(path="son_kontrol.png", full_page=True)

            musait = []

            # JavaScript ile DOM yapısına dayalı seans taraması
            sonuclar = self.page.evaluate("""() => {
                const kartlar = [];
                const tarihRe = /\\b(\\d{2}\\.\\d{2}\\.\\d{4})\\b/;

                // Her gün kolonu bir div.col-md-1 içinde
                // Her kolonun içinde bir panel var:
                //   panel-heading → tarih (h3.panel-title)
                //   panel-body → seans kartları (div.well)
                const gunKolonlari = document.querySelectorAll('#dvScheduler > div.col-md-1');

                for (const kolon of gunKolonlari) {
                    // Gün başlığından tarih ve gün adını al
                    const baslik = kolon.querySelector('.panel-heading .panel-title');
                    if (!baslik) continue;

                    const baslikMetin = (baslik.innerText || baslik.textContent || '').trim();
                    const tarihMatch = baslikMetin.match(tarihRe);
                    if (!tarihMatch) continue;

                    const tarih = tarihMatch[1];
                    // Gün adı ilk satırda (ör. "Pazartesi")
                    const gunAdi = baslikMetin.split('\\n')[0].trim();

                    // Bu günün seans kartlarını bul
                    const wells = kolon.querySelectorAll('div.well');
                    for (const well of wells) {
                        // Saat bilgisi
                        const saatEl = well.querySelector('span[id*="lblSeansSaat"]');
                        const saat = saatEl ? (saatEl.innerText || saatEl.textContent || '').trim() : null;
                        if (!saat) continue;

                        // Kontenjan bilgisi
                        const kontenjanEl = well.querySelector('span[title="Kalan Kontenjan"]');
                        const kontenjanStr = kontenjanEl ? (kontenjanEl.innerText || kontenjanEl.textContent || '').trim() : '0';
                        const kontenjan = parseInt(kontenjanStr) || 0;

                        // Cinsiyet tipi
                        const cinsiyetEl = well.querySelector('label[title="Seans Cinsiyeti"]');
                        const cinsiyet = cinsiyetEl ? (cinsiyetEl.innerText || cinsiyetEl.textContent || '').trim() : '';

                        // Salon/branş adı
                        const salonEl = well.querySelector('label[title="Salon Adı"]');
                        const salon = salonEl ? (salonEl.innerText || salonEl.textContent || '').trim() : '';

                        // Border rengine göre durum (opsiyonel bilgi)
                        const borderColor = well.style.borderColor || '';

                        kartlar.push({
                            tarih: tarih,
                            gunAdi: gunAdi,
                            saat: saat,
                            kontenjan: kontenjan,
                            cinsiyet: cinsiyet,
                            salon: salon,
                            borderColor: borderColor
                        });
                    }
                }
                return kartlar;
            }""")

            log.info(f"   DOM taraması: {len(sonuclar)} seans kartı bulundu.")

            for kart in sonuclar:
                try:
                    tarih     = kart.get("tarih", "")
                    gun_ad    = kart.get("gunAdi", "")
                    saat_raw  = kart.get("saat", "")
                    kontenjan = kart.get("kontenjan", 0)
                    cinsiyet  = kart.get("cinsiyet", "")
                    salon     = kart.get("salon", "")

                    # Saat formatını normalize et (ör. "17:00 - 21:00" → "17:00-21:00")
                    saat = saat_raw.replace(" ", "").replace("–", "-") if saat_raw else ""

                    log.info(f"   Kart: {gun_ad} {tarih} | {saat_raw} | {cinsiyet} | Kontenjan={kontenjan} | {salon}")

                    # Kontenjan 0 ise dolu → atla
                    if kontenjan == 0:
                        continue

                    # Geçmiş seans eleme
                    if seans_gecmis_mi(tarih, saat):
                        log.info(f"   ⏩ Geçmiş seans atlandı: {tarih} {saat_raw}")
                        continue

                    # Gün adını doğrula (JS'den gelen veya hesaplanan)
                    gad = gun_ad or gun_adi(tarih)

                    bilgi = f"{gad} {tarih} {saat_raw} | {cinsiyet} | {salon} | Boş: {kontenjan}"
                    musait.append({
                        "tarih": tarih,
                        "saat": saat_raw,
                        "gun": gad,
                        "ozet": f"{salon} {saat_raw} {cinsiyet}",
                        "sayi": kontenjan,
                        "ham": bilgi
                    })
                    log.info(f"   ✅ MÜSAİT ({kontenjan} boşluk): {bilgi}")
                except Exception as ex:
                    log.warning(f"   Kart işleme hatası: {ex}")
                    continue

            log.info(
                f"🎉 {len(musait)} müsait seans bulundu!" if musait
                else "😔 Müsait seans bulunamadı."
            )
            return musait

        except Exception as e:
            log.error(f"❌ Seans kontrol hatası: {e}")
            return []

    # ----------------------------------------------------------
    def tam_kontrol(self):
        try:
            self.baslat()
            if not self.giris_yap():            return False
            if not self.seanslarim_sayfasina_git(): return False
            if not self.seans_secim_butonuna_tikla(): return False
            if not self.filtreleri_uygula():    return False

            musait = self.seanslari_kontrol_et()

            if musait:
                mesaj  = f"🏋️ <b>HALİÇ SU SPORLARI - FITNESS</b>\n"
                mesaj += f"📅 Kontrol: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                mesaj += f"🎉 <b>{len(musait)} müsait seans!</b>\n"
                mesaj += "─────────────────────────\n\n"

                for i, s in enumerate(musait[:10], 1):
                    tarih = s.get("tarih") or "?"
                    saat  = s.get("saat")  or "?"
                    gad   = s.get("gun")   or ""
                    sayi  = s.get("sayi",  "?")
                    ozet  = s.get("ozet", "")[:200]

                    mesaj += f"<b>#{i} — {gad} {tarih}</b>\n"
                    mesaj += f"🕐 <code>{saat}</code>\n"
                    mesaj += f"🪑 Boş kontenjan: <b>{sayi}</b>\n"
                    mesaj += f"📝 {ozet}\n"
                    mesaj += "─────────────────────────\n"

                mesaj += f"\n🔗 <a href='https://online.spor.istanbul/uyespor'><b>🚀 REZERVASYON YAP!</b></a>"
                telegram_gonder(mesaj)
            else:
                log.info("⏰ Bir sonraki kontrol ~15-20 dk sonra...")

        except Exception as e:
            log.error(f"❌ Genel hata: {e}")
        finally:
            self.kapat()


# ============================================================
# ANA DÖNGÜ
# ============================================================
def main():
    if not TC_KIMLIK or not SIFRE:
        log.error("❌ .env dosyasında SPOR_TC ve SPOR_SIFRE tanımlanmalı!")
        sys.exit(1)

    log.info("=" * 60)
    log.info("🚀 Spor Istanbul Bot Başlatıldı!")
    log.info("   Tesis : Haliç Su Sporları Merkezi")
    log.info("   Branş : FITNESS")
    log.info("=" * 60)

    telegram_gonder(
        f"🤖 <b>Bot Başlatıldı!</b>\n"
        f"📍 Haliç Su Sporları Merkezi - FITNESS\n"
        f"⏰ Her {CHECK_INTERVAL_MIN//60}-{CHECK_INTERVAL_MAX//60} dk'da bir kontrol\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    kontrol_no = 0
    while True:
        kontrol_no += 1
        log.info(f"\n{'='*60}")
        log.info(f"🔄 Kontrol #{kontrol_no} — {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        log.info(f"{'='*60}")

        SporBot().tam_kontrol()

        bekleme = random.randint(CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX)
        log.info(f"⏳ Sonraki kontrol: {bekleme//60} dk {bekleme%60} sn sonra...")
        try:
            time.sleep(bekleme)
        except KeyboardInterrupt:
            log.info("\n🛑 Bot durduruldu.")
            telegram_gonder("🛑 Bot durduruldu.")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n🛑 Bot durduruldu.")
