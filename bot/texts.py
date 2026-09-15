WELCOME = (
    "Assalomu alaykum, <b>{name}</b>! 👋\n\n"
    "<b>Sefer</b> loyihasiga ariza topshirish botiga xush kelibsiz.\n\n"
    "Ariza topshirish bosqichlari:\n"
    "1️⃣ Sefer kanali va Instagram sahifasiga a’zo bo‘lish\n"
    "2️⃣ {refs} ta do‘stingizni taklif qilish\n"
    "3️⃣ Anketani to‘ldirish"
)

SUBSCRIBE = (
    "<b>1-bosqich: Obuna</b>\n\n"
    "Botdan foydalanish uchun quyidagi sahifalarga a’zo bo‘ling, so‘ng "
    "<b>«✅ Tekshirish»</b> tugmasini bosing."
)
NOT_SUBSCRIBED = "❌ Siz hali Sefer kanaliga a’zo bo‘lmagansiz. Avval kanalga qo‘shiling."
SUBSCRIBED_OK = "✅ Obuna tasdiqlandi!"

REFERRAL = (
    "<b>2-bosqich: Do‘stlarni taklif qilish</b>\n\n"
    "Quyidagi shaxsiy havolangiz orqali <b>{need} ta</b> do‘stingizni taklif qiling. "
    "Do‘stingiz botga kirib, Sefer kanaliga a’zo bo‘lgachgina hisobga olinadi.\n\n"
    "🔗 Sizning havolangiz:\n<code>{link}</code>\n\n"
    "📊 Taklif qilinganlar: <b>{count}/{need}</b>"
)
REFERRAL_NOT_ENOUGH = "Hozircha {count}/{need}. Yana {left} ta do‘stingizni taklif qiling."
REFERRAL_SHARE_TEXT = "Sefer loyihasiga ariza topshirish uchun botga qo‘shiling 👇"
REFERRAL_NEW = "🎉 Yangi do‘stingiz qo‘shildi! Taklif qilinganlar: <b>{count}/{need}</b>"
REFERRAL_DONE = "🎉 Tabriklaymiz! {need} ta do‘stingizni taklif qildingiz. Endi anketani to‘ldirishingiz mumkin."

FORM_START = "<b>3-bosqich: Anketa</b>\n\nIltimos, savollarga ketma-ket javob bering."
ASK_NAME = "✍️ <b>Ism va familiyangizni</b> kiriting:\n\n<i>Masalan: Aliyev Vali</i>"
BAD_NAME = "Iltimos, ism va familiyangizni to‘liq kiriting (kamida 2 so‘z, faqat harflar)."

ASK_PHONE = (
    "📱 <b>Telefon raqamingizni</b> yuboring.\n\n"
    "Pastdagi tugmani bosing yoki raqamni <code>+998901234567</code> ko‘rinishida yozing."
)
BAD_PHONE = "Telefon raqam noto‘g‘ri. Tugmani bosing yoki <code>+998901234567</code> ko‘rinishida yozing."
FOREIGN_CONTACT = "Iltimos, o‘zingizning raqamingizni yuboring."

ASK_CV = "📄 <b>Rezyumengizni (CV)</b> fayl ko‘rinishida yuboring.\n\nQabul qilinadigan formatlar: PDF, DOC, DOCX."
BAD_CV = "Iltimos, rezyumeni <b>PDF, DOC yoki DOCX</b> fayl sifatida yuboring."

ASK_ESSAY = (
    "📝 <b>Nega aynan sizni loyihaga qabul qilishimiz kerak?</b>\n\n"
    "Esse yozing (<b>{max} ta so‘zgacha</b>)."
)
ESSAY_TOO_LONG = "Esse {count} ta so‘zdan iborat. Iltimos, uni <b>{max} ta so‘zgacha</b> qisqartiring."

ASK_ANSWER = (
    "📚 <b>Elektron kitob, audiokitob va qog‘oz kitob — qaysi biri kelajak uchun samaraliroq? Nega?</b>\n\n"
    "Fikringizni yozing."
)

TEXT_ONLY = "Iltimos, javobni matn ko‘rinishida yozing."

CONFIRM = (
    "<b>Anketangizni tekshiring:</b>\n\n"
    "👤 <b>Ism familiya:</b> {full_name}\n"
    "📱 <b>Telefon:</b> {phone}\n"
    "📄 <b>CV:</b> {cv}\n\n"
    "📝 <b>Esse:</b>\n{essay}\n\n"
    "📚 <b>Kitoblar haqida:</b>\n{answer}\n\n"
    "Hammasi to‘g‘rimi?"
)
SUBMITTED = (
    "✅ <b>Arizangiz qabul qilindi!</b>\n\n"
    "Rahmat! Natijalar haqida siz bilan bog‘lanamiz. Sefer kanalini kuzatib boring."
)
ALREADY_SUBMITTED = "✅ Siz allaqachon ariza topshirgansiz. Natijalar haqida siz bilan bog‘lanamiz."
RESTART_FORM = "Anketani qaytadan to‘ldiramiz."

BTN_CHANNEL = "📢 Sefer kanali"
BTN_INSTAGRAM = "📸 Instagram"
BTN_CHECK = "✅ Tekshirish"
BTN_SHARE = "📤 Do‘stlarga ulashish"
BTN_CHECK_REFS = "🔄 Tekshirish"
BTN_PHONE = "📱 Raqamni yuborish"
BTN_SUBMIT = "✅ Yuborish"
BTN_RESTART = "🔄 Qaytadan to‘ldirish"

STATUS_LABELS = {
    "new": "🆕 Yangi",
    "reviewing": "👀 Ko‘rib chiqilmoqda",
    "accepted": "✅ Qabul qilindi",
    "rejected": "❌ Rad etildi",
}
# Holat o'zgarganda foydalanuvchiga yuboriladigan xabarlar ("new" uchun xabar yo'q)
STATUS_NOTIFY = {
    "reviewing": "👀 Arizangiz ko‘rib chiqilmoqda. Natija haqida xabar beramiz.",
    "accepted": "🎉 <b>Tabriklaymiz!</b> Arizangiz qabul qilindi. Tez orada siz bilan bog‘lanamiz.",
    "rejected": (
        "Afsuski, arizangiz bu safar qabul qilinmadi. Qiziqishingiz uchun rahmat! "
        "Sefer kanalini kuzatib boring — yangi imkoniyatlar albatta bo‘ladi."
    ),
}
AUDIENCE_LABELS = {
    "all": "👥 Barcha foydalanuvchilar",
    "applied": "📝 Ariza topshirganlar",
    "not_applied": "⏳ Ariza topshirmaganlar",
    **{status: f"{label} arizalar" for status, label in STATUS_LABELS.items()},
}

ADMIN_APPLICATION = (
    "🆕 <b>Yangi ariza</b>\n\n"
    "👤 <b>Ism familiya:</b> {full_name}\n"
    "📱 <b>Telefon:</b> {phone}\n"
    "🆔 <b>Telegram:</b> {user_link}\n"
    "👥 <b>Takliflar:</b> {referrals}"
)
