import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv

# =========================================================
# ENV
# =========================================================

load_dotenv()

# =========================================================
# DATABASE CONFIG
# =========================================================

DB_CONFIG = {
    "host": os.getenv("MYSQLHOST"),
    "port": int(os.getenv("MYSQLPORT", "3306")),
    "user": os.getenv("MYSQLUSER", "root"),
    "password": os.getenv("MYSQLPASSWORD", ""),
    "database": os.getenv("MYSQLDATABASE", "railway"),
}

# =========================================================
# INITIAL COUNT
# =========================================================

INITIAL_VOUCH_COUNT = 86
INITIAL_PAYMENT_COUNT = 105


# =========================================================
# CONNECTION
# =========================================================

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # TICKETS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                thread_id BIGINT NOT NULL UNIQUE,
                customer_id BIGINT NOT NULL,
                staff_id BIGINT NULL,
                ticket_type VARCHAR(50) NOT NULL,
                order_text TEXT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                created_at DATETIME NOT NULL,
                claimed_at DATETIME NULL,
                closed_at DATETIME NULL,
                vouched TINYINT(1) NOT NULL DEFAULT 0,

                INDEX idx_customer_status (
                    customer_id,
                    status
                ),

                INDEX idx_thread (
                    thread_id
                )
            )
        """)

        # VOUCHES
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vouches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL,
                customer_id BIGINT NOT NULL,
                rating TINYINT NOT NULL,
                review TEXT NOT NULL,
                created_at DATETIME NOT NULL,

                INDEX idx_vouch_ticket (
                    ticket_id
                ),

                INDEX idx_vouch_customer (
                    customer_id
                )
            )
        """)

        # PAYMENTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL UNIQUE,
                customer_id BIGINT NOT NULL,
                staff_id BIGINT NOT NULL,
                created_at DATETIME NOT NULL,

                INDEX idx_payment_ticket (
                    ticket_id
                ),

                INDEX idx_payment_customer (
                    customer_id
                ),

                INDEX idx_payment_staff (
                    staff_id
                ),

                INDEX idx_payment_created (
                    created_at
                )
            )
        """)

        # COUNTERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS counters (
                name VARCHAR(50) PRIMARY KEY,
                value INT NOT NULL DEFAULT 0
            )
        """)

        # Counter vouch dimulai dari 86 jika belum ada
        cursor.execute("""
            INSERT IGNORE INTO counters (name, value)
            VALUES ('vouch', %s)
        """, (INITIAL_VOUCH_COUNT,))

        # PANELS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS panels (
                id INT AUTO_INCREMENT PRIMARY KEY,
                panel_type VARCHAR(50) NOT NULL UNIQUE,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL
            )
        """)

        # TICKET LOGS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL,
                action VARCHAR(50) NOT NULL,
                user_id BIGINT NULL,
                created_at DATETIME NOT NULL,
                details TEXT NULL,

                INDEX idx_log_ticket (
                    ticket_id
                ),

                INDEX idx_log_action (
                    action
                )
            )
        """)

        connection.commit()
        print("✅ Database berhasil diinisialisasi.")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# =========================================================
# NEXT VOUCH NUMBER
# =========================================================

def get_next_vouch_number():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE counters
            SET value = value + 1
            WHERE name = 'vouch'
        """)

        # Pastikan counter tersedia
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT IGNORE INTO counters (name, value)
                VALUES ('vouch', %s)
            """, (INITIAL_VOUCH_COUNT,))

            cursor.execute("""
                UPDATE counters
                SET value = value + 1
                WHERE name = 'vouch'
            """)

        cursor.execute("""
            SELECT value
            FROM counters
            WHERE name = 'vouch'
            LIMIT 1
        """)

        result = cursor.fetchone()
        connection.commit()

        return (
            result[0]
            if result
            else INITIAL_VOUCH_COUNT + 1
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# =========================================================
# PAYMENT COUNT
# =========================================================

def get_payment_count():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT MAX(ticket_id)
            FROM payments
        """)

        result = cursor.fetchone()

        if not result or result[0] is None:
            return INITIAL_PAYMENT_COUNT

        return result[0]

    finally:
        cursor.close()
        connection.close()


# =========================================================
# VOUCH COUNT
# =========================================================

def get_vouch_count():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT MAX(ticket_id)
            FROM vouches
        """)

        result = cursor.fetchone()

        if not result or result[0] is None:
            return INITIAL_VOUCH_COUNT

        return result[0]

    finally:
        cursor.close()
        connection.close()


# =========================================================
# CHECK PAYMENT
# =========================================================

def has_payment(ticket_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT id
            FROM payments
            WHERE ticket_id = %s
            LIMIT 1
        """, (ticket_id,))

        return cursor.fetchone() is not None

    finally:
        cursor.close()
        connection.close()


# =========================================================
# RECORD PAYMENT
# =========================================================

def record_payment(
    ticket_id: int,
    customer_id: int,
    staff_id: int,
    created_at=None,
):
    if created_at is None:
        created_at = datetime.utcnow()

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Cegah payment dua kali
        cursor.execute("""
            SELECT id
            FROM payments
            WHERE ticket_id = %s
            LIMIT 1
        """, (ticket_id,))

        if cursor.fetchone():
            return None

        cursor.execute("""
            INSERT INTO payments (
                ticket_id,
                customer_id,
                staff_id,
                created_at
            )
            VALUES (%s, %s, %s, %s)
        """, (
            ticket_id,
            customer_id,
            staff_id,
            created_at,
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# =========================================================
# SAVE TICKET LOG
# =========================================================

def save_ticket_log(
    ticket_id: int,
    action: str,
    user_id=None,
    details=None,
    created_at=None,
):
    if created_at is None:
        created_at = datetime.utcnow()

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO ticket_logs (
                ticket_id,
                action,
                user_id,
                created_at,
                details
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            ticket_id,
            action,
            user_id,
            created_at,
            details,
        ))

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
