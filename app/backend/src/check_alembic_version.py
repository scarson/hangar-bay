import sqlite3
import os

# Assuming the database hangar_bay_dev.db is in the same directory as this script
# and alembic.ini, which is app/backend/src/
DB_PATH = os.path.join(os.path.dirname(__file__), 'hangar_bay_dev.db')

def get_alembic_version():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT version_num FROM alembic_version")
        result = cursor.fetchone()
        if result:
            print(f"Current Alembic version in DB: {result[0]}")
        else:
            print("Alembic version table is empty or does not exist.")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    get_alembic_version()
