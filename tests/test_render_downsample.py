"""The 4000 px final render becomes the 2000 px final in place, alpha intact."""

import numpy as np
from PIL import Image

from logo_maker.render import _downsample_final


def test_final_downsamples_in_place_keeping_alpha(tmp_path):
    arr = np.zeros((4000, 4000, 4), dtype=np.uint8)
    arr[1000:3000, 1000:3000] = (30, 74, 122, 255)
    png = tmp_path / "final.png"
    Image.fromarray(arr).save(png)

    out = _downsample_final(png)

    assert out == png
    assert sorted(p.name for p in tmp_path.iterdir()) == ["final.png"]
    small = np.array(Image.open(png))
    assert small.shape == (2000, 2000, 4)
    assert small[0, 0, 3] == 0
    assert tuple(small[1000, 1000]) == (30, 74, 122, 255)


def test_small_final_is_left_alone(tmp_path):
    png = tmp_path / "final.png"
    Image.new("RGBA", (2000, 2000), (1, 2, 3, 255)).save(png)
    before = png.read_bytes()
    assert _downsample_final(png) == png
    assert png.read_bytes() == before
