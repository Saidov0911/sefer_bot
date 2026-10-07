"""Web panel ruxsatlari: har bir ish alohida belgilanadi.

.env dagi asosiy hisob (superadmin) hammasini qila oladi va boshqa hisoblarga
qaysi ishlar ochiqligini faqat u belgilaydi.
"""

# (bo'lim, [(kalit, nom, izoh)])
GROUPS = (
    ("Telegram bot", (
        ("applications.view", "Arizalarni ko‘rish", "Arizalar ro‘yxati, ariza tafsilotlari va bosh sahifadagi ariza ko‘rsatkichlari."),
        ("applications.status", "Ariza holatini o‘zgartirish", "Ko‘rib chiqilmoqda / qabul qilindi / rad etildi; arizachiga xabar yuborish."),
        ("applications.cv", "CV yuklab olish", "Arizaga biriktirilgan faylni yuklab olish."),
        ("applications.export", "Arizalarni CSV qilib yuklash", "Hamma arizalar, telefon raqamlari bilan, bitta faylda."),
        ("applications.toggle", "Ariza qabulini ochish va yopish", "Bot yangi ariza qabul qiladimi — bosh sahifadagi tugma."),
        ("applications.sync", "Yetkazilmagan arizalarni qayta yuborish", "Guruhga yoki Sheets’ga yetib bormagan arizalar."),
        ("users.view", "Bot foydalanuvchilarini ko‘rish", "Botga kirganlar ro‘yxati, takliflar va bosh sahifadagi ko‘rsatkichlar."),
        ("broadcast.send", "Ommaviy xabar yuborish", "Bot foydalanuvchilariga tarqatma yuborish va uni to‘xtatish."),
    )),
    ("Sayt", (
        ("site.stats", "Sayt statistikasi", "Qidiruvlar, solishtirishlar, do‘konga o‘tishlar."),
        ("site.users", "Sayt hisoblari", "Saytga kirganlar ro‘yxati, telefon raqamlari bilan."),
        ("site.shops", "Do‘konlar", "Do‘konlar, takliflar soni va o‘qish jurnali."),
        ("site.bookings", "Bandlovlar", "Saytda qilingan bandlovlar."),
        ("site.reviews", "Shubhali juftliklarni ko‘rish", "Nomi o‘xshash, birlashtirilmagan asarlar ro‘yxati."),
        ("site.reviews.decide", "Juftliklar bo‘yicha qaror", "«Bir asar» / «Boshqa asar» va ro‘yxatni qayta hisoblash."),
    )),
)

LABELS = {key: label for _, items in GROUPS for key, label, _ in items}
ALL = frozenset(LABELS)

# Bu ishlar sahifaning o'zini ko'rmasdan bajarilmaydi — ko'rish ruxsati birga beriladi.
REQUIRES = {
    "applications.status": "applications.view",
    "applications.cv": "applications.view",
    "applications.export": "applications.view",
    "site.reviews.decide": "site.reviews",
}

# Ruxsatlar qo'shilishidan oldin ochilgan hisoblar: eski rolidagi imkoniyatlar saqlanadi.
LEGACY_ROLES = {
    "admin": ALL,
    "viewer": frozenset({
        "applications.view", "applications.status", "applications.cv", "applications.export", "users.view",
        "site.stats", "site.users", "site.shops", "site.bookings", "site.reviews",
    }),
}


def normalize(keys) -> frozenset[str]:
    """Noma'lum kalitlarni tashlaydi va kerakli ko'rish ruxsatlarini qo'shadi."""
    granted = {k for k in keys if k in ALL}
    granted |= {REQUIRES[k] for k in granted if k in REQUIRES}
    return frozenset(granted)


def encode(keys) -> str:
    return ",".join(sorted(normalize(keys)))


def decode(stored: str | None, legacy_role: str) -> frozenset[str]:
    if stored is None:
        return LEGACY_ROLES.get(legacy_role, frozenset())
    return normalize(stored.split(","))
