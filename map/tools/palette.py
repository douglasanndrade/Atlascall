"""Render a verification sheet of chosen furniture multi-tile blocks."""
from PIL import Image, ImageDraw, ImageFont
mo = Image.open("tilesets/ModernOffice.png").convert("RGBA")
TILE = 32

# each item: (label, col, row, w, h) block from ModernOffice
items = [
    ("chair gray down", 0, 8, 1, 1),
    ("chair gray up", 0, 9, 1, 1),
    ("chair orange", 0, 11, 1, 1),
    ("chair side L", 4, 8, 1, 1),
    ("chair side R", 5, 8, 1, 1),
    ("plant tall", 6, 8, 1, 2),
    ("plant snake", 6, 10, 1, 2),
    ("plant small", 6, 12, 1, 2),
    ("monitor white", 13, 10, 1, 1),
    ("monitor blue", 12, 12, 1, 1),
    ("laptop", 10, 8, 1, 1),
    ("screen chart", 10, 13, 1, 2),
    ("screen pie", 10, 15, 1, 2),
    ("screen blank", 10, 11, 1, 2),
    ("desk2 top+front", 5, 18, 1, 2),
    ("desk wood", 5, 20, 1, 2),
    ("table3", 7, 29, 3, 2),
    ("table white", 1, 31, 3, 2),
    ("sofa gray", 0, 18, 2, 2),
    ("armchair blue", 3, 16, 1, 1),
    ("armchair gray", 4, 16, 1, 1),
    ("bookshelf", 7, 12, 1, 3),
    ("reception", 1, 27, 3, 2),
    ("printer", 8, 24, 1, 2),
    ("workstation blue", 9, 35, 2, 1),
    ("rug beige", 0, 0, 3, 3),
    ("frame team", 0, 13, 1, 1),
]

scale = 3
cell_w, cell_h = 5 * TILE * scale // 2, 4 * TILE * scale // 2
cols = 6
rows = (len(items) + cols - 1) // cols
pad = 26
W = cols * (cell_w + pad) + pad
H = rows * (cell_h + pad) + pad
sheet = Image.new("RGBA", (W, H), (35, 35, 42, 255))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arial.ttf", 15)
except Exception:
    font = ImageFont.load_default()

for i, (label, c, r, w, h) in enumerate(items):
    gx = i % cols
    gy = i // cols
    x0 = pad + gx * (cell_w + pad)
    y0 = pad + gy * (cell_h + pad)
    block = mo.crop((c * TILE, r * TILE, (c + w) * TILE, (r + h) * TILE))
    block = block.resize((block.width * scale, block.height * scale), Image.NEAREST)
    bg = Image.new("RGBA", block.size, (60, 60, 70, 255))
    bg.alpha_composite(block)
    sheet.alpha_composite(bg, (x0, y0 + 20))
    d.text((x0, y0), f"{label} ({c},{r})", fill=(255, 235, 0, 255), font=font)

sheet.convert("RGB").save("tools/_palette.png")
print("saved tools/_palette.png", len(items), "items")
