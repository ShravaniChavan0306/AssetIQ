
from flask import Flask, render_template, request, jsonify

from database.db import fetch_all, get_connection
from chatbot.mysql_chatbot import answer_question


app = Flask(__name__)


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def database_is_connected():
    """Check whether the MySQL database is reachable."""
    connection = get_connection()

    if connection is None:
        return False

    try:
        return connection.is_connected()
    finally:
        connection.close()


def database_error():
    return jsonify({
        "error": "Unable to connect to the AssetIQ MySQL database. Check the MySQL server and database configuration."
    }), 503


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# DASHBOARD API
# --------------------------------------------------

@app.route("/api/dashboard")
def dashboard():

    if not database_is_connected():
        return database_error()

    totals = fetch_all("""
        SELECT
            COUNT(*) AS total_assets,
            SUM(asset_status = 'Assigned') AS assigned,
            SUM(asset_status = 'Available') AS available,
            SUM(asset_status = 'Under Maintenance') AS maintenance
        FROM assets
    """)

    if not totals:
        return jsonify({"error": "Unable to retrieve dashboard statistics."}), 500

    categories_data = fetch_all("""
        SELECT
            c.category_name,
            COUNT(a.asset_id) AS asset_count
        FROM asset_categories c
        LEFT JOIN assets a ON c.category_id = a.category_id
        GROUP BY c.category_id, c.category_name
        ORDER BY c.category_name
    """)

    recent_assets = fetch_all("""
        SELECT
            a.asset_id AS id,
            a.asset_name AS name,
            c.category_name AS category,
            e.full_name AS employee,
            d.department_name AS department,
            a.asset_status AS status
        FROM assets a
        LEFT JOIN asset_categories c
            ON a.category_id = c.category_id
        LEFT JOIN allocations al
            ON a.asset_id = al.asset_id
            AND al.returned_date IS NULL
        LEFT JOIN employees e
            ON al.employee_id = e.employee_id
        LEFT JOIN departments d
            ON e.department_id = d.department_id
        ORDER BY a.created_at DESC
        LIMIT 5
    """)

    stats = totals[0]

    return jsonify({
        "total_assets": int(stats["total_assets"] or 0),
        "assigned": int(stats["assigned"] or 0),
        "available": int(stats["available"] or 0),
        "maintenance": int(stats["maintenance"] or 0),
        "categories": {
            item["category_name"]: int(item["asset_count"])
            for item in categories_data
        },
        "recent_assets": recent_assets
    })


# --------------------------------------------------
# EMPLOYEE API
# --------------------------------------------------

@app.route("/api/employees")
def get_employees():

    if not database_is_connected():
        return database_error()

    employees = fetch_all("""
        SELECT
            e.employee_id AS id,
            e.full_name AS name,
            e.email,
            e.job_title,
            e.employment_status,
            d.department_name AS department
        FROM employees e
        LEFT JOIN departments d
            ON e.department_id = d.department_id
        ORDER BY e.full_name
    """)

    return jsonify(employees)


# --------------------------------------------------
# ASSET API
# --------------------------------------------------

@app.route("/api/assets")
def get_assets():

    if not database_is_connected():
        return database_error()

    assets = fetch_all("""
        SELECT
            a.asset_id AS id,
            a.asset_name AS name,
            c.category_name AS category,
            d.department_name AS department,
            e.employee_id AS employee_id,
            e.full_name AS employee,
            a.asset_status AS status,
            a.brand,
            a.model,
            a.warranty_expiry
        FROM assets a
        LEFT JOIN asset_categories c
            ON a.category_id = c.category_id
        LEFT JOIN allocations al
            ON a.asset_id = al.asset_id
            AND al.returned_date IS NULL
        LEFT JOIN employees e
            ON al.employee_id = e.employee_id
        LEFT JOIN departments d
            ON e.department_id = d.department_id
        ORDER BY a.asset_id
    """)

    return jsonify(assets)


# --------------------------------------------------
# MAINTENANCE API
# --------------------------------------------------

@app.route("/api/maintenance")
def get_maintenance():

    if not database_is_connected():
        return database_error()

    records = fetch_all("""
        SELECT
            m.maintenance_id AS id,
            m.asset_id AS asset,
            m.issue_title AS issue,
            m.reported_date AS date,
            m.maintenance_status AS status,
            m.technician_name AS technician
        FROM maintenance m
        ORDER BY m.reported_date DESC
    """)

    return jsonify(records)


# --------------------------------------------------
# MYSQL CHATBOT API
# --------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():

    if not database_is_connected():
        return database_error()

    data = request.get_json(silent=True) or {}

    message = data.get("message", "")

    if not isinstance(message, str):
        return jsonify({"error": "Invalid message format."}), 400

    message = message.strip()

    if not message:
        return jsonify({"error": "Please enter a question."}), 400

    if len(message) > 4000:
        return jsonify({"error": "Please enter a shorter question."}), 400

    try:
        # The chatbot retrieves factual answers from MySQL.
        answer = answer_question(message)

        return jsonify({
            "reply": answer,
            "source": "MySQL",
            "status": "success"
        })

    except Exception as error:
        app.logger.exception("AssetIQ chatbot error: %s", error)

        return jsonify({
            "error": "An error occurred while processing your database question. Please try again."
        }), 500


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health")
def health():

    connected = database_is_connected()

    return jsonify({
        "status": "running",
        "application": "AssetIQ",
        "database": "connected" if connected else "disconnected"
    }), (200 if connected else 503)


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    print("=" * 50)
    print("ASSETIQ - INTELLIGENT ASSET MANAGEMENT")
    print("=" * 50)

    if database_is_connected():
        print("MySQL database: CONNECTED")
    else:
        print("MySQL database: DISCONNECTED")

    print("Starting AssetIQ at http://127.0.0.1:5000")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
