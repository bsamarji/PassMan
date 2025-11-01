import base64
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .config import DB_DIR_NAME, SECURITY_DIR_NAME, SALT_FILE_NAME, PEK_FILE_NAME
from .config import COLOR_WARNING, COLOR_ERROR, COLOR_PROMPT_BOLD, COLOR_PROMPT_LIGHT, COLOR_SUCCESS
import click
import sys


def initialise_security_dir():
    """
    Initialise the security directory.
    """
    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    try:
        Path.mkdir(security_dir, parents=True, exist_ok=True)
    except OSError as e:
        click.secho(f"Error creating security directory at {security_dir}: {e}", **COLOR_ERROR)
        sys.exit(1)

def generate_salt_file():
    """
    Generate a random salt and write it to a file, if a salt file doesn't exist.
    """
    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    salt_file = security_dir / SALT_FILE_NAME
    if not salt_file.exists():
        salt = os.urandom(16)
        try:
            with open(salt_file, "wb") as f:
                f.write(salt)
        except IOError as e:
            click.secho(f"Error writing salt file to {salt_file}: {e}", **COLOR_ERROR)
            sys.exit(1)


def retrieve_salt():
    """
    Retrieve the salt from the salt file.

    Returns:
         The salt (bytes) or None on failure.
    """
    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    salt_file = security_dir / SALT_FILE_NAME
    try:
        with open(salt_file, "rb") as f:
            salt = f.read()
        if not salt:
            click.secho(f"Salt file is empty: {salt_file}", **COLOR_ERROR)
            sys.exit(1)
        return salt
    except FileNotFoundError:
        click.secho(f"Salt file not found at {salt_file}. Run setup first.", **COLOR_ERROR)
        sys.exit(1)
    except IOError as e:
        click.secho(f"Error reading salt file: {e}", **COLOR_ERROR)
        sys.exit(1)


def key_derivation_function(salt):
    """
    Define a key derivation function that uses the salt from the salt file.

    Args:
        salt (bytes): The salt from the salt file

    Returns:
        The key derivation function
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=1_200_000,
    )
    return kdf


def login():
    """
    Login to the password manager.

    Returns:
         The master password (str).
    """
    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    pek_file = security_dir / PEK_FILE_NAME

    if not pek_file.exists():
        click.secho("Welcome to PassMan! Initial setup required.", **COLOR_WARNING)
        master_password = click.prompt(
            click.style("Please create your master password", **COLOR_PROMPT_BOLD),
            hide_input=True,
            confirmation_prompt=True,
        )
        # Check for empty password
        if not master_password:
            click.secho("Master password cannot be empty.", **COLOR_ERROR)
            sys.exit(1)
        return master_password
    else:
        master_password = click.prompt(
            click.style("Please enter your master password", **COLOR_PROMPT_BOLD),
            hide_input=True,
            confirmation_prompt=True,
        )
        return master_password


def prompt_new_master_password():
    """
    Prompts the user for a new master password.

    Returns:
         The new master password (str).
    """
    master_password = click.prompt(
        click.style("\nPlease enter your new master password", **COLOR_PROMPT_BOLD),
        hide_input=True,
        confirmation_prompt=True,
    )
    # Check for empty password
    if not master_password:
        click.secho("Master password cannot be empty.", **COLOR_ERROR)
        sys.exit(1)
    if click.confirm(click.style("Ready to save your new master password?", **COLOR_PROMPT_LIGHT)):
        click.secho("Successfully updated master password!", **COLOR_SUCCESS)
    else:
        click.secho("Operation cancelled.", **COLOR_WARNING)
        click.Abort()
    return master_password


def generate_derived_key(kdf, master_password):
    """
    Create derived key using the given kdf and master password.

    Args:
        kdf: The key derivation function to use
        master_password: The master password to use

    Returns:
        The derived key (bytes)
    """
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return key


def generate_pek():
    """
    Generate a cryptographically strong PEK.
    """
    pek = os.urandom(32)
    return pek


def encrypt_pek(derived_key, pek):
    """
    Takes Primary Encryption Key (PEK) and locks it
    by encrypting it with the derived key (Key Encryption Key - KEK) using Fernet.
    Stores the encrypted PEK to disk.

    Args:
        derived_key (bytes): The 44-byte base64url-encoded key from the KDF.
        pek (bytes): The PEK to encrypt

    Returns:
        The decrypted PEK (bytes) or None on failure.
    """
    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    pek_file = security_dir / PEK_FILE_NAME

    try:
        f = Fernet(derived_key)
    except ValueError as e:
        click.secho(f"Internal error: Invalid Fernet key generated: {e}", **COLOR_ERROR)
        sys.exit(1)

    # 1. Encrypt the PEK
    try:
        encrypted_pek = f.encrypt(pek)
    except Exception as e:
        click.secho(f"Internal error: Failed to encrypt PEK: {e}", **COLOR_ERROR)
        sys.exit(1)

    # 2. Store the Encrypted PEK
    try:
        with open(pek_file, "wb") as file:
            file.write(encrypted_pek)
    except IOError as e:
        click.secho(f"Critical error: Failed to write PEK file: {e}", **COLOR_ERROR)
        sys.exit(1)

    return pek


def retrieve_and_decrypt_pek(derived_key):
    """
    Retrieve the PEK and decrypt it using Fernet.

    Args:
        derived_key (bytes): The derived key (KEK) to use

    Returns:
        The decrypted primary encryption key (PEK) (bytes) or None on failure.
    """
    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    pek_file = security_dir / PEK_FILE_NAME

    # 1. Retrieve the Encrypted PEK
    try:
        with open(pek_file, "rb") as file:
            encrypted_pek = file.read()
    except FileNotFoundError:
        click.secho(f"PEK file not found at {pek_file}. Run setup first.", **COLOR_ERROR)
        return None
    except IOError as e:
        click.secho(f"Error reading PEK file: {e}", **COLOR_ERROR)
        return None

    # 2. Initialize Fernet
    try:
        f = Fernet(derived_key)
    except ValueError as e:
        click.secho(f"Internal error: Invalid Fernet key generated: {e}", **COLOR_ERROR)
        return None

    # 3. Decrypt the PEK
    try:
        pek = f.decrypt(encrypted_pek)
        return pek
    except InvalidToken:
        click.secho("The master password is incorrect. Please try again.", **COLOR_ERROR)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Unknown decryption error: {e}", **COLOR_ERROR)
        sys.exit(1)
