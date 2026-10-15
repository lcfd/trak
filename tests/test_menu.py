"""How the Actions of the home rank commands for the filter."""

import pytest
from typer.testing import CliRunner

from trak.main.menu import command_score

runner = CliRunner()


COMMANDS = [
    "start",
    "stop",
    "sessions list",
    "sessions show",
    "sessions edit",
    "projects list",
    "projects create",
    "projects edit",
    "customers list",
    "customers edit",
    "help",
    "quit",
]


def ranked(query: str) -> list[str]:
    scores = {path: command_score(query, path) for path in COMMANDS}
    matches = [path for path in COMMANDS if scores[path] is not None]
    return sorted(matches, key=lambda path: -scores[path])


@pytest.mark.parametrize(
    ("query", "best"),
    [
        ("sl", "sessions list"),
        ("se", "sessions edit"),
        ("pc", "projects create"),
        ("ce", "customers edit"),
        ("cl", "customers list"),
        ("sess li", "sessions list"),
        ("seli", "sessions list"),
        ("st", "start"),
        ("SL", "sessions list"),
    ],
)
def test_abbreviations_find_the_command_first(query, best):
    assert ranked(query)[0] == best


def test_a_later_word_matches_after_the_abbreviations():
    assert ranked("edit") == ["sessions edit", "projects edit", "customers edit"]


def test_letters_in_order_match_last():
    # "sl" abbreviates "sessions list", and is only in order in the others.
    assert ranked("sl") == ["sessions list", "projects list", "customers list"]
    assert command_score("tsp", "stop") is None


def test_description_matches_when_the_name_does_not():
    assert command_score("newest", "sessions list", "List sessions, newest first.")
    assert command_score("newest", "sessions list") is None
