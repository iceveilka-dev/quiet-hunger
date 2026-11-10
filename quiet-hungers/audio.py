import os
import pygame

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_current = None


def play_music(name, volume=0.5, fade_ms=1000):
    """Запускает трек из assets/ по кругу. Если он уже играет, ничего не делает."""
    global _current
    if name == _current:
        return
    path = os.path.join(ASSET_DIR, name)
    print("Ищу музыку:", path, "| существует:", os.path.exists(path))   # <-- новая строка
    if not os.path.exists(path):
        print(f"Музыка не найдена: {path}")
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(-1, fade_ms=fade_ms)
        _current = name
    except pygame.error as e:
        print(f"Не удалось запустить музыку: {e}")