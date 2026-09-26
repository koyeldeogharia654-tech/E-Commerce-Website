from flask import Flask, render_template, render_template_string, redirect, url_for, session, request
import sqlite3
import random
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "my_secret_key"

DATABASE = "database.db"

# ==================================================
# UPLOAD FOLDERS
# ==================================================

app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["PRODUCT_IMAGE_FOLDER"] = "static/images"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["PRODUCT_IMAGE_FOLDER"], exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

# ==================================================
# ADMIN LOGIN
# ==================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# ==================================================
# ORDER STATUS
# ==================================================

ORDER_STATUSES = [
    "Order Placed",
    "Processing",
    "Shipped",
    "Out for Delivery",
    "Delivered",
    "Cancelled"
]

RETURN_STATUSES = ["Pending", "Approved", "Rejected"]
RETURN_DAYS = 7

# ==================================================
# DEFAULT PRODUCTS
# ==================================================

DEFAULT_PRODUCTS = [
    {
        "id": 1,
        "name": "Smartphone",
        "price": 15000,
        "category": "Electronics",
        "image": "smartphone.jpg",
        "description": "Latest smartphone with powerful performance and modern design.",
        "rating": 4.5
    },
    {
        "id": 2,
        "name": "Laptop",
        "price": 50000,
        "category": "Computers",
        "image": "laptop.jpg",
        "description": "Powerful laptop suitable for study, programming and daily work.",
        "rating": 4.7
    },
    {
        "id": 3,
        "name": "Headphones",
        "price": 2000,
        "category": "Audio",
        "image": "headphones.jpg",
        "description": "Wireless headphones with clear sound and comfortable design.",
        "rating": 4.3
    }
]

SAMPLE_REVIEWS = {
    1: [
        {
            "name": "Rahul",
            "rating": 5,
            "comment": "Excellent smartphone. Very good performance!"
        },
        {
            "name": "Priya",
            "rating": 4,
            "comment": "Good phone at this price."
        }
    ],
    2: [
        {
            "name": "Amit",
            "rating": 5,
            "comment": "Very fast and powerful laptop."
        },
        {
            "name": "Sneha",
            "rating": 4,
            "comment": "Good laptop for students."
        }
    ],
    3: [
        {
            "name": "Arjun",
            "rating": 5,
            "comment": "Sound quality is really good."
        },
        {
            "name": "Riya",
            "rating": 4,
            "comment": "Comfortable and easy to use."
        }
    ]
}

PRODUCTS = []

