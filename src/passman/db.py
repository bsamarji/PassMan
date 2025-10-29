import sqlcipher3.dbapi2 as sqlite3
from pathlib import Path
import click
import sys
from .config import *


def get_db_path():
    """
    Returns the cross-platform path to the SQLite database file.
    """
    home_dir = Path.home()
    db_dir = home_dir / DB_DIR_NAME
    try:
        Path.mkdir(db_dir, parents=True, exist_ok=True)
        return db_dir / DB_FILE_NAME
    except OSError as e:
        click.secho(
            f"Critical Error: Failed to create database directory at {db_dir}. Details: {e}",
            err=True,
            **COLOR_ERROR,
        )
        sys.exit(1)


def get_db_connection(pek):
    """
    Creates and returns a connection to the database.
    """
    db_path = get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        key_hex = pek.hex()
        conn.execute(f"PRAGMA key = \"x'{key_hex}'\";")
        return conn
    except sqlite3.Error as e:
        click.secho(
            f"Critical Error: Could not connect to the database at {db_path}. Details: {e}",
            err=True,
            **COLOR_ERROR,
        )
        sys.exit(1)


def initialise_db(pek):
    """
    Creates the 'entries' table if it does not already exist.
    """
    try:
        with get_db_connection(pek) as conn:
            conn.execute(SQL_CREATE_TABLE)
    except sqlite3.Error as e:
        click.secho(f"Could not initialise the database. Details: {e}", err=True, **COLOR_ERROR)
        sys.exit(1)


def add_entry(pek, service_name, username, password, url, note):
    """
    Insert a new entry into the database.
    """
    try:
        with get_db_connection(pek) as conn:
            conn.execute(
                SQL_INSERT_ENTRY, (service_name, username, password, url, note)
            )
    except sqlite3.Error as e:
        raise Exception(f"Could not insert entry for {service_name}. Details: {e}")


def view_entry(pek, service_name):
    """
    Retrieve information from the db for the requested entry and return a list containing a tuple.
    The output will be piped into the tabulate() func which requires a list of iterables.
    """
    try:
        with get_db_connection(pek) as conn:
            cur = conn.cursor()
            cur.execute(SQL_VIEW_ENTRY, (service_name,))
            row = cur.fetchmany(1)
            if len(row) == 0:
                click.secho(f"No entry was found with the service name: {service_name}", fg="yellow")
                sys.exit(0)
            return row
    except sqlite3.Error as e:
        raise Exception(f"Could not retrieve entry for {service_name}. Details: {e}")


def search(pek, search_term):
    """
    Retrieve information from the db for any service name that matches to the search term and return a list containing tuples.
    The output will be piped into the tabulate() func which requires a list of iterables.
    """
    search_pattern = f"%{search_term}%"

    try:
        with get_db_connection(pek) as conn:
            cur = conn.cursor()
            cur.execute(SQL_SEARCH, (search_pattern,))
            rows = cur.fetchall()
            if len(rows) == 0:
                click.secho(
                    f"No entries were found with service names that contain the search term: {search_term}",
                    fg="yellow",
                )
                sys.exit(0)
            return rows
    except sqlite3.Error as e:
        raise Exception(
            f"Could not retrieve any entries for {search_term}. Details: {e}"
        )


def list_entries(pek):
    """
    Retrieve information from the db for all service names and return a list containing tuples.
    The output will be piped into the tabulate() func which requires a list of iterables.
    """
    try:
        with get_db_connection(pek) as conn:
            cur = conn.cursor()
            cur.execute(SQL_LIST)
            rows = cur.fetchall()
            if len(rows) == 0:
                click.secho(
                    f"No entries are currently stored. Please add at least one entry",
                    fg="yellow",
                )
                sys.exit(0)
            return rows
    except sqlite3.Error as e:
        raise Exception(f"Could not retrieve all entries. Details: {e}")


def update_entry(pek, service_name, password):
    """
    Update the password for an entry in the database.
    """
    try:
        with get_db_connection(pek) as conn:
            conn.execute(
                SQL_UPDATE_ENTRY,
                (
                    password,
                    service_name,
                ),
            )
    except sqlite3.Error as e:
        raise Exception(f"Could not update the entry for {service_name}. Details: {e}")


def delete_entry(pek, service_name):
    """
    Delete an entry from the database.
    """
    try:
        with get_db_connection(pek) as conn:
            conn.execute(SQL_DELETE_ENTRY, (service_name,))
    except sqlite3.Error as e:
        raise Exception(f"Could not delete the entry for {service_name}. Details: {e}")


def validate_service_name(pek, service_name):
    """
    Validate that a record exists in the database using the passed service name.
    """
    try:
        with get_db_connection(pek) as conn:
            cur = conn.cursor()
            cur.execute(
                SQL_VALIDATE_SERVICE_NAME,
                (service_name,),
            )
            row = cur.fetchmany(1)
            if len(row) > 0:
                return True
            else:
                return False
    except sqlite3.Error as e:
        raise Exception(
            f"Could not validate the entry for {service_name}. Details: {e}"
        )
