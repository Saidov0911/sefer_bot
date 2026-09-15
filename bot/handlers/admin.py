import html
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message

from bot import admin_ui as ui
from bot import texts
from bot.config import settings
from bot.db import Database
from bot.services.broadcast import Broadcaster, BroadcastJob
from bot.services.delivery import deliver_pending
from bot.services.export import applications_csv
from bot.services.sheets import Sheets
from bot.services.status import change_status
from bot.states import Admin
from bot.utils import TASHKENT

router = Router()
router.message.filter(F.from_user.id.in_(settings.admin_id_set))
router.callback_query.filter(F.from_user.id.in_(settings.admin_id_set))

QUERY_KEY = "admin_query"
ADMIN_STATES = StateFilter(Admin.search, Admin.broadcast_message, Admin.broadcast_confirm)


def not_command(message: Message) -> bool:
    return not (message.text or "").startswith("/")


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def _saved_query(state: FSMContext) -> str | None:
    return (await state.get_data()).get(QUERY_KEY)


# --- Buyruqlar ---

@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE)
async def cmd_admin(message: Message, db: Database, state: FSMContext):
    await state.clear()
    text, markup = await ui.home(db)
    await message.answer(text, reply_markup=markup)


@router.message(Command("cancel"), ADMIN_STATES)
async def cmd_cancel(message: Message, db: Database, state: FSMContext):
    await state.set_state(None)
    text, markup = await ui.home(db)
    await message.answer(text, reply_markup=markup)


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database):
    await message.answer(await ui.stats_text(db))


@router.message(Command("sync"))
async def cmd_sync(message: Message, bot: Bot, db: Database, sheets: Sheets | None):
    count = await deliver_pending(bot, db, sheets)
    await message.answer(f"🔄 Qayta yuborildi: {count} ta ariza. Natijani /stats orqali tekshiring.")


# --- Menyu ---

@router.callback_query(ui.Menu.filter(F.action == "noop"))
async def on_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(ui.Menu.filter(F.action == "home"))
async def on_home(callback: CallbackQuery, db: Database, state: FSMContext):
    await state.set_state(None)
    await callback.answer()
    await _edit(callback, *await ui.home(db))


@router.callback_query(ui.Menu.filter(F.action == "stats"))
async def on_stats(callback: CallbackQuery, db: Database):
    await callback.answer()
    await _edit(callback, await ui.stats_text(db), ui.back_home())


@router.callback_query(ui.Menu.filter(F.action == "sync"))
async def on_sync(callback: CallbackQuery, bot: Bot, db: Database, sheets: Sheets | None):
    await callback.answer("⏳ Yuborilmoqda...")
    count = await deliver_pending(bot, db, sheets)
    await callback.message.answer(f"🔄 Qayta yuborildi: {count} ta ariza.")


# --- Arizalar ---

@router.callback_query(ui.Menu.filter(F.action == "search"))
async def on_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.search)
    await callback.answer()
    await _edit(
        callback,
        "🔍 <b>Qidiruv</b>\n\nIsm, telefon, @username yoki Telegram ID yuboring.\n\n/cancel — bekor qilish",
        ui.back_home(),
    )


@router.message(Admin.search, F.text, not_command)
async def got_search(message: Message, db: Database, state: FSMContext):
    query = message.text.strip()[:100]
    await state.set_state(None)
    await state.update_data({QUERY_KEY: query})
    text, markup = await ui.app_list(db, status="", page=0, query=query)
    await message.answer(text, reply_markup=markup)


@router.callback_query(ui.AppList.filter())
async def on_list(callback: CallbackQuery, callback_data: ui.AppList, db: Database, state: FSMContext):
    query = await _saved_query(state) if callback_data.q else None
    await callback.answer()
    await _edit(callback, *await ui.app_list(db, callback_data.status, callback_data.page, query))


@router.callback_query(ui.AppView.filter())
async def on_view(callback: CallbackQuery, callback_data: ui.AppView, db: Database):
    app = await db.get_application(callback_data.user_id)
    if app is None:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return
    await callback.answer()
    await _edit(callback, *ui.app_view(app, callback_data.status, callback_data.page, callback_data.q))


@router.callback_query(ui.AppAction.filter(F.action == "cv"))
async def on_cv(callback: CallbackQuery, callback_data: ui.AppAction, db: Database):
    app = await db.get_application(callback_data.user_id)
    if app is None:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer_document(app.cv_file_id, caption=f"📄 {html.escape(app.full_name)}")


@router.callback_query(ui.AppAction.filter(F.action == "ask"))
async def on_ask_status(callback: CallbackQuery, callback_data: ui.AppAction, db: Database):
    app = await db.get_application(callback_data.user_id)
    if app is None:
        await callback.answer("Ariza topilmadi", show_alert=True)
        return
    await callback.answer()
    d = callback_data
    await _edit(callback, *ui.app_view(app, d.status, d.page, d.q, confirm=d.value))


@router.callback_query(ui.AppAction.filter(F.action == "set"))
async def on_set_status(callback: CallbackQuery, callback_data: ui.AppAction, bot: Bot, db: Database):
    d = callback_data
    changed, notified = await change_status(bot, db, d.user_id, d.value, d.notify)
    if not changed:
        note = "Holat o‘zgarmadi"
    elif d.notify and not notified:
        note = "✅ Holat o‘zgartirildi, lekin foydalanuvchiga xabar yetib bormadi (botni bloklagan bo‘lishi mumkin)"
    else:
        note = "✅ Holat o‘zgartirildi" + (", xabar yuborildi" if notified else "")
    await callback.answer(note, show_alert=changed and d.notify and not notified)

    app = await db.get_application(d.user_id)
    if app is not None:
        await _edit(callback, *ui.app_view(app, d.status, d.page, d.q))


@router.callback_query(ui.Export.filter())
async def on_export(callback: CallbackQuery, callback_data: ui.Export, db: Database, state: FSMContext):
    query = await _saved_query(state) if callback_data.q else None
    apps = await db.list_applications(callback_data.status or None, query)
    await callback.answer()
    if not apps:
        await callback.message.answer("Eksport uchun ariza yo‘q.")
        return
    filename = f"arizalar_{datetime.now(TASHKENT):%Y%m%d_%H%M}.csv"
    await callback.message.answer_document(
        BufferedInputFile(applications_csv(apps), filename), caption=f"📥 {len(apps)} ta ariza"
    )


# --- Ommaviy xabar ---

@router.callback_query(ui.Menu.filter(F.action == "broadcast"))
@router.callback_query(ui.Broadcast.filter(F.action == "refresh"))
async def on_broadcast_menu(callback: CallbackQuery, db: Database, state: FSMContext, broadcaster: Broadcaster):
    await state.set_state(None)
    await callback.answer()
    await _edit(callback, *await ui.broadcast_menu(db, broadcaster))


@router.callback_query(ui.Broadcast.filter(F.action == "audience"))
async def on_broadcast_audience(
    callback: CallbackQuery, callback_data: ui.Broadcast, state: FSMContext, broadcaster: Broadcaster
):
    if broadcaster.running:
        await callback.answer("Boshqa tarqatma hali tugamagan", show_alert=True)
        return
    await state.set_state(Admin.broadcast_message)
    await state.update_data(broadcast_audience=callback_data.audience)
    await callback.answer()
    await _edit(
        callback,
        "📢 <b>Ommaviy xabar</b>\n"
        f"Auditoriya: {texts.AUDIENCE_LABELS[callback_data.audience]}\n\n"
        "Yubormoqchi bo‘lgan xabaringizni yuboring — matn, rasm, video, fayl yoki ovozli xabar "
        "(albom emas, bitta xabar). U foydalanuvchilarga aynan shu ko‘rinishda yetkaziladi.\n\n"
        "/cancel — bekor qilish",
        ui.back_home(),
    )


@router.message(Admin.broadcast_message, F.chat.type == ChatType.PRIVATE, not_command)
async def got_broadcast_message(message: Message, db: Database, state: FSMContext):
    audience = (await state.get_data()).get("broadcast_audience", "all")
    count = len(await db.audience_ids(audience))
    await state.update_data(broadcast_chat_id=message.chat.id, broadcast_msg_id=message.message_id)
    await state.set_state(Admin.broadcast_confirm)
    await message.reply(
        f"Yuqoridagi xabar <b>{count}</b> ta foydalanuvchiga yuboriladi "
        f"({texts.AUDIENCE_LABELS[audience]}). Tasdiqlaysizmi?",
        reply_markup=ui.broadcast_confirm(),
    )


@router.message(Admin.broadcast_confirm, not_command)
async def need_broadcast_confirm(message: Message):
    await message.answer("Iltimos, «🚀 Yuborish» yoki «❌ Bekor qilish» tugmasini bosing (/cancel — bekor qilish).")


@router.callback_query(Admin.broadcast_confirm, ui.Broadcast.filter(F.action == "send"))
async def on_broadcast_send(
    callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext, broadcaster: Broadcaster
):
    data = await state.get_data()
    await state.set_state(None)
    if broadcaster.running:
        await callback.answer("Boshqa tarqatma hali tugamagan", show_alert=True)
        return

    admin_id = callback.from_user.id
    chat_id, msg_id = data["broadcast_chat_id"], data["broadcast_msg_id"]

    async def on_done(job: BroadcastJob) -> None:
        await bot.send_message(admin_id, ui.job_text(job))

    await broadcaster.start(
        data["broadcast_audience"],
        lambda user_id: bot.copy_message(user_id, chat_id, msg_id),
        started_by=f"bot:{admin_id}",
        on_done=on_done,
    )
    await callback.answer("🚀 Tarqatma boshlandi")
    await _edit(callback, *await ui.broadcast_menu(db, broadcaster))


@router.callback_query(ui.Broadcast.filter(F.action == "cancel"))
async def on_broadcast_cancel(callback: CallbackQuery, db: Database, state: FSMContext):
    await state.set_state(None)
    await callback.answer("Bekor qilindi")
    await _edit(callback, *await ui.home(db))


@router.callback_query(ui.Broadcast.filter(F.action == "stop"))
async def on_broadcast_stop(callback: CallbackQuery, db: Database, broadcaster: Broadcaster):
    broadcaster.cancel()
    await callback.answer("⛔ To‘xtatilmoqda...")
    await _edit(callback, *await ui.broadcast_menu(db, broadcaster))
