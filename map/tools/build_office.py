"""Atlas Call - escritorio completo (estrutura do Douglas).
Monta um escritorio com SALAS de verdade (paredes + portas + corredores) no
estilo LimeZu: saguao/recepcao, area de trabalho conjunta, salas 1-6 e duas
salas de reuniao nas laterais. Compoe uma imagem grande (chao LimeZu + paredes
+ moveis LimeZu) e fatia 1:1 num tileset, gerando um .tmj valido com colisao,
areas nomeadas por sala e ponto de entrada no saguao.

Rodar:  py -3 -I map/tools/build_office.py
Saida:  map/tools/dist/office.tmj  +  map/tools/dist/office2.png
        map/tools/_office_preview.png (visualizacao com grade)
"""
import json, os
from PIL import Image, ImageDraw

TILE = 32
PACK = "E:/Downloads/modern_office_extracted/"
RB = Image.open(PACK + "1_Room_Builder_Office/Room_Builder_Office_32x32.png").convert("RGBA")
SINGLES = PACK + "4_Modern_Office_singles/32x32/"

W, H = 46, 32  # tiles

def floor_tile(tx, ty):
    # achata sobre um cinza claro opaco (alguns tiles do pack tem alpha)
    base = Image.new("RGBA", (TILE, TILE), (206, 208, 214, 255))
    base.alpha_composite(RB.crop((tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE)))
    return base

# ---- paletas de chao (coords no Room Builder) ----
FLOORS = {
    "corr":   floor_tile(10, 8),   # corredor  - cinza
    "commons":floor_tile(11, 8),   # saguao/coworking - cinza claro
    "meet":   floor_tile(1, 10),   # reuniao - madeira
    "tan":    floor_tile(13, 7),   # carpete
    "blu":    floor_tile(10, 10),  # ladrilho
    "wood":   floor_tile(1, 10),   # madeira
}

def sprite(n):
    return Image.open(SINGLES + f"Modern_Office_Singles_32x32_{n}.png").convert("RGBA")

# ---------- grelha logica ----------
WALL, DOOR = "#WALL", "#DOOR"
grid = [["corr"] * W for _ in range(H)]          # chao por celula (id de FLOORS) ou WALL
block = [[False] * W for _ in range(H)]          # colisao

def set_floor(x, y, fid):
    if 0 <= x < W and 0 <= y < H:
        grid[y][x] = fid

# outer ring = parede
for x in range(W):
    grid[0][x] = WALL; grid[H - 1][x] = WALL
for y in range(H):
    grid[y][0] = WALL; grid[y][W - 1] = WALL

rooms = []  # cada sala: dict com floor rect + moveis + nome + area

def add_room(name, x, y, w, h, fid, doors, area_props=None, walls=True):
    """x,y,w,h = retangulo do CHAO. Paredes no anel ao redor; portas abrem o anel."""
    for ry in range(y, y + h):
        for rx in range(x, x + w):
            set_floor(rx, ry, fid)
    if walls:
        for rx in range(x - 1, x + w + 1):
            set_floor(rx, y - 1, WALL); set_floor(rx, y + h, WALL)
        for ry in range(y - 1, y + h + 1):
            set_floor(x - 1, ry, WALL); set_floor(x + w, ry, WALL)
        for (dx, dy) in doors:
            set_floor(dx, dy, "corr")  # porta = passagem
    rooms.append({"name": name, "x": x, "y": y, "w": w, "h": h, "props": area_props or []})

# ---- SALAS DE CIMA (1,2,3) ----
add_room("Sala 1", 2, 1, 11, 7, "tan",  [(7, 8), (8, 8)])
add_room("Sala 2", 17, 1, 12, 7, "blu", [(22, 8), (23, 8)])
add_room("Sala 3", 33, 1, 11, 7, "wood",[(38, 8), (39, 8)])

