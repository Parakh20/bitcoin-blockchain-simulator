import queue

import event_bus


def test_subscribe_returns_a_queue():
    bus = event_bus.EventBus()
    sub = bus.subscribe()
    assert isinstance(sub, queue.Queue)


def test_publish_delivers_to_a_single_subscriber():
    bus = event_bus.EventBus()
    sub = bus.subscribe()
    bus.publish({"type": "txn_created"})
    assert sub.get(timeout=1) == {"type": "txn_created"}


def test_publish_fans_out_to_multiple_subscribers():
    bus = event_bus.EventBus()
    sub_a = bus.subscribe()
    sub_b = bus.subscribe()
    bus.publish({"type": "block_mined"})
    assert sub_a.get(timeout=1) == {"type": "block_mined"}
    assert sub_b.get(timeout=1) == {"type": "block_mined"}


def test_unsubscribe_stops_delivery():
    bus = event_bus.EventBus()
    sub = bus.subscribe()
    bus.unsubscribe(sub)
    bus.publish({"type": "block_mined"})
    assert sub.empty()


def test_module_level_bus_singleton_exists():
    assert isinstance(event_bus.bus, event_bus.EventBus)
