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

## Admin panel

Ikki xil panel bor, ikkalasi ham bir xil ma'lumot bilan ishlaydi.

### Bot ichida

`ADMIN_IDS` dagi foydalanuvchilar uchun:

- `/admin` — tugmali panel:
  - **Arizalar** — holat bo'yicha filtr, sahifalash, arizani ochish, CV faylni olish;
  - **Holat** — Yangi / Ko'rib chiqilmoqda / Qabul qilindi / Rad etildi. O'zgartirishdan oldin tasdiqlanadi,
    foydalanuvchiga xabar yuborish ixtiyoriy;
  - **Qidirish** — ism, telefon, @username yoki Telegram ID bo'yicha;
  - **CSV eksport** — barcha yoki filtrlangan arizalar (Excel'da ochiladi);
  - **Ommaviy xabar** — auditoriya tanlanadi (hammasi, ariza topshirgan/topshirmagan, holat bo'yicha),
    istalgan xabar (matn, rasm, video, fayl) aynan shu ko'rinishda yuboriladi. Botni bloklaganlar belgilanadi
    va keyingi tarqatmalarda hisobga olinmaydi.
- `/stats` — statistika.
- `/sync` — guruhga yoki Sheets'ga yetib bormagan arizalarni qayta yuborish (bot ishga tushganda ham avtomatik bajariladi).
- `/cancel` — qidiruv yoki tarqatmani bekor qilish.

### Web panel

`.env` da `ADMIN_PASSWORD` berilsa, bot bilan birga web panel ham ishga tushadi (`WEB_PORT`, standart `8080`):
bosh sahifa (statistika), arizalar (filtr, qidiruv, CSV, CV yuklab olish, holatni o'zgartirish),
foydalanuvchilar ro'yxati va matnli ommaviy xabar (avval adminlarga sinab ko'rish mumkin).

- `WEB_SECRET_KEY` ni albatta bering — aks holda har restartda qayta kirish kerak bo'ladi.
- Docker'da panel faqat `127.0.0.1:8080` da ochiladi. Serverdan tashqariga **HTTPS orqali** chiqaring
  (masalan, Caddy: `admin.example.uz { reverse_proxy 127.0.0.1:8080 }`) va `WEB_HTTPS_ONLY=true` qiling.
  Paroli bor panelni oddiy HTTP orqali ochiq qoldirmang.
- 10 daqiqada 5 marta noto'g'ri parol kiritilsa, shu IP vaqtincha bloklanadi.

Arizalar holati bazada saqlanadi (eski bazaga ustunlar bot ishga tushganda avtomatik qo'shiladi);
Google Sheets'dagi qatorlar holat o'zgarganda yangilanmaydi.

## Tuzilma

```
bot/
  __main__.py        ishga tushirish
  config.py          .env sozlamalari
  db.py              SQLite (users, applications) + migratsiyalar
  flow.py            bosqichlarni aniqlash: obuna → referal → anketa
  texts.py           barcha matnlar
  keyboards.py, states.py
  admin_ui.py        bot ichidagi admin panel tugmalari va matnlari
  handlers/          start (obuna, referal), form (anketa), admin, fallback
  services/          subscription, delivery (guruh + Sheets), sheets, status, broadcast, export
  web/               web admin panel (FastAPI + Jinja2 shablonlar)
```
