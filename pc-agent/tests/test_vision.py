import json

from PIL import Image

from desktop_friend.vision import Vision, annotate_grid, crop_box, parse_point


class StubCapture:
    def __init__(self, size=(1920, 1080)):
        self.size = size

    def grab(self):
        return Image.new("RGB", self.size, "white")


class ScriptedGroq:
    """Answers the first (full screen) pass and the refine pass differently."""

    configured = True

    def __init__(self, answers):
        self.answers = list(answers)
        self.images = []

    async def vision(self, model, prompt, jpeg, system=None, json_mode=False):
        import io

        self.images.append(Image.open(io.BytesIO(jpeg)).size)
        return self.answers.pop(0)


def test_parse_point_variants():
    assert parse_point('{"found": true, "x": 500, "y": 250, "description": "Save"}') == (True, 0.5, 0.25, "Save")
    assert parse_point('Sure! ```json\n{"found": true, "x": 100, "y": 900}\n```')[1:3] == (0.1, 0.9)
    assert parse_point('{"found": true, "x": 0.5, "y": 0.25}')[1:3] == (0.5, 0.25)  # model used 0..1
    assert parse_point('{"found": "false"}')[0] is False
    assert parse_point('{"x": 2000, "y": -5}')[1:3] == (1.0, 0.0)  # clamped
    assert parse_point("no json here") is None


def test_crop_box_clamps_to_image():
    assert crop_box(1000, 800, 0.5, 0.5) == (350, 280, 650, 520) or crop_box(1000, 800, 0.5, 0.5)[2] - crop_box(1000, 800, 0.5, 0.5)[0] == 360
    l, t, r, b = crop_box(1920, 1080, 0.0, 0.0)
    assert (l, t) == (0, 0) and r - l == 576 and b - t == 324
    l, t, r, b = crop_box(1920, 1080, 1.0, 1.0)
    assert (r, b) == (1920, 1080)


def test_annotate_grid_keeps_size():
    img = Image.new("RGB", (1280, 720), "white")
    out = annotate_grid(img)
    assert out.size == img.size and out.getpixel((128 * 3, 360)) != (255, 255, 255)


async def test_locate_two_pass_refines():
    # pass 1 says (0.5, 0.5); pass 2 says the element is at the top-left quarter of the crop
    groq = ScriptedGroq([json.dumps({"found": True, "x": 500, "y": 500, "description": "Save"}),
                         json.dumps({"found": True, "x": 250, "y": 250, "description": "Save button"})])
    v = Vision(groq, lambda: "m", lambda: True, StubCapture((1920, 1080)))
    res = await v.locate("save")
    l, t, r, b = crop_box(1920, 1080, 0.5, 0.5)
    assert res.refined and res.description == "Save button"
    assert abs(res.x - (l + 0.25 * (r - l)) / 1920) < 1e-6
    assert abs(res.y - (t + 0.25 * (b - t)) / 1080) < 1e-6
    assert groq.images[0][0] == 1280 and groq.images[1][0] == 1024  # downscaled full shot, then zoomed crop


async def test_locate_not_found_and_no_refine():
    v = Vision(ScriptedGroq(['{"found": false}']), lambda: "m", lambda: True, StubCapture())
    assert await v.locate("ghost") is None
    v = Vision(ScriptedGroq(['{"found": true, "x": 100, "y": 200}']), lambda: "m", lambda: False, StubCapture())
    res = await v.locate("thing")
    assert (round(res.x, 3), round(res.y, 3), res.refined) == (0.1, 0.2, False)
