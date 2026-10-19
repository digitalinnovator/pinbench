from semver_range import satisfies


def test_sample():
    assert satisfies("1.4.0", "^1.2.3")
    assert not satisfies("2.0.0", ">=1.0.0 <2.0.0")