# ---- SALAS DE REUNIAO (laterais) ----
add_room("Reuniao Esquerda", 2, 11, 11, 9, "meet", [(13, 15), (13, 16)])
add_room("Reuniao Direita", 33, 11, 11, 9, "meet", [(32, 15), (32, 16)])

# ---- SALAS DE BAIXO (4,5,6) ----
add_room("Sala 4", 2, 24, 11, 6, "tan",  [(7, 23), (8, 23)])
add_room("Sala 5", 17, 24, 12, 6, "blu", [(22, 23), (23, 23)])
add_room("Sala 6", 33, 24, 11, 6, "wood",[(38, 23), (39, 23)])

# ---- SAGUAO + AREA DE TRABALHO CONJUNTA (centro aberto) ----
add_room("Saguao e Area Comum", 14, 9, 17, 13, "commons", [], walls=False)

# ---------- render da imagem ----------
canvas = Image.new("RGBA", (W * TILE, H * TILE), (28, 32, 44, 255))

def draw_wall(x, y):
    """parede com topo iluminado (da sensacao de altura)."""
    x0, y0 = x * TILE, y * TILE
    d = ImageDraw.Draw(canvas)
    d.rectangle((x0, y0, x0 + TILE - 1, y0 + TILE - 1), fill=(46, 53, 80))       # corpo
    d.rectangle((x0, y0, x0 + TILE - 1, y0 + 11), fill=(86, 97, 140))            # topo iluminado
    d.line((x0, y0 + 12, x0 + TILE - 1, y0 + 12), fill=(30, 35, 54))             # sombra sob o topo
    d.line((x0, y0 + TILE - 2, x0 + TILE - 1, y0 + TILE - 2), fill=(22, 26, 40)) # rodape

for y in range(H):
    for x in range(W):
        g = grid[y][x]
        if g == WALL:
            draw_wall(x, y); block[y][x] = True
        else:
            canvas.alpha_composite(FLOORS[g], (x * TILE, y * TILE))

# ---------- moveis ----------
def place(n, tx, ty, foot=None):
    """cola o sprite (64x96) com o canto sup-esq na celula (tx,ty).
    foot = lista de celulas (dx,dy) relativas a bloquear; default base 2x1."""
    sp = sprite(n)
    canvas.alpha_composite(sp, (tx * TILE, ty * TILE))
    if foot is None:
        foot = [(0, 2), (1, 2)]  # base do movel
    for (dx, dy) in foot:
        bx, by = tx + dx, ty + dy
        if 0 <= bx < W and 0 <= by < H:
            block[by][bx] = True

# salas de cima: 2 estacoes de trabalho + planta
for (bx, nm) in [(2, 320), (17, 321), (33, 320)]:
    place(nm, bx + 1, 2); place(nm + 1 if nm == 320 else nm - 1, bx + 6, 2)
place(98, 11, 5); place(99, 27, 5); place(100, 42, 5)

# reunioes: mesa grande (2 modulos) + cadeiras + planta
for (bx, rx) in [(2, None), (33, None)]:
    place(263, bx + 2, 13, foot=[(0, 1), (1, 1)]); place(263, bx + 5, 13, foot=[(0, 1), (1, 1)])
    place(101, bx + 2, 11); place(101, bx + 5, 11)
    place(107, bx + 2, 16); place(107, bx + 5, 16)
place(98, 11, 17); place(100, 42, 17)

# salas de baixo: estacoes + planta
for (bx, nm) in [(2, 321), (17, 320), (33, 321)]:
    place(nm, bx + 1, 25); place(nm, bx + 6, 25)
place(99, 11, 27); place(98, 27, 27); place(100, 42, 27)

# saguao/coworking: recepcao + fileiras de estacoes + sofas + plantas + tapete
place(208, 15, 9, foot=[(0, 1), (1, 1)]); place(209, 17, 9, foot=[(0, 1)])  # balcao recepcao
place(107, 15, 12); place(110, 28, 12)                                       # poltronas
for i, cx in enumerate([16, 20, 24]):                                        # coworking
    place(320, cx, 15); place(321, cx, 18)
