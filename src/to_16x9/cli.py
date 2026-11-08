"""把照片轉成 16:9 比例。

模式:
  crop  - 置中裁切成 16:9(預設,不變形、會裁掉邊緣)
  pad   - 加邊框補成 16:9(保留完整畫面,邊框可用純色)
  blur  - 加邊框補成 16:9,邊框用模糊放大的原圖填滿

用法範例:
  to-16x9 photo.jpg
  to-16x9 photos/ -o out/ -m blur
  to-16x9 a.jpg b.png -m pad --color white --width 1920
  to-16x9 photo.jpg --offset-x -200 --offset-y 150
  to-16x9 photo.jpg --zoom 1.5 --offset-x 300

位移(--offset-x / --offset-y,單位為原尺寸像素,以中心為基準):
  crop      - 移動裁切框:+x 往右、-x 往左、+y 往下、-y 往上
  pad/blur  - 移動原圖在畫布中的位置,方向同上
  超出可移動範圍時會自動限制在邊界

縮放(--zoom,照片相對預設大小的比例):
  crop      - zoom >= 1,裁切框縮小為 1/zoom,上下左右都能移動
  pad/blur  - 0 < zoom <= 1,照片在畫布中縮小,四周都能移動

單張互動調整可用網頁版:https://changyy.github.io/py-to-16x9/
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from ._version import __version__

RATIO = 16 / 9
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def target_size(w, h, mode):
    """依模式算出 16:9 畫布尺寸(crop 往內縮,pad/blur 往外擴)。"""
    if mode == "crop":
        if w / h > RATIO:
            return round(h * RATIO), h
        return w, round(w / RATIO)
    if w / h > RATIO:
        return w, round(w / RATIO)
    return round(h * RATIO), h


def check_zoom(mode, zoom):
    """crop 只能放大(zoom >= 1),pad/blur 只能縮小(0 < zoom <= 1)。"""
    if mode == "crop" and zoom < 1:
        raise ValueError(f"crop 模式的 zoom 必須 >= 1,收到 {zoom}")
    if mode != "crop" and not 0 < zoom <= 1:
        raise ValueError(f"{mode} 模式的 zoom 必須介於 0 和 1 之間(可等於 1),收到 {zoom}")


def photo_size(w, h, zoom):
    """pad/blur 模式中照片縮放後的尺寸。"""
    return max(1, round(w * zoom)), max(1, round(h * zoom))


def offset_range(w, h, mode, zoom=1.0):
    """回傳輸出 16:9 尺寸,以及 offset-x / offset-y 可移動的 (最小, 最大) 範圍。

    crop 的尺寸即裁切框大小;pad/blur 則是畫布大小。
    """
    check_zoom(mode, zoom)
    tw, th = target_size(w, h, mode)
    if mode == "crop":
        if zoom != 1:
            tw = max(1, min(w, round(tw / zoom)))
            th = max(1, min(h, round(tw / RATIO)))
        slack_x, slack_y = w - tw, h - th
    else:
        pw, ph = photo_size(w, h, zoom)
        slack_x, slack_y = tw - pw, th - ph
    cx, cy = slack_x // 2, slack_y // 2
    return (tw, th), (-cx, slack_x - cx), (-cy, slack_y - cy)


def clamp_offset(offset, limits, axis, warn=True):
    """把位移限制在 limits 範圍內,超出時提示。"""
    lo, hi = limits
    clamped = min(max(offset, lo), hi)
    if warn and clamped != offset:
        print(f"  注意:offset-{axis}={offset} 超出範圍,已限制為 {clamped}", file=sys.stderr)
    return clamped


def convert(img, mode, color, dx=0, dy=0, warn=True, zoom=1.0):
    img = ImageOps.exif_transpose(img)  # 依 EXIF 轉正手機照片
    w, h = img.size
    (tw, th), xr, yr = offset_range(w, h, mode, zoom)
    dx = clamp_offset(dx, xr, "x", warn)
    dy = clamp_offset(dy, yr, "y", warn)

    if mode == "crop":
        left, top = (w - tw) // 2 + dx, (h - th) // 2 + dy
        return img.crop((left, top, left + tw, top + th))

    if mode == "blur":
        bg = ImageOps.fit(img.convert("RGB"), (tw, th), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=max(tw, th) // 40))
    else:
        bg = Image.new("RGB", (tw, th), color)

    pw, ph = photo_size(w, h, zoom)
    fg = img.convert("RGBA")
    if (pw, ph) != (w, h):
        fg = fg.resize((pw, ph), Image.LANCZOS)
    bg = bg.convert("RGBA")
    bg.paste(fg, ((tw - pw) // 2 + dx, (th - ph) // 2 + dy), fg)
    return bg


def save(out, dst, width=None, quality=95):
    """依需要縮放後存檔,JPEG 會轉成 RGB。回傳實際輸出的圖。"""
    if width:
        out = out.resize((width, round(width / RATIO)), Image.LANCZOS)
    if Path(dst).suffix.lower() in {".jpg", ".jpeg"}:
        out.convert("RGB").save(dst, quality=quality)
    else:
        out.save(dst)
    return out


def collect(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(f for f in p.iterdir() if f.suffix.lower() in EXTS)
        elif p.is_file():
            yield p
        else:
            print(f"找不到:{p}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="to-16x9", description="把照片轉成 16:9")
    ap.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("inputs", nargs="+", help="圖片檔或資料夾")
    ap.add_argument("-o", "--outdir", default="output_16x9", help="輸出資料夾(預設 output_16x9)")
    ap.add_argument("-m", "--mode", choices=["crop", "pad", "blur"], default="crop")
    ap.add_argument("--color", default="black", help="pad 模式的邊框顏色,例如 black、white、#202020")
    ap.add_argument("--width", type=int, help="輸出寬度(高度自動依 16:9 計算),例如 1920")
    ap.add_argument("--offset-x", type=int, default=0, help="從中心水平位移的像素,正數往右、負數往左")
    ap.add_argument("--offset-y", type=int, default=0, help="從中心垂直位移的像素,正數往下、負數往上")
    ap.add_argument("--zoom", type=float, default=1.0,
                    help="照片縮放比例:crop 用 >= 1(裁切框變小),pad/blur 用 0~1(照片變小),預設 1")
    ap.add_argument("--quality", type=int, default=95, help="JPEG 品質(預設 95)")
    args = ap.parse_args(argv)
    try:
        check_zoom(args.mode, args.zoom)
    except ValueError as e:
        ap.error(str(e))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    count = 0
    for src in collect(args.inputs):
        try:
            with Image.open(src) as img:
                out = convert(img, args.mode, args.color, args.offset_x, args.offset_y, zoom=args.zoom)
        except Exception as e:
            print(f"略過 {src}:{e}", file=sys.stderr)
            continue

        dst = outdir / src.name
        out = save(out, dst, args.width, args.quality)
        print(f"{src} -> {dst}  {out.size[0]}x{out.size[1]}")
        count += 1

    print(f"完成,共 {count} 張")


if __name__ == "__main__":
    main()
