import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.tools.postgres import PostgresTools
from agno.models.groq import Groq

# Load environment variables
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is not set in environment or .env file")
os.environ["GROQ_API_KEY"] = api_key

# Initialize PostgresTools
postgres_tools = PostgresTools(
    db_name='planmans',
    user='planmans',
    password='Ls4LEZ#c!u',
    host='216.225.193.213',
    port='5432'
)

# Create the agent
agent = Agent(
    tools=[postgres_tools],
    model=Groq(id="qwen-qwq-32b"),
    instructions="""
You are a PostgreSQL assistant for all tables in the `planmans` database. Perform CRUD operations (create, read, update, delete) with these guidelines:
- Work with any specified table, using provided column names and values.
- **Create**: Insert records with user-provided column-value pairs using INSERT.
- **Read**: Retrieve records (all or by a condition, e.g., ID) and display in a formatted table.
- **Update**: Modify records by a condition (e.g., ID) with provided fields using UPDATE.
- **Delete**: Remove records by a condition (e.g., ID) using DELETE.
- If the database is read-only, report the issue and suggest checking permissions, transaction settings, or primary node status.
- Handle errors clearly, asking for clarification if input is ambiguous.
- Use table metadata (e.g., from show_tables()) to validate columns if needed.
"""
)

def get_tables():
    try:
        response = agent.print_response("list all the the data from the table name hotels_bankdetail")


        # For simplicity, we expect a list or string of table names
        return response.split() if isinstance(response, str) else []
    except Exception as e:
        print(f"Error fetching tables: {str(e)}")
        return []

def execute_operation(table, operation, fields=None, condition=None):
    if operation == "create":
        field_str = ", ".join([f"{key} '{value}'" for key, value in fields.items()])
        command = f"Insert a record into {table} with {field_str}"
    elif operation == "read":
        command = f"Show all records in {table}" if not condition else f"Show records in {table} where {condition}"
    elif operation == "update":
        field_str = ", ".join([f"{key} '{value}'" for key, value in fields.items()])
        command = f"Update {table} set {field_str} where {condition}"
    elif operation == "delete":
        command = f"Delete from {table} where {condition}"
    else:
        return "Invalid operation."

    print(f"Executing: {command}")
    try:
        agent.print_response(command)
    except Exception as e:
        print(f"Error: {str(e)}")
        if "read-only" in str(e).lower():
            print("Database is read-only. Please check:")
            print("- Permissions: GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO planmans;")
            print("- Transaction: Ensure not in read-only mode.")
            print("- Database: Verify primary node (SELECT pg_is_in_recovery(); should return false).")

def main():
    print("PostgreSQL Database Management (CRUD Operations for All Tables)")
    
    # Fetch and display available tables
    tables = get_tables()
    if not tables:
        print("No tables found or error accessing database.")
        return
    print("\nAvailable tables:", ", ".join(tables))
    print("Operations: create, read, update, delete, exit")

    while True:
        table = input("\nEnter table name (or 'exit' to quit): ").strip().lower()
        if table == "exit":
            print("Goodbye!")
            break
        if table not in tables:
            print(f"Table '{table}' not found. Available tables: {', '.join(tables)}")
            continue

        operation = input("Enter operation (create/read/update/delete): ").strip().lower()
        if operation not in ["create", "read", "update", "delete"]:
            print("Invalid operation. Choose: create, read, update, delete")
            continue

        if operation == "create":
            print(f"Enter column values for {table} (type 'done' when finished):")
            fields = {}
            while True:
                column = input("Column name (or 'done'): ").strip()
                if column.lower() == "done":
                    break
                value = input(f"Value for {column}: ").strip()
                fields[column] = value
            if not fields:
                print("At least one field is required.")
                continue
            print("\nData to insert:")
            print("| Column | Value |")
            print("|--------|-------|")
            for k, v in fields.items():
                print(f"| {k} | {v} |")
            if input("Proceed? (yes/no): ").strip().lower() == "yes":
                execute_operation(table, "create", fields=fields)

        elif operation == "read":
            condition = input("Enter condition (e.g., id=1, or press Enter for all): ").strip()
            execute_operation(table, "read", condition=condition if condition else None)

        elif operation == "update":
            condition = input("Enter condition (e.g., id=1): ").strip()
            if not condition:
                print("Condition is required (e.g., id=1).")
                continue
            print(f"Enter columns to update for {table} (type 'done' when finished):")
            fields = {}
            while True:
                column = input("Column name (or 'done'): ").strip()
                if column.lower() == "done":
                    break
                value = input(f"New value for {column}: ").strip()
                fields[column] = value
            if not fields:
                print("At least one field is required.")
                continue
            print("\nFields to update:")
            print("| Column | Value |")
            print("|--------|-------|")
            for k, v in fields.items():
                print(f"| {k} | {v} |")
            if input("Proceed? (yes/no): ").strip().lower() == "yes":
                execute_operation(table, "update", fields=fields, condition=condition)

        elif operation == "delete":
            condition = input("Enter condition (e.g., id=1): ").strip()
            if not condition:
                print("Condition is required (e.g., id=1).")
                continue
            print(f"\nDeleting from {table} where {condition}")
            if input("Proceed? (yes/no): ").strip().lower() == "yes":
                execute_operation(table, "delete", condition=condition)

if __name__ == "__main__":
    main()