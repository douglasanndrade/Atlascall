"""Overlay a grid + tile index on a tileset so we can identify tiles by (col,row).
Usage: py -3 annotate.py <tileset.png> <out.png> [scale] [tile=32] [row_start] [row_end]
Index shown is the 0-based (col,row). GID in Tiled = row*cols + col + firstgid.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

src = sys.argv[1]
out = sys.argv[2]
scale = int(sys.argv[3]) if len(sys.argv) > 3 else 3
tile = int(sys.argv[4]) if len(sys.argv) > 4 else 32
row_start = int(sys.argv[5]) if len(sys.argv) > 5 else 0
row_end = int(sys.argv[6]) if len(sys.argv) > 6 else 10**9

img = Image.open(src).convert("RGBA")
cols = img.width // tile
rows = img.height // tile
row_end = min(row_end, rows)

# crop to row range
crop = img.crop((0, row_start * tile, img.width, row_end * tile))
big = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
# checkerboard behind transparency
bg = Image.new("RGBA", big.size, (40, 40, 48, 255))
bg.alpha_composite(big)
big = bg
d = ImageDraw.Draw(big)
ts = tile * scale
try:
    font = ImageFont.truetype("arial.ttf", max(9, scale * 3))
except Exception:
    font = ImageFont.load_default()

for c in range(cols + 1):
    d.line([(c * ts, 0), (c * ts, big.height)], fill=(0, 255, 180, 120), width=1)
for r in range(row_end - row_start + 1):
    d.line([(0, r * ts), (big.width, r * ts)], fill=(0, 255, 180, 120), width=1)

for r in range(row_start, row_end):
    for c in range(cols):
        x = c * ts + 1
        y = (r - row_start) * ts + 1
        d.text((x, y), f"{c},{r}", fill=(255, 235, 0, 255), font=font)

big.save(out)
print(f"{src}: {cols} cols x {rows} rows (tile {tile}). Saved rows {row_start}-{row_end} -> {out}")