# ==================================================
# DATABASE
# ==================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    conn = get_db()
    cursor = conn.cursor()

    # ==================================================
    # USERS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            address TEXT DEFAULT '',
            photo TEXT DEFAULT '',
            role TEXT DEFAULT 'user'
        )
    """)

    cursor.execute("PRAGMA table_info(users)")
    user_columns = [column["name"] for column in cursor.fetchall()]

    if "address" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN address TEXT DEFAULT ''"
        )

    if "photo" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN photo TEXT DEFAULT ''"
        )

    if "role" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"
        )

    cursor.execute("""
        UPDATE users
        SET role = 'user'
        WHERE role IS NULL OR role = ''
    """)

    # ==================================================
    # ORDERS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            username TEXT,
            name TEXT,
            address TEXT,
            phone TEXT,
            payment_method TEXT,
            items TEXT,
            total REAL,
            status TEXT,
            order_date TEXT,
            delivery_date TEXT,
            delivered_date TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(orders)")
    order_columns = [column["name"] for column in cursor.fetchall()]

    if "username" not in order_columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN username TEXT"
        )

    if "status" not in order_columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN status TEXT"
        )

    if "order_date" not in order_columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN order_date TEXT"
        )

    if "delivery_date" not in order_columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN delivery_date TEXT"
        )

    if "delivered_date" not in order_columns:
        cursor.execute(
            "ALTER TABLE orders ADD COLUMN delivered_date TEXT"
        )

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE status IS NULL OR status = ''
    """, ("Order Placed",))

    today = datetime.now().date()

    cursor.execute("""
        SELECT id, order_date, delivery_date
        FROM orders
        WHERE order_date IS NULL OR order_date = ''
           OR delivery_date IS NULL OR delivery_date = ''
    """)

    old_orders = cursor.fetchall()

    for old_order in old_orders:

        base_date = today

        order_date_value = (
            old_order["order_date"]
            or base_date.strftime("%Y-%m-%d")
        )

        delivery_date_value = (
            old_order["delivery_date"]
            or (base_date + timedelta(days=4)).strftime("%Y-%m-%d")
        )

        cursor.execute("""
            UPDATE orders
            SET order_date = ?, delivery_date = ?
            WHERE id = ?
        """, (
            order_date_value,
            delivery_date_value,
            old_order["id"]
        ))

    # Existing Delivered orders
    cursor.execute("""
        UPDATE orders
        SET delivered_date = delivery_date
        WHERE status = 'Delivered'
          AND (delivered_date IS NULL OR delivered_date = '')
          AND delivery_date IS NOT NULL
          AND delivery_date != ''
    """)

    # ==================================================
    # RETURN REQUESTS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS return_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            request_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            reason TEXT DEFAULT '',
            decision_date TEXT DEFAULT ''
        )
    """)

    cursor.execute("PRAGMA table_info(return_requests)")
    return_columns = [column["name"] for column in cursor.fetchall()]

    if "reason" not in return_columns:
        cursor.execute(
            "ALTER TABLE return_requests ADD COLUMN reason TEXT DEFAULT ''"
        )

    if "decision_date" not in return_columns:
        cursor.execute(
            "ALTER TABLE return_requests ADD COLUMN decision_date TEXT DEFAULT ''"
        )

    # ==================================================
    # WISHLIST
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            UNIQUE(username, product_id)
        )
    """)

    # ==================================================
    # REVIEWS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL
        )
    """)

    # ==================================================
    # PRODUCTS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            image TEXT NOT NULL,
            description TEXT NOT NULL,
            rating REAL DEFAULT 0
        )
    """)

    cursor.execute("PRAGMA table_info(products)")
    product_columns = [column["name"] for column in cursor.fetchall()]

    if "name" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN name TEXT"
        )

    if "price" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN price REAL DEFAULT 0"
        )

    if "category" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'Other'"
        )

    if "image" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN image TEXT DEFAULT 'default.jpg'"
        )

    if "description" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN description TEXT DEFAULT ''"
        )

    if "rating" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN rating REAL DEFAULT 0"
        )

    # ==================================================
    # PRODUCT SEED CONTROL
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)

    cursor.execute(
        "SELECT setting_value FROM app_settings WHERE setting_name = ?",
        ("products_seeded",)
    )

    seeded = cursor.fetchone()

    if not seeded:

        cursor.execute(
            "SELECT COUNT(*) AS total FROM products"
        )

        product_count = cursor.fetchone()["total"]

        if product_count == 0:

            for product in DEFAULT_PRODUCTS:

                cursor.execute("""
                    INSERT INTO products
                    (id, name, price, category, image, description, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    product["id"],
                    product["name"],
                    product["price"],
                    product["category"],
                    product["image"],
                    product["description"],
                    product["rating"]
                ))

        cursor.execute(
            "INSERT INTO app_settings (setting_name, setting_value) VALUES (?, ?)",
            ("products_seeded", "1")
        )

    # ==================================================
    # SAMPLE REVIEWS
    # ==================================================

    for product_id, reviews in SAMPLE_REVIEWS.items():

        for review in reviews:

            cursor.execute("""
                SELECT id
                FROM reviews
                WHERE username = ?
                AND product_id = ?
                AND rating = ?
                AND comment = ?
            """, (
                review["name"],
                product_id,
                review["rating"],
                review["comment"]
            ))

            if not cursor.fetchone():

                cursor.execute("""
                    INSERT INTO reviews
                    (username, product_id, rating, comment)
                    VALUES (?, ?, ?, ?)
                """, (
                    review["name"],
                    product_id,
                    review["rating"],
                    review["comment"]
                ))

    conn.commit()
    conn.close()


def load_products_from_database():

    global PRODUCTS

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, price, category, image, description, rating
        FROM products
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    PRODUCTS = []

    for row in rows:

        raw_price = float(row["price"])

        price = (
            int(raw_price)
            if raw_price.is_integer()
            else raw_price
        )

        PRODUCTS.append({
            "id": row["id"],
            "name": row["name"],
            "price": price,
            "category": row["category"],
            "image": row["image"],
            "description": row["description"],
            "rating": float(row["rating"] or 0),
            "reviews": SAMPLE_REVIEWS.get(
                row["id"],
                []
            ).copy()
        })


# ==================================================
# DATE FORMAT
# ==================================================

def format_date_with_day(date_text):

    if not date_text:
        return ""

    try:

        date_obj = datetime.strptime(
            str(date_text),
            "%Y-%m-%d"
        )

        # Example:
        # 26.09.2026 Saturday
        return date_obj.strftime("%d.%m.%Y %A")

    except (TypeError, ValueError):

        return str(date_text)


# ==================================================
# HELPERS
# ==================================================

def get_cart():

    cart = session.get("cart", {})

    if isinstance(cart, list):

        new_cart = {}

        for product_id in cart:

            key = str(product_id)

            new_cart[key] = (
                new_cart.get(key, 0) + 1
            )

        return new_cart

    if not isinstance(cart, dict):
        return {}

    return cart


def is_admin():
    return session.get("role") == "admin"


def is_user():
    return session.get("role") == "user"


def require_user():
    return is_user()


def require_admin():
    return is_admin()


def parse_order_items(items_text):

    items = []

    if items_text is None:
        return items

    try:
        text_value = str(items_text)
    except Exception:
        return items

    for item_data in text_value.split(";;"):

        item_data = item_data.strip()

        if not item_data:
            continue

        parts = item_data.split("|")

        if len(parts) < 3:
            continue

        item_name = "|".join(
            parts[:-2]
        ).strip()

        quantity_text = parts[-2].strip()
        subtotal_text = parts[-1].strip()

        try:
            quantity = int(quantity_text)
        except (TypeError, ValueError):
            continue

        try:
            subtotal = float(subtotal_text)
        except (TypeError, ValueError):
            continue

        if not item_name:
            item_name = "Product"

        items.append({
            "name": item_name,
            "quantity": quantity,
            "subtotal": subtotal
        })

    return items


def get_product(product_id):

    load_products_from_database()

    return next(
        (
            product
            for product in PRODUCTS
            if product["id"] == product_id
        ),
        None
    )


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    load_products_from_database()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    category = request.args.get(
        "category",
        ""
    ).strip()

    filtered_products = PRODUCTS[:]

    if search:

        filtered_products = [
            product
            for product in filtered_products
            if (
                search in product["name"].lower()
                or search in product["description"].lower()
                or search in product["category"].lower()
            )
        ]

    if category:

        filtered_products = [
            product
            for product in filtered_products
            if product["category"] == category
        ]

    categories = sorted({
        product["category"]
        for product in PRODUCTS
    })

    return render_template(
        "index.html",
        products=filtered_products,
        search=search,
        category=category,
        categories=categories
    )


# ==================================================
# SIGNUP
# ==================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not username or not email or not password:

            return render_template(
                "signup.html",
                error="Please fill all the fields."
            )

        if password != confirm_password:

            return render_template(
                "signup.html",
                error="Passwords do not match."
            )

        if username.lower() == ADMIN_USERNAME.lower():

            return render_template(
                "signup.html",
                error="This username is reserved."
            )

        conn = get_db()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO users
                (username, email, password, address, photo, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                username,
                email,
                password,
                "",
                "",
                "user"
            ))

            conn.commit()
            conn.close()

            return redirect(
                url_for("login")
            )

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "signup.html",
                error="Username already exists. Please choose another username."
            )

    return render_template("signup.html")


# ==================================================
# USER LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        # Admin login
        if (
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session.clear()

            session["username"] = ADMIN_USERNAME
            session["role"] = "admin"
            session["admin"] = True

            return redirect(
                url_for("admin_products")
            )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username = ?
            AND password = ?
        """, (
            username,
            password
        ))

        user = cursor.fetchone()

        conn.close()

        if user:

            session.clear()

            session["username"] = user["username"]
            session["role"] = "user"
            session["admin"] = False

            return redirect(
                url_for("home")
            )

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")


# ==================================================
# OLD ADMIN URL
# ==================================================

@app.route("/admin")
def admin_login_redirect():

    return redirect(
        url_for("login")
    )


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


@app.route("/admin_logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==================================================
# PROFILE
# ==================================================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if not require_user():
        return redirect(url_for("login"))

    username = session["username"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    )

    user = cursor.fetchone()

    if not user:

        conn.close()
        session.clear()

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        address = request.form.get(
            "address",
            ""
        ).strip()

        photo = request.files.get("photo")

        photo_filename = user["photo"] or ""

        if photo and photo.filename:

            filename = secure_filename(
                photo.filename
            )

            if filename:

                photo_filename = (
                    username
                    + "_"
                    + filename
                )

                photo.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        photo_filename
                    )
                )

        cursor.execute("""
            UPDATE users
            SET address = ?, photo = ?
            WHERE username = ?
        """, (
            address,
            photo_filename,
            username
        ))

        conn.commit()

        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        return render_template(
            "profile.html",
            user=user,
            success="Profile updated successfully!"
        )

    conn.close()

    return render_template(
        "profile.html",
        user=user
    )


# ==================================================
# PRODUCT DETAILS
# ==================================================

