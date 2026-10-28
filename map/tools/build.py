"""Atlas Call office map builder.
Outputs a valid WorkAdventure .tmj + copies tilesets + renders a preview.

Tilesets (firstgid):
  RoomBuilder.png  -> 1    (16 cols x 14 rows = 224 tiles)
  ModernOffice.png -> 225  (16 cols x 53 rows = 848 tiles)
  atlas-a.png      -> 1073 (4 cols x 4 rows  = 16 tiles, the green "A" logo)
GID(tileset) = firstgid + row*cols + col
"""
import json, os, shutil
from PIL import Image, ImageDraw, ImageFont

TILE = 32
W, H = 50, 36

RB_FIRST, RB_COLS = 1, 16
MO_FIRST, MO_COLS = 225, 16
LOGO_FIRST, LOGO_COLS = 1073, 4

def rb(c, r): return RB_FIRST + r * RB_COLS + c
def mo(c, r): return MO_FIRST + r * MO_COLS + c

# ---- RoomBuilder tiles ----
FLOOR_WOOD = rb(13, 9)
FLOOR_MARBLE = rb(10, 5)
FLOOR_SOFT = rb(13, 7)
WALL = rb(11, 3)

# ---- ModernOffice furniture ----
DESK_TOP, DESK_FRONT = mo(5, 18), mo(5, 19)
MON_BLUE = mo(12, 12)
CHAIR_OR = mo(0, 11)
PLANT_T, PLANT_T2 = mo(6, 8), mo(6, 9)
PLANT_S, PLANT_S2 = mo(6, 10), mo(6, 11)
SOFA = [mo(0, 18), mo(1, 18), mo(0, 19), mo(1, 19)]
ARM_BL, ARM_GY = mo(3, 16), mo(4, 16)
BOOK = [mo(7, 12), mo(7, 13), mo(7, 14)]
RECEP = [mo(1, 27), mo(2, 27), mo(3, 27), mo(1, 28), mo(2, 28), mo(3, 28)]
PRINTER = [mo(8, 24), mo(8, 25)]
TABLE3 = [mo(7, 29), mo(8, 29), mo(9, 29), mo(7, 30), mo(8, 30), mo(9, 30)]
SCREEN_CHART = mo(10, 13)
FRAME = mo(0, 13)
RUG = [mo(c, r) for r in range(3) for c in range(3)]  # 0,0..2,2

COLLIDE = set([WALL, DESK_TOP, DESK_FRONT, PLANT_T, PLANT_T2, PLANT_S, PLANT_S2,
               ARM_BL, ARM_GY, *SOFA, *BOOK, *RECEP, *PRINTER, *TABLE3])

# ---- layers (flat lists, 0 = empty) ----
L = {k: [0] * (W * H) for k in ["start", "floor", "floordecor", "walls", "furn1", "furn2", "above"]}
areas = []

def put(layer, x, y, g):
    if 0 <= x < W and 0 <= y < H and g:
        L[layer][y * W + x] = g

def fill(layer, x0, y0, x1, y1, g):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(layer, x, y, g)

def rect_walls(x0, y0, x1, y1, doors=()):
    dset = set(doors)
    cells = []
    for x in range(x0, x1 + 1):
        cells += [(x, y0), (x, y1)]
    for y in range(y0, y1 + 1):
        cells += [(x0, y), (x1, y)]
    for (x, y) in cells:
        if (x, y) not in dset:
            put("walls", x, y, WALL)

def area(name, x0, y0, x1, y1):
    areas.append({
        "id": len(areas) + 1, "name": name, "type": "area",
        "x": x0 * TILE, "y": y0 * TILE,
        "width": (x1 - x0 + 1) * TILE, "height": (y1 - y0 + 1) * TILE,
        "visible": True, "rotation": 0, "properties": [],
    })

def workstation(x, y):
    put("furn1", x, y, DESK_TOP)
    put("furn1", x, y + 1, DESK_FRONT)
    put("furn2", x, y, MON_BLUE)
    put("furn2", x, y + 2, CHAIR_OR)

def plant(x, y, snake=False):
    put("furn1", x, y, PLANT_S if snake else PLANT_T)
    put("furn1", x, y + 1, PLANT_S2 if snake else PLANT_T2)

