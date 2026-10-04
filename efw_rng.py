"""SplitMix64 (Vigna) in reiner Ganzzahl-Arithmetik: ein skalarer Generator für die Streckenkonfiguration und ein vektorisierter Zähler-Strom für die Szenarien.

numpy garantiert keine versionsstabilen Zufallsströme, die CI installiert die neueste Version; SplitMix64 liefert überall dieselbe Zahlenfolge. Der Vektorstrom gibt
dieselbe Folge wie der skalare Generator (Zählerform: Zustand = Seed + i * GAMMA), numpy-uint64-Arithmetik läuft modulo 2^64 und ist plattformstabil."""
import numpy as np

_MASK = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15
_C1 = 0xBF58476D1CE4E5B9
_C2 = 0x94D049BB133111EB


class SplitMix64:
    """Skalarer Generator."""

    def __init__(self, seed):
        self.state = seed & _MASK

    def next(self):
        self.state = (self.state + GAMMA) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * _C1) & _MASK
        z = ((z ^ (z >> 27)) * _C2) & _MASK
        return z ^ (z >> 31)

    def below(self, n):
        """Ganzzahl in 0..n-1."""
        return self.next() % n


class Stream:
    """Vektorisierter Strom: `below(n, shape)` liefert ganze Zahlen in 0..n-1 und setzt den Zähler fort."""

    def __init__(self, seed):
        self.seed = seed & _MASK
        self.i = 0

    def raw(self, count):
        idx = np.arange(self.i + 1, self.i + 1 + count, dtype=np.uint64)
        self.i += count
        z = np.uint64(self.seed) + idx * np.uint64(GAMMA)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(_C1)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(_C2)
        return z ^ (z >> np.uint64(31))

    def below(self, n, shape):
        count = int(np.prod(shape))
        return (self.raw(count) % np.uint64(n)).astype(np.int64).reshape(shape)
