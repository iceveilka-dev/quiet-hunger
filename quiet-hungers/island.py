import math
import os
import random
import pygame
import sys
import traceback
# Quiet Hunger — процедурный мир тропического острова
# Море и волны, пальмы, джунгли и акулы собраны из ассетов в папке assets/.
# Управление: WASD / стрелки, Shift — бег, E — действие, F — съесть предмет из выбранного слота,
# 1-8 — выбор слота, TAB / I — инвентарь, ESC — выход в меню.

SCREEN_W, SCREEN_H = 1600, 900
WORLD_W, WORLD_H = 3600, 2800
FPS = 60

SEA = (35, 145, 170)
SAND = (222, 190, 123)
SAND_LIGHT = (237, 210, 151)
GRASS = (58, 112, 57)
JUNGLE = (32, 83, 48)
DARK_JUNGLE = (24, 66, 43)

# ---------- спрайты (Farm RPG 16x16 Tiny Asset Pack) ----------
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
PALM_SCALE = 1  # масштаб пальм (целое число; 1 = как в Trees_.png)
PS = 3  # во сколько раз увеличиваем пиксель-арт (целое число, чтобы пиксели оставались чёткими)

# Сколько сытости даёт еда (F по выбранному слоту)
FOOD = {"Кокос": 18, "Яйцо": 15, "Молоко": 30}

# Деревья джунглей (из Trees_.png): вид -> (файл, радиус ствола, сколько дерева даёт, вес при генерации)
JUNGLE_SCALE = 2   # масштаб деревьев джунглей (целое число)
JUNGLE_TREES = {
    "vine1": ("Jungle_Vine1.png", 16, 3, 0.17),
    "vine2": ("Jungle_Vine2.png", 16, 3, 0.17),
    "leaf1": ("Jungle_Leaf1.png", 15, 3, 0.15),
    "leaf2": ("Jungle_Leaf2.png", 15, 3, 0.15),
    "bamboo": ("Jungle_Bamboo.png", 12, 2, 0.12),
    "baobab": ("Jungle_Baobab.png", 30, 5, 0.04),
    "bush1": ("Jungle_Bush1.png", 0, 1, 0.10),
    "bush2": ("Jungle_Bush2.png", 0, 1, 0.10),
}
TREE_RADIUS = {k: v[1] for k, v in JUNGLE_TREES.items()}
TREE_RADIUS["stump"] = 10

# Вода
WATER_FPS = 10      # скорость анимации моря (кадров в секунду), кадры идут туда-обратно
WAVE_ROWS = (0, 1, 4, 5)   # какие ряды листа вода.png используем для прибоя


def _load(name, optional=False, scale=None):
    scale = PS if scale is None else scale
    path = os.path.join(ASSET_DIR, name)
    if optional and not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, (img.get_width() * scale, img.get_height() * scale))


