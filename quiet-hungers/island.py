import json
import math
import os
import random
import pygame
import sys

import settings
import ui
# Quiet Hunger — процедурный мир тропического острова
# Управление: WASD / стрелки, Shift — бег, E — действие, F — съесть предмет из выбранного слота,
# 1-8 — выбор слота, TAB / I — инвентарь, F11 — полный экран, ESC — меню паузы.

SCREEN_W, SCREEN_H = 1600, 900
WORLD_W, WORLD_H = 5200, 3800   # остров стал заметно больше
FPS = 60

SEA = (35, 145, 170)
SAND = (222, 190, 123)
SAND_LIGHT = (237, 210, 151)
GRASS = (58, 112, 57)
JUNGLE = (32, 83, 48)
DARK_JUNGLE = (24, 66, 43)
MEADOW = (104, 158, 70)          # светлая трава на поляне
MEADOW_DARK = (88, 140, 62)      # чуть темнее в глубине поляны

# Остров делится по вертикали: слева — небольшая поляна, справа — тропики.
# Положение границы относительно центра острова (минус = граница левее, поляна меньше).
MEADOW_SPLIT = -300

# ---------- спрайты (Farm RPG 16x16 Tiny Asset Pack) ----------
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "savegame.json")
INV_SLOTS = 32    # 8 быстрых слотов + рюкзак 8x3
HOTBAR = 8
PALM_SCALE = 1  # масштаб пальм (целое число; 1 = как в Trees_.png)
PS = 3  # во сколько раз увеличиваем пиксель-арт (целое число, чтобы пиксели оставались чёткими)

# Сколько сытости даёт еда (F по выбранному слоту)
FOOD = {"Кокос": 18, "Яйцо": 15, "Молоко": 30}

# Прямоугольники деревьев на листе Maple_Tree.png (x, y, w, h в исходных пикселях)
TREE_RECTS = {
    "big": (96, 0, 32, 47),
    "young": (70, 13, 22, 34),
    "sap": (42, 33, 11, 13),
    "stump": (136, 34, 16, 13),
}
# Деревья джунглей (тропики): ключ -> файл в папке assets
JUNGLE_TREES = {"jleaf": "Jungle_Leaf1.png", "jbamboo": "Jungle_Bamboo.png",
                "jvine1": "Jungle_Vine1.png", "jvine2": "Jungle_Vine2.png"}
JUNGLE_SCALE = 2     # во сколько раз увеличить деревья джунглей (целое число)
TREE_RADIUS = {"big": 15, "young": 12, "sap": 0, "stump": 9, "oak": 18,
               "jleaf": 14, "jbamboo": 12, "jvine1": 14, "jvine2": 14}   # радиус «ствола» для столкновений

# Новые спрайты (папка assets): дуб, кусты, сундук для окна, самолёт и его салон
BUSH_SCALE = 1       # во сколько раз увеличить кусты (целое число)
PLANE_SCALE = 0.62   # размер самолёта на карте
CHEST_SLOTS = 16     # ячеек в сундуке
BOX_BASE = 100       # номера ячеек сундука в окне (чтобы не путать с ячейками рюкзака)


def _load(name, optional=False):
    path = os.path.join(ASSET_DIR, name)
    if optional and not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, (img.get_width() * PS, img.get_height() * PS))


def _cut(sheet, x, y, w, h):
    """Вырезает кусок из уже увеличенного листа; x, y, w, h — в исходных пикселях."""
    return sheet.subsurface((x * PS, y * PS, w * PS, h * PS)).copy()


def _load_plain(name, alpha=True):
    """Грузит картинку как есть (без увеличения); если файла нет — возвращает None."""
    path = os.path.join(ASSET_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        img = pygame.image.load(path)
        return img.convert_alpha() if alpha else img.convert()
    except pygame.error:
        return None


def add_to_list(lst, name, count=1):
    """Кладёт предмет в список ячеек: сначала к такой же стопке, потом в первую пустую."""
    for it in lst:
        if it and it["name"] == name:
            it["count"] += count
            return True
    for i, it in enumerate(lst):
        if it is None:
            lst[i] = {"name": name, "count": count}
            return True
    return False


def _clean_slots(raw, n):
    """Проверяет список ячеек из сохранения."""
    raw = list(raw or [])[:n]
    raw += [None] * (n - len(raw))
    return [{"name": str(it["name"]), "count": int(it["count"])}
            if isinstance(it, dict) and int(it.get("count", 0)) > 0 else None for it in raw]


def _flip(surf):
    return pygame.transform.flip(surf, True, False)


class Sprites:
    def __init__(self):
        # Герой: ряды — вниз, вверх, вбок (смотрит влево); 4 кадра по 32x32
        idle = _load("Idle.png")
        self.idle = {
            "down": [_cut(idle, i * 32, 0, 32, 32) for i in range(4)],
            "up": [_cut(idle, i * 32, 32, 32, 32) for i in range(4)],
            "left": [_cut(idle, i * 32, 64, 32, 32) for i in range(4)],
        }
        self.idle["right"] = [_flip(s) for s in self.idle["left"]]

        # Необязательная анимация ходьбы: положи Walk.png в папку assets
        self.walk = None
        walk = _load("Walk.png", optional=True)
        if walk is not None and walk.get_height() == 96 * PS and walk.get_width() % (32 * PS) == 0:
            n = walk.get_width() // (32 * PS)
            self.walk = {
                "down": [_cut(walk, i * 32, 0, 32, 32) for i in range(n)],
                "up": [_cut(walk, i * 32, 32, 32, 32) for i in range(n)],
                "left": [_cut(walk, i * 32, 64, 32, 32) for i in range(n)],
            }
            self.walk["right"] = [_flip(s) for s in self.walk["left"]]

        # Коровы (смотрят влево), 4 кадра по 32x32
        self.cow = {}
        for key, fname in (("f", "Female_Cow_Brown.png"), ("m", "Male_Cow_Brown.png")):
            sheet = _load(fname)
            left = [_cut(sheet, i * 32, 0, 32, 32) for i in range(4)]
            self.cow[key] = {"left": left, "right": [_flip(s) for s in left]}

        # Куры: ряд 0 смотрит влево, ряд 1 — вправо, кадры 16x16
        self.hen = {}
        for key, fname in (("red", "Chicken_Red.png"), ("blonde", "Chicken_Blonde_Green.png")):
            sheet = _load(fname)
            self.hen[key] = {
                "left": [_cut(sheet, i * 16, 0, 16, 16) for i in range(4)],
                "right": [_cut(sheet, i * 16, 16, 16, 16) for i in range(4)],
            }

        # Цыплёнок смотрит вправо
        sheet = _load("Baby_Chicken_Yellow.png")
        right = [_cut(sheet, i * 16, 0, 16, 16) for i in range(4)]
        self.chick = {"right": right, "left": [_flip(s) for s in right]}

        # Деревья и камни
        maple = _load("Maple_Tree.png")
        self.tree = {k: _cut(maple, *r) for k, r in TREE_RECTS.items()}
        rocks = _load("Rocks.png")
        self.rocks = [_cut(rocks, i * 16, 0, 16, 16) for i in range(3)]

        # --- новые необязательные спрайты: если файла нет, соответствующая возможность просто не включается ---
        oak = _load_plain("oak.png")
        if oak is not None:
            self.tree["oak"] = oak
        for key, fname in JUNGLE_TREES.items():
            path = os.path.join(ASSET_DIR, fname)
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                self.tree[key] = pygame.transform.scale(
                    img, (img.get_width() * JUNGLE_SCALE, img.get_height() * JUNGLE_SCALE))
        self.bush = {"tropic": [], "meadow": []}
        atlas, rects_path = _load_plain("bushes.png"), os.path.join(ASSET_DIR, "bushes.json")
        if atlas is not None and os.path.exists(rects_path):
            try:
                with open(rects_path, "r", encoding="utf-8") as f:
                    for r in json.load(f):
                        img = atlas.subsurface((r["x"], r["y"], r["w"], r["h"])).copy()
                        if BUSH_SCALE != 1:
                            img = pygame.transform.scale(img, (img.get_width() * BUSH_SCALE, img.get_height() * BUSH_SCALE))
                        self.bush[r["kind"]].append(img)
            except (OSError, ValueError, KeyError, pygame.error):
                self.bush = {"tropic": [], "meadow": []}
        self.chest_ui = _load_plain("chest_ui.png")
        plane = _load_plain("plane.png")
        self.plane = None
        if plane is not None:
            self.plane = pygame.transform.smoothscale(
                plane, (int(plane.get_width() * PLANE_SCALE), int(plane.get_height() * PLANE_SCALE)))
        self.interior = _load_plain("plane_interior.png", alpha=False)
        self.interior_mask = _load_plain("plane_interior_mask.png", alpha=False)

        chest = _load("chest.png")
        self.chest_closed = _cut(chest, 0, 0, 32, 16)
        self.chest_open = _cut(chest, 0, 16, 32, 16)

        # Пальмы (из Trees_.png): зелёная, тёмная, жёлтая
        self.palm = {}
        for key, fname in (("green", "Palm_Green.png"), ("dark", "Palm_Dark.png"), ("yellow", "Palm_Yellow.png")):
            img = pygame.image.load(os.path.join(ASSET_DIR, fname)).convert_alpha()
            if PALM_SCALE != 1:
                img = pygame.transform.scale(img, (img.get_width() * PALM_SCALE, img.get_height() * PALM_SCALE))
            self.palm[key] = img

        # Акула (из tenor.gif): 10 кадров, в каждом плавник смотрит в свою сторону
        shark = [_load("Shark_%d.png" % i) for i in range(10)]
        self.shark = {
            "left": [shark[i] for i in (0, 1, 2)],
            "down": [shark[i] for i in (3, 4)],
            "right": [shark[i] for i in (5, 6, 7)],
            "up": [shark[i] for i in (8, 9)],
        }


def make_island_points(cx, cy, rx, ry, count=180, seed=12):
    rng = random.Random(seed)
    points = []
    for i in range(count):
        angle = 2 * math.pi * i / count
        noise = 1 + 0.075 * math.sin(angle * 5 + 0.7) + 0.045 * math.sin(angle * 11 + 1.8)
        noise += rng.uniform(-0.025, 0.025)
        points.append((int(cx + math.cos(angle) * rx * noise),
                       int(cy + math.sin(angle) * ry * noise)))
    return points


def shrink_polygon(points, factor):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return [(int(cx + (x - cx) * factor), int(cy + (y - cy) * factor))
            for x, y in points]


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


class Palm:
    """Пальма из пака деревьев; ствол твёрдый, за ней можно спрятаться."""
    RADIUS = 11

    def __init__(self, x, y, variant):
        self.x, self.y, self.variant = x, y, variant

    def draw(self, surface, cam, sprites):
        img = sprites.palm[self.variant]
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() - cam[1])))


