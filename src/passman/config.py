# --- COLOR SCHEME DEFINITIONS ---
COLOR_ERROR = dict(fg="red", bold=True)  # Critical failure, security warnings, irreversible actions
COLOR_SUCCESS = dict(fg="green", bold=True)  # Successful operation, generated passwords
COLOR_PROMPT_BOLD = dict(fg="cyan", bold=True)  # Primary prompts (username, password)
COLOR_PROMPT_LIGHT = dict(fg="cyan")  # Secondary/optional prompts (URL, note)
COLOR_WARNING = dict(fg="yellow")  # Non-fatal warnings, operation cancelled, secondary notes
COLOR_HEADER = dict(fg="magenta", bold=True)  # Table headers, main information headers
COLOR_PRIMARY_DATA = dict(fg="white")  # Non-sensitive primary data (timestamps, username)
COLOR_SENSITIVE_DATA = dict(fg="green")  # Highly sensitive data (passwords in view)

# --- DB FILE PATHS ---
DB_FILE_NAME = "passman.db"
DB_DIR_NAME = ".passman"

# --- SECURITY FILE NAMES ---
SECURITY_DIR_NAME = ".security"
SALT_FILE_NAME = "passman.salt"
PEK_FILE_NAME = "passman.key"

# --- SESSION CONFIG ---
SESSION_FILE_NAME = "passman.session"
SESSION_TIMEOUT_SECONDS = 3600

# --- COMMAND CONFIG ---
COMMANDS_VALID_NO_ARGS = ['list', 'login', 'logout', 'help']

# --- PASSWORD GENERATOR CONFIG ---
PASSWORD_LENGTH = 20
PASSWORD_SPECIAL_CHARS = "!@#$%^&*"

# --- DB QUERIES ---
SQL_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    service_name TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    url TEXT NULL,
    note TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
"""

SQL_INSERT_ENTRY = """
INSERT INTO entries (
    service_name,
    username,
    password,
    url,
    note
    )
VALUES (
    ?,
    ?,
    ?,
    ?,
    ?
    );
"""

SQL_VIEW_ENTRY = """
SELECT service_name,
    username,
    password,
    url,
    note,
    created_at,
    updated_at
FROM entries
WHERE service_name = ?
"""

SQL_SEARCH = """
SELECT service_name,
    url,
    note,
    created_at,
    updated_at
FROM entries
WHERE service_name LIKE ?
"""

SQL_LIST = """
SELECT service_name,
    url,
    note,
    created_at,
    updated_at
FROM entries
"""

SQL_UPDATE_ENTRY = """
UPDATE entries
SET password = ?,
    updated_at = datetime()
WHERE service_name = ?;
"""

SQL_DELETE_ENTRY = """
DELETE FROM entries
WHERE service_name = ?;
"""

SQL_VALIDATE_SERVICE_NAME = """
SELECT service_name
FROM entries
WHERE service_name = ?
"""