def _cut(sheet, x, y, w, h):
    """Вырезает кусок из уже увеличенного листа; x, y, w, h — в исходных пикселях."""
    return sheet.subsurface((x * PS, y * PS, w * PS, h * PS)).copy()


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

        # Деревья джунглей, кусты и пень
        self.tree = {k: _load(v[0], scale=JUNGLE_SCALE) for k, v in JUNGLE_TREES.items()}
        self.tree["stump"] = _load("Jungle_Stump.png", scale=JUNGLE_SCALE)
        rocks = _load("Rocks.png")
        self.rocks = [_cut(rocks, i * 16, 0, 16, 16) for i in range(3)]

        chest = _load("chest.png")
        self.chest_closed = _cut(chest, 0, 0, 32, 16)
        self.chest_open = _cut(chest, 0, 16, 32, 16)

        # Вода: анимированная текстура моря (50 кадров 250x250, сетка 10x5)
        atlas = pygame.image.load(os.path.join(ASSET_DIR, "Water.png")).convert()
        self.water = [atlas.subsurface(((i % 10) * 250, (i // 10) * 250, 250, 250)).copy() for i in range(50)]
        # Прибой: сетка 9x6, 6 видов волн по 9 кадров
        wsheet = pygame.image.load(os.path.join(ASSET_DIR, "Waves.png")).convert_alpha()
        cw, ch = wsheet.get_width() // 9, wsheet.get_height() // 6
        self.wave = [[wsheet.subsurface((c * cw, r * ch, cw, ch)).copy() for c in range(9)] for r in range(6)]

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


class Wave:
    """Волна прибоя: накатывает у берега, затем пауза."""
    FPS = 9

    def __init__(self, x, y, row, phase):
        self.x, self.y, self.row = x, y, row
        self.pause = random.uniform(2, 6)
        self.t = phase

    def frame(self):
        local = self.t % (9 / self.FPS + self.pause)
        return int(local * self.FPS) if local < 9 / self.FPS else None

    def draw(self, surface, cam, sprites):
        fr = self.frame()
        if fr is None:
            return
        img = sprites.wave[self.row][fr]
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() / 2 - cam[1])))


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

    def draw(self, surface, cam, sprites):
        img = sprites.chest_open if self.open else sprites.chest_closed
        surface.blit(img, (int(self.x - img.get_width() / 2 - cam[0]),
                           int(self.y - img.get_height() - cam[1])))


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
            if point_in_polygon((nx, ny), area) and not world.blocked(nx, ny, 12):
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
            None, None, None, None, None, None, None,
            None, None, None, None, None,
            None, None, None, None, None,
            None, None, None, None, None
        ]
        self.camera_x = 0
        self.camera_y = 0
        self.hint = ""
        self.t = 0.0
        self.water_idx = -1
        self.water_tile = pygame.Surface((500, 500))
        self.floats = []   # всплывающие надписи: [текст, x, y, время жизни]

        self.island = make_island_points(WORLD_W//2, WORLD_H//2, 1450, 1050)
        self.beach = shrink_polygon(self.island, 0.91)
        self.jungle = shrink_polygon(self.island, 0.78)

        self.decor = pygame.Surface((WORLD_W, WORLD_H))
        self.decor.fill(SEA)
        self.decor.set_colorkey(SEA)   # синий цвет моря прозрачный: под ним рисуется анимированная вода
        pygame.draw.polygon(self.decor, SAND, self.island)
        pygame.draw.polygon(self.decor, SAND_LIGHT, self.beach)
        pygame.draw.polygon(self.decor, GRASS, self.jungle)
        inner = shrink_polygon(self.island, 0.64)
        pygame.draw.polygon(self.decor, JUNGLE, inner)
        inner2 = shrink_polygon(self.island, 0.43)
        pygame.draw.polygon(self.decor, DARK_JUNGLE, inner2)

        self.trees = []
        self.palms = []
        self.rocks = []
        self.bushes = []
        self.grass_marks = []
        self.animals = []
        self.sharks = []
        self.selected_slot = 0

        # Пальмы на пляже и вдоль кромки джунглей
        spawn = (self.player.centerx, self.player.bottom)
        for _ in range(900):
            if len(self.palms) >= 60:
                break
            x = self.rng.randint(250, WORLD_W-250)
            y = self.rng.randint(250, WORLD_H-250)
            if not (point_in_polygon((x, y), self.beach) and not point_in_polygon((x, y), self.jungle)):
                continue
            if math.hypot(x - spawn[0], y - spawn[1]) < 160:
                continue
            if any(math.hypot(p.x - x, p.y - y) < 120 for p in self.palms):
                continue
            variant = self.rng.choices(["green", "dark", "yellow"], [0.5, 0.35, 0.15])[0]
            self.palms.append(Palm(x, y, variant))

        # Клёны внутри острова (с минимальным расстоянием друг от друга)
        for _ in range(1500):
            if len(self.trees) >= 130:
                break
            x = self.rng.randint(250, WORLD_W-250)
            y = self.rng.randint(250, WORLD_H-250)
            if not point_in_polygon((x, y), self.jungle):
                continue
            if math.hypot(x - spawn[0], y - spawn[1]) < 230:
                continue
            kind = self.rng.choices(list(JUNGLE_TREES), [v[3] for v in JUNGLE_TREES.values()])[0]
            small = kind.startswith("bush")
            if any(math.hypot(t.x - x, t.y - y) < (55 if small or t.kind.startswith("bush") else 130) for t in self.trees):
                continue
            self.trees.append(Tree(x, y, kind))

        # Камни, кусты и пятна травы
        for _ in range(90):
            x = self.rng.randint(250, WORLD_W-250)
            y = self.rng.randint(250, WORLD_H-250)
            if point_in_polygon((x, y), self.beach):
                self.rocks.append((x, y, self.rng.randint(0, 2)))
        for _ in range(160):
            x = self.rng.randint(250, WORLD_W-250)
            y = self.rng.randint(250, WORLD_H-250)
            if point_in_polygon((x, y), self.jungle):
                self.bushes.append((x, y, self.rng.randint(7, 15)))
        for _ in range(1200):
            x = self.rng.randint(250, WORLD_W-250)
            y = self.rng.randint(250, WORLD_H-250)
            if point_in_polygon((x, y), self.beach):
                self.grass_marks.append((x, y))

        # Сундук рядом с местом старта
        self.chest = Chest(spawn[0] + 150, spawn[1] + 40)

        # Прибой по краю острова
        self.waves = []
        for i in range(0, len(self.island), 5):
            x, y = self.island[i]
            d = math.hypot(x - WORLD_W / 2, y - WORLD_H / 2) or 1
            ox, oy = (x - WORLD_W / 2) / d * 46, (y - WORLD_H / 2) / d * 46
            self.waves.append(Wave(x + ox, y + oy, random.choice(WAVE_ROWS), random.uniform(0, 10)))
        self.sea_safe = shrink_polygon(self.island, 1.06)   # акулы не заплывают внутрь этой границы
        self.spawn_animals()
        self.spawn_sharks()
        self.draw_decorations()

    def spawn_animals(self):
        spawn = (self.player.centerx, self.player.bottom)

        def place(kind, variant, area, rmin, rmax):
            for _ in range(400):
                a = random.uniform(0, math.tau)
                d = random.uniform(rmin, rmax)
                x, y = spawn[0] + math.cos(a) * d, spawn[1] + math.sin(a) * d
                if point_in_polygon((x, y), area) and not self.blocked(x, y, 20):
                    self.animals.append(Animal(kind, variant, x, y))
                    return

        for v in ("f", "m", "f", "m", "f", "m"):
            place("cow", v, self.jungle, 300, 900)
        for _ in range(8):
            place("hen", random.choice(["red", "blonde"]), self.beach, 250, 1000)
        for _ in range(5):
            place("chick", None, self.beach, 250, 1000)

    def in_sea(self, x, y):
        return 70 < x < WORLD_W - 70 and 70 < y < WORLD_H - 70 and not point_in_polygon((x, y), self.sea_safe)

    def spawn_sharks(self):
        for _ in range(7):
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
        for x, y, r in self.bushes:
            pygame.draw.circle(self.decor, (23, 76, 42), (x, y), r+3)
            pygame.draw.circle(self.decor, (47, 119, 57), (x-3, y-3), r)

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
        return False

    def add_item(self, name, count=1):
        for it in self.inventory:
            if it and it["name"] == name:
                it["count"] += count
                return True
        for i, it in enumerate(self.inventory):
            if it is None:
                self.inventory[i] = {"name": name, "count": count}
                return True
        return False

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
        if not self.chest.open:
            d = math.hypot(self.chest.x - px, self.chest.y - py)
            if d < best_d:
                best, best_d = ("chest", self.chest), d
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
            return "E — собрать ветки" if obj.kind.startswith("bush") else "E — рубить дерево"
        return "E — открыть сундук"

    def interact(self):
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
            amount = JUNGLE_TREES[obj.kind][2]
            if self.add_item("Дерево", amount):
                self.say("+%d Дерево" % amount, obj.x, obj.y - 30)
                if obj.kind.startswith("bush"):
                    self.trees.remove(obj)
                else:
                    obj.kind = "stump"
            else:
                self.say("Инвентарь полон", obj.x, obj.y - 30)
        else:
            obj.open = True
            self.add_item("Дерево", 4)
            self.add_item("Камень", 3)
            self.add_item("Кокос", 3)
            self.say("Нашёл припасы!", obj.x, obj.y)

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
        keys = pygame.key.get_pressed()
        self.hunger = max(0, self.hunger - 0.12 * dt)
        running = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        if running:
            self.stamina = max(0, self.stamina - 25 * dt)
        else:
            self.stamina = min(100, self.stamina + 15 * dt)
        if self.hunger <= 0:
            self.health = max(0, self.health - 3 * dt)
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
        self.t += dt
        for w in self.waves:
            w.t += dt
        self.floats = [f for f in self.floats if (f.__setitem__(3, f[3] - dt) or f[3] > 0)]
        self.hint = self.hint_for(self.nearest_target())

        self.camera_x = max(0, min(WORLD_W-SCREEN_W, self.player.centerx-SCREEN_W//2))
        self.camera_y = max(0, min(WORLD_H-SCREEN_H, self.player.centery-SCREEN_H//2))

    # ---------- рисование ----------
    def draw_sea(self, cam):
        """Анимированное море. Текстура не бесшовная, поэтому тайлы чередуются зеркально."""
        frames = self.sprites.water
        n = len(frames)
        step = int(self.t * WATER_FPS) % (2 * (n - 1))
        idx = step if step < n else 2 * (n - 1) - step      # туда-обратно, без скачка в конце
        if idx != self.water_idx:
            self.water_idx = idx
            f, tile = frames[idx], self.water_tile
            tile.blit(f, (0, 0))
            tile.blit(pygame.transform.flip(f, True, False), (250, 0))
            tile.blit(pygame.transform.flip(f, False, True), (0, 250))
            tile.blit(pygame.transform.flip(f, True, True), (250, 250))
        for y in range(-(cam[1] % 500), SCREEN_H, 500):
            for x in range(-(cam[0] % 500), SCREEN_W, 500):
                self.screen.blit(self.water_tile, (x, y))

    def draw_player(self, cam):
        sp = self.sprites
        frames = (sp.walk or sp.idle)[self.face] if self.moving and sp.walk else sp.idle[self.face]
        img = frames[int(self.anim) % len(frames)]
        bob = -abs(math.sin(self.anim * 1.2)) * 4 if (self.moving and not sp.walk) else 0
        cx = self.player.centerx - cam[0]
        bottom = self.player.bottom - cam[1]
        pygame.draw.ellipse(self.screen, (30, 50, 35), (cx - 20, bottom - 8, 40, 14))
        # ноги героя на 26-й строке из 32 -> опускаем спрайт на 6 пикселей исходника
        self.screen.blit(img, (int(cx - img.get_width() / 2),
                               int(bottom - img.get_height() + 6 * PS + bob)))

    def draw(self):
        cam = (int(self.camera_x), int(self.camera_y))
        self.draw_sea(cam)
        self.screen.blit(self.decor, (0, 0), (cam[0], cam[1], SCREEN_W, SCREEN_H))

        view = pygame.Rect(cam[0] - 150, cam[1] - 250, SCREEN_W + 300, SCREEN_H + 450)
        for w in self.waves:
            if view.collidepoint(w.x, w.y):
                w.draw(self.screen, cam, self.sprites)
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
        if view.collidepoint(self.chest.x, self.chest.y):
            items.append((self.chest.y, lambda: self.chest.draw(self.screen, cam, self.sprites)))
        items.append((self.player.bottom, lambda: self.draw_player(cam)))
        for _, fn in sorted(items, key=lambda it: it[0]):
            fn()

        # Всплывающие надписи
        for text, x, y, life in self.floats:
            rise = (1.6 - life) * 30
            img = self.small_font.render(text, True, (255, 245, 205))
            shadow = self.small_font.render(text, True, (15, 25, 20))
            pos = (int(x - cam[0] - img.get_width() / 2), int(y - cam[1] - rise))
            self.screen.blit(shadow, (pos[0] + 2, pos[1] + 2))
            self.screen.blit(img, pos)

        # Небольшой интерфейс
        label = self.font.render("QUIET HUNGER  |  WASD — движение  |  SHIFT — бег  |  E — действие  |  F — съесть", True, (255, 255, 255))
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

    for i in range(8):
        x = start_x + i * (slot_size + gap)
        rect = pygame.Rect(x, start_y, slot_size, slot_size)

        color = (170, 135, 65) if i == world.selected_slot else (90, 105, 80)

        pygame.draw.rect(screen, (17, 29, 25), rect)
        pygame.draw.rect(screen, color, rect, 4 if i == world.selected_slot else 2)

        item = world.inventory[i]

        if item:
            name = item["name"][:5].upper()
            text = small.render(name, True, (245, 235, 195))
            screen.blit(text, text.get_rect(center=(x + 33, start_y + 30)))

            count = small.render(str(item["count"]), True, (255, 255, 255))
            screen.blit(count, (x + 45, start_y + 45))

        key = small.render(str(i + 1), True, (210, 210, 190))
        screen.blit(key, (x + 5, start_y + 4))


def draw_inventory(screen, world):
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 190))
    screen.blit(overlay, (0, 0))

    font = pygame.font.SysFont("consolas", 27, bold=True)
    small = pygame.font.SysFont("consolas", 16, bold=True)

    panel = pygame.Rect(0, 0, 650, 550)
    panel.center = screen.get_rect().center

    pygame.draw.rect(screen, (18, 31, 27), panel)
    pygame.draw.rect(screen, (125, 145, 95), panel, 4)

    title = font.render("INVENTORY", True, (230, 210, 150))
    screen.blit(title, (panel.x + 25, panel.y + 20))

    pygame.draw.line(
        screen, (125, 145, 95),
        (panel.x + 20, panel.y + 65),
        (panel.right - 20, panel.y + 65), 3
    )

    # Сетка 5 на 5
    for i in range(25):
        col = i % 5
        row = i // 5

        x = panel.x + 28 + col * 120
        y = panel.y + 90 + row * 78

        rect = pygame.Rect(x, y, 105, 65)

        pygame.draw.rect(screen, (32, 48, 39), rect)
        pygame.draw.rect(screen, (95, 115, 80), rect, 2)

        item = world.inventory[i]

        if item:
            name = small.render(
                item["name"][:11], True, (240, 230, 195)
            )
            count = small.render(
                "x" + str(item["count"]), True, (190, 205, 150)
            )

            screen.blit(name, (x + 7, y + 13))
            screen.blit(count, (x + 7, y + 39))

        number = small.render(str(i + 1), True, (130, 145, 120))
        screen.blit(number, (x + 88, y + 3))

    hint = small.render(
        "TAB / I - CLOSE INVENTORY",
        True, (205, 205, 175)
    )
    screen.blit(hint, (panel.x + 25, panel.bottom - 35))

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

def _run_game():
    pygame.init()

    screen = pygame.display.get_surface()

    if screen is None:
        screen = pygame.display.set_mode(
            (1600, 900),
            pygame.SCALED | pygame.RESIZABLE
        )

    pygame.display.set_caption("Quiet Hunger — Survival")

    world = IslandWorld(screen)

    running = True
    inventory_open = False
    dead = False

    while running:
        dt = min(world.clock.tick(FPS) / 1000, 0.05)

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if dead:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    new_game_button = pygame.Rect(600, 440, 400, 70)
                    menu_button = pygame.Rect(600, 540, 400, 70)

                    if new_game_button.collidepoint(event.pos):
                        world = IslandWorld(screen)
                        inventory_open = False
                        dead = False

                    elif menu_button.collidepoint(event.pos):
                        running = False

                continue

            if event.type == pygame.KEYDOWN:

                if event.key in (pygame.K_TAB, pygame.K_i):
                    inventory_open = not inventory_open

                elif event.key == pygame.K_ESCAPE:
                    if inventory_open:
                        inventory_open = False
                    else:
                        running = False

                elif not inventory_open:
                    if pygame.K_1 <= event.key <= pygame.K_8:
                        world.selected_slot = event.key - pygame.K_1
                    elif event.key == pygame.K_e:
                        world.interact()
                    elif event.key == pygame.K_f:
                        world.use_selected()

        if not dead:

            if not inventory_open:
                world.update(dt)

            if world.health <= 0:
                world.health = 0
                dead = True

        world.draw()
        draw_hud(screen, world)

        if inventory_open and not dead:
            draw_inventory(screen, world)

        if dead:
            draw_death_screen(screen)

        pygame.display.flip()

    pygame.display.set_caption("Quiet Hunger")


def _show_error(text):
    """Показывает ошибку на экране вместо того, чтобы молча закрыться."""
    screen = pygame.display.get_surface()
    if screen is None:
        return
    font = pygame.font.SysFont("consolas", 18)
    big = pygame.font.SysFont("arial", 34, bold=True)
    lines = []
    for raw in text.strip().splitlines()[-16:]:
        while len(raw) > 130:
            lines.append(raw[:130])
            raw = "    " + raw[130:]
        lines.append(raw)
    while True:
        screen.fill((20, 10, 12))
        screen.blit(big.render("Ошибка в игре (подробности в crash.log)", True, (240, 120, 100)), (40, 30))
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, (235, 225, 205)), (40, 100 + i * 26))
        screen.blit(font.render("Нажми любую клавишу, чтобы вернуться в меню", True, (150, 200, 150)),
                    (40, SCREEN_H - 50))
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                return


def run_game():
    try:
        _run_game()
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log"), "w", encoding="utf-8") as f:
                f.write(tb)
        except OSError:
            pass
        _show_error(tb)


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
