import click
import tabulate
import sys
from pathlib import Path
import pyperclip
from . import db, security, session
from .config import (COLOR_SENSITIVE_DATA, COLOR_PRIMARY_DATA, COLOR_WARNING, COLOR_ERROR,
                     COLOR_HEADER, COLOR_PROMPT_BOLD, COLOR_PROMPT_LIGHT, COLOR_SUCCESS)
from .config import DB_DIR_NAME, SECURITY_DIR_NAME, PEK_FILE_NAME
from .config import COMMANDS_VALID_NO_ARGS
from .password_generator import password_generator

# TODO: Create password generator function
# TODO: Create master password update function

def authenticate_from_session(ctx):
    """
    Attempts to retrieve the PEK from the session file.
    If successful, stores the PEK in ctx.obj and initializes the DB.
    """
    session_pek = session.retrieve_session_pek()

    if session_pek:
        # Vault is successfully unlocked via session file!
        ctx.ensure_object(dict)
        ctx.obj['pek'] = session_pek
        db.initialise_db(pek=session_pek)

        # --- SUPPRESS MESSAGE LOGIC ---
        subcommand_name = ctx.invoked_subcommand
        is_help_requested = any(h in sys.argv for h in ['-h', '--help'])
        is_only_subcommand = (len(sys.argv) == 2 and subcommand_name is not None)

        # Suppress the message if:
        # 1. Help was explicitly requested (e.g., passman view -h)
        # 2. The subcommand was run with no args AND that command is NOT in the valid no-arg list.
        #    (e.g., 'passman add' is suppressed, but 'passman list' is NOT suppressed)
        should_suppress = (
                is_help_requested or
                (is_only_subcommand and subcommand_name not in COMMANDS_VALID_NO_ARGS)
        )

        if not should_suppress:
            # Only print if it's a valid command execution (like 'list') or a valid command with arguments
            click.secho("Vault is unlocked via the active session.", **COLOR_SUCCESS)
            click.secho("Run 'passman logout' when done.", **COLOR_WARNING)

        return True
    return False

@click.group(
    context_settings=dict(help_option_names=["-h", "--help"]),
    epilog="Use 'passman <command> --help' for command-specific usage and examples.",
)
@click.pass_context
def cli(ctx):
    """
    PassMan - A secure CLI password manager.

    Manages passwords and sensitive data locally using an encrypted SQLite vault.
    """
    # Try to unlock the vault from the session file
    if not authenticate_from_session(ctx=ctx):
        # Set a flag indicating the vault is locked
        ctx.ensure_object(dict)
        ctx.obj['pek'] = None

        if ctx.invoked_subcommand not in ['login', 'logout', None]:
            # Check if help was explicitly requested. If so, suppress the lock warning.
            is_help_requested = any(h in sys.argv for h in ['-h', '--help'])
            if not is_help_requested:
                click.secho("Vault is LOCKED. Run 'passman login' to unlock it.", **COLOR_ERROR)


@cli.command(help="Unlocks the vault for subsequent commands in the terminal until timeout or explicit logout.")
def login():
    """
    Prompts for the master password, decrypts the PEK, and stores it in a session file.
    """
    # --- SECURITY/KEY RETRIEVAL LOGIC ---
    db.get_db_path()
    security.initialise_security_dir()
    security.generate_salt_file()
    salt = security.retrieve_salt()
    kdf = security.key_derivation_function(salt=salt)
    master_password = security.login()
    kek = security.generate_derived_key(kdf=kdf, master_password=master_password)

    home_dir = Path.home()
    security_dir = home_dir / DB_DIR_NAME / SECURITY_DIR_NAME
    pek_file = security_dir / PEK_FILE_NAME

    if not pek_file.exists():
        # First time setup
        session_pek = security.generate_and_encrypt_pek(derived_key=kek)
    else:
        # Subsequent login
        session_pek = security.retrieve_and_decrypt_pek(derived_key=kek)

    if session_pek is None:
        sys.exit(1)

    # --- SESSION STORAGE ---
    if session.store_session_data(pek=session_pek):
        db.initialise_db(pek=session_pek)  # Ensure DB is initialized with the PEK
        click.secho(f"\nVault UNLOCKED. Commands will now run without further authentication.", **COLOR_SUCCESS)
        click.secho("Remember to run 'passman logout' when finished.", **COLOR_WARNING)