@app.route("/product/<int:product_id>")
def product_details(product_id):

    product = get_product(product_id)

    if product is None:
        return "Product not found", 404

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, rating, comment
        FROM reviews
        WHERE product_id = ?
        ORDER BY id DESC
    """, (product_id,))

    database_reviews = cursor.fetchall()

    conn.close()

    reviews = [
        review.copy()
        for review in SAMPLE_REVIEWS.get(
            product_id,
            []
        )
    ]

    sample_keys = {
        (
            review["name"],
            review["rating"],
            review["comment"]
        )
        for review in reviews
    }

    for review in database_reviews:

        key = (
            review["username"],
            review["rating"],
            review["comment"]
        )

        if key not in sample_keys:

            reviews.append({
                "name": review["username"],
                "rating": review["rating"],
                "comment": review["comment"]
            })

    if reviews:

        product["rating"] = round(
            sum(
                review["rating"]
                for review in reviews
            ) / len(reviews),
            1
        )

    else:

        product["rating"] = 0

    product["reviews"] = reviews

    return render_template(
        "product_details.html",
        product=product
    )


# ==================================================
# ADD REVIEW
# ==================================================

@app.route(
    "/add_review/<int:product_id>",
    methods=["POST"]
)
def add_review(product_id):

    if not require_user():
        return redirect(url_for("login"))

    if get_product(product_id) is None:
        return "Product not found", 404

    rating_text = request.form.get(
        "rating",
        ""
    ).strip()

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    try:
        rating = int(rating_text)
    except ValueError:
        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            )
        )

    if (
        rating < 1
        or rating > 5
        or not comment
    ):

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            )
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM reviews
        WHERE username = ?
        AND product_id = ?
    """, (
        session["username"],
        product_id
    ))

    if cursor.fetchone():

        conn.close()

        return redirect(
            url_for(
                "product_details",
                product_id=product_id
            )
        )

    cursor.execute("""
        INSERT INTO reviews
        (username, product_id, rating, comment)
        VALUES (?, ?, ?, ?)
    """, (
        session["username"],
        product_id,
        rating,
        comment
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            "product_details",
            product_id=product_id
        )
    )


# ==================================================
# CART
# ==================================================

@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):

    if not require_user():
        return redirect(url_for("login"))

    if get_product(product_id) is None:
        return "Product not found", 404

    cart = get_cart()

    key = str(product_id)

    cart[key] = cart.get(key, 0) + 1

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


@app.route("/cart")
def cart():

    if not require_user():
        return redirect(url_for("login"))

    load_products_from_database()

    cart_data = get_cart()

    cart_items = []
    total = 0

    for product_id, quantity in cart_data.items():

        product = next(
            (
                product
                for product in PRODUCTS
                if product["id"] == int(product_id)
            ),
            None
        )

        if product:

            item = product.copy()

            item["quantity"] = quantity

            item["subtotal"] = (
                product["price"]
                * quantity
            )

            cart_items.append(item)

            total += item["subtotal"]

    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )


@app.route(
    "/update_cart/<int:product_id>/<action>"
)
def update_cart(product_id, action):

    if not require_user():
        return redirect(url_for("login"))

    cart = get_cart()

    key = str(product_id)

    if key in cart:

        if action == "increase":

            cart[key] += 1

        elif action == "decrease":

            cart[key] -= 1

            if cart[key] <= 0:
                del cart[key]

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


@app.route(
    "/remove_from_cart/<int:product_id>"
)
def remove_from_cart(product_id):

    if not require_user():
        return redirect(url_for("login"))

    cart = get_cart()

    cart.pop(
        str(product_id),
        None
    )

    session["cart"] = cart

    return redirect(
        url_for("cart")
    )


@app.route("/clear_cart")
def clear_cart():

    if not require_user():
        return redirect(url_for("login"))

    session["cart"] = {}

    return redirect(
        url_for("cart")
    )


# ==================================================
# WISHLIST
# ==================================================

@app.route(
    "/add_to_wishlist/<int:product_id>"
)
def add_to_wishlist(product_id):

    if not require_user():
        return redirect(url_for("login"))

    if get_product(product_id) is None:
        return "Product not found", 404

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO wishlist
        (username, product_id)
        VALUES (?, ?)
    """, (
        session["username"],
        product_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        request.referrer
        or url_for("home")
    )


@app.route("/wishlist")
def wishlist():

    if not require_user():
        return redirect(url_for("login"))

    load_products_from_database()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT product_id
        FROM wishlist
        WHERE username = ?
        ORDER BY id DESC
    """, (
        session["username"],
    ))

    rows = cursor.fetchall()

    conn.close()

    wishlist_products = []

    for row in rows:

        product = next(
            (
                product
                for product in PRODUCTS
                if product["id"] == row["product_id"]
            ),
            None
        )

        if product:
            wishlist_products.append(product)

    return render_template(
        "wishlist.html",
        wishlist_products=wishlist_products
    )


