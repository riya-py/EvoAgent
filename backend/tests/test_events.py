import asyncio

import pytest

from app.events import ArenaEvent, EventBus, EventType


def _event(event_type=EventType.ROUND_STARTED, round_number=1, data=None):
    return ArenaEvent(type=event_type, round_number=round_number, data=data or {})


async def test_subscriber_receives_published_event():
    bus = EventBus()
    queue = bus.subscribe()

    await bus.publish(_event(data={"question": "Q1"}))

    received = queue.get_nowait()
    assert received.type == EventType.ROUND_STARTED
    assert received.data == {"question": "Q1"}


async def test_multiple_subscribers_all_receive_the_same_event():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()

    await bus.publish(_event(event_type=EventType.AGENT_STARTED))

    assert q1.get_nowait().type == EventType.AGENT_STARTED
    assert q2.get_nowait().type == EventType.AGENT_STARTED


async def test_unsubscribe_stops_further_delivery():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.unsubscribe(q1)

    await bus.publish(_event(event_type=EventType.ROUND_COMPLETED))

    assert q2.get_nowait().type == EventType.ROUND_COMPLETED
    with pytest.raises(asyncio.QueueEmpty):
        q1.get_nowait()


def test_unsubscribing_unknown_queue_is_a_no_op():
    bus = EventBus()
    stray_queue = asyncio.Queue()
    bus.unsubscribe(stray_queue)  # must not raise


async def test_no_subscribers_publish_is_a_no_op():
    bus = EventBus()
    await bus.publish(_event())  # must not raise, nothing to deliver to