import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from database.db import get_connection

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = BASE_DIR / "knowledge_base"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

client = None
if GEMINI_API_KEY:
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=45000),
    )

ALLOWED_TABLES = {
    "employees",
    "departments",
    "assets",
    "asset_categories",
    "allocations",
    "maintenance",
}

# This schema is based on the user's uploaded chatbot code.
SCHEMA = """
employees:
  employee_id, full_name, email, job_title, employment_status, department_id

departments:
  department_id, department_name

asset_categories:
  category_id, category_name, description

assets:
  asset_id, asset_name, category_id, brand, model,
  purchase_date, warranty_expiry, asset_status, created_at

allocations:
  allocation_id, asset_id, employee_id,
  assigned_date, returned_date, allocation_notes

maintenance:
  maintenance_id, asset_id, issue_title, issue_description,
  reported_date, maintenance_status, technician_name

Relationships:
  employees.department_id = departments.department_id
  assets.category_id = asset_categories.category_id
  allocations.employee_id = employees.employee_id
  allocations.asset_id = assets.asset_id
  maintenance.asset_id = assets.asset_id

Rules:
  A current allocation has returned_date IS NULL.
  Active maintenance has maintenance_status Open or In Progress.
  Never invent records.
"""

# ============================================================
# GEMINI HELPERS
# ============================================================

def gemini_text(prompt):
    if client is None:
        raise RuntimeError("Gemini API key is not configured.")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"temperature": 0.2},
    )

    answer = (response.text or "").strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty response.")
    return answer


def gemini_json(prompt):
    if client is None:
        raise RuntimeError("Gemini API key is not configured.")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    )

    result = (response.text or "").strip()
    if not result:
        raise RuntimeError("Gemini returned an empty response.")

    result = re.sub(r"^\s*```(?:json)?\s*", "", result)
    result = re.sub(r"\s*```\s*$", "", result)
    return json.loads(result)

def validate_sql(sql):
    """
    Validate Gemini-generated SQL.
    Only one SELECT query using approved tables is allowed.
    """

    import sqlglot
    from sqlglot import exp

    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("No SQL query was generated.")

    parsed = sqlglot.parse(sql, read="mysql")

    if len(parsed) != 1 or parsed[0] is None:
        raise ValueError("Only one SQL statement is allowed.")

    tree = parsed[0]

    if not isinstance(tree, exp.Select):
        raise ValueError("Only SELECT queries are allowed.")

    allowed_tables = {
        "employees",
        "departments",
        "assets",
        "asset_categories",
        "allocations",
        "maintenance"
    }

    tables = {
        table.name.lower()
        for table in tree.find_all(exp.Table)
    }

    if not tables or not tables.issubset(allowed_tables):
        raise ValueError("Unapproved database table.")

    if tree.args.get("into") is not None:
        raise ValueError("SELECT INTO is not allowed.")

    if tree.args.get("locks"):
        raise ValueError("Locking queries are not allowed.")

    if tree.args.get("limit") is None:
        tree = tree.limit(100)

    return tree.sql(dialect="mysql")



# ============================================================
# DATABASE QUERY EXECUTION
# ============================================================

def run_read_query(sql, params=None):
    """Run a read-only query and return rows as dictionaries."""
    connection = get_connection()
    if connection is None:
        raise RuntimeError("Could not connect to the MySQL database.")

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()

        cleaned_rows = []
        for row in rows:
            cleaned_rows.append({
                key: value.isoformat() if hasattr(value, "isoformat") else value
                for key, value in row.items()
            })
        return cleaned_rows
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


# ============================================================
# DIRECT DATABASE ANSWERS
# Common questions do not need a Gemini request.
# ============================================================

def _format_rows(rows, heading, max_rows=25):
    if not rows:
        return f"No {heading.lower()} were found in the database."

    output = [f"{heading} ({len(rows)} record(s)):"]
    for index, row in enumerate(rows[:max_rows], start=1):
        output.append(f"\nRecord {index}:")
        for key, value in row.items():
            label = key.replace("_", " ").title()
            output.append(f"{label}: {value}")
    if len(rows) > max_rows:
        output.append(f"\nShowing the first {max_rows} records.")
    return "\n".join(output)