@app.route(
    "/remove_from_wishlist/<int:product_id>"
)
def remove_from_wishlist(product_id):

    if not require_user():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM wishlist
        WHERE username = ?
        AND product_id = ?
    """, (
        session["username"],
        product_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("wishlist")
    )


# ==================================================
# CHECKOUT
# ==================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
def checkout():

    if not require_user():
        return redirect(url_for("login"))

    load_products_from_database()

    cart_data = get_cart()

    cart_items = []
    total = 0

    for product_id, quantity in cart_data.items():

        product = next(
            (
                product
                for product in PRODUCTS
                if product["id"] == int(product_id)
            ),
            None
        )

        if product:

            item = product.copy()

            item["quantity"] = quantity

            item["subtotal"] = (
                product["price"]
                * quantity
            )

            cart_items.append(item)

            total += item["subtotal"]

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        payment_method = request.form.get(
            "payment_method",
            "Cash on Delivery"
        )

        if not name or not address or not phone:

            return render_template(
                "checkout.html",
                cart_items=cart_items,
                total=total,
                error="Please fill all the fields."
            )

        if not cart_items:

            return render_template(
                "checkout.html",
                cart_items=[],
                total=0,
                error="Your cart is empty."
            )

        # Generate unique order ID
        while True:

            order_id = (
                "ORD"
                + str(
                    random.randint(
                        100000,
                        999999
                    )
                )
            )

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM orders WHERE order_id = ?",
                (order_id,)
            )

            existing_order = cursor.fetchone()

            conn.close()

            if not existing_order:
                break

        items_text = ""

        for item in cart_items:

            items_text += (
                f'{item["name"]}|'
                f'{item["quantity"]}|'
                f'{item["subtotal"]};;'
            )

        order_date = datetime.now().date()

        delivery_date = (
            order_date
            + timedelta(days=4)
        )

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders
            (
                order_id,
                username,
                name,
                address,
                phone,
                payment_method,
                items,
                total,
                status,
                order_date,
                delivery_date,
                delivered_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            session["username"],
            name,
            address,
            phone,
            payment_method,
            items_text,
            total,
            "Order Placed",
            order_date.strftime("%Y-%m-%d"),
            delivery_date.strftime("%Y-%m-%d"),
            ""
        ))

        conn.commit()
        conn.close()

        session["cart"] = {}

        return render_template(
            "checkout.html",
            success=True,
            order_id=order_id,
            name=name,
            address=address,
            phone=phone,
            payment_method=payment_method,
            total=total,

            # Date + Day
            order_date=format_date_with_day(
                order_date.strftime("%Y-%m-%d")
            ),

            delivery_date=format_date_with_day(
                delivery_date.strftime("%Y-%m-%d")
            ),

            cart_items=[]
        )

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total
    )


# ==================================================
# MY ORDERS
# ==================================================

@app.route("/orders")
def orders():

    if not require_user():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        WHERE username = ?
        ORDER BY id DESC
    """, (
        session["username"],
    ))

    rows = cursor.fetchall()

    orders_list = []

    for row in rows:

        items = parse_order_items(
            row["items"]
        )

        cursor.execute("""
            SELECT request_date, status, reason, decision_date
            FROM return_requests
            WHERE order_id = ?
        """, (
            row["order_id"],
        ))

        return_row = cursor.fetchone()

        return_status = (
            return_row["status"]
            if return_row
            else ""
        )

        # ==================================================
        # RETURN DATE CALCULATION
        # ==================================================

        delivered_date = (
            row["delivered_date"]
            or ""
        )

        return_deadline = ""
        return_allowed = False

        if row["status"] == "Delivered":

            delivered_date_text = (
                delivered_date
                or (row["delivery_date"] or "")
            )

            if delivered_date_text:

                try:

                    delivered = datetime.strptime(
                        delivered_date_text,
                        "%Y-%m-%d"
                    ).date()

                    # Save fallback delivered date
                    if not delivered_date:

                        delivered_date = (
                            delivered.strftime(
                                "%Y-%m-%d"
                            )
                        )

                        cursor.execute(
                            """
                            UPDATE orders
                            SET delivered_date = ?
                            WHERE order_id = ?
                            """,
                            (
                                delivered_date,
                                row["order_id"]
                            )
                        )

                    deadline = (
                        delivered
                        + timedelta(days=RETURN_DAYS)
                    )

                    # Keep database date unchanged
                    return_deadline_raw = (
                        deadline.strftime(
                            "%Y-%m-%d"
                        )
                    )

                    # Display date with day
                    return_deadline = (
                        format_date_with_day(
                            return_deadline_raw
                        )
                    )

                    return_allowed = (
                        datetime.now().date()
                        <= deadline
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    return_allowed = False

        orders_list.append({

            "order_id": row["order_id"],

            "name": row["name"],

            "address": row["address"],

            "phone": row["phone"],

            "payment_method": (
                row["payment_method"]
                or "Cash on Delivery"
            ),

            "items": items,

            "total": row["total"] or 0,

            "status": (
                row["status"]
                or "Order Placed"
            ),

            # ==================================================
            # DATE + DAY DISPLAY
            # ==================================================

            "order_date": format_date_with_day(
                row["order_date"] or ""
            ),

            "delivery_date": format_date_with_day(
                row["delivery_date"] or ""
            ),

            "delivered_date": format_date_with_day(
                delivered_date
            ),

            "return_status": return_status,

            "return_reason": (
                return_row["reason"]
                if return_row
                else ""
            ),

            "return_decision_date": (
                format_date_with_day(
                    return_row["decision_date"]
                    if return_row
                    else ""
                )
            ),

            "return_deadline": return_deadline,

            "return_allowed": return_allowed
        })

    conn.commit()
    conn.close()

    return render_template(
        "orders.html",
        orders=orders_list
    )


# ==================================================
# CANCEL ORDER
# ==================================================

@app.route(
    "/cancel_order/<order_id>",
    methods=["GET", "POST"]
)
def cancel_order(order_id):

    if not require_user():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = ?
        WHERE order_id = ?
        AND username = ?
        AND status = ?
    """, (
        "Cancelled",
        order_id,
        session["username"],
        "Order Placed"
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("orders")
    )


# ==================================================
# RETURN ORDER
# ==================================================

@app.route(
    "/return_order/<order_id>",
    methods=["GET", "POST"]
)
def return_order(order_id):

    if not require_user():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            order_id,
            username,
            status,
            delivered_date,
            delivery_date
        FROM orders
        WHERE order_id = ?
        AND username = ?
    """, (
        order_id,
        session["username"]
    ))

    order = cursor.fetchone()

    if not order:

        conn.close()

        return redirect(
            url_for("orders")
        )

    if order["status"] != "Delivered":

        conn.close()

        return redirect(
            url_for("orders")
        )

    delivered_date_text = (
        order["delivered_date"]
        or order["delivery_date"]
        or ""
    )

    try:

        delivered_date = datetime.strptime(
            delivered_date_text,
            "%Y-%m-%d"
        ).date()

    except (
        TypeError,
        ValueError
    ):

        conn.close()

        return redirect(
            url_for("orders")
        )

    # Keep delivered_date populated
    if not order["delivered_date"]:

        cursor.execute(
            """
            UPDATE orders
            SET delivered_date = ?
            WHERE order_id = ?
            """,
            (
                delivered_date.strftime(
                    "%Y-%m-%d"
                ),
                order_id
            )
        )

    deadline = (
        delivered_date
        + timedelta(days=RETURN_DAYS)
    )

    if datetime.now().date() > deadline:

        conn.close()

        return redirect(
            url_for("orders")
        )

    cursor.execute(
        """
        SELECT id
        FROM return_requests
        WHERE order_id = ?
        """,
        (order_id,)
    )

    existing = cursor.fetchone()

    if existing:

        conn.close()

        return redirect(
            url_for("orders")
        )

    if request.method == "POST":

        reason = request.form.get(
            "reason",
            ""
        ).strip()

        cursor.execute("""
            INSERT INTO return_requests
            (
                order_id,
                username,
                request_date,
                status,
                reason,
                decision_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            session["username"],
            datetime.now().date().strftime(
                "%Y-%m-%d"
            ),
            "Pending",
            reason,
            ""
        ))

        conn.commit()
        conn.close()

        return redirect(
            url_for("orders")
        )

    conn.close()

    return render_template_string(
        """
        <!DOCTYPE html>
        <html lang="en">

        <head>

            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>Return Order</title>

            <style>

                body{
                    font-family:Arial,sans-serif;
                    background:#f5f5f5;
                    margin:0;
                }

                .box{
                    max-width:500px;
                    margin:60px auto;
                    background:white;
                    padding:30px;
                    border-radius:12px;
                    box-shadow:
                        0 3px 12px rgba(0,0,0,.15);
                }

                textarea{
                    width:100%;
                    box-sizing:border-box;
                    padding:10px;
                    margin-top:10px;
                    border:1px solid #ccc;
                    border-radius:6px;
                    height:120px;
                }

                button,.back{
                    display:inline-block;
                    padding:11px 18px;
                    margin-top:15px;
                    border:0;
                    border-radius:6px;
                    text-decoration:none;
                    cursor:pointer;
                }

                button{
                    background:#dc3545;
                    color:white;
                }

                .back{
                    background:#ddd;
                    color:#333;
                }

            </style>

        </head>

        <body>

            <div class="box">

                <h2>↩️ Return Order</h2>

                <p>
                    <strong>Order ID:</strong>
                    {{ order_id }}
                </p>

                <p>
                    <strong>Return deadline:</strong>
                    {{ deadline }}
                </p>

                <form method="POST">

                    <label>
                        <strong>
                            Reason for return (optional)
                        </strong>
                    </label>

                    <textarea
                        name="reason"
                        placeholder="Enter your reason..."
                    ></textarea>

                    <br>

                    <button type="submit">
                        Submit Return Request
                    </button>

                    <a
                        class="back"
                        href="{{ url_for('orders') }}"
                    >
                        ← Back
                    </a>

                </form>

            </div>

        </body>

        </html>
        """,

        order_id=order_id,

        # Date + Day
        deadline=format_date_with_day(
            deadline.strftime("%Y-%m-%d")
        )
    )


# ==================================================
# ADMIN ORDERS
# ==================================================

ADMIN_ORDERS_HTML = """

<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Admin Orders</title>

    <style>

        body {
            font-family: Arial, sans-serif;
            background:#f5f5f5;
            margin:0;
        }

        .header {
            background:#333;
            color:white;
            padding:20px;
            text-align:center;
        }

        .top {
            text-align:center;
            margin:20px;
        }

        .button {
            display:inline-block;
            padding:10px 15px;
            margin:5px;
            background:#333;
            color:white;
            text-decoration:none;
            border-radius:6px;
        }

        .orders {
            padding:20px;
            max-width:1000px;
            margin:auto;
        }

        .order {
            background:white;
            padding:20px;
            margin-bottom:20px;
            border-radius:10px;
            box-shadow:
                0 3px 10px rgba(0,0,0,0.12);
        }

        .status-form {
            margin-top:15px;
        }

        select,
        input,
        textarea {
            padding:10px;
            border-radius:6px;
            border:1px solid #ccc;
        }

        .update {
            padding:10px 15px;
            background:#007bff;
            color:white;
            border:none;
            border-radius:6px;
            cursor:pointer;
        }

        .approve {
            background:#28a745;
        }

        .reject {
            background:#dc3545;
        }

        .item {
            margin:6px 0;
        }

        .return-box {
            margin-top:20px;
            padding:15px;
            background:#fff8e1;
            border:1px solid #ffe082;
            border-radius:8px;
        }

        .approved {
            color:#155724;
            font-weight:bold;
        }

        .pending {
            color:#856404;
            font-weight:bold;
        }

        .rejected {
            color:#721c24;
            font-weight:bold;
        }

    </style>

</head>

<body>

<div class="header">

    <h1>Admin Orders</h1>

</div>

<div class="top">

    <a
        class="button"
        href="{{ url_for('admin_products') }}"
    >
        📦 Manage Products
    </a>

    <a
        class="button"
        href="{{ url_for('admin_add_product') }}"
    >
        ➕ Add Product
    </a>

    <a
        class="button"
        href="{{ url_for('admin_logout') }}"
    >
        🚪 Logout
    </a>

</div>

<div class="orders">

{% if orders %}

    {% for order in orders %}

        <div class="order">

            <h2>
                Order ID:
                {{ order["order_id"] }}
            </h2>

            <p>
                <strong>User:</strong>
                {{ order["username"] }}
            </p>

            <p>
                <strong>Name:</strong>
                {{ order["name"] }}
            </p>

            <p>
                <strong>Address:</strong>
                {{ order["address"] }}
            </p>

            <p>
                <strong>Phone:</strong>
                {{ order["phone"] }}
            </p>

            <p>
                <strong>Payment:</strong>
                {{ order["payment_method"] }}
            </p>

            <h3>Items</h3>

            {% for item in order["items"] %}

                <div class="item">

                    {{ item["name"] }}
                    ×
                    {{ item["quantity"] }}
                    =
                    ₹{{ item["subtotal"] }}

                </div>

            {% endfor %}

            <p>
                <strong>Total:</strong>
                ₹{{ order["total"] }}
            </p>

            <p>
                <strong>Order Date:</strong>
                {{ order["order_date"] }}
            </p>

            <p>
                <strong>Expected Delivery:</strong>
                {{ order["delivery_date"] }}
            </p>

            <p>
                <strong>Delivered Date:</strong>
                {{ order["delivered_date"] or "Not delivered yet" }}
            </p>

            <p>
                <strong>Current Status:</strong>
                {{ order["status"] }}
            </p>

            <!-- STATUS UPDATE -->

            <form
                class="status-form"
                method="POST"
                action="{{ url_for(
                    'update_order_status',
                    order_id=order['order_id']
                ) }}"
            >

                <select name="status">

                    {% for status in order_statuses %}

                        <option
                            value="{{ status }}"
                            {% if status == order["status"] %}
                                selected
                            {% endif %}
                        >
                            {{ status }}
                        </option>

                    {% endfor %}

                </select>

                <button
                    class="update"
                    type="submit"
                >
                    Update Status
                </button>

            </form>

            <!-- DELIVERY DATE UPDATE -->

            <form
                class="status-form"
                method="POST"
                action="{{ url_for(
                    'update_delivery_date',
                    order_id=order['order_id']
                ) }}"
            >

                <label>
                    <strong>
                        Change Expected Delivery Date:
                    </strong>
                </label>

                <br>

                <input
                    type="date"
                    name="delivery_date"
                    value="{{ order['delivery_date_raw'] }}"
                    required
                >

                <button
                    class="update"
                    type="submit"
                >
                    Update Delivery Date
                </button>

            </form>

            <!-- RETURN REQUEST -->

            {% if order["return_status"] %}

                <div class="return-box">

                    <h3>
                        ↩️ Return Request
                    </h3>

                    <p>

                        <strong>Status:</strong>

                        {% if order["return_status"] == "Approved" %}

                            <span class="approved">
                                Approved
                            </span>

                        {% elif order["return_status"] == "Rejected" %}

                            <span class="rejected">
                                Rejected
                            </span>

                        {% else %}

                            <span class="pending">
                                Pending
                            </span>

                        {% endif %}

                    </p>

                    <p>

                        <strong>Request Date:</strong>

                        {{ order["return_request_date"] }}

                    </p>

                    {% if order["return_reason"] %}

                        <p>

                            <strong>Reason:</strong>

                            {{ order["return_reason"] }}

                        </p>

                    {% endif %}

                    {% if order["return_decision_date"] %}

                        <p>

                            <strong>
                                Decision Date:
                            </strong>

                            {{ order["return_decision_date"] }}

                        </p>

                    {% endif %}

                    {% if order["return_status"] == "Pending" %}

                        <form
                            class="status-form"
                            method="POST"
                            action="{{ url_for(
                                'update_return_status',
                                order_id=order['order_id']
                            ) }}"
                        >

                            <button
                                class="update approve"
                                type="submit"
                                name="return_status"
                                value="Approved"
                            >
                                Approve Return
                            </button>

                            <button
                                class="update reject"
                                type="submit"
                                name="return_status"
                                value="Rejected"
                            >
                                Reject Return
                            </button>

                        </form>

                    {% endif %}

                </div>

            {% endif %}

        </div>

    {% endfor %}

