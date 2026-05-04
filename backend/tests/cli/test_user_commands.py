"""End-to-end tests for ``medminder-admin user ...``."""

from __future__ import annotations

from typer.testing import CliRunner

from medminder.cli.main import app

GOOD_PASSWORD = "correct horse battery staple"


def test_help_lists_subcommands(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "user" in result.stdout
    assert "db" in result.stdout


def test_user_help_does_not_offer_password_flag(cli_runner: CliRunner) -> None:
    """D23: there is no ``--password`` flag — only ``--password-stdin``."""
    result = cli_runner.invoke(app, ["user", "add", "--help"])
    assert result.exit_code == 0
    assert "--password-stdin" in result.stdout
    assert "--password " not in result.stdout
    assert "--password=" not in result.stdout


def test_add_then_list(cli_runner: CliRunner, truncate_users: None) -> None:
    add = cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    assert add.exit_code == 0, add.stdout + add.stderr
    user_id = add.stdout.strip()
    assert user_id

    listing = cli_runner.invoke(app, ["user", "list"])
    assert listing.exit_code == 0
    assert "a@example.com" in listing.stdout
    # D25: the column header order is fixed.
    header_line = listing.stdout.splitlines()[1]
    for col in ("id", "email", "name", "role", "created_at", "deleted_at"):
        assert col in header_line


def test_add_short_password_rejected(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    result = cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input="short\n",
    )
    assert result.exit_code != 0


def test_add_duplicate_email_case_insensitive(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    first = cli_runner.invoke(
        app,
        ["user", "add", "--email", "Foo@x.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    assert first.exit_code == 0
    second = cli_runner.invoke(
        app,
        ["user", "add", "--email", "FOO@X.COM", "--name", "B", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    assert second.exit_code != 0


def test_role_rejects_unknown_value(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    result = cli_runner.invoke(
        app,
        [
            "user",
            "add",
            "--email",
            "a@example.com",
            "--name",
            "A",
            "--role",
            "superadmin",
        ],
        input=GOOD_PASSWORD + "\n",
    )
    assert result.exit_code != 0


def test_delete_soft_deletes(cli_runner: CliRunner, truncate_users: None) -> None:
    cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    deleted = cli_runner.invoke(app, ["user", "delete", "--email", "a@example.com"])
    assert deleted.exit_code == 0
    listing = cli_runner.invoke(app, ["user", "list"])
    assert "a@example.com" not in listing.stdout
    listing_all = cli_runner.invoke(app, ["user", "list", "--include-deleted"])
    assert "a@example.com" in listing_all.stdout


def test_delete_missing_user(cli_runner: CliRunner, truncate_users: None) -> None:
    result = cli_runner.invoke(app, ["user", "delete", "--email", "nope@example.com"])
    assert result.exit_code != 0


def test_update_no_changes(cli_runner: CliRunner, truncate_users: None) -> None:
    cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    result = cli_runner.invoke(app, ["user", "update", "--email", "a@example.com"])
    assert result.exit_code != 0
    assert "no changes" in (result.stderr + result.stdout).lower()


def test_update_changes_name(cli_runner: CliRunner, truncate_users: None) -> None:
    cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    result = cli_runner.invoke(
        app,
        ["user", "update", "--email", "a@example.com", "--name", "Renamed"],
    )
    assert result.exit_code == 0
    listing = cli_runner.invoke(app, ["user", "list"])
    assert "Renamed" in listing.stdout


def test_update_password_round_trip(
    cli_runner: CliRunner, truncate_users: None
) -> None:
    """D28: a CLI-issued password verifies via the domain module."""
    from medminder.domain.users import (
        get_user_by_email,
        verify_password,
    )

    cli_runner.invoke(
        app,
        ["user", "add", "--email", "a@example.com", "--name", "A", "--role", "user"],
        input=GOOD_PASSWORD + "\n",
    )
    new_password = "another correct horse value"
    result = cli_runner.invoke(
        app,
        [
            "user",
            "update",
            "--email",
            "a@example.com",
            "--password-stdin",
        ],
        input=new_password + "\n",
    )
    assert result.exit_code == 0

    # Verify via the same domain function the future Phase 2 auth
    # middleware will call.
    from medminder.cli._session import run_with_session

    async def fetch(session):  # type: ignore[no-untyped-def]
        return await get_user_by_email(session, email="a@example.com")

    user = run_with_session(fetch)
    assert user is not None
    assert verify_password(user.password_hash, new_password)