def answer_database_directly(question):
    """Handle common database questions. Return None if not recognized."""
    q = question.lower().strip()

    # Employee count
    if (
        ("employee" in q or "employees" in q or "staff" in q)
        and any(word in q for word in ("how many", "count", "total", "number"))
    ):
        rows = run_read_query(
            "SELECT COUNT(*) AS total_employees FROM employees"
        )
        return f"There are {rows[0]['total_employees']} employees registered in the database."

    # Available assets
    if (
        ("available asset" in q or "assets available" in q)
        and any(word in q for word in ("show", "list", "what", "all", "available"))
    ):
        rows = run_read_query(
            """
            SELECT asset_id, asset_name, brand, model, asset_status
            FROM assets
            WHERE LOWER(asset_status) = 'available'
            ORDER BY asset_id
            LIMIT 100
            """
        )
        return _format_rows(rows, "Available assets")

    # Asset ID in the question
    asset_match = re.search(
        r"\b(?:LAP|DES|MON|PRN|NET)-\d{3}\b",
        question.upper(),
    )

    if asset_match:
        asset_id = asset_match.group(0)

        # Who is using / assigned this asset?
        if any(word in q for word in (
            "who", "using", "holder", "allocated", "assigned",
            "employee", "person", "belongs to",
        )):
            rows = run_read_query(
                """
                SELECT
                    a.asset_id,
                    a.asset_name,
                    a.asset_status,
                    e.employee_id,
                    e.full_name,
                    al.assigned_date
                FROM assets a
                LEFT JOIN allocations al
                    ON a.asset_id = al.asset_id
                    AND al.returned_date IS NULL
                LEFT JOIN employees e
                    ON al.employee_id = e.employee_id
                WHERE a.asset_id = %s
                ORDER BY al.assigned_date DESC
                LIMIT 10
                """,
                (asset_id,),
            )

            if not rows:
                return f"Asset {asset_id} was not found in the database."

            current = [row for row in rows if row.get("employee_id")]
            if not current:
                return f"{asset_id} ({rows[0]['asset_name']}) has no current employee allocation."

            return "\n".join(
                f"{row['asset_id']} ({row['asset_name']}) is currently allocated "
                f"to {row['full_name']} ({row['employee_id']})."
                for row in current
            )

        # General asset details
        rows = run_read_query(
            """
            SELECT
                a.asset_id, a.asset_name, a.brand, a.model,
                a.asset_status, a.purchase_date, a.warranty_expiry,
                c.category_name
            FROM assets a
            LEFT JOIN asset_categories c ON a.category_id = c.category_id
            WHERE a.asset_id = %s
            LIMIT 1
            """,
            (asset_id,),
        )
        if rows:
            return _format_rows(rows, f"Details for {asset_id}")
        return f"Asset {asset_id} was not found in the database."

    # Maintenance records
    if "maintenance" in q:
        if any(word in q for word in ("active", "open", "pending", "ongoing", "in progress")):
            rows = run_read_query(
                """
                SELECT maintenance_id, asset_id, issue_title,
                       issue_description, reported_date,
                       maintenance_status, technician_name
                FROM maintenance
                WHERE maintenance_status IN ('Open', 'In Progress')
                ORDER BY reported_date DESC
                LIMIT 100
                """
            )
            return _format_rows(rows, "Active maintenance records")

        rows = run_read_query(
            """
            SELECT maintenance_id, asset_id, issue_title,
                   issue_description, reported_date,
                   maintenance_status, technician_name
            FROM maintenance
            ORDER BY reported_date DESC
            LIMIT 100
            """
        )
        return _format_rows(rows, "Maintenance records")

    # Department listing
    if "department" in q and any(word in q for word in ("show", "list", "all", "what")):
        rows = run_read_query(
            "SELECT department_id, department_name FROM departments ORDER BY department_name"
        )
        return _format_rows(rows, "Departments")

    return None


# ============================================================
# QUESTION CLASSIFICATION AND SQL GENERATION
# ============================================================


