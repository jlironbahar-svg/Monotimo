from urllib.parse import parse_qs, urlparse

from desktop_friend.pairing import PairingStore, pairing_url, qr_png_bytes


def test_pair_then_device_token(tmp_path):
    store = PairingStore(tmp_path / "p.json")
    assert store.check_pair_token(store.pair_token)
    assert not store.check_pair_token("wrong")
    assert not store.check_pair_token(None)
    token = store.register_device("dev1", "Pixel")
    assert store.check_device_token("dev1", token)
    assert not store.check_device_token("dev2", token)
    assert not store.check_device_token("dev1", "nope")
    # tokens are stored hashed, never in clear text
    assert token not in (tmp_path / "p.json").read_text()


def test_persists_across_restarts_and_rotation(tmp_path):
    store = PairingStore(tmp_path / "p.json")
    pair = store.pair_token
    token = store.register_device("dev1", "Pixel")
    again = PairingStore(tmp_path / "p.json")
    assert again.pair_token == pair
    assert again.check_device_token("dev1", token)
    again.rotate_pair_token()
    assert not again.check_pair_token(pair)
    assert again.check_device_token("dev1", token), "rotating the QR must not log out paired phones"
    again.forget_devices()
    assert not again.check_device_token("dev1", token)


def test_pairing_url_roundtrip():
    url = pairing_url(["192.168.1.5", "10.0.0.2"], 8765, "a-b_c", "Lily's PC")
    assert url.startswith("desktopfriend://pair?")
    q = parse_qs(urlparse(url.replace("desktopfriend://", "http://x/")).query)
    assert q["h"] == ["192.168.1.5,10.0.0.2"]
    assert q["p"] == ["8765"] and q["t"] == ["a-b_c"] and q["n"] == ["Lily's PC"]


def test_qr_png():
    assert qr_png_bytes("desktopfriend://pair?v=1").startswith(b"\x89PNG")
