import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).parent / "obs.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    # =========================================================
    # USERS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # =========================================================
    # FLIGHTS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_number TEXT NOT NULL,
            flight_date TEXT NOT NULL,
            aircraft TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            passengers INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(flight_number, flight_date)
        )
    """)

    # =========================================================
    # PRODUCTS
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            selling_price REAL NOT NULL,
            cost REAL NOT NULL
        )
    """)

    # =========================================================
    # INVENTORY
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            flight_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,

            loaded_quantity INTEGER NOT NULL DEFAULT 0,
            sold_quantity INTEGER NOT NULL DEFAULT 0,
            returned_quantity INTEGER NOT NULL DEFAULT 0,
            wasted_quantity INTEGER NOT NULL DEFAULT 0,

            UNIQUE(flight_id, product_id),

            FOREIGN KEY(flight_id)
                REFERENCES flights(id)
                ON DELETE CASCADE,

            FOREIGN KEY(product_id)
                REFERENCES products(id)
                ON DELETE CASCADE
        )
    """)

    # =========================================================
    # SALES
    # =========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transaction_id TEXT UNIQUE NOT NULL,

            flight_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,

            crew_id TEXT NOT NULL,

            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_amount REAL NOT NULL,

            payment_method TEXT NOT NULL,

            transaction_time TEXT NOT NULL,

            FOREIGN KEY(flight_id)
                REFERENCES flights(id),

            FOREIGN KEY(product_id)
                REFERENCES products(id)
        )
    """)

    # =========================================================
    # DEMO USERS
    # =========================================================

    users = [
        ("CREW001", "Demo Crew", "1234", "crew"),
        ("INV001", "Inventory Officer", "1234", "inventory"),
        ("SUP001", "Cabin Supervisor", "1234", "supervisor"),
        ("OBS001", "OBS Manager", "1234", "obs"),
        ("FIN001", "Finance User", "1234", "finance"),
        ("MGT001", "Management", "1234", "management"),
        ("ADMIN001", "IT Administrator", "1234", "admin"),
    ]

    for user in users:

        try:

            cursor.execute("""
                INSERT INTO users
                (
                    employee_id,
                    name,
                    password,
                    role
                )
                VALUES (?, ?, ?, ?)
            """, user)

        except sqlite3.IntegrityError:
            pass

    # =========================================================
    # DEMO PRODUCTS
    # =========================================================

    products = [
        ("WATER", "Mineral Water", "Beverage", 2.00, 0.50),
        ("COFFEE", "Coffee", "Beverage", 4.00, 1.20),
        ("SANDWICH", "Chicken Sandwich", "Food", 7.00, 3.00),
        ("JUICE", "Orange Juice", "Beverage", 3.00, 1.00),
        ("NOODLES", "Instant Noodles", "Food", 5.00, 2.00),
    ]

    for product in products:

        try:

            cursor.execute("""
                INSERT INTO products
                (
                    product_code,
                    product_name,
                    category,
                    selling_price,
                    cost
                )
                VALUES (?, ?, ?, ?, ?)
            """, product)

        except sqlite3.IntegrityError:
            pass

    # =========================================================
    # DEMO FLIGHTS
    # =========================================================

    flights = [
        ("H9-123", "2026-09-03", "9N-ABC", "KTM", "DXB", 180),
        ("H9-456", "2026-09-03", "9N-ABD", "KTM", "DOH", 170),
        ("H9-789", "2026-09-03", "9N-ABE", "KTM", "KUL", 165),
        ("H9-111", "2026-09-03", "9N-ABF", "KTM", "BKK", 160),
        ("H9-222", "2026-09-03", "9N-ABG", "KTM", "DEL", 150),
    ]

    for flight in flights:

        cursor.execute("""
            SELECT id
            FROM flights
            WHERE flight_number = ?
            AND flight_date = ?
        """, (
            flight[0],
            flight[1]
        ))

        if cursor.fetchone() is None:

            cursor.execute("""
                INSERT INTO flights
                (
                    flight_number,
                    flight_date,
                    aircraft,
                    origin,
                    destination,
                    passengers
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, flight)

    # =========================================================
    # INVENTORY
    # =========================================================

    cursor.execute("SELECT id FROM flights")

    flight_ids = [
        row["id"]
        for row in cursor.fetchall()
    ]

    cursor.execute("SELECT id FROM products")

    product_ids = [
        row["id"]
        for row in cursor.fetchall()
    ]

    default_inventory = {
        1: 100,
        2: 50,
        3: 30,
        4: 40,
        5: 35,
    }

    for flight_id in flight_ids:

        for product_id in product_ids:

            cursor.execute("""
                SELECT id
                FROM inventory
                WHERE flight_id = ?
                AND product_id = ?
            """, (
                flight_id,
                product_id
            ))

            if cursor.fetchone() is None:

                loaded = default_inventory.get(
                    product_id,
                    50
                )

                cursor.execute("""
                    INSERT INTO inventory
                    (
                        flight_id,
                        product_id,
                        loaded_quantity
                    )
                    VALUES (?, ?, ?)
                """, (
                    flight_id,
                    product_id,
                    loaded
                ))

    connection.commit()
    connection.close()