def understand_question(question):

    prompt = f"""
You are AssetIQ, an intelligent IT Asset Management
assistant that converts natural-language questions into
safe MySQL SELECT queries.

Understand the USER QUESTION by its meaning, not just
by matching exact keywords.

Return valid JSON only in this format:

{{
    "mode": "database",
    "sql": "SELECT ...",
    "reason": "short explanation"
}}

AVAILABLE MODES:

database = questions about actual database records.
policy = questions about company policies.
mixed = questions requiring database and policy information.
general = greetings and general AssetIQ questions.
unsupported = unrelated questions.

DATABASE SCHEMA:

employees:
employee_id, full_name, email, job_title,
employment_status, department_id

departments:
department_id, department_name

asset_categories:
category_id, category_name, description

assets:
asset_id, asset_name, category_id, brand, model,
purchase_date, warranty_expiry, asset_status, created_at

allocations:
allocation_id, asset_id, employee_id,
assigned_date, returned_date, allocation_notes

maintenance:
maintenance_id, asset_id, issue_title,
issue_description, reported_date, maintenance_status,
technician_name

TABLE RELATIONSHIPS:

employees.department_id = departments.department_id
assets.category_id = asset_categories.category_id
allocations.employee_id = employees.employee_id
allocations.asset_id = assets.asset_id
maintenance.asset_id = assets.asset_id

IMPORTANT BUSINESS RULES:

1. A current allocation has returned_date IS NULL.
2. Active maintenance statuses are Open and In Progress.
3. Use JOIN when information comes from multiple tables.
4. Use LIKE for employee names or asset names when appropriate.
5. Use case-insensitive matching for names.
6. Understand synonyms and conversational wording.
7. "Has", "using", "holds", "assigned", and "allocated"
   can refer to an employee's current asset.
8. "Who has this laptop?" means find its current employee.
9. "Which laptop does this employee have?" means find
   the employee's currently allocated assets.
10. If the user asks for previous or returned allocations,
    do not filter them as current allocations.
11. Use the correct database columns only.
12. Never invent records or values.
13. Never generate INSERT, UPDATE, DELETE, DROP,
    ALTER, CREATE or other modification queries.
14. Generate exactly one SELECT statement.
15. Use LIMIT 100 for list queries.
16. For database questions, never return an empty SQL query.

EXAMPLES:

Question:
Which laptop does Sneha Desai have?

SQL:
SELECT a.asset_id, a.asset_name, a.brand, a.model
FROM employees e
JOIN allocations al ON e.employee_id = al.employee_id
JOIN assets a ON al.asset_id = a.asset_id
WHERE e.full_name LIKE '%Sneha Desai%'
AND al.returned_date IS NULL
LIMIT 100

Question:
Who is currently using LAP-102?

SQL:
SELECT e.employee_id, e.full_name, a.asset_id, a.asset_name
FROM assets a
JOIN allocations al ON a.asset_id = al.asset_id
JOIN employees e ON al.employee_id = e.employee_id
WHERE a.asset_id = 'LAP-102'
AND al.returned_date IS NULL
LIMIT 100

Question:
Show me all laptops that are available.

SQL:
SELECT asset_id, asset_name, brand, model, asset_status
FROM assets
WHERE asset_status = 'Available'
AND asset_name LIKE '%Laptop%'
LIMIT 100

Question:
Which assets need repair?

SQL:
SELECT a.asset_id, a.asset_name, m.issue_title,
m.maintenance_status, m.technician_name
FROM assets a
JOIN maintenance m ON a.asset_id = m.asset_id
WHERE m.maintenance_status IN ('Open', 'In Progress')
LIMIT 100

Question:
How many employees work in each department?

SQL:
SELECT d.department_name, COUNT(e.employee_id) AS total_employees
FROM departments d
LEFT JOIN employees e ON d.department_id = e.department_id
GROUP BY d.department_id, d.department_name
LIMIT 100

Question:
Show all assets assigned to employees.

SQL:
SELECT e.full_name, a.asset_id, a.asset_name,
al.assigned_date
FROM employees e
JOIN allocations al ON e.employee_id = al.employee_id
JOIN assets a ON al.asset_id = a.asset_id
WHERE al.returned_date IS NULL
LIMIT 100

USER QUESTION:
{question}

Return JSON only. Do not include Markdown.
"""

    return gemini_json(prompt)


# ============================================================
# RAG - POLICY DOCUMENT RETRIEVAL
# ============================================================

