from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlite3

from database import (
    get_connection,
    initialize_database
)


# =========================================================
# APPLICATION
# =========================================================

app = FastAPI(
    title="Himalaya Airlines OBS Revenue Management System",
    version="2.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =========================================================
# DATABASE
# =========================================================

initialize_database()


# =========================================================
# CONSTANTS
# =========================================================

TARGET_RPP = 2.00

EXCHANGE_RATES = {
    "USD": 1.0000,
    "NPR": 135.0000,
    "GBP": 0.7900,
    "EUR": 0.9200,
    "AED": 3.6700,
    "QAR": 3.6400,
    "MYR": 4.2200,
    "THB": 32.5000,
    "INR": 83.5000
}

CURRENCY_NAMES = {
    "USD": "US Dollar",
    "NPR": "Nepalese Rupee",
    "GBP": "British Pound",
    "EUR": "Euro",
    "AED": "UAE Dirham",
    "QAR": "Qatari Riyal",
    "MYR": "Malaysian Ringgit",
    "THB": "Thai Baht",
    "INR": "Indian Rupee"
}

VALID_ROLES = {
    "crew",
    "inventory",
    "management",
    "admin"
}


# =========================================================
# PYDANTIC MODELS
# =========================================================

class LoginRequest(BaseModel):
    employee_id: str
    password: str


class FlightCreate(BaseModel):
    flight_number: str
    flight_date: str
    aircraft: str
    origin: str
    destination: str
    passengers: int = Field(gt=0)


class SaleItem(BaseModel):
    transaction_id: str
    flight_id: int
    product_id: int
    crew_id: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)
    total_amount: float = Field(ge=0)
    payment_method: str
    transaction_time: str


class UserCreate(BaseModel):
    employee_id: str
    name: str
    password: str
    role: str


class UserUpdate(BaseModel):
    name: str
    role: str


class PasswordUpdate(BaseModel):
    password: str


class ProductCreate(BaseModel):
    product_code: str
    product_name: str
    category: str
    selling_price: float = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)


class InventoryCreate(BaseModel):
    product_id: int
    loaded_quantity: int = Field(default=0, ge=0)
    returned_quantity: int = Field(default=0, ge=0)
    wasted_quantity: int = Field(default=0, ge=0)


class InventoryUpdate(BaseModel):
    loaded_quantity: int = Field(default=0, ge=0)
    returned_quantity: int = Field(default=0, ge=0)
    wasted_quantity: int = Field(default=0, ge=0)


# =========================================================
# AUTHENTICATION HELPERS
# =========================================================

def get_current_user(employee_id: str | None):
    if not employee_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required."
        )

    connection = get_connection()

    try:
        user = connection.execute(
            """
            SELECT
                id,
                employee_id,
                name,
                role
            FROM users
            WHERE employee_id = ?
            """,
            (employee_id.strip(),)
        ).fetchone()

    finally:
        connection.close()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found."
        )

    return dict(user)


def require_role(
    employee_id: str | None,
    allowed_roles
):
    user = get_current_user(employee_id)

    if user["role"] not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to perform this action."
        )

    return user


# =========================================================
# HEALTH
# =========================================================

@app.get("/")
def root():
    return {
        "system": "Himalaya Airlines OBS Revenue Management System",
        "status": "running",
        "version": "2.0"
    }


@app.get("/health")
def health():
    return {
        "status": "online"
    }


# =========================================================
# LOGIN
# =========================================================

@app.post("/login")
def login(data: LoginRequest):
    connection = get_connection()

    try:
        user = connection.execute(
            """
            SELECT
                id,
                employee_id,
                name,
                role
            FROM users
            WHERE employee_id = ?
            AND password = ?
            """,
            (
                data.employee_id.strip(),
                data.password
            )
        ).fetchone()

    finally:
        connection.close()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid Employee ID or password."
        )

    return dict(user)


# =========================================================
# USERS - ADMIN ONLY
# =========================================================

