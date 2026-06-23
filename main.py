import requests
from bs4 import BeautifulSoup
import time
import json
import os
import hashlib
from datetime import datetime

# ============================================================
# AYARLAR - Sadece burası değiştir!
# ============================================================
TELEGRAM_TOKEN = "8857167618:AAF3m1zCDteHcMU6QtORN0kFqrM3IUYCQ-I"
TELEGRAM_CHAT_ID = "622428916"
KONTROL_SURESI = 60  # saniye (60 = 1 dakikada bir)
# ============================================================

FORUMLAR = [
    {
        "isim": "DonanımHaber",
        "url": "https://forum.donanimhaber.com/sicak-firsatlar--f193",
        "selectors": ["h3.konu-baslik a", "h4.konu-baslik a", "td.subject a", "a.konu-link"],
    },
    {
        "isim": "DonanımArşivi",
        "url": "https://forum.donanimarsivi.com/forumlar/Sicakfirsatlar/",
        "selectors": ["h3.structItem-title a[data-preview-url]", "div.structItem-title a", "h3 a.PreviewTooltip"],
    },
    {
        "isim": "R10",
        "url": "https://www.r10.net/sicak-firsatlar/",
        "selectors": ["h2.thread-title a", "a.thread-link", "div.threadTitle a", "td.alt1 a.title"],
    },
]

GORULMUS_DOSYA = "gorulmus.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def gorulmusleri_yukle():
    if os.path.exists(GORULMUS_DOSYA):
        with open(GORULMUS_DOSYA, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def gorulmusleri_kaydet(gorulmus):
    # Son 5000 kaydı tut (dosya şişmesin)
    liste = list(gorulmus)[-5000:]
    with open(GORULMUS_DOSYA, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False)


def hash_olustur(metin):
    return hashlib.md5(metin.encode("utf-8")).hexdigest()


def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    veri = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, data=veri, timeout=10)
        if r.status_code != 200:
            print(f"Telegram hatası: {r.text}")
    except Exception as e:
        print(f"Telegram gönderilemedi: {e}")


def forum_tara(forum):
    try:
        r = requests.get(forum["url"], headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        basliklar = []
        for selector in forum["selectors"]:
            bulunanlar = soup.select(selector)
            if bulunanlar:
                basliklar = bulunanlar
                break

        if not basliklar:
            # Genel fallback: sayfadaki tüm linkleri dene
            basliklar = soup.select("a[href]")

        sonuclar = []
        for tag in basliklar[:30]:  # İlk 30 gönderi
            baslik = tag.get_text(strip=True)
            href = tag.get("href", "")

            if not baslik or len(baslik) < 10:
                continue

            # Tam URL oluştur
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                base = "/".join(forum["url"].split("/")[:3])
                link = base + href
            else:
                continue

            sonuclar.append({"baslik": baslik, "link": link})

        return sonuclar

    except Exception as e:
        print(f"[{forum['isim']}] Tarama hatası: {e}")
        return []


def kontrol_et(gorulmus):
    yeni_sayisi = 0

    for forum in FORUMLAR:
        gonderiler = forum_tara(forum)

        for gonderi in gonderiler:
            anahtar = hash_olustur(gonderi["link"])

            if anahtar not in gorulmus:
                gorulmus.add(anahtar)
                yeni_sayisi += 1

                mesaj = (
                    f"🔥 <b>Yeni Fırsat!</b> [{forum['isim']}]\n\n"
                    f"📌 {gonderi['baslik']}\n\n"
                    f"🔗 {gonderi['link']}"
                )
                telegram_gonder(mesaj)
                print(f"[YENİ] {forum['isim']}: {gonderi['baslik'][:60]}")
                time.sleep(0.5)  # Telegram rate limit

    return gorulmus, yeni_sayisi


def main():
    print("=" * 50)
    print("🚀 Fırsat Takip Botu Başlatıldı")
    print(f"⏱  Kontrol sıklığı: {KONTROL_SURESI} saniye")
    print(f"📡 Takip edilen forum sayısı: {len(FORUMLAR)}")
    print("=" * 50)

    telegram_gonder("✅ <b>Fırsat Takip Botu başlatıldı!</b>\n\nYeni fırsatlar bulunduğunda seni bilgilendireceğim. 🔥")

    gorulmus = gorulmusleri_yukle()
    print(f"📂 Daha önce görülmüş {len(gorulmus)} kayıt yüklendi")

    # İlk çalışmada mevcut fırsatları kaydet, bildirim gönderme
    if len(gorulmus) == 0:
        print("🔍 İlk tarama yapılıyor, mevcut fırsatlar kaydediliyor...")
        for forum in FORUMLAR:
            gonderiler = forum_tara(forum)
            for g in gonderiler:
                gorulmus.add(hash_olustur(g["link"]))
        gorulmusleri_kaydet(gorulmus)
        print(f"✅ {len(gorulmus)} mevcut fırsat kaydedildi. Artık yenileri takip edilecek!")

    while True:
        try:
            saat = datetime.now().strftime("%H:%M:%S")
            print(f"[{saat}] Kontrol ediliyor...", end=" ")

            gorulmus, yeni = kontrol_et(gorulmus)
            gorulmusleri_kaydet(gorulmus)

            if yeni > 0:
                print(f"✅ {yeni} yeni fırsat bulundu!")
            else:
                print("Yeni fırsat yok.")

        except KeyboardInterrupt:
            print("\n⛔ Bot durduruldu.")
            break
        except Exception as e:
            print(f"\n❌ Beklenmeyen hata: {e}")

        time.sleep(KONTROL_SURESI)


if __name__ == "__main__":
    main()
