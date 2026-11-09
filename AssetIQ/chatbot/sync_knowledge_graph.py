
from database.db import fetch_all
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([URI, USERNAME, PASSWORD]):
    raise RuntimeError("Configure Neo4j settings in your .env file.")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
driver.verify_connectivity()

def sync():
    with driver.session() as session:

        # Departments
        departments = fetch_all("""
            SELECT department_id, department_name
            FROM departments
        """)

        for row in departments:
            session.run("""
                MERGE (d:Department {department_id: $id})
                SET d.department_name = $name
            """, id=row["department_id"], name=row["department_name"])

        # Employees and department relationships
        employees = fetch_all("""
            SELECT employee_id, full_name, email, job_title,
                   employment_status, department_id
            FROM employees
        """)

        for row in employees:
            session.run("""
                MERGE (e:Employee {employee_id: $id})
                SET e.full_name = $name,
                    e.email = $email,
                    e.job_title = $job,
                    e.employment_status = $status
                WITH e
                MATCH (d:Department {department_id: $department_id})
                MERGE (e)-[:WORKS_IN]->(d)
            """,
                id=row["employee_id"],
                name=row["full_name"],
                email=row["email"],
                job=row["job_title"],
                status=row["employment_status"],
                department_id=row["department_id"]
            )

        # Assets
        assets = fetch_all("""
            SELECT a.asset_id, a.asset_name, a.asset_status,
                   a.brand, a.model, c.category_name
            FROM assets a
            LEFT JOIN asset_categories c
                ON a.category_id = c.category_id
        """)

        for row in assets:
            session.run("""
                MERGE (a:Asset {asset_id: $id})
                SET a.asset_name = $name,
                    a.asset_status = $status,
                    a.brand = $brand,
                    a.model = $model
                WITH a
                OPTIONAL MATCH (c:Category {category_name: $category})
                FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
                    MERGE (a)-[:BELONGS_TO]->(c)
                )
            """,
                id=row["asset_id"],
                name=row["asset_name"],
                status=row["asset_status"],
                brand=row["brand"],
                model=row["model"],
                category=row["category_name"]
            )

            if row["category_name"]:
                session.run("""
                    MERGE (c:Category {category_name: $category})
                """, category=row["category_name"])

                session.run("""
                    MATCH (a:Asset {asset_id: $asset_id})
                    MATCH (c:Category {category_name: $category})
                    MERGE (a)-[:BELONGS_TO]->(c)
                """,
                    asset_id=row["asset_id"],
                    category=row["category_name"]
                )

        # Allocation relationships, including historical allocations
        allocations = fetch_all("""
            SELECT allocation_id, asset_id, employee_id,
                   assigned_date, returned_date, allocation_notes
            FROM allocations
        """)

        for row in allocations:
            session.run("""
                MATCH (e:Employee {employee_id: $employee_id})
                MATCH (a:Asset {asset_id: $asset_id})
                MERGE (e)-[r:ALLOCATED_TO {
                    allocation_id: $allocation_id
                }]->(a)
                SET r.assigned_date = $assigned_date,
                    r.returned_date = $returned_date,
                    r.active = ($returned_date IS NULL),
                    r.notes = $notes
            """,
                employee_id=row["employee_id"],
                asset_id=row["asset_id"],
                allocation_id=row["allocation_id"],
                assigned_date=str(row["assigned_date"]),
                returned_date=(
                    str(row["returned_date"])
                    if row["returned_date"] else None
                ),
                notes=row["allocation_notes"]
            )

        # Maintenance records
        maintenance = fetch_all("""
            SELECT maintenance_id, asset_id, issue_title,
                   maintenance_status, reported_date, technician_name
            FROM maintenance
        """)

        for row in maintenance:
            session.run("""
                MATCH (a:Asset {asset_id: $asset_id})
                MERGE (m:Maintenance {
                    maintenance_id: $maintenance_id
                })
                SET m.issue_title = $issue,
                    m.maintenance_status = $status,
                    m.reported_date = $reported_date,
                    m.technician_name = $technician
                MERGE (a)-[:HAS_MAINTENANCE]->(m)
            """,
                asset_id=row["asset_id"],
                maintenance_id=row["maintenance_id"],
                issue=row["issue_title"],
                status=row["maintenance_status"],
                reported_date=str(row["reported_date"]),
                technician=row["technician_name"]
            )

    print("AssetIQ Knowledge Graph synchronisation completed.")

try:
    sync()
finally:
    driver.close()
