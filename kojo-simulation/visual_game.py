"""
Visualizador grafico para Kojo's Restaurant.

Instalacion:
    pip install pygame

Ejecucion:
    py -m visual_game
    # o
    python visual_game.py

Controles:
    SPACE   iniciar / pausar
    RIGHT   avanzar un evento discreto
    R       reiniciar replica
    1       escenario base: 2 empleados
    2       escenario con empleado extra en horas pico
    C       cambiar configuracion experimental, si existe config.EXPERIMENT_CONFIGS
    S       cambiar semilla y reiniciar
    + / -   cambiar velocidad
    TAB     mostrar/ocultar panel tecnico
    ESC     salir

Assets opcionales soportados:
    assets/backgrounds/kojo_overcooked.png
    assets/characters/chef_idle.png
    assets/characters/chef_busy.png
    assets/characters/chef_inactive.png
    assets/characters/customer_sandwich.png
    assets/characters/customer_sushi.png
    assets/food/sandwich.png
    assets/food/sushi.png
    assets/food/bread.png
    assets/food/tomato.png
    assets/food/rice.png
    assets/food/fish.png
    assets/food/nori.png
"""

from __future__ import annotations

import heapq
import inspect
import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import pygame

# Entrada al proyecto existente. No se copia ni reimplementa el simulador.

try:
    import config
    from src.events import ARRIVAL, SERVICE_END, PEAK_START, PEAK_END, CLOSE
    from src.logger import setup_logger
    from src.simulator import KojoSimulator
    PROJECT_AVAILABLE = True
except Exception: 
    PROJECT_AVAILABLE = False

    ARRIVAL = "arrival"
    SERVICE_END = "service_end"
    PEAK_START = "peak_start"
    PEAK_END = "peak_end"
    CLOSE = "close"

    class _Config:
        LOG_FILE = "logs/simulation.log"
        DEFAULT_SEED = 1
        DAY_CLOSE = 660
        WAIT_THRESHOLD = 5.0
        EXPERIMENT_CONFIGS = [
            {"config_id": "demo", "mean_interarrival_normal": 6.0, "mean_interarrival_peak": 2.5}
        ]

    config = _Config()

    def setup_logger(enabled=True, level="INFO", log_file="logs/simulation.log"):
        import logging
        logger = logging.getLogger("kojo-demo")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        logger.disabled = True
        return logger

    @dataclass
    class _DemoClient:
        id: int
        arrival_time: float
        product: str
        service_time: float
        service_start_time: Optional[float] = None
        service_end_time: Optional[float] = None
        employee_id: Optional[int] = None

    @dataclass
    class _DemoEmployee:
        id: int
        is_extra: bool = False
        active: bool = True
        can_take_new_clients: bool = True
        busy: bool = False
        current_client: Optional[_DemoClient] = None
        busy_time: float = 0.0
        last_service_start: Optional[float] = None

        def is_available(self):
            return self.active and self.can_take_new_clients and not self.busy

    @dataclass(order=True)
    class _DemoEvent:
        time: float
        priority: int
        sequence: int
        event_type: str = field(compare=False)
        payload: Any = field(default=None, compare=False)

    class KojoSimulator:

        def __init__(self, seed=1, use_extra_employee=False, logger=None, experiment_config=None):
            self.seed = seed
            self.rng = random.Random(seed)
            self.use_extra_employee = use_extra_employee
            self.logger = logger
            self.clock = 0.0
            self.sequence = 0
            self.event_queue = []
            self.waiting_queue = []
            self.total_customers = 0
            self.completed_customers = 0
            self.delayed_customers = 0
            self.total_waiting_time = 0.0
            self.max_waiting_time = 0.0
            self.generated_customers = 0
            self.employees = [_DemoEmployee(1), _DemoEmployee(2)]
            if use_extra_employee:
                self.employees.append(_DemoEmployee(3, is_extra=True, active=False, can_take_new_clients=False))

        def schedule_event(self, time, event_type, payload=None):
            priorities = {SERVICE_END: 1, PEAK_START: 2, PEAK_END: 3, ARRIVAL: 4, CLOSE: 5}
            heapq.heappush(self.event_queue, _DemoEvent(time, priorities[event_type], self.sequence, event_type, payload))
            self.sequence += 1

        def schedule_initial_events(self):
            cid = 1
            for start, end, mean in [(0, 90, 7.0), (90, 210, 2.9), (210, 420, 6.0), (420, 540, 2.6), (540, 660, 6.5)]:
                t = start
                while True:
                    u = max(1e-9, self.rng.random())
                    t += -mean * math.log(u)
                    if t >= end:
                        break
                    product = "sandwich" if self.rng.random() < 0.55 else "sushi"
                    service = self.rng.uniform(3.0, 5.0) if product == "sandwich" else self.rng.uniform(5.0, 8.0)
                    self.schedule_event(t, ARRIVAL, _DemoClient(cid, t, product, service))
                    cid += 1
            self.generated_customers = cid - 1
            if self.use_extra_employee:
                for a, b in [(90, 210), (420, 540)]:
                    self.schedule_event(a, PEAK_START)
                    self.schedule_event(b, PEAK_END)
            self.schedule_event(660, CLOSE)

        def advance_clock(self, new_time):
            self.clock = new_time

        def _available(self):
            for e in self.employees:
                if e.is_available():
                    return e
            return None

        def _try_start(self):
            while self.waiting_queue:
                e = self._available()
                if e is None:
                    break
                c = self.waiting_queue.pop(0)
                c.service_start_time = self.clock
                c.employee_id = e.id
                wait = self.clock - c.arrival_time
                self.total_waiting_time += wait
                self.max_waiting_time = max(self.max_waiting_time, wait)
                if wait > getattr(config, "WAIT_THRESHOLD", 5.0):
                    self.delayed_customers += 1
                e.busy = True
                e.current_client = c
                e.last_service_start = self.clock
                self.schedule_event(self.clock + c.service_time, SERVICE_END, e)

        def handle_arrival(self, client):
            self.total_customers += 1
            self.waiting_queue.append(client)
            self._try_start()

        def handle_service_end(self, employee):
            c = employee.current_client
            if c:
                c.service_end_time = self.clock
            if employee.last_service_start is not None:
                employee.busy_time += self.clock - employee.last_service_start
            employee.busy = False
            employee.current_client = None
            employee.last_service_start = None
            self.completed_customers += 1
            if employee.is_extra and not employee.can_take_new_clients:
                employee.active = False
            self._try_start()

        def handle_peak_start(self):
            for e in self.employees:
                if e.is_extra:
                    e.active = True
                    e.can_take_new_clients = True
            self._try_start()

        def handle_peak_end(self):
            for e in self.employees:
                if e.is_extra:
                    e.can_take_new_clients = False
                    if not e.busy:
                        e.active = False

        def handle_close(self):
            pass

        def validate_end_state(self):
            pass

        def build_results(self):
            avg = self.total_waiting_time / self.total_customers if self.total_customers else 0.0
            pct = 100 * self.delayed_customers / self.total_customers if self.total_customers else 0.0
            return {
                "total_customers": self.total_customers,
                "completed_customers": self.completed_customers,
                "delayed_customers": self.delayed_customers,
                "delayed_percentage": pct,
                "average_wait": avg,
                "max_wait": self.max_waiting_time,
            }


# Configuracion visual

ASSETS_DIR = Path("assets")
LOGICAL_WIDTH = 1600
LOGICAL_HEIGHT = 900
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
FPS = 60

SCENARIOS = {
    "two_employees": False,
    "extra_employee_peak": True,
}

