"""Seed control and randomization utilities for deterministic scenario generation.

Provides:
- Seeded random number generators
- Deterministic data generation utilities
- Reproducibility guarantees across runs
"""

import hashlib
import random
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class SeedContext:
    """Context for seeded randomization operations."""

    base_seed: int
    scenario_id: str
    component: str | None = None

    def derive_seed(self) -> int:
        """Derive a deterministic seed from context.

        Combines base_seed, scenario_id, and optional component
        to produce a stable, unique seed for each randomization point.
        """
        if self.component:
            seed_string = f"{self.base_seed}:{self.scenario_id}:{self.component}"
        else:
            seed_string = f"{self.base_seed}:{self.scenario_id}"

        # Hash to integer for reproducibility
        hash_digest = hashlib.sha256(seed_string.encode("utf-8")).digest()
        return int.from_bytes(hash_digest[:4], byteorder="big")


class SeededRandom:
    """Deterministic random number generator with seed control.

    Wraps Python's random module with explicit seeding for reproducibility.
    Each instance maintains its own Random instance to avoid global state pollution.
    """

    def __init__(self, seed: int) -> None:
        """Initialize with a specific seed.

        Args:
            seed: Integer seed for deterministic randomization
        """
        self.seed = seed
        self._rng = random.Random(seed)

    def randint(self, a: int, b: int) -> int:
        """Return random integer in range [a, b]."""
        return self._rng.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        """Return random float in range [a, b)."""
        return self._rng.uniform(a, b)

    def choice(self, seq: list) -> object:
        """Return random element from non-empty sequence."""
        return self._rng.choice(seq)

    def choices(self, population: list, k: int) -> list:
        """Return k-length list of elements chosen from population with replacement."""
        return self._rng.choices(population, k=k)

    def shuffle(self, seq: list) -> None:
        """Shuffle sequence in-place."""
        self._rng.shuffle(seq)

    def sample(self, population: list, k: int) -> list:
        """Return k-length list of unique elements chosen from population."""
        return self._rng.sample(population, k=k)


@contextmanager
def seeded_context(seed_ctx: SeedContext) -> Iterator[SeededRandom]:
    """Context manager for seeded randomization.

    Derives a deterministic seed from the context and provides
    a SeededRandom instance. Ensures no global random state is affected.

    Args:
        seed_ctx: Seed context describing the randomization point

    Yields:
        SeededRandom: Seeded random number generator

    Example:
        >>> ctx = SeedContext(base_seed=42, scenario_id="risk_001", component="tradelines")
        >>> with seeded_context(ctx) as rng:
        ...     score = rng.randint(720, 800)
    """
    derived_seed = seed_ctx.derive_seed()
    rng = SeededRandom(derived_seed)
    try:
        yield rng
    finally:
        # Cleanup if needed (currently no-op)
        pass


def generate_deterministic_id(base: str, seed: int) -> str:
    """Generate a deterministic ID from base string and seed.

    Args:
        base: Base identifier string
        seed: Seed for determinism

    Returns:
        Deterministic ID string combining base and seed hash
    """
    seed_hash = hashlib.sha256(f"{base}:{seed}".encode("utf-8")).hexdigest()[:8]
    return f"{base}_{seed_hash}"
