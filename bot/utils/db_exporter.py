import os
import csv
import zipfile
import asyncio
import aiosqlite
from datetime import datetime
from typing import Optional, List
from loguru import logger

DB_PATH = "bot_database.db"
DUMP_DIR = "db_dumps"

def _write_csv_sync(csv_path: str, headers: List[str], rows: List):
    try:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        logger.debug(f"Successfully wrote to {csv_path}")
    except Exception as e:
        logger.error(f"Failed to write to {csv_path}: {e}")
        raise

def _create_zip_sync(zip_path: str, files_to_zip: List[str]):
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in files_to_zip:
                zf.write(file_path, arcname=os.path.basename(file_path))
        logger.info(f"Successfully created {zip_path}")
    except Exception as e:
        logger.error(f"Failed to create {zip_path}: {e}")
        raise

async def create_db_dump_zip() -> Optional[str]:
    logger.info("Starting database export process...")
    os.makedirs(DUMP_DIR, exist_ok=True)
    csv_files = []

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = await cursor.fetchall()
            table_names = [table[0] for table in tables]
            logger.info(f"Found {len(table_names)} tables in the database: {', '.join(table_names)}")

            for table_name in table_names:
                csv_path = os.path.join(DUMP_DIR, f"{table_name}.csv")
                try:
                    data_cursor = await db.execute(f"SELECT * FROM {table_name}")
                    headers = [description[0] for description in data_cursor.description]
                    rows = await data_cursor.fetchall()

                    await asyncio.to_thread(_write_csv_sync, csv_path, headers, rows)

                    csv_files.append(csv_path)
                except Exception as e:
                    logger.error(f"Failed to export table {table_name}: {e}")
                    continue

        if not csv_files:
            logger.warning("No CSV files were generated. Aborting zip creation.")
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_path = os.path.join(DUMP_DIR, f"database_dump_{timestamp}.zip")

        await asyncio.to_thread(_create_zip_sync, zip_path, csv_files)

        return zip_path
    except Exception as e:
        logger.error(f"An unexpected error occurred during DB export: {e}")
        return None
    finally:
        for f in csv_files:
            try:
                os.remove(f)
                logger.debug(f"Removed temporary CSV file: {f}")
            except OSError as e:
                logger.warning(f"Error removing temporary file {f}: {e}")