def retrieve_policy_context(question, max_chunks=4):
    """Retrieve relevant passages from .txt and .md knowledge-base files."""
    if not DOCUMENTS_DIR.exists():
        return ""

    stop_words = {
        "the", "and", "for", "are", "was", "were", "what", "when",
        "where", "which", "who", "how", "does", "can", "could",
        "would", "should", "this", "that", "with", "from", "have",
        "has", "about", "tell", "give", "show", "please", "explain",
        "you", "your", "asset", "assets",
    }

    question_words = {
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9]+", question)
        if len(word) > 2 and word.lower() not in stop_words
    }
    if not question_words:
        return ""

    candidates = []
    for file_path in DOCUMENTS_DIR.rglob("*"):
        if file_path.suffix.lower() not in {".txt", ".md"}:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        paragraphs = [
            part.strip()
            for part in re.split(r"\n\s*\n", content)
            if part.strip()
        ]

        for paragraph in paragraphs:
            words = {
                word.lower()
                for word in re.findall(r"[a-zA-Z0-9]+", paragraph)
                if len(word) > 2
            }
            overlap = len(question_words.intersection(words))
            if overlap:
                score = overlap / max(len(question_words), 1)
                candidates.append((score, file_path.name, paragraph[:1800]))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[:max_chunks]

    return "\n\n".join(
        f"Source document: {name}\nPassage: {passage}"
        for score, name, passage in selected
    )


# ============================================================
# KNOWLEDGE GRAPH - MYSQL-BACKED RELATIONSHIPS
# ============================================================

def retrieve_graph_context(question):
    """
    Build a small relationship graph from actual MySQL records.
    This is a MySQL-backed graph representation, not a Neo4j database.
    """
    asset_match = re.search(
        r"\b(?:LAP|DES|MON|PRN|NET)-\d{3}\b",
        question.upper(),
    )
    employee_match = re.search(r"\bEMP-\d{3}\b", question.upper())

    if not asset_match and not employee_match:
        return ""

    graph = {"nodes": [], "relationships": []}

    if asset_match:
        rows = run_read_query(
            """
            SELECT a.asset_id, a.asset_name, a.asset_status,
                   e.employee_id, e.full_name, d.department_name
            FROM assets a
            LEFT JOIN allocations al
                ON a.asset_id = al.asset_id
                AND al.returned_date IS NULL
            LEFT JOIN employees e ON al.employee_id = e.employee_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE a.asset_id = %s
            """,
            (asset_match.group(0),),
        )

        for row in rows:
            graph["nodes"].append({
                "type": "Asset",
                "id": row["asset_id"],
                "name": row["asset_name"],
                "status": row["asset_status"],
            })
            if row.get("employee_id"):
                graph["nodes"].append({
                    "type": "Employee",
                    "id": row["employee_id"],
                    "name": row["full_name"],
                })
                graph["relationships"].append({
                    "from": row["employee_id"],
                    "relationship": "ALLOCATED_TO",
                    "to": row["asset_id"],
                })
            if row.get("department_name") and row.get("employee_id"):
                graph["nodes"].append({
                    "type": "Department",
                    "name": row["department_name"],
                })
                graph["relationships"].append({
                    "from": row["employee_id"],
                    "relationship": "WORKS_IN",
                    "to": row["department_name"],
                })

    if employee_match:
        rows = run_read_query(
            """
            SELECT e.employee_id, e.full_name, d.department_name,
                   a.asset_id, a.asset_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN allocations al
                ON e.employee_id = al.employee_id
                AND al.returned_date IS NULL
            LEFT JOIN assets a ON al.asset_id = a.asset_id
            WHERE e.employee_id = %s
            """,
            (employee_match.group(0),),
        )

        for row in rows:
            graph["nodes"].append({
                "type": "Employee",
                "id": row["employee_id"],
                "name": row["full_name"],
            })
            if row.get("department_name"):
                graph["nodes"].append({
                    "type": "Department",
                    "name": row["department_name"],
                })
                graph["relationships"].append({
                    "from": row["employee_id"],
                    "relationship": "WORKS_IN",
                    "to": row["department_name"],
                })
            if row.get("asset_id"):
                graph["nodes"].append({
                    "type": "Asset",
                    "id": row["asset_id"],
                    "name": row["asset_name"],
                })
                graph["relationships"].append({
                    "from": row["employee_id"],
                    "relationship": "ALLOCATED_TO",
                    "to": row["asset_id"],
                })

    # Remove duplicate nodes and edges while preserving order.
    graph["nodes"] = list({
        json.dumps(item, sort_keys=True): item for item in graph["nodes"]
    }.values())
    graph["relationships"] = list({
        json.dumps(item, sort_keys=True): item
        for item in graph["relationships"]
    }.values())

    if not graph["nodes"]:
        return ""
    return json.dumps(graph, indent=2, default=str)


