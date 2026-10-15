import pytest
from pydantic import TypeAdapter

from tests.fakes import FakeScreen
from trak import tui
from trak.prompts import (
    CTRL_D,
    CTRL_U,
    CTRL_W,
    ESC,
    Menu,
    PromptCancelled,
    ScreenPrompter,
    TextInput,
    split_escape,
)
from trak.sessions.guided import start_validator

DOWN, UP, LEFT = "\x1b[B", "\x1b[A", "\x1b[D"


def menu(names=("alpha", "beta", "gamma", "delta"), **kwargs):
    options = [{"name": name, "value": name} for name in names]
    return Menu("Pick", options, **kwargs)


def press(element, *keys):
    done = False
    for key in keys:
        done = element.handle_key(key)
    return done


def current(m):
    return m.value


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("j", ["j"]),
        (ESC, [ESC]),
        (DOWN, [DOWN]),  # arrows stay whole
        ("\x1bOA", ["\x1bOA"]),
        ("\x1bj", [ESC, "j"]),  # a fast Esc glued to the next key
    ],
)
def test_split_escape(key, expected):
    assert split_escape(key) == expected


# filterable lists


def test_filterable_list_starts_in_insert_mode_and_types_j_k():
    m = menu(names=("jkl", "other"), allow_filtering=True)

    press(m, "j", "k")

    assert m.mode == "insert"
    assert m.text == "jk"
    assert current(m) == "jkl"


def test_esc_switches_to_normal_mode_where_j_k_move():
    m = menu(allow_filtering=True)

    press(m, ESC, "j", "j", "k")

    assert m.mode == "normal"
    assert m.text == ""
    assert current(m) == "beta"
    assert ("Esc", "back") in m.hints()


def test_arrows_move_in_both_modes():
    m = menu(allow_filtering=True)

    press(m, DOWN, ESC, DOWN)
    assert current(m) == "gamma"

    press(m, UP, UP, UP)
    assert current(m) == "delta"  # wraps around


def test_normal_mode_jumps():
    m = menu(allow_filtering=True)

    press(m, ESC, "G")
    assert current(m) == "delta"
    press(m, "g")
    assert current(m) == "alpha"


def test_half_screen_moves_stop_at_the_ends():
    m = menu(names=[f"item {i}" for i in range(10)], allow_filtering=True)
    # Drawn 4 rows high: half a screen is 2.
    m.body(40, 5)

    press(m, ESC, CTRL_D)
    assert m.selected == 2
    press(m, CTRL_D, CTRL_D, CTRL_D, CTRL_D)
    assert m.selected == 9
    press(m, CTRL_U)
    assert m.selected == 7


def test_i_resumes_the_filter_and_slash_starts_a_new_one():
    m = menu(allow_filtering=True)

    press(m, "a", ESC, "i", "l")
    assert (m.mode, m.text) == ("insert", "al")

    press(m, ESC, "/")
    assert (m.mode, m.text) == ("insert", "")


@pytest.mark.parametrize("key", [ESC, "q"])
def test_going_back_from_normal_mode(key):
    m = menu(allow_filtering=True)

    with pytest.raises(PromptCancelled):
        press(m, ESC, key)


def test_other_keys_do_nothing_in_normal_mode():
    m = menu(allow_filtering=True)

    press(m, ESC, "x", "z", "1")

    assert (m.text, current(m)) == ("", "alpha")


def test_the_filter_matches_any_part_ignoring_case():
    m = menu(allow_filtering=True)

    press(m, "L", "T")

    assert [o["value"] for o in m.options] == ["delta"]


def test_enter_with_no_match_picks_nothing():
    m = menu(allow_filtering=True)

    assert press(m, "z", "z", "\r") is False


def test_default_starts_on_its_option():
    assert current(menu(default="gamma")) == "gamma"


# lists without a filter


def test_list_without_filter_is_always_in_normal_mode():
    m = menu()

    press(m, "j")

    assert m.mode == "normal"
    assert current(m) == "beta"
    with pytest.raises(PromptCancelled):
        press(m, ESC)


def test_inline_list_moves_with_h_l():
    m = menu(names=("Yes", "No"), inline=True)

    press(m, "l")
    assert current(m) == "No"
    press(m, "h")
    assert current(m) == "Yes"
    with pytest.raises(PromptCancelled):
        press(m, "q")


# text inputs


def text_input(text="", **kwargs):
    i = TextInput("Name", **kwargs)
    press(i, *text)
    return i


def test_input_types_vim_keys_as_text():
    assert text_input("jkq").text == "jkq"


def test_esc_in_an_input_goes_back():
    with pytest.raises(PromptCancelled):
        press(text_input("abc"), ESC)


def test_ctrl_u_clears_the_line():
    i = text_input("hello world")

    press(i, CTRL_U, "x")

    assert i.text == "x"


def test_ctrl_w_deletes_the_word_before_the_cursor():
    i = text_input("landing page ")

    press(i, CTRL_W)
    assert i.text == "landing "
    press(i, CTRL_W)
    assert i.text == ""


def test_typing_and_deleting_at_the_cursor():
    i = text_input("helo", value="")

    press(i, LEFT, "l", "\x1b[F", "!", "\x7f")

    assert i.text == "hello"