{% else %}

    <div class="order">

        <h2>
            No orders found.
        </h2>

    </div>

{% endif %}

</div>

</body>

</html>

"""


@app.route("/admin/orders")
def admin_orders():

    if not require_admin():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            order_id,
            username,
            name,
            address,
            phone,
            payment_method,
            items,
            total,
            status,
            order_date,
            delivery_date,
            delivered_date
        FROM orders
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    orders_list = []

    for row in rows:

        try:

            total = float(
                row["total"] or 0
            )

        except (
            TypeError,
            ValueError
        ):

            total = 0.0

        status = (
            row["status"]
            or "Order Placed"
        )

        if status not in ORDER_STATUSES:
            status = "Order Placed"

        cursor.execute("""
            SELECT
                request_date,
                status,
                reason,
                decision_date
            FROM return_requests
            WHERE order_id = ?
        """, (
            row["order_id"],
        ))

        rr = cursor.fetchone()

        orders_list.append({

            "order_id": (
                row["order_id"]
                or ("ORDER-" + str(row["id"]))
            ),

            "username": (
                row["username"]
                or "Unknown User"
            ),

            "name": row["name"] or "",

            "address": row["address"] or "",

            "phone": row["phone"] or "",

            "payment_method": (
                row["payment_method"]
                or "Cash on Delivery"
            ),

            "items": parse_order_items(
                row["items"]
            ),

            "total": total,

            "status": status,

            # ==================================================
            # DATE + DAY DISPLAY
            # ==================================================

            "order_date": format_date_with_day(
                row["order_date"] or ""
            ),

            "delivery_date": format_date_with_day(
                row["delivery_date"] or ""
            ),

            "delivered_date": format_date_with_day(
                row["delivered_date"] or ""
            ),

            # Raw date is needed for HTML date input
            "delivery_date_raw": (
                row["delivery_date"] or ""
            ),

            "return_status": (
                rr["status"]
                if rr
                else ""
            ),

            "return_request_date": (
                format_date_with_day(
                    rr["request_date"]
                    if rr
                    else ""
                )
            ),

            "return_reason": (
                rr["reason"]
                if rr
                else ""
            ),

            "return_decision_date": (
                format_date_with_day(
                    rr["decision_date"]
                    if rr
                    else ""
                )
            )

        })

    conn.close()

    return render_template_string(
        ADMIN_ORDERS_HTML,
        orders=orders_list,
        order_statuses=ORDER_STATUSES
    )


# ==================================================
# UPDATE DELIVERY DATE
# ==================================================

@app.route(
    "/admin/update_delivery_date/<order_id>",
    methods=["POST"]
)
def update_delivery_date(order_id):

    if not require_admin():
        return redirect(url_for("login"))

    new_delivery_date = request.form.get(
        "delivery_date",
        ""
    ).strip()

    if not new_delivery_date:
        return redirect(
            url_for("admin_orders")
        )

    try:

        datetime.strptime(
            new_delivery_date,
            "%Y-%m-%d"
        )

    except ValueError:

        return redirect(
            url_for("admin_orders")
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE orders
        SET delivery_date = ?
        WHERE order_id = ?
        """,
        (
            new_delivery_date,
            order_id
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_orders")
    )


