import pytest
from rich.text import Text
from rich_toolkit.styles import MinimalStyle

from trak.prompts import (
    CTRL_D,
    CTRL_U,
    CTRL_W,
    ESC,
    PromptCancelled,
    VimInput,
    VimMenu,
    split_escape,
)

DOWN, UP = "\x1b[B", "\x1b[A"


def menu(names=("alpha", "beta", "gamma", "delta"), **kwargs):
    options = [{"name": name, "value": name} for name in names]
    return VimMenu(label="Pick", options=options, style=MinimalStyle(), **kwargs)


def press(element, *keys):
    for key in keys:
        element.handle_key(key)


def current(m):
    return m.options[m.selected]["value"]


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
    assert m.should_show_cursor


def test_esc_switches_to_normal_mode_where_j_k_move():
    m = menu(allow_filtering=True)

    press(m, ESC, "j", "j", "k")

    assert m.mode == "normal"
    assert m.text == ""
    assert current(m) == "beta"
    assert not m.should_show_cursor
    assert "NORMAL" in m.selection_count_hint


def test_arrows_move_in_both_modes():
    m = menu(allow_filtering=True)

    press(m, DOWN, ESC, DOWN)
    assert current(m) == "gamma"

    press(m, UP, UP, UP)
    assert current(m) == "delta"  # wraps around, like rich-toolkit


def test_normal_mode_jumps():
    m = menu(allow_filtering=True)

    press(m, ESC, "G")
    assert current(m) == "delta"
    press(m, "g")
    assert current(m) == "alpha"


def test_half_screen_moves_stop_at_the_ends():
    m = menu(
        names=[f"item {i}" for i in range(10)], allow_filtering=True, max_visible=4
    )

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


# lists without a filter


def test_list_without_filter_is_always_in_normal_mode():
    m = menu()

    press(m, "j")

    assert m.mode == "normal"
    assert current(m) == "beta"
    assert m.selection_count_hint is None
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


def text_input(text=""):
    i = VimInput(label="Name", style=MinimalStyle())
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

    names = [option["name"] for option in m.options]
    assert names[0] == "Name\n"  # a blank line above the button
    assert isinstance(names[1], Text)
    assert names[1].plain == " Save "

    press(m, "j")
    assert current(m) == "Save"
    assert m.result_display_name == "Save"
