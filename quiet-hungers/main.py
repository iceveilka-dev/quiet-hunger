from island import run_game
from audio import play_music
import math
import os
import random
import sys
from island import run_game

import pygame

W, H = 1600, 900
SCALE = 4                      # эффекты рисуются в низком разрешении и растягиваются -> пиксель-арт стиль
LW, LH = W // SCALE, H // SCALE
BASE = os.path.dirname(os.path.abspath(__file__))
BG_FILE = "background.jpg"     # имя файла с картинкой (1600x900)

# Кнопки меню (названия и области на картинке)
BUTTONS = [
    ("PLAY",       pygame.Rect(98, 404, 304, 62)),
    ("SETTINGS",   pygame.Rect(116, 493, 268, 46)),
    ("STATISTICS", pygame.Rect(116, 563, 268, 46)),
    ("ABOUT",      pygame.Rect(116, 629, 266, 46)),
    ("QUIT",       pygame.Rect(116, 696, 262, 44)),
]
MENU_ZONE = pygame.Rect(80, 385, 340, 375)   # сюда блики на воде не попадают

# Зоны воды, где появляются блики
WATER_ZONES = [
    pygame.Rect(0, 780, 1600, 120),
    pygame.Rect(0, 610, 85, 165),
    pygame.Rect(420, 610, 150, 70),
]

SUN_POS = (793, 120)
FIRE_POS = (1125, 685)

# Блёстки на вывеске: x, y, сдвиг по времени, период (сек)
SPARKLES = [
    (190, 135, 0.0, 3.4), (335, 105, 1.3, 4.1), (445, 122, 2.2, 3.7),
    (300, 238, 0.8, 4.6), (560, 215, 2.9, 3.9), (210, 300, 1.7, 5.0),
]


def make_glow(radius, color, max_alpha):
    """Мягкое круглое свечение (плавно затухает к краям)."""
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        a = int(max_alpha * (1 - r / radius) ** 2)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf


class Smoke:
    """Дым от костра."""
    def __init__(self):
        self.x = FIRE_POS[0] - 10 + random.uniform(-6, 6)
        self.y = 600
        self.vx = random.uniform(-4, 8)
        self.vy = random.uniform(-34, -24)
        self.life = random.uniform(3.0, 4.5)
        self.age = 0.0
        self.seed = random.uniform(0, 6.28)

    def update(self, dt):
        self.age += dt
        self.y += self.vy * dt
        self.x += (self.vx + math.sin(self.age * 1.5 + self.seed) * 7) * dt
        return self.age < self.life

    def draw(self, layer):
        k = self.age / self.life
        radius = int(2 + k * 5)
        alpha = int(120 * (1 - k) ** 1.5)
        pygame.draw.circle(layer, (225, 225, 230, alpha),
                           (int(self.x / SCALE), int(self.y / SCALE)), radius)


class Ember:
    """Искра, летящая вверх от костра."""
    def __init__(self):
        self.x = FIRE_POS[0] + random.uniform(-12, 12)
        self.y = FIRE_POS[1] - 25
        self.vx = random.uniform(-12, 12)
        self.vy = random.uniform(-90, -40)
        self.life = random.uniform(0.8, 1.6)
        self.age = 0.0
        self.seed = random.uniform(0, 6.28)

    def update(self, dt):
        self.age += dt
        self.vy += 30 * dt
        self.y += self.vy * dt
        self.x += (self.vx + math.sin(self.age * 8 + self.seed) * 14) * dt
        return self.age < self.life

    def draw(self, layer):
        k = self.age / self.life
        color = (255, int(220 - 110 * k), int(90 - 60 * k), int(255 * (1 - k)))
        layer.set_at((int(self.x / SCALE), int(self.y / SCALE)), color)


class Mist:
    """Брызги и туман у подножия водопада."""
    def __init__(self):
        self.x = random.uniform(1190, 1260)
        self.y = 578 + random.uniform(-5, 5)
        self.vx = random.uniform(5, 20)
        self.vy = random.uniform(-25, -10)
        self.life = random.uniform(1.5, 2.5)
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.age < self.life

    def draw(self, layer):
        k = self.age / self.life
        pygame.draw.circle(layer, (240, 250, 255, int(90 * (1 - k))),
                           (int(self.x / SCALE), int(self.y / SCALE)), int(2 + k * 3))


