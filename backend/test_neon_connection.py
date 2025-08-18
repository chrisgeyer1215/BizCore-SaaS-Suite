# test_neon_connection.py
import os
from decouple import config
import psycopg2
from urllib.parse import urlparse

def test_neon_connection():
    try:
        # Test using individual variables
        conn = psycopg2.connect(
            host=config('DB_HOST'),
            database=config('DB_NAME'),
            user=config('DB_USER'),
            password=config('DB_PASSWORD'),
            port=config('DB_PORT'),
            sslmode='require'
        )
        
        cur = conn.cursor()
        cur.execute('SELECT version();')
        version = cur.fetchone()
        print("✅ Database connection successful!")
        print(f"PostgreSQL version: {version[0]}")
        
        cur.execute('SELECT current_database();')
        db_name = cur.fetchone()
        print(f"Connected to database: {db_name[0]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    test_neon_connection()