# ==================================================
# UPDATE ORDER STATUS
# ==================================================

@app.route(
    "/admin/update_status/<order_id>",
    methods=["POST"]
)
@app.route(
    "/admin/update_order_status/<order_id>",
    methods=["POST"]
)
def update_order_status(order_id):

    if not require_admin():
        return redirect(url_for("login"))

    new_status = request.form.get(
        "status",
        ""
    ).strip()

    if new_status not in ORDER_STATUSES:

        return redirect(
            url_for("admin_orders")
        )

    conn = get_db()
    cursor = conn.cursor()

    if new_status == "Delivered":

        cursor.execute("""
            UPDATE orders
            SET
                status = ?,
                delivered_date = ?
            WHERE order_id = ?
        """, (
            new_status,
            datetime.now().date().strftime(
                "%Y-%m-%d"
            ),
            order_id
        ))

    else:

        cursor.execute("""
            UPDATE orders
            SET status = ?
            WHERE order_id = ?
        """, (
            new_status,
            order_id
        ))

    conn.commit()

    conn.close()

    return redirect(
        url_for("admin_orders")
    )


# ==================================================
# ADMIN UPDATE RETURN STATUS
# ==================================================

@app.route(
    "/admin/update_return_status/<order_id>",
    methods=["POST"]
)
def update_return_status(order_id):

    if not require_admin():
        return redirect(url_for("login"))

    new_status = request.form.get(
        "return_status",
        ""
    ).strip()

    if new_status not in (
        "Approved",
        "Rejected"
    ):

        return redirect(
            url_for("admin_orders")
        )

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE return_requests
        SET
            status = ?,
            decision_date = ?
        WHERE order_id = ?
        AND status = 'Pending'
    """, (
        new_status,
        datetime.now().date().strftime(
            "%Y-%m-%d"
        ),
        order_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin_orders")
    )


# ==================================================
# ADMIN ADD PRODUCT
# ==================================================

ADMIN_ADD_PRODUCT_HTML = """

<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Add Product - Admin</title>

    <style>

        body {
            font-family:Arial,sans-serif;
            background:#f5f5f5;
            margin:0;
        }

        .header {
            background:#333;
            color:white;
            padding:20px;
            text-align:center;
        }

        .container {

            width:500px;

            max-width:90%;

            margin:30px auto;

            background:white;

            padding:30px;

            border-radius:12px;

            box-shadow:
                0 4px 15px rgba(0,0,0,0.15);

        }

        label {
            display:block;
            font-weight:bold;
            margin-top:15px;
        }

        input,
        textarea {

            width:100%;

            box-sizing:border-box;

            padding:10px;

            margin-top:6px;

            border:1px solid #ccc;

            border-radius:6px;

        }

        textarea {
            height:100px;
            resize:vertical;
        }

        button {

            width:100%;

            margin-top:20px;

            padding:12px;

            background:#333;

            color:white;

            border:none;

            border-radius:6px;

            cursor:pointer;

            font-size:16px;

        }

        .success {

            background:#d4edda;

            color:#155724;

            padding:12px;

            border-radius:6px;

            margin-bottom:15px;

        }

        .error {

            background:#f8d7da;

            color:#721c24;

            padding:12px;

            border-radius:6px;

            margin-bottom:15px;

        }

        .links {

            text-align:center;

            margin-top:20px;

        }

        .links a {

            margin:0 8px;

            color:#333;

            text-decoration:none;

        }

    </style>

</head>

<body>

<div class="header">

    <h1>Admin - Add Product</h1>

</div>

