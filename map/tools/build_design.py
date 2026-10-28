"""Atlas Call map from the LimeZu pro 'Office Design 2'.
Uses the ready-made professional composition AS the map: slices it 1:1 into a
tileset, classifies each cell (floor=walkable, furniture/wall/void=blocked),
and writes a valid WorkAdventure .tmj. Also renders a collision overlay to check.
"""
import json, os, statistics
from PIL import Image, ImageDraw, ImageSequence

TILE = 32
SRC = r"E:\Downloads\modern_office_extracted\6_Office_Designs\Office_Design_2.gif"

im = Image.open(SRC)
im.seek(0)
im = im.convert("RGBA")
W, H = im.width // TILE, im.height // TILE
print(f"design {im.width}x{im.height} = {W}x{H} tiles")

# --- logo "A" da Atlas na TV de parede (topo, cols 3-4) ---
try:
    lg = Image.open(r"E:\Downloads\WhatsApp Image 2026-10-27 at 21.55.28.jpeg").convert("RGBA")
    lw, lh = lg.size
    a = lg.crop((int(lw * 0.24), int(lh * 0.15), int(lw * 0.76), int(lh * 0.66)))
    a = a.resize((46, 46), Image.LANCZOS)
    ap = a.load()
    for yy in range(46):
        for xx in range(46):
            r, g, b, al = ap[xx, yy]
            if max(r, g, b) < 60:
                ap[xx, yy] = (r, g, b, 0)
    im.alpha_composite(a, (170, 10))   # centraliza na TV em branco da parede
    print("logo colada na TV de parede")
except Exception as e:
    print("logo skip:", e)

# classify each cell
FLOOR, FURN, VOID = 0, 1, 2
cls = [[FLOOR] * W for _ in range(H)]
px = im.load()
for ty in range(H):
    for tx in range(W):
        grays = []
        for yy in range(ty * TILE, ty * TILE + TILE):
            for xx in range(tx * TILE, tx * TILE + TILE):
                r, g, b, a = px[xx, yy]
                if a > 128:
                    grays.append(0.299 * r + 0.587 * g + 0.114 * b)
        total = TILE * TILE
        if len(grays) < total * 0.35:
            cls[ty][tx] = VOID
            continue
        mean = sum(grays) / len(grays)
        # chao e claro -> andavel. Movel/parede escuros (cadeiras, telas, sombras) -> bloqueia.
        if mean > 140:
            cls[ty][tx] = FLOOR
        else:
            cls[ty][tx] = FURN

# manual fixes (cell coords to force) can go here after inspecting overlay
FORCE_WALK = set()   # (tx,ty) force walkable
FORCE_BLOCK = set()  # (tx,ty) force blocked
for (tx, ty) in FORCE_WALK:
    cls[ty][tx] = FLOOR
for (tx, ty) in FORCE_BLOCK:
    if cls[ty][tx] == FLOOR:
        cls[ty][tx] = FURN

blocked = lambda tx, ty: cls[ty][tx] != FLOOR
void = lambda tx, ty: cls[ty][tx] == VOID

# ---- save tileset image (the design itself) ----
os.makedirs("dist", exist_ok=True)
im.save("dist/office2.png")

# ---- build .tmj ----
# floor layer: place a unique tile for every non-void cell (renders the image 1:1)
# collision: mark blocked cells' tile ids as collides in the tileset
floor = [0] * (W * H)
collide_ids = []
for ty in range(H):
    for tx in range(W):
        idx = ty * W + tx          # 0-based tile index in the sliced tileset
        gid = idx + 1              # firstgid = 1
        if not void(tx, ty):
            floor[ty * W + tx] = gid
        if blocked(tx, ty) and not void(tx, ty):
            collide_ids.append(idx)   # furniture/walls are drawn AND block

# start: first walkable cell near the center-bottom (open area)
start_cell = None
for ty in range(H - 1, -1, -1):
    for tx in range(W):
        if cls[ty][tx] == FLOOR:
            start_cell = (tx, ty); break
    if start_cell: break
sx, sy = start_cell
start = [0] * (W * H)
start[sy * W + sx] = floor[sy * W + sx] or 1

def tilelayer(name, data, visible=True):
    return {"type": "tilelayer", "name": name, "x": 0, "y": 0, "width": W, "height": H,
            "opacity": 1, "visible": visible, "data": data}

tmj = {
    "compressionlevel": -1, "infinite": False, "orientation": "orthogonal",
    "renderorder": "right-down", "tiledversion": "1.10.2", "type": "map", "version": "1.10",
    "width": W, "height": H, "tilewidth": TILE, "tileheight": TILE,
    "properties": [
        {"name": "mapName", "type": "string", "value": "Atlas Call - Escritorio"},
        {"name": "mapDescription", "type": "string", "value": "Escritorio Atlas Scale"},
    ],
    "tilesets": [{
        "firstgid": 1, "name": "design", "image": "office2.png",
        "imagewidth": im.width, "imageheight": im.height, "tilewidth": TILE, "tileheight": TILE,
        "tilecount": W * H, "columns": W, "margin": 0, "spacing": 0,
        "tiles": [{"id": i, "properties": [{"name": "collides", "type": "bool", "value": True}]}
                  for i in sorted(collide_ids)],
    }],
    "layers": [
        tilelayer("start", start, visible=False),
        tilelayer("floor", floor),
        {"type": "objectgroup", "name": "floorLayer", "x": 0, "y": 0, "opacity": 1,
         "visible": True, "draworder": "topdown", "objects": [
            {"id": 1, "name": "Escritorio", "type": "area", "x": 0, "y": 0,
             "width": W * TILE, "height": H * TILE, "visible": True, "rotation": 0, "properties": []},
         ]},
    ],
}
for i, L in enumerate(tmj["layers"], 1):
    L["id"] = i
tmj["nextlayerid"] = len(tmj["layers"]) + 1
tmj["nextobjectid"] = 2
json.dump(tmj, open("dist/office.tmj", "w", encoding="utf-8"), ensure_ascii=False)

walk = sum(1 for row in cls for c in row if c == FLOOR)
print(f"tiles: {W*H}  walkable: {walk}  blocked: {len(collide_ids)}  void: {sum(1 for row in cls for c in row if c==VOID)}")
print(f"start at tile ({sx},{sy})")

# ---- collision overlay (for checking) ----
ov = im.convert("RGBA").copy()
d = ImageDraw.Draw(ov, "RGBA")
for ty in range(H):
    for tx in range(W):
        x0, y0 = tx * TILE, ty * TILE
        if cls[ty][tx] == FURN:
            d.rectangle((x0, y0, x0 + TILE - 1, y0 + TILE - 1), fill=(255, 0, 0, 70))
        elif cls[ty][tx] == VOID:
            d.rectangle((x0, y0, x0 + TILE - 1, y0 + TILE - 1), fill=(0, 0, 0, 90))
d.rectangle((sx * TILE, sy * TILE, sx * TILE + TILE - 1, sy * TILE + TILE - 1), outline=(0, 255, 255, 255), width=3)
ov.convert("RGB").save("tools/_design_overlay.png")
print("saved tools/_design_overlay.png (vermelho=bloqueado, preto=vazio, ciano=spawn)")