PRODUCT_STYLES = {
    "sandwich": {
        "name": "Sandwich",
        "short": "S",
        "main": (235, 145, 56),
        "dark": (151, 82, 39),
        "light": (255, 223, 159),
        "ticket": (255, 242, 222),
        "ingredients": ["bread", "tomato", "bread"],
    },
    "sushi": {
        "name": "Sushi",
        "short": "SU",
        "main": (82, 173, 204),
        "dark": (39, 92, 121),
        "light": (225, 249, 255),
        "ticket": (228, 248, 255),
        "ingredients": ["rice", "fish", "nori"],
    },
}

COLORS = {
    "road": (56, 62, 65),
    "road_dark": (39, 44, 48),
    "sidewalk": (174, 172, 159),
    "sidewalk_line": (126, 124, 115),
    "crosswalk": (244, 240, 213),
    "yellow_line": (236, 193, 68),
    "counter": (214, 148, 70),
    "counter_top": (250, 197, 104),
    "counter_side": (151, 86, 47),
    "counter_dark": (105, 59, 39),
    "wood": (126, 76, 47),
    "panel": (255, 249, 231),
    "panel_line": (117, 77, 50),
    "red": (213, 67, 57),
    "green": (75, 166, 88),
    "blue": (82, 143, 199),
    "white": (255, 255, 255),
    "black": (28, 25, 23),
}


# Utilidades

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (int(lerp(a[0], b[0], t)), int(lerp(a[1], b[1], t)), int(lerp(a[2], b[2], t)))


def draw_text(surface: pygame.Surface, font: pygame.font.Font, text: str, pos, color=(30, 30, 30), anchor="topleft"):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(img, rect)
    return rect


def rr(surface: pygame.Surface, color, rect, radius=14, width=0, border=None):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)
    if border is not None and width == 0:
        pygame.draw.rect(surface, border, rect, 2, border_radius=radius)


def alpha_rect(surface: pygame.Surface, color, rect, radius=0):
    rect = pygame.Rect(rect)
    tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(tmp, color, tmp.get_rect(), border_radius=radius)
    surface.blit(tmp, rect.topleft)


def shadow(surface: pygame.Surface, center, w: int, h: int, alpha=55):
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(tmp, (0, 0, 0, alpha), (0, 0, w, h))
    surface.blit(tmp, (int(center[0] - w / 2), int(center[1] - h / 2)))


def saw_noise(x: float, period: float) -> float:
    return (x % period) / period


# Assets

