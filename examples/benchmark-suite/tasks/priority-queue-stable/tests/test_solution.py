import sys

import pytest

sys.path.insert(0, "/app")
from pqueue import PriorityQueue  # noqa: E402


def make(*pairs):
    """Build a queue from (id, priority) pairs, pushed in the order given."""
    queue = PriorityQueue()
    for item_id, priority in pairs:
        queue.push({"id": item_id}, priority)
    return queue


def pop_ids(queue, count):
    return [queue.pop()["id"] for _ in range(count)]


def item_ids(queue):
    return [item["id"] for item in queue.items()]


# --- pop order, distinct priorities ---------------------------------------------------------


def test_pop_returns_lowest_priority_first():
    queue = make(("a", 5), ("b", 1), ("c", 3))
    assert pop_ids(queue, 3) == ["b", "c", "a"]


def test_int_float_and_negative_priorities():
    queue = make(("a", 0), ("b", -2.5), ("c", 1.5), ("d", -2), ("e", 1))
    assert pop_ids(queue, 5) == ["b", "d", "a", "e", "c"]


def test_pop_and_remove_return_the_pushed_object():
    first = {"id": "a", "payload": [1, 2]}
    second = {"id": "b", "payload": [3]}
    queue = PriorityQueue()
    queue.push(first, 2)
    queue.push(second, 1)
    assert queue.remove("a") is first
    assert queue.pop() is second


# --- remove and update, distinct priorities -------------------------------------------------


@pytest.mark.parametrize(("gone", "rest"), [("a", ["b", "c"]), ("b", ["a", "c"])])
def test_remove_takes_the_item_out(gone, rest):
    queue = make(("a", 1), ("b", 2), ("c", 3))
    assert queue.remove(gone) == {"id": gone}
    assert pop_ids(queue, 2) == rest


@pytest.mark.parametrize(
    ("item_id", "priority", "order"), [("c", 0, ["c", "a", "b"]), ("a", 2.5, ["b", "a", "c"])]
)
def test_update_changes_the_pop_order_and_returns_none(item_id, priority, order):
    queue = make(("a", 1), ("b", 2), ("c", 3))
    assert queue.update(item_id, priority) is None
    assert pop_ids(queue, 3) == order


def test_update_several_times_changes_the_order_but_not_len():
    queue = make(("a", 1), ("b", 2), ("c", 3))
    queue.update("a", 7)
    queue.update("c", 0)
    queue.update("a", 2.5)
    queue.update("b", 9)
    assert len(queue) == 3
    assert pop_ids(queue, 3) == ["c", "a", "b"]
    assert len(queue) == 0


# --- len ------------------------------------------------------------------------------------


def test_len_counts_items_in_the_queue():
    queue = PriorityQueue()
    assert len(queue) == 0
    for item_id, priority in [("a", 3), ("b", 1), ("c", 2)]:
        queue.push({"id": item_id}, priority)
    assert len(queue) == 3
    queue.pop()
    assert len(queue) == 2
    queue.remove("a")
    assert len(queue) == 1


# --- errors ---------------------------------------------------------------------------------


def test_pop_raises_index_error_when_the_queue_holds_no_items():
    with pytest.raises(IndexError):
        PriorityQueue().pop()
    queue = make(("a", 1), ("b", 2), ("c", 3))
    queue.remove("b")
    queue.pop()
    queue.remove("c")
    assert len(queue) == 0
    with pytest.raises(IndexError):
        queue.pop()


@pytest.mark.parametrize(
    ("method", "target"), [("remove", "never pushed"), ("remove", "a"), ("update", "b")]
)
def test_key_error_when_the_id_is_not_in_the_queue(method, target):
    queue = make(("a", 1), ("b", 2), ("c", 3))
    queue.remove("b")
    assert queue.pop()["id"] == "a"
    with pytest.raises(KeyError):
        if method == "remove":
            queue.remove(target)
        else:
            queue.update(target, 5)


# --- pushing an id again --------------------------------------------------------------------


def test_id_can_be_pushed_again_after_pop():
    queue = make(("a", 1), ("b", 5))
    assert queue.pop()["id"] == "a"
    again = {"id": "a", "round": 2}
    queue.push(again, 9)
    assert len(queue) == 2
    queue.update("a", 8)
    assert queue.pop()["id"] == "b"
    assert queue.pop() is again


def test_id_can_be_pushed_again_after_remove():
    queue = make(("a", 1), ("b", 5))
    queue.remove("a")
    again = {"id": "a", "round": 2}
    queue.push(again, 9)
    assert len(queue) == 2
    assert queue.pop()["id"] == "b"
    assert queue.remove("a") is again
    with pytest.raises(IndexError):
        queue.pop()