def test_an_empty_input_answers_its_default():
    i = text_input(default="website")

    assert press(i, "\r") is True
    assert i.value == "website"


def test_value_starts_the_text():
    assert text_input("s", value="page").text == "pages"


def test_an_invalid_value_stays_with_the_error():
    i = text_input("25:99", validator=start_validator)

    assert press(i, "\r") is False
    assert i.error.startswith("Use")
    assert any("Use" in line.plain for line in i.body(40, 5))
    # Typing again hides the error until the next Enter.
    press(i, "\x7f")
    assert i.error == ""


def test_any_pydantic_validator_works():
    i = text_input("x", validator=TypeAdapter(int))

    assert press(i, "\r") is False and i.error


# ranked filtering


def by_length(text, option):
    """Options containing `text`, shortest first."""

    name = option["name"]
    return -len(name) if text in name else None


def test_rank_hides_and_orders_the_matches():
    m = menu(names=("abcdef", "xyz", "abc"), allow_filtering=True, rank=by_length)

    press(m, "a", "b")

    assert [o["value"] for o in m.options] == ["abc", "abcdef"]


def test_rank_selects_the_best_match_when_the_filter_changes():
    m = menu(names=("abcdef", "abc"), allow_filtering=True, rank=by_length)
    press(m, "a", ESC, "j")
    assert current(m) == "abcdef"

    press(m, "i", "b")

    assert current(m) == "abc"


def test_rank_without_filter_keeps_every_option_in_order():
    m = menu(allow_filtering=True, rank=lambda text, option: None)

    assert [o["value"] for o in m.options] == ["alpha", "beta", "gamma", "delta"]


def test_button_is_drawn_apart_but_picked_like_any_option():
    m = menu(names=("Name", "Save"), button="Save")

    lines = [line.plain for line in m.body(40, 10)]
    assert lines == ["› Name", "", "   Save "]

    press(m, "j")
    assert current(m) == "Save"


def test_a_long_list_scrolls_to_the_cursor():
    m = menu(names=[f"item {i}" for i in range(50)])

    press(m, "G")
    lines = [line.plain for line in m.body(40, 10)]

    assert len(lines) == 10
    assert lines[-1] == "› item 49"


# full screen


def prompter(*keys, width=80, height=24):
    screen = FakeScreen(keys, width, height)
    p = ScreenPrompter(title="start")
    p.screen = screen
    return p, screen


def test_each_question_takes_the_whole_screen():
    p, screen = prompter("w", "e", "b", "\r")

    assert p.input("Name", placeholder="optional") == "web"

    frame = screen.last.splitlines()
    assert len(frame) == 24 and all(len(line) == 80 for line in frame)
    assert "─ start ─" in frame[1]
    assert "Enter confirm" in frame[-1]


def test_answers_are_listed_above_the_next_question():
    p, screen = prompter("w", "\r", "j", "\r", "\r")

    p.input("Name")
    p.ask("Project", [{"name": "a", "value": 1}, {"name": "b", "value": 2}])
    assert p.confirm("Start this session?") is True

    assert "Name     w" in screen.last and "Project  b" in screen.last
    assert "Yes" in screen.last


def test_a_form_starts_the_answers_afresh():
    p, screen = prompter("x", "\r", "\r")

    p.input("Name")
    p.ask("Edit", [{"name": "Save", "value": "save"}], button="save")

    assert "Name " not in screen.last


def test_questions_follow_resizes():
    p, screen = prompter(("resize", 100, 30), "\r")

    p.ask("Project", [{"name": "a", "value": 1}])

    assert [len(f.splitlines()) for f in screen.frames] == [24, 30]


def test_a_tiny_terminal_asks_for_more_room():
    p, screen = prompter("\r", width=20, height=5)

    p.ask("Project", [{"name": "a", "value": 1}])

    assert "bigger" in screen.last


def test_the_prompter_opens_the_screen_once(monkeypatch):
    opened = []

    class Opening(tui.PlainScreen):
        def __enter__(self):
            opened.append(self)
            return self

    monkeypatch.setattr(tui, "PlainScreen", Opening)

    with ScreenPrompter() as outer, tui.open_screen() as inner:
        assert outer.screen is inner

    assert len(opened) == 1


def test_the_title_is_the_running_command(monkeypatch, cli_db):

    from typer.testing import CliRunner

    from trak.sessions import commands
    from trak.typer_app import app

    titles = []

    class Recording:
        def __enter__(self):
            p = ScreenPrompter()
            p.screen = FakeScreen([])
            from trak.prompts import command_title

            titles.append(command_title())
            raise PromptCancelled

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(commands, "is_interactive", lambda: True)
    monkeypatch.setattr(commands, "make_prompter", lambda: Recording())

    CliRunner().invoke(app, ["sessions", "create"])

    assert titles == ["sessions create"]


def test_a_filterable_menu_can_start_in_normal_mode():
    options = [{"name": "a", "value": 1}, {"name": "b", "value": 2}]

    assert Menu("x", options, allow_filtering=True).mode == "insert"
    menu = Menu("x", options, allow_filtering=True, normal=True)
    assert menu.mode == "normal"
    menu.handle_key("j")
    assert menu.value == 2 and menu.text == ""
