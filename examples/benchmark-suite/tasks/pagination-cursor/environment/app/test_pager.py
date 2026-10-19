from pager import fetch_page
from store import Store


def test_second_page_keeps_rows_with_the_same_created_at():
    store = Store()
    for id, created_at in [("a", 100), ("b", 200), ("c", 200), ("d", 200), ("e", 300)]:
        store.add(id, created_at)
    first, cursor = fetch_page(store, 2)
    second, _ = fetch_page(store, 2, cursor)
    assert [row["id"] for row in first] == ["a", "b"]
    assert [row["id"] for row in second] == ["c", "d"]
