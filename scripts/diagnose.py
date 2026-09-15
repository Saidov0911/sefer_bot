"""Faqat o'qiydigan diagnostika: referal voronkasi va arizalar yetkazilishi. Bazaga hech narsa yozmaydi."""
import os
import sqlite3
import sys

path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DB_PATH", "data/bot.db")
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
q = lambda sql: conn.execute(sql).fetchall()
one = lambda sql: q(sql)[0][0]
NEED = int(os.environ.get("REQUIRED_REFERRALS", 3))

INVITES = "SELECT referrer_id, COUNT(*) AS n FROM users WHERE referral_credited = 1 GROUP BY referrer_id"
REACHED = f"SELECT referrer_id FROM ({INVITES}) WHERE n >= {NEED}"

print(f"== Voronka (baza: {path})")
print(f"Foydalanuvchilar jami:                     {one('SELECT COUNT(*) FROM users')}")
print(f"Havola orqali kelgan:                      {one('SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL')}")
print(f"  ...shundan kanalga a'zo (hisoblangan):   {one('SELECT COUNT(*) FROM users WHERE referral_credited = 1')}")
print(f"Kamida 1 kishi taklif qilganlar:           {one(f'SELECT COUNT(*) FROM ({INVITES})')}")
print(f"{NEED}+ kishi taklif qilganlar (anketaga o'tgan): {one(f'SELECT COUNT(*) FROM ({REACHED})')}")
print(f"  ...shundan ariza topshirgan:             {one(f'SELECT COUNT(*) FROM ({REACHED}) r JOIN applications a ON a.user_id = r.referrer_id')}")
print(f"  ...ariza topshirMAGAN:                   {one(f'SELECT COUNT(*) FROM ({REACHED}) r LEFT JOIN applications a ON a.user_id = r.referrer_id WHERE a.user_id IS NULL')}")
print(f"Arizalar jami:                             {one('SELECT COUNT(*) FROM applications')}")
print(f"{NEED} tadan ortiqcha takliflar:                 {one(f'SELECT COALESCE(SUM(n - {NEED}), 0) FROM ({INVITES}) WHERE n > {NEED}')}")
print(f"Taklif qilingan, o'zi ham ariza topshirgan: {one('SELECT COUNT(*) FROM users u JOIN applications a ON a.user_id = u.id WHERE u.referral_credited = 1')}")

print("\n== Bir kishi nechta odam taklif qilgan (hisoblanganlar)")
for invites, referrers in q(f"SELECT CASE WHEN n >= 10 THEN '10+' ELSE CAST(n AS TEXT) END, COUNT(*) FROM ({INVITES}) GROUP BY 1 ORDER BY MIN(n)"):
    print(f"  {invites:>4} ta taklif: {referrers} kishi")

print("\n== Eng ko'p taklif qilganlar")
for uid, username, name, n, applied in q(
    f"SELECT i.referrer_id, u.username, u.tg_name, i.n, a.user_id IS NOT NULL "
    f"FROM ({INVITES}) i JOIN users u ON u.id = i.referrer_id LEFT JOIN applications a ON a.user_id = i.referrer_id "
    f"ORDER BY i.n DESC LIMIT 15"
):
    print(f"  {n:>4}  {uid}  @{username or '-'}  {name or ''}  {'ariza bor' if applied else 'ariza YOQ'}")

print("\n== Yetkazish")
total, no_group, no_sheet = q("SELECT COUNT(*), COALESCE(SUM(admin_msg_id IS NULL), 0), COALESCE(SUM(sheet_synced = 0), 0) FROM applications")[0]
print(f"Arizalar: {total} · guruhga yetmagan: {no_group} · Sheets'ga yozilmagan: {no_sheet}")
print(f"Oxirgi ariza: {one('SELECT MAX(created_at) FROM applications')} (UTC)")