@cli.command(help="Locks the vault by deleting the active session file.")
def logout():
    """
    Deletes the session file, requiring re-authentication for the next command.
    """
    if session.clear_session_data():
        click.secho("\nVault LOCKED.", **COLOR_SUCCESS)
    else:
        click.secho("\nVault was already locked.", **COLOR_WARNING)

@cli.command(
    help="Creates a new password entry. Prompts user for username/email, password, URL, and note.",
    epilog="""\b
    EXAMPLES:
      # Interactive - prompts for all fields:
      $ passman add new_service
      \b
      # Generate password option - prompts for username, URL, and note. 
      $ passman add website_name -g
      \b
      # Generate password option without special chars - automatically generates a strong new password:
      $ passman update github -g -w
      \b
    NOTE: Using -g will automatically generate a strong password.
    \b
    """
)
@click.argument("service_name", type=str)
@click.option(
    "-g",
    "--generate",
    is_flag=True,
    help="Generate a cryptographically strong password instead of prompting for user input. "
         "By default it includes special characters. "
         "Use the -w option to generate a strong password without special characters.",
)
@click.option(
    "-w",
    "--without-special-chars",
    is_flag=True,
    help="Specify if the password should be generated without special characters. Only works with the -g option.",
)
@click.pass_context
def add(ctx, service_name, generate, without_special_chars):
    """
    Creates a new entry in the database.
    Prompts user for username/email, password, url and note.
    Prompts user to confirm the new entry and save it into database.
    """
    session_pek = ctx.obj["pek"]

    if not session_pek:
        sys.exit(1)

    if db.validate_service_name(pek=session_pek, service_name=service_name) is True:
        click.secho(f"An entry for '{service_name}' already exists. Please use a different name.", **COLOR_WARNING)
        sys.exit(0)

    username = click.prompt(click.style("Enter username/email", **COLOR_PROMPT_BOLD), type=str)

    if generate:
        password = password_generator(without_special_chars=without_special_chars)
        click.secho(f"Generated password for '{service_name}': {password}", **COLOR_SUCCESS)
    else:
        password = click.prompt(
            click.style("Enter password", **COLOR_PROMPT_BOLD),
            hide_input=True,
            confirmation_prompt=True
        )

    url = click.prompt(
        click.style("Enter url (optional)", **COLOR_PROMPT_LIGHT),
        type=str,
        default="null",
        show_default=False
    )

    note = click.prompt(
        click.style("Enter note (optional)", **COLOR_PROMPT_LIGHT),
        type=str,
        default="null",
        show_default=False
    )

    if click.confirm(click.style(f"Ready to securely save the entry for '{service_name}'?", **COLOR_PROMPT_LIGHT)):
        try:
            db.add_entry(pek=session_pek, service_name=service_name, username=username,
                         password=password, url=url, note=note)
            click.secho(f"Entry for '{service_name}' saved successfully.", **COLOR_SUCCESS)
        except Exception as e:
            click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
            click.Abort()
    else:
        click.secho("Operation cancelled.", **COLOR_WARNING)
        click.Abort()


