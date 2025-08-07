import aiosqlite
from loguru import logger
from typing import List


class DatabaseManager:
    """
    Manages the bot's SQLite database, including initialization,
    schema creation, and data migrations.
    """
    SCHEMA_SQL = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            balance_nuts INTEGER DEFAULT 0, active_car_id INTEGER,
            mileage_reminder_period INTEGER DEFAULT 1, referrer_id INTEGER
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS cars (
            car_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, mileage INTEGER,
            last_mileage_update_at DATE DEFAULT (date('now')), make TEXT, model TEXT, year INTEGER,
            engine_model TEXT, engine_volume REAL, tank_volume REAL, fuel_type TEXT, power TEXT, transmission TEXT,
            drive_type TEXT, body_type TEXT, mileage_allowance INTEGER DEFAULT 1000,
            last_allowance_update_at DATE DEFAULT (date('now')),
            insurance_start_date DATE, insurance_duration_days INTEGER,
            insurance_migrated BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT, car_id INTEGER, text TEXT NOT NULL,
            created_at DATE DEFAULT (date('now')),
            FOREIGN KEY (car_id) REFERENCES cars (car_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id INTEGER PRIMARY KEY AUTOINCREMENT, car_id INTEGER, name TEXT NOT NULL,
            type TEXT,
            interval_km INTEGER, last_reset_mileage INTEGER,
            interval_days INTEGER, last_reset_date DATE,
            is_repeating BOOLEAN DEFAULT FALSE,
            target_mileage INTEGER,
            target_date DATE,
            notification_schedule TEXT,
            FOREIGN KEY (car_id) REFERENCES cars (car_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER NOT NULL,
            description TEXT, created_at DATETIME DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        """
    ]

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self):
        """
        The main entry point to connect to the DB, run all necessary migrations,
        and ensure the schema is up-to-date.
        """
        logger.info("Starting database initialization process...")
        async with aiosqlite.connect(self.db_path) as db:
            # The order of operations is crucial.
            # 1. Run critical schema fixes that must happen before anything else.
            await self._migrate_reminders_schema_fix(db)

            # 2. Create the base schema. This is idempotent and safe to run every time.
            await self._execute_schema(db)

            # 3. Add new columns to existing tables.
            await self._migrate_add_new_columns(db)

            # 4. Perform data migrations (moving data between tables).
            await self._migrate_insurance_data(db)

            await db.commit()
        logger.success("Database initialization and migration checks complete.")

    async def _execute_schema(self, db: aiosqlite.Connection):
        """Ensures all tables exist based on the defined schema."""
        logger.info("Ensuring base schema exists...")
        for statement in self.SCHEMA_SQL:
            await db.execute(statement)
        logger.success("Base schema check complete.")

    async def _get_table_columns(self, db: aiosqlite.Connection, table_name: str) -> List[str]:
        """A helper to get a list of column names for a given table."""
        try:
            cursor = await db.execute(f"PRAGMA table_info({table_name})")
            return [row[1] for row in await cursor.fetchall()]
        except aiosqlite.OperationalError:
            return []

    async def _reminders_has_not_null_issue(self, db: aiosqlite.Connection) -> bool:
        """Checks for the specific legacy schema issue in the 'reminders' table."""
        try:
            cursor = await db.execute("PRAGMA table_info(reminders)")
            for row in await cursor.fetchall():
                # row[1] is column name, row[3] is the 'notnull' flag
                if row[1] == 'interval_km' and row[3] == 1:
                    return True
            return False
        except aiosqlite.OperationalError:
            return False

    async def _migrate_reminders_schema_fix(self, db: aiosqlite.Connection):
        """Rebuilds the 'reminders' table if the flawed NOT NULL constraint exists."""
        if not await self._reminders_has_not_null_issue(db):
            return

        logger.warning(
            "Migration: Detected flawed schema with 'NOT NULL' on reminders.interval_km. Rebuilding table...")

        temp_table_name = "reminders_old_migration_final"
        await db.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
        await db.execute(f"ALTER TABLE reminders RENAME TO {temp_table_name}")

        # Re-create the table using the correct schema from the class definition
        await db.execute(self.SCHEMA_SQL[3])

        await db.execute(
            f"""
            INSERT INTO reminders (reminder_id, car_id, name, interval_km, last_reset_mileage)
            SELECT reminder_id, car_id, name, interval_km, last_reset_mileage
            FROM {temp_table_name};
            """
        )

        await db.execute(f"DROP TABLE {temp_table_name}")
        logger.success("Migration: 'reminders' table successfully rebuilt.")

    async def _migrate_add_new_columns(self, db: aiosqlite.Connection):
        """Adds all missing columns to tables in an idempotent way."""
        logger.info("Checking for missing columns...")

        # Add columns to 'reminders' table
        reminders_cols = await self._get_table_columns(db, 'reminders')
        new_reminder_cols = {
            'type': 'TEXT', 'interval_days': 'INTEGER', 'last_reset_date': 'DATE',
            'is_repeating': 'BOOLEAN DEFAULT FALSE', 'target_mileage': 'INTEGER',
            'target_date': 'DATE', 'notification_schedule': 'TEXT'
        }

        for col, col_type in new_reminder_cols.items():
            if col not in reminders_cols:
                logger.info(f"Migration: Adding column '{col}' to 'reminders'.")
                if "DEFAULT" in col_type.upper():
                    await db.execute(f"ALTER TABLE reminders ADD COLUMN {col} {col_type}")
                else:
                    await db.execute(f"ALTER TABLE reminders ADD COLUMN {col} {col_type}")

        # Set a default type for old reminders to prevent issues
        await db.execute("UPDATE reminders SET type = 'mileage' WHERE type IS NULL")

        notes_cols = await self._get_table_columns(db, 'notes')
        if 'is_pinned' not in notes_cols:
            logger.info("Migration: Adding column 'is_pinned' to 'notes'.")
            await db.execute("ALTER TABLE notes ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE")

        # Add 'insurance_migrated' flag to 'cars' table
        cars_cols = await self._get_table_columns(db, 'cars')
        if 'insurance_migrated' not in cars_cols:
            logger.info("Migration: Adding column 'insurance_migrated' to 'cars'.")
            await db.execute("ALTER TABLE cars ADD COLUMN insurance_migrated BOOLEAN DEFAULT FALSE")

        if 'tank_volume' not in cars_cols:
            logger.info("Migration: Adding column 'tank_volume' to 'cars'.")
            await db.execute("ALTER TABLE cars ADD COLUMN tank_volume REAL")

    async def _migrate_insurance_data(self, db: aiosqlite.Connection):
        """Migrates legacy insurance data from the 'cars' table to the 'reminders' table."""
        logger.info("Checking for insurance data to migrate from 'cars' to 'reminders'...")
        cursor = await db.execute(
            """
            SELECT car_id, insurance_start_date, insurance_duration_days
            FROM cars WHERE insurance_start_date IS NOT NULL 
              AND insurance_duration_days IS NOT NULL AND insurance_migrated = FALSE
            """
        )
        cars_to_migrate = await cursor.fetchall()

        if not cars_to_migrate:
            logger.info("No new insurance data found to migrate.")
            return

        logger.info(f"Migration: Found {len(cars_to_migrate)} cars with insurance data to migrate.")
        for car_id, start_date, duration_days in cars_to_migrate:
            # Check if an empty 'Страховой полис' reminder already exists
            rem_cursor = await db.execute(
                "SELECT reminder_id FROM reminders WHERE car_id = ? AND name = 'Страховой полис' AND interval_days IS NULL",
                (car_id,)
            )
            existing_empty_reminder = await rem_cursor.fetchone()

            if existing_empty_reminder:
                # If it exists, UPDATE it with the migrated data
                reminder_id = existing_empty_reminder[0]
                await db.execute(
                    "UPDATE reminders SET interval_days = ?, last_reset_date = ? WHERE reminder_id = ?",
                    (duration_days, start_date, reminder_id)
                )
            else:
                # Otherwise, INSERT a new one, ignoring if a configured one already exists
                await db.execute(
                    """
                    INSERT OR IGNORE INTO reminders (car_id, name, type, interval_days, last_reset_date)
                    VALUES (?, 'Страховой полис', 'time', ?, ?)
                    """,
                    (car_id, duration_days, start_date)
                )

            await db.execute("UPDATE cars SET insurance_migrated = TRUE WHERE car_id = ?", (car_id,))
        logger.success("Migration: Insurance data migration complete.")


async def init_db():
    """Initializes the database by calling the DatabaseManager."""
    manager = DatabaseManager("bot_database.db")
    await manager.initialize()