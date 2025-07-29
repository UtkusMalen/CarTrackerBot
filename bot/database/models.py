import aiosqlite
from typing import Optional, Tuple


class User:
    @staticmethod
    async def create_user(user_id: int, username: str, first_name: str) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            await db.commit()

    @staticmethod
    async def get_user(user_id: int) -> Optional[tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return await cursor.fetchone()

    @staticmethod
    async def get_active_car_id(user_id: int) -> Optional[int]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT active_car_id FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    @staticmethod
    async def set_active_car(user_id: int, car_id: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("UPDATE users SET active_car_id = ? WHERE user_id = ?", (car_id, user_id))
            await db.commit()

    @staticmethod
    async def get_all_user_ids() -> list[int]:
        """Returns a list of all user IDs."""
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    @staticmethod
    async def set_mileage_reminder_period(user_id: int, days: int) -> None:
        """Sets the custom mileage update reminder period for the user."""
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE users SET mileage_reminder_period = ? WHERE user_id = ?",
                (days, user_id)
            )
            await db.commit()

class Car:
    @staticmethod
    async def add_car(user_id: int, name: str, mileage: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor =await db.execute(
                """
                INSERT INTO cars (user_id, name, mileage)
                VALUES (?, ?, ?)
                """,
                (user_id, name, mileage)
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def get_active_car(user_id: int) -> Optional[tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT active_car_id FROM users WHERE user_id = ?", (user_id,))
            active_id_row = await cursor.fetchone()
            active_id = active_id_row[0] if active_id_row else None

            if active_id:
                car_cursor = await db.execute("SELECT * FROM cars WHERE car_id = ?", (active_id,))
                return await car_cursor.fetchone()
            else:
                latest_car_cursor = await db.execute("SELECT * FROM cars WHERE user_id = ? ORDER BY car_id DESC LIMIT 1", (user_id,))
                latest_car = await latest_car_cursor.fetchone()
                if latest_car:
                    await db.execute("UPDATE users SET active_car_id = ? WHERE user_id = ?", (latest_car[0], user_id))
                    await db.commit()
                    return latest_car
            return None

    @staticmethod
    async def get_all_cars_for_user(user_id: int) -> list[Tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT car_id, name, mileage FROM cars WHERE user_id = ? ORDER BY car_id", (user_id,))
            return await cursor.fetchall()

    @staticmethod
    async def car_exists_by_name(user_id: int, name: str) -> bool:
        """Checks if a car with the given name already exists for the user."""
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT 1 FROM cars WHERE user_id = ? AND name = ?",
                (user_id, name)
            )
            result = await cursor.fetchone()
            return result is not None

    @staticmethod
    async def update_mileage(car_id: int, new_mileage: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE cars SET mileage = ?, last_mileage_update_at = date('now') WHERE car_id = ?",
                (new_mileage, car_id)
            )
            await db.commit()

    @staticmethod
    async def snooze_mileage_update(car_id: int) -> None:
        """Resets the last update timestamp for a car to snooze the reminder"""
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE cars SET last_mileage_update_at = date('now') WHERE car_id = ?",
                (car_id,)
            )
            await db.commit()

    @staticmethod
    async def get_cars_needing_mileage_update() -> list[Tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            query = """
                SELECT u.user_id, c.name, c.car_id
                FROM cars c
                JOIN users u ON c.user_id = u.user_id
                WHERE c.car_id = u.active_car_id
                    AND julianday('now') - julianday(c.last_mileage_update_at) >= u.mileage_reminder_period
            """
            cursor = await db.execute(query)
            return await cursor.fetchall()

class Note:
    @staticmethod
    async def add_note(car_id: int, text: str) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("INSERT INTO notes (car_id, text) VALUES (?, ?)", (car_id, text))
            await db.commit()

    @staticmethod
    async def get_notes_for_car(car_id: int) -> list[Tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT note_id, text, created_at FROM notes WHERE car_id = ? ORDER BY created_at DESC", (car_id,))
            return await cursor.fetchall()

    @staticmethod
    async def delete_note(note_id: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
            await db.commit()

class Reminder:
    @staticmethod
    async def add_reminder(car_id: int, name: str, interval: int, last_reset: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "INSERT INTO reminders (car_id, name, interval_km, last_reset_mileage) VALUES (?, ?, ?, ?)",
                (car_id, name, interval, last_reset)
            )
            await db.commit()

    @staticmethod
    async def get_reminders_for_car(car_id: int) -> list[Tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT reminder_id, name, interval_km, last_reset_mileage FROM reminders WHERE car_id = ?",
                (car_id,)
            )
            return await cursor.fetchall()

    @staticmethod
    async def get_reminder(reminder_id: int) -> Optional[Tuple]:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT * FROM reminders WHERE reminder_id = ?", (reminder_id,))
            return await cursor.fetchone()

    @staticmethod
    async def reset_reminder(reminder_id: int, current_mileage: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE reminders SET last_reset_mileage = ? WHERE reminder_id = ?",
                (current_mileage, reminder_id)
            )
            await db.commit()

    @staticmethod
    async def update_interval(reminder_id: int, new_interval: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE reminders SET interval_km = ? WHERE reminder_id = ?",
                (new_interval, reminder_id)
            )
            await db.commit()

    @staticmethod
    async def delete_reminder(reminder_id: int) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("DELETE FROM reminders WHERE reminder_id = ?", (reminder_id,))
            await db.commit()