@cli.command(
    help="Retrieves a specific entry, displaying all sensitive and non-sensitive information.",
    epilog="""\b
    EXAMPLE:
      $ passman view github 
      \b
      NOTE: This command displays the raw username and password. The information should be copied 
      and the terminal screen cleared immediately for security.
      \b
    """,
)
@click.argument("service_name", type=str)
@click.pass_context
def view(ctx, service_name):
    """
    Retrieve an entry with sensitive info from the database.
    Display the entry in a beautiful table.
    """
    session_pek = ctx.obj["pek"]
    if not session_pek:
        sys.exit(1)

    try:
        click.secho(f"Retrieving credentials for: {service_name}", **COLOR_HEADER)
        row = db.view_entry(pek=session_pek, service_name=service_name)

        headers = [
            click.style("SERVICE", **COLOR_HEADER),
            click.style("USERNAME", **COLOR_HEADER),
            click.style("PASSWORD", **COLOR_HEADER),
            click.style("URL", **COLOR_HEADER),
            click.style("NOTE", **COLOR_HEADER),
            click.style("CREATED AT", **COLOR_HEADER),
            click.style("UPDATED AT", **COLOR_HEADER),
        ]

        styled_row = []
        for r in row:
            styled_row.append([
                click.style(r[0], **COLOR_SENSITIVE_DATA), # service_name
                click.style(r[1], **COLOR_SENSITIVE_DATA),  # username
                click.style(r[2], **COLOR_SENSITIVE_DATA),  # password
                click.style(r[3], **COLOR_WARNING),  # url
                click.style(r[4], **COLOR_WARNING),  # note
                click.style(r[5], **COLOR_PRIMARY_DATA),  # created_at
                click.style(r[6], **COLOR_PRIMARY_DATA)  # updated_at
            ])

        display_table = tabulate.tabulate(
            styled_row,
            headers=headers,
            tablefmt="rounded_grid",
        )
        click.secho(display_table)

        pyperclip.copy(row[0][2])
        click.secho(f"The password for '{service_name}' has been copied to your clipboard!", **COLOR_SUCCESS)
        click.secho("\nSECURITY NOTE: Clear your screen immediately!", **COLOR_ERROR)

    except pyperclip.PyperclipException as e:
        click.secho(f"ERROR: {e}", **COLOR_ERROR)
        click.secho("Please install ONE of the following copy/paste mechanisms (e.g. 'pip install xsel'):",
                    **COLOR_WARNING)
        click.secho("xsel, xclip, gtk, PyQt4", **COLOR_WARNING)
        click.Abort()
    except Exception as e:
        click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
        click.Abort()


@cli.command(
    help="Searches for entries by matching the search term against service names.",
    epilog="""\b
    EXAMPLE:
      # Find all services containing 'bank'
      $ passman search bank
      \b
      NOTE: Usernames and passwords are intentionally EXCLUDED. Use 'passman view <service>' 
      to retrieve sensitive credentials for a specific entry.
      \b
    """,
)
@click.argument("search_term", type=str)
@click.pass_context
def search(ctx, search_term):
    """
    Retrieve entries with non-sensitive info matching on a search term from the database.
    Display entries in a beautiful table.
    Usernames and passwords are not retrieved.
    User must use the 'view' command to retrieve sensitive information.
    """
    session_pek = ctx.obj["pek"]
    if not session_pek:
        sys.exit(1)

    try:
        click.secho(
            f"Retrieving entries with service names that contain the search term: {search_term}",
            **COLOR_HEADER,
        )
        rows = db.search(pek=session_pek, search_term=search_term)

        headers = [
            click.style("SERVICE NAME", **COLOR_HEADER),
            click.style("URL", **COLOR_HEADER),
            click.style("NOTE", **COLOR_HEADER),
            click.style("CREATED AT", **COLOR_HEADER),
            click.style("UPDATED AT", **COLOR_HEADER),
        ]

        styled_rows = []
        for r in rows:
            styled_rows.append([
                click.style(r[0], **COLOR_SENSITIVE_DATA),  # service_name
                click.style(r[1], **COLOR_WARNING),  # url
                click.style(r[2], **COLOR_WARNING),  # note
                click.style(r[3], **COLOR_PRIMARY_DATA),  # created_at
                click.style(r[4], **COLOR_PRIMARY_DATA)  # updated_at
            ])

        display_table = tabulate.tabulate(
            styled_rows,
            headers=headers,
            tablefmt="rounded_grid",
        )
        click.secho(display_table)
    except Exception as e:
        click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
        click.Abort()


@cli.command(
    name="list",  # Use name="list" because list() is a built-in Python function
    help="Lists all stored entries by service name and non-sensitive metadata.",
    epilog="""\b
    EXAMPLE:
      $ passman list
      \b
      NOTE: Usernames and passwords are intentionally EXCLUDED. Use 'passman view <service>' 
      to retrieve sensitive credentials for a specific entry.
      \b
    """,
)
@click.pass_context
def list_entries(ctx):
    """
    Retrieve all entries with non-sensitive info from the database.
    Display entries in a beautiful table.
    Usernames and passwords are not retrieved.
    User must use the 'view' command to retrieve sensitive information.
    """
    session_pek = ctx.obj["pek"]
    if not session_pek:
        sys.exit(1)

    try:
        click.secho(f"Retrieving all entries.", **COLOR_HEADER)
        rows = db.list_entries(pek=session_pek)

        headers = [
            click.style("SERVICE NAME", **COLOR_HEADER),
            click.style("URL", **COLOR_HEADER),
            click.style("NOTE", **COLOR_HEADER),
            click.style("CREATED AT", **COLOR_HEADER),
            click.style("UPDATED AT", **COLOR_HEADER),
        ]

        styled_rows = []
        for r in rows:
            styled_rows.append([
                click.style(r[0], **COLOR_SENSITIVE_DATA),  # service_name
                click.style(r[1], **COLOR_WARNING),  # url
                click.style(r[2], **COLOR_WARNING),  # note
                click.style(r[3], **COLOR_PRIMARY_DATA),  # created_at
                click.style(r[4], **COLOR_PRIMARY_DATA)  # updated_at
            ])

        display_table = tabulate.tabulate(
            styled_rows,
            headers=headers,
            tablefmt="rounded_grid",
        )
        click.secho(display_table)
    except Exception as e:
        click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
        click.Abort()


