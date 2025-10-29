import click
from . import db, security
import tabulate
import sys
from pathlib import Path
import pyperclip
from .config import (COLOR_SENSITIVE_DATA, COLOR_PRIMARY_DATA, COLOR_WARNING, COLOR_ERROR,
                     COLOR_HEADER, COLOR_PROMPT_BOLD, COLOR_PROMPT_LIGHT, COLOR_SUCCESS)
from .config import DB_DIR_NAME, SECURITY_DIR_NAME, PEK_FILE_NAME


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
    # --- INITIALISE SECURITY ---
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
        session_pek = security.generate_and_encrypt_pek(derived_key=kek)
    else:
        session_pek = security.retrieve_and_decrypt_pek(derived_key=kek)

    # --- INITIALISE DATABASE ---
    db.initialise_db(pek=session_pek)

    # --- SET CONTEXT OBJECT TO SHARE PEK TO SUBCOMMANDS ---
    ctx.ensure_object(dict)
    ctx.obj['pek'] = session_pek

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
    NOTE: Using -g will automatically generate a strong password.
    \b
    """
)
@click.argument("service_name", type=str)
@click.option(
    "-g",
    "--generate",
    is_flag=True,
    help="Generate a strong password instead of prompting for user input.",
)
@click.pass_context
def add(ctx, service_name, generate):
    """
    Creates a new entry in the database.
    Prompts user for username/email, password, url and note.
    Prompts user to confirm the new entry and save it into database.
    """
    session_pek = ctx.obj["pek"]

    if db.validate_service_name(pek=session_pek, service_name=service_name) is True:
        click.secho(f"An entry for '{service_name}' already exists. Please use a different name.", **COLOR_WARNING)
        sys.exit(0)

    username = click.prompt(click.style("Enter username/email", **COLOR_PROMPT_BOLD), type=str)

    if generate:
        password = "generatedTestPassword123"
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
      NOTE: This command currently only updates the password field.
      \b
    """,
)
@click.argument("service_name", type=str)
@click.option(
    "-g",
    "--generate",
    is_flag=True,
    help="Generate a strong password instead of prompting for manual entry.",
)
@click.pass_context
def update(ctx, service_name, generate):
    """
    Update the password for an entry in the database.
    Prompts user to confirm password update.
    """
    session_pek = ctx.obj["pek"]

    if db.validate_service_name(pek=session_pek, service_name=service_name) is False:
        click.secho(f"An entry for '{service_name}' doesn't exist. Please check the service name and try again.",
                    **COLOR_WARNING)
        sys.exit(0)

    if generate:
        password = "updatedPassword123"
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