place(98, 14, 20); place(100, 30, 20); place(99, 30, 9)

os.makedirs(os.path.join(os.path.dirname(__file__), "dist"), exist_ok=True)
DIST = os.path.join(os.path.dirname(__file__), "dist")
canvas.convert("RGB").save(os.path.join(DIST, "office2.png"))

# ---------- .tmj (fatiar 1:1) ----------
floor_data = [0] * (W * H)
collide_ids = []
for ty in range(H):
    for tx in range(W):
        idx = ty * W + tx
        floor_data[idx] = idx + 1  # firstgid 1, tudo desenhado
        if block[ty][tx]:
            collide_ids.append(idx)

# start no saguao
sx, sy = 22, 15
start = [0] * (W * H); start[sy * W + sx] = floor_data[sy * W + sx]

def tilelayer(name, data, visible=True):
    return {"type": "tilelayer", "name": name, "x": 0, "y": 0, "width": W, "height": H,
            "opacity": 1, "visible": visible, "data": data}

area_objs = []
oid = 1
for r in rooms:
    area_objs.append({"id": oid, "name": r["name"], "type": "area",
                      "x": r["x"] * TILE, "y": r["y"] * TILE,
                      "width": r["w"] * TILE, "height": r["h"] * TILE,
                      "visible": True, "rotation": 0, "properties": r["props"]})
    oid += 1

tmj = {
    "compressionlevel": -1, "infinite": False, "orientation": "orthogonal",
    "renderorder": "right-down", "tiledversion": "1.10.2", "type": "map", "version": "1.10",
    "width": W, "height": H, "tilewidth": TILE, "tileheight": TILE,
    "properties": [
        {"name": "mapName", "type": "string", "value": "Atlas Call - Escritorio"},
        {"name": "mapDescription", "type": "string", "value": "Escritorio Atlas Scale"},
    ],
    "tilesets": [{
        "firstgid": 1, "name": "office", "image": "office2.png",
        "imagewidth": W * TILE, "imageheight": H * TILE, "tilewidth": TILE, "tileheight": TILE,
        "tilecount": W * H, "columns": W, "margin": 0, "spacing": 0,
        "tiles": [{"id": i, "properties": [{"name": "collides", "type": "bool", "value": True}]}
                  for i in sorted(collide_ids)],
    }],
    "layers": [
        tilelayer("start", start, visible=False),
        tilelayer("floor", floor_data),
        {"type": "objectgroup", "name": "floorLayer", "x": 0, "y": 0, "opacity": 1,
         "visible": True, "draworder": "topdown", "objects": area_objs},
    ],
}
for i, L in enumerate(tmj["layers"], 1):
    L["id"] = i
tmj["nextlayerid"] = len(tmj["layers"]) + 1
tmj["nextobjectid"] = oid
json.dump(tmj, open(os.path.join(DIST, "office.tmj"), "w", encoding="utf-8"), ensure_ascii=False)

walk = sum(1 for row in block for b in row if not b)
print(f"mapa {W}x{H}  andavel ~{walk}  colisao {len(collide_ids)}  salas {len(rooms)}")

# ---------- preview com grade + nomes ----------
pv = canvas.convert("RGBA").copy(); d = ImageDraw.Draw(pv, "RGBA")
for r in rooms:
    d.rectangle((r["x"] * TILE, r["y"] * TILE, (r["x"] + r["w"]) * TILE - 1, (r["y"] + r["h"]) * TILE - 1),
                outline=(0, 255, 255, 120))
    d.text((r["x"] * TILE + 3, r["y"] * TILE + 3), r["name"], fill=(255, 255, 0, 255))
d.rectangle((sx * TILE, sy * TILE, sx * TILE + TILE - 1, sy * TILE + TILE - 1), outline=(0, 255, 0, 255), width=2)
pv.convert("RGB").save(os.path.join(os.path.dirname(__file__), "_office_preview.png"))
print("preview: map/tools/_office_preview.png")
