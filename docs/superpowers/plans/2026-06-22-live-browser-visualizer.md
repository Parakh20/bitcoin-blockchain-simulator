# Live Browser Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `live_visualizer.py` entry point that runs the existing Bitcoin simulator forever with randomly generated transactions, streaming live events to a browser page showing a scrolling event feed and a live-updating block tree, until the process is killed with Ctrl+C.

**Architecture:** A thread-safe in-process pub/sub (`event_bus.py`) is the single integration point between the simulator's existing threads and the web layer. `miner_node.py` gets four one-line `publish()` calls added at points where it already prints a status line — no control-flow changes. `live_visualizer.py` boots 5 miner nodes, starts their mining threads plus a random-transaction-generator thread (all daemon threads), and runs a Flask app in the main thread that serves a page and a Server-Sent-Events stream sourced from the event bus.

**Tech Stack:** Python 3, Flask (dev server, SSE via generator + `text/event-stream`), vanilla JS/HTML/CSS (no frontend framework or build step), pytest for the testable pure-logic pieces.

## Global Constraints

- No manual transaction injection from the browser — fully autonomous random transaction generation only.
- No persistence across restarts — in-memory state only, same as `demo.py`/`simulation.py`.
- No changes to consensus, mining, UTXO, or validation logic — this is an observability layer only.
- Existing `print()` statements in `miner_node.py` stay untouched; `demo.py`, `simulation.py`, `test_scenario_1.py`, `test_scenario_2.py` must keep working unmodified and unaffected.
- 5 miner nodes, fixed (not configurable via CLI).
- Random transaction interval: 3–8 seconds between attempts. Random amount: 1–5.
- Shutdown is Ctrl+C only — no coordinated graceful-shutdown logic; rely on daemon threads dying with the process.
- New dependencies added to `requirements.txt`: `flask`, `pytest`.

---

### Task 1: Event bus

**Files:**
- Create: `event_bus.py`
- Create: `test_event_bus.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `event_bus.EventBus` class with `.subscribe() -> queue.Queue`, `.unsubscribe(q: queue.Queue) -> None`, `.publish(event: dict) -> None`. Module-level singleton `event_bus.bus: EventBus`. Later tasks (`miner_node.py`, `live_visualizer.py`) call `event_bus.bus.publish(...)` and `event_bus.bus.subscribe()`/`.unsubscribe()`.

- [ ] **Step 1: Write the failing tests**

Create `test_event_bus.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest test_event_bus.py -v`
Expected: `ModuleNotFoundError: No module named 'event_bus'`

- [ ] **Step 3: Add pytest and flask to requirements.txt**

`requirements.txt` becomes:

```
ecdsa==0.19.2
flask
pytest
```

Run: `.venv/bin/pip install -r requirements.txt`

- [ ] **Step 4: Implement event_bus.py**

Create `event_bus.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest test_event_bus.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add event_bus.py test_event_bus.py requirements.txt
git commit -m "feat: add thread-safe event bus for simulation events"
```

---

### Task 2: Wire event publishing into the miner

**Files:**
- Modify: `miner_node.py:10` (imports), `miner_node.py:63-99` (`create_transaction`), `miner_node.py:121-126` (`handle_incoming_transaction`), `miner_node.py:128-150` (`perform_proof_of_work`), `miner_node.py:176-183` (`handle_incoming_block`)
- Create: `test_miner_events.py`

**Interfaces:**
- Consumes: `event_bus.bus` (Task 1).
- Produces: `Miner` now publishes 4 event types: `txn_created {from, to, amount}`, `txn_received {node, txn_id}`, `block_mined {node, height, hash, parent, txns}`, `block_received {node, height, hash, parent, txns}`. Later tasks (`live_visualizer.py` UI) consume these exact shapes.

- [ ] **Step 1: Write the failing integration test**

Create `test_miner_events.py`:

```python
import block_data
import event_bus
import miner_node
import p2p_network
import settings
import transaction_data


