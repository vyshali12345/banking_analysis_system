
import mysql.connector

def get_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="aimlb4",
        database="banking_analysis"
    )
    return connection


if __name__ == "__main__":
    try:
        conn = get_connection()
        print("MySQL connected successfully!")

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions")
        result = cursor.fetchone()

        print("Total transactions:", result[0])

        cursor.close()
        conn.close()

    except mysql.connector.Error as error:
        print("Database connection failed:", error)
