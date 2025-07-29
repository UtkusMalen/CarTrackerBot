import aiosqlite
from loguru import logger

async def init_db():
    """Initializes the database and creates tables if they don't exist."""
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance_nuts INTEGER DEFAULT 0,
                active_car_id INTEGER,
                mileage_reminder_period INTEGER DEFAULT 1
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cars (
                car_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                mileage INTEGER,
                last_mileage_update_at DATE DEFAULT (date('now')),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER,
                text TEXT NOT NULL,
                created_at DATE DEFAULT (date('now')),
                FOREIGN KEY (car_id) REFERENCES cars (car_id) ON DELETE CASCADE
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER,
                name TEXT NOT NULL,
                interval_km INTEGER NOT NULL,
                last_reset_mileage INTEGER NOT NULL,
                FOREIGN KEY (car_id) REFERENCES cars (car_id) ON DELETE CASCADE
            );
            """
        )
        await db.commit()
    logger.info("Database tables created or already exist.")