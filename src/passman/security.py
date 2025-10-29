import base64
import os
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .config import DB_DIR_NAME, SALT_FILE_NAME

def generate_salt_file():
    """
    Generate a random salt and write it to a file, if a salt file doesn't exist.
    """
    home_dir = Path.home()
    db_dir = home_dir / DB_DIR_NAME
    salt_file = db_dir / SALT_FILE_NAME
    if not salt_file.exists():
        salt = os.urandom(16)
        with open(salt_file, "wb") as f:
            f.write(salt)

def retrieve_salt():
    """
    Retrieve the salt from the salt file.
    Returns the salt.
    """
    home_dir = Path.home()
    db_dir = home_dir / DB_DIR_NAME
    salt_file = db_dir / SALT_FILE_NAME
    with open(salt_file, "rb") as f:
        salt = f.read()
    return salt

def key_derivation_function(salt):
    """
    Define a key derivation function that uses the salt from the salt file.
    Returns the key derivation function.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=1_200_000,
    )
    return kdf