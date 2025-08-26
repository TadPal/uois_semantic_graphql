import psycopg2


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

        print("Successfully connected to database")
        return connection

    except psycopg2.Error as error:
        print(f"Error connecting to PostgreSQL: {error}")
        return None