def block(cells, gids, x, y, w):
    for i, g in enumerate(gids):
        cells.append((x + i % w, y + i // w, g))

# ===== base floor + outer walls =====
fill("floor", 0, 0, W - 1, H - 1, FLOOR_WOOD)
rect_walls(0, 0, W - 1, H - 1)

cols3 = [(1, 15), (17, 32), (34, 48)]
RT0, RT1, RB0, RB1 = 1, 10, 25, 34

# ===== top + bottom private rooms =====
def build_room(name, x0, y0, x1, y1, door):
    rect_walls(x0, y0, x1, y1, doors=[door])
    fill("floor", x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR_WOOD)
    ix0, iy0, ix1 = x0 + 1, y0 + 1, x1 - 1
    for k, dx in enumerate([ix0 + 1, ix0 + 5, ix0 + 9]):
        if dx + 0 <= ix1 - 1:
            workstation(dx, iy0 + 1)
    plant(ix1 - 1, iy0 + 1)
    put("above", (x0 + x1) // 2 - 1, y0, FRAME)
    area(name, x0 + 1, y0 + 1, x1 - 1, y1 - 1)

for i, (x0, x1) in enumerate(cols3, 1):
    build_room(f"Sala {i}", x0, RT0, x1, RT1, ((x0 + x1) // 2, RT1))
for i, (x0, x1) in enumerate(cols3, 4):
    build_room(f"Sala {i}", x0, RB0, x1, RB1, ((x0 + x1) // 2, RB0))

# ===== middle band (saguao + work) marble =====
fill("floor", 1, RT1 + 1, W - 2, RB0 - 1, FLOOR_MARBLE)

# ===== side meeting rooms =====
def build_meeting(name, x0, y0, x1, y1, door):
    rect_walls(x0, y0, x1, y1, doors=[door])
    fill("floor", x0 + 1, y0 + 1, x1 - 1, y1 - 1, FLOOR_SOFT)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    cells = []
    block(cells, TABLE3, cx - 1, cy - 1, 3)
    for (x, y, g) in cells:
        put("furn1", x, y, g)
    for dx in range(cx - 1, cx + 2):
        put("furn2", dx, cy - 2, CHAIR_OR)
        put("furn2", dx, cy + 2, CHAIR_OR)
    put("above", cx, y0, SCREEN_CHART)
    plant(x0 + 1, y1 - 2)
    area(name, x0 + 1, y0 + 1, x1 - 1, y1 - 1)

MY0, MY1 = 12, 23
build_meeting("Reuniao A", 1, MY0, 12, MY1, (12, (MY0 + MY1) // 2))
build_meeting("Reuniao B", 37, MY0, 48, MY1, (37, (MY0 + MY1) // 2))

# ===== saguao: reception + logo + plants =====
cxm = W // 2
# logo on the back wall of the saguao
for i, g in enumerate(range(LOGO_FIRST, LOGO_FIRST + 16)):
    put("above", cxm - 2 + i % 4, 12 + i // 4, g)
# reception counter
rc = []
block(rc, RECEP, cxm - 2, 16, 3)
for (x, y, g) in rc:
    put("furn1", x, y, g)
plant(cxm - 4, 16)
plant(cxm + 4, 16, snake=True)
area("Recepcao", cxm - 5, RT1 + 1, cxm + 5, 17)

# ===== trabalho (shared work + lounge) =====
workstation(16, 19)
workstation(22, 19)
workstation(28, 19)
# lounge
fill("floordecor", 32, 19, 34, 21, RUG[0])  # placeholder single rug tile
for i, g in enumerate(RUG):
    put("floordecor", 32 + i % 3, 19 + i // 3, g)
for (x, y, g) in [(32, 19, SOFA[0]), (33, 19, SOFA[1]), (32, 20, SOFA[2]), (33, 20, SOFA[3])]:
    put("furn1", x, y, g)
put("furn2", 32, 21, ARM_BL)
put("furn2", 34, 21, ARM_GY)
area("Trabalho", 14, 18, 30, 23)

# start point (saguao center)
put("start", cxm, RB0 - 3, FLOOR_MARBLE)

# ================= logo image (green A) =================
def build_logo(dst):
    src = r"E:\Downloads\WhatsApp Image 2026-10-27 at 21.55.28.jpeg"
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    # crop the "A" symbol (upper-center portion, square)
    cx0 = int(w * 0.22); cx1 = int(w * 0.78)
    cy0 = int(h * 0.14); cy1 = int(h * 0.70)
    a = im.crop((cx0, cy0, cx1, cy1))
    a = a.resize((128, 128), Image.LANCZOS)
    px = a.load()
    for yy in range(128):
        for xx in range(128):
            r, g, b, al = px[xx, yy]
            if max(r, g, b) < 55:  # key out black background
                px[xx, yy] = (r, g, b, 0)
    a.save(dst)

# ================= export .tmj =================
def tileset(firstgid, name, image, iw, ih, cols, collide_local=None):
    tc = (iw // TILE) * (ih // TILE)
    ts = {"firstgid": firstgid, "name": name, "image": image,
          "imagewidth": iw, "imageheight": ih, "tilewidth": TILE, "tileheight": TILE,
          "tilecount": tc, "columns": cols, "margin": 0, "spacing": 0}
    if collide_local:
        ts["tiles"] = [{"id": i, "properties": [{"name": "collides", "type": "bool", "value": True}]}
                       for i in sorted(collide_local)]
    return ts

def tilelayer(name, data, visible=True):
    return {"type": "tilelayer", "name": name, "x": 0, "y": 0,
            "width": W, "height": H, "opacity": 1, "visible": visible, "data": data}

rb_coll = {g - RB_FIRST for g in COLLIDE if g < MO_FIRST}
mo_coll = {g - MO_FIRST for g in COLLIDE if MO_FIRST <= g < LOGO_FIRST}

tmj = {
    "compressionlevel": -1, "infinite": False, "orientation": "orthogonal",
    "renderorder": "right-down", "tiledversion": "1.10.2", "type": "map", "version": "1.10",
    "width": W, "height": H, "tilewidth": TILE, "tileheight": TILE, "nextlayerid": 50, "nextobjectid": 50,
    "properties": [
        {"name": "mapName", "type": "string", "value": "Atlas Call - Escritorio"},
        {"name": "mapDescription", "type": "string", "value": "Escritorio virtual da Atlas Scale"},
    ],
    "tilesets": [
        tileset(RB_FIRST, "RoomBuilder", "RoomBuilder.png", 512, 448, 16, rb_coll),
        tileset(MO_FIRST, "ModernOffice", "ModernOffice.png", 512, 1696, 16, mo_coll),
        tileset(LOGO_FIRST, "logo", "atlas-a.png", 128, 128, 4),
    ],
    "layers": [
        tilelayer("start", L["start"], visible=False),
        tilelayer("floor", L["floor"]),
        tilelayer("floordecor", L["floordecor"]),
        tilelayer("walls", L["walls"]),
        tilelayer("furniture", L["furn1"]),
        tilelayer("furniture2", L["furn2"]),
        {"type": "objectgroup", "name": "floorLayer", "x": 0, "y": 0, "opacity": 1,
         "visible": True, "draworder": "topdown", "objects": areas},
        tilelayer("above", L["above"]),
    ],
}

# assign sequential layer ids (Tiled/WA expect them)
for i, layer in enumerate(tmj["layers"], 1):
    layer["id"] = i
tmj["nextlayerid"] = len(tmj["layers"]) + 1
tmj["nextobjectid"] = len(areas) + 1

os.makedirs("dist", exist_ok=True)
shutil.copy("tilesets/RoomBuilder.png", "dist/RoomBuilder.png")
shutil.copy("tilesets/ModernOffice.png", "dist/ModernOffice.png")
build_logo("dist/atlas-a.png")
json.dump(tmj, open("dist/office.tmj", "w", encoding="utf-8"), ensure_ascii=False)
print("wrote dist/office.tmj + tilesets + atlas-a.png")

# ================= preview render =================
imgs = {"rb": Image.open("tilesets/RoomBuilder.png").convert("RGBA"),
        "mo": Image.open("tilesets/ModernOffice.png").convert("RGBA"),
        "logo": Image.open("dist/atlas-a.png").convert("RGBA")}

def tile_img(g):
    if g < MO_FIRST:
        src, cols, first = imgs["rb"], RB_COLS, RB_FIRST
    elif g < LOGO_FIRST:
        src, cols, first = imgs["mo"], MO_COLS, MO_FIRST
    else:
        src, cols, first = imgs["logo"], LOGO_COLS, LOGO_FIRST
    idx = g - first
    c, r = idx % cols, idx // cols
    return src.crop((c * TILE, r * TILE, c * TILE + TILE, r * TILE + TILE))

canvas = Image.new("RGBA", (W * TILE, H * TILE), (24, 24, 30, 255))
for name in ["floor", "floordecor", "walls", "furn1", "furn2", "above"]:
    for y in range(H):
        for x in range(W):
            g = L[name][y * W + x]
            if g:
                canvas.alpha_composite(tile_img(g), (x * TILE, y * TILE))

d = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("arialbd.ttf", 18)
except Exception:
    font = ImageFont.load_default()
for a in areas:
    tx = a["x"] + a["width"] // 2
    ty = a["y"] + a["height"] // 2
    nm = a["name"]
    bb = d.textbbox((0, 0), nm, font=font)
    tw = bb[2] - bb[0]
    d.rectangle((tx - tw // 2 - 5, ty - 12, tx + tw // 2 + 5, ty + 12), fill=(0, 0, 0, 120))
    d.text((tx - tw // 2, ty - 10), nm, fill=(255, 240, 90, 255), font=font)

canvas.convert("RGB").save("tools/_final.png")
print("wrote tools/_final.png")