@app.get("/users")
def get_users(
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {"admin"}
    )

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                employee_id,
                name,
                role
            FROM users
            ORDER BY id
            """
        ).fetchall()

    finally:
        connection.close()

    return [dict(row) for row in rows]


@app.post("/users")
def create_user(
    data: UserCreate,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {"admin"}
    )

    employee_id = data.employee_id.strip()
    name = data.name.strip()
    role = data.role.strip().lower()

    if not employee_id:
        raise HTTPException(
            status_code=400,
            detail="Employee ID is required."
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name is required."
        )

    if not data.password:
        raise HTTPException(
            status_code=400,
            detail="Password is required."
        )

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Invalid role."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO users
            (
                employee_id,
                name,
                password,
                role
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                employee_id,
                name,
                data.password,
                role
            )
        )

        user_id = cursor.lastrowid

        connection.commit()

        row = cursor.execute(
            """
            SELECT
                id,
                employee_id,
                name,
                role
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        return dict(row)

    except sqlite3.IntegrityError:
        connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="Employee ID already exists."
        )

    finally:
        connection.close()


@app.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    x_employee_id: str | None = Header(default=None)
):
    current_user = require_role(
        x_employee_id,
        {"admin"}
    )

    role = data.role.strip().lower()
    name = data.name.strip()

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Invalid role."
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name is required."
        )

    connection = get_connection()

    try:
        existing = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="User not found."
            )

        if (
            existing["employee_id"] == current_user["employee_id"]
            and role != "admin"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "You cannot remove administrator access "
                    "from your own account."
                )
            )

        connection.execute(
            """
            UPDATE users
            SET
                name = ?,
                role = ?
            WHERE id = ?
            """,
            (
                name,
                role,
                user_id
            )
        )

        connection.commit()

        updated = connection.execute(
            """
            SELECT
                id,
                employee_id,
                name,
                role
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        return dict(updated)

    finally:
        connection.close()


@app.put("/users/{user_id}/password")
def change_user_password(
    user_id: int,
    data: PasswordUpdate,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {"admin"}
    )

    password = data.password.strip()

    if len(password) < 4:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 4 characters."
        )

    connection = get_connection()

    try:
        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="User not found."
            )

        connection.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (
                password,
                user_id
            )
        )

        connection.commit()

        return {
            "status": "success",
            "message": "Password changed successfully."
        }

    finally:
        connection.close()


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    x_employee_id: str | None = Header(default=None)
):
    current_user = require_role(
        x_employee_id,
        {"admin"}
    )

    connection = get_connection()

    try:
        existing = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="User not found."
            )

        if existing["employee_id"] == current_user["employee_id"]:
            raise HTTPException(
                status_code=400,
                detail="You cannot delete your own account."
            )

        connection.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (user_id,)
        )

        connection.commit()

        return {
            "status": "success",
            "message": "User deleted successfully."
        }

    finally:
        connection.close()


# =========================================================
# PRODUCTS
# =========================================================

@app.get("/products")
def get_products():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                product_code,
                product_name,
                category,
                selling_price,
                cost
            FROM products
            ORDER BY id
            """
        ).fetchall()

    finally:
        connection.close()

    return [dict(row) for row in rows]


