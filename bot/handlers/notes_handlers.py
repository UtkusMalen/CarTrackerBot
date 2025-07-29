# bot/handlers/notes_handlers.py
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.database.models import Car, Note
from bot.fsm.notes import NotesFSM
from bot.keyboards.inline import get_notes_keyboard, get_delete_notes_keyboard, get_back_keyboard
from bot.utils.text_manager import get_text

router = Router()

async def format_notes_text(car_id: int, car_name: str) -> str:
    notes = await Note.get_notes_for_car(car_id)
    header = get_text('notes.header', car_name=car_name)
    if not notes:
        return f"{header}\n\n{get_text('notes.no_notes')}"

    notes_list = [get_text('notes.note_line', date=date.replace('-', '.'), text=text) for _, text, date in notes]
    return f"{header}\n\n" + "\n\n".join(notes_list)

async def show_notes(message: Message, user_id: int, edit: bool = True):
    car = await Car.get_active_car(user_id)
    if not car:
        await message.edit_text(get_text('main_menu.add_car_first'))
        return

    text = await format_notes_text(car[0], car[2])
    if edit:
        await message.edit_text(text, reply_markup=get_notes_keyboard())
    else:
        await message.answer(text, reply_markup=get_notes_keyboard())

@router.callback_query(F.data == "show_notes")
async def show_notes_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_notes(callback.message, callback.from_user.id)
    await callback.answer()

@router.callback_query(F.data == "add_note")
async def add_note_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(NotesFSM.add_note)
    await callback.message.edit_text(get_text('notes.add_note_prompt'),reply_markup=get_back_keyboard("show_notes"))
    await state.update_data(prompt_message_id=callback.message.message_id)
    await callback.answer()

@router.message(NotesFSM.add_note)
async def add_note_process(message: Message, state: FSMContext, bot: Bot):
    car = await Car.get_active_car(message.from_user.id)
    if not car:
        await state.clear()
        return

    await Note.add_note(car[0], message.text)

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    await state.clear()
    await message.delete()

    if prompt_message_id:
        try:
            new_text = await format_notes_text(car[0], car[2])
            await bot.edit_message_text(
                text=new_text,
                chat_id=message.chat.id,
                message_id=prompt_message_id,
                reply_markup=get_notes_keyboard()
            )
        except TelegramBadRequest as e:
            logger.error(f"Failed to edit notes message: {e}")
            await show_notes(message, message.from_user.id, edit=False)
    else:
        await show_notes(message, message.from_user.id, edit=False)

@router.callback_query(F.data == "delete_note_start")
async def delete_note_start(callback: CallbackQuery):
    car = await Car.get_active_car(callback.from_user.id)
    notes = await Note.get_notes_for_car(car[0])
    if not notes:
        await callback.answer(get_text('notes.no_notes_to_delete'), show_alert=True)
        return

    await callback.message.edit_text(
        get_text('notes.delete_prompt'),
        reply_markup=get_delete_notes_keyboard(notes)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_note_confirm:"))
async def delete_note_process(callback: CallbackQuery):
    note_id = int(callback.data.split(":")[1])
    await Note.delete_note(note_id)
    await show_notes(callback.message, callback.from_user.id)
    await callback.answer(get_text('notes.note_deleted'), show_alert=True)