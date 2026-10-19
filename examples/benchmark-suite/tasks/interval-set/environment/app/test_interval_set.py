from interval_set import IntervalSet


def test_overlapping_adds_merge():
    s = IntervalSet()
    s.add(1, 4)
    s.add_text("2:6")
    assert s.intervals == [(1, 6)]
    assert s.contains(5)
    assert not s.contains(6)
