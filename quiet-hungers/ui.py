import pygame

import audio
import settings


def make_fonts():
    return {
        "title": pygame.font.SysFont("consolas", 40, bold=True),
        "button": pygame.font.SysFont("consolas", 26, bold=True),
        "text": pygame.font.SysFont("consolas", 22, bold=True),
        "small": pygame.font.SysFont("consolas", 18, bold=True),
    }


def draw_text(screen, font, text, color, **pos):
    img = font.render(text, True, color)
    screen.blit(img, img.get_rect(**pos))


def draw_button(screen, font, rect, label, hover, base=(40, 62, 48), enabled=True):
    if not enabled:
        base, hover = (36, 40, 38), False
    color = tuple(min(255, c + 25) for c in base) if hover else base
    pygame.draw.rect(screen, color, rect, border_radius=8)
    pygame.draw.rect(screen, (150, 170, 115) if enabled else (80, 85, 75), rect, 2, border_radius=8)
    draw_text(screen, font, label, (240, 232, 195) if enabled else (110, 115, 105), center=rect.center)


def draw_frame(screen, rect, title, fonts):
    """Тёмная панель с зелёной рамкой и заголовком."""
    pygame.draw.rect(screen, (18, 31, 27), rect, border_radius=10)
    pygame.draw.rect(screen, (125, 145, 95), rect, 4, border_radius=10)
    draw_text(screen, fonts["title"], title, (230, 210, 150), midtop=(rect.centerx, rect.y + 24))
    pygame.draw.line(screen, (125, 145, 95), (rect.x + 30, rect.y + 82), (rect.right - 30, rect.y + 82), 3)


class SettingsPanel:
    """Окно настроек: громкость музыки и полноэкранный режим (используется в меню и в игре)."""

    def __init__(self, center):
        self.rect = pygame.Rect(0, 0, 680, 430)
        self.rect.center = center
        r = self.rect
        self.slider = pygame.Rect(r.x + 70, r.y + 175, 540, 12)
        self.slider_hit = self.slider.inflate(30, 44)
        self.fs_btn = pygame.Rect(r.right - 230, r.y + 245, 160, 46)
        self.back_btn = pygame.Rect(0, 0, 220, 52)
        self.back_btn.midbottom = (r.centerx, r.bottom - 28)
        self.dragging = False

    def _volume_from_mouse(self, x):
        settings.set_volume((x - self.slider.x) / self.slider.width)
        audio.refresh_volume()

    def hit_any(self, pos):
        return (self.slider_hit.collidepoint(pos) or self.fs_btn.collidepoint(pos)
                or self.back_btn.collidepoint(pos))

    def handle(self, e):
        """Обрабатывает событие. Возвращает True, когда окно нужно закрыть."""
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return True
            if e.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                step = 0.05 if e.key in (pygame.K_RIGHT, pygame.K_d) else -0.05
                settings.set_volume(round(settings.volume + step, 2))
                audio.refresh_volume()
                settings.save()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.back_btn.collidepoint(e.pos):
                return True
            if self.slider_hit.collidepoint(e.pos):
                self.dragging = True
                self._volume_from_mouse(e.pos[0])
            elif self.fs_btn.collidepoint(e.pos):
                settings.toggle_fullscreen()
        elif e.type == pygame.MOUSEMOTION and self.dragging:
            self._volume_from_mouse(e.pos[0])
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.dragging:
            self.dragging = False
            settings.save()
        return False

    def draw(self, screen, dim, fonts):
        mouse = pygame.mouse.get_pos()
        screen.blit(dim, (0, 0))
        draw_frame(screen, self.rect, "SETTINGS", fonts)
        s = self.slider

        draw_text(screen, fonts["text"], "MUSIC VOLUME", (225, 225, 200), topleft=(s.x, s.y - 52))
        draw_text(screen, fonts["text"], "%d%%" % round(settings.volume * 100), (230, 210, 150),
                  topright=(s.right, s.y - 52))
        pygame.draw.rect(screen, (35, 43, 39), s, border_radius=6)
        fill = pygame.Rect(s.x, s.y, int(s.width * settings.volume), s.height)
        if fill.width > 0:
            pygame.draw.rect(screen, (80, 180, 85), fill, border_radius=6)
        pygame.draw.rect(screen, (160, 165, 135), s, 2, border_radius=6)
        knob = (s.x + int(s.width * settings.volume), s.centery)
        pygame.draw.circle(screen, (240, 232, 195) if self.slider_hit.collidepoint(mouse) else (210, 200, 160), knob, 15)
        pygame.draw.circle(screen, (90, 105, 80), knob, 15, 3)

        draw_text(screen, fonts["text"], "FULLSCREEN  (F11)", (225, 225, 200), midleft=(s.x, self.fs_btn.centery))
        draw_button(screen, fonts["text"], self.fs_btn, "ON" if settings.fullscreen else "OFF",
                    self.fs_btn.collidepoint(mouse),
                    base=(60, 110, 65) if settings.fullscreen else (95, 60, 55))
        draw_button(screen, fonts["button"], self.back_btn, "BACK", self.back_btn.collidepoint(mouse))