<div class="container">

    <h2>➕ Add Product</h2>

    {% if success %}

        <div class="success">
            {{ success }}
        </div>

    {% endif %}

    {% if error %}

        <div class="error">
            {{ error }}
        </div>

    {% endif %}

    <form
        method="POST"
        enctype="multipart/form-data"
    >

        <label>
            Product Name
        </label>

        <input
            type="text"
            name="name"
            required
        >

        <label>
            Price (₹)
        </label>

        <input
            type="number"
            name="price"
            step="0.01"
            min="0.01"
            required
        >

        <label>
            Category
        </label>

        <input
            type="text"
            name="category"
            required
        >

        <label>
            Description
        </label>

        <textarea
            name="description"
            required
        ></textarea>

        <label>
            Product Image
        </label>

        <input
            type="file"
            name="image"
            accept=".jpg,.jpeg,.png,.gif,.webp"
            required
        >

        <button type="submit">
            ➕ Add Product
        </button>

    </form>

    <div class="links">

        <a href="{{ url_for('admin_products') }}">
            📦 Manage Products
        </a>

        <a href="{{ url_for('admin_orders') }}">
            📋 Admin Orders
        </a>

        <a href="{{ url_for('admin_logout') }}">
            🚪 Logout
        </a>

    </div>

</div>

</body>

</html>

"""


@app.route(
    "/admin/add_product",
    methods=["GET", "POST"]
)
def admin_add_product():

    if not require_admin():
        return redirect(url_for("login"))

    error = ""
    success = ""

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        price_text = request.form.get(
            "price",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        image = request.files.get(
            "image"
        )

        if (
            not name
            or not price_text
            or not category
            or not description
        ):

            error = (
                "Please fill all the fields."
            )

        elif not image or not image.filename:

            error = (
                "Please select a product image."
            )

        else:

            try:

                price = float(
                    price_text
                )

                if price <= 0:
                    raise ValueError

            except ValueError:

                price = 0

                error = (
                    "Please enter a valid positive price."
                )

            if not error:

                filename = secure_filename(
                    image.filename
                )

                extension = (
                    filename.rsplit(
                        ".",
                        1
                    )[-1].lower()
                    if "." in filename
                    else ""
                )

                if (
                    not filename
                    or extension
                    not in ALLOWED_IMAGE_EXTENSIONS
                ):

                    error = (
                        "Only JPG, JPEG, PNG, GIF "
                        "or WEBP images are allowed."
                    )

                else:

                    conn = get_db()
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT id
                        FROM products
                        WHERE LOWER(name) = LOWER(?)
                    """, (
                        name,
                    ))

                    existing_product = (
                        cursor.fetchone()
                    )

                    if existing_product:

                        conn.close()

                        error = (
                            "A product with this name "
                            "already exists."
                        )

                    else:

                        unique_filename = (
                            str(
                                random.randint(
                                    100000,
                                    999999999
                                )
                            )
                            + "_"
                            + filename
                        )

                        image.save(
                            os.path.join(
                                app.config[
                                    "PRODUCT_IMAGE_FOLDER"
                                ],
                                unique_filename
                            )
                        )

                        cursor.execute("""
                            INSERT INTO products
                            (
                                name,
                                price,
                                category,
                                image,
                                description,
                                rating
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            name,
                            price,
                            category,
                            unique_filename,
                            description,
                            0
                        ))

                        conn.commit()
                        conn.close()

                        load_products_from_database()

                        success = (
                            "Product added successfully!"
                        )

    return render_template_string(
        ADMIN_ADD_PRODUCT_HTML,
        error=error,
        success=success
    )


# ==================================================
# ADMIN PRODUCTS LIST
# ==================================================

ADMIN_PRODUCTS_HTML = """

<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Admin Products</title>

    <style>

        body {

            font-family: Arial, sans-serif;

            background: #f5f5f5;

            margin: 0;

        }

        .header {

            background: #333;

            color: white;

            padding: 20px;

            text-align: center;

        }

        .top {

            text-align: center;

            margin: 20px;

        }

        .button {

            display: inline-block;

            padding: 10px 15px;

            margin: 5px;

            background: #333;

            color: white;

            text-decoration: none;

            border-radius: 6px;

        }

        .button:hover {
            background: #555;
        }

        .products {

            display: flex;

            flex-wrap: wrap;

            gap: 20px;

            justify-content: center;

            padding: 20px;

        }

        .card {

            background: white;

            width: 230px;

            padding: 15px;

            border-radius: 10px;

            box-shadow:
                0 3px 10px rgba(0,0,0,0.12);

            text-align: center;

        }

        .card img {

            width: 100%;

            height: 170px;

            object-fit: contain;

            border-radius: 8px;

        }

        .price {

            font-weight: bold;

            font-size: 18px;

        }

        .edit {

            background: #007bff;

        }

        .delete {

            background: #dc3545;

        }

        .edit:hover {

            background: #0069d9;

        }

        .delete:hover {

            background: #c82333;

        }

        .empty {

            text-align: center;

            margin: 40px;

            font-size: 20px;

            color: #666;

        }

    </style>

</head>

<body>

<div class="header">

    <h1>Admin Products</h1>

</div>

<div class="top">

    <a
        class="button"
        href="{{ url_for('admin_add_product') }}"
    >
        ➕ Add New Product
    </a>

    <a
        class="button"
        href="{{ url_for('admin_orders') }}"
    >
        📋 Admin Orders
    </a>

    <a
        class="button"
        href="{{ url_for('admin_logout') }}"
    >
        🚪 Logout
    </a>

</div>

{% if products %}

<div class="products">

    {% for product in products %}

    <div class="card">

        <img
            src="{{ url_for(
                'static',
                filename='images/' + product.image
            ) }}"
            alt="{{ product.name }}"
        >

        <h2>
            {{ product.name }}
        </h2>

        <p>

            <strong>
                Category:
            </strong>

            {{ product.category }}

        </p>

        <p class="price">
            ₹{{ product.price }}
        </p>

        <p>
            {{ product.description }}
        </p>

        <a
            class="button edit"
            href="{{ url_for(
                'admin_edit_product',
                product_id=product.id
            ) }}"
        >
            ✏️ Edit
        </a>

        <a
            class="button delete"
            href="{{ url_for(
                'admin_delete_product',
                product_id=product.id
            ) }}"
            onclick="return confirm(
                'Are you sure you want to delete this product?'
            );"
        >
            🗑️ Delete
        </a>

    </div>

    {% endfor %}

</div>

{% else %}

<div class="empty">

    No products available.

</div>

{% endif %}

</body>

</html>

"""


@app.route("/admin/products")
def admin_products():

    if not require_admin():
        return redirect(url_for("login"))

    load_products_from_database()

    return render_template_string(
        ADMIN_PRODUCTS_HTML,
        products=PRODUCTS
    )


# ==================================================
# ADMIN EDIT PRODUCT
# ==================================================

ADMIN_EDIT_PRODUCT_HTML = """