class Streak:
    """Светлая полоска, стекающая по водопаду."""
    def __init__(self):
        self.x = random.uniform(1190, 1225)
        self.y = 250.0
        self.vy = random.uniform(160, 230)

    def update(self, dt):
        self.y += self.vy * dt
        return self.y < 570

    def draw(self, layer):
        px, py = int(self.x / SCALE), int(self.y / SCALE)
        pygame.draw.rect(layer, (235, 248, 255, 150), (px, py, 1, 3))


class Glint:
    """Блик на воде."""
    def __init__(self):
        while True:
            zone = random.choice(WATER_ZONES)
            self.x = random.uniform(zone.left, zone.right)
            self.y = random.uniform(zone.top, zone.bottom)
            if not MENU_ZONE.collidepoint(self.x, self.y):
                break
        self.life = random.uniform(0.7, 1.3)
        self.age = random.uniform(0, self.life)

    def update(self, dt):
        self.age += dt
        if self.age >= self.life:
            self.__init__()
            self.age = 0.0

    def draw(self, layer):
        k = math.sin(math.pi * self.age / self.life)
        px, py = int(self.x / SCALE), int(self.y / SCALE)
        layer.set_at((px, py), (255, 255, 255, int(255 * k)))
        if k > 0.6:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                layer.set_at((px + dx, py + dy), (255, 255, 255, 120))


class Gull:
    """Чайка, пролетающая над островом."""
    X_MIN, X_MAX = 660, 1560

    def __init__(self):
        self.reset(first=True)

    def reset(self, first=False):
        self.x = random.uniform(self.X_MIN, self.X_MAX) if first else self.X_MIN
        self.y0 = random.uniform(40, 170)
        self.speed = random.uniform(35, 65)
        self.phase = random.uniform(0, 6.28)
        self.flap = random.uniform(5, 7)

    def update(self, dt):
        self.x += self.speed * dt
        if self.x > self.X_MAX:
            self.reset()

    def draw(self, layer, t):
        y = self.y0 + math.sin(t * 0.8 + self.phase) * 10
        fade = max(0.0, min(1.0, (self.x - self.X_MIN) / 60, (self.X_MAX - self.x) / 60))
        color = (250, 250, 255, int(255 * fade))
        px, py = int(self.x / SCALE), int(y / SCALE)
        dy = -1 if math.sin(t * self.flap + self.phase) > 0 else 1
        for dx, oy in ((-2, dy), (-1, 0), (0, 0), (1, 0), (2, dy)):
            layer.set_at((px + dx, py + oy), color)


def draw_sparkles(layer, t):
    """Мигающие блёстки-звёздочки на вывеске."""
    for x, y, phase, period in SPARKLES:
        p = ((t + phase) % period) / period
        if p > 0.18:
            continue
        s = math.sin(math.pi * p / 0.18)
        arm = int(round(3 * s))
        px, py = int(x / SCALE), int(y / SCALE)
        layer.set_at((px, py), (255, 255, 235, 255))
        for i in range(1, arm + 1):
            a = int(255 * (1 - i / (arm + 1)))
            for dx, dy in ((i, 0), (-i, 0), (0, i), (0, -i)):
                layer.set_at((px + dx, py + dy), (255, 255, 235, a))