# ============================================================
# ANSWER FORMATTING AND GROUNDED GENERATION
# ============================================================

def format_database_answer(question, rows, graph_context=""):
    if not rows:
        answer = "No matching records were found in the AssetIQ MySQL database."
    elif len(rows) == 1 and len(rows[0]) == 1:
        key, value = next(iter(rows[0].items()))
        answer = f"{key.replace('_', ' ').title()}: {value}"
    else:
        answer = _format_rows(rows, "Matching database records")

    if graph_context:
        try:
            graph = json.loads(graph_context)
            relationships = graph.get("relationships", [])
            if relationships:
                answer += "\n\nKnowledge graph relationships:"
                for edge in relationships:
                    answer += (
                        f"\n{edge['from']} "
                        f"--{edge['relationship']}--> {edge['to']}"
                    )
        except (ValueError, TypeError, KeyError):
            pass

    return answer.strip()


def create_grounded_answer(question, database_rows, policy_context, graph_context):
    prompt = f"""
You are AssetIQ, an IT Asset Management assistant.

Answer the user's question clearly and naturally.

Strict rules:
- MySQL results are the source of truth for actual records.
- Never invent employee names, asset IDs, dates, statuses or counts.
- Make policy claims only when supported by the retrieved policy passages.
- Use the supplied relationship graph to explain employee, asset and department links.
- If a source does not contain the answer, say that it was not found.
- Do not expose SQL, API keys or passwords.
- Do not claim to use Neo4j. The supplied graph was constructed from MySQL data.

USER QUESTION:
{question}

MYSQL RESULTS:
{json.dumps(database_rows, indent=2, default=str)}

RETRIEVED POLICY PASSAGES:
{policy_context or "No relevant policy passages were retrieved."}

RELATIONSHIP GRAPH:
{graph_context or "No matching graph relationships were retrieved."}

Provide the final answer.
"""
    return gemini_text(prompt)
def answer_relationship_directly(question):
    """Answer employee/asset relationship questions without Gemini."""

    q = question.lower()

    relationship_words = (
        "relationship", "connected", "assigned",
        "allocated", "using", "belongs to",
        "department", "works in", "linked"
    )

    if not any(word in q for word in relationship_words):
        return None

    has_id = (
        re.search(r"\b(?:LAP|DES|MON|PRN|NET)-\d{3}\b", question.upper())
        or re.search(r"\bEMP-\d{3}\b", question.upper())
    )

    if not has_id:
        return None

    graph_context = retrieve_graph_context(question)

    if not graph_context:
        return "No matching employee, asset or department relationships were found in MySQL."

    graph = json.loads(graph_context)

    answer = ["Knowledge Graph Results:"]

    for node in graph.get("nodes", []):
        if node.get("type") == "Employee":
            answer.append(
                f"Employee: {node.get('name')} ({node.get('id')})"
            )
        elif node.get("type") == "Asset":
            answer.append(
                f"Asset: {node.get('name')} ({node.get('id')})"
            )
        elif node.get("type") == "Department":
            answer.append(
                f"Department: {node.get('name')}"
            )

    answer.append("\nRelationships:")

    for edge in graph.get("relationships", []):
        answer.append(
            f"{edge['from']} --{edge['relationship']}--> {edge['to']}"
        )

    if not graph.get("relationships"):
        answer.append("No relationship records were found for this entity.")

    return "\n".join(answer)
def answer_policy_directly(question):
    """Return relevant policy passages directly from knowledge_base."""

    q = question.lower()

    policy_words = (
    "policy",
    "warranty",
    "procedure",
    "rules",
    "guidelines",
    "allocation",
    "transfer",
    "return",
    "overdue",
    "preventive",
    "priority",
    "inspection",
    "disposal",
    "inventory",
    "security",
    "data protection",
    "software"
)
    if not any(word in q for word in policy_words):
        return None

    context = retrieve_policy_context(question)

    if not context:
        return (
            "I could not find relevant information in the policy documents. "
            "Please check knowledge_base/asset_policy.txt."
        )

    return (
        "Information retrieved from the AssetIQ knowledge base:\n\n"
        + context
    )


# ============================================================
# MAIN CHATBOT FUNCTION
# ============================================================