def reset_network():
    p2p_network.PeerNetwork.nodes = []
    p2p_network.PeerNetwork.address_map = {}


def bootstrap_two_funded_nodes():
    reset_network()
    p2p_network.PeerNetwork.initialize_nodes(num_nodes=2)
    miner_a, miner_b = p2p_network.PeerNetwork.nodes

    genesis = miner_node.Miner.generate_genesis_block(miner_a.keys)
    miner_a.receive_transaction_id((genesis.transactions[0].transaction_id, 0))

    for i, m in enumerate(p2p_network.PeerNetwork.nodes):
        p2p_network.PeerNetwork.address_map[m.pub_key_hash] = i
        m.store_genesis_block(genesis.clone())

    return miner_a, miner_b


def test_full_event_cycle(monkeypatch):
    monkeypatch.setattr(settings, "BITS", 1)
    miner_a, miner_b = bootstrap_two_funded_nodes()
    sub = event_bus.bus.subscribe()

    # 1. create_transaction publishes txn_created
    assert miner_a.create_transaction(miner_b.pub_key_hash, 5) is True
    txn_created = sub.get(timeout=1)
    assert txn_created == {
        "type": "txn_created",
        "from": miner_a.pub_key_hash,
        "to": miner_b.pub_key_hash,
        "amount": 5,
    }

    # 2. draining miner_a's own queue publishes txn_received
    miner_a.process_message_queue()
    txn_received = sub.get(timeout=1)
    assert txn_received["type"] == "txn_received"
    assert txn_received["node"] == miner_a.pub_key_hash

    # 3. mining the pending txn publishes block_mined
    pending_txn = miner_a.waiting_txn_pool[0]
    coinbase_txn = transaction_data.Txn.create_coinbase_txn(miner_a.keys)
    miner_a.current_block = block_data.MinedBlock(
        [coinbase_txn, pending_txn], miner_a.ledger.last_block_hash
    )
    miner_a.perform_proof_of_work()
    block_mined = sub.get(timeout=10)
    assert block_mined["type"] == "block_mined"
    assert block_mined["node"] == miner_a.pub_key_hash
    assert block_mined["hash"] == miner_a.current_block.block_hash
    assert block_mined["height"] == 1
    assert block_mined["txns"] == 2

    # 4. a peer receiving that block (on a fresh pair of nodes) publishes
    #    block_received -- isolated from the events asserted above.
    reset_network()
    miner_c, miner_d = bootstrap_two_funded_nodes()
    sub2 = event_bus.bus.subscribe()
    miner_c.create_transaction(miner_d.pub_key_hash, 5)
    miner_c.process_message_queue()
    pending = miner_c.waiting_txn_pool[0]
    coinbase = transaction_data.Txn.create_coinbase_txn(miner_c.keys)
    miner_c.current_block = block_data.MinedBlock(
        [coinbase, pending], miner_c.ledger.last_block_hash
    )
    miner_c.perform_proof_of_work()
    sub2.get(timeout=10)  # drain block_mined from miner_c

    miner_d.handle_incoming_block(miner_c.current_block.clone())
    block_received = sub2.get(timeout=1)
    assert block_received["type"] == "block_received"
    assert block_received["node"] == miner_d.pub_key_hash
    assert block_received["hash"] == miner_c.current_block.block_hash
    assert block_received["height"] == 1
    assert block_received["txns"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest test_miner_events.py -v`
Expected: FAIL — `sub.get(timeout=1)` raises `queue.Empty` (no events published yet)

- [ ] **Step 3: Add the import and the four publish calls to miner_node.py**

Add the import (after the existing `import p2p_network` line):

```python
import p2p_network
import event_bus
```

In `create_transaction`, add the publish call immediately before the final `return True`:

```python
        with self.lock:
            for n in p2p_network.PeerNetwork.nodes:
                if n != self:
                    n.message_queue.append(("txn", new_txn))

        event_bus.bus.publish({
            "type": "txn_created",
            "from": self.pub_key_hash,
            "to": receiver_address,
            "amount": amount,
        })
        return True
```

In `handle_incoming_transaction`, add the publish call after appending to the pool:

```python
    def handle_incoming_transaction(self, txn):
        # Validates and adds a received transaction to the pool.
        is_valid = self.ledger.validate_transaction(txn)
        if not is_valid:
            print(f"T: {current_thread().name} TXN Invalid")
        self.waiting_txn_pool.append(txn)
        event_bus.bus.publish({
            "type": "txn_received",
            "node": self.pub_key_hash,
            "txn_id": txn.transaction_id,
        })
```

In `perform_proof_of_work`, add the publish call after `self.ledger.append_block(...)` and before the broadcast:

```python
        self.current_block.nonce = result.nonce
        self.current_block.block_hash = result.block_hash
        self.current_block.display()
        print("T: ", current_thread().name, "[MINED] [BLOCK]")
        self.ledger.append_block(self.current_block)
        event_bus.bus.publish({
            "type": "block_mined",
            "node": self.pub_key_hash,
            "height": self.ledger.consensus.longest_chain_height,
            "hash": self.current_block.block_hash,
            "parent": self.current_block.previous_hash,
            "txns": len(self.current_block.transactions),
        })
        p2p_network.PeerNetwork.broadcast_block(self.current_block, self)
```

In `handle_incoming_block`, add the publish call in the success branch:

```python
    def handle_incoming_block(self, block):
        # Handles a received block.
        success = self.ledger.append_block(block)
        if not success:
            print("[?] Block validation failed or not added")
        else:
            event_bus.bus.publish({
                "type": "block_received",
                "node": self.pub_key_hash,
                "height": self.ledger.consensus.longest_chain_height,
                "hash": block.block_hash,
                "parent": block.previous_hash,
                "txns": len(block.transactions),
            })
            if self.pow_worker is not None:
                self.pow_worker.stop_mining = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest test_miner_events.py -v`
Expected: 1 passed

- [ ] **Step 5: Regression check — existing entry points still work**

Run: `timeout 60 .venv/bin/python demo.py; echo "EXIT: $?"`
Expected: `EXIT: 0`, output ends with the chain-tree printout (same shape as before these changes)

- [ ] **Step 6: Commit**

```bash
git add miner_node.py test_miner_events.py
git commit -m "feat: publish txn/block lifecycle events from Miner"
```

---

### Task 3: live_visualizer.py core (node bootstrap + random transactions, no web yet)

**Files:**
- Create: `live_visualizer.py`

**Interfaces:**
- Consumes: `event_bus.bus` (Task 1), `miner_node.Miner` (Task 2), `p2p_network.PeerNetwork`.
- Produces: `bootstrap_network() -> list[threading.Thread]`, `random_transaction_loop() -> None` (runs forever), `main() -> None`. Task 4 modifies `main()`'s tail end; the rest of this file is unchanged by later tasks.

- [ ] **Step 1: Write live_visualizer.py**

Create `live_visualizer.py`:

```python
import random
import threading
import time

import event_bus
import miner_node
from p2p_network import PeerNetwork

NUM_NODES = 5
MIN_INTERVAL_SECONDS = 3
MAX_INTERVAL_SECONDS = 8
MIN_AMOUNT = 1
MAX_AMOUNT = 5


def start_miner_thread(miner):
    miner.mine_continuously()


def bootstrap_network():
    # Creates NUM_NODES miner nodes, mines/distributes the genesis block,
    # and starts each miner's mining loop on its own daemon thread.
    PeerNetwork.initialize_nodes(num_nodes=NUM_NODES)

    genesis_block = miner_node.Miner.generate_genesis_block(PeerNetwork.nodes[0].keys)
    PeerNetwork.nodes[0].receive_transaction_id(
        (genesis_block.transactions[0].transaction_id, 0)
    )

    for i, miner in enumerate(PeerNetwork.nodes):
        PeerNetwork.address_map[miner.pub_key_hash] = i
        miner.store_genesis_block(genesis_block.clone())

    threads = []
    for miner in PeerNetwork.nodes:
        t = threading.Thread(target=start_miner_thread, args=(miner,), daemon=True)
        t.start()
        threads.append(t)
    return threads


def random_transaction_loop():
    # Forever: wait a random interval, then queue a random amount between
    # two random distinct nodes. Insufficient-funds attempts are silently
    # dropped by Miner.create_transaction itself.
    while True:
        time.sleep(random.uniform(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS))

        sender, receiver = random.sample(PeerNetwork.nodes, 2)
        amount = random.randint(MIN_AMOUNT, MAX_AMOUNT)
        sender.send_message(("new_txn", (receiver.pub_key_hash, amount)))


def main():
    print(f"[*] Bootstrapping {NUM_NODES} miner nodes...")
    bootstrap_network()

    print("[*] Starting random transaction generator...")
    threading.Thread(target=random_transaction_loop, daemon=True).start()

    print("[*] Network running. Press Ctrl+C to stop.")
    sub = event_bus.bus.subscribe()
    try:
        while True:
            event = sub.get()
            print(f"[EVENT] {event}")
    except KeyboardInterrupt:
        print("\n[*] Stopped.")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Verify it runs and produces events**

Run: `timeout 40 .venv/bin/python live_visualizer.py`
Expected: exit code 124 (the `timeout` command SIGTERMs it — that's expected here, not a failure). Before that, stdout shows `[*] Bootstrapping 5 miner nodes...`, `[*] Network running...`, and at least one `[EVENT] {'type': 'txn_created', ...}` line within the first ~8 seconds.

- [ ] **Step 3: Commit**

```bash
git add live_visualizer.py
git commit -m "feat: add live_visualizer entry point with random transaction loop"
```

---

### Task 4: Flask app + SSE endpoint

**Files:**
- Modify: `live_visualizer.py` (imports, add `app` + routes, replace `main()`'s console loop)
- Create: `templates/index.html` (minimal stub, replaced fully in Task 5)

**Interfaces:**
- Produces: `live_visualizer.app` (Flask instance), routes `GET /` and `GET /events` (SSE, `text/event-stream`, each line `data: <json>\n\n`).

- [ ] **Step 1: Add Flask imports and routes to live_visualizer.py**

Replace the top imports:

```python
import json
import random
import threading
import time

from flask import Flask, Response, render_template

import event_bus
import miner_node
from p2p_network import PeerNetwork
```

Add the Flask app and routes (after the constants, before `start_miner_thread`):

```python
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/events')
def events():
    def stream():
        sub = event_bus.bus.subscribe()
        try:
            while True:
                event = sub.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            event_bus.bus.unsubscribe(sub)

    return Response(stream(), mimetype='text/event-stream')
```

Replace `main()`'s tail (the `sub = event_bus.bus.subscribe()` console loop) with:

```python
def main():
    print(f"[*] Bootstrapping {NUM_NODES} miner nodes...")
    bootstrap_network()

    print("[*] Starting random transaction generator...")
    threading.Thread(target=random_transaction_loop, daemon=True).start()

    print("[*] Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop.")
    app.run(host='127.0.0.1', port=5000, threaded=True)
```

- [ ] **Step 2: Create the minimal template stub**

Create `templates/index.html`:

```html
<!DOCTYPE html>
<html>
<head><title>Bitcoin Simulator - Live</title></head>
<body>
<h1>Live Blockchain Simulator</h1>
<pre id="feed"></pre>
<script>
const feed = document.getElementById('feed');
const source = new EventSource('/events');
source.onmessage = (e) => {
    feed.textContent += e.data + "\n";
};
</script>
</body>
</html>
```

- [ ] **Step 3: Verify the server starts and streams events**

Run in background:
```bash
.venv/bin/python live_visualizer.py > /tmp/live_viz.log 2>&1 &
echo $! > /tmp/live_viz.pid
sleep 10
curl -s http://127.0.0.1:5000/ | head -5
curl -N --max-time 5 http://127.0.0.1:5000/events
kill $(cat /tmp/live_viz.pid)
```
Expected: the `curl /` call returns the HTML stub; the `curl /events` call prints one or more `data: {...}` lines within 5 seconds before the `--max-time` cutoff ends it.

- [ ] **Step 4: Commit**

```bash
git add live_visualizer.py templates/index.html
git commit -m "feat: serve live simulation events over SSE via Flask"
```

---

### Task 5: Full browser UI (event feed + block tree)

**Files:**
- Modify: `templates/index.html` (full page, replaces Task 4's stub)
- Create: `static/style.css`
- Create: `static/app.js`

**Interfaces:**
- Consumes: the SSE stream from Task 4 (`/events`), event shapes from Task 2.
- Produces: no new Python interfaces — this is the terminal UI layer.

- [ ] **Step 1: Replace templates/index.html with the full page**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bitcoin Simulator - Live</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <h1>Live Blockchain Simulator</h1>
    <div id="layout">
        <section id="feed-panel">
            <h2>Event Feed</h2>
            <ul id="feed"></ul>
        </section>
        <section id="tree-panel">
            <h2>Block Tree</h2>
            <div id="tree"></div>
        </section>
    </div>
    <script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
```

- [ ] **Step 2: Create static/style.css**

```css
body {
    font-family: monospace;
    background: #111;
    color: #eee;
    margin: 0;
    padding: 1rem;
}

#layout {
    display: flex;
    gap: 1rem;
}

#feed-panel, #tree-panel {
    flex: 1;
    background: #1b1b1b;
    border: 1px solid #333;
    padding: 0.5rem 1rem;
    height: 80vh;
    overflow-y: auto;
}

#feed {
    list-style: none;
    padding: 0;
    margin: 0;
}

#feed li {
    padding: 0.2rem 0;
    border-bottom: 1px solid #222;
}