@app.post("/products")
def create_product(
    data: ProductCreate,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {
            "inventory",
            "management"
        }
    )

    product_code = data.product_code.strip()
    product_name = data.product_name.strip()
    category = data.category.strip()

    if not product_code:
        raise HTTPException(
            status_code=400,
            detail="Product code is required."
        )

    if not product_name:
        raise HTTPException(
            status_code=400,
            detail="Product name is required."
        )

    if not category:
        raise HTTPException(
            status_code=400,
            detail="Category is required."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO products
            (
                product_code,
                product_name,
                category,
                selling_price,
                cost
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                product_code,
                product_name,
                category,
                data.selling_price,
                data.cost
            )
        )

        product_id = cursor.lastrowid

        connection.commit()

        product = cursor.execute(
            """
            SELECT
                id,
                product_code,
                product_name,
                category,
                selling_price,
                cost
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        ).fetchone()

        return dict(product)

    except sqlite3.IntegrityError:
        connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="Product code already exists."
        )

    finally:
        connection.close()


@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {
            "inventory",
            "management"
        }
    )

    connection = get_connection()

    try:
        used_inventory = connection.execute(
            """
            SELECT id
            FROM inventory
            WHERE product_id = ?
            LIMIT 1
            """,
            (product_id,)
        ).fetchone()

        if used_inventory:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot delete this product because "
                    "it is already used in inventory."
                )
            )

        used_sales = connection.execute(
            """
            SELECT id
            FROM sales
            WHERE product_id = ?
            LIMIT 1
            """,
            (product_id,)
        ).fetchone()

        if used_sales:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot delete this product because "
                    "sales already exist for it."
                )
            )

        cursor = connection.execute(
            """
            DELETE FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Product not found."
            )

        connection.commit()

        return {
            "status": "success",
            "message": "Product deleted successfully."
        }

    finally:
        connection.close()


# =========================================================
# FLIGHTS
# =========================================================

@app.get("/flights")
def get_flights():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                flight_number,
                flight_date,
                aircraft,
                origin,
                destination,
                passengers
            FROM flights
            ORDER BY
                flight_date DESC,
                id DESC
            """
        ).fetchall()

    finally:
        connection.close()

    return [dict(row) for row in rows]


@app.post("/flights")
def create_flight(
    data: FlightCreate,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {
            "crew",
            "inventory",
            "management"
        }
    )

    flight_number = data.flight_number.strip().upper()
    flight_date = data.flight_date.strip()
    aircraft = data.aircraft.strip().upper()
    origin = data.origin.strip().upper()
    destination = data.destination.strip().upper()

    if not flight_number:
        raise HTTPException(
            status_code=400,
            detail="Flight number is required."
        )

    if not aircraft:
        raise HTTPException(
            status_code=400,
            detail="Aircraft is required."
        )

    if len(origin) != 3 or len(destination) != 3:
        raise HTTPException(
            status_code=400,
            detail=(
                "Origin and destination must be "
                "3-letter airport codes."
            )
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
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
            """,
            (
                flight_number,
                flight_date,
                aircraft,
                origin,
                destination,
                data.passengers
            )
        )

        flight_id = cursor.lastrowid

        # Default inventory for a newly-created flight.
        default_inventory = {
            1: 100,
            2: 50,
            3: 30,
            4: 40,
            5: 35
        }

        products = cursor.execute(
            """
            SELECT id
            FROM products
            """
        ).fetchall()

        for product in products:
            product_id = product["id"]

            loaded = default_inventory.get(
                product_id,
                50
            )

            cursor.execute(
                """
                INSERT INTO inventory
                (
                    flight_id,
                    product_id,
                    loaded_quantity
                )
                VALUES (?, ?, ?)
                """,
                (
                    flight_id,
                    product_id,
                    loaded
                )
            )

        connection.commit()

        flight = cursor.execute(
            """
            SELECT *
            FROM flights
            WHERE id = ?
            """,
            (flight_id,)
        ).fetchone()

        return dict(flight)

    except sqlite3.IntegrityError:
        connection.rollback()

        raise HTTPException(
            status_code=409,
            detail="This flight already exists for the selected date."
        )

    finally:
        connection.close()


# =========================================================
# INVENTORY - VIEW
# =========================================================