class Shark:
    """Акула: плавает в море вокруг острова, к берегу не подплывает."""
    SPEED = 70
    FPS = 6.7   # как в исходной гифке (150 мс на кадр)

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.angle = random.uniform(0, math.tau)
        self.timer = random.uniform(2, 5)
        self.frame = random.uniform(0, 3)

    def update(self, dt, world):
        self.timer -= dt
        if self.timer <= 0:
            self.angle += random.uniform(-1.0, 1.0)
            self.timer = random.uniform(3, 6)
        nx = self.x + math.cos(self.angle) * self.SPEED * dt
        ny = self.y + math.sin(self.angle) * self.SPEED * dt
        if world.in_sea(nx, ny):
            self.x, self.y = nx, ny
        else:
            self.angle += random.uniform(1.6, 3.0)   # упёрлись в берег или край карты — разворачиваемся
            self.timer = random.uniform(2, 4)
        self.frame += dt * self.FPS

    def direction(self):
        c, s = math.cos(self.angle), math.sin(self.angle)
        if abs(c) >= abs(s):
            return "right" if c > 0 else "left"
        return "down" if s > 0 else "up"

    def draw(self, surface, cam, sprites):
        frames = sprites.shark[self.direction()]
        img = frames[int(self.frame) % len(frames)]
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() - cam[1])))


class Tree:
    """Клён из пака; можно рубить (E)."""
    def __init__(self, x, y, kind):
        self.x, self.y, self.kind = x, y, kind

    @property
    def radius(self):
        return TREE_RADIUS[self.kind]

    def draw(self, surface, cam, sprites):
        img = sprites.tree[self.kind]
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() - cam[1])))


class Chest:
    def __init__(self, x, y):
        self.x, self.y, self.open = x, y, False
        # внутри сундука с самого начала лежат припасы
        self.items = [{"name": "Дерево", "count": 4}, {"name": "Камень", "count": 3},
                      {"name": "Кокос", "count": 3}] + [None] * (CHEST_SLOTS - 3)

    def draw(self, surface, cam, sprites):
        img = sprites.chest_open if self.open else sprites.chest_closed
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() - cam[1])))


class Plane:
    """Разбитый самолёт на карте. Корпус твёрдый, войти можно через пролом (E)."""
    def __init__(self, x, y, img):
        self.x, self.y, self.img = x, y, img     # (x, y) — середина нижнего края спрайта
        self.w, self.h = img.get_size()
        self.block = pygame.Rect(x - self.w // 2 + 50, y - 50, self.w - 100, 50)       # то, через что не пройти
        self.door = (x + int(self.w * 0.09), y + 8)                                   # место входа (под проломом)
        self.zone = pygame.Rect(x - self.w // 2 - 140, y - self.h - 140, self.w + 280, self.h + 300)  # тут ничего не растёт

    def draw(self, surface, cam):
        surface.blit(self.img, (int(self.x - self.w / 2 - cam[0]), int(self.y - self.h - cam[1])))


class PlaneInterior:
    """Салон самолёта (вид сверху): герой ходит по проходу и между креслами.
    Проходимые места берутся из plane_interior_mask.png (белое — можно ходить, зелёное — выход)."""
    SPAWN = (1090, 319)       # где появляется герой (координаты исходной картинки интерьера)

    def __init__(self, sprites):
        img = sprites.interior
        self.mask = sprites.interior_mask
        iw, ih = img.get_size()
        self.scale = min((SCREEN_W - 60) / iw, (SCREEN_H - 100) / ih)
        self.img = pygame.transform.smoothscale(img, (int(iw * self.scale), int(ih * self.scale)))
        self.ox = (SCREEN_W - self.img.get_width()) // 2
        self.oy = (SCREEN_H - self.img.get_height()) // 2
        self.px = self.py = 0.0

    def to_screen(self, sx, sy):
        return self.ox + sx * self.scale, self.oy + sy * self.scale

    def mask_at(self, x, y):
        mx, my = int((x - self.ox) / self.scale), int((y - self.oy) / self.scale)
        if 0 <= mx < self.mask.get_width() and 0 <= my < self.mask.get_height():
            c = self.mask.get_at((mx, my))
            return c[1] > 128, (c[1] > 128 and c[0] < 128)      # (можно стоять, зона выхода)
        return False, False

    def can_stand(self, x, y):
        return all(self.mask_at(x + dx, y + dy)[0] for dx in (-11, 11) for dy in (-8, 0))

    def at_exit(self):
        return self.mask_at(self.px, self.py)[1]

    def enter(self, world):
        self.px, self.py = self.to_screen(*self.SPAWN)
        world.face = "left"

    def update(self, dt, world):
        keys = pygame.key.get_pressed()
        running = world.tick_needs(dt, keys)
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        length = math.hypot(dx, dy)
        world.moving = bool(length)
        if length:
            dx, dy = dx / length, dy / length
            speed = world.speed * 0.8 * (1.55 if running and world.stamina > 0 else 1)
            nx, ny = self.px + dx * speed * dt, self.py + dy * speed * dt
            if self.can_stand(nx, self.py):
                self.px = nx
            if self.can_stand(self.px, ny):
                self.py = ny
            if abs(dx) > abs(dy):
                world.face = "left" if dx < 0 else "right"
            else:
                world.face = "up" if dy < 0 else "down"
        world.anim += dt * ((11 if running else 8) if world.moving else 2.5)
        world.floats = [f for f in world.floats if (f.__setitem__(3, f[3] - dt) or f[3] > 0)]
        world.hint = "E — выйти из самолёта" if self.at_exit() else ""

    def interact(self, world):
        if self.at_exit():
            world.exit_plane()

    def draw(self, world):
        world.screen.fill((0, 0, 0))
        world.screen.blit(self.img, (self.ox, self.oy))
        world.draw_player_at(self.px, self.py)
        world.draw_overlay((0, 0))


class Animal:
    SPEED = {"cow": 38, "hen": 50, "chick": 62}
    ANIM = {"cow": 5, "hen": 8, "chick": 9}

    def __init__(self, kind, variant, x, y):
        self.kind, self.variant = kind, variant
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.timer = random.uniform(0, 2)
        self.frame = random.uniform(0, 4)
        self.face = random.choice(["left", "right"])
        self.cool = 0.0

    def update(self, dt, world):
        self.timer -= dt
        if self.timer <= 0:
            if random.random() < 0.55:
                a = random.uniform(0, math.tau)
                self.vx, self.vy = math.cos(a), math.sin(a)
                self.timer = random.uniform(1, 3)
            else:
                self.vx = self.vy = 0.0
                self.timer = random.uniform(1, 4)
        if self.vx or self.vy:
            sp = self.SPEED[self.kind]
            nx, ny = self.x + self.vx * sp * dt, self.y + self.vy * sp * dt
            area = world.jungle if self.kind == "cow" else world.beach
            if (point_in_polygon((nx, ny), area) and not world.blocked(nx, ny, 12)
                    and not (self.kind == "cow" and world.is_tropic(nx, ny))):
                self.x, self.y = nx, ny
                self.face = "left" if self.vx < 0 else "right"
                self.frame += dt * self.ANIM[self.kind]
            else:
                self.vx = self.vy = 0.0
                self.timer = 0.3
        self.cool = max(0.0, self.cool - dt)

    def draw(self, surface, cam, sprites):
        fr = int(self.frame) % 4
        if self.kind == "cow":
            img = sprites.cow[self.variant][self.face][fr]
            oy = 0
        elif self.kind == "hen":
            img = sprites.hen[self.variant][self.face][fr]
            oy = PS
        else:
            img = sprites.chick[self.face][fr]
            oy = PS
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() + oy - cam[1])))


