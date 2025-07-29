import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database.models import Car
from bot.utils.text_manager import get_text

router = Router()

@router.callback_query(F.data.startswith("snooze_mileage_reminder:"))
async def snooze_reminder(callback: CallbackQuery):
    car_id = int(callback.data.split(":")[1])
    await Car.snooze_mileage_update(car_id)

    await callback.message.edit_text(get_text('mileage_update_reminder.snoozed_feedback'))
    await callback.answer()

    await asyncio.sleep(5)
    await callback.message.delete()