class AssetManager:
    def __init__(self):
        self.cache: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}

    def _has_real_alpha(self, surface: pygame.Surface) -> bool:
        """Verifica si la superficie tiene algun pixel con transparencia real."""
        if not (surface.get_flags() & pygame.SRCALPHA) and surface.get_bitsize() < 32:
            return False
        w, h = surface.get_size()
        for x in [0, w // 2, w - 1]:
            for y in [0, h // 2, h - 1]:
                if surface.get_at((x, y))[3] < 255:
                    return True
        return False

    def _is_fake_transparency(self, surface: pygame.Surface) -> bool:
        """Detecta si la imagen tiene el patron de cuadritos (fake transparency) en las esquinas."""
        if surface.get_width() < 10 or surface.get_height() < 10:
            return False
        c1 = surface.get_at((0, 0))[:3]
        c2 = surface.get_at((5, 5))[:3]
        checker_colors = {(255, 255, 255), (204, 204, 204), (192, 192, 192), (247, 247, 247)}
        return c1 in checker_colors and c2 in checker_colors and c1 != c2

    def load(self, key: str, candidates: list[str], size: tuple[int, int], generator) -> pygame.Surface:
        cache_key = (key, size)
        if cache_key in self.cache:
            return self.cache[cache_key]
        image = None
        for rel in candidates:
            path = ASSETS_DIR / rel
            if path.exists() and path.is_file():
                try:
                    raw_image = pygame.image.load(str(path))
                    
                    # Caso 1: Imagen con transparencia real (PNG con alpha)
                    if self._has_real_alpha(raw_image):
                        image = raw_image.convert_alpha()
                    else:
                        # Caso 2: Fake transparency (checkerboard) - Avisar al log
                        if self._is_fake_transparency(raw_image):
                            print(f"AVISO: {rel} parece tener 'fake transparency' (fondo de cuadritos).")
                            image = raw_image.convert_alpha()
                        else:
                            # Caso 3: Imagen opaca con fondo solido (blanco/negro) - Usar colorkey
                            bg_color = raw_image.get_at((0, 0))
                            # Solo si es muy claro o muy oscuro lo tratamos como fondo a remover
                            if sum(bg_color[:3]) > 700 or sum(bg_color[:3]) < 50:
                                raw_image.set_colorkey(bg_color)
                                image = raw_image.convert_alpha()
                            else:
                                image = raw_image.convert_alpha()
                    
                    image = pygame.transform.smoothscale(image, size)
                    break
                except pygame.error:
                    image = None
        if image is None:
            image = generator(size)
        self.cache[cache_key] = image
        return image

    def background(self) -> Optional[pygame.Surface]:
        candidates = [
            "backgrounds/kojo_overcooked.png",
            "backgrounds/kojos_restaurant.png",
            "backgrounds/kojo_restaurant.png",
            "background.png",
        ]
        for rel in candidates:
            path = ASSETS_DIR / rel
            if path.exists() and path.is_file():
                try:
                    img = pygame.image.load(str(path)).convert()
                    return pygame.transform.smoothscale(img, (LOGICAL_WIDTH, LOGICAL_HEIGHT))
                except pygame.error:
                    return None
        return None

    def food(self, name: str, size=(48, 40)) -> pygame.Surface:
        name = name.lower()
        return self.load(
            f"food_{name}",
            [f"food/{name}.png", f"ingredients/{name}.png", f"{name}.png"],
            size,
            lambda s: generate_food_sprite(name, s),
        )

    def chef(self, state="idle", size=(88, 110)) -> pygame.Surface:
        state = state if state in {"idle", "busy", "inactive"} else "idle"
        return self.load(
            f"chef_{state}",
            [f"characters/chef_{state}.png", f"chef_{state}.png"],
            size,
            lambda s: generate_chef_sprite(state, s),
        )

    def customer(self, product="sandwich", angry=False, size=(72, 100)) -> pygame.Surface:
        product = product if product in PRODUCT_STYLES else "sandwich"
        key = f"customer_{product}_{'angry' if angry else 'ok'}"
        candidates = [
            f"characters/customer_{product}.png",
            "characters/customer_angry.png" if angry else f"customer_{product}.png",
        ]
        return self.load(key, candidates, size, lambda s: generate_customer_sprite(product, angry, s))


def generate_food_sprite(name: str, size: tuple[int, int]) -> pygame.Surface:
    w, h = size
    s = pygame.Surface(size, pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    name = name.lower()

    if name in {"sandwich", "bread"}:
        pygame.draw.ellipse(s, (236, 181, 93), (3, 4, w - 6, h * 0.42))
        pygame.draw.rect(s, (95, 164, 76), (5, int(h * 0.42), w - 10, max(3, h // 10)), border_radius=3)
        pygame.draw.rect(s, (219, 75, 57), (7, int(h * 0.55), w - 14, max(3, h // 10)), border_radius=3)
        pygame.draw.ellipse(s, (171, 99, 51), (3, int(h * 0.59), w - 6, h * 0.33))
        pygame.draw.arc(s, (111, 67, 36), (3, 4, w - 6, h - 6), 0, 2 * math.pi, 2)
        for px in [0.33, 0.52, 0.70]:
            pygame.draw.circle(s, (255, 237, 164), (int(w * px), int(h * 0.22)), max(1, w // 30))
    elif name == "tomato":
        pygame.draw.circle(s, (222, 49, 42), (cx, cy), min(w, h) // 3)
        pygame.draw.circle(s, (255, 92, 80), (cx - w // 10, cy - h // 12), min(w, h) // 8)
        pygame.draw.polygon(s, (43, 149, 56), [(cx, cy - h // 3), (cx - 8, cy - h // 2), (cx + 8, cy - h // 2)])
    elif name in {"sushi", "rice", "fish", "nori"}:
        if name == "rice":
            pygame.draw.ellipse(s, (255, 255, 250), (5, 6, w - 10, h - 12))
            pygame.draw.ellipse(s, (205, 211, 207), (5, 6, w - 10, h - 12), 2)
        elif name == "fish":
            pygame.draw.ellipse(s, (236, 91, 100), (4, int(h * 0.25), w - 8, int(h * 0.48)))
            pygame.draw.polygon(s, (236, 91, 100), [(w - 8, cy), (w - 1, cy - 8), (w - 1, cy + 8)])
            pygame.draw.arc(s, (255, 177, 173), (8, int(h * 0.30), w - 16, int(h * 0.35)), 0.2, 2.9, 2)
        elif name == "nori":
            rr(s, (42, 54, 48), (6, 6, w - 12, h - 12), radius=5, border=(17, 25, 22))
            for x in range(10, w - 8, max(7, w // 6)):
                pygame.draw.line(s, (69, 92, 78), (x, 8), (x, h - 8), 1)
        else:
            for dx in [-w * 0.17, w * 0.17]:
                pygame.draw.circle(s, (32, 36, 38), (int(cx + dx), cy), min(w, h) // 4)
                pygame.draw.circle(s, (255, 255, 252), (int(cx + dx), cy), min(w, h) // 5)
                pygame.draw.circle(s, (231, 74, 91), (int(cx + dx), cy), min(w, h) // 10)
                pygame.draw.circle(s, (82, 166, 85), (int(cx + dx + 2), int(cy - 1)), min(w, h) // 16)
    else:
        pygame.draw.circle(s, (230, 180, 90), (cx, cy), min(w, h) // 3)
        pygame.draw.circle(s, (90, 60, 35), (cx, cy), min(w, h) // 3, 2)
    return s


def generate_chef_sprite(state: str, size: tuple[int, int]) -> pygame.Surface:
    w, h = size
    s = pygame.Surface(size, pygame.SRCALPHA)
    cx = w // 2
    foot = int(h * 0.88)
    coat = (237, 245, 244) if state != "inactive" else (170, 172, 173)
    apron = (84, 160, 208) if state == "idle" else (217, 82, 67) if state == "busy" else (130, 130, 130)
    skin = (226, 165, 111)

    pygame.draw.ellipse(s, (0, 0, 0, 45), (cx - 28, foot - 4, 56, 15))
    pygame.draw.line(s, (56, 64, 86), (cx - 10, int(h * 0.62)), (cx - 18, foot), 8)
    pygame.draw.line(s, (56, 64, 86), (cx + 10, int(h * 0.62)), (cx + 18, foot), 8)
    pygame.draw.ellipse(s, (32, 32, 34), (cx - 26, foot - 6, 19, 10))
    pygame.draw.ellipse(s, (32, 32, 34), (cx + 7, foot - 6, 19, 10))

    pygame.draw.line(s, skin, (cx - 24, int(h * 0.48)), (cx - 38, int(h * 0.62)), 8)
    pygame.draw.line(s, skin, (cx + 24, int(h * 0.48)), (cx + 38, int(h * 0.62)), 8)
    pygame.draw.circle(s, skin, (cx - 40, int(h * 0.63)), 5)
    pygame.draw.circle(s, skin, (cx + 40, int(h * 0.63)), 5)

    rr(s, coat, (cx - 26, int(h * 0.39), 52, 40), radius=14, border=(61, 62, 63))
    pygame.draw.polygon(s, apron, [(cx - 18, int(h * 0.47)), (cx + 18, int(h * 0.47)), (cx + 13, int(h * 0.75)), (cx - 13, int(h * 0.75))])
    pygame.draw.line(s, (85, 86, 88), (cx, int(h * 0.40)), (cx, int(h * 0.72)), 2)
    pygame.draw.circle(s, (80, 80, 80), (cx - 6, int(h * 0.50)), 2)
    pygame.draw.circle(s, (80, 80, 80), (cx + 6, int(h * 0.58)), 2)

    pygame.draw.circle(s, skin, (cx, int(h * 0.27)), 18)
    pygame.draw.arc(s, (67, 43, 30), (cx - 18, int(h * 0.16), 36, 28), math.pi, 2 * math.pi, 6)
    pygame.draw.circle(s, (45, 32, 24), (cx - 6, int(h * 0.28)), 2)
    pygame.draw.circle(s, (45, 32, 24), (cx + 6, int(h * 0.28)), 2)
    pygame.draw.arc(s, (116, 58, 39), (cx - 8, int(h * 0.32), 16, 9), 0.1, math.pi - 0.1, 2)

    pygame.draw.rect(s, (255, 255, 255), (cx - 26, int(h * 0.13), 52, 16), border_radius=6)
    for px, py, pr in [(cx - 17, 0.12, 12), (cx, 0.08, 16), (cx + 17, 0.12, 12)]:
        pygame.draw.circle(s, (255, 255, 255), (int(px), int(h * py)), pr)
    pygame.draw.rect(s, (78, 78, 78), (cx - 26, int(h * 0.13), 52, 16), 2, border_radius=6)

    if state == "busy":
        pygame.draw.line(s, (70, 70, 70), (cx + 36, int(h * 0.60)), (cx + 54, int(h * 0.49)), 4)
        pygame.draw.ellipse(s, (55, 55, 55), (cx + 47, int(h * 0.43), 22, 12), 2)
        pygame.draw.circle(s, (255, 211, 82), (cx + 55, int(h * 0.47)), 3)

    if state == "inactive":
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        overlay.fill((90, 90, 90, 75))
        s.blit(overlay, (0, 0))
    return s


def generate_customer_sprite(product: str, angry: bool, size: tuple[int, int]) -> pygame.Surface:
    product = product if product in PRODUCT_STYLES else "sandwich"
    style = PRODUCT_STYLES[product]
    w, h = size
    s = pygame.Surface(size, pygame.SRCALPHA)
    cx = w // 2
    foot = int(h * 0.90)
    shirt = (217, 71, 65) if angry else style["main"]
    dark = (108, 36, 43) if angry else style["dark"]
    skin = (223, 166, 112)

    pygame.draw.ellipse(s, (0, 0, 0, 45), (cx - 24, foot - 4, 48, 13))
    pygame.draw.line(s, (57, 60, 80), (cx - 10, int(h * 0.63)), (cx - 15, foot), 7)
    pygame.draw.line(s, (57, 60, 80), (cx + 10, int(h * 0.63)), (cx + 15, foot), 7)
    pygame.draw.circle(s, (30, 31, 34), (cx - 16, foot), 5)
    pygame.draw.circle(s, (30, 31, 34), (cx + 16, foot), 5)
    pygame.draw.line(s, skin, (cx - 23, int(h * 0.51)), (cx - 36, int(h * 0.63)), 7)
    pygame.draw.line(s, skin, (cx + 23, int(h * 0.51)), (cx + 36, int(h * 0.63)), 7)
    pygame.draw.circle(s, skin, (cx - 38, int(h * 0.64)), 4)
    pygame.draw.circle(s, skin, (cx + 38, int(h * 0.64)), 4)
    rr(s, shirt, (cx - 23, int(h * 0.43), 46, 36), radius=15, border=(52, 47, 43))
    pygame.draw.circle(s, skin, (cx, int(h * 0.29)), 18)
    pygame.draw.arc(s, dark, (cx - 20, int(h * 0.14), 40, 34), math.pi, 2 * math.pi, 9)
    pygame.draw.circle(s, dark, (cx - 14, int(h * 0.19)), 7)
    pygame.draw.circle(s, dark, (cx + 13, int(h * 0.19)), 7)
    pygame.draw.circle(s, (48, 31, 24), (cx - 6, int(h * 0.29)), 2)
    pygame.draw.circle(s, (48, 31, 24), (cx + 6, int(h * 0.29)), 2)
    if angry:
        pygame.draw.line(s, (120, 0, 0), (cx - 11, int(h * 0.24)), (cx - 3, int(h * 0.27)), 2)
        pygame.draw.line(s, (120, 0, 0), (cx + 11, int(h * 0.24)), (cx + 3, int(h * 0.27)), 2)
        pygame.draw.arc(s, (120, 0, 0), (cx - 8, int(h * 0.36), 16, 9), math.pi, 2 * math.pi, 2)
    else:
        pygame.draw.arc(s, (116, 61, 41), (cx - 7, int(h * 0.33), 14, 8), 0.1, math.pi - 0.1, 2)
    badge = generate_food_sprite(product, (27, 22))
    s.blit(badge, badge.get_rect(center=(cx, int(h * 0.55))))
    return s


# Estado visual

@dataclass
class Motion:
    x: float
    y: float
    tx: float
    ty: float
    speed: float = 7.5
    visible: bool = True
    leaving: bool = False

    def set_target(self, pos: tuple[float, float], speed: Optional[float] = None):
        self.tx, self.ty = pos
        if speed is not None:
            self.speed = speed

    def update(self, dt: float):
        a = 1.0 - math.exp(-self.speed * dt)
        self.x = lerp(self.x, self.tx, a)
        self.y = lerp(self.y, self.ty, a)

    def close_to_target(self) -> bool:
        return abs(self.x - self.tx) + abs(self.y - self.ty) < 8

    @property
    def pos(self) -> tuple[float, float]:
        return self.x, self.y


@dataclass
class Ticket:
    client_id: int
    product: str
    created_time: float
    due_time: float
    status: str = "waiting"  # waiting | cooking | served
    screen_x: float = -200.0
    target_x: float = 0.0
    age_after_served: float = 0.0

    def update(self, dt: float):
        self.screen_x = lerp(self.screen_x, self.target_x, 1.0 - math.exp(-9 * dt))
        if self.status == "served":
            self.age_after_served += dt

    @property
    def remove(self) -> bool:
        return self.status == "served" and self.age_after_served > 1.0


@dataclass
class FloatingText:
    text: str
    x: float
    y: float
    color: tuple[int, int, int]
    age: float = 0.0
    duration: float = 1.15

    def update(self, dt: float):
        self.age += dt
        self.y -= 24 * dt

    @property
    def done(self) -> bool:
        return self.age >= self.duration


# Aplicacion principal
class KojoOvercookedApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Kojo's Restaurant - Overcooked Style DES")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        self.logical = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT)).convert_alpha()
        self.clock = pygame.time.Clock()
        self.assets = AssetManager()
        self.bg = self.assets.background()

        self.font_xs = pygame.font.SysFont("arial", 13)
        self.font_sm = pygame.font.SysFont("arial", 15)
        self.font = pygame.font.SysFont("arial", 17)
        self.font_bold = pygame.font.SysFont("arial", 17, bold=True)
        self.font_lg = pygame.font.SysFont("arial", 24, bold=True)
        self.font_xl = pygame.font.SysFont("arial", 36, bold=True)

        log_file = getattr(config, "LOG_FILE", "logs/simulation.log")
        self.logger = setup_logger(enabled=False, level=getattr(config, "LOG_LEVEL", "INFO"), log_file=log_file)

        self.scenario_names = list(SCENARIOS.keys())
        self.scenario_index = 1 if "extra_employee_peak" in self.scenario_names else 0
        self.experiment_configs = getattr(
            config,
            "EXPERIMENT_CONFIGS",
            [{"config_id": "default"}],
        )
        self.config_index = 0
        self.seed = int(getattr(config, "DEFAULT_SEED", 1))
        self.autoplay = False
        self.delay_ms = 420
        self.next_step_ms = 0
        self.show_debug = True
        self.finished = False
        self.phase = 0.0

        self.simulator: Optional[KojoSimulator] = None
        self.employee_visuals: dict[int, Motion] = {}
        self.customer_visuals: dict[int, Motion] = {}
        self.customer_objects: dict[int, Any] = {}
        self.tickets: list[Ticket] = []
        self.floating: list[FloatingText] = []
        self.event_log: list[str] = []
        self.current_event = "Listo"
        self.reset_simulation()

    # Integracion con simulador
    def make_simulator(self, seed: int, use_extra_employee: bool, experiment_config: dict):
        signature = inspect.signature(KojoSimulator.__init__)
        kwargs = {"seed": seed, "use_extra_employee": use_extra_employee, "logger": self.logger}
        if "experiment_config" in signature.parameters:
            kwargs["experiment_config"] = experiment_config
        return KojoSimulator(**kwargs)

    def reset_simulation(self):
        scenario_name = self.scenario_names[self.scenario_index]
        use_extra = SCENARIOS[scenario_name]
        experiment_config = self.experiment_configs[self.config_index]
        self.simulator = self.make_simulator(self.seed, use_extra, experiment_config)
        self.simulator.schedule_initial_events()
        self.autoplay = False
        self.finished = False
        self.current_event = "Replica reiniciada"
        self.employee_visuals.clear()
        self.customer_visuals.clear()
        self.customer_objects.clear()
        self.tickets.clear()
        self.floating.clear()
        self.event_log.clear()

        for employee in self.simulator.employees:
            pos = self.employee_home(employee.id)
            self.employee_visuals[employee.id] = Motion(pos[0], pos[1], pos[0], pos[1], speed=9.0)
        self.update_employee_targets(force=True)
        self.relayout_tickets()
        self.log(f"Nueva replica | escenario={scenario_name} | seed={self.seed}")
        self.log(f"Config={experiment_config.get('config_id', 'default')} | Proyecto={'OK' if PROJECT_AVAILABLE else 'DEMO'}")
        self.log("SPACE iniciar/pausar | RIGHT paso | R reiniciar | +/- velocidad")

    def step_once(self):
        if self.simulator is None or self.finished:
            return
        if not self.simulator.event_queue:
            self.finish()
            return

        event = heapq.heappop(self.simulator.event_queue)
        before_queue = self.queue_positions_by_client()
        before_busy = {e.id: e.current_client for e in self.simulator.employees}
        before_current_ids = {e.id: getattr(e.current_client, "id", None) for e in self.simulator.employees}

        served_client = None
        if event.event_type == SERVICE_END and event.payload is not None:
            served_client = getattr(event.payload, "current_client", None)

        self.simulator.advance_clock(event.time)
        self.process_event(event)

        after_busy = {e.id: e.current_client for e in self.simulator.employees}
        self.current_event = self.describe_event(event, served_client)
        self.log(self.current_event)

        self.apply_visual_transitions(event, before_queue, before_busy, before_current_ids, after_busy, served_client)
        self.update_employee_targets()
        self.relayout_tickets()

        if not self.simulator.event_queue and not self.customer_visuals:
            self.finish()

    def process_event(self, event):
        if event.event_type == ARRIVAL:
            self.simulator.handle_arrival(event.payload)
        elif event.event_type == SERVICE_END:
            self.simulator.handle_service_end(event.payload)
        elif event.event_type == PEAK_START:
            self.simulator.handle_peak_start()
        elif event.event_type == PEAK_END:
            self.simulator.handle_peak_end()
        elif event.event_type == CLOSE:
            self.simulator.handle_close()

    def finish(self):
        if self.finished or self.simulator is None:
            return
        self.finished = True
        self.autoplay = False
        self.current_event = "Simulacion finalizada"
        try:
            if hasattr(self.simulator, "validate_end_state"):
                self.simulator.validate_end_state()
            results = self.simulator.build_results()
            self.log("SIMULACION FINALIZADA")
            self.log(
                f"total={results.get('total_customers', 0)} | atendidos={results.get('completed_customers', 0)} | "
                f"espera>5={results.get('delayed_percentage', 0):.2f}% | espera_prom={results.get('average_wait', 0):.2f}"
            )
        except Exception as exc:
            self.log(f"ERROR al cerrar: {exc}")

    # Eventos visuales

    def apply_visual_transitions(self, event, before_queue, before_busy, before_current_ids, after_busy, served_client):
        if self.simulator is None:
            return

        # Llegada: se crea el ticket arriba y el cliente entra por la acera central.
        if event.event_type == ARRIVAL:
            client = event.payload
            cid = getattr(client, "id", None)
            if cid is not None:
                self.customer_objects[cid] = client
                self.customer_visuals[cid] = Motion(*self.spawn_position(), *self.queue_entry_position(), speed=5.0)
                self.create_ticket(client)
                self.floating.append(FloatingText("NUEVO PEDIDO", 805, 235, (219, 79, 48)))

        # Clientes que terminaron salen hacia la derecha.
        if served_client is not None:
            cid = getattr(served_client, "id", None)
            if cid in self.customer_visuals:
                self.customer_visuals[cid].set_target(self.exit_position(), speed=4.6)
                self.customer_visuals[cid].leaving = True
            self.mark_ticket(cid, "served")
            emp_id = getattr(event.payload, "id", None)
            sx, sy = self.service_customer_position(emp_id or 1)
            self.floating.append(FloatingText("SERVIDO", sx, sy - 76, (36, 142, 74)))

        # Clientes que pasan de cola a servicio.
        for emp in self.simulator.employees:
            before_client = before_busy.get(emp.id)
            after_client = after_busy.get(emp.id)
            before_id = getattr(before_client, "id", None)
            after_id = getattr(after_client, "id", None)
            if after_client is not None and after_id != before_id:
                self.customer_objects[after_id] = after_client
                if after_id not in self.customer_visuals:
                    start = before_queue.get(after_id, self.queue_entry_position())
                    self.customer_visuals[after_id] = Motion(start[0], start[1], start[0], start[1], speed=8.0)
                self.customer_visuals[after_id].set_target(self.service_customer_position(emp.id), speed=7.0)
                self.mark_ticket(after_id, "cooking")
                self.floating.append(FloatingText("A COCINA", *self.service_customer_position(emp.id), (53, 92, 178)))

        # Los que quedan en la cola se reacomodan sobre la acera/crosswalk del medio.
        for idx, client in enumerate(list(getattr(self.simulator, "waiting_queue", []))):
            cid = getattr(client, "id", None)
            if cid is None:
                continue
            if cid not in self.customer_visuals:
                start = before_queue.get(cid, self.spawn_position())
                self.customer_visuals[cid] = Motion(start[0], start[1], start[0], start[1], speed=6.0)
            self.customer_objects[cid] = client
            self.customer_visuals[cid].set_target(self.queue_slot(idx), speed=6.0)

        # Avisos de hora pico.
        if event.event_type == PEAK_START:
            self.floating.append(FloatingText("HORA PICO", 805, 165, (194, 42, 50), duration=1.6))
        elif event.event_type == PEAK_END:
            self.floating.append(FloatingText("FIN HORA PICO", 805, 165, (54, 79, 118), duration=1.6))

    def create_ticket(self, client):
        cid = getattr(client, "id", None)
        product = getattr(client, "product", "sandwich")
        product = product if product in PRODUCT_STYLES else "sandwich"
        created = getattr(client, "arrival_time", getattr(self.simulator, "clock", 0.0))
        service = getattr(client, "service_time", 5.0)
        due = created + getattr(config, "WAIT_THRESHOLD", 5.0) + service
        self.tickets.append(Ticket(cid, product, created, due))

    def mark_ticket(self, client_id, status):
        if client_id is None:
            return
        for t in self.tickets:
            if t.client_id == client_id:
                t.status = status
                return

    def relayout_tickets(self):
        # Mantiene los tickets activos arriba.
        active = [t for t in self.tickets if not t.remove]
        self.tickets = active[-8:]
        start = 20
        for i, ticket in enumerate(self.tickets):
            ticket.target_x = start + i * 184

    def update_employee_targets(self, force=False):
        if self.simulator is None:
            return
        for emp in self.simulator.employees:
            actor = self.employee_visuals.get(emp.id)
            if actor is None:
                pos = self.employee_home(emp.id)
                actor = Motion(pos[0], pos[1], pos[0], pos[1], speed=8.0)
                self.employee_visuals[emp.id] = actor
            active = getattr(emp, "active", True)
            busy = getattr(emp, "busy", False)
            if not active:
                target = self.employee_offstage(emp.id)
            elif busy:
                target = self.employee_station(emp.id, getattr(getattr(emp, "current_client", None), "product", "sandwich"))
            else:
                target = self.employee_home(emp.id)
            actor.set_target(target)
            if force:
                actor.x, actor.y = target

    # Coordenadas

    def spawn_position(self) -> tuple[float, float]:
        return 810, 930

    def queue_entry_position(self) -> tuple[float, float]:
        return 810, 780

    def exit_position(self) -> tuple[float, float]:
        return 1540, 492

    def queue_slot(self, index: int) -> tuple[float, float]:
        # Cola central: acera/crosswalk del medio. Primero vertical, luego zigzag leve.
        index = max(0, index)
        y = 765 - index * 46
        if y >= 320:
            x = 805 + (index % 2) * 20
            return x, y
        extra = index - 10
        return 735 - extra * 44, 308

    def queue_positions_by_client(self) -> dict[int, tuple[float, float]]:
        if self.simulator is None:
            return {}
        out = {}
        for idx, client in enumerate(list(getattr(self.simulator, "waiting_queue", []))):
            out[getattr(client, "id", -1)] = self.queue_slot(idx)
        return out

    def employee_home(self, emp_id: int) -> tuple[float, float]:
        return {
            1: (462, 625),
            2: (1124, 340),
            3: (1118, 620),
        }.get(emp_id, (780, 460))

    def employee_offstage(self, emp_id: int) -> tuple[float, float]:
        return {
            1: (462, 625),
            2: (1124, 340),
            3: (1520, 805),
        }.get(emp_id, (1520, 805))

    def employee_station(self, emp_id: int, product: str) -> tuple[float, float]:
        product = product if product in PRODUCT_STYLES else "sandwich"
        # Ambos productos aparecen en ambos lados del mapa.
        left_sandwich = (445, 620)
        left_sushi = (405, 285)
        right_sandwich = (1185, 295)
        right_sushi = (1138, 620)
        extra_sandwich = (1020, 620)
        extra_sushi = (1010, 300)
        if emp_id == 1:
            return left_sandwich if product == "sandwich" else left_sushi
        if emp_id == 2:
            return right_sandwich if product == "sandwich" else right_sushi
        return extra_sandwich if product == "sandwich" else extra_sushi

    def service_customer_position(self, emp_id: int) -> tuple[float, float]:
        return {
            1: (650, 610),
            2: (960, 300),
            3: (965, 610),
        }.get(emp_id, (820, 460))

    # Bucle
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    else:
                        self.handle_key(event.key)

            self.update(dt)
            if self.autoplay and now >= self.next_step_ms:
                self.step_once()
                self.next_step_ms = now + self.delay_ms

            self.draw()
            pygame.display.flip()
        pygame.quit()

    def handle_key(self, key):
        if key == pygame.K_SPACE:
            self.autoplay = not self.autoplay
            self.next_step_ms = pygame.time.get_ticks()
        elif key == pygame.K_RIGHT:
            self.step_once()
        elif key == pygame.K_r:
            self.reset_simulation()
        elif key == pygame.K_1:
            self.scenario_index = self.scenario_names.index("two_employees")
            self.reset_simulation()
        elif key == pygame.K_2:
            self.scenario_index = self.scenario_names.index("extra_employee_peak")
            self.reset_simulation()
        elif key == pygame.K_c:
            self.config_index = (self.config_index + 1) % len(self.experiment_configs)
            self.reset_simulation()
        elif key == pygame.K_s:
            self.seed += 1
            self.reset_simulation()
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.delay_ms = max(70, self.delay_ms - 60)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.delay_ms = min(2500, self.delay_ms + 60)
        elif key == pygame.K_TAB:
            self.show_debug = not self.show_debug

    def update(self, dt):
        self.phase += dt
        for motion in self.employee_visuals.values():
            motion.update(dt)
        for cid, motion in list(self.customer_visuals.items()):
            motion.update(dt)
            if motion.leaving and motion.close_to_target():
                self.customer_visuals.pop(cid, None)
                self.customer_objects.pop(cid, None)
        for t in list(self.tickets):
            t.update(dt)
            if t.remove:
                self.tickets.remove(t)
        for ft in list(self.floating):
            ft.update(dt)
            if ft.done:
                self.floating.remove(ft)

    # Dibujo

    def draw(self):
        self.logical.fill((33, 43, 53, 255))
        if self.bg is not None:
            self.logical.blit(self.bg, (0, 0))
            alpha_rect(self.logical, (0, 0, 0, 35), (0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT))
        else:
            self.draw_stage()

        self.draw_entities()
        self.draw_tickets()
        self.draw_hud()
        self.present_scaled()

    def present_scaled(self):
        sw, sh = self.screen.get_size()
        scale = min(sw / LOGICAL_WIDTH, sh / LOGICAL_HEIGHT)
        tw, th = int(LOGICAL_WIDTH * scale), int(LOGICAL_HEIGHT * scale)
        x, y = (sw - tw) // 2, (sh - th) // 2
        self.screen.fill((18, 22, 29))
        scaled = pygame.transform.smoothscale(self.logical, (tw, th))
        self.screen.blit(scaled, (x, y))

    def draw_stage(self):
        self.draw_roads_and_sidewalks()
        self.draw_counters_and_stations()
        self.draw_props()
        self.draw_warm_light()

    def draw_roads_and_sidewalks(self):
        # Fondo de carretera y aceras.
        pygame.draw.rect(self.logical, COLORS["road"], (0, 110, 1600, 790))
        pygame.draw.rect(self.logical, COLORS["sidewalk"], (0, 0, 1600, 110))
        pygame.draw.rect(self.logical, COLORS["sidewalk"], (0, 790, 1600, 110))
        pygame.draw.rect(self.logical, COLORS["sidewalk"], (690, 110, 230, 790))

        # Losas de la acera central.
        for y in range(120, 900, 46):
            pygame.draw.line(self.logical, COLORS["sidewalk_line"], (690, y), (920, y), 1)
        for x in range(690, 921, 46):
            pygame.draw.line(self.logical, COLORS["sidewalk_line"], (x, 110), (x, 900), 1)

        # Calles laterales y lineas amarillas.
        for x in [50, 1548, 680, 930]:
            pygame.draw.line(self.logical, COLORS["yellow_line"], (x, 120), (x, 780), 4)
        pygame.draw.line(self.logical, COLORS["yellow_line"], (0, 777), (1600, 777), 4)
        pygame.draw.line(self.logical, COLORS["yellow_line"], (0, 123), (1600, 123), 4)

        # Crosswalk central vertical: aqui se forma la cola.
        for y in range(300, 775, 54):
            rr(self.logical, COLORS["crosswalk"], (745, y, 130, 30), radius=3)
        alpha_rect(self.logical, (255, 255, 255, 18), (722, 280, 175, 520), radius=18)
        draw_text(self.logical, self.font_bold, "COLA / ACERA", (810, 285), (70, 64, 55), anchor="center")

        # Borde superior tipo edificios.
        pygame.draw.rect(self.logical, (84, 139, 64), (0, 0, 1600, 28))
        for x in range(0, 1600, 140):
            pygame.draw.rect(self.logical, (73, 126, 55), (x, 28, 100, 14))

    def draw_counter_block(self, x, y, w, h, label: Optional[str] = None):
        shadow(self.logical, (x + w / 2 + 4, y + h / 2 + 9), w, h // 2, 45)
        rr(self.logical, COLORS["counter_side"], (x, y + 8, w, h), radius=10)
        rr(self.logical, COLORS["counter_top"], (x, y, w, h), radius=10, border=COLORS["counter_dark"])
        pygame.draw.line(self.logical, (255, 224, 143), (x + 8, y + 6), (x + w - 10, y + 6), 2)
        if label:
            draw_text(self.logical, self.font_bold, label, (x + w / 2, y + h / 2), (88, 53, 31), anchor="center")

    def draw_counters_and_stations(self):
        # Barras top/bottom y lados, dejando pasillos.
        # Lado izquierdo: sushi arriba, sandwich abajo.
        for i in range(5):
            self.draw_counter_block(130 + i * 95, 210, 90, 64)
        for i in range(6):
            self.draw_counter_block(125 + i * 95, 650, 90, 64)
        for i in range(3):
            self.draw_counter_block(580, 335 + i * 86, 72, 80)

        # Lado derecho: sandwich arriba, sushi abajo.
        for i in range(5):
            self.draw_counter_block(970 + i * 95, 210, 90, 64)
        for i in range(5):
            self.draw_counter_block(965 + i * 95, 650, 90, 64)
        for i in range(3):
            self.draw_counter_block(935, 335 + i * 86, 72, 80)

        # Ventanas de entrega cerca de la cola.
        self.draw_counter_block(610, 555, 100, 70, "PICK")
        self.draw_counter_block(890, 250, 100, 70, "PICK")
        self.draw_counter_block(890, 555, 100, 70, "PICK")

        # Estaciones con ingredientes.
        self.draw_station_label(360, 178, "SUSHI", "sushi")
        self.draw_station_label(360, 622, "SANDWICH", "sandwich")
        self.draw_station_label(1130, 178, "SANDWICH", "sandwich")
        self.draw_station_label(1130, 622, "SUSHI", "sushi")

        self.draw_ingredient_bins([(245, 229, "rice"), (345, 229, "fish"), (445, 229, "nori")])
        self.draw_ingredient_bins([(250, 670, "bread"), (350, 670, "tomato"), (450, 670, "bread")])
        self.draw_ingredient_bins([(1090, 230, "bread"), (1190, 230, "tomato"), (1290, 230, "bread")])
        self.draw_ingredient_bins([(1088, 670, "rice"), (1188, 670, "fish"), (1288, 670, "nori")])

        # Ollas, tablas y platos.
        self.draw_pot(525, 226)
        self.draw_pot(1380, 667)
        for px, py in [(632, 590), (912, 285), (912, 590)]:
            pygame.draw.ellipse(self.logical, (255, 255, 248), (px, py, 58, 32))
            pygame.draw.ellipse(self.logical, (207, 205, 191), (px, py, 58, 32), 2)

    def draw_station_label(self, x, y, text, product):
        style = PRODUCT_STYLES[product]
        rr(self.logical, style["dark"], (x - 78, y, 156, 34), radius=12)
        draw_text(self.logical, self.font_bold, text, (x, y + 17), (255, 255, 255), anchor="center")

    def draw_ingredient_bins(self, items: list[tuple[int, int, str]]):
        for x, y, name in items:
            rr(self.logical, (188, 127, 69), (x - 30, y - 20, 60, 44), radius=8, border=(91, 55, 34))
            rr(self.logical, (226, 179, 111), (x - 26, y - 26, 52, 22), radius=7)
            icon = self.assets.food(name, (40, 34))
            self.logical.blit(icon, icon.get_rect(center=(x, y)))

    def draw_pot(self, x, y):
        pygame.draw.ellipse(self.logical, (61, 74, 83), (x - 30, y - 22, 60, 44))
        pygame.draw.ellipse(self.logical, (115, 134, 146), (x - 27, y - 20, 54, 27))
        pygame.draw.ellipse(self.logical, (37, 47, 54), (x - 24, y - 17, 48, 20))
        # Vapor animado.
        for i in range(3):
            off = math.sin(self.phase * 2.7 + i) * 4
            pygame.draw.arc(self.logical, (255, 255, 255), (x - 18 + i * 14 + off, y - 54, 18, 32), 1.6, 4.4, 2)

    def draw_props(self):
        # Toldos y decoracion en el borde.
        self.draw_awning(120, 780, 360, "blue")
        self.draw_awning(1090, 780, 360, "red")
        self.draw_awning(105, 112, 360, "red")
        self.draw_awning(1085, 112, 360, "blue")

        # Carros/conos/plantas.
        for x, y in [(1460, 205), (1510, 205), (1478, 735), (1518, 735), (70, 280), (45, 720)]:
            pygame.draw.polygon(self.logical, (229, 104, 42), [(x, y - 18), (x - 16, y + 17), (x + 16, y + 17)])
            pygame.draw.rect(self.logical, (245, 232, 215), (x - 10, y + 2, 20, 8))
        self.draw_car(1450, 360)
        self.draw_tree(60, 60)
        self.draw_tree(1530, 60)
        self.draw_tree(1510, 830)

    def draw_awning(self, x, y, w, color="red"):
        c = (222, 84, 73) if color == "red" else (151, 186, 204)
        rr(self.logical, (98, 88, 73), (x + 10, y + 42, w - 20, 8), radius=4)
        pygame.draw.rect(self.logical, c, (x, y, w, 54), border_radius=8)
        stripe_w = 40
        for i in range(0, w, stripe_w * 2):
            pygame.draw.rect(self.logical, (245, 236, 210), (x + i, y, stripe_w, 54))
        pygame.draw.rect(self.logical, (94, 83, 70), (x, y, w, 54), 2, border_radius=8)

    def draw_car(self, x, y):
        rr(self.logical, (74, 158, 80), (x, y, 92, 150), radius=28, border=(34, 91, 49))
        rr(self.logical, (54, 106, 131), (x + 14, y + 25, 64, 42), radius=10)
        rr(self.logical, (36, 73, 91), (x + 14, y + 86, 64, 42), radius=10)
        pygame.draw.circle(self.logical, (245, 227, 142), (x + 8, y + 136), 7)
        pygame.draw.circle(self.logical, (245, 227, 142), (x + 84, y + 136), 7)

    def draw_tree(self, x, y):
        pygame.draw.rect(self.logical, (103, 64, 37), (x - 9, y + 8, 18, 38), border_radius=5)
        for dx, dy, r in [(-18, 0, 25), (10, -4, 28), (0, -22, 24), (24, 14, 20), (-24, 19, 19)]:
            pygame.draw.circle(self.logical, (75, 146, 68), (x + dx, y + dy), r)
            pygame.draw.circle(self.logical, (47, 102, 53), (x + dx, y + dy), r, 2)

    def draw_warm_light(self):
        # Viñeta suave.
        alpha_rect(self.logical, (255, 213, 117, 22), (0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT))
        alpha_rect(self.logical, (0, 0, 0, 45), (-40, 850, 1680, 80), radius=30)

    def draw_entities(self):
        # Clientes: ordenar por y para profundidad.
        entries = []
        for cid, motion in self.customer_visuals.items():
            obj = self.customer_objects.get(cid)
            entries.append((motion.y, "customer", cid, motion, obj))
        for eid, motion in self.employee_visuals.items():
            entries.append((motion.y, "employee", eid, motion, None))
        entries.sort(key=lambda item: item[0])

        for _, kind, ident, motion, obj in entries:
            if kind == "customer":
                self.draw_customer(obj, motion)
            else:
                self.draw_employee(ident, motion)

        for ft in self.floating:
            alpha = int(255 * (1 - ft.age / ft.duration))
            color = (*ft.color, alpha)
            tmp = pygame.Surface((260, 36), pygame.SRCALPHA)
            draw_text(tmp, self.font_bold, ft.text, (130, 18), color, anchor="center")
            self.logical.blit(tmp, (ft.x - 130, ft.y - 18))

    def draw_customer(self, client, motion: Motion):
        product = getattr(client, "product", "sandwich") if client is not None else "sandwich"
        product = product if product in PRODUCT_STYLES else "sandwich"
        now = getattr(self.simulator, "clock", 0.0) if self.simulator else 0.0
        arrival = getattr(client, "arrival_time", now) if client is not None else now
        service_start = getattr(client, "service_start_time", None) if client is not None else None
        wait = (service_start if service_start is not None else now) - arrival
        angry = service_start is None and wait > getattr(config, "WAIT_THRESHOLD", 5.0)
        moving = abs(motion.x - motion.tx) + abs(motion.y - motion.ty) > 12
        bob = math.sin(self.phase * (9.0 if moving else 3.0) + (getattr(client, "id", 0) or 0)) * (4 if moving else 1.5)
        sprite = self.assets.customer(product, angry=angry, size=(74, 102))
        shadow(self.logical, (motion.x, motion.y + 18), 48, 13, 50)
        self.logical.blit(sprite, sprite.get_rect(midbottom=(motion.x, motion.y + bob)))
        cid = getattr(client, "id", "") if client is not None else ""
        draw_text(self.logical, self.font_xs, f"C{cid}", (motion.x, motion.y - 82), (37, 31, 26), anchor="center")
        self.draw_order_bubble(product, (motion.x + 34, motion.y - 76), small=True)
        if service_start is None and wait > 0.1:
            color = (160, 36, 45) if angry else (46, 64, 82)
            draw_text(self.logical, self.font_xs, f"{wait:.1f}m", (motion.x, motion.y + 14), color, anchor="center")

    def draw_employee(self, employee_id: int, motion: Motion):
        emp = None
        if self.simulator is not None:
            for e in self.simulator.employees:
                if e.id == employee_id:
                    emp = e
                    break
        active = getattr(emp, "active", True) if emp is not None else True
        busy = getattr(emp, "busy", False) if emp is not None else False
        state = "inactive" if not active else "busy" if busy else "idle"
        moving = abs(motion.x - motion.tx) + abs(motion.y - motion.ty) > 8
        bob = math.sin(self.phase * (8 if moving else 2.5) + employee_id) * (3 if moving else 1)
        sprite = self.assets.chef(state, size=(88, 110))
        shadow(self.logical, (motion.x, motion.y + 18), 56, 14, 55)
        self.logical.blit(sprite, sprite.get_rect(midbottom=(motion.x, motion.y + bob)))
        draw_text(self.logical, self.font_xs, f"E{employee_id}", (motion.x, motion.y - 93), (28, 28, 28), anchor="center")
        if busy and emp is not None and getattr(emp, "current_client", None) is not None:
            product = getattr(emp.current_client, "product", "sandwich")
            self.draw_order_bubble(product, (motion.x + 38, motion.y - 88), small=True)

    def draw_order_bubble(self, product: str, pos, small=False):
        product = product if product in PRODUCT_STYLES else "sandwich"
        r = 19 if small else 25
        pygame.draw.circle(self.logical, (255, 255, 255), (int(pos[0]), int(pos[1])), r)
        pygame.draw.circle(self.logical, PRODUCT_STYLES[product]["dark"], (int(pos[0]), int(pos[1])), r, 2)
        icon = self.assets.food(product, (29, 23) if small else (40, 32))
        self.logical.blit(icon, icon.get_rect(center=pos))

    def draw_tickets(self):
        # Tickets superiores de pedidos, con barra de paciencia.
        now = getattr(self.simulator, "clock", 0.0) if self.simulator else 0.0
        for ticket in self.tickets:
            x = ticket.screen_x
            y = 18
            alpha = 255
            if ticket.status == "served":
                alpha = int(255 * (1 - ticket.age_after_served / 1.0))
            tmp = pygame.Surface((168, 126), pygame.SRCALPHA)
            style = PRODUCT_STYLES.get(ticket.product, PRODUCT_STYLES["sandwich"])
            rr(tmp, (255, 255, 255, alpha), (0, 0, 168, 126), radius=14, border=(94, 68, 46))
            rr(tmp, (*style["dark"], alpha), (0, 0, 168, 18), radius=12)
            icon = self.assets.food(ticket.product, (48, 38))
            tmp.blit(icon, icon.get_rect(center=(84, 42)))
            # ingredientes del pedido.
            for i, ing in enumerate(style["ingredients"]):
                rr(tmp, (226, 238, 241, alpha), (16 + i * 48, 68, 38, 34), radius=8, border=(128, 143, 143))
                ing_icon = self.assets.food(ing, (30, 26))
                tmp.blit(ing_icon, ing_icon.get_rect(center=(35 + i * 48, 85)))
            total = max(1.0, ticket.due_time - ticket.created_time)
            remaining = clamp((ticket.due_time - now) / total, 0.0, 1.0)
            if ticket.status == "served":
                bar_color = (88, 173, 84, alpha)
                remaining = 1.0
            elif ticket.status == "cooking":
                bar_color = (74, 136, 206, alpha)
            else:
                bar_color = (*mix((217, 65, 59), (83, 176, 86), remaining), alpha)
            rr(tmp, (85, 71, 60, alpha), (14, 109, 140, 10), radius=5)
            rr(tmp, bar_color, (14, 109, int(140 * remaining), 10), radius=5)
            draw_text(tmp, self.font_xs, f"C{ticket.client_id}", (10, 22), (42, 38, 35), anchor="topleft")
            if ticket.status == "served":
                alpha_rect(tmp, (65, 180, 75, 95), (0, 0, 168, 126), radius=14)
                draw_text(tmp, self.font_bold, "OK", (84, 62), (255, 255, 255), anchor="center")
            self.logical.blit(tmp, (x, y))

    def draw_hud(self):
        # Panel inferior derecho: timer grande.
        now = getattr(self.simulator, "clock", 0.0) if self.simulator else 0.0
        remaining = max(0.0, getattr(config, "DAY_CLOSE", 660) - min(now, getattr(config, "DAY_CLOSE", 660)))
        m = int(remaining)
        time_text = f"{m // 60:02d}:{m % 60:02d}"
        shadow(self.logical, (1486, 823), 165, 70, 70)
        draw_text(self.logical, self.font_xl, time_text, (1490, 824), (255, 255, 255), anchor="center")
        draw_text(self.logical, self.font_xs, "tiempo restante", (1490, 852), (255, 244, 220), anchor="center")

        # Moneda/score: porcentaje de demora acumulado.
        score_rect = pygame.Rect(18, 805, 140, 76)
        pygame.draw.ellipse(self.logical, (232, 195, 54), score_rect)
        pygame.draw.ellipse(self.logical, (162, 117, 32), score_rect, 4)
        pct = 0.0
        if self.simulator is not None and getattr(self.simulator, "total_customers", 0):
            pct = 100 * getattr(self.simulator, "delayed_customers", 0) / max(1, getattr(self.simulator, "total_customers", 1))
        draw_text(self.logical, self.font_xl, f"-{pct:.0f}", (88, 842), (255, 255, 255), anchor="center")

        if self.show_debug:
            self.draw_debug_panel()

    def draw_debug_panel(self):
        panel = pygame.Rect(18, 150, 392, 270)
        alpha_rect(self.logical, (255, 248, 232, 222), panel, radius=16)
        pygame.draw.rect(self.logical, (112, 76, 47), panel, 2, border_radius=16)
        y = panel.y + 14
        scenario = self.scenario_names[self.scenario_index]
        cfg = self.experiment_configs[self.config_index]
        lines = [
            "Kojo's Restaurant - DES visual",
            f"Escenario: {scenario}",
            f"Config: {cfg.get('config_id', 'default')}",
            f"Seed: {self.seed} | Delay: {self.delay_ms} ms",
            f"Evento: {self.current_event[:56]}",
        ]
        if self.simulator is not None:
            lines += [
                f"t={getattr(self.simulator, 'clock', 0):.2f} ({self.format_time(getattr(self.simulator, 'clock', 0))})",
                f"Cola={len(getattr(self.simulator, 'waiting_queue', []))} | Pedidos HUD={len(self.tickets)}",
                f"Clientes={getattr(self.simulator, 'total_customers', 0)} | Servidos={getattr(self.simulator, 'completed_customers', 0)}",
            ]
        for i, line in enumerate(lines):
            font = self.font_bold if i == 0 else self.font_sm
            draw_text(self.logical, font, line, (panel.x + 14, y), (47, 42, 37), anchor="topleft")
            y += 25 if i == 0 else 22
        y += 4
        draw_text(self.logical, self.font_xs, "Controles: SPACE, RIGHT, R, 1, 2, C, S, +/-, TAB", (panel.x + 14, y), (83, 73, 65))

        log_panel = pygame.Rect(18, 430, 490, 180)
        alpha_rect(self.logical, (31, 36, 42, 190), log_panel, radius=14)
        pygame.draw.rect(self.logical, (255, 255, 255, 55), log_panel, 1, border_radius=14)
        draw_text(self.logical, self.font_bold, "Eventos recientes", (log_panel.x + 12, log_panel.y + 10), (255, 246, 225))
        yy = log_panel.y + 34
        for line in self.event_log[-7:]:
            draw_text(self.logical, self.font_xs, line[:76], (log_panel.x + 12, yy), (234, 235, 229))
            yy += 20

    # Helpers

    def describe_event(self, event, served_client=None) -> str:
        t = getattr(event, "time", 0.0)
        prefix = f"t={t:.2f} ({self.format_time(t)})"
        if event.event_type == ARRIVAL:
            c = event.payload
            return f"{prefix} | LLEGADA | C{getattr(c, 'id', '?')} | {getattr(c, 'product', '?')}"
        if event.event_type == SERVICE_END:
            emp = event.payload
            c = served_client
            return f"{prefix} | FIN SERVICIO | C{getattr(c, 'id', '?')} | E{getattr(emp, 'id', '?')}"
        if event.event_type == PEAK_START:
            return f"{prefix} | INICIO HORA PICO | empleado extra entra"
        if event.event_type == PEAK_END:
            return f"{prefix} | FIN HORA PICO | empleado extra se retira"
        if event.event_type == CLOSE:
            return f"{prefix} | CIERRE | no entran mas clientes"
        return f"{prefix} | {event.event_type}"

    def format_time(self, minutes_from_open: float) -> str:
        total = int(round(10 * 60 + minutes_from_open))
        h24 = (total // 60) % 24
        minute = total % 60
        suffix = "a.m." if h24 < 12 else "p.m."
        h12 = h24 % 12 or 12
        return f"{h12}:{minute:02d} {suffix}"

    def log(self, line: str):
        self.event_log.append(line)
        if len(self.event_log) > 80:
            self.event_log = self.event_log[-80:]



def main():
    os.chdir(Path(__file__).resolve().parent)
    app = KojoOvercookedApp()
    app.run()


if __name__ == "__main__":
    main()
