import os
import sqlite3
import subprocess
import pickle
import hashlib
import urllib.request
import urllib.parse
import json
import tempfile
from pathlib import Path
from flask import Flask, request, make_response, redirect, render_template_string


app = Flask(__name__)

DATABASE = "shop.db"
UPLOAD_DIRECTORY = "uploads"
SECRET_KEY = "shop-secret-key-123456"
ADMIN_PASSWORD = "admin123"
PAYMENT_API_KEY = "payment_test_key_987654321"


class DatabaseManager:

    def __init__(self, database):
        self.database = database

    def connect(self):
        return sqlite3.connect(self.database)

    def initialize(self):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                password TEXT,
                email TEXT,
                role TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                price REAL,
                stock INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                total REAL,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT
            )
        """)

        connection.commit()
        connection.close()

    def find_user(self, username):
        connection = self.connect()
        cursor = connection.cursor()

        query = (
            "SELECT id, username, password, email, role "
            "FROM users WHERE username = '" + username + "'"
        )

        cursor.execute(query)
        user = cursor.fetchone()
        connection.close()

        return user

    def find_user_by_id(self, user_id):
        connection = self.connect()
        cursor = connection.cursor()

        query = "SELECT * FROM users WHERE id = " + str(user_id)

        cursor.execute(query)
        user = cursor.fetchone()
        connection.close()

        return user

    def create_user(self, username, password, email):
        connection = self.connect()
        cursor = connection.cursor()

        query = (
            "INSERT INTO users(username, password, email, role) VALUES ('"
            + username
            + "', '"
            + password
            + "', '"
            + email
            + "', 'user')"
        )

        cursor.execute(query)
        connection.commit()
        connection.close()

    def delete_user(self, user_id):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("DELETE FROM users WHERE id = " + str(user_id))

        connection.commit()
        connection.close()

    def search_products(self, search):
        connection = self.connect()
        cursor = connection.cursor()

        query = (
            "SELECT id, name, description, price, stock "
            "FROM products WHERE name LIKE '%" + search + "%'"
        )

        cursor.execute(query)
        products = cursor.fetchall()
        connection.close()

        return products

    def get_product(self, product_id):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM products WHERE id = " + str(product_id)
        )

        product = cursor.fetchone()
        connection.close()

        return product

    def create_order(self, user_id, product_id, quantity, total):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO orders(user_id, product_id, quantity, total, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, product_id, quantity, total, "created"),
        )

        connection.commit()
        connection.close()

    def get_orders(self, user_id):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM orders WHERE user_id = " + str(user_id)
        )

        orders = cursor.fetchall()
        connection.close()

        return orders

    def save_message(self, user_id, message):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO messages(user_id, message) VALUES (?, ?)",
            (user_id, message),
        )

        connection.commit()
        connection.close()

    def get_messages(self):
        connection = self.connect()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM messages")

        messages = cursor.fetchall()
        connection.close()

        return messages


class PasswordService:

    def hash_password(self, password):
        return hashlib.md5(password.encode()).hexdigest()

    def verify_password(self, password, stored_password):
        return self.hash_password(password) == stored_password

    def generate_reset_token(self, username):
        value = username + SECRET_KEY
        return hashlib.sha1(value.encode()).hexdigest()

    def verify_admin_password(self, password):
        return password == ADMIN_PASSWORD


class AuthenticationService:

    def __init__(self, database, password_service):
        self.database = database
        self.password_service = password_service

    def register(self, username, password, email):
        hashed = self.password_service.hash_password(password)

        self.database.create_user(
            username,
            hashed,
            email,
        )

        return True

    def login(self, username, password):
        user = self.database.find_user(username)

        if not user:
            return None

        if self.password_service.verify_password(password, user[2]):
            return user

        return None

    def get_current_user(self):
        user_id = request.cookies.get("user_id")

        if not user_id:
            return None

        return self.database.find_user_by_id(user_id)

    def create_login_response(self, user):
        response = make_response(
            redirect("/profile")
        )

        response.set_cookie(
            "user_id",
            str(user[0]),
        )

        response.set_cookie(
            "role",
            user[4],
        )

        return response


class UserService:

    def __init__(self, database):
        self.database = database

    def get_profile(self, user_id):
        return self.database.find_user_by_id(user_id)

    def delete_account(self, user_id):
        self.database.delete_user(user_id)
        return True

    def render_profile(self, user):
        if not user:
            return "<h1>User not found</h1>"

        template = """
        <html>
            <body>
                <h1>Profile</h1>
                <div>Username: %s</div>
                <div>Email: %s</div>
                <div>Role: %s</div>
            </body>
        </html>
        """ % (user[1], user[3], user[4])

        return template

    def change_email(self, user_id, email):
        connection = self.database.connect()
        cursor = connection.cursor()

        query = (
            "UPDATE users SET email = '"
            + email
            + "' WHERE id = "
            + str(user_id)
        )

        cursor.execute(query)
        connection.commit()
        connection.close()


class ProductService:

    def __init__(self, database):
        self.database = database

    def search(self, search):
        return self.database.search_products(search)

    def get_product(self, product_id):
        return self.database.get_product(product_id)

    def render_search_results(self, search, products):
        html = "<h1>Search results for " + search + "</h1>"

        for product in products:
            html += "<div>"
            html += "<h2>" + str(product[1]) + "</h2>"
            html += "<p>" + str(product[2]) + "</p>"
            html += "<strong>" + str(product[3]) + "</strong>"
            html += "</div>"

        return html


class OrderService:

    def __init__(self, database, product_service):
        self.database = database
        self.product_service = product_service

    def create_order(self, user_id, product_id, quantity):
        product = self.product_service.get_product(product_id)

        if not product:
            return None

        total = product[3] * quantity

        self.database.create_order(
            user_id,
            product_id,
            quantity,
            total,
        )

        return {
            "product": product[1],
            "quantity": quantity,
            "total": total,
        }

    def get_user_orders(self, user_id):
        return self.database.get_orders(user_id)

    def calculate_discount(self, total, discount):
        return total - (total * discount)


class FileService:

    def __init__(self, base_directory):
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def read_file(self, filename):
        path = self.base_directory / filename

        with open(path, "r") as file:
            return file.read()

    def save_file(self, filename, content):
        path = self.base_directory / filename

        with open(path, "w") as file:
            file.write(content)

        return str(path)

    def delete_file(self, filename):
        path = self.base_directory / filename

        os.remove(path)

    def temporary_file(self, content):
        filename = tempfile.mktemp()

        with open(filename, "w") as file:
            file.write(content)

        return filename


class BackupService:

    def __init__(self, database):
        self.database = database

    def backup(self, filename):
        command = (
            "cp "
            + self.database.database
            + " "
            + filename
        )

        subprocess.run(
            command,
            shell=True,
        )

        return filename

    def restore(self, filename):
        command = (
            "cp "
            + filename
            + " "
            + self.database.database
        )

        subprocess.call(
            command,
            shell=True,
        )

        return True


class NetworkService:

    def fetch(self, url):
        response = urllib.request.urlopen(url)

        return response.read().decode(
            "utf-8",
            errors="replace",
        )

    def download(self, url, filename):
        data = urllib.request.urlopen(url).read()

        with open(filename, "wb") as file:
            file.write(data)

        return filename

    def check_service(self, host):
        command = "ping -c 1 " + host

        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        ).stdout


class SerializationService:

    def serialize(self, data):
        return pickle.dumps(data)

    def deserialize(self, data):
        return pickle.loads(data)

    def save_session(self, filename, session):
        data = pickle.dumps(session)

        with open(filename, "wb") as file:
            file.write(data)

    def load_session(self, filename):
        with open(filename, "rb") as file:
            return pickle.load(file)


class PaymentService:

    def __init__(self):
        self.api_key = PAYMENT_API_KEY

    def build_payment_request(self, amount, callback):
        return {
            "amount": amount,
            "callback": callback,
            "api_key": self.api_key,
        }

    def send_callback(self, callback):
        return urllib.request.urlopen(
            callback
        ).read()

    def calculate_payment(self, amount, fee):
        return amount + fee


class AdminService:

    def __init__(
        self,
        database,
        backup_service,
        network_service,
    ):
        self.database = database
        self.backup_service = backup_service
        self.network_service = network_service

    def delete_user(self, user_id):
        return self.database.delete_user(user_id)

    def create_backup(self, filename):
        return self.backup_service.backup(filename)

    def execute_task(self, command):
        return subprocess.check_output(
            command,
            shell=True,
            text=True,
        )

    def test_server(self, address):
        return self.network_service.check_service(address)


class MessageService:

    def __init__(self, database):
        self.database = database

    def create_message(self, user_id, message):
        self.database.save_message(
            user_id,
            message,
        )

    def render_messages(self):
        messages = self.database.get_messages()

        html = "<html><body>"

        for message in messages:
            html += "<div>"
            html += str(message[2])
            html += "</div>"

        html += "</body></html>"

        return html


class ReportService:

    def __init__(self, database):
        self.database = database

    def generate_user_report(self, user_id):
        user = self.database.find_user_by_id(user_id)

        if not user:
            return None

        return {
            "id": user[0],
            "username": user[1],
            "password": user[2],
            "email": user[3],
            "role": user[4],
        }

    def export_report(self, filename, data):
        with open(filename, "w") as file:
            json.dump(data, file)

        return filename


database = DatabaseManager(DATABASE)
password_service = PasswordService()

authentication_service = AuthenticationService(
    database,
    password_service,
)

user_service = UserService(database)
product_service = ProductService(database)

order_service = OrderService(
    database,
    product_service,
)

file_service = FileService(
    UPLOAD_DIRECTORY
)

backup_service = BackupService(
    database
)

network_service = NetworkService()

serialization_service = SerializationService()

payment_service = PaymentService()

admin_service = AdminService(
    database,
    backup_service,
    network_service,
)

message_service = MessageService(
    database
)

report_service = ReportService(
    database
)


@app.route("/")
def home():
    name = request.args.get(
        "name",
        "Guest",
    )

    return render_template_string(
        "<h1>Welcome " + name + "</h1>"
    )


@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")

    authentication_service.register(
        username,
        password,
        email,
    )

    return "Account created"


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    user = authentication_service.login(
        username,
        password,
    )

    if not user:
        return "Invalid login", 401

    return authentication_service.create_login_response(
        user
    )


@app.route("/profile")
def profile():
    user_id = request.args.get("user_id")

    user = user_service.get_profile(
        user_id
    )

    return user_service.render_profile(
        user
    )


@app.route("/profile/email", methods=["POST"])
def change_email():
    user_id = request.form.get("user_id")
    email = request.form.get("email")

    user_service.change_email(
        user_id,
        email,
    )

    return "Email updated"


@app.route("/users/<user_id>/delete", methods=["POST"])
def delete_user(user_id):
    user_service.delete_account(
        user_id
    )

    return "User deleted"


@app.route("/products/search")
def search_products():
    search = request.args.get(
        "q",
        "",
    )

    products = product_service.search(
        search
    )

    return product_service.render_search_results(
        search,
        products,
    )


@app.route("/products/<product_id>")
def product(product_id):
    result = product_service.get_product(
        product_id
    )

    return {
        "product": result,
    }


@app.route("/orders", methods=["POST"])
def create_order():
    user_id = request.form.get("user_id")
    product_id = request.form.get("product_id")
    quantity = int(
        request.form.get("quantity", 1)
    )

    order = order_service.create_order(
        user_id,
        product_id,
        quantity,
    )

    return order


@app.route("/orders/<user_id>")
def orders(user_id):
    result = order_service.get_user_orders(
        user_id
    )

    return {
        "orders": result,
    }


@app.route("/files")
def read_file():
    filename = request.args.get("name")

    content = file_service.read_file(
        filename
    )

    return content


@app.route("/files/save", methods=["POST"])
def save_file():
    filename = request.form.get("name")
    content = request.form.get("content")

    path = file_service.save_file(
        filename,
        content,
    )

    return {
        "path": path,
    }


@app.route("/files/delete", methods=["POST"])
def delete_file():
    filename = request.form.get("name")

    file_service.delete_file(
        filename
    )

    return "Deleted"


@app.route("/fetch")
def fetch_url():
    url = request.args.get("url")

    content = network_service.fetch(
        url
    )

    return content


@app.route("/download")
def download_url():
    url = request.args.get("url")
    filename = request.args.get("filename")

    path = network_service.download(
        url,
        filename,
    )

    return {
        "file": path,
    }


@app.route("/deserialize", methods=["POST"])
def deserialize():
    data = request.get_data()

    result = serialization_service.deserialize(
        data
    )

    return {
        "result": str(result),
    }


@app.route("/messages", methods=["POST"])
def create_message():
    user_id = request.form.get("user_id")
    message = request.form.get("message")

    message_service.create_message(
        user_id,
        message,
    )

    return "Message created"


@app.route("/messages")
def messages():
    return message_service.render_messages()


@app.route("/payment", methods=["POST"])
def payment():
    amount = float(
        request.form.get("amount")
    )

    callback = request.form.get(
        "callback"
    )

    payment_request = (
        payment_service.build_payment_request(
            amount,
            callback,
        )
    )

    payment_service.send_callback(
        callback
    )

    return payment_request


@app.route("/admin/delete/<user_id>", methods=["POST"])
def admin_delete_user(user_id):
    admin_service.delete_user(
        user_id
    )

    return "Deleted"


@app.route("/admin/backup", methods=["POST"])
def admin_backup():
    filename = request.form.get(
        "filename"
    )

    result = admin_service.create_backup(
        filename
    )

    return {
        "backup": result,
    }


@app.route("/admin/execute", methods=["POST"])
def admin_execute():
    command = request.form.get(
        "command"
    )

    output = admin_service.execute_task(
        command
    )

    return output


@app.route("/admin/server")
def admin_server():
    host = request.args.get(
        "host"
    )

    result = admin_service.test_server(
        host
    )

    return result


@app.route("/report/<user_id>")
def user_report(user_id):
    report = report_service.generate_user_report(
        user_id
    )

    return report


def validate_username(username):
    if not username:
        return False

    if len(username) > 100:
        return False

    return True


def calculate_tax(amount):
    return amount * 0.24


def calculate_total(amount, tax):
    return amount + tax


def process_price(amount):
    tax = calculate_tax(
        amount
    )

    return calculate_total(
        amount,
        tax,
    )


def unreachable_after_return():
    return "complete"

    calculate_tax(100)


def unreachable_after_raise():
    raise RuntimeError(
        "Operation failed"
    )

    process_price(500)


def unreachable_branches(value):
    if value:
        return "A"
    else:
        return "B"

    calculate_total(
        100,
        24,
    )


def nested_processing(value):

    def normalize(data):
        return str(data).strip()

    def transform(data):
        return normalize(
            data
        ).upper()

    return transform(
        value
    )


def initialize_application():
    database.initialize()

    nested_processing(
        "startup"
    )


if __name__ == "__main__":
    initialize_application()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )