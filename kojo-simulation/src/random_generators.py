import math
import random

class RandomGenerator:

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def uniform_01(self) -> float:
        # Genera U ~ Uniforme(0, 1).
        u = self.rng.random()
        while u == 0.0:
            u = self.rng.random()
        return u

    def uniform(self, a: float, b: float) -> float:
        # Genera X ~ Uniforme(a, b).
        # X = a + (b - a)U

        if b < a:
            raise ValueError("En uniforme(a, b), b debe ser mayor o igual que a.")
        return a + (b - a) * self.uniform_01()


    def exponential_by_mean(self, mean: float) -> float:
        # Si X ~ Exponencial con media m:
        # X = -m * ln(U) donde U ~ Uniforme(0, 1).

        if mean <= 0:
            raise ValueError("La media de la exponencial debe ser positiva.")
        return -mean * math.log(self.uniform_01())


    def bernoulli(self, probability: float) -> bool:

        if not 0.0 <= probability <= 1.0:
            raise ValueError("La probabilidad debe estar entre 0 y 1.")
        return self.uniform_01() <= probability


    def choose_product(self, p_sandwich: float) -> str:
        # Con probabilidad p_sandwich devuelve 'sandwich'.
        # Con probabilidad 1 - p_sandwich devuelve 'sushi'.

        if self.bernoulli(p_sandwich):
            return "sandwich"
        return "sushi"