#feed li.txn { color: #6cf; }
#feed li.block { color: #6f6; }

.tree-row {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
}

.block-box {
    border: 1px solid #555;
    border-radius: 4px;
    padding: 0.4rem 0.6rem;
    background: #222;
    font-size: 0.8rem;
}
```

- [ ] **Step 3: Create static/app.js**

```javascript
const feedEl = document.getElementById('feed');
const treeEl = document.getElementById('tree');

// height (int) -> array of { hash, parent, txns }
const blocksByHeight = {};

const source = new EventSource('/events');

source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    appendToFeed(event);

    if (event.type === 'block_mined' || event.type === 'block_received') {
        recordBlock(event);
        renderTree();
    }
};

function appendToFeed(event) {
    const li = document.createElement('li');
    li.className = event.type.startsWith('block') ? 'block' : 'txn';
    li.textContent = describeEvent(event);
    feedEl.insertBefore(li, feedEl.firstChild);
}

function describeEvent(event) {
    switch (event.type) {
        case 'txn_created':
            return `TXN CREATED  ${short(event.from)} -> ${short(event.to)}  amount=${event.amount}`;
        case 'txn_received':
            return `TXN RECEIVED by ${short(event.node)}  id=${short(event.txn_id)}`;
        case 'block_mined':
            return `BLOCK MINED by ${short(event.node)}  height=${event.height}  hash=${short(event.hash)}  txns=${event.txns}`;
        case 'block_received':
            return `BLOCK RECEIVED by ${short(event.node)}  height=${event.height}  hash=${short(event.hash)}  txns=${event.txns}`;
        default:
            return JSON.stringify(event);
    }
}

