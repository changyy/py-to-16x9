import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from to_16x9 import __version__
from to_16x9.cli import check_zoom, clamp_offset, collect, convert, main, offset_range, save, target_size


def bands(w, h):
    """上紅、中白、下藍的直式測試圖,方便檢查裁切位置。"""
    img = Image.new("RGB", (w, h), "white")
    img.paste((255, 0, 0), (0, 0, w, h // 4))
    img.paste((0, 0, 255), (0, h * 3 // 4, w, h))
    return img


class TargetSizeTest(unittest.TestCase):
    def test_crop_shrinks(self):
        self.assertEqual(target_size(1600, 1600, "crop"), (1600, 900))
        self.assertEqual(target_size(4000, 1000, "crop"), (1778, 1000))

    def test_pad_expands(self):
        self.assertEqual(target_size(1600, 1600, "pad"), (2844, 1600))
        self.assertEqual(target_size(4000, 1000, "blur"), (4000, 2250))

    def test_already_16x9(self):
        for mode in ("crop", "pad", "blur"):
            self.assertEqual(target_size(1920, 1080, mode), (1920, 1080))


class OffsetRangeTest(unittest.TestCase):
    def test_crop_range(self):
        size, xr, yr = offset_range(1600, 1600, "crop")
        self.assertEqual(size, (1600, 900))
        self.assertEqual(xr, (0, 0))
        self.assertEqual(yr, (-350, 350))

    def test_pad_range(self):
        size, xr, yr = offset_range(1600, 1600, "pad")
        self.assertEqual(size, (2844, 1600))
        self.assertEqual(xr, (-622, 622))
        self.assertEqual(yr, (0, 0))

    def test_odd_slack(self):
        _, _, yr = offset_range(16, 10, "crop")  # 16x9,剩 1px
        self.assertEqual(yr, (0, 1))

    def test_crop_zoom(self):
        size, xr, yr = offset_range(1600, 1600, "crop", zoom=2)
        self.assertEqual(size, (800, 450))
        self.assertEqual(xr, (-400, 400))
        self.assertEqual(yr, (-575, 575))

    def test_pad_zoom(self):
        size, xr, yr = offset_range(1600, 1600, "pad", zoom=0.5)
        self.assertEqual(size, (2844, 1600))  # 畫布不變,照片縮成 800x800
        self.assertEqual(xr, (-1022, 1022))
        self.assertEqual(yr, (-400, 400))

    def test_zoom_one_matches_default(self):
        for mode in ("crop", "pad", "blur"):
            self.assertEqual(offset_range(1234, 987, mode, 1.0), offset_range(1234, 987, mode))

    def test_invalid_zoom(self):
        for mode, zoom in (("crop", 0.9), ("pad", 1.1), ("blur", 0), ("pad", -1)):
            with self.assertRaises(ValueError):
                check_zoom(mode, zoom)

    def test_clamp(self):
        self.assertEqual(clamp_offset(5, (-10, 10), "x"), 5)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(clamp_offset(99, (-10, 10), "x"), 10)
            self.assertEqual(clamp_offset(-99, (-10, 10), "y"), -10)
        self.assertIn("offset-x=99", err.getvalue())

    def test_clamp_quiet(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            clamp_offset(99, (0, 0), "x", warn=False)
        self.assertEqual(err.getvalue(), "")


class ConvertTest(unittest.TestCase):
    def test_crop_center(self):
        out = convert(bands(1600, 1600), "crop", "black")
        self.assertEqual(out.size, (1600, 900))
        self.assertEqual(out.getpixel((800, 0)), (255, 0, 0))
        self.assertEqual(out.getpixel((800, 899)), (0, 0, 255))

    def test_crop_offset_up_and_down(self):
        up = convert(bands(1600, 1600), "crop", "black", dy=-350)
        self.assertEqual(up.getpixel((800, 0)), (255, 0, 0))
        self.assertEqual(up.getpixel((800, 899)), (255, 255, 255))
        down = convert(bands(1600, 1600), "crop", "black", dy=350)
        self.assertEqual(down.getpixel((800, 0)), (255, 255, 255))
        self.assertEqual(down.getpixel((800, 899)), (0, 0, 255))

    def test_crop_offset_clamped(self):
        with contextlib.redirect_stderr(io.StringIO()):
            far = convert(bands(1600, 1600), "crop", "black", dy=9999)
        edge = convert(bands(1600, 1600), "crop", "black", dy=350)
        self.assertEqual(list(far.getdata()), list(edge.getdata()))

    def test_crop_zoom_offset_reaches_corner(self):
        img = Image.new("RGB", (1600, 1600), "white")
        img.putpixel((0, 0), (255, 0, 0))
        out = convert(img, "crop", "black", dx=-400, dy=-575, zoom=2)
        self.assertEqual(out.size, (800, 450))
        self.assertEqual(out.getpixel((0, 0)), (255, 0, 0))

    def test_pad_zoom(self):
        out = convert(Image.new("RGB", (1600, 1600), "white"), "pad", "black", dx=-1022, dy=400, zoom=0.5)
        self.assertEqual(out.size, (2844, 1600))
        self.assertEqual(out.getpixel((0, 1599))[:3], (255, 255, 255))   # 照片貼在左下角
        self.assertEqual(out.getpixel((799, 800))[:3], (255, 255, 255))
        self.assertEqual(out.getpixel((800, 1599))[:3], (0, 0, 0))
        self.assertEqual(out.getpixel((0, 799))[:3], (0, 0, 0))

    def test_pad_center(self):
        out = convert(Image.new("RGB", (1600, 1600), "white"), "pad", "red")
        self.assertEqual(out.size, (2844, 1600))
        self.assertEqual(out.getpixel((0, 800))[:3], (255, 0, 0))
        self.assertEqual(out.getpixel((621, 800))[:3], (255, 0, 0))
        self.assertEqual(out.getpixel((622, 800))[:3], (255, 255, 255))
        self.assertEqual(out.getpixel((2221, 800))[:3], (255, 255, 255))
        self.assertEqual(out.getpixel((2222, 800))[:3], (255, 0, 0))

    def test_pad_offset(self):
        out = convert(Image.new("RGB", (1600, 1600), "white"), "pad", "black", dx=300)
        self.assertEqual(out.getpixel((921, 800))[:3], (0, 0, 0))
        self.assertEqual(out.getpixel((922, 800))[:3], (255, 255, 255))

    def test_pad_offset_to_edge(self):
        out = convert(Image.new("RGB", (1600, 1600), "white"), "pad", "black", dx=-622)
        self.assertEqual(out.getpixel((0, 800))[:3], (255, 255, 255))
        self.assertEqual(out.getpixel((2843, 800))[:3], (0, 0, 0))

    def test_blur_fills_border_with_photo_colors(self):
        out = convert(Image.new("RGB", (1600, 1600), (0, 200, 0)), "blur", "black")
        self.assertEqual(out.size, (2844, 1600))
        r, g, b = out.getpixel((10, 800))[:3]
        self.assertGreater(g, 150)
        self.assertLess(r + b, 30)

    def test_keeps_transparency(self):
        out = convert(Image.new("RGBA", (400, 400), (0, 0, 0, 0)), "pad", "white")
        self.assertEqual(out.getpixel((355, 200)), (255, 255, 255, 255))

    def test_exif_orientation(self):
        img = Image.new("RGB", (400, 300), "white")
        exif = Image.Exif()
        exif[0x0112] = 6  # 需順時針轉 90 度
        buf = io.BytesIO()
        img.save(buf, "JPEG", exif=exif.tobytes())
        buf.seek(0)
        with Image.open(buf) as rotated:
            out = convert(rotated, "pad", "black")
        self.assertEqual(out.size, (711, 400))  # 轉正後是 300x400 直式


class SaveAndCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            main(list(argv))
        return out.getvalue(), err.getvalue()

    def test_save_resizes_and_converts_rgba_jpeg(self):
        dst = self.dir / "a.jpg"
        out = save(Image.new("RGBA", (3200, 1800)), dst, width=1920)
        self.assertEqual(out.size, (1920, 1080))
        with Image.open(dst) as img:
            self.assertEqual((img.format, img.mode, img.size), ("JPEG", "RGB", (1920, 1080)))

    def test_collect_directory_filters_and_sorts(self):
        for n in ("b.png", "a.JPG", "notes.txt"):
            (self.dir / n).write_bytes(b"")
        self.assertEqual([p.name for p in collect([self.dir])], ["a.JPG", "b.png"])

    def test_collect_missing(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(list(collect([self.dir / "nope.jpg"])), [])
        self.assertIn("nope.jpg", err.getvalue())

    def test_main_batch(self):
        src = self.dir / "in"
        src.mkdir()
        bands(1200, 1600).save(src / "tall.jpg")
        Image.new("RGBA", (4000, 1000), "blue").save(src / "wide.png")
        (src / "broken.png").write_bytes(b"not an image")
        outdir = self.dir / "out"

        stdout, stderr = self.run_main(str(src), "-o", str(outdir), "-m", "blur", "--width", "640")

        self.assertIn("完成,共 2 張", stdout)
        self.assertIn("broken.png", stderr)
        for n in ("tall.jpg", "wide.png"):
            with Image.open(outdir / n) as img:
                self.assertEqual(img.size, (640, 360))

    def test_main_zoom(self):
        bands(1600, 1600).save(self.dir / "sq.png")
        outdir = self.dir / "out"
        self.run_main(str(self.dir / "sq.png"), "-o", str(outdir), "--zoom", "2", "--offset-x", "400")
        with Image.open(outdir / "sq.png") as img:
            self.assertEqual(img.size, (800, 450))

    def test_main_rejects_bad_zoom(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_main(str(self.dir), "-m", "pad", "--zoom", "1.5")
        self.assertEqual(cm.exception.code, 2)

    def test_version(self):
        self.assertRegex(__version__, r"^1\.\d{8}\.1\d{6}$")  # 1.YYYYmmdd.1HHmmss
        with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), f"to-16x9 {__version__}")

    def test_main_offset(self):
        bands(1600, 1600).save(self.dir / "sq.png")
        outdir = self.dir / "out"
        self.run_main(str(self.dir / "sq.png"), "-o", str(outdir), "--offset-y", "-350")
        with Image.open(outdir / "sq.png") as img:
            self.assertEqual(img.getpixel((800, 899))[:3], (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
