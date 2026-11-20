import json
import os

import pygame

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

volume = 0.6          # общая громкость музыки, 0.0 – 1.0
fullscreen = False    # полноэкранный режим


def load():
    """Читает настройки из settings.json (если файла нет — остаются значения по умолчанию)."""
    global volume, fullscreen
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        volume = max(0.0, min(1.0, float(data.get("volume", volume))))
        fullscreen = bool(data.get("fullscreen", fullscreen))
    except (OSError, ValueError, TypeError):
        pass


def save():
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump({"volume": round(volume, 3), "fullscreen": fullscreen}, f)
    except OSError:
        pass


def set_volume(v):
    global volume
    volume = max(0.0, min(1.0, v))


def display_flags():
    """Флаги окна для pygame.display.set_mode с учётом полноэкранного режима."""
    flags = pygame.SCALED | pygame.RESIZABLE
    if fullscreen:
        flags |= pygame.FULLSCREEN
    return flags


def set_fullscreen(value):
    """Включает/выключает полноэкранный режим, не пересоздавая окно."""
    global fullscreen
    value = bool(value)
    if value == fullscreen:
        return
    fullscreen = value
    try:
        pygame.display.toggle_fullscreen()
    except pygame.error:
        pass
    save()


def toggle_fullscreen():
    set_fullscreen(not fullscreen)
