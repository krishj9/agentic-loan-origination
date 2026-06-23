"""Tests for seed control and deterministic randomization."""

import pytest

from evaluation.scenarios.seed_control import (
    SeedContext,
    SeededRandom,
    generate_deterministic_id,
    seeded_context,
)


class TestSeedContext:
    """Tests for SeedContext."""

    def test_derive_seed_without_component(self):
        """Test seed derivation without component."""
        ctx = SeedContext(base_seed=42, scenario_id="test_001")
        seed1 = ctx.derive_seed()
        seed2 = ctx.derive_seed()

        # Same context should produce same seed
        assert seed1 == seed2
        assert isinstance(seed1, int)

    def test_derive_seed_with_component(self):
        """Test seed derivation with component."""
        ctx = SeedContext(base_seed=42, scenario_id="test_001", component="risk")
        seed = ctx.derive_seed()

        assert isinstance(seed, int)

    def test_derive_seed_different_contexts(self):
        """Test that different contexts produce different seeds."""
        ctx1 = SeedContext(base_seed=42, scenario_id="test_001")
        ctx2 = SeedContext(base_seed=42, scenario_id="test_002")
        ctx3 = SeedContext(base_seed=43, scenario_id="test_001")

        seed1 = ctx1.derive_seed()
        seed2 = ctx2.derive_seed()
        seed3 = ctx3.derive_seed()

        # Different contexts should produce different seeds
        assert seed1 != seed2
        assert seed1 != seed3
        assert seed2 != seed3

    def test_derive_seed_with_component_differs(self):
        """Test that adding a component changes the seed."""
        ctx_no_component = SeedContext(base_seed=42, scenario_id="test_001")
        ctx_with_component = SeedContext(base_seed=42, scenario_id="test_001", component="risk")

        seed1 = ctx_no_component.derive_seed()
        seed2 = ctx_with_component.derive_seed()

        assert seed1 != seed2


class TestSeededRandom:
    """Tests for SeededRandom."""

    def test_deterministic_randint(self):
        """Test that same seed produces same random integers."""
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        values1 = [rng1.randint(1, 100) for _ in range(10)]
        values2 = [rng2.randint(1, 100) for _ in range(10)]

        assert values1 == values2

    def test_different_seeds_produce_different_values(self):
        """Test that different seeds produce different values."""
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(43)

        values1 = [rng1.randint(1, 100) for _ in range(10)]
        values2 = [rng2.randint(1, 100) for _ in range(10)]

        assert values1 != values2

    def test_deterministic_uniform(self):
        """Test that same seed produces same random floats."""
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        values1 = [rng1.uniform(0.0, 1.0) for _ in range(10)]
        values2 = [rng2.uniform(0.0, 1.0) for _ in range(10)]

        assert values1 == values2

    def test_deterministic_choice(self):
        """Test that same seed produces same choices."""
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        options = ["A", "B", "C", "D", "E"]
        choices1 = [rng1.choice(options) for _ in range(10)]
        choices2 = [rng2.choice(options) for _ in range(10)]

        assert choices1 == choices2

    def test_deterministic_sample(self):
        """Test that same seed produces same samples."""
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        population = list(range(20))
        sample1 = rng1.sample(population, 5)
        sample2 = rng2.sample(population, 5)

        assert sample1 == sample2


class TestSeededContext:
    """Tests for seeded_context context manager."""

    def test_context_manager_provides_seeded_random(self):
        """Test that context manager provides SeededRandom instance."""
        ctx = SeedContext(base_seed=42, scenario_id="test_001")

        with seeded_context(ctx) as rng:
            assert isinstance(rng, SeededRandom)
            value = rng.randint(1, 100)
            assert isinstance(value, int)

    def test_context_manager_deterministic(self):
        """Test that same context produces same random values."""
        ctx = SeedContext(base_seed=42, scenario_id="test_001")

        with seeded_context(ctx) as rng1:
            values1 = [rng1.randint(1, 100) for _ in range(10)]

        with seeded_context(ctx) as rng2:
            values2 = [rng2.randint(1, 100) for _ in range(10)]

        assert values1 == values2


class TestGenerateDeterministicId:
    """Tests for generate_deterministic_id function."""

    def test_generates_id_with_base_and_seed(self):
        """Test that ID is generated with base and seed."""
        id1 = generate_deterministic_id("app", 42)

        assert id1.startswith("app_")
        assert len(id1) > len("app_")

    def test_same_inputs_produce_same_id(self):
        """Test that same inputs produce same ID."""
        id1 = generate_deterministic_id("app", 42)
        id2 = generate_deterministic_id("app", 42)

        assert id1 == id2

    def test_different_seeds_produce_different_ids(self):
        """Test that different seeds produce different IDs."""
        id1 = generate_deterministic_id("app", 42)
        id2 = generate_deterministic_id("app", 43)

        assert id1 != id2

    def test_different_bases_produce_different_ids(self):
        """Test that different bases produce different IDs."""
        id1 = generate_deterministic_id("app", 42)
        id2 = generate_deterministic_id("user", 42)

        assert id1 != id2
        assert id1.startswith("app_")
        assert id2.startswith("user_")
