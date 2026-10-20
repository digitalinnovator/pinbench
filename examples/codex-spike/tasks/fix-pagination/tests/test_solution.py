import sys

import pytest

sys.path.insert(0, "/app")
from pagination import paginate  # noqa: E402

ITEMS = list(range(10))


def test_first_page():
    assert paginate(ITEMS, 1, 3) == [0, 1, 2]


def test_middle_page():
    assert paginate(ITEMS, 2, 3) == [3, 4, 5]


def test_last_partial_page():
    assert paginate(ITEMS, 4, 3) == [9]


def test_past_the_end():
    assert paginate(ITEMS, 5, 3) == []


@pytest.mark.parametrize(("page", "per_page"), [(0, 3), (-1, 3), (1, 0), (1, -2)])
def test_rejects_invalid_arguments(page, per_page):
    with pytest.raises(ValueError):
        paginate(ITEMS, page, per_page)
