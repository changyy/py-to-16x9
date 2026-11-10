# to-16x9

![PyPI](https://img.shields.io/pypi/v/to-16x9.svg)
[![PyPI Downloads](https://static.pepy.tech/badge/to-16x9)](https://pepy.tech/projects/to-16x9)
[![Tests](https://github.com/changyy/py-to-16x9/actions/workflows/test.yml/badge.svg)](https://github.com/changyy/py-to-16x9/actions/workflows/test.yml)

A command-line tool that batch converts photos to a 16:9 aspect ratio — by center crop, solid-color padding, or a blurred background — with pixel offsets to reposition the frame.

**Try it in your browser:** https://changyy.github.io/py-to-16x9/ — open a photo, drag it into place, download. Everything runs locally; nothing is uploaded.

## Features

- ✂️ **crop** — center crop to 16:9, no distortion
- 🖼️ **pad** — keep the whole photo, fill the sides with a solid color
- 🌫️ **blur** — keep the whole photo, fill the sides with a blurred copy of itself
- 🎯 `--offset-x` / `--offset-y` — shift from center by any positive or negative number of pixels, clamped to the image edges
- 🔍 `--zoom` — tighter crop frame, or a smaller photo on the canvas, so it can move in both directions
- 📁 Batch process files and folders in one command
- 📐 Optional fixed output width (e.g. `--width 1920` → 1920×1080)
- 🔲 `--ratio` for other aspect ratios, e.g. `9:7`, `4:3`, `1:1` (default 16:9)
- 📱 Honors EXIF orientation from phone cameras
- 🌐 Companion web page with drag / arrow-key positioning that shows the matching CLI command

## Installation

```bash
# Using pip
pip install to-16x9

# From source
git clone https://github.com/changyy/py-to-16x9.git
cd py-to-16x9
pip install -e .
```

## Usage

```bash
to-16x9 photo.jpg                                  # center crop → output_16x9/photo.jpg
to-16x9 photos/ -o out/ -m blur                    # whole folder, blurred background
to-16x9 a.jpg b.png -m pad --color white --width 1920
to-16x9 photo.jpg --offset-x -200 --offset-y 150   # shift from center
to-16x9 photo.jpg --zoom 1.5 --offset-x 300        # tighter crop, then move right
to-16x9 photos/ --ratio 9:7 --width 900            # 9:7 → output_9x7/, 900×700
```

`python -m to_16x9 ...` works too. Source files are never modified.

### Options

| Option | Description |
|---|---|
| `-o, --outdir` | Output folder (default `output_WxH`, e.g. `output_16x9`) |
| `-m, --mode` | `crop` (default), `pad` or `blur` |
| `-r, --ratio` | Output aspect ratio as `W:H` or `WxH`, e.g. `9:7`, `4:3` (default `16:9`) |
| `--color` | Border color for `pad`, e.g. `black`, `white`, `#202020` |
| `--width` | Output width; height follows the ratio |
| `--offset-x` | Horizontal shift from center in source pixels; positive = right |
| `--offset-y` | Vertical shift from center in source pixels; positive = down |
| `--zoom` | Photo scale vs. the default fit: `>= 1` for `crop`, `0`–`1` for `pad` / `blur` (default 1) |
| `--quality` | JPEG quality (default 95) |

### How offsets work

- **crop**: moves the crop frame over the photo. `--offset-y -300` keeps more of the top.
- **pad / blur**: moves the photo on the 16:9 canvas.
- Offsets beyond the movable range are clamped, with a notice.
- At `--zoom 1` one axis has no room to move: a portrait photo in crop mode already uses its full width, so `--offset-x` stays 0. Use `--zoom` to free up both axes:
  - **crop**: `--zoom 1.5` shrinks the crop frame to 1/1.5 of its size (the output is smaller too; add `--width` to scale it back up).
  - **pad / blur**: `--zoom 0.8` shrinks the photo on the canvas, leaving room on all four sides.

A typical workflow: find the right zoom and position for one photo on the [web page](https://changyy.github.io/py-to-16x9/), copy the command it shows, and run it on the whole folder.

## Python API

```python
from PIL import Image
from to_16x9 import convert

with Image.open("photo.jpg") as img:
    out = convert(img, "blur", "black", dx=0, dy=-100, zoom=0.9)
out.convert("RGB").save("photo_16x9.jpg")

# Other ratios: pass ratio=width/height
with Image.open("photo.jpg") as img:
    out = convert(img, "crop", "black", ratio=9 / 7)
```

## Development

```bash
pip install -e .
python -m unittest discover -s tests -v
```

Run `to-16x9 --version` to see the installed version.

### Releasing

The version lives only in [`src/to_16x9/_version.py`](src/to_16x9/_version.py) and follows `1.YYYYmmdd.1HHmmss`. Bump it, commit, then publish a GitHub Release tagged with the same string (e.g. `1.20261109.1002300`); the `Upload Python Package` workflow tests, builds and publishes to PyPI.

The web page lives in [`docs/index.html`](docs/index.html) as a single static file and is served by GitHub Pages from the `docs/` folder.

## License

MIT
