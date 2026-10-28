"""Atlas Call - escritorio a partir da arte pronta (desenho do ChatGPT).
Usa a imagem 14.png (layout lindo: Salas 1-6, reunioes, saguao, area comum,
jardim) COMO o mapa: redimensiona pra grade 48x32, fatia num tileset compacto
(dedup) e gera um .tmj jogavel com colisao nas paredes (areas escuras) e portas
abertas. Chao/sofa/rug/jardim ficam andaveis.

Rodar:  py -3 -I map/tools/build_office_cg.py
Saida:  map/tools/dist/office.tmj + office2.png  (+ _cg_reconstruct.png pra conferir)
"""
import json, os
from PIL import Image, ImageDraw

SRC = r"C:\Users\dougl\AppData\Local\Temp\claude\e--saas-atlas-Atlas-Call\303694b7-ea0a-4d91-b0ce-bc4d126ed44b\images\14.png"
TILE = 32
W, H = 48, 32  # 1536 x 1024

im = Image.open(SRC).convert("RGBA").resize((W * TILE, H * TILE), Image.LANCZOS)
px = im.load()

def mean_brightness(tx, ty):
    s = 0.0
    n = 0
    for yy in range(ty * TILE, ty * TILE + TILE, 2):
        for xx in range(tx * TILE, tx * TILE + TILE, 2):
            r, g, b, _ = px[xx, yy]
            s += 0.299 * r + 0.587 * g + 0.114 * b
            n += 1
    return s / n

# colisao: paredes / fundo escuro bloqueiam; resto anda
BLOCK_THRESH = 60
block = [[mean_brightness(tx, ty) < BLOCK_THRESH for tx in range(W)] for ty in range(H)]

# ponto de entrada: centro do saguao/area comum (chao de madeira)
sx, sy = 24, 15
if block[sy][sx]:
    # procura a celula andavel mais proxima do centro
    for rad in range(1, 20):
        done = False
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                nx, ny = sx + dx, sy + dy
                if 0 <= nx < W and 0 <= ny < H and not block[ny][nx]:
                    sx, sy = nx, ny; done = True; break
            if done: break
        if done: break

# ---------- tileset compacto com dedup ----------
TS_COLS = 16
tiles = {}
order = []
cell_tile = [0] * (W * H)
collide_ids = set()
for ty in range(H):
    for tx in range(W):
        cell = im.crop((tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE))
        b = bool(block[ty][tx])
        key = (b, cell.tobytes())
        tid = tiles.get(key)
        if tid is None:
            tid = len(order); tiles[key] = tid; order.append(cell)
            if b: collide_ids.add(tid)
        cell_tile[ty * W + tx] = tid

NT = len(order)
TS_ROWS = (NT + TS_COLS - 1) // TS_COLS
ts_img = Image.new("RGBA", (TS_COLS * TILE, TS_ROWS * TILE), (0, 0, 0, 0))
for i, t in enumerate(order):
    ts_img.alpha_composite(t, ((i % TS_COLS) * TILE, (i // TS_COLS) * TILE))

DIST = os.path.join(os.path.dirname(__file__), "dist")
os.makedirs(DIST, exist_ok=True)
ts_img.convert("RGB").save(os.path.join(DIST, "office2.png"))

floor_data = [cell_tile[i] + 1 for i in range(W * H)]
start = [0] * (W * H); start[sy * W + sx] = floor_data[sy * W + sx]

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
        {"name": "script", "type": "string", "value": "nudge.js"},
        {"name": "scriptDisableModuleSupport", "type": "bool", "value": True},
    ],
    "tilesets": [{
        "firstgid": 1, "name": "office", "image": "office2.png",
        "imagewidth": TS_COLS * TILE, "imageheight": TS_ROWS * TILE, "tilewidth": TILE, "tileheight": TILE,
        "tilecount": NT, "columns": TS_COLS, "margin": 0, "spacing": 0,
        "tiles": [{"id": i, "properties": [{"name": "collides", "type": "bool", "value": True}]}
                  for i in sorted(collide_ids)],
    }],
    "layers": [
        tilelayer("start", start, visible=False),
        tilelayer("floor", floor_data),
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
json.dump(tmj, open(os.path.join(DIST, "office.tmj"), "w", encoding="utf-8"), ensure_ascii=False)

walk = sum(1 for row in block for b in row if not b)
print(f"mapa {W}x{H}  tiles unicos {NT}  colisao(tiles) {len(collide_ids)}  andavel(celulas) {walk}")
print(f"start em ({sx},{sy})")

# reconstrucao pra conferir
cols = TS_COLS
out = Image.new("RGBA", (W * TILE, H * TILE), (10, 12, 20, 255))
for i, g in enumerate(floor_data):
    tid = g - 1; sxp = (tid % cols) * TILE; syp = (tid // cols) * TILE
    out.alpha_composite(ts_img.crop((sxp, syp, sxp + TILE, syp + TILE)), ((i % W) * TILE, (i // W) * TILE))
d = ImageDraw.Draw(out, "RGBA")
d.rectangle((sx * TILE, sy * TILE, sx * TILE + TILE - 1, sy * TILE + TILE - 1), outline=(0, 255, 0, 255), width=3)
out.convert("RGB").save(os.path.join(os.path.dirname(__file__), "_cg_reconstruct.png"))
print("reconstruido -> map/tools/_cg_reconstruct.png")