function short(value) {
    return value ? String(value).slice(0, 10) : '(none)';
}

function recordBlock(event) {
    const height = event.height;
    if (!blocksByHeight[height]) {
        blocksByHeight[height] = [];
    }
    const exists = blocksByHeight[height].some((b) => b.hash === event.hash);
    if (!exists) {
        blocksByHeight[height].push({ hash: event.hash, parent: event.parent, txns: event.txns });
    }
}

function renderTree() {
    treeEl.innerHTML = '';
    const heights = Object.keys(blocksByHeight).map(Number).sort((a, b) => a - b);
    for (const height of heights) {
        const row = document.createElement('div');
        row.className = 'tree-row';
        for (const block of blocksByHeight[height]) {
            const box = document.createElement('div');
            box.className = 'block-box';
            box.textContent = `h${height} ${short(block.hash)}... (txns:${block.txns}) parent:${short(block.parent)}...`;
            row.appendChild(box);
        }
        treeEl.appendChild(row);
    }
}
```

- [ ] **Step 4: Verify static assets are served**

Run in background:
```bash
.venv/bin/python live_visualizer.py > /tmp/live_viz.log 2>&1 &
echo $! > /tmp/live_viz.pid
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/static/style.css
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/static/app.js
kill $(cat /tmp/live_viz.pid)
```
Expected: both `curl` calls print `200`

- [ ] **Step 5: Manual browser verification**

Open `http://127.0.0.1:5000` in a browser while `live_visualizer.py` is running. Confirm within ~60 seconds: the event feed panel is actively appending new lines, and the block tree panel shows at least one box at height 1 with a sensible txn count.

