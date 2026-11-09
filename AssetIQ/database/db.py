
import os

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Create and return a MySQL database connection."""

    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "assetiq_db")
        )

        return connection

    except Error as error:
        print("MySQL connection error:", error)
        return None


def fetch_all(query, params=None):
    """Execute a SELECT query and return all records."""

    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        records = cursor.fetchall()

        return records

    except Error as error:
        print("Database query error:", error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def fetch_one(query, params=None):
    """Execute a SELECT query and return one record."""

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor.fetchone()

    except Error as error:
        print("Database query error:", error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def test_connection():
    """Check whether AssetIQ can connect to MySQL."""

    connection = get_connection()

    if connection is None:
        print("MySQL connection FAILED.")
        return False

    try:
        print("MySQL connection SUCCESSFUL!")
        print("Connected database:", connection.database)
        return True

    finally:
        connection.close()


if __name__ == "__main__":
    test_connection()
