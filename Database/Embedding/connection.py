import psycopg2
from pgvector.psycopg2 import register_vector

def connect_to_postgres(env):
    """
    Connect to PostgreSQL database
    """
    try:
        # Connection parameters
        connection = psycopg2.connect(
            host=env["DBHOSTNAME"],
            database=env["DBNAME"],
            user=env["DBUSERNAME"],
            password=env["DBPASS"],
            port=env["DBPORT"],
        )
        
        # register_vector(connection)
        print("Successfully connected to database")
        return connection

    except psycopg2.Error as error:
        print(f"Error connecting to PostgreSQL: {error}")
        return None


