import sys

import pytest

sys.path.insert(0, "/app")
from semver_range import satisfies  # noqa: E402


@pytest.mark.parametrize(
    ("version", "spec", "expected"),
    [
        # plain comparators, combined with AND; parts compare as numbers
        ("1.10.0", "1.10.0 =1.10.0 <=1.10.0 >1.9.0", True),
        # x-ranges
        ("1.4.2", "1.x 1.4.x >=1.4.2", True),
        # tilde: below the next minor
        ("1.3.0", "~1.2.3", False),
        # caret: below the bump of the leftmost non-zero part
        ("0.2.9", "^0.2.3", True),
        ("0.3.0", "^0.2.3", False),
        ("0.0.4", "^0.0.3", False),
    ],
)
def test_ranges(version, spec, expected):
    assert satisfies(version, spec) is expected


@pytest.mark.parametrize(
    ("version", "spec", "expected"),
    [
        # a pre-release is lower than its release and still ordered by major.minor.patch first
        ("1.0.0-alpha", "<1.0.0", True),
        ("1.5.0-rc.1", ">=1.2.3", True),
        # numeric identifiers compare as numbers and sort below non-numeric ones
        ("1.0.0-rc.10", ">1.0.0-rc.9", True),
        ("1.0.0-2", "<1.0.0-10", True),
        ("1.0.0-alpha.1", "<1.0.0-alpha.beta", True),
        # fewer identifiers is lower; non-numeric identifiers compare as ASCII
        ("1.0.0-alpha", "<1.0.0-alpha.1", True),
        ("1.0.0-Beta", "<1.0.0-alpha", True),
        # N.x is >=N.0.0 <(N+1).0.0 and N.M.x is >=N.M.0 <N.(M+1).0
        ("1.0.0-alpha", "1.x", False),
        ("1.2.0-rc.1", "1.2.x", False),
    ],
)
def test_pre_release_ordering(version, spec, expected):
    assert satisfies(version, spec) is expected


@pytest.mark.parametrize(
    ("version", "spec"),
    [
        ("1.2", ">=1.0.0"),
        ("1.2.3", ""),
        # a spec is malformed if any of its comparators is
        ("1.0.0", ">=2.0.0 latest"),
        ("1.0.0", "<0.5.0 >=1.2"),
        # comparators are separated by single spaces
        ("1.2.3", "1.2.3  1.2.3"),
        # identifiers are non-empty and made of ASCII letters, digits and hyphens
        ("1.2.3-", "1.x"),
        ("1.2.3-a..b", "1.x"),
        ("1.2.3-a_b", "1.x"),
        # a number is 0 or digits not starting with 0
        ("1.02.3", "1.x"),
        ("1.0.0-rc.01", "<2.0.0"),
    ],
)
def test_malformed(version, spec):
    with pytest.raises(ValueError):
        satisfies(version, spec)
