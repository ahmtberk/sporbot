# Sporbot

Sporbot, Spor Istanbul tesislerinde uygun seans olup olmadigini Playwright ile kontrol eden ve Telegram uzerinden yonetilen bir Python botudur.

> Not: Spor Istanbul, GitHub Actions ve benzeri bulut/veri merkezi tarayicilarinda Cloudflare insan dogrulamasi gosterebiliyor. Bu nedenle ucretsiz ve daha stabil kullanim icin botu kendi bilgisayarinizda calistirmeniz onerilir.

## Ozellikler

- Telegram komutlariyla botu baslatma, durdurma ve durum sorgulama
- Belirli sure calistirip otomatik durdurma
- Tesis, brans ve kontrol araligi ayarlarini runtime degistirme
- Uygun seans bulundugunda Telegram bildirimi gonderme
- Docker ile calistirma destegi

## Kurulum

Python bagimliliklarini yukleyin:

```bash
pip install -r requirements.txt
playwright install chromium
```

Ornek ortam dosyasini kopyalayip kendi bilgilerinizle doldurun:

```bash
cp .env.example .env
```

Windows PowerShell kullaniyorsaniz:

```powershell
Copy-Item .env.example .env
```

Gerekli temel degiskenler:

```text
SPOR_TC=
SPOR_SIFRE=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## Calistirma

Telegram servislerini baslatmak icin:

```bash
python app.py
```

Windows'ta 2 saatlik otomatik kontrol icin `start_sporbot_2h.bat` dosyasini cift tiklayabilirsiniz. Terminal penceresi kapatilirsa bot da durur.

Docker ile calistirmak icin:

```bash
docker compose up --build
```

## Telegram Komutlari

```text
/start veya /help
/startbot
/runfor 180
/status
/stopbot
/setinterval 10 15
/setbranch FITNESS
/stopafterfound on
```

## Ayarlar

Varsayilan tesis, brans ve kontrol araligi `.env` icinden ayarlanabilir. Calisma sirasinda degistirilen ayarlar `runtime_config.json` dosyasina yazilir. Bu dosya kisiye ozel oldugu icin repoya dahil edilmemelidir.

Detayli kurulum ve gunluk kullanim icin [USAGE.md](USAGE.md) dosyasina bakabilirsiniz.

## Public Repo Notlari

- `.env` dosyasini repoya eklemeyin; Telegram tokeni ve Spor Istanbul giris bilgileriniz bu dosyada durur.
- `runtime_config.json`, `bot.log`, `logs/`, `data/`, ekran goruntuleri ve debug ciktilari repoya eklenmemelidir.
- `.env.example` yalnizca bos/guvenli ornek degerler icermelidir.

## Dosya Yapisi

- `app.py`: Telegram kontrollu servis giris noktasi
- `telegram_service.py`: Telegram komutlari ve arka plan gorev yonetimi
- `checker.py`: Playwright tabanli Spor Istanbul kontrol mantigi
- `runtime_config.py`: Runtime ayarlarinin JSON dosyasinda saklanmasi
- `bot.py`: Eski lokal dongu scripti, referans amacli tutuluyor
- `Dockerfile` ve `docker-compose.yml`: Docker calistirma dosyalari

