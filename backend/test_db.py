from db import get_connection

conn = get_connection()

if conn:
    print("Connected!")

    conn.close()