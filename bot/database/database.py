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
                mileage_reminder_period INTEGER DEFAULT 1,
                referrer_id INTEGER
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
                make TEXT,
                model TEXT,
                year INTEGER,
                engine_model TEXT,
                engine_volume REAL,
                fuel_type TEXT,
                power TEXT,
                transmission TEXT,
                drive_type TEXT,
                body_type TEXT,
                mileage_allowance INTEGER DEFAULT 1000,
                last_allowance_update_at DATE DEFAULT (date('now')),
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            );
            """
        )
        try:
            await db.execute("ALTER TABLE cars ADD COLUMN insurance_start_date DATE")
            logger.info("Column 'insurance_start_date' added to 'cars' table.")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        try:
            await db.execute("ALTER TABLE cars ADD COLUMN insurance_duration_days INTEGER")
            logger.info("Column 'insurance_duration_days' added to 'cars' table.")
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        await db.commit()
    logger.info("Database tables created or already exist.")