def activate(name):
    if name == "QUIT":
        pygame.quit()
        sys.exit()

    elif name == "PLAY":
        print("Starting a new game...")
        play_music("game.ogg")
        run_game()
        play_music("menu.ogg", volume=0.35)

    else:
        print(f"Нажата кнопка: {name}")


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("Quiet Hunger")
    clock = pygame.time.Clock()
    
    play_music("menu.ogg", volume=0.35)

    bg = pygame.image.load(os.path.join(BASE, BG_FILE)).convert()
    if bg.get_size() != (W, H):
        bg = pygame.transform.smoothscale(bg, (W, H))

    layer = pygame.Surface((LW, LH), pygame.SRCALPHA)       # слой эффектов (низкое разрешение)
    big = pygame.Surface((W, H), pygame.SRCALPHA)           # он же, растянутый до экрана
    fade = pygame.Surface((W, H))
    fade.fill((0, 0, 0))

    sun_glow = make_glow(190, (255, 240, 170), 110)
    fire_glow = make_glow(150, (255, 150, 50), 140)

    smoke, embers, mist, streaks = [], [], [], []
    timers = {"smoke": 0.0, "ember": 0.0, "mist": 0.0, "streak": 0.0}
    glints = [Glint() for _ in range(45)]
    gulls = [Gull() for _ in range(3)]

    selected, press_t, hand = 0, 0.0, False
    t = 0.0

    while True:
        dt = min(clock.tick(60) / 1000, 0.05)
        t += dt
        press_t = max(0.0, press_t - dt)

        # --- события ---
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(BUTTONS)
                elif e.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(BUTTONS)
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    press_t = 0.18
                    activate(BUTTONS[selected][0])
            elif e.type == pygame.MOUSEMOTION:
                for i, (_, rect) in enumerate(BUTTONS):
                    if rect.collidepoint(e.pos):
                        selected = i
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, (name, rect) in enumerate(BUTTONS):
                    if rect.collidepoint(e.pos):
                        selected = i
                        press_t = 0.18
                        activate(name)

        # курсор-«рука» над кнопками
        over = any(r.collidepoint(pygame.mouse.get_pos()) for _, r in BUTTONS)
        if over != hand:
            hand = over
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hand else pygame.SYSTEM_CURSOR_ARROW)
            except Exception:
                pass

        # --- обновление ---
        for key, every, cls, lst in (("smoke", 0.14, Smoke, smoke), ("ember", 0.07, Ember, embers),
                                     ("mist", 0.10, Mist, mist), ("streak", 0.05, Streak, streaks)):
            timers[key] += dt
            if timers[key] > every:
                timers[key] = 0.0
                lst.append(cls())
        smoke = [p for p in smoke if p.update(dt)]
        embers = [p for p in embers if p.update(dt)]
        mist = [p for p in mist if p.update(dt)]
        streaks = [p for p in streaks if p.update(dt)]
        for g in glints:
            g.update(dt)
        for g in gulls:
            g.update(dt)

        # --- рисование ---
        screen.blit(bg, (0, 0))

        # свечение солнца (медленно «дышит»)
        sun_glow.set_alpha(int(255 * (0.8 + 0.2 * math.sin(t * 0.9))))
        screen.blit(sun_glow, (SUN_POS[0] - 190, SUN_POS[1] - 190))

        # мерцание костра
        k = 0.7 + 0.15 * math.sin(t * 13) + 0.10 * math.sin(t * 23 + 1) + random.uniform(-0.05, 0.05)
        fire_glow.set_alpha(int(255 * max(0.0, min(1.0, k))))
        screen.blit(fire_glow, (FIRE_POS[0] - 150, FIRE_POS[1] - 150))

        # эффекты в пиксельном разрешении
        layer.fill((0, 0, 0, 0))
        for g in glints:
            g.draw(layer)
        for p in streaks:
            p.draw(layer)
        for p in mist:
            p.draw(layer)
        for p in smoke:
            p.draw(layer)
        for p in embers:
            p.draw(layer)
        for g in gulls:
            g.draw(layer, t)
        draw_sparkles(layer, t)
        pygame.transform.scale(layer, (W, H), big)
        screen.blit(big, (0, 0))

        # подсветка выбранной кнопки
        rect = BUTTONS[selected][1]
        v = 18 + 12 * math.sin(t * 4) + 60 * (press_t / 0.18)
        v = int(max(0, min(255, v)))
        glow = pygame.Surface(rect.size)
        glow.fill((v, v, v))
        screen.blit(glow, rect.topleft, special_flags=pygame.BLEND_RGB_ADD)

        # плавное появление в начале
        if t < 1.2:
            fade.set_alpha(int(255 * (1 - t / 1.2)))
            screen.blit(fade, (0, 0))

        pygame.display.flip()

if __name__ == "__main__":
    main()