- [ ] **Step 6: Commit**

```bash
git add templates/index.html static/style.css static/app.js
git commit -m "feat: build live event feed and block tree UI"
```

---

### Task 6: Final regression and shutdown verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm existing entry points still pass**

```bash
timeout 60 .venv/bin/python demo.py; echo "demo.py EXIT: $?"
timeout 100 .venv/bin/python simulation.py; echo "simulation.py EXIT: $?"
timeout 100 .venv/bin/python test_scenario_1.py; echo "test_scenario_1.py EXIT: $?"
timeout 100 .venv/bin/python test_scenario_2.py; echo "test_scenario_2.py EXIT: $?"
```
Expected: all four print `EXIT: 0`.

- [ ] **Step 2: Confirm the full pytest suite passes**

```bash
.venv/bin/python -m pytest test_event_bus.py test_miner_events.py -v
```
Expected: all tests pass.

- [ ] **Step 3: Confirm Ctrl+C shuts down cleanly**

```bash
.venv/bin/python live_visualizer.py > /tmp/live_viz_final.log 2>&1 &
PID=$!
sleep 15
kill -INT "$PID"
sleep 2
if kill -0 "$PID" 2>/dev/null; then
  echo "STILL RUNNING - FAIL"
else
  echo "STOPPED CLEANLY"
fi
```
Expected: `STOPPED CLEANLY`, and the process should be gone with no traceback in `/tmp/live_viz_final.log` (SIGINT to a Flask `app.run()` process is handled by Werkzeug directly, not by the `try/except KeyboardInterrupt` block — that block only wrapped the pre-Flask console loop in Task 3 and is no longer on the hot path after Task 4's `app.run()` call).

- [ ] **Step 4: Update README.md with the new entry point**

Add a row to the Architecture table in `README.md` (after the `chain_visualizer.py` row):

```
| `event_bus.py` | Thread-safe pub/sub used to stream simulation events to the live browser visualizer |
| `live_visualizer.py` | Flask app: runs the simulator forever with random transactions, serves a live browser UI (event feed + block tree) over Server-Sent Events |
```

Add a new section after "Install and run":

```markdown
## Live browser visualizer

`live_visualizer.py` runs the simulator indefinitely with 5 nodes and randomly generated transactions, and serves a live view in your browser:

\`\`\`bash
python live_visualizer.py
\`\`\`

Open `http://127.0.0.1:5000`. The left panel shows a live event feed (transactions and blocks as they happen); the right panel shows the block tree growing in real time. Press Ctrl+C in the terminal to stop.
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document the live browser visualizer"
```