@app.get("/inventory/{flight_id}")
def get_inventory(
    flight_id: int
):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                i.id,
                i.flight_id,
                i.product_id,

                p.product_code,
                p.product_name,
                p.category,

                i.loaded_quantity,
                i.sold_quantity,
                i.returned_quantity,
                i.wasted_quantity,

                (
                    i.loaded_quantity
                    - i.sold_quantity
                    - i.returned_quantity
                    - i.wasted_quantity
                ) AS remaining_quantity

            FROM inventory i

            JOIN products p
                ON p.id = i.product_id

            WHERE i.flight_id = ?

            ORDER BY p.id
            """,
            (flight_id,)
        ).fetchall()

    finally:
        connection.close()

    return [dict(row) for row in rows]


# =========================================================
# INVENTORY - ADD
# =========================================================

@app.post("/inventory/{flight_id}")
def add_inventory(
    flight_id: int,
    data: InventoryCreate,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {
            "inventory",
            "management"
        }
    )

    connection = get_connection()

    try:
        flight = connection.execute(
            """
            SELECT id
            FROM flights
            WHERE id = ?
            """,
            (flight_id,)
        ).fetchone()

        if flight is None:
            raise HTTPException(
                status_code=404,
                detail="Flight not found."
            )

        product = connection.execute(
            """
            SELECT id
            FROM products
            WHERE id = ?
            """,
            (data.product_id,)
        ).fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found."
            )

        existing = connection.execute(
            """
            SELECT id
            FROM inventory
            WHERE flight_id = ?
            AND product_id = ?
            """,
            (
                flight_id,
                data.product_id
            )
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="This product already exists for this flight."
            )

        if (
            data.returned_quantity
            + data.wasted_quantity
            > data.loaded_quantity
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Returned plus wasted quantity "
                    "cannot exceed loaded quantity."
                )
            )

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO inventory
            (
                flight_id,
                product_id,
                loaded_quantity,
                sold_quantity,
                returned_quantity,
                wasted_quantity
            )
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (
                flight_id,
                data.product_id,
                data.loaded_quantity,
                data.returned_quantity,
                data.wasted_quantity
            )
        )

        inventory_id = cursor.lastrowid

        connection.commit()

        return {
            "status": "success",
            "id": inventory_id,
            "message": "Inventory added successfully."
        }

    finally:
        connection.close()


# =========================================================
# INVENTORY - UPDATE
# =========================================================

@app.put("/inventory/{inventory_id}")
def update_inventory(
    inventory_id: int,
    data: InventoryUpdate,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {
            "inventory",
            "management"
        }
    )

    connection = get_connection()

    try:
        inventory = connection.execute(
            """
            SELECT *
            FROM inventory
            WHERE id = ?
            """,
            (inventory_id,)
        ).fetchone()

        if inventory is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory record not found."
            )

        # Sold quantity comes from actual sales.
        # Inventory users cannot directly modify it.
        if (
            data.returned_quantity
            + data.wasted_quantity
            + inventory["sold_quantity"]
            > data.loaded_quantity
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Sold + returned + wasted quantity "
                    "cannot exceed loaded quantity."
                )
            )

        connection.execute(
            """
            UPDATE inventory
            SET
                loaded_quantity = ?,
                returned_quantity = ?,
                wasted_quantity = ?
            WHERE id = ?
            """,
            (
                data.loaded_quantity,
                data.returned_quantity,
                data.wasted_quantity,
                inventory_id
            )
        )

        connection.commit()

        return {
            "status": "success",
            "message": "Inventory updated successfully."
        }

    finally:
        connection.close()


# =========================================================
# INVENTORY - DELETE
# =========================================================

@app.delete("/inventory/{inventory_id}")
def delete_inventory(
    inventory_id: int,
    x_employee_id: str | None = Header(default=None)
):
    require_role(
        x_employee_id,
        {
            "inventory",
            "management"
        }
    )

    connection = get_connection()

    try:
        inventory = connection.execute(
            """
            SELECT *
            FROM inventory
            WHERE id = ?
            """,
            (inventory_id,)
        ).fetchone()

        if inventory is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory record not found."
            )

        if inventory["sold_quantity"] > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot delete inventory because sales "
                    "have already been recorded for this product."
                )
            )

        connection.execute(
            """
            DELETE FROM inventory
            WHERE id = ?
            """,
            (inventory_id,)
        )

        connection.commit()

        return {
            "status": "success",
            "message": "Inventory deleted successfully."
        }

    finally:
        connection.close()


# =========================================================
# SALES
# =========================================================

@app.post("/sales")
def record_sale(
    data: SaleItem,
    x_employee_id: str | None = Header(default=None)
):
    current_user = get_current_user(
        x_employee_id
    )

    # Only crew and management can record sales.
    if current_user["role"] not in {
        "crew",
        "management"
    }:
        raise HTTPException(
            status_code=403,
            detail="This account cannot record sales."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        flight = cursor.execute(
            """
            SELECT *
            FROM flights
            WHERE id = ?
            """,
            (data.flight_id,)
        ).fetchone()

        if flight is None:
            raise HTTPException(
                status_code=404,
                detail="Flight not found."
            )

        product = cursor.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (data.product_id,)
        ).fetchone()

        if product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found."
            )

        inventory = cursor.execute(
            """
            SELECT *
            FROM inventory
            WHERE flight_id = ?
            AND product_id = ?
            """,
            (
                data.flight_id,
                data.product_id
            )
        ).fetchone()

        if inventory is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory record not found."
            )

        remaining = (
            inventory["loaded_quantity"]
            - inventory["sold_quantity"]
            - inventory["returned_quantity"]
            - inventory["wasted_quantity"]
        )

        if data.quantity > remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock. "
                    f"Only {remaining} unit(s) available."
                )
            )

        existing = cursor.execute(
            """
            SELECT id
            FROM sales
            WHERE transaction_id = ?
            """,
            (data.transaction_id,)
        ).fetchone()

        if existing:
            return {
                "status": "already_recorded",
                "transaction_id": data.transaction_id
            }

        cursor.execute(
            """
            INSERT INTO sales
            (
                transaction_id,
                flight_id,
                product_id,
                crew_id,
                quantity,
                unit_price,
                total_amount,
                payment_method,
                transaction_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.transaction_id,
                data.flight_id,
                data.product_id,
                current_user["employee_id"],
                data.quantity,
                data.unit_price,
                data.total_amount,
                data.payment_method,
                data.transaction_time
            )
        )

        cursor.execute(
            """
            UPDATE inventory
            SET sold_quantity = sold_quantity + ?
            WHERE flight_id = ?
            AND product_id = ?
            """,
            (
                data.quantity,
                data.flight_id,
                data.product_id
            )
        )

        connection.commit()

        return {
            "status": "success",
            "transaction_id": data.transaction_id
        }

    except HTTPException:
        connection.rollback()
        raise

    except sqlite3.IntegrityError as error:
        connection.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    finally:
        connection.close()


