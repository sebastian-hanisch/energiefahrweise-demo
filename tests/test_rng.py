"""SplitMix64 gegen die veröffentlichten Referenzwerte (Vigna, Seed 0); der Vektorstrom liefert dieselbe Folge wie der skalare Generator."""
import numpy as np

from efw_rng import SplitMix64, Stream


def test_splitmix64_reference_values_for_seed_zero():
    r = SplitMix64(0)
    assert [r.next() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_stream_equals_the_scalar_generator():
    scalar = SplitMix64(12345)
    stream = Stream(12345)
    assert [int(x) for x in stream.raw(6)] == [scalar.next() for _ in range(6)]
    assert [int(x) for x in stream.raw(3)] == [scalar.next() for _ in range(3)]                  # der Zähler setzt fort


def test_below_is_the_remainder_and_roughly_uniform():
    scalar = SplitMix64(7)
    assert Stream(7).below(1000, (5,)).tolist() == [scalar.below(1000) for _ in range(5)]
    draws = Stream(3).below(6, (6000,))
    assert set(draws.tolist()) == set(range(6)) and all(abs(int((draws == i).sum()) - 1000) < 120 for i in range(6))


def test_below_keeps_the_shape_and_the_integer_type():
    out = Stream(1).below(10, (2, 3, 4))
    assert out.shape == (2, 3, 4) and out.dtype == np.int64 and out.min() >= 0 and out.max() < 10