@cli.command(
    help="Updates only the password for an existing entry.",
    epilog="""\b
    EXAMPLES:
      # Interactive - prompts for new password:
      $ passman update gmail 
      \b
      # Generate password option - automatically generates a strong new password:
      $ passman update github -g
      \b
      # Generate password option without special chars - automatically generates a strong new password:
      $ passman update github -g -w
      \b
      NOTE: This command currently only updates the password field.
      \b
    """,
)
@click.argument("service_name", type=str)
@click.option(
    "-g",
    "--generate",
    is_flag=True,
    help="Generate a cryptographically strong password instead of prompting for user input. "
         "By default it includes special characters. "
         "Use the -w option to generate a strong password without special characters.",
)
@click.option(
    "-w",
    "--without-special-chars",
    is_flag=True,
    help="Specify if the password should be generated without special characters. Only works with the -g option.",
)
@click.pass_context
def update(ctx, service_name, generate, without_special_chars):
    """
    Update the password for an entry in the database.
    Prompts user to confirm password update.
    """
    session_pek = ctx.obj["pek"]
    if not session_pek:
        sys.exit(1)

    if db.validate_service_name(pek=session_pek, service_name=service_name) is False:
        click.secho(f"An entry for '{service_name}' doesn't exist. Please check the service name and try again.",
                    **COLOR_WARNING)
        sys.exit(0)

    if generate:
        password = password_generator(without_special_chars=without_special_chars)
        click.secho(f"Generated new password for '{service_name}': {password}", **COLOR_SUCCESS)
    else:
        password = click.prompt(
            click.style(f"Enter new password for {service_name}", **COLOR_PROMPT_BOLD),
            hide_input=True,
            confirmation_prompt=True,
        )

    if click.confirm(
            click.style(f"Ready to securely save the new password for '{service_name}'?", **COLOR_PROMPT_LIGHT)):
        try:
            db.update_entry(pek=session_pek, service_name=service_name, password=password)
            click.secho(f"Password for '{service_name}' saved successfully.", **COLOR_SUCCESS)
        except Exception as e:
            # DB Error: Red
            click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
            click.Abort()
    else:
        click.secho("Operation cancelled.", **COLOR_WARNING)


@cli.command(
    help="Permanently deletes an entry from the vault after a confirmation prompt.",
    epilog="""\b
    EXAMPLE:
      $ passman delete old_site
      \b
      WARNING: Deletion is permanent and cannot be undone.
      \b
    """,
)
@click.argument("service_name", type=str)
@click.pass_context
def delete(ctx, service_name):
    """
    Delete an entry in the database.
    Prompts user to confirm deletion.
    """
    session_pek = ctx.obj["pek"]
    if not session_pek:
        sys.exit(1)

    if db.validate_service_name(pek=session_pek, service_name=service_name) is False:
        click.secho(f"An entry for '{service_name}' doesn't exist. Please check the service name and try again.",
                    **COLOR_WARNING)
        sys.exit(0)

    if click.confirm(click.style(f"Ready to PERMANENTLY delete the entry for: {service_name}? (This cannot be undone)",
                                 **COLOR_ERROR)):
        try:
            db.delete_entry(pek=session_pek, service_name=service_name)
            click.secho(f"{service_name} successfully deleted.", **COLOR_SUCCESS)
        except Exception as e:
            click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
            click.Abort()
    else:
        click.secho("Operation cancelled.", **COLOR_WARNING)

cli(obj={})
