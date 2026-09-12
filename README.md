# Sefer ariza boti

Sefer loyihasiga ariza qabul qiluvchi Telegram bot (Python 3.12+, aiogram 3).

## Oqim

1. **Obuna** — Sefer Telegram kanali (bot tekshiradi) va Instagram (faqat havola, tekshirib bo'lmaydi).
2. **3 ta do'st** — har kimga shaxsiy havola (`t.me/<bot>?start=<id>`). Do'st faqat havola orqali
   *birinchi marta* kirib, kanalga a'zo bo'lgach hisoblanadi. O'zini taklif qilish va eski foydalanuvchilar hisoblanmaydi.
3. **Anketa** — ism familiya → telefon (tugma yoki qo'lda) → CV (PDF/DOC/DOCX) → esse (≤200 so'z) →
   "Elektron, audio yoki qog'oz kitob?" → tasdiqlash → yuborish.

Yuborilgan ariza admin guruhiga (CV fayli + esse) va Google Sheets'ga yoziladi. Har bir foydalanuvchi bitta ariza topshira oladi.

## Sozlash

1. @BotFather'da bot yarating, tokenni oling.
2. Botni **Sefer kanaliga admin** qiling (a'zolikni tekshirish uchun shart).
3. Yopiq guruh oching, botni qo'shing. Guruh ID'sini oling (`-100...`).
4. `cp .env.example .env` va qiymatlarni to'ldiring.

### Google Sheets (ixtiyoriy)

1. Google Cloud'da loyiha → **Google Sheets API** ni yoqing → **Service account** yarating → JSON kalitni yuklab,
   `credentials.json` nomi bilan loyiha papkasiga qo'ying.
2. Jadval oching va uni service account email'iga (`...@...iam.gserviceaccount.com`) **Editor** sifatida ulashing.
3. `.env` da `GOOGLE_SHEET_ID` ni kiriting (jadval URL'idagi `/d/<ID>/edit` qismi).

`GOOGLE_SHEET_ID` bo'sh bo'lsa Sheets o'chiq bo'ladi.

## Ishga tushirish

```bash
# Docker (Redis bilan — anketa javoblari restartda yo'qolmaydi)
docker compose up -d --build

# yoki lokal
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m bot
```

> Docker'da `credentials.json` fayli mavjud bo'lishi kerak. Sheets ishlatilmasa, `docker-compose.yml` dagi
> tegishli `volumes` qatorini o'chiring.

## Admin buyruqlari

`ADMIN_IDS` dagi foydalanuvchilar uchun:

- `/stats` — foydalanuvchilar, takliflar, arizalar soni.
- `/sync` — guruhga yoki Sheets'ga yetib bormagan arizalarni qayta yuborish (bot ishga tushganda ham avtomatik bajariladi).

## Tuzilma

```
bot/
  __main__.py        ishga tushirish
  config.py          .env sozlamalari
  db.py              SQLite (users, applications)
  flow.py            bosqichlarni aniqlash: obuna → referal → anketa
  texts.py           barcha matnlar
  keyboards.py, states.py
  handlers/          start (obuna, referal), form (anketa), admin, fallback
  services/          subscription, delivery (guruh + Sheets), sheets
```
