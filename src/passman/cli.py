import click
from . import db
import tabulate
import sys
import pyperclip
from .config import COLOR_SENSITIVE_DATA, COLOR_PRIMARY_DATA, COLOR_WARNING, COLOR_ERROR, COLOR_HEADER, COLOR_PROMPT_BOLD, COLOR_PROMPT_LIGHT, COLOR_SUCCESS


@click.group(
    context_settings=dict(help_option_names=["-h", "--help"]),
    epilog="Use 'passman <command> --help' for command-specific usage and examples.",
)
def cli():
    """
    PassMaster - A secure CLI password manager.

    Manages passwords and sensitive data locally using an encrypted SQLite vault.
    """
    try:
        db.initialise_db()
    except Exception as e:
        # Critical Error: Red and bold
        click.secho(f"DB ERROR: {e}. Exiting program.", err=True, **COLOR_ERROR)
        raise click.Abort()


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
def add(service_name, generate):
    """
    Creates a new entry in the database.
    Prompts user for username/email, password, url and note.
    Prompts user to confirm the new entry and save it into database.
    """
    if db.validate_service_name(service_name) is True:
        # Warning: Yellow
        click.secho(f"An entry for '{service_name}' already exists. Please use a different name.", **COLOR_WARNING)
        sys.exit(0)

    # Prompts: Cyan and bold for visibility
    username = click.prompt(click.style("Enter username/email", **COLOR_PROMPT_BOLD), type=str)

    if generate:
        password = "generatedTestPassword123"
        # Generated Password/Success: Green and bold
        click.secho(f"Generated password for '{service_name}': {password}", **COLOR_SUCCESS)
    else:
        password = click.prompt(
            click.style("Enter password", **COLOR_PROMPT_BOLD),
            hide_input=True,
            confirmation_prompt=True
        )

    url = click.prompt(
        click.style("Enter url (optional)", **COLOR_PROMPT_LIGHT),  # Optional fields use lighter prompt style
        type=str,
        default="null",
        show_default=False
    )

    note = click.prompt(
        click.style("Enter note (optional)", **COLOR_PROMPT_LIGHT),  # Optional fields use lighter prompt style
        type=str,
        default="null",
        show_default=False
    )

    # Confirmation: Cyan
    if click.confirm(click.style(f"Ready to securely save the entry for '{service_name}'?", **COLOR_PROMPT_LIGHT)):
        try:
            # Placeholder IV of 1, should be changed when encryption is implemented
            db.add_entry(service_name, username, password, url, note)
            # Success Message: Green and bold
            click.secho(f"Entry for '{service_name}' saved successfully.", **COLOR_SUCCESS)
        except Exception as e:
            # DB Error: Red
            click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
            click.Abort()
    else:
        # Operation Cancelled: Yellow
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
def view(service_name):
    """
    Retrieve an entry with sensitive info from the database.
    Display the entry in a beautiful table.
    """
    try:
        # Information header: Magenta
        click.secho(f"Retrieving credentials for: {service_name}",
                    fg="magenta")  # Using fg="magenta" without bold for the main message
        row = db.view_entry(service_name)

        # Style the headers and data within the table
        headers = [
            click.style("SERVICE", **COLOR_HEADER),
            click.style("USERNAME", **COLOR_HEADER),
            click.style("PASSWORD", **COLOR_HEADER),
            click.style("URL", **COLOR_HEADER),
            click.style("NOTE", **COLOR_HEADER),
            click.style("CREATED AT", **COLOR_HEADER),
            click.style("UPDATED AT", **COLOR_HEADER),
        ]

        # Row data styling
        styled_row = []
        for r in row:
            styled_row.append([
                click.style(r[0], **COLOR_SENSITIVE_DATA),
                click.style(r[1], **COLOR_SENSITIVE_DATA),  # username
                click.style(r[2], **COLOR_SENSITIVE_DATA),  # password (highlight sensitive data)
                click.style(r[3], **COLOR_WARNING),  # url (Warning/Annotation Data)
                click.style(r[4], **COLOR_WARNING),  # note (Warning/Annotation Data)
                click.style(r[5], **COLOR_PRIMARY_DATA),  # created_at
                click.style(r[6], **COLOR_PRIMARY_DATA)  # updated_at
            ])

        display_table = tabulate.tabulate(
            styled_row,
            headers=headers,
            tablefmt="rounded_grid",
        )
        click.secho(display_table)

        pyperclip.copy(row[0][2])  # copy password to clipboard
        # Success and critical security message: Green and Red/Bold
        click.secho(f"The password for '{service_name}' has been copied to your clipboard!", **COLOR_SUCCESS)
        click.secho("\nSECURITY NOTE: Clear your screen immediately!", **COLOR_ERROR)

    except pyperclip.PyperclipException as e:
        # Warning/Error: Red and Yellow
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
def search(search_term):
    """
    Retrieve entries with non-sensitive info matching on a search term from the database.
    Display entries in a beautiful table.
    Usernames and passwords are not retrieved.
    User must use the 'view' command to retrieve sensitive information.
    """
    try:
        # Information header: Magenta
        click.secho(
            f"Retrieving entries with service names that contain the search term: {search_term}",
            fg="magenta"
        )
        rows = db.search(search_term)

        # Style the headers and data rows
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
                click.style(r[0], **COLOR_SENSITIVE_DATA),  # service_name (Primary Data)
                click.style(r[1], **COLOR_WARNING),  # url (Secondary Data)
                click.style(r[2], **COLOR_WARNING),  # note (Warning/Annotation Data)
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
def list_entries():
    """
    Retrieve all entries with non-sensitive info from the database.
    Display entries in a beautiful table.
    Usernames and passwords are not retrieved.
    User must use the 'view' command to retrieve sensitive information.
    """
    try:
        # Information header: Magenta
        click.secho(f"Retrieving all entries.", fg="magenta")
        rows = db.list()

        # Style the headers and data rows
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
                click.style(r[0], **COLOR_SENSITIVE_DATA),  # service_name (Primary Data)
                click.style(r[1], **COLOR_WARNING),  # url (Secondary Data)
                click.style(r[2], **COLOR_WARNING),  # note (Warning/Annotation Data)
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
def update(service_name, generate):
    """
    Update the password for an entry in the database.
    Prompts user to confirm password update.
    """
    # Validation is now handled inside db.validate_service_name, but a check here is fine.
    if db.validate_service_name(service_name) is False:
        click.secho(f"An entry for '{service_name}' doesn't exist. Please check the service name and try again.",
                    **COLOR_WARNING)
        sys.exit(0)

    if generate:
        password = "updatedPassword123"
        # Generated Password/Success: Green and bold
        click.secho(f"Generated new password for '{service_name}': {password}", **COLOR_SUCCESS)
    else:
        # Prompt: Cyan and bold
        password = click.prompt(
            click.style(f"Enter new password for {service_name}", **COLOR_PROMPT_BOLD),
            hide_input=True,
            confirmation_prompt=True,
        )

    # Confirmation: Cyan
    if click.confirm(
            click.style(f"Ready to securely save the new password for '{service_name}'?", **COLOR_PROMPT_LIGHT)):
        try:
            db.update_entry(service_name, password)
            # Success Message: Green and bold
            click.secho(f"Password for '{service_name}' saved successfully.", **COLOR_SUCCESS)
        except Exception as e:
            # DB Error: Red
            click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
            click.Abort()
    else:
        # Operation Cancelled: Yellow
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
def delete(service_name):
    """
    Delete an entry in the database.
    Prompts user to confirm deletion.
    """
    if db.validate_service_name(service_name) is False:
        click.secho(f"An entry for '{service_name}' doesn't exist. Please check the service name and try again.",
                    **COLOR_WARNING)
        sys.exit(0)

    # Confirmation: Critical (Red) for an irreversible action
    if click.confirm(click.style(f"Ready to PERMANENTLY delete the entry for: {service_name}? (This cannot be undone)",
                                 **COLOR_ERROR)):
        try:
            db.delete_entry(service_name)
            # Success Message: Green and bold
            click.secho(f"{service_name} successfully deleted.", **COLOR_SUCCESS)
        except Exception as e:
            # DB Error: Red
            click.secho(f"DB ERROR: {e}", **COLOR_ERROR)
            click.Abort()
    else:
        # Operation Cancelled: Yellow
        click.secho("Operation cancelled.", **COLOR_WARNING)


cli()
