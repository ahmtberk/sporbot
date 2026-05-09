# Spor Istanbul Slot Botu (Sporbot)

## Telegram kontrollu servis

Uzaktan/Docker ile calistirmak ve Telegram komutlariyla yonetmek icin yeni servis girisi:

```bash
python app.py
```

Komutlar: `/startbot`, `/stopbot`, `/status`, `/setfacility`, `/setbranch`, `/setinterval`, `/stopafterfound`.

Detayli kurulum ve deployment notlari icin [DEPLOYMENT.md](DEPLOYMENT.md) dosyasina bakin.

Bu bot, Online Spor İstanbul (`online.spor.istanbul`) üzerinden "Haliç Su Sporları Merkezi" (veya ayarlayacağınız başka bir tesis) için "Fitness" branşındaki boş yerleri periyodik olarak kontrol eder. Boş bir yer bulduğunda size ücretsiz olarak Telegram üzerinden anlık mesaj gönderir.

## Gereksinimler

- [Python 3.8+](https://www.python.org/downloads/) yüklü olmalıdır.

## Kurulum Adımları

1. Bu klasördeki terminali/komut istemini (CMD veya PowerShell) açın.
2. Gerekli kütüphaneleri yüklemek için aşağıdaki komutu çalıştırın:
   ```bash
   pip install -r requirements.txt
   ```
3. Playwright tarayıcılarını kurmak için şu komutu çalıştırın:
   ```bash
   playwright install chromium
   ```
4. `.env.example` dosyasının adını `.env` olarak değiştirin ve içini kendi bilgilerinizle doldurun:
   - `SPOR_TC` = TC Kimlik Numaranız
   - `SPOR_SIFRE` = Spor İstanbul Şifreniz
   - `TELEGRAM_BOT_TOKEN` = BotFather'dan aldığınız token
   - `TELEGRAM_CHAT_ID` = Kendi sohbet ID'niz

## Telegram Bot Bilgileri Nasıl Alınır?

**1. Bot Token Alma:**
- Telegram uygulamasında arama kısmına **@BotFather** yazın ve ona mesaj atın.
- `/newbot` komutunu gönderin ve botunuza bir isim verin.
- Sonunda `bot` kelimesi geçen bir kullanıcı adı belirleyin (Örn: `spor_istanbul_bot`).
- İşlem bitince size uzun bir **HTTP API Token** (Örn: `123456789:ABCdefGHI...`) verecektir. Bu kodu `TELEGRAM_BOT_TOKEN` kısmına yapıştırın.
- *Önemli:* Oluşturduğunuz bota Telegram'da aratıp **"Başlat (Start)"** butonuna basmayı unutmayın, aksi halde bot size mesaj gönderemez.

**2. Chat ID Alma:**
- Kendi hesabınızın ID'sini öğrenmek için Telegram arama kısmına **@userinfobot** yazın ve mesaj gönderin.
- Size `Id: 123456789` şeklinde bir cevap verecektir. Bu rakamları `TELEGRAM_CHAT_ID` kısmına yapıştırın.

## Botu Çalıştırma

Tüm ayarları yaptıktan sonra komut satırına aşağıdaki komutu yazarak botu başlatabilirsiniz:

```bash
python bot.py
```

Bot 15-20 dakika arasında rastgele bekleyerek kontrol sağlayacaktır.

## İleri Düzey Ayarlar
Eğer `bot.py`'nin çalışmasında takılmalar olursa veya tesis ismini ("Haliç Su Sporları Merkezi") farklı şekilde girmek isterseniz `bot.py` içerisindeki `TESIS_ADI` ve `BRANS_ADI` değişkenlerini güncelleyebilirsiniz. Ayrıca sayfa içindeki butonların tam isimleri sistem tarafından değiştirildiyse kodun `try...except` blokları arasındaki `text=''` kısımlarını tarayıcıda gördüğünüz güncel kelimelerle değiştirebilirsiniz.