<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Edit Product</title>

    <style>

        body {

            font-family: Arial, sans-serif;

            background: #f5f5f5;

            margin: 0;

        }

        .header {

            background: #333;

            color: white;

            padding: 20px;

            text-align: center;

        }

        .container {

            width: 450px;

            max-width: 90%;

            margin: 35px auto;

            background: white;

            padding: 25px;

            border-radius: 12px;

            box-shadow:
                0 4px 15px rgba(0,0,0,0.12);

        }

        label {

            display: block;

            font-weight: bold;

            margin-top: 14px;

        }

        input,
        textarea {

            width: 100%;

            box-sizing: border-box;

            padding: 10px;

            margin-top: 6px;

            border: 1px solid #ccc;

            border-radius: 6px;

        }

        textarea {

            height: 100px;

            resize: vertical;

        }

        button,
        .back {

            display: inline-block;

            padding: 11px 16px;

            margin-top: 20px;

            border: none;

            border-radius: 6px;

            text-decoration: none;

            cursor: pointer;

            font-size: 15px;

        }

        button {

            background: #333;

            color: white;

        }

        .back {

            background: #ddd;

            color: #333;

            margin-left: 8px;

        }

        .success {

            color: #155724;

            background: #d4edda;

            padding: 10px;

            border-radius: 6px;

            margin-bottom: 12px;

        }

        .error {

            color: #721c24;

            background: #f8d7da;

            padding: 10px;

            border-radius: 6px;

            margin-bottom: 12px;

        }

        .current-image {

            margin-top: 10px;

            width: 140px;

            height: 110px;

            object-fit: contain;

            border: 1px solid #ddd;

            border-radius: 8px;

        }

        .small-links {

            margin-top: 20px;

        }

    </style>

</head>

<body>

<div class="header">

    <h1>Edit Product</h1>

</div>

<div class="container">

    {% if success %}

        <div class="success">
            {{ success }}
        </div>

    {% endif %}

    {% if error %}

        <div class="error">
            {{ error }}
        </div>

    {% endif %}

    <form
        method="POST"
        enctype="multipart/form-data"
    >

        <label>
            Product Name
        </label>

        <input
            type="text"
            name="name"
            value="{{ product.name }}"
            required
        >

        <label>
            Price (₹)
        </label>

        <input
            type="number"
            name="price"
            value="{{ product.price }}"
            step="0.01"
            min="0.01"
            required
        >

        <label>
            Category
        </label>

        <input
            type="text"
            name="category"
            value="{{ product.category }}"
            required
        >

        <label>
            Description
        </label>

        <textarea
            name="description"
            required
        >{{ product.description }}</textarea>

        <label>
            Current Image
        </label>

        <img
            class="current-image"
            src="{{ url_for(
                'static',
                filename='images/' + product.image
            ) }}"
            alt="{{ product.name }}"
        >

        <label>
            New Image (optional)
        </label>

        <input
            type="file"
            name="image"
            accept=".jpg,.jpeg,.png,.gif,.webp"
        >

        <button type="submit">
            💾 Save Changes
        </button>

        <a
            class="back"
            href="{{ url_for('admin_products') }}"
        >
            ← Back
        </a>

    </form>

    <div class="small-links">

        <a href="{{ url_for('admin_orders') }}">
            📋 Admin Orders
        </a>

    </div>

</div>

</body>

</html>

"""


@app.route(
    "/admin/edit_product/<int:product_id>",
    methods=["GET", "POST"]
)
def admin_edit_product(product_id):

    if not require_admin():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            price,
            category,
            image,
            description,
            rating
        FROM products
        WHERE id = ?
    """, (
        product_id,
    ))

    row = cursor.fetchone()

    if not row:

        conn.close()

        return "Product not found", 404

    product = dict(row)

    error = ""
    success = ""

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        price_text = request.form.get(
            "price",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        image = request.files.get(
            "image"
        )

        price = None

        if (
            not name
            or not price_text
            or not category
            or not description
        ):

            error = (
                "Please fill all the fields."
            )

        else:

            try:

                price = float(
                    price_text
                )

                if price <= 0:
                    raise ValueError

            except ValueError:

                error = (
                    "Please enter a valid positive price."
                )

        # Duplicate name check

        if not error:

            cursor.execute("""
                SELECT id
                FROM products
                WHERE LOWER(name) = LOWER(?)
                AND id != ?
            """, (
                name,
                product_id
            ))

            duplicate = cursor.fetchone()

            if duplicate:

                error = (
                    "A product with this name "
                    "already exists. "
                    "Please use another name."
                )

        new_image = product["image"]

        # Optional new image

        if (
            not error
            and image
            and image.filename
        ):

            filename = secure_filename(
                image.filename
            )

            extension = (
                filename.rsplit(
                    ".",
                    1
                )[-1].lower()
                if "." in filename
                else ""
            )

            if (
                not filename
                or extension
                not in ALLOWED_IMAGE_EXTENSIONS
            ):

                error = (
                    "Only JPG, JPEG, PNG, GIF "
                    "or WEBP images are allowed."
                )

            else:

                new_image = (
                    str(
                        random.randint(
                            100000,
                            999999999
                        )
                    )
                    + "_"
                    + filename
                )

                image.save(
                    os.path.join(
                        app.config[
                            "PRODUCT_IMAGE_FOLDER"
                        ],
                        new_image
                    )
                )

        if not error:

            cursor.execute("""
                UPDATE products
                SET
                    name = ?,
                    price = ?,
                    category = ?,
                    image = ?,
                    description = ?
                WHERE id = ?
            """, (
                name,
                price,
                category,
                new_image,
                description,
                product_id
            ))

            conn.commit()

            product.update({

                "name": name,

                "price": price,

                "category": category,

                "image": new_image,

                "description": description

            })

            success = (
                "Product updated successfully!"
            )

    conn.close()

    if not error and success:

        load_products_from_database()

    return render_template_string(
        ADMIN_EDIT_PRODUCT_HTML,
        product=product,
        error=error,
        success=success
    )


# ==================================================
# ADMIN DELETE PRODUCT
# ==================================================

@app.route(
    "/admin/delete_product/<int:product_id>"
)
def admin_delete_product(product_id):

    if not require_admin():
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT image FROM products WHERE id = ?",
        (product_id,)
    )

    existing = cursor.fetchone()

    if not existing:

        conn.close()

        return "Product not found", 404

    image_filename = existing["image"]

    # Delete wishlist records
    cursor.execute(
        "DELETE FROM wishlist WHERE product_id = ?",
        (product_id,)
    )

    # Delete review records
    cursor.execute(
        "DELETE FROM reviews WHERE product_id = ?",
        (product_id,)
    )

    # Delete product
    cursor.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    # Remove uploaded image file
    if image_filename:

        image_path = os.path.join(
            app.config["PRODUCT_IMAGE_FOLDER"],
            image_filename
        )

        original_images = {
            product["image"]
            for product in DEFAULT_PRODUCTS
        }

        if (
            image_filename not in original_images
            and os.path.exists(image_path)
        ):

            try:
                os.remove(image_path)
            except OSError:
                pass

    load_products_from_database()

    return redirect(
        url_for("admin_products")
    )


# ==================================================
# START APPLICATION
# ==================================================

create_database()

load_products_from_database()

if __name__ == "__main__":

    create_database()

    load_products_from_database()

    app.run(debug=True)