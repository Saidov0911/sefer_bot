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

**Hisoblar va rollar.** `.env` dagi `ADMIN_USERNAME`/`ADMIN_PASSWORD` — asosiy hisob (uni paneldan o'chirib bo'lmaydi).
Qolgan xodimlarga hisob panel ichida **«Hisoblar»** bo'limidan ochiladi, parollar bazada `scrypt` bilan hashlab saqlanadi:

| Rol | Nima qila oladi |
|---|---|
| To'liq admin | Hammasi: ommaviy xabar, hisoblarni boshqarish, `/sync` |
| Ko'ruvchi | Arizalar va foydalanuvchilarni ko'radi, holat qo'yadi, CV va CSV yuklaydi |

Har kim o'z parolini yuqoridagi o'z logini orqali o'zgartira oladi; unutilgan parolni to'liq admin tiklaydi.
Hisob o'chirilsa yoki roli o'zgarsa, bu o'sha odamning ochiq sessiyasiga ham darhol ta'sir qiladi.

- `WEB_SECRET_KEY` ni albatta bering — aks holda har restartda qayta kirish kerak bo'ladi.
- Panel faqat `127.0.0.1:8080` da ochiladi. Domen orqali ochish — quyidagi **Domen va HTTPS (nginx)** bo'limida.
  Paroli bor panelni oddiy HTTP orqali ochiq qoldirmang.
- 10 daqiqada 5 marta noto'g'ri parol kiritilsa, shu IP vaqtincha bloklanadi.

Arizalar holati bazada saqlanadi (eski bazaga ustunlar bot ishga tushganda avtomatik qo'shiladi);
Google Sheets'dagi qatorlar holat o'zgarganda yangilanmaydi.

### Domen va HTTPS (nginx)

Ubuntu/Debian serverda, bot Docker'da ishlayotgan holat uchun. Quyida `admin.example.uz` o'rniga o'z domeningizni yozing.

**1. DNS.** Domen panelida `A` yozuv qo'shing: `admin.example.uz → serverning IP manzili`. Tarqalishini tekshiring:

```bash
dig +short admin.example.uz   # server IP'sini ko'rsatishi kerak
```

**2. Bot.** `.env` da:

```env
ADMIN_PASSWORD=kuchli-parol
WEB_SECRET_KEY=...        # python3 -c "import secrets; print(secrets.token_hex(32))"
WEB_HTTPS_ONLY=true
```

```bash
docker compose up -d --build
# 200 chiqishi kerak (WEB_PORT o'zgartirilgan bo'lsa, portni ham almashtiring).
# curl -I ishlatmang: u HEAD so'rovi yuboradi va panel 405 qaytaradi — bu xato emas
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/login
```

**3. nginx va certbot.**

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
sudo ufw allow 'Nginx Full'   # 80 va 443. 8080 portni OCHMANG
```

**4. Sertifikat** (nginx konfiguratsiyasidan oldin — u sertifikat fayllariga tayanadi):

```bash
sudo certbot certonly --nginx -d admin.example.uz --deploy-hook "systemctl reload nginx"
```

**5. nginx konfiguratsiyasi** (loyiha papkasidan):

```bash
DOMAIN=admin.example.uz
sudo cp deploy/nginx/sefer-admin.conf /etc/nginx/sites-available/sefer-admin.conf
sudo sed -i "s/admin\.example\.uz/$DOMAIN/g" /etc/nginx/sites-available/sefer-admin.conf
sudo ln -s /etc/nginx/sites-available/sefer-admin.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**6. Tekshirish.** `https://admin.example.uz` login sahifasini ochishi kerak. Sertifikat 90 kunda avtomatik yangilanadi,
buni sinab ko'rish:

```bash
sudo certbot renew --dry-run
```

**Muammolar:**

| Belgi | Sabab |
|---|---|
| `502 Bad Gateway` | Bot ishlamayapti, `ADMIN_PASSWORD` bo'sh yoki nginx'dagi `proxy_pass` porti `WEB_PORT` ga mos emas: `docker compose logs bot \| grep -i web` |
| `Bind for 127.0.0.1:8080 failed: port is already allocated` | Port band. Kim band qilganini ko'ring: `sudo lsof -i :8080` va `docker ps`. Eski konteyner bo'lsa `docker compose down` qiling (ikkita bot bir vaqtda ishlasa, Telegram 409 xatosi chiqadi). Boshqa dastur bo'lsa `.env` da `WEB_PORT` ni o'zgartiring va `proxy_pass` ni ham moslang |
| Kirgach yana login sahifasiga qaytaradi | `WEB_HTTPS_ONLY=true`, lekin sayt `http://` orqali ochilgan — `https://` dan kiring |
| Har restartdan keyin qayta kirish kerak | `WEB_SECRET_KEY` berilmagan |
| `certbot` domen tekshiruvidan o'tmaydi | DNS hali tarqalmagan yoki 80-port yopiq |
| `nginx -t`: `cannot load certificate` | 4-qadam bajarilmagan yoki domen nomi `sed` da noto'g'ri yozilgan |

CentOS/RHEL'da `sites-available` o'rniga faylni `/etc/nginx/conf.d/sefer-admin.conf` ga qo'ying.

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
