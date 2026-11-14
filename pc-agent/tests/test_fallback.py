import pytest

from desktop_friend.fallback import route


@pytest.mark.parametrize(
    "text, tool, args",
    [
        ("Search the web for cute puppies", "web_search", {"query": "cute puppies"}),
        ("google best pizza near me", "web_search", {"query": "best pizza near me"}),
        ("Point at the save button", "point_at", {"target": "the save button"}),
        ("click on the Save button", "click", {"target": "the Save button", "double": False, "button": "left"}),
        ("double-click the folder", "click", {"target": "the folder", "double": True, "button": "left"}),
        ("press enter", "press_keys", {"keys": ["enter"]}),
        ("press ctrl+s", "press_keys", {"keys": ["ctrl", "s"]}),
        ("scroll down 3", "scroll", {"direction": "down", "amount": 3}),
        ("scroll up", "scroll", {"direction": "up", "amount": 5}),
        ("type hello world and press enter", "type_text", {"text": "hello world", "press_enter": True}),
        ("open youtube.com", "open_website", {"url": "youtube.com"}),
        ("open the calculator", "open_app", {"name": "calculator"}),
        ("launch Spotify", "open_app", {"name": "Spotify"}),
        ("what's on my screen?", "look_at_screen", {"question": "What is on my screen?"}),
    ],
)
def test_routes(text, tool, args):
    assert route(text) == (tool, args)


def test_unknown():
    assert route("tell me a joke") is None
