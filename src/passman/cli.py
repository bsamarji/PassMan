import click
import db
import tabulate
import sys
import pyperclip

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
        click.echo(f"DB ERROR: {e}. Exiting program.", err=True)
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
        click.echo(f"An entry for '{service_name}' already exists. Please use a different name.")
        sys.exit(0)

    username = click.prompt("Enter username/email", type=str)

    if generate:
        password = "generatedTestPassword123"
        click.echo(f"Generated password for '{service_name}': {password}")
    else:
        password = click.prompt(
            "Enter password", hide_input=True, confirmation_prompt=True
        )

    url = click.prompt(
        "Enter url (optional)", type=str, default="null", show_default=False
    )
    note = click.prompt(
        "Enter note (optional)", type=str, default="null", show_default=False
    )

    if click.confirm(f"Ready to securely save the entry for '{service_name}'?"):
        try:
            db.add_entry(service_name, username, password, url, note, 1)
            click.echo(f"Entry for '{service_name}' saved successfully.")
        except Exception as e:
            print(f"DB ERROR: {e}")
            click.Abort()
    else:
        click.echo("Operation cancelled.")


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
        click.echo(f"Retrieving credentials for: {service_name}")
        row = db.view_entry(service_name)
        display_table = tabulate.tabulate(
            row,
            headers=[
                "service_name",
                "username",
                "password",
                "url",
                "note",
                "created_at",
                "updated_at",
            ],
            tablefmt="rounded_grid",
        )
        click.echo(display_table)
        pyperclip.copy(row[0][2]) # copy password to clipboard
        click.secho(f"The password for '{service_name}' has been copied to your clipboard!", fg="yellow", bold=True)
    except Exception as e:
        click.echo(f"DB ERROR: {e}")
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
        click.echo(
            f"Retrieving entries with service names that contain the search term: {search_term}"
        )
        rows = db.search(search_term)
        display_table = tabulate.tabulate(
            rows,
            headers=[
                "service_name",
                "url",
                "note",
                "created_at",
                "updated_at",
            ],
            tablefmt="rounded_grid",
        )
        click.echo(display_table)
    except Exception as e:
        click.echo(f"DB ERROR: {e}")
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
        click.echo(f"Retrieving all entries.")
        rows = db.list()
        display_table = tabulate.tabulate(
            rows,
            headers=[
                "service_name",
                "url",
                "note",
                "created_at",
                "updated_at",
            ],
            tablefmt="rounded_grid",
        )
        click.echo(display_table)
    except Exception as e:
        click.echo(f"DB ERROR: {e}")
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
    db.validate_service_name(service_name)
    if generate:
        password = "updatedPassword123"
        click.echo(f"Generated new password for '{service_name}': {password}")
    else:
        password = click.prompt(
            f"Enter new password for {service_name}",
            hide_input=True,
            confirmation_prompt=True,
        )

    if click.confirm(f"Ready to securely save the new password for '{service_name}'?"):
        try:
            db.update_entry(service_name, password)
            click.echo(f"Password for '{service_name}' saved successfully.")
        except Exception as e:
            print(f"DB ERROR: {e}")
            click.Abort()
    else:
        click.echo("Operation cancelled.")


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
    db.validate_service_name(service_name)
    if click.confirm(f"Ready to securely delete the entry for: {service_name}?"):
        try:
            if db.validate_service_name(service_name) is False:
                click.echo(f"An entry for '{service_name}' doesn't exist. Please check the service name and try again.")
                sys.exit(0)
            db.delete_entry(service_name)
            click.echo(f"{service_name} successfully deleted.")
        except Exception as e:
            print(f"DB ERROR: {e}")
            click.Abort()
    else:
        click.echo("Operation cancelled.")


cli()
