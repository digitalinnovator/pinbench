from events import apply
from orders import Order


def test_pay_then_ship():
    order = Order(total=500)
    apply(order, {"type": "pay", "amount": 500})
    apply(order, {"type": "ship"})
    assert order.status == "shipped"
    assert order.paid == 500
    assert order.history == ["pay", "ship"]
