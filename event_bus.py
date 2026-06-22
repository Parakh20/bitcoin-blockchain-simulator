import queue
import threading


class EventBus:
    # Thread-safe publish/subscribe hub for simulation events.

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = []

    def subscribe(self):
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event):
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)


bus = EventBus()


if __name__ == '__main__':
    pass