def test_push_of_an_id_already_in_the_queue_raises_value_error():
    queue = make(("a", 1), ("b", 2))
    with pytest.raises(ValueError):
        queue.push({"id": "a"}, 5)
    queue.update("b", 0)
    with pytest.raises(ValueError):
        queue.push({"id": "b"}, 0)


def test_failed_push_leaves_the_queue_unchanged():
    first = {"id": "a", "round": 1}
    queue = PriorityQueue()
    queue.push(first, 3)
    queue.push({"id": "b"}, 2)
    with pytest.raises(ValueError):
        queue.push({"id": "a", "round": 2}, 1)
    assert len(queue) == 2
    assert queue.pop()["id"] == "b"
    assert queue.pop() is first
    with pytest.raises(IndexError):
        queue.pop()


# --- equal priorities -----------------------------------------------------------------------


def test_equal_priorities_pop_in_push_order():
    queue = make(("a", 2), ("b", 1), ("c", 2), ("d", 1), ("e", 2), ("f", 1))
    assert pop_ids(queue, 6) == ["b", "d", "f", "a", "c", "e"]


def test_equal_priorities_with_pops_removes_and_new_pushes_in_between():
    queue = make(("a", 1), ("b", 1), ("c", 1))
    assert queue.pop()["id"] == "a"
    queue.push({"id": "a"}, 1)
    queue.remove("b")
    queue.push({"id": "d"}, 1)
    queue.push({"id": "b"}, 1)
    assert len(queue) == 4
    assert pop_ids(queue, 4) == ["c", "a", "d", "b"]


def test_update_keeps_the_items_place_among_equal_priorities():
    queue = make(("a", 9), ("b", 5), ("c", 5), ("d", 1))
    queue.update("a", 5)
    queue.update("d", 5)
    assert pop_ids(queue, 4) == ["a", "b", "c", "d"]

    queue = make(("a", 5), ("b", 1), ("c", 5), ("d", 9), ("e", 5))
    queue.update("d", 5)
    queue.update("b", 5)
    assert pop_ids(queue, 5) == ["a", "b", "c", "d", "e"]


def test_update_away_and_back_keeps_the_items_place():
    queue = make(("a", 5), ("b", 5), ("c", 5))
    queue.update("a", 1)
    queue.update("a", 5)
    queue.update("c", 8)
    queue.update("b", 2)
    queue.update("c", 5)
    queue.update("b", 5)
    assert len(queue) == 3
    assert pop_ids(queue, 3) == ["a", "b", "c"]
    with pytest.raises(IndexError):
        queue.pop()


# --- items ----------------------------------------------------------------------------------


def test_items_lists_the_queue_in_pop_order():
    assert PriorityQueue().items() == []
    queue = make(("a", 1), ("b", 5), ("c", 3), ("d", 4), ("e", 2))
    listed = queue.items()
    assert isinstance(listed, list)
    assert [item["id"] for item in listed] == ["a", "e", "c", "d", "b"]


def test_items_gives_the_pushed_objects_and_leaves_the_queue_unchanged():
    first, second, third = {"id": "a"}, {"id": "b"}, {"id": "c"}
    queue = PriorityQueue()
    queue.push(first, 2)
    queue.push(second, 3)
    queue.push(third, 1)
    listed = queue.items()
    assert len(listed) == 3
    assert listed[0] is third and listed[1] is first and listed[2] is second
    assert item_ids(queue) == ["c", "a", "b"]
    assert len(queue) == 3
    assert pop_ids(queue, 3) == ["c", "a", "b"]
    assert queue.items() == []
    with pytest.raises(IndexError):
        queue.pop()


def test_items_with_equal_priorities_is_in_push_order():
    queue = make(("a", 2), ("b", 2), ("c", 1), ("d", 2), ("e", 1))
    assert item_ids(queue) == ["c", "e", "a", "b", "d"]
    assert pop_ids(queue, 5) == ["c", "e", "a", "b", "d"]


def test_items_after_remove_update_and_pop():
    queue = make(("a", 5), ("b", 5), ("c", 5), ("d", 1), ("e", 7))
    queue.remove("b")
    queue.update("c", 9)
    queue.update("c", 5)
    queue.update("a", 8)
    assert queue.pop()["id"] == "d"
    assert item_ids(queue) == ["c", "e", "a"]
    assert len(queue) == 3
    queue.update("a", 5)
    queue.update("e", 5)
    assert item_ids(queue) == ["a", "c", "e"]
    assert pop_ids(queue, 3) == ["a", "c", "e"]
    assert queue.items() == []
