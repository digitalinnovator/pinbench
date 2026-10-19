from pqueue import PriorityQueue


def test_remove_and_update():
    queue = PriorityQueue()
    queue.push({"id": "a"}, 3)
    queue.push({"id": "b"}, 1)
    queue.push({"id": "c"}, 2)
    assert queue.remove("c") == {"id": "c"}
    queue.update("a", 0)
    assert [queue.pop()["id"], queue.pop()["id"]] == ["a", "b"]
