import csv
import os
from datetime import datetime

import mysql.connector


def get_mysql_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT", "3306")),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
    )

def get_expiry_stats():
    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT list_name, COUNT(*)
            FROM expiry_items
            GROUP BY list_name
            ORDER BY list_name
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "list_name": row[0],
                "rows_count": row[1],
            }
            for row in rows
        ]

    finally:
        cursor.close()
        connection.close()
        
def parse_date(value):
    value = (value or "").strip()

    if not value:
        return None

    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    raise ValueError(f"Невірний формат дати: {value}")


def import_expiry_csv(file_path):
    required_columns = {
        "list_name",
        "tt_number",
        "product_name",
        "stock_qty",
        "term1",
        "qty1",
        "term2",
        "qty2",
        "status",
    }

    records = []
    list_names = set()

    with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        actual_columns = set(reader.fieldnames or [])
        missing_columns = required_columns - actual_columns

        if missing_columns:
            raise ValueError(
                "У файлі немає колонок: "
                + ", ".join(sorted(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            list_name = (row.get("list_name") or "").strip()
            tt_number = (row.get("tt_number") or "").strip()
            product_name = (row.get("product_name") or "").strip()
            stock_qty = (row.get("stock_qty") or "").strip()

            if not list_name:
                raise ValueError(
                    f"Рядок {row_number}: не вказано list_name"
                )

            if not tt_number:
                raise ValueError(
                    f"Рядок {row_number}: не вказано tt_number"
                )

            if not product_name:
                raise ValueError(
                    f"Рядок {row_number}: не вказано product_name"
                )

            tt_number = tt_number.zfill(3)
            list_names.add(list_name)

            records.append(
                (
                    list_name,
                    tt_number,
                    product_name,
                    stock_qty,
                    parse_date(row.get("term1")),
                    (row.get("qty1") or "").strip() or None,
                    parse_date(row.get("term2")),
                    (row.get("qty2") or "").strip() or None,
                    (row.get("status") or "").strip() or "pending",
                )
            )

    if not records:
        raise ValueError("У CSV немає рядків для завантаження")

    if len(list_names) != 1:
        raise ValueError(
            "В одному файлі має бути тільки одна назва списку"
        )

    list_name = next(iter(list_names))

    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM expiry_items
            WHERE list_name = %s
            """,
            (list_name,),
        )

        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            raise ValueError(
                f"Список {list_name} вже є в MySQL. "
                f"Знайдено рядків: {existing_count}"
            )

        cursor.executemany(
            """
            INSERT INTO expiry_items (
                list_name,
                tt_number,
                product_name,
                stock_qty,
                term1,
                qty1,
                term2,
                qty2,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            records,
        )

        connection.commit()

        return {
            "list_name": list_name,
            "imported_rows": len(records),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

def get_list_names_from_mysql():
    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT DISTINCT list_name
            FROM expiry_items
            ORDER BY list_name
            """
        )

        rows = cursor.fetchall()
        return [row[0] for row in rows]

    finally:
        cursor.close()
        connection.close()


def get_available_list_names_for_tt_mysql(tt_number):
    tt_number = str(tt_number).strip().zfill(3)

    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT DISTINCT list_name
            FROM expiry_items
            WHERE tt_number = %s
              AND (
                    status IS NULL
                    OR status = ''
                    OR status = 'pending'
                  )
            ORDER BY list_name
            """,
            (tt_number,)
        )

        rows = cursor.fetchall()
        return [row[0] for row in rows]

    finally:
        cursor.close()
        connection.close()


def get_products_by_tt_mysql(list_name, tt_number):
    tt_number = str(tt_number).strip().zfill(3)

    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                id,
                product_name,
                stock_qty
            FROM expiry_items
            WHERE list_name = %s
              AND tt_number = %s
              AND (
                    status IS NULL
                    OR status = ''
                    OR status = 'pending'
                  )
            ORDER BY id
            """,
            (list_name, tt_number)
        )

        rows = cursor.fetchall()

        products = []

        for row in rows:
            products.append({
                "row_number": row["id"],
                "product_name": row["product_name"],
                "stock": row["stock_qty"],
            })

        return products

    finally:
        cursor.close()
        connection.close()


def save_product_result_mysql(list_name, row_id, term1, qty1, term2="", qty2=""):
    term1_value = parse_date(term1)
    term2_value = parse_date(term2)

    qty1_value = (qty1 or "").strip() or None
    qty2_value = (qty2 or "").strip() or None

    if not term1_value and qty1_value == "-" and not term2_value and not qty2_value:
        status = "absent"
    else:
        status = "done"

    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE expiry_items
            SET
                term1 = %s,
                qty1 = %s,
                term2 = %s,
                qty2 = %s,
                status = %s,
                checked_at = NOW()
            WHERE id = %s
              AND list_name = %s
            """,
            (
                term1_value,
                qty1_value,
                term2_value,
                qty2_value,
                status,
                row_id,
                list_name,
            )
        )

        if cursor.rowcount == 0:
            raise ValueError(
                f"Не знайдено рядок для запису: list_name={list_name}, id={row_id}"
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

def import_store_managers_csv(file_path):
    required_columns = {
        "tt_number",
        "store_name",
        "tm_name",
        "active",
    }

    records = []

    with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        actual_columns = set(reader.fieldnames or [])
        missing_columns = required_columns - actual_columns

        if missing_columns:
            raise ValueError(
                "У файлі довідника немає колонок: "
                + ", ".join(sorted(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            tt_number = (row.get("tt_number") or "").strip()
            store_name = (row.get("store_name") or "").strip()
            tm_name = (row.get("tm_name") or "").strip()
            active = (row.get("active") or "").strip().lower() or "active"

            if not tt_number:
                raise ValueError(
                    f"Рядок {row_number}: не вказано tt_number"
                )

            if not store_name:
                raise ValueError(
                    f"Рядок {row_number}: не вказано store_name"
                )

            if not tm_name:
                raise ValueError(
                    f"Рядок {row_number}: не вказано tm_name"
                )

            if active not in ("active", "inactive"):
                raise ValueError(
                    f"Рядок {row_number}: active має бути active або inactive"
                )

            tt_number = tt_number.zfill(3)

            records.append(
                (
                    tt_number,
                    store_name,
                    tm_name,
                    active,
                )
            )

    if not records:
        raise ValueError("У CSV довідника немає рядків для завантаження")

    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS store_managers (
                tt_number VARCHAR(10) NOT NULL PRIMARY KEY,
                store_name VARCHAR(255) NOT NULL,
                tm_name VARCHAR(255) NOT NULL,
                active VARCHAR(20) DEFAULT 'active'
            )
            """
        )

        cursor.executemany(
            """
            INSERT INTO store_managers (
                tt_number,
                store_name,
                tm_name,
                active
            )
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                store_name = VALUES(store_name),
                tm_name = VALUES(tm_name),
                active = VALUES(active)
            """,
            records,
        )

        connection.commit()

        return {
            "imported_rows": len(records),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()

def get_store_managers_stats():
    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN active = 'active' THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN active = 'inactive' THEN 1 ELSE 0 END) AS inactive_count
            FROM store_managers
            """
        )

        row = cursor.fetchone()

        return {
            "total_count": row["total_count"] or 0,
            "active_count": row["active_count"] or 0,
            "inactive_count": row["inactive_count"] or 0,
        }

    finally:
        cursor.close()
        connection.close()

def column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name)
    )

    return cursor.fetchone()[0] > 0


def parse_check_date_from_list_name(list_name):
    value = (list_name or "").strip()

    if "_" in value:
        value = value.split("_", 1)[0]

    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def ensure_expiry_items_extra_columns():
    connection = get_mysql_connection()
    cursor = connection.cursor()

    try:
        columns_to_add = [
            (
                "checked_at",
                "ALTER TABLE expiry_items ADD COLUMN checked_at DATETIME NULL"
            ),
            (
                "check_date",
                "ALTER TABLE expiry_items ADD COLUMN check_date DATE NULL"
            ),
            (
                "source",
                "ALTER TABLE expiry_items ADD COLUMN source VARCHAR(20) DEFAULT 'manual'"
            ),
            (
                "created_at",
                "ALTER TABLE expiry_items ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ),
        ]

        for column_name, alter_sql in columns_to_add:
            if not column_exists(cursor, "expiry_items", column_name):
                cursor.execute(alter_sql)

        cursor.execute(
            """
            UPDATE expiry_items
            SET check_date = STR_TO_DATE(SUBSTRING_INDEX(list_name, '_', 1), '%d.%m.%Y')
            WHERE check_date IS NULL
              AND list_name REGEXP '^[0-9]{2}\\.[0-9]{2}\\.[0-9]{4}_'
            """
        )

        cursor.execute(
            """
            UPDATE expiry_items
            SET source = 'manual'
            WHERE source IS NULL OR source = ''
            """
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