class IslandWorld:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.rng = random.Random(42)
        self.sprites = Sprites()
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 20, bold=True)

        self.player = pygame.Rect(WORLD_W//2 - 14, WORLD_H//2 + 120, 28, 18)
        self.face = "down"
        self.anim = 0.0
        self.moving = False
        self.speed = 260
        self.health = 100
        self.hunger = 100
        self.stamina = 100
        self.inventory = [
            {"name": "Кокос", "count": 3},
            {"name": "Дерево", "count": 5},
            {"name": "Камень", "count": 2},
        ] + [None] * (INV_SLOTS - 3)
        self.camera_x = 0
        self.camera_y = 0
        self.hint = ""
        self.floats = []   # всплывающие надписи: [текст, x, y, время жизни]

        self.split_x = WORLD_W // 2 + MEADOW_SPLIT
        self.island = make_island_points(WORLD_W//2, WORLD_H//2, 2100, 1450)
        self.beach = shrink_polygon(self.island, 0.91)
        self.jungle = shrink_polygon(self.island, 0.78)
        self.inner = shrink_polygon(self.island, 0.64)
        self.inner2 = shrink_polygon(self.island, 0.43)

        self.decor = pygame.Surface((WORLD_W, WORLD_H))
        self.decor.fill(SEA)
        pygame.draw.polygon(self.decor, SAND, self.island)
        pygame.draw.polygon(self.decor, SAND_LIGHT, self.beach)
        self.paint_zones()

        self.scene = "world"        # "world" — остров, "plane" — салон самолёта
        self.ui_request = None      # что нужно открыть в окне (например, сундук)
        self.interior = None
        self.plane = self.place_plane() if self.sprites.plane is not None else None

        self.trees = []
        self.palms = []
        self.rocks = []
        self.bushes = []
        self.flowers = []
        self.tufts = []
        self.grass_marks = []
        self.animals = []
        self.sharks = []
        self.selected_slot = 0

        rng = self.rng
        spawn = (self.player.centerx, self.player.bottom)

        def rand_point():
            return rng.randint(250, WORLD_W - 250), rng.randint(250, WORLD_H - 250)

        def far_from(items, x, y, dist):
            d2 = dist * dist
            return all((o.x - x) ** 2 + (o.y - y) ** 2 >= d2 for o in items)

        def near_plane(x, y):
            return self.plane is not None and self.plane.zone.collidepoint(x, y)

        # Пальмы на пляже (по всему берегу)
        for _ in range(6000):
            if len(self.palms) >= 90:
                break
            x, y = rand_point()
            if not (point_in_polygon((x, y), self.beach) and not point_in_polygon((x, y), self.jungle)):
                continue
            if math.hypot(x - spawn[0], y - spawn[1]) < 160:
                continue
            if not far_from(self.palms, x, y, 120):
                continue
            variant = rng.choices(["green", "dark", "yellow"], [0.5, 0.35, 0.15])[0]
            self.palms.append(Palm(x, y, variant))

        # Тропики — джунгли из особых деревьев; пальмы растут только на пляже.
        # (Если файлов Jungle_*.png в assets нет, остаётся прежний лес из пальм и клёнов.)
        jungle_kinds = [k for k in JUNGLE_TREES if k in self.sprites.tree]
        if not jungle_kinds:
            # Тропики: густой пальмовый лес в правой части острова
            for _ in range(9000):
                if len(self.palms) >= 90 + 170:
                    break
                x, y = rand_point()
                if not point_in_polygon((x, y), self.jungle) or not self.is_tropic(x, y):
                    continue
                if math.hypot(x - spawn[0], y - spawn[1]) < 230:
                    continue
                if not far_from(self.palms, x, y, 95):
                    continue
                variant = rng.choices(["green", "dark", "yellow"], [0.5, 0.4, 0.1])[0]
                self.palms.append(Palm(x, y, variant))

        # Клёны (дерево для рубки): немного в тропиках и редко на поляне
        def scatter_maples(limit, want_tropic, spacing):
            placed = 0
            for _ in range(6000):
                if placed >= limit:
                    break
                x, y = rand_point()
                if (not point_in_polygon((x, y), self.jungle) or self.is_tropic(x, y) != want_tropic
                        or near_plane(x, y)):
                    continue
                if math.hypot(x - spawn[0], y - spawn[1]) < 260:
                    continue
                if not far_from(self.trees, x, y, spacing) or not far_from(self.palms, x, y, 60):
                    continue
                kinds = ["big", "young", "sap"] + (["oak"] if "oak" in self.sprites.tree else [])
                kind = rng.choices(kinds, [0.3, 0.3, 0.15, 0.25][:len(kinds)])[0]
                self.trees.append(Tree(x, y, kind))
                placed += 1

        if jungle_kinds:
            placed = 0
            for _ in range(15000):
                if placed >= 220:
                    break
                x, y = rand_point()
                if not point_in_polygon((x, y), self.jungle) or not self.is_tropic(x, y):
                    continue
                if math.hypot(x - spawn[0], y - spawn[1]) < 230:
                    continue
                if not far_from(self.trees, x, y, 100) or not far_from(self.palms, x, y, 70):
                    continue
                self.trees.append(Tree(x, y, rng.choice(jungle_kinds)))
                placed += 1
        else:
            scatter_maples(70, True, 110)     # тропики (запасной вариант)
        scatter_maples(45, False, 170)    # поляна: деревьев мало

        # Камни на пляже
        for _ in range(500):
            if len(self.rocks) >= 200:
                break
            x, y = rand_point()
            if point_in_polygon((x, y), self.beach):
                self.rocks.append((x, y, rng.randint(0, 2)))

        # Кусты: в тропиках густо (в основном папоротники), на поляне — редкие круглые
        tropic_imgs, round_imgs = self.sprites.bush["tropic"], self.sprites.bush["meadow"]

        def pick_bush(in_tropics):
            if tropic_imgs and round_imgs:
                pool = tropic_imgs if (in_tropics and rng.random() < 0.75) else round_imgs
                return rng.choice(pool)
            return rng.randint(7, 15)       # нет спрайтов кустов — рисуем круги, как раньше

        for _ in range(5000):
            if len(self.bushes) >= 460:
                break
            x, y = rand_point()
            if not point_in_polygon((x, y), self.jungle) or near_plane(x, y):
                continue
            in_tropics = self.is_tropic(x, y)
            if not in_tropics and rng.random() > 0.17:      # на поляне кусты редкие
                continue
            self.bushes.append((x, y, pick_bush(in_tropics)))

        # Поляна: цветы и пучки травы
        flower_colors = [(245, 245, 235), (250, 215, 80), (235, 120, 150), (170, 140, 230), (240, 150, 70)]
        for _ in range(6000):
            if len(self.flowers) >= 650:
                break
            x, y = rand_point()
            if point_in_polygon((x, y), self.jungle) and not self.is_tropic(x, y) and not near_plane(x, y):
                self.flowers.append((x, y, rng.choice(flower_colors)))
        for _ in range(3000):
            if len(self.tufts) >= 700:
                break
            x, y = rand_point()
            if point_in_polygon((x, y), self.jungle) and not self.is_tropic(x, y) and not near_plane(x, y):
                self.tufts.append((x, y))

        # Сухая трава на песке
        for _ in range(6000):
            if len(self.grass_marks) >= 2800:
                break
            x, y = rand_point()
            if point_in_polygon((x, y), self.beach) and not point_in_polygon((x, y), self.jungle):
                self.grass_marks.append((x, y))

        # Сундук рядом с местом старта
        self.chest = Chest(spawn[0] + 150, spawn[1] + 40)

        self.sea_safe = shrink_polygon(self.island, 1.06)   # акулы не заплывают внутрь этой границы
        self.spawn_animals()
        self.spawn_sharks()
        self.draw_decorations()

    # ---------- зоны острова: поляна слева, тропики справа ----------
    def border_x(self, y):
        """Граница между поляной и тропиками на высоте y (слегка извилистая)."""
        return self.split_x + 110 * math.sin(y * 0.0042) + 50 * math.sin(y * 0.011 + 1.3)

    def is_tropic(self, x, y):
        return x > self.border_x(y)

    def paint_zones(self):
        # Тропики рисуем по всему острову, а светлую поляну — отдельным слоем,
        # который подставляем слева от извилистой границы.
        pygame.draw.polygon(self.decor, GRASS, self.jungle)
        pygame.draw.polygon(self.decor, JUNGLE, self.inner)
        pygame.draw.polygon(self.decor, DARK_JUNGLE, self.inner2)

        max_bx = int(self.split_x + 200)
        meadow = pygame.Surface((max_bx, WORLD_H), pygame.SRCALPHA)
        pygame.draw.polygon(meadow, MEADOW, self.jungle)
        pygame.draw.polygon(meadow, MEADOW_DARK, self.inner)
        step = 8
        for y0 in range(0, WORLD_H, step):
            bx = int(self.border_x(y0 + step // 2))
            self.decor.blit(meadow, (0, y0), (0, y0, bx, step))
        del meadow

        # Рваный край границы: пятна обеих «зон» вдоль неё
        rng = random.Random(7)
        for y in range(0, WORLD_H, 14):
            x = self.border_x(y) + rng.uniform(-26, 26)
            if not point_in_polygon((x, y), self.jungle):
                continue
            if x > self.border_x(y):
                if point_in_polygon((x, y), self.inner2):
                    color = DARK_JUNGLE
                elif point_in_polygon((x, y), self.inner):
                    color = JUNGLE
                else:
                    color = GRASS
            else:
                color = MEADOW_DARK if point_in_polygon((x, y), self.inner) else MEADOW
            pygame.draw.circle(self.decor, color, (int(x), y), rng.randint(7, 16))

    def spawn_animals(self):
        spawn = (self.player.centerx, self.player.bottom)

        def place(kind, variant, area, rmin, rmax, ok=None):
            for _ in range(1500):
                a = random.uniform(0, math.tau)
                d = random.uniform(rmin, rmax)
                x, y = spawn[0] + math.cos(a) * d, spawn[1] + math.sin(a) * d
                if ok and not ok(x, y):
                    continue
                if point_in_polygon((x, y), area) and not self.blocked(x, y, 20):
                    self.animals.append(Animal(kind, variant, x, y))
                    return

        for v in ("f", "m", "f", "m", "f", "m", "f", "m"):
            place("cow", v, self.jungle, 300, 1500, ok=lambda x, y: not self.is_tropic(x, y))   # коровы на поляне
        for _ in range(12):
            place("hen", random.choice(["red", "blonde"]), self.beach, 250, 1800)
        for _ in range(7):
            place("chick", None, self.beach, 250, 1800)

    def in_sea(self, x, y):
        return 70 < x < WORLD_W - 70 and 70 < y < WORLD_H - 70 and not point_in_polygon((x, y), self.sea_safe)

    def spawn_sharks(self):
        for _ in range(10):
            for _ in range(500):
                x, y = random.uniform(70, WORLD_W - 70), random.uniform(70, WORLD_H - 70)
                if self.in_sea(x, y) and all(math.hypot(x - o.x, y - o.y) > 300 for o in self.sharks):
                    self.sharks.append(Shark(x, y))
                    break

    def draw_decorations(self):
        for x, y in self.grass_marks:
            pygame.draw.line(self.decor, (190, 170, 111), (x, y), (x+2, y-5), 2)
        for x, y, v in self.rocks:
            img = self.sprites.rocks[v]
            self.decor.blit(img, (x - img.get_width() // 2, y - img.get_height()))
        for x, y, b in sorted(self.bushes, key=lambda it: it[1]):
            if isinstance(b, int):                      # запасной вариант без спрайтов
                pygame.draw.circle(self.decor, (23, 76, 42), (x, y), b + 3)
                pygame.draw.circle(self.decor, (47, 119, 57), (x - 3, y - 3), b)
            else:
                self.decor.blit(b, (x - b.get_width() // 2, y - b.get_height()))
        # поляна: пучки травы и цветы
        for x, y in self.tufts:
            pygame.draw.line(self.decor, (74, 126, 54), (x, y), (x - 2, y - 6), 2)
            pygame.draw.line(self.decor, (74, 126, 54), (x + 2, y), (x + 3, y - 5), 2)
        for x, y, color in self.flowers:
            pygame.draw.line(self.decor, (60, 110, 50), (x, y), (x, y + 5), 1)
            pygame.draw.circle(self.decor, color, (x, y), 3)
            self.decor.set_at((x, y), (255, 210, 60))

    # ---------- логика ----------
    def blocked(self, x, y, r=10):
        for t in self.trees:
            rad = t.radius
            if rad and abs(t.x - x) < rad + r and abs(t.y - y) < rad + r:
                if math.hypot(t.x - x, t.y - y) < rad + r:
                    return True
        for p in self.palms:
            if abs(p.x - x) < Palm.RADIUS + r and abs(p.y - y) < Palm.RADIUS + r:
                if math.hypot(p.x - x, p.y - y) < Palm.RADIUS + r:
                    return True
        if math.hypot(self.chest.x - x, self.chest.y - y) < 22 + r:
            return True
        if self.plane is not None and self.plane.block.inflate(2 * r, 2 * r).collidepoint(x, y):
            return True
        return False

    def add_item(self, name, count=1):
        return add_to_list(self.inventory, name, count)

    # ---------- сохранение / загрузка ----------
    def get_save_data(self):
        return {
            "version": 2,
            "player": [self.player.x, self.player.y],
            "face": self.face,
            "health": self.health,
            "hunger": self.hunger,
            "stamina": self.stamina,
            "selected_slot": self.selected_slot,
            "inventory": self.inventory,
            "chest_open": self.chest.open,
            "chest_items": self.chest.items,
            "trees": [[t.x, t.y, t.kind] for t in self.trees],
            "animals": [[a.kind, a.variant, a.x, a.y, a.cool] for a in self.animals],
        }

    def load_data(self, d):
        self.player.x, self.player.y = int(d["player"][0]), int(d["player"][1])
        self.face = d.get("face", "down") if d.get("face") in ("up", "down", "left", "right") else "down"
        self.health = max(1.0, min(100.0, float(d.get("health", 100))))
        self.hunger = max(0.0, min(100.0, float(d.get("hunger", 100))))
        self.stamina = max(0.0, min(100.0, float(d.get("stamina", 100))))
        self.selected_slot = max(0, min(HOTBAR - 1, int(d.get("selected_slot", 0))))

        inv = list(d.get("inventory", []))[:INV_SLOTS]
        inv += [None] * (INV_SLOTS - len(inv))
        self.inventory = [
            {"name": str(it["name"]), "count": int(it["count"])}
            if isinstance(it, dict) and int(it.get("count", 0)) > 0 else None
            for it in inv
        ]
        self.chest.open = bool(d.get("chest_open", False))
        if "chest_items" in d:
            self.chest.items = _clean_slots(d["chest_items"], CHEST_SLOTS)
        elif self.chest.open:                       # старое сохранение: припасы уже были забраны
            self.chest.items = [None] * CHEST_SLOTS

        if d.get("trees") and d.get("version", 1) >= 2:
            self.trees = [Tree(x, y, kind) for x, y, kind in d["trees"] if kind in TREE_RADIUS and kind in self.sprites.tree]
        if d.get("animals"):
            self.animals = []
            for kind, variant, x, y, cool in d["animals"]:
                a = Animal(kind, variant, x, y)
                a.cool = float(cool)
                self.animals.append(a)

        self.camera_x = max(0, min(WORLD_W - SCREEN_W, self.player.centerx - SCREEN_W // 2))
        self.camera_y = max(0, min(WORLD_H - SCREEN_H, self.player.centery - SCREEN_H // 2))

    # ---------- самолёт ----------
    def place_plane(self):
        """Ищет на поляне ровное место для самолёта (ничего не должно выходить за берег или в тропики)."""
        img = self.sprites.plane
        w = img.get_width()
        cx0, cy0 = WORLD_W // 2 - 1000, WORLD_H // 2 - 100
        for r in range(0, 750, 50):
            for k in range(12 if r else 1):
                a = k * math.tau / 12
                x, y = cx0 + math.cos(a) * r, cy0 + math.sin(a) * r
                pts = [(x - w * 0.45, y), (x + w * 0.45, y), (x - w * 0.45, y - 140),
                       (x + w * 0.45, y - 140), (x, y + 90)]
                if all(point_in_polygon(p, self.jungle) and not self.is_tropic(p[0] + 150, p[1]) for p in pts):
                    return Plane(int(x), int(y), img)
        return Plane(int(cx0), int(cy0), img)

    def _door_front(self):
        """Ставит героя на землю перед проломом в фюзеляже."""
        self.player.centerx = self.plane.door[0]
        self.player.bottom = self.plane.y + 30

    def enter_plane(self):
        if self.sprites.interior is None or self.sprites.interior_mask is None:
            self.say("Дверь заклинило", self.player.centerx, self.player.top)
            return
        if self.interior is None:
            self.interior = PlaneInterior(self.sprites)
        self._door_front()
        self.scene = "plane"
        self.interior.enter(self)
        self.hint = ""

    def exit_plane(self):
        self.scene = "world"
        self._door_front()
        self.floats = []

    def tick_needs(self, dt, keys):
        """Голод, выносливость и здоровье; возвращает True, если герой бежит."""
        self.hunger = max(0, self.hunger - 0.12 * dt)
        running = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        if running:
            self.stamina = max(0, self.stamina - 25 * dt)
        else:
            self.stamina = min(100, self.stamina + 15 * dt)
        if self.hunger <= 0:
            self.health = max(0, self.health - 3 * dt)
        return running

    def say(self, text, x, y):
        self.floats.append([text, x, y - 70, 1.6])

    def nearest_target(self):
        px, py = self.player.centerx, self.player.bottom
        best, best_d = None, 85
        for a in self.animals:
            d = math.hypot(a.x - px, a.y - py)
            if d < best_d:
                best, best_d = ("animal", a), d
        for t in self.trees:
            if t.kind == "stump":
                continue
            d = math.hypot(t.x - px, t.y - py)
            if d < best_d:
                best, best_d = ("tree", t), d
        d = math.hypot(self.chest.x - px, self.chest.y - py)
        if d < best_d:
            best, best_d = ("chest", self.chest), d
        if self.plane is not None:
            d = math.hypot(self.plane.door[0] - px, self.plane.door[1] - py)
            if d < best_d:
                best, best_d = ("plane", self.plane), d
        return best

    def hint_for(self, target):
        if not target:
            return ""
        kind, obj = target
        if kind == "animal":
            if obj.kind == "cow":
                return "Корова отдыхает" if obj.cool > 0 else "E — подоить корову"
            if obj.kind == "hen":
                return "Курица отдыхает" if obj.cool > 0 else "E — взять яйцо"
            return "Цыплёнок ещё маленький"
        if kind == "tree":
            return "E — собрать ветки" if obj.kind == "sap" else "E — рубить дерево"
        if kind == "plane":
            return "E — войти в самолёт"
        return "E — открыть сундук"

    def interact(self):
        if self.scene == "plane":
            self.interior.interact(self)
            return
        target = self.nearest_target()
        if not target:
            return
        kind, obj = target
        if kind == "animal":
            if obj.kind == "cow" and obj.cool <= 0:
                if self.add_item("Молоко"):
                    obj.cool = 45
                    self.say("+1 Молоко", obj.x, obj.y)
                else:
                    self.say("Инвентарь полон", obj.x, obj.y)
            elif obj.kind == "hen" and obj.cool <= 0:
                if self.add_item("Яйцо"):
                    obj.cool = 30
                    self.say("+1 Яйцо", obj.x, obj.y)
                else:
                    self.say("Инвентарь полон", obj.x, obj.y)
        elif kind == "tree":
            amount = {"big": 3, "young": 2, "sap": 1, "oak": 5, "jbamboo": 3}.get(obj.kind, 4)
            if self.add_item("Дерево", amount):
                self.say("+%d Дерево" % amount, obj.x, obj.y - 30)
                if obj.kind == "sap":
                    self.trees.remove(obj)
                else:
                    obj.kind = "stump"
            else:
                self.say("Инвентарь полон", obj.x, obj.y - 30)
        elif kind == "plane":
            self.enter_plane()
        else:
            self.ui_request = "chest"       # окно сундука откроет игровой цикл

    def use_selected(self):
        item = self.inventory[self.selected_slot]
        if not item or item["name"] not in FOOD:
            return
        self.hunger = min(100, self.hunger + FOOD[item["name"]])
        item["count"] -= 1
        if item["count"] <= 0:
            self.inventory[self.selected_slot] = None
        self.say("+%d сытость" % FOOD[item["name"]], self.player.centerx, self.player.top)

    def update(self, dt):
        if self.scene == "plane":
            self.interior.update(dt, self)
            return
        keys = pygame.key.get_pressed()
        running = self.tick_needs(dt, keys)
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        length = math.hypot(dx, dy)
        self.moving = bool(length)
        if length:
            dx, dy = dx/length, dy/length
            speed = self.speed * (1.55 if running and self.stamina > 0 else 1)
            nx = self.player.x + dx * speed * dt
            ny = self.player.y + dy * speed * dt
            if (point_in_polygon((nx + self.player.width/2, self.player.centery), self.island)
                    and not self.blocked(nx + self.player.width/2, self.player.bottom, 8)):
                self.player.x = int(nx)
            if (point_in_polygon((self.player.centerx, ny + self.player.height/2), self.island)
                    and not self.blocked(self.player.centerx, ny + self.player.height, 8)):
                self.player.y = int(ny)
            if abs(dx) > abs(dy):
                self.face = "left" if dx < 0 else "right"
            else:
                self.face = "up" if dy < 0 else "down"
        self.anim += dt * ((11 if running else 8) if self.moving else 2.5)

        for a in self.animals:
            a.update(dt, self)
        for sh in self.sharks:
            sh.update(dt, self)
        self.floats = [f for f in self.floats if (f.__setitem__(3, f[3] - dt) or f[3] > 0)]
        self.hint = self.hint_for(self.nearest_target())

        self.camera_x = max(0, min(WORLD_W-SCREEN_W, self.player.centerx-SCREEN_W//2))
        self.camera_y = max(0, min(WORLD_H-SCREEN_H, self.player.centery-SCREEN_H//2))

    # ---------- рисование ----------
    def draw_player(self, cam):
        self.draw_player_at(self.player.centerx - cam[0], self.player.bottom - cam[1])

    def draw_player_at(self, cx, bottom):
        sp = self.sprites
        frames = (sp.walk or sp.idle)[self.face] if self.moving and sp.walk else sp.idle[self.face]
        img = frames[int(self.anim) % len(frames)]
        bob = -abs(math.sin(self.anim * 1.2)) * 4 if (self.moving and not sp.walk) else 0
        pygame.draw.ellipse(self.screen, (30, 50, 35), (cx - 20, bottom - 8, 40, 14))
        # ноги героя на 26-й строке из 32 -> опускаем спрайт на 6 пикселей исходника
        self.screen.blit(img, (int(cx - img.get_width() / 2),
                               int(bottom - img.get_height() + 6 * PS + bob)))

    def draw(self):
        if self.scene == "plane":
            self.interior.draw(self)
            return
        cam = (int(self.camera_x), int(self.camera_y))
        self.screen.blit(self.decor, (0, 0), (cam[0], cam[1], SCREEN_W, SCREEN_H))

        view = pygame.Rect(cam[0] - 150, cam[1] - 250, SCREEN_W + 300, SCREEN_H + 450)
        for sh in self.sharks:
            if view.collidepoint(sh.x, sh.y):
                sh.draw(self.screen, cam, self.sprites)
        items = []
        for p in self.palms:
            if view.collidepoint(p.x, p.y):
                items.append((p.y, lambda o=p: o.draw(self.screen, cam, self.sprites)))
        for t in self.trees:
            if view.collidepoint(t.x, t.y):
                items.append((t.y, lambda o=t: o.draw(self.screen, cam, self.sprites)))
        for a in self.animals:
            if view.collidepoint(a.x, a.y):
                items.append((a.y, lambda o=a: o.draw(self.screen, cam, self.sprites)))
        if self.plane is not None and view.colliderect(self.plane.zone):
            items.append((self.plane.y, lambda: self.plane.draw(self.screen, cam)))
        if view.collidepoint(self.chest.x, self.chest.y):
            items.append((self.chest.y, lambda: self.chest.draw(self.screen, cam, self.sprites)))
        items.append((self.player.bottom, lambda: self.draw_player(cam)))
        for _, fn in sorted(items, key=lambda it: it[0]):
            fn()

        self.draw_overlay(cam)

    def draw_overlay(self, cam):
        # Всплывающие надписи
        for text, x, y, life in self.floats:
            rise = (1.6 - life) * 30
            img = self.small_font.render(text, True, (255, 245, 205))
            shadow = self.small_font.render(text, True, (15, 25, 20))
            pos = (int(x - cam[0] - img.get_width() / 2), int(y - cam[1] - rise))
            self.screen.blit(shadow, (pos[0] + 2, pos[1] + 2))
            self.screen.blit(img, pos)

        # Небольшой интерфейс
        label = self.font.render("QUIET HUNGER  |  WASD — движение  |  SHIFT — бег  |  E — действие  |  F — съесть  |  F11 — экран", True, (255, 255, 255))
        panel = pygame.Surface((label.get_width()+28, 48), pygame.SRCALPHA)
        panel.fill((12, 30, 25, 175))
        self.screen.blit(panel, (SCREEN_W - panel.get_width() - 18, 18))
        self.screen.blit(label, (SCREEN_W - panel.get_width() - 18 + 14, 29))

        # Подсказка действия над слотами
        if self.hint:
            txt = self.font.render(self.hint, True, (255, 245, 205))
            box = pygame.Surface((txt.get_width() + 30, 42), pygame.SRCALPHA)
            box.fill((12, 30, 25, 200))
            bx = SCREEN_W // 2 - box.get_width() // 2
            self.screen.blit(box, (bx, SCREEN_H - 155))
            self.screen.blit(txt, (bx + 15, SCREEN_H - 148))


def has_save():
    return os.path.exists(SAVE_PATH)


def write_save(data):
    try:
        tmp = SAVE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, SAVE_PATH)
        return True
    except OSError:
        return False


def read_save():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def draw_hud(screen, world):
    font = pygame.font.SysFont("consolas", 18, bold=True)
    small = pygame.font.SysFont("consolas", 14, bold=True)

    # Пиксельная панель показателей
    panel = pygame.Rect(20, 20, 310, 154)

    pygame.draw.rect(screen, (10, 22, 20), panel)
    pygame.draw.rect(screen, (105, 125, 85), panel, 3)

    stats = [
        ("HP", world.health, (190, 55, 55)),
        ("FOOD", world.hunger, (206, 155, 57)),
        ("ENERGY", world.stamina, (80, 180, 85))
    ]

    for i, (name, value, color) in enumerate(stats):
        y = 36 + i * 32

        label = font.render(name, True, (230, 230, 205))
        screen.blit(label, (32, y))

        bar = pygame.Rect(115, y + 3, 155, 17)
        pygame.draw.rect(screen, (35, 43, 39), bar)

        fill = int(bar.width * value / 100)
        if fill > 0:
            pygame.draw.rect(
                screen, color,
                (bar.x, bar.y, fill, bar.height)
            )

        pygame.draw.rect(screen, (160, 165, 135), bar, 2)

        number = small.render(
            str(int(value)), True, (255, 255, 255)
        )
        screen.blit(number, (280, y + 3))

    # Быстрые слоты
    slot_size = 66
    gap = 7
    total_width = 8 * slot_size + 7 * gap
    start_x = (screen.get_width() - total_width) // 2
    start_y = screen.get_height() - 95

    for i in range(HOTBAR):
        x = start_x + i * (slot_size + gap)
        rect = pygame.Rect(x, start_y, slot_size, slot_size)
        draw_slot(screen, rect, world.inventory[i], i == world.selected_slot, i + 1)


# ---------- предметы, слоты и инвентарь ----------
_font_cache = {}


def _font(size):
    f = _font_cache.get(size)
    if f is None:
        f = _font_cache[size] = pygame.font.SysFont("consolas", size, bold=True)
    return f


def item_description(name):
    if name in FOOD:
        return "F — съесть (+%d сытость)" % FOOD[name]
    return "Материал"


def draw_item_icon(screen, name, rect):
    """Простые иконки предметов, нарисованные кодом."""
    cx, cy = rect.center
    r = min(rect.width, rect.height) // 2 - 10
    if name == "Кокос":
        pygame.draw.circle(screen, (70, 45, 28), (cx, cy), r)
        pygame.draw.circle(screen, (122, 82, 48), (cx - 2, cy - 2), r - 3)
        for dx, dy in ((-r // 3, -r // 4), (r // 4, -r // 3), (0, r // 6)):
            pygame.draw.circle(screen, (45, 28, 18), (cx + dx, cy + dy), max(2, r // 7))
    elif name == "Дерево":
        for off in (-r // 2, r // 3):
            log = pygame.Rect(cx - r, cy + off - r // 3, 2 * r, (2 * r) // 3)
            pygame.draw.rect(screen, (140, 92, 50), log, border_radius=4)
            pygame.draw.rect(screen, (88, 58, 32), log, 2, border_radius=4)
            pygame.draw.circle(screen, (205, 165, 105), (log.right - 4, log.centery), max(2, log.height // 2 - 2))
    elif name == "Камень":
        pts = [(cx - r, cy + r // 2), (cx - r // 2, cy - r // 2), (cx + r // 3, cy - r),
               (cx + r, cy - r // 6), (cx + r * 2 // 3, cy + r * 2 // 3)]
        pygame.draw.polygon(screen, (130, 134, 138), pts)
        pygame.draw.polygon(screen, (80, 84, 90), pts, 3)
    elif name == "Молоко":
        body = pygame.Rect(cx - r // 2, cy - r // 2, r, int(r * 1.5))
        pygame.draw.rect(screen, (245, 248, 250), body, border_radius=4)
        pygame.draw.rect(screen, (120, 150, 190), body, 2, border_radius=4)
        pygame.draw.rect(screen, (90, 140, 200), (cx - r // 3, cy - r // 2 - 8, r * 2 // 3, 9), border_radius=2)
    elif name == "Яйцо":
        egg = pygame.Rect(cx - r * 2 // 3, cy - r, r * 4 // 3, int(r * 1.9))
        pygame.draw.ellipse(screen, (240, 225, 190), egg)
        pygame.draw.ellipse(screen, (190, 170, 130), egg, 2)
    else:
        txt = _font(22).render(name[:1].upper(), True, (240, 232, 195))
        screen.blit(txt, txt.get_rect(center=rect.center))


def draw_slot(screen, rect, item, selected=False, number=None, hover=False):
    pygame.draw.rect(screen, (34, 50, 42) if hover else (17, 29, 25), rect)
    pygame.draw.rect(screen, (170, 135, 65) if selected else (90, 105, 80), rect, 4 if selected else 2)
    if item:
        draw_item_icon(screen, item["name"], rect)
        txt = _font(16).render(str(item["count"]), True, (255, 255, 255))
        screen.blit(txt, (rect.right - txt.get_width() - 6, rect.bottom - txt.get_height() - 4))
    if number is not None:
        screen.blit(_font(14).render(str(number), True, (210, 210, 190)), (rect.x + 5, rect.y + 4))


class InventoryUI:
    """Окно инвентаря (персонаж слева) или окно сундука (сундук слева, его ячейки справа сверху).
    Предметы переносятся мышью: ЛКМ — взять/положить, ПКМ — половина стопки / один предмет,
    Shift + ЛКМ — быстро переложить между рюкзаком и сундуком."""
    SLOT, GAP = 80, 8

    def __init__(self):
        self.overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 190))
        self.layouts = {"inv": self._build(False), "box": self._build(True)}
        self.mode = "inv"
        self.L = self.layouts["inv"]
        self.box = None           # список ячеек открытого сундука
        self.title = "INVENTORY"
        self.box_img = None
        self._box_scaled = None
        self.preview = None
        self.held = None          # предмет «в руке» (на курсоре)
        self.held_src = None      # из какой ячейки взяли
        self.press_pos = None
        self.pressing = False

    def _build(self, with_box):
        step = self.SLOT + self.GAP
        panel = pygame.Rect(0, 0, 1120, 820 if with_box else 650)
        panel.center = (SCREEN_W // 2, SCREEN_H // 2)
        p = panel
        gx = p.x + 380
        rects, labels = {}, {}
        if with_box:
            gy = p.y + 124
            for n in range(CHEST_SLOTS):                         # ячейки сундука: 8 x 2
                rects[BOX_BASE + n] = pygame.Rect(gx + (n % 8) * step, gy + (n // 8) * step, self.SLOT, self.SLOT)
            labels["box"] = (gx, gy - 30)
            pack_y = gy + 2 * step + 52
        else:
            pack_y = p.y + 128
        labels["pack"] = (gx, pack_y - 30)
        for n in range(INV_SLOTS - HOTBAR):                      # рюкзак: 8 x 3
            rects[HOTBAR + n] = pygame.Rect(gx + (n % 8) * step, pack_y + (n // 8) * step, self.SLOT, self.SLOT)
        hot_y = pack_y + 3 * step + 58
        labels["hot"] = (gx, hot_y - 30)
        for n in range(HOTBAR):                                  # быстрые слоты
            rects[n] = pygame.Rect(gx + n * step, hot_y, self.SLOT, self.SLOT)
        portrait = pygame.Rect(p.x + 30, p.y + 100, 320, 300 if with_box else 470)
        return {"panel": panel, "rects": rects, "labels": labels, "portrait": portrait}

    # ----- открыть / закрыть сундук -----
    def open_box(self, items, title, image):
        self.mode, self.L = "box", self.layouts["box"]
        self.box, self.title, self.box_img = items, title, image
        self._box_scaled = None

    def close(self, world):
        self.return_held(world)
        self.mode, self.L = "inv", self.layouts["inv"]
        self.box, self.title = None, "INVENTORY"

    # ----- логика -----
    def slot_at(self, pos):
        for key, r in self.L["rects"].items():
            if r.collidepoint(pos):
                return key
        return None

    def _ref(self, world, key):
        """(список, индекс) для ячейки: рюкзак/быстрые слоты или ячейка сундука."""
        if key >= BOX_BASE:
            return self.box, key - BOX_BASE
        return world.inventory, key

    def mouse_down(self, world, button, pos, shift=False):
        key = self.slot_at(pos)
        if self.held is None:
            if key is None:
                return
            lst, idx = self._ref(world, key)
            if not lst[idx]:
                return
            if shift and button == 1 and self.box is not None:
                self.quick_move(world, key)
                return
            if button == 1:
                self.held, lst[idx] = lst[idx], None
            elif button == 3:
                half = (lst[idx]["count"] + 1) // 2
                self.held = {"name": lst[idx]["name"], "count": half}
                lst[idx]["count"] -= half
                if lst[idx]["count"] <= 0:
                    lst[idx] = None
            else:
                return
            self.held_src = key
            self.press_pos = pos
            self.pressing = (button == 1)
        else:
            self.pressing = False
            if key is None:
                self.return_held(world)
            else:
                self.place(world, key, button)

    def mouse_up(self, world, button, pos):
        # «перетаскивание»: взяли ЛКМ, сдвинули мышь и отпустили над ячейкой
        if button == 1 and self.pressing and self.held is not None:
            if math.hypot(pos[0] - self.press_pos[0], pos[1] - self.press_pos[1]) > 10:
                key = self.slot_at(pos)
                if key is None:
                    self.return_held(world)
                else:
                    self.place(world, key, 1)
        self.pressing = False

    def quick_move(self, world, key):
        lst, idx = self._ref(world, key)
        item = lst[idx]
        target = world.inventory if key >= BOX_BASE else self.box
        if add_to_list(target, item["name"], item["count"]):
            lst[idx] = None

    def place(self, world, key, button):
        lst, idx = self._ref(world, key)
        held, slot = self.held, lst[idx]
        if button == 3:                       # положить один предмет
            if slot is None:
                lst[idx] = {"name": held["name"], "count": 1}
            elif slot["name"] == held["name"]:
                slot["count"] += 1
            else:
                return
            held["count"] -= 1
            if held["count"] <= 0:
                self.held = None
            return
        if slot is None:
            lst[idx] = held
            self.held = None
        elif slot["name"] == held["name"]:    # одинаковые предметы складываются в одну стопку
            slot["count"] += held["count"]
            self.held = None
        else:                                 # разные — меняются местами
            lst[idx], self.held = held, slot

    def return_held(self, world):
        if self.held is None:
            return
        src = self.held_src
        if src is not None and (src < BOX_BASE or self.box is not None):
            lst, idx = self._ref(world, src)
            if lst[idx] is None:
                lst[idx] = self.held
                self.held = None
        if self.held is not None and world.add_item(self.held["name"], self.held["count"]):
            self.held = None
        self.pressing = False

    def number_key(self, world, n):
        """Цифра 1-8 над предметом: обменять его с быстрым слотом n."""
        key = self.slot_at(pygame.mouse.get_pos())
        if key is None or self.held is not None or key == n:
            return
        lst, idx = self._ref(world, key)
        lst[idx], world.inventory[n] = world.inventory[n], lst[idx]

    # ----- рисование -----
    def draw(self, screen, world, t):
        mouse = pygame.mouse.get_pos()
        L = self.L
        screen.blit(self.overlay, (0, 0))
        p, pr = L["panel"], L["portrait"]
        pygame.draw.rect(screen, (18, 31, 27), p, border_radius=10)
        pygame.draw.rect(screen, (125, 145, 95), p, 4, border_radius=10)
        screen.blit(_font(30).render(self.title, True, (230, 210, 150)), (p.x + 30, p.y + 24))
        pygame.draw.line(screen, (125, 145, 95), (p.x + 20, p.y + 76), (p.right - 20, p.y + 76), 3)

        pygame.draw.rect(screen, (26, 44, 37), pr, border_radius=8)
        pygame.draw.rect(screen, (95, 115, 80), pr, 2, border_radius=8)
        if self.mode == "box":
            self._draw_chest_picture(screen, pr)
        else:
            self._draw_player_portrait(screen, world, pr, t)

        # подписи и ячейки
        lab = L["labels"]
        if "box" in lab:
            screen.blit(_font(16).render("CHEST", True, (205, 205, 175)), lab["box"])
        screen.blit(_font(16).render("BACKPACK", True, (205, 205, 175)), lab["pack"])
        screen.blit(_font(16).render("QUICK SLOTS  (1-8)", True, (205, 205, 175)), lab["hot"])
        for key, r in L["rects"].items():
            lst, idx = self._ref(world, key)
            draw_slot(screen, r, lst[idx],
                      selected=(key < HOTBAR and key == world.selected_slot),
                      number=(key + 1 if key < HOTBAR else None),
                      hover=r.collidepoint(mouse))

        if self.mode == "box":
            hint = "LMB - take / put   RMB - half / one   SHIFT+LMB - quick move   E / ESC - close"
        else:
            hint = "LMB - take / put    RMB - half / one    1-8 - to quick slot    TAB / ESC - close"
        screen.blit(_font(15).render(hint, True, (205, 205, 175)), (p.x + 30, p.bottom - 38))

        # подсказка над предметом
        hover = self.slot_at(mouse)
        if self.held is None and hover is not None:
            lst, idx = self._ref(world, hover)
            item = lst[idx]
            if item:
                l1 = _font(18).render(item["name"], True, (255, 245, 205))
                l2 = _font(14).render(item_description(item["name"]), True, (205, 215, 180))
                box = pygame.Rect(mouse[0] + 18, mouse[1] + 18, max(l1.get_width(), l2.get_width()) + 24, 56)
                box.clamp_ip(screen.get_rect())
                pygame.draw.rect(screen, (12, 24, 20), box, border_radius=6)
                pygame.draw.rect(screen, (125, 145, 95), box, 2, border_radius=6)
                screen.blit(l1, (box.x + 12, box.y + 8))
                screen.blit(l2, (box.x + 12, box.y + 32))

        # предмет на курсоре
        if self.held is not None:
            r = pygame.Rect(0, 0, 64, 64)
            r.center = mouse
            draw_item_icon(screen, self.held["name"], r)
            cnt = _font(16).render(str(self.held["count"]), True, (255, 255, 255))
            screen.blit(cnt, (r.right - cnt.get_width(), r.bottom - cnt.get_height()))

    def _draw_chest_picture(self, screen, pr):
        if self.box_img is not None:
            if self._box_scaled is None:
                iw, ih = self.box_img.get_size()
                k = min((pr.width - 20) / iw, (pr.height - 20) / ih)
                self._box_scaled = pygame.transform.smoothscale(self.box_img, (int(iw * k), int(ih * k)))
            screen.blit(self._box_scaled, self._box_scaled.get_rect(center=pr.center))
        else:
            pygame.draw.rect(screen, (110, 70, 40), pr.inflate(-60, -60), border_radius=6)
        txt = _font(15).render("Items stay in the chest", True, (170, 175, 150))
        screen.blit(txt, txt.get_rect(midtop=(pr.centerx, pr.bottom + 14)))

    def _draw_player_portrait(self, screen, world, pr, t):
        if self.preview is None:
            self.preview = [pygame.transform.scale(f, (f.get_width() * 2, f.get_height() * 2))
                            for f in world.sprites.idle["down"]]
        img = self.preview[int(t * 2.5) % len(self.preview)]
        top = pr.y + 28
        pygame.draw.ellipse(screen, (16, 28, 22), (pr.centerx - 55, top + img.get_height() - 54, 110, 26))
        screen.blit(img, (pr.centerx - img.get_width() // 2, top))
        label = _font(22).render("SURVIVOR", True, (230, 210, 150))
        screen.blit(label, label.get_rect(midtop=(pr.centerx, pr.y + 236)))
        for k, (name, value, color) in enumerate((("HP", world.health, (190, 55, 55)),
                                                  ("FOOD", world.hunger, (206, 155, 57)),
                                                  ("ENERGY", world.stamina, (80, 180, 85)))):
            y = pr.y + 290 + k * 44
            screen.blit(_font(16).render(name, True, (230, 230, 205)), (pr.x + 22, y))
            bar = pygame.Rect(pr.x + 110, y + 1, 180, 18)
            pygame.draw.rect(screen, (35, 43, 39), bar)
            fill = int(bar.width * max(0, min(100, value)) / 100)
            if fill > 0:
                pygame.draw.rect(screen, color, (bar.x, bar.y, fill, bar.height))
            pygame.draw.rect(screen, (160, 165, 135), bar, 2)


# ---------- меню паузы ----------
PAUSE_PANEL = pygame.Rect(0, 0, 520, 520)
PAUSE_PANEL.center = (SCREEN_W // 2, SCREEN_H // 2)
PAUSE_BUTTONS = {}
for _k, _name in enumerate(("RESUME", "SETTINGS", "SAVE GAME", "MAIN MENU")):
    _r = pygame.Rect(0, 0, 360, 62)
    _r.center = (PAUSE_PANEL.centerx, PAUSE_PANEL.y + 140 + _k * 80)
    PAUSE_BUTTONS[_name] = _r


def draw_pause_menu(screen, dim, fonts):
    mouse = pygame.mouse.get_pos()
    screen.blit(dim, (0, 0))
    ui.draw_frame(screen, PAUSE_PANEL, "PAUSED", fonts)
    for name, rect in PAUSE_BUTTONS.items():
        base = (60, 110, 65) if name == "SAVE GAME" else (40, 62, 48)
        ui.draw_button(screen, fonts["button"], rect, name, rect.collidepoint(mouse), base=base)
    ui.draw_text(screen, fonts["small"], "Unsaved progress is lost when you leave", (170, 170, 150),
                 midbottom=(PAUSE_PANEL.centerx, PAUSE_PANEL.bottom - 16))


def draw_death_screen(screen):
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 190))
    screen.blit(overlay, (0, 0))

    title_font = pygame.font.SysFont("arial", 90, bold=True)
    button_font = pygame.font.SysFont("arial", 30, bold=True)

    title = title_font.render("DEATH", True, (190, 45, 45))
    screen.blit(
        title,
        title.get_rect(center=(800, 330))
    )

    new_game_button = pygame.Rect(600, 440, 400, 70)
    menu_button = pygame.Rect(600, 540, 400, 70)

    pygame.draw.rect(screen, (65, 105, 65), new_game_button, border_radius=8)
    pygame.draw.rect(screen, (100, 100, 100), menu_button, border_radius=8)

    pygame.draw.rect(screen, (180, 180, 180), new_game_button, 2, border_radius=8)
    pygame.draw.rect(screen, (180, 180, 180), menu_button, 2, border_radius=8)

    text = button_font.render("NEW GAME", True, (255, 255, 255))
    screen.blit(text, text.get_rect(center=new_game_button.center))

    text = button_font.render("MAIN MENU", True, (255, 255, 255))
    screen.blit(text, text.get_rect(center=menu_button.center))

    return new_game_button, menu_button

def run_game(load=False):
    pygame.init()

    screen = pygame.display.get_surface()

    if screen is None:
        screen = pygame.display.set_mode((1600, 900), settings.display_flags())

    pygame.display.set_caption("Quiet Hunger — Survival")

    world = IslandWorld(screen)
    notice, notice_t = "", 0.0

    if load:
        data = read_save()
        try:
            if data is None:
                raise ValueError("нет сохранения")
            world.load_data(data)
        except (ValueError, KeyError, TypeError, IndexError):
            world = IslandWorld(screen)            # сохранение битое — начинаем заново
            notice, notice_t = "Could not load the save - new game started", 4.0

    fonts = ui.make_fonts()
    dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    settings_panel = ui.SettingsPanel((SCREEN_W // 2, SCREEN_H // 2))
    inv_ui = InventoryUI()

    running = True
    inventory_open = False
    pause = None            # None | "menu" | "settings"
    dead = False
    t = 0.0

    while running:
        dt = min(world.clock.tick(FPS) / 1000, 0.05)
        t += dt
        notice_t = max(0.0, notice_t - dt)

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                settings.toggle_fullscreen()
                continue

            if dead:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    new_game_button = pygame.Rect(600, 440, 400, 70)
                    menu_button = pygame.Rect(600, 540, 400, 70)

                    if new_game_button.collidepoint(event.pos):
                        world = IslandWorld(screen)
                        inv_ui = InventoryUI()
                        inventory_open = False
                        dead = False

                    elif menu_button.collidepoint(event.pos):
                        running = False

                continue

            # --- меню паузы ---
            if pause == "settings":
                if settings_panel.handle(event):
                    pause = "menu"
                continue

            if pause == "menu":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pause = None
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for name, rect in PAUSE_BUTTONS.items():
                        if not rect.collidepoint(event.pos):
                            continue
                        if name == "RESUME":
                            pause = None
                        elif name == "SETTINGS":
                            pause = "settings"
                        elif name == "SAVE GAME":
                            ok = write_save(world.get_save_data())
                            notice, notice_t = ("Game saved" if ok else "Could not save the game"), 2.5
                        elif name == "MAIN MENU":
                            running = False
                continue

            # --- обычная игра / инвентарь ---
            if inventory_open:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    inv_ui.mouse_down(world, event.button, event.pos,
                                      bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
                elif event.type == pygame.MOUSEBUTTONUP:
                    inv_ui.mouse_up(world, event.button, event.pos)
            elif event.type == pygame.MOUSEWHEEL:
                world.selected_slot = (world.selected_slot - event.y) % HOTBAR

            if event.type == pygame.KEYDOWN:

                if event.key in (pygame.K_TAB, pygame.K_i):
                    inventory_open = not inventory_open
                    if not inventory_open:
                        inv_ui.close(world)

                elif event.key == pygame.K_ESCAPE:
                    if inventory_open:
                        inventory_open = False
                        inv_ui.close(world)
                    else:
                        pause = "menu"

                elif inventory_open:
                    if event.key == pygame.K_e and inv_ui.mode == "box":
                        inventory_open = False
                        inv_ui.close(world)
                    elif pygame.K_1 <= event.key <= pygame.K_8:
                        inv_ui.number_key(world, event.key - pygame.K_1)

                else:
                    if pygame.K_1 <= event.key <= pygame.K_8:
                        world.selected_slot = event.key - pygame.K_1
                    elif event.key == pygame.K_e:
                        world.interact()
                    elif event.key == pygame.K_f:
                        world.use_selected()

        if world.ui_request:
            request, world.ui_request = world.ui_request, None
            if request == "chest" and not inventory_open and pause is None and not dead:
                world.chest.open = True
                inventory_open = True
                inv_ui.open_box(world.chest.items, "CHEST", world.sprites.chest_ui)

        if not dead:

            if not inventory_open and pause is None:
                world.update(dt)

            if world.health <= 0:
                world.health = 0
                dead = True
                if inventory_open:
                    inventory_open = False
                    inv_ui.close(world)

        world.draw()
        draw_hud(screen, world)

        if inventory_open and not dead:
            inv_ui.draw(screen, world, t)

        if pause == "menu":
            draw_pause_menu(screen, dim, fonts)
        elif pause == "settings":
            settings_panel.draw(screen, dim, fonts)

        if dead:
            draw_death_screen(screen)

        if notice_t > 0:
            ui.draw_text(screen, fonts["text"], notice, (255, 240, 190), midtop=(SCREEN_W // 2, 24))

        pygame.display.flip()

    pygame.display.set_caption("Quiet Hunger")


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("Quiet Hunger — Island")
    world = IslandWorld(screen)
    running = True

    while running:
        dt = min(world.clock.tick(FPS) / 1000, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        world.update(dt)
        world.draw()
        pygame.display.flip()

    pygame.quit()