def answer_question(question):
    if not isinstance(question, str) or not question.strip():
        return "Please enter a question."

    question = question.strip()
    if len(question) > 4000:
        return "Please ask a shorter question."

    question_lower = question.lower().strip(" .!?")

    greetings = {
        "hi", "hello", "hey", "hii", "good morning",
        "good afternoon", "good evening", "thanks", "thank you",
    }
    if question_lower in greetings:
        return (
            "Hello! I am AssetIQ, your IT Asset Management Assistant. "
            "Ask me about assets, employees, allocations, departments, "
            "maintenance, warranties and policies."
        )
        # Handle relationship questions using the MySQL-backed graph.
    try:
        graph_answer = answer_relationship_directly(question)
        if graph_answer is not None:
            return graph_answer

        # Handle policy questions using local document retrieval.
        policy_answer = answer_policy_directly(question)
        if policy_answer is not None:
            return policy_answer

    except Exception as error:
        print("Local retrieval error:", repr(error))
        return "Unable to retrieve the requested information from the knowledge base."

    # 1. Handle common database questions without Gemini.
    try:
        direct_answer = answer_database_directly(question)
        if direct_answer is not None:
            return direct_answer
    except Exception as error:
        print("AssetIQ direct database error:", repr(error))
        return "I could not retrieve those records from MySQL. Check the Flask terminal for the database error."

    # 2. General questions can be answered locally.
    if any(term in question_lower for term in (
        "what is assetiq", "what can you do", "what do you do",
        "explain assetiq", "who are you",
    )):
        return (
            "AssetIQ is an IT Asset Management assistant. It uses MySQL "
            "records for asset and employee information, retrieves relevant "
            "policy passages from the knowledge base using RAG, and builds "
            "a relationship graph from employee, department and asset records."
        )

    if client is None:
        return (
            "Gemini is not configured. Common database questions can still "
            "be answered, but flexible natural-language questions require "
            "a valid GEMINI_API_KEY in your local .env file."
        )

    try:
        # 3. Classify the question and generate SQL only when required.
        plan = understand_question(question)
        mode = str(plan.get("mode", "unsupported")).lower()
        sql = plan.get("sql", "")

        if mode == "unsupported":
            return (
                "I can help with IT assets, employees, departments, "
                "allocations, maintenance and asset policies."
            )

        if mode == "general":
            return (
                "I am AssetIQ, an IT Asset Management assistant. "
                "I can retrieve records from MySQL, search policy documents "
                "using RAG, and explain relationships between employees, "
                "departments and assets."
            )

        # 4. Retrieve policy passages for policy and mixed questions.
        policy_context = ""
        if mode in {"policy", "mixed"}:
            policy_context = retrieve_policy_context(question)

        # 5. Run validated read-only SQL for database and mixed questions.
        database_rows = []
        if mode in {"database", "mixed"}:
            safe_sql = validate_sql(sql)
            database_rows = run_read_query(safe_sql)

        # 6. Retrieve graph relationships when an ID is present and
        #    the question asks about a relationship.
        graph_context = ""
        relationship_terms = (
            "relationship", "connected", "assigned to", "allocated to",
            "who is using", "who uses", "belongs to", "department of",
            "works in", "linked to",
        )
        has_entity_id = bool(
            re.search(r"\b(?:LAP|DES|MON|PRN|NET)-\d{3}\b", question.upper())
            or re.search(r"\bEMP-\d{3}\b", question.upper())
        )
        if has_entity_id and any(term in question_lower for term in relationship_terms):
            graph_context = retrieve_graph_context(question)

        # 7. Database-only answers do not need a second Gemini call.
        if mode == "database":
            return format_database_answer(question, database_rows, graph_context)

        # 8. Policy and mixed answers are grounded in retrieved sources.
        if mode in {"policy", "mixed"}:
            if mode == "policy" and not policy_context:
                return (
                    "I could not find a relevant passage in the knowledge_base "
                    "documents. Add the applicable policy to asset_policy.txt "
                    "and ask again."
                )
            return create_grounded_answer(
                question,
                database_rows,
                policy_context,
                graph_context,
            )

        return "Please ask a question related to IT asset management."

    except Exception as error:
        print("AssetIQ chatbot error:", repr(error))
        return (
            "I encountered a problem while processing that question. "
            "Please check the Flask terminal for the technical error."
        )
