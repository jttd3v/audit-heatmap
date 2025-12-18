import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection_string():
    """Build MSSQL connection string based on environment variables."""
    server = os.getenv('DB_SERVER', 'localhost')
    database = os.getenv('DB_NAME', 'heatmapdb')
    trusted = os.getenv('DB_TRUSTED_CONNECTION', 'True').lower() == 'true'
    
    if trusted:
        # Windows Authentication
        return f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    else:
        # SQL Server Authentication
        user = os.getenv('DB_USER', 'sa')
        password = os.getenv('DB_PASSWORD', '')
        return f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={user};PWD={password};"


def get_db_connection():
    """Create and return a database connection."""
    conn_str = get_connection_string()
    return pyodbc.connect(conn_str)


def init_database():
    """Initialize the database and create tables if they don't exist."""
    # First, connect to master to create database if needed
    server = os.getenv('DB_SERVER', 'localhost')
    trusted = os.getenv('DB_TRUSTED_CONNECTION', 'True').lower() == 'true'
    
    if trusted:
        master_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=master;Trusted_Connection=yes;"
    else:
        user = os.getenv('DB_USER', 'sa')
        password = os.getenv('DB_PASSWORD', '')
        master_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=master;UID={user};PWD={password};"
    
    # Create database if not exists
    try:
        conn = pyodbc.connect(master_conn_str, autocommit=True)
        cursor = conn.cursor()
        
        db_name = os.getenv('DB_NAME', 'heatmapdb')
        cursor.execute(f"""
            IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}')
            BEGIN
                CREATE DATABASE [{db_name}]
            END
        """)
        conn.close()
        print(f"Database '{db_name}' verified/created successfully.")
    except Exception as e:
        print(f"Warning: Could not create database: {e}")
    
    # Now connect to the actual database and create tables
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create Audits table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Audits' AND xtype='U')
            BEGIN
                CREATE TABLE Audits (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    audit_type VARCHAR(20) NOT NULL CHECK (audit_type IN ('internal', 'external')),
                    title NVARCHAR(255) NOT NULL,
                    description NVARCHAR(MAX),
                    audit_date DATE NOT NULL,
                    created_at DATETIME DEFAULT GETDATE(),
                    updated_at DATETIME DEFAULT GETDATE()
                )
            END
        """)
        
        # Create index for faster date queries
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Audits_Date_Type')
            BEGIN
                CREATE INDEX IX_Audits_Date_Type ON Audits(audit_date, audit_type)
            END
        """)
        
        conn.commit()
        conn.close()
        print("Tables created successfully.")
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False


if __name__ == "__main__":
    init_database()
