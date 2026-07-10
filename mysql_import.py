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