# =========================================================
# CURRENCIES
# =========================================================

@app.get("/currencies")
def get_currencies():
    return [
        {
            "code": code,
            "name": CURRENCY_NAMES[code],
            "rate": rate
        }
        for code, rate in EXCHANGE_RATES.items()
    ]


@app.get("/exchange-rate/{currency}")
def get_exchange_rate(
    currency: str
):
    currency = currency.upper()

    if currency not in EXCHANGE_RATES:
        raise HTTPException(
            status_code=404,
            detail="Currency not supported."
        )

    return {
        "currency": currency,
        "rate": EXCHANGE_RATES[currency],
        "source": "Demo fixed rate"
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/dashboard")
def dashboard(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None
):
    connection = get_connection()

    try:
        conditions = []
        params = []

        if year is not None:
            conditions.append(
                "substr(f.flight_date, 1, 4) = ?"
            )
            params.append(
                str(year)
            )

        if month is not None:
            conditions.append(
                "substr(f.flight_date, 6, 2) = ?"
            )
            params.append(
                f"{month:02d}"
            )

        if day is not None:
            conditions.append(
                "substr(f.flight_date, 9, 2) = ?"
            )
            params.append(
                f"{day:02d}"
            )

        where_clause = ""

        if conditions:
            where_clause = (
                "WHERE " + " AND ".join(conditions)
            )

        flight_rows = connection.execute(
            f"""
            SELECT
                f.id,
                f.flight_number,
                f.flight_date,
                f.origin,
                f.destination,
                f.passengers,
                COALESCE(
                    SUM(s.total_amount),
                    0
                ) AS revenue

            FROM flights f

            LEFT JOIN sales s
                ON s.flight_id = f.id

            {where_clause}

            GROUP BY
                f.id,
                f.flight_number,
                f.flight_date,
                f.origin,
                f.destination,
                f.passengers

            ORDER BY
                f.flight_date DESC
            """,
            params
        ).fetchall()

        flights = []

        total_revenue = 0.0
        total_passengers = 0

        for row in flight_rows:
            revenue = float(
                row["revenue"] or 0
            )

            passengers = int(
                row["passengers"] or 0
            )

            rpp = (
                revenue / passengers
                if passengers > 0
                else 0
            )

            total_revenue += revenue
            total_passengers += passengers

            flights.append({
                "id": row["id"],
                "flight_number": row["flight_number"],
                "flight_date": row["flight_date"],
                "origin": row["origin"],
                "destination": row["destination"],
                "passengers": passengers,
                "revenue": revenue,
                "rpp": rpp
            })

        current_rpp = (
            total_revenue / total_passengers
            if total_passengers > 0
            else 0
        )

        gap = (
            current_rpp - TARGET_RPP
        )

        achievement = (
            (current_rpp / TARGET_RPP) * 100
            if TARGET_RPP > 0
            else 0
        )

        product_conditions = []
        product_params = []

        if year is not None:
            product_conditions.append(
                "substr(f.flight_date, 1, 4) = ?"
            )
            product_params.append(
                str(year)
            )

        if month is not None:
            product_conditions.append(
                "substr(f.flight_date, 6, 2) = ?"
            )
            product_params.append(
                f"{month:02d}"
            )

        if day is not None:
            product_conditions.append(
                "substr(f.flight_date, 9, 2) = ?"
            )
            product_params.append(
                f"{day:02d}"
            )

        product_where = ""

        if product_conditions:
            product_where = (
                "WHERE "
                + " AND ".join(product_conditions)
            )

        product_rows = connection.execute(
            f"""
            SELECT
                p.product_name,

                COALESCE(
                    SUM(s.quantity),
                    0
                ) AS quantity_sold,

                COALESCE(
                    SUM(s.total_amount),
                    0
                ) AS revenue

            FROM products p

            LEFT JOIN sales s
                ON s.product_id = p.id

            LEFT JOIN flights f
                ON f.id = s.flight_id

            {product_where}

            GROUP BY
                p.id,
                p.product_name

            ORDER BY
                revenue DESC
            """,
            product_params
        ).fetchall()

        products = [
            {
                "product_name": row["product_name"],
                "quantity_sold": int(
                    row["quantity_sold"] or 0
                ),
                "revenue": float(
                    row["revenue"] or 0
                )
            }
            for row in product_rows
        ]

        return {
            "target_rpp": TARGET_RPP,
            "rpp": current_rpp,
            "gap": gap,
            "achievement": achievement,
            "revenue": total_revenue,
            "passengers": total_passengers,
            "flights": flights,
            "products": products
        }

    finally:
        connection.close()


# =========================================================
# RECENT SALES
# =========================================================

@app.get("/sales")
def get_sales(
    x_employee_id: str | None = Header(default=None)
):
    get_current_user(
        x_employee_id
    )

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                s.id,
                s.transaction_id,
                s.flight_id,
                f.flight_number,
                s.product_id,
                p.product_name,
                s.crew_id,
                s.quantity,
                s.unit_price,
                s.total_amount,
                s.payment_method,
                s.transaction_time

            FROM sales s

            JOIN flights f
                ON f.id = s.flight_id

            JOIN products p
                ON p.id = s.product_id

            ORDER BY
                s.id DESC

            LIMIT 100
            """
        ).fetchall()

    finally:
        connection.close()

    return [
        dict(row)
        for row in rows
    ]