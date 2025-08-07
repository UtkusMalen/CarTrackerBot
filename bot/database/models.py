from sqlite3 import Row

import aiosqlite
from typing import Optional, Tuple, Set, Dict, Any, List

from loguru import logger


class User:
    @staticmethod
    async def create_user(user_id: int, username: str, first_name: str, referrer_id: Optional[int] = None) -> None:
        async with aiosqlite.connect("bot_database.db") as db:
            cursor =await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)",
                (user_id, username, first_name, referrer_id),
            )
            await db.commit()
            if cursor.rowcount > 0:
                logger.info(f"New user {user_id} ({username}) created. Referrer: {referrer_id}")
            else:
                logger.debug(f"User {user_id} ({username}) already exists.")

    @staticmethod
    async def get_user(user_id: int) -> Optional[tuple]:
        logger.debug(f"Fetching user data for user_id: {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return await cursor.fetchone()

    @staticmethod
    async def get_user_rank(user_id: int) -> int:
        """Calculates and returns the rank of the user."""
        logger.debug(f"Calculating rank for user_id: {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            query = """
                SELECT rank
                FROM (
                    SELECT
                        user_id,
                        ROW_NUMBER() OVER (ORDER BY balance_nuts DESC, user_id ASC) as rank
                    FROM users
                )
                WHERE user_id = ?
            """
            cursor = await db.execute(query, (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def get_user_balance_by_rank(rank: int) -> Optional[int]:
        """Fetches the balance of a user by their rank."""
        if rank <= 1:
            return None

        offset = rank - 2
        logger.debug(f"Fetching balance for user at rank {rank - 1} (offset {offset})")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                """
                SELECT balance_nuts FROM users
                ORDER BY balance_nuts DESC, user_id ASC
                LIMIT 1 OFFSET ?
                """,
                (offset,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    @staticmethod
    async def get_total_users_count() -> int:
        """Counts the total number of registered users."""
        logger.debug("Counting total users")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT COUNT(user_id) FROM users")
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def update_balance(db: aiosqlite.Connection, user_id: int, amount: int):
        """Helper to update a user's balance."""
        logger.info(f"Updating balance for user {user_id} by {amount}")
        await db.execute(
            "UPDATE users SET balance_nuts = balance_nuts + ? WHERE user_id = ?",
            (amount, user_id)
        )

    @staticmethod
    async def get_active_car_id(user_id: int) -> Optional[int]:
        logger.debug(f"Fetching active_car_id for user_id: {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT active_car_id FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    @staticmethod
    async def set_active_car(user_id: int, car_id: int) -> None:
        logger.info(f"Setting active car for user {user_id} to car_id {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("UPDATE users SET active_car_id = ? WHERE user_id = ?", (car_id, user_id))
            await db.commit()

    @staticmethod
    async def get_all_user_ids() -> list[int]:
        """Returns a list of all user IDs."""
        logger.debug("Fetching all user IDs for mailing.")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    @staticmethod
    async def set_mileage_reminder_period(user_id: int, days: int) -> None:
        """Sets the custom mileage update reminder period for the user."""
        logger.info(f"User {user_id} is setting mileage reminder period to {days} days.")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE users SET mileage_reminder_period = ? WHERE user_id = ?",
                (days, user_id)
            )
            await db.commit()

    @staticmethod
    async def get_top_users_paginated(page: int, page_size: int = 10) -> list[Tuple]:
        """Fetches a paginated list of top users ordered by balance."""
        offset = (page - 1) * page_size
        logger.debug(f"Fetching top users page {page} (offset {offset}, size {page_size})")

        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                """
                SELECT user_id, first_name, username, balance_nuts
                FROM users
                ORDER BY balance_nuts DESC, user_id ASC
                LIMIT ? OFFSET ?
                """,
                (page_size, offset)
            )
            return await cursor.fetchall()

    @staticmethod
    async def count_referrals(user_id: int) -> int:
        logger.debug(f"Counting referrals for user_id: {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT COUNT(user_id) FROM users WHERE referrer_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0

class Car:
    @staticmethod
    async def add_car(user_id: int, name: str, mileage: Optional[int]) -> int:
        logger.info(f"User {user_id} is adding a new car: Name='{name}', Mileage={mileage}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                """
                INSERT INTO cars (user_id, name, mileage)
                VALUES (?, ?, ?)
                """,
                (user_id, name, mileage)
            )
            await db.commit()
            logger.success(f"Car '{name}' added for user {user_id} with ID {cursor.lastrowid}")
            return cursor.lastrowid

    @staticmethod
    async def get_active_car(user_id: int) -> Optional[aiosqlite.Row]:
        logger.debug(f"Fetching active car for user_id: {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT active_car_id FROM users WHERE user_id = ?", (user_id,))
            active_id_row = await cursor.fetchone()
            active_id = active_id_row['active_car_id'] if active_id_row else None

            if active_id:
                car_cursor = await db.execute("SELECT * FROM cars WHERE car_id = ?", (active_id,))
                return await car_cursor.fetchone()
            else:
                logger.debug(f"No active car set for user {user_id}. Trying to find the latest one.")
                latest_car_cursor = await db.execute("SELECT * FROM cars WHERE user_id = ? ORDER BY car_id DESC LIMIT 1", (user_id,))
                latest_car = await latest_car_cursor.fetchone()
                if latest_car:
                    logger.info(f"Auto-setting latest car {latest_car['car_id']} as active for user {user_id}")
                    await db.execute("UPDATE users SET active_car_id = ? WHERE user_id = ?", (latest_car['car_id'], user_id))
                    await db.commit()
                    return latest_car
            return None

    @staticmethod
    async def get_all_cars_for_user(user_id: int) -> List[aiosqlite.Row]:
        logger.debug(f"Fetching all cars for user_id: {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM cars WHERE user_id = ? ORDER BY car_id",
            (user_id,))
            return await cursor.fetchall()

    @staticmethod
    async def car_exists_by_name(user_id: int, name: str) -> bool:
        """Checks if a car with the given name already exists for the user."""
        logger.debug(f"Checking if car with name '{name}' exists for user {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT 1 FROM cars WHERE user_id = ? AND name = ?",
                (user_id, name)
            )
            result = await cursor.fetchone()
            return result is not None

    @staticmethod
    async def update_mileage(car_id: int, new_mileage: int) -> None:
        logger.info(f"Updating mileage for car_id {car_id} to {new_mileage}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE cars SET mileage = ?, last_mileage_update_at = date('now') WHERE car_id = ?",
                (new_mileage, car_id)
            )
            await db.commit()

    @staticmethod
    async def snooze_mileage_update(car_id: int) -> None:
        """Resets the last update timestamp for a car to snooze the reminder"""
        logger.info(f"Snoozing mileage update reminder for car_id {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE cars SET last_mileage_update_at = date('now') WHERE car_id = ?",
                (car_id,)
            )
            await db.commit()

    @staticmethod
    async def get_cars_needing_mileage_update() -> list[Tuple]:
        logger.debug("Querying for cars that need a mileage update reminder.")
        async with aiosqlite.connect("bot_database.db") as db:
            query = """
                SELECT u.user_id, c.name, c.car_id
                FROM cars c
                JOIN users u ON c.user_id = u.user_id
                WHERE c.car_id = u.active_car_id
                    AND c.mileage IS NOT NULL
                    AND julianday('now') - julianday(c.last_mileage_update_at) >= 7
            """
            cursor = await db.execute(query)
            return await cursor.fetchall()

    @staticmethod
    async def delete_car(car_id: int) -> None:
        logger.info(f"Attempting to delete car with car_id: {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE users SET active_car_id = NULL WHERE active_car_id = ?",
                (car_id,)
            )
            await db.execute("DELETE FROM cars WHERE car_id = ?", (car_id,))
            await db.commit()
            logger.success(f"Successfully deleted car {car_id} and updated relevant users.")

    @staticmethod
    async def get_car_for_allowance_update(car_id: int) -> Optional[Tuple]:
        """Fetches the specific field needed for the allowance update."""
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT mileage, mileage_allowance, last_allowance_update_at FROM cars WHERE car_id = ?",
                (car_id,)
            )
            return await cursor.fetchone()

    @staticmethod
    async def update_mileage_and_allowance(car_id: int, new_mileage: int, new_allowance: int) -> None:
        """Atomically updates mileage, allowance and timestamp"""
        logger.info(f"Updating car {car_id}: new mileage {new_mileage}, new allowance {new_allowance}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                """
                UPDATE cars
                SET
                    mileage = ?,
                    mileage_allowance = ?,
                    last_mileage_update_at = date('now'),
                    last_allowance_update_at = date('now')
                WHERE car_id = ?
                """,
                (new_mileage, new_allowance, car_id)
            )
            await db.commit()

    @staticmethod
    async def update_car_details(car_id: int, details: Dict[str, Any]) -> None:
        """Updates the details of a car."""
        if not details:
            return

        # Build the SET part of the SQL query
        set_clause = ", ".join([f"{key} = ?" for key in details.keys()])
        values = list(details.values())
        values.append(car_id)

        query = f"UPDATE cars SET {set_clause} WHERE car_id = ?"

        logger.info(f"Updating car details for car_id {car_id}: {details}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(query, tuple(values))
            await db.commit()


class Note:
    @staticmethod
    async def add_note(car_id: int, text: str) -> None:
        logger.info(f"Adding new note for car_id {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("INSERT INTO notes (car_id, text) VALUES (?, ?)", (car_id, text))
            await db.commit()

    @staticmethod
    async def get_notes_for_car_paginated(car_id: int, page: int, page_size: int = 10) -> list[Tuple]:
        offset = (page - 1) * page_size
        logger.debug(f"Fetching notes for car_id {car_id}, page {page} (offset {offset}, size {page_size})")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT note_id, text, created_at, is_pinned FROM notes WHERE car_id = ? ORDER BY is_pinned DESC, created_at DESC LIMIT ? OFFSET ?", (car_id, page_size, offset))
            return await cursor.fetchall()

    @staticmethod
    async def get_notes_count_for_car(car_id: int) -> int:
        logger.debug(f"Counting notes for car_id {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT COUNT(*) FROM notes WHERE car_id = ?", (car_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def delete_note(note_id: int) -> None:
        logger.info(f"Deleting note with note_id {note_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
            await db.commit()

    @staticmethod
    async def toggle_pin_note(note_id: int) -> None:
        logger.info(f"Toggling pin status for note with note_id {note_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE notes SET is_pinned = NOT is_pinned WHERE note_id = ?",
                (note_id,)
            )
            await db.commit()

class Reminder:
    @staticmethod
    async def add_reminder(car_id: int, name: str, type: str, interval_km: Optional[int] = None, last_reset_mileage: Optional[int] = None, interval_days: Optional[int] = None, last_reset_date: Optional[str] = None, target_mileage: Optional[int] = None, target_date: Optional[str] = None) -> int:
        logger.info(f"Adding reminder '{name}' of type '{type}' for car_id {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                """
                INSERT INTO reminders 
                (car_id, name, type, interval_km, last_reset_mileage, interval_days, last_reset_date, target_mileage, target_date, notification_schedule) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (car_id, name, type, interval_km, last_reset_mileage, interval_days, last_reset_date, target_mileage, target_date, "7,3,1")
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def get_reminders_for_car(car_id: int) -> List[aiosqlite.Row]:
        logger.debug(f"Fetching reminders for car_id: {car_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM reminders WHERE car_id = ?",
                (car_id,)
            )
            return await cursor.fetchall()

    @staticmethod
    async def get_reminder(reminder_id: int) -> Optional[aiosqlite.Row]:
        logger.debug(f"Fetching reminder data for reminder_id: {reminder_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM reminders WHERE reminder_id = ?", (reminder_id,))
            return await cursor.fetchone()

    @staticmethod
    async def get_reminders_for_notification() -> List[aiosqlite.Row]:
        logger.debug("Querying for time-based reminders for notification check.")
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT r.reminder_id, r.name, c.user_id, c.name as car_name,
                    r.last_reset_date, r.interval_days, r.notification_schedule
                FROM reminders r
                JOIN cars c ON r.car_id = c.car_id
                WHERE r.type = 'time'
                    AND r.last_reset_date IS NOT NULL
                    AND r.interval_days IS NOT NULL
                    AND r.notification_schedule IS NOT NULL
                    AND r.notification_schedule != ''
            """
            cursor = await db.execute(query)
            return await cursor.fetchall()

    @staticmethod
    async def reset_mileage_reminder(reminder_id: int, current_mileage: int) -> None:
        logger.info(f"Resetting mileage reminder {reminder_id} at mileage {current_mileage}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                "UPDATE reminders SET last_reset_mileage = ? WHERE reminder_id = ?",
                (current_mileage, reminder_id)
            )
            await db.commit()

    @staticmethod
    async def reset_time_reminder(reminder_id: int, start_date: str, repeat: bool = False) -> None:
        logger.info(f"Resetting time reminder {reminder_id} with start date {start_date}. Repeat: {repeat}")
        async with aiosqlite.connect("bot_database.db") as db:
            if repeat:
                query = """
                    UPDATE reminders
                    SET last_reset_date = date(last_reset_date, '+' || interval_days || ' days')
                    WHERE reminder_id = ? AND last_reset_date IS NOT NULL AND interval_days IS NOT NULL
                """
                await db.execute(query, (reminder_id,))
            else:
                await db.execute(
                    "UPDATE reminders SET last_reset_date = ? WHERE reminder_id = ?",
                    (start_date, reminder_id)
                )
            await db.commit()

    @staticmethod
    async def update_reminder_details(reminder_id: int, details: Dict[str, Any]) -> None:
        """Updates the details of a reminder."""
        if not details:
            return

        set_clause = ", ".join([f"{key} = ?" for key in details.keys()])
        values = list(details.values())
        values.append(reminder_id)

        query = f"UPDATE reminders SET {set_clause} WHERE reminder_id = ?"

        logger.info(f"Updating reminder {reminder_id} with {details}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(query, tuple(values))
            await db.commit()

    @staticmethod
    async def delete_reminder(reminder_id: int) -> None:
        logger.info(f"Deleting reminder with reminder_id {reminder_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("DELETE FROM reminders WHERE reminder_id = ?", (reminder_id,))
            await db.commit()

    @staticmethod
    async def toggle_reminder_repeat(reminder_id: int) -> bool:
        logger.info(f"Toggling repeat for reminder with reminder_id {reminder_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute("SELECT is_repeating FROM reminders WHERE reminder_id = ?", (reminder_id,))
            row = await cursor.fetchone()
            if not row:
                logger.warning(f"Toggle repeat failed: Reminder {reminder_id} not found")
                return False

            new_state = not (row[0] or False)
            await db.execute("UPDATE reminders SET is_repeating = ? WHERE reminder_id = ?", (new_state, reminder_id))
            await db.commit()
            logger.success(f"Toggled repeat state for reminder {reminder_id} to {new_state}.")
            return new_state

    @staticmethod
    async def get_expired_repeating_reminders() -> List[Row]:
        """Fetches all time-based reminders that are set to repeat and have expired."""
        logger.debug("Querying for expired repeating reminders.")
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = Row
            query = """
                SELECT r.reminder_id, r.name, c.user_id, c.name as car_name
                FROM reminders r
                JOIN cars c ON r.car_id = c.car_id
                WHERE r.type = 'time'
                  AND r.is_repeating = TRUE
                  AND r.last_reset_date IS NOT NULL
                  AND r.interval_days IS NOT NULL
                  AND julianday('now') - julianday(r.last_reset_date) >= r.interval_days;
            """
            cursor = await db.execute(query)
            return await cursor.fetchall()

class Transaction:
    @staticmethod
    async def add_transaction(user_id: int, amount: int, description: str) -> None:
        """Adds a transaction and updates the user's balance."""
        if amount == 0:
            return

        log_verb = "Spending" if amount < 0 else "Adding"
        logger.info(f"{log_verb} transaction for user {user_id}: {amount} nuts for '{description}'")
        async with aiosqlite.connect("bot_database.db") as db:
            async with db.execute("BEGIN"):
                await db.execute(
                    "INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)",
                    (user_id, amount, description)
                )
                await db.execute(
                    "UPDATE users SET balance_nuts = balance_nuts + ? WHERE user_id = ?",
                    (amount, user_id)
                )
            await db.commit()

    @staticmethod
    async def has_received_reward(user_id: int, description: str) -> bool:
        """Checks if a user has already received a reward for a specific action."""
        logger.debug(f"Checking if user {user_id} has already received reward for '{description}'")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT 1 FROM transactions WHERE user_id = ? AND description = ? LIMIT 1",
                (user_id, description)
            )
            return bool(await cursor.fetchone())

    @staticmethod
    async def get_all_reward_descriptions(user_id: int) -> Set[str]:
        """Fetches a set of unique reward descriptions a user has received."""
        logger.debug(f"Fetching all unique reward descriptions for user {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT DISTINCT description FROM transactions WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    @staticmethod
    async def get_transactions_paginated(user_id: int, page: int, page_size: int = 10) -> list[Tuple]:
        """Fetches a paginated list of all transactions for a user."""
        offset = (page - 1) * page_size
        logger.debug(f"Fetching transactions for user {user_id}, page {page}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT amount, description, created_at FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset)
            )
            return await cursor.fetchall()

    @staticmethod
    async def get_transactions_count(user_id: int) -> int:
        """Counts the total number of transactions for a user."""
        logger.debug(f"Counting total transactions for user {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT COUNT(transaction_id) FROM transactions WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    @staticmethod
    async def get_latest_transactions(user_id: int, limit: int = 3) -> list[Tuple]:
        """Fetches the N latest transactions for a user."""
        logger.debug(f"Fetching last {limit} transactions for user {user_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "SELECT amount, description FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            return await cursor.fetchall()

class ExpenseCategory:
    @staticmethod
    async def get_categories_for_user(user_id: int) -> List[Row]:
        """Fetches default and user-specific categories, ordered."""
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT category_id, name FROM expense_categories
                WHERE is_default = TRUE OR user_id = ?
                ORDER BY is_default DESC, name ASC
                """,
                (user_id,)
            )
            return await cursor.fetchall()

    @staticmethod
    async def add_category(user_id: int, name: str) -> int:
        """Adds a new custom category for a user."""
        async with aiosqlite.connect("bot_database.db") as db:
            cursor = await db.execute(
                "INSERT INTO expense_categories (user_id, name) VALUES (?, ?)",
                (user_id, name)
            )
            await db.commit()
            return cursor.lastrowid

    @staticmethod
    async def find_category_by_name(user_id: int, name: str) -> Optional[Row]:
        """Finds a category by name, checking user-specific then defaults."""
        async with aiosqlite.connect("bot_database.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT category_id FROM expense_categories
                WHERE (user_id = ? AND name = ?) OR (is_default = TRUE AND name = ?)
                ORDER BY user_id DESC
                LIMIT 1
                """,
                (user_id, name, name)
            )
            return await cursor.fetchone()

class Expense:
    @staticmethod
    async def add_expense(car_id: int, category_id: int, amount: float, mileage: Optional[int], description: Optional[str], date: str) -> None:
        """Adds a new expense record."""
        logger.info(f"Adding expense for car {car_id}: amount={amount}, category={category_id}")
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute(
                """
                INSERT INTO expenses (car_id, category_id, amount, mileage, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (car_id, category_id, amount, mileage, description, date)
            )
            await db.commit()