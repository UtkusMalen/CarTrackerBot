import math

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.database.models import Car, Note
from bot.fsm.notes import NotesFSM
from bot.keyboards.inline import get_notes_keyboard, get_delete_notes_keyboard, get_back_keyboard, \
    get_pin_notes_keyboard
from bot.utils.text_manager import get_text

router = Router()
NOTES_PER_PAGE = 10

async def format_notes_text(notes: list, car_name: str, page: int, total_pages: int) -> str:
    header = get_text('notes.header', car_name=car_name)
    if not notes:
        return f"{header}\n\n{get_text('notes.no_notes')}"

    notes_list = []

    for _, text, date, is_pinned in notes:
        pin_emoji = "📌" if is_pinned else ""
        note_line = get_text('notes.note_line', date=date.replace('-', '.'), text=text)
        notes_list.append(f"{pin_emoji} {note_line}")

    notes_section = "\n\n".join(notes_list)
    page_footer = f"\n\nСтраница {page} из {total_pages}" if total_pages > 1 else ""

    return f"{header}\n\n{notes_section}{page_footer}"

async def show_notes(message: Message, user_id: int, page: int = 1, edit: bool = True):
    logger.debug(f"User {user_id} is viewing notes, page {page}.")
    car = await Car.get_active_car(user_id)
    if not car:
        logger.warning(f"User {user_id} tried to view notes but has no active car.")
        await message.edit_text(get_text('main_menu.add_car_first'))
        return

    car_id, _, car_name, *_ = car
    total_notes = await Note.get_notes_count_for_car(car_id)
    total_pages = math.ceil(total_notes / NOTES_PER_PAGE) if total_notes > 0 else 1
    page = max(1, min(page, total_pages))

    notes = await Note.get_notes_for_car_paginated(car_id, page, NOTES_PER_PAGE)
    text = await format_notes_text(notes, car_name, page, total_pages)
    keyboard = get_notes_keyboard(page, total_pages)

    if edit:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            pass
    else:
        await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.in_({"show_notes", "show_notes_page:1"}))
async def show_notes_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    logger.info(f"User {callback.from_user.id} requested to see notes via callback (initial page).")
    await show_notes(callback.message, callback.from_user.id, page=1)
    await callback.answer()

@router.callback_query(F.data.startswith("show_notes_page:"))
async def show_notes_page_callback(callback: CallbackQuery, state: FSMContext):
    """ Handler for returning to a specific page, e.g., from note deletion """
    await state.clear()
    page = int(callback.data.split(":")[1])
    logger.info(f"User {callback.from_user.id} returning to notes page {page}.")
    await show_notes(callback.message, callback.from_user.id, page=page)
    await callback.answer()

@router.callback_query(F.data.startswith("notes_page:"))
async def paginate_notes(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    logger.debug(f"User {callback.from_user.id} paginating notes to page {page}.")
    await show_notes(callback.message, callback.from_user.id, page=page)
    await callback.answer()

@router.callback_query(F.data == "add_note")
async def add_note_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started adding a note.")
    await state.set_state(NotesFSM.add_note)
    await callback.message.edit_text(get_text('notes.add_note_prompt'), reply_markup=get_back_keyboard("show_notes_page:1"))
    await state.update_data(prompt_message_id=callback.message.message_id)
    await callback.answer()

@router.message(NotesFSM.add_note)
async def add_note_process(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} sent text for a new note.")
    car = await Car.get_active_car(user_id)
    if not car:
        await state.clear()
        return

    await Note.add_note(car[0], message.text)
    logger.success(f"User {user_id} successfully added a new note for car {car[0]}.")

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    await state.clear()
    # Delete the user's message that contained the note text
    await message.delete()

    # Now, edit the original prompt message to show the updated notes list
    if prompt_message_id:
        # Generate the content for the first page of notes
        car_id, _, car_name, *_ = car
        total_notes = await Note.get_notes_count_for_car(car_id)
        total_pages = math.ceil(total_notes / NOTES_PER_PAGE) if total_notes > 0 else 1
        page = 1
        notes = await Note.get_notes_for_car_paginated(car_id, page, NOTES_PER_PAGE)
        text = await format_notes_text(notes, car_name, page, total_pages)
        keyboard = get_notes_keyboard(page, total_pages)

        try:
            # Directly edit the prompt message
            await bot.edit_message_text(
                text=text,
                chat_id=message.chat.id,
                message_id=prompt_message_id,
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            logger.error(f"Failed to edit notes prompt message {prompt_message_id}: {e}. Sending new message.")
            # If editing fails, delete the prompt and send a new message instead.
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
            except TelegramBadRequest:
                pass  # Message might already be gone
            await bot.send_message(message.chat.id, text, reply_markup=keyboard)
    else:
        # Fallback if the prompt message ID was lost for some reason
        await show_notes(message, user_id, page=1, edit=False)


@router.callback_query(F.data.startswith("delete_note_start:"))
async def delete_note_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    current_page = int(callback.data.split(":")[1])
    logger.info(f"User {user_id} started deleting a note from page {current_page}.")
    car = await Car.get_active_car(user_id)

    notes_on_page = await Note.get_notes_for_car_paginated(car[0], page=current_page, page_size=NOTES_PER_PAGE)

    if not notes_on_page:
        await callback.answer(get_text('notes.no_notes_to_delete'), show_alert=True)
        return

    await callback.message.edit_text(
        get_text('notes.delete_prompt'),
        reply_markup=get_delete_notes_keyboard(notes_on_page, page=current_page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_note_confirm:"))
async def delete_note_process(callback: CallbackQuery):
    user_id = callback.from_user.id
    _, note_id, current_page = callback.data.split(":")
    note_id, current_page = int(note_id), int(current_page)

    logger.info(f"User {user_id} confirmed deletion of note {note_id}.")
    await Note.delete_note(note_id)

    await show_notes(callback.message, user_id, page=current_page)
    await callback.answer(get_text('notes.note_deleted'), show_alert=True)

@router.callback_query(F.data.startswith("pin_note_start:"))
async def pin_note_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    current_page = int(callback.data.split(":")[1])
    logger.info(f"User {user_id} started pinning a note from page {current_page}.")
    car = await Car.get_active_car(user_id)

    notes_on_page = await Note.get_notes_for_car_paginated(car[0], page=current_page, page_size=NOTES_PER_PAGE)

    if not notes_on_page:
        await callback.answer(get_text('notes.no_notes_to_pin'), show_alert=True)
        return

    await callback.message.edit_text(
        get_text('notes.pin_prompt'),
        reply_markup=get_pin_notes_keyboard(notes_on_page, page=current_page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pin_note_confirm:"))
async def pin_note_process(callback: CallbackQuery):
    user_id = callback.from_user.id
    _, note_id, current_page = callback.data.split(":")
    note_id, current_page = int(note_id), int(current_page)

    logger.info(f"User {user_id} confirmed to pin note {note_id}.")
    await Note.toggle_pin_note(note_id)

    await show_notes(callback.message, user_id, page=current_page)
    await callback.answer(get_text('notes.note_pin_toggled'), show_alert=True)