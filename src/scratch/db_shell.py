import sys
import os
from tabulate import tabulate
from sqlalchemy import text

sys.path.append("/Users/aryanbarnwal/Projects/GenAI Project/Sample/src")
from db import SessionLocal, engine

def run_query(query_str):
    db = SessionLocal()
    try:
        result = db.execute(text(query_str))
        if result.returns_rows:
            rows = result.fetchall()
            headers = result.keys()
            print(tabulate(rows, headers=headers, tablefmt="psql"))
        else:
            db.commit()
            print("Query executed successfully. No rows returned.")
    except Exception as e:
        print(f"❌ Error executing query: {e}")
    finally:
        db.close()

def show_menu():
    print("\n" + "="*50)
    print(f" 🗄️  DiversifyAI Database Shell ({engine.dialect.name.upper()})")
    print("="*50)
    print(" [1] View registered users (users table)")
    print(" [2] View active email subscribers (user_subscriptions table)")
    print(" [3] View raw user portfolios (user_portfolios table)")
    print(" [4] View historical daily advisor reports (daily_reports table)")
    print(" [5] View database table schemas")
    print(" [6] Run a custom SQL query")
    print(" [q] Exit")
    print("="*50)

def view_schemas():
    if engine.dialect.name == "sqlite":
        run_query("SELECT name, sql FROM sqlite_master WHERE type='table';")
    else:
        run_query("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)

def main():
    # Install tabulate dynamically if not present
    try:
        import tabulate
    except ImportError:
        import subprocess
        print("Installing tabulate for formatting...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tabulate"])
        from tabulate import tabulate

    while True:
        show_menu()
        choice = input("Enter choice: ").strip()
        if choice == "1":
            print("\n👤 Users:")
            run_query("SELECT id, email, created_at FROM users;")
        elif choice == "2":
            print("\n✉️ Subscribers:")
            run_query("SELECT id, user_id, email, is_active, model, SUBSTR(api_key, 1, 8) || '...' AS api_key_masked, created_at FROM user_subscriptions;")
        elif choice == "3":
            print("\n💼 Portfolios:")
            run_query("SELECT id, subscription_id, LENGTH(holdings_json) AS holdings_bytes, updated_at FROM user_portfolios;")
        elif choice == "4":
            print("\n📰 Historical Reports:")
            run_query("SELECT id, subscription_id, created_at FROM daily_reports;")
        elif choice == "5":
            print("\n📋 Table Schemas:")
            view_schemas()
        elif choice == "6":
            sql = input("Enter SQL Query: ").strip()
            if sql:
                run_query(sql)
        elif choice.lower() == "q":
            print("Goodbye!")
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    main()
