# Mining Hash Computation Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface live proof-of-work detail (nonce attempts, hash-vs-target comparison, hashrate, winning block fields) per miner node in the existing browser visualizer.

**Architecture:** `pow_mechanism.py`'s existing 1000-nonce checkpoint starts returning the attempted hash alongside the nonce; `miner_node.py` publishes that as a new `mining_progress` event and adds `nonce`/`bits`/`target`/`merkle_root` to the existing `block_mined` event; the browser's `app.js` tracks per-node mining state from those events (including a client-computed hashrate) and renders it into a new mining panel in `index.html`/`style.css`.

**Tech Stack:** Python (Flask, existing `event_bus` pub/sub), vanilla JS (`EventSource`/SSE, no framework), plain CSS — all consistent with the existing visualizer.

## Global Constraints

- The 1000-nonce checkpoint interval in `pow_mechanism.py` is unchanged — no new constant, no configurability (explicit decision in the design spec).
- No change to `block_received`'s event fields — only the mining node has nonce-attempt data to show.
- No persistence of mining history across page reloads (live view only).
- No authentication/access control changes (matches existing localhost-only, portfolio-project scope).

---

### Task 1: `pow_mechanism.py` checkpoint returns `(nonce, current_hash)`

**Files:**
- Modify: `pow_mechanism.py:32-33`
- Test: Create `test_pow_mechanism.py`

**Interfaces:**
- Consumes: nothing new — uses `ProofOfWork.__init__(block)`, `ProofOfWork.calculate_block_hash(nonce)` (both already exist, unchanged signatures).
- Produces: `ProofOfWork.mine(start_nonce)`'s periodic-checkpoint branch now returns `(nonce: int, current_hash: str)` instead of a bare `int`. Task 2's implementer relies on this exact tuple shape.

- [ ] **Step 1: Write the failing test**

```python
import block_data
import helpers
import pow_mechanism
import transaction_data


def test_mine_returns_nonce_and_hash_tuple_at_checkpoint():
    keys = helpers.generate_key_pair()
    coinbase_txn = transaction_data.Txn.create_coinbase_txn(keys)
    block = block_data.MinedBlock([coinbase_txn], "0" * 64)

    pow_worker = pow_mechanism.ProofOfWork(block)
    pow_worker.target = "0" * 64  # impossible target: no hash can be lower

    result = pow_worker.mine(0)

    assert result == (1000, pow_worker.calculate_block_hash(1000))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_pow_mechanism.py -v`
Expected: FAIL — `assert (1000, ...) == 1000` (current code returns a bare int)

- [ ] **Step 3: Write minimal implementation**

In `pow_mechanism.py`, the `mine` method currently ends:

```python
            # Return progress every 1000 iterations to allow checking for new blocks
            if nonce % 1000 == 0:
                return nonce
```

Change to:

```python
            # Return progress every 1000 iterations to allow checking for new blocks
            if nonce % 1000 == 0:
                return (nonce, current_hash)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_pow_mechanism.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pow_mechanism.py test_pow_mechanism.py
git commit -m "feat: return hash alongside nonce at mining checkpoint"
```

---

### Task 2: `miner_node.py` publishes `mining_progress`, enriches `block_mined`

**Files:**
- Modify: `miner_node.py:145-175` (`perform_proof_of_work`)
- Test: Modify `test_miner_events.py`

**Interfaces:**
- Consumes: Task 1's `ProofOfWork.mine(start_nonce)` returning `(nonce, current_hash)` at checkpoints; existing `self.pow_worker.target` (str), `self.ledger.consensus.longest_chain_height` (int), `self.current_block.{nonce, difficulty_bits, merkle_tree_root}` (all already exist on `MinedBlock`/`Ledger`).
- Produces: a new published event `{"type": "mining_progress", "node": str, "height": int, "nonce": int, "hash": str, "target": str}`; the existing `block_mined` event gains keys `nonce` (int), `bits` (int), `target` (str), `merkle_root` (str). Task 3's frontend code relies on these exact key names.

- [ ] **Step 1: Write the failing test**

Add to `test_miner_events.py` (uses the existing `bootstrap_two_funded_nodes` helper already defined in that file):

```python
def test_perform_proof_of_work_publishes_progress_and_enriched_block_mined(monkeypatch):
    monkeypatch.setattr(settings, "BITS", 1)
    miner_a, miner_b = bootstrap_two_funded_nodes()
    sub = event_bus.bus.subscribe()

    coinbase_txn = transaction_data.Txn.create_coinbase_txn(miner_a.keys)
    miner_a.current_block = block_data.MinedBlock(
        [coinbase_txn], miner_a.ledger.last_block_hash
    )

    fake_hash = "0" * 63 + "1"
    calls = {"count": 0}

    def fake_mine(self, start_nonce):
        calls["count"] += 1
        if calls["count"] == 1:
            return (1000, fake_hash)
        return pow_mechanism.MiningResult(1001, self.calculate_block_hash(1001))

    monkeypatch.setattr(pow_mechanism.ProofOfWork, "mine", fake_mine)

    miner_a.perform_proof_of_work()

    progress = sub.get(timeout=1)
    assert progress["type"] == "mining_progress"
    assert progress["node"] == miner_a.pub_key_hash
    assert progress["height"] == 1
    assert progress["nonce"] == 1000
    assert progress["hash"] == fake_hash
    assert "target" in progress

    block_mined = sub.get(timeout=1)
    assert block_mined["type"] == "block_mined"
    assert block_mined["nonce"] == 1001
    assert block_mined["bits"] == 1
    assert "target" in block_mined
    assert block_mined["merkle_root"] == miner_a.current_block.merkle_tree_root
```

Add `import pow_mechanism` to the top of `test_miner_events.py` alongside the existing imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_miner_events.py::test_perform_proof_of_work_publishes_progress_and_enriched_block_mined -v`
Expected: FAIL — no `mining_progress` event is ever published (the first `sub.get(timeout=1)` either times out or returns the eventual `block_mined` event instead)

- [ ] **Step 3: Write minimal implementation**

In `miner_node.py`, `perform_proof_of_work` currently reads:

```python
    def perform_proof_of_work(self):
        # Performs Proof of Work for the current block.
        self.pow_worker = ProofOfWork(self.current_block)
        nonce = 0
        while True:
            result = self.pow_worker.mine(nonce)
            if isinstance(result, int):
                # Mining interrupted or paused to check messages
                nonce = result
                self.process_message_queue()
            else:
                # Mining successful or stopped
                break

        if result is None:
            return

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

Change to:

```python
    def perform_proof_of_work(self):
        # Performs Proof of Work for the current block.
        self.pow_worker = ProofOfWork(self.current_block)
        nonce = 0
        while True:
            result = self.pow_worker.mine(nonce)
            if isinstance(result, tuple):
                # Mining interrupted or paused to check messages
                nonce, current_hash = result
                event_bus.bus.publish({
                    "type": "mining_progress",
                    "node": self.pub_key_hash,
                    "height": self.ledger.consensus.longest_chain_height + 1,
                    "nonce": nonce,
                    "hash": current_hash,
                    "target": self.pow_worker.target,
                })
                self.process_message_queue()
            else:
                # Mining successful or stopped
                break

        if result is None:
            return

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
            "nonce": self.current_block.nonce,
            "bits": self.current_block.difficulty_bits,
            "target": self.pow_worker.target,
            "merkle_root": self.current_block.merkle_tree_root,
        })
        p2p_network.PeerNetwork.broadcast_block(self.current_block, self)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_miner_events.py -v`
Expected: PASS (all tests in the file, including the pre-existing `test_full_event_cycle`)

- [ ] **Step 5: Commit**

```bash
git add miner_node.py test_miner_events.py
git commit -m "feat: publish mining_progress event and enrich block_mined payload"
```

---

### Task 3: Live mining panel in the browser UI

**Files:**
- Modify: `static/app.js`
- Modify: `templates/index.html:9-19`
- Modify: `static/style.css`

**Interfaces:**
- Consumes: SSE events from `/events` (unchanged route) — specifically the new `mining_progress` event and the enriched `block_mined` event from Task 2, both with the exact key names defined there.
- Produces: nothing consumed by later tasks (this is the final task).

- [ ] **Step 1: Add mining-panel markup**

In `templates/index.html`, the `#layout` div currently contains only `#feed-panel` and `#tree-panel`:

```html
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
```

Add a third panel after `#tree-panel`:

```html
    <div id="layout">
        <section id="feed-panel">
            <h2>Event Feed</h2>
            <ul id="feed"></ul>
        </section>
        <section id="tree-panel">
            <h2>Block Tree</h2>
            <div id="tree"></div>
        </section>
        <section id="mining-panel">
            <h2>Mining</h2>
            <div id="mining"></div>
        </section>
    </div>
```

- [ ] **Step 2: Add mining-panel styles**

In `static/style.css`, the `#feed-panel, #tree-panel` rule currently reads:

```css
#feed-panel, #tree-panel {
    flex: 1;
    background: #1b1b1b;
    border: 1px solid #333;
    padding: 0.5rem 1rem;
    height: 80vh;
    overflow-y: auto;
}
```

Change the selector to include the new panel, and append card styles at the end of the file:

```css
#feed-panel, #tree-panel, #mining-panel {
    flex: 1;
    background: #1b1b1b;
    border: 1px solid #333;
    padding: 0.5rem 1rem;
    height: 80vh;
    overflow-y: auto;
}
```

Append to the end of `static/style.css`:

```css
.mining-card {
    border: 1px solid #555;
    border-radius: 4px;
    padding: 0.4rem 0.6rem;
    margin-bottom: 0.5rem;
    background: #222;
    font-size: 0.8rem;
}

.mining-card .mining-node {
    color: #fc6;
    font-weight: bold;
}

.mining-card .mining-row {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
}

.mining-card.won {
    border-color: #6f6;
    background: #1a2e1a;
}
```

- [ ] **Step 3: Add mining state, hashrate, and render logic to `app.js`**

`static/app.js` currently reads:

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
```

Change the `source.onmessage` handler and add mining-panel logic:

```javascript
const feedEl = document.getElementById('feed');
const treeEl = document.getElementById('tree');
const miningEl = document.getElementById('mining');

// height (int) -> array of { hash, parent, txns }
const blocksByHeight = {};

// node (pub_key_hash) -> { height, nonce, hash, target, hashrate,
//                          lastNonce, lastTimestamp, won, wonNonce, wonHash, wonMerkleRoot }
const miningByNode = {};
// preserves first-seen order of nodes for stable card ordering
const nodeOrder = [];

const source = new EventSource('/events');

source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    appendToFeed(event);

    if (event.type === 'block_mined' || event.type === 'block_received') {
        recordBlock(event);
        renderTree();
    }

    if (event.type === 'mining_progress') {
        recordMiningProgress(event);
        renderMining();
    }

    if (event.type === 'block_mined') {
        recordMiningWin(event);
        renderMining();
    }
};
```

Add these new functions at the end of `static/app.js` (after the existing `renderTree` function):

```javascript
function ensureNodeTracked(node) {
    if (!miningByNode[node]) {
        miningByNode[node] = {
            height: null,
            nonce: null,
            hash: null,
            target: null,
            hashrate: null,
            lastNonce: null,
            lastTimestamp: null,
            won: false,
            wonNonce: null,
            wonHash: null,
            wonMerkleRoot: null,
        };
        nodeOrder.push(node);
    }
    return miningByNode[node];
}

function recordMiningProgress(event) {
    const entry = ensureNodeTracked(event.node);
    const now = Date.now();

    if (entry.lastNonce !== null && entry.lastTimestamp !== null) {
        const nonceDelta = event.nonce - entry.lastNonce;
        const secondsDelta = (now - entry.lastTimestamp) / 1000;
        if (secondsDelta > 0 && nonceDelta > 0) {
            entry.hashrate = nonceDelta / secondsDelta;
        }
    }

    entry.lastNonce = event.nonce;
    entry.lastTimestamp = now;
    entry.height = event.height;
    entry.nonce = event.nonce;
    entry.hash = event.hash;
    entry.target = event.target;
    entry.won = false;
}

function recordMiningWin(event) {
    const entry = ensureNodeTracked(event.node);
    entry.won = true;
    entry.wonNonce = event.nonce;
    entry.wonHash = event.hash;
    entry.wonMerkleRoot = event.merkle_root;
    entry.target = event.target;
    entry.height = event.height;
}

function renderMining() {
    miningEl.innerHTML = '';
    for (const node of nodeOrder) {
        const entry = miningByNode[node];
        const card = document.createElement('div');
        card.className = entry.won ? 'mining-card won' : 'mining-card';

        const hashrateText = entry.hashrate ? `${entry.hashrate.toFixed(0)} h/s` : '...';

        if (entry.won) {
            card.innerHTML = `
                <div class="mining-node">${short(node)}</div>
                <div class="mining-row"><span>won block</span><span>height ${entry.height}</span></div>
                <div class="mining-row"><span>nonce</span><span>${entry.wonNonce}</span></div>
                <div class="mining-row"><span>hash</span><span>${short(entry.wonHash)}</span></div>
                <div class="mining-row"><span>target</span><span>${short(entry.target)}</span></div>
                <div class="mining-row"><span>merkle root</span><span>${short(entry.wonMerkleRoot)}</span></div>
            `;
        } else {
            card.innerHTML = `
                <div class="mining-node">${short(node)}</div>
                <div class="mining-row"><span>height</span><span>${entry.height ?? '...'}</span></div>
                <div class="mining-row"><span>nonce</span><span>${entry.nonce ?? '...'}</span></div>
                <div class="mining-row"><span>hash</span><span>${short(entry.hash)}</span></div>
                <div class="mining-row"><span>target</span><span>${short(entry.target)}</span></div>
                <div class="mining-row"><span>hashrate</span><span>${hashrateText}</span></div>
            `;
        }

        miningEl.appendChild(card);
    }
}
```

- [ ] **Step 4: Run the full regression suite**

Run: `pytest -v`
Expected: all tests PASS, including Task 1's `test_pow_mechanism.py` and Task 2's additions to `test_miner_events.py`

- [ ] **Step 5: Manually verify the mining panel in a browser**

Run: `python live_visualizer.py`

Open `http://127.0.0.1:5000`. Confirm:
- A third "Mining" panel appears to the right of the event feed and block tree.
- Each node gets its own card, showing a live-updating nonce, hash attempt, and target.
- After a few seconds, a hashrate value appears on each card (not `...`).
- When a node mines a block, its card switches to the green "won" state showing the final nonce, hash, target, and merkle root, then returns to the live-attempt state once that node starts racing for the next height.

Press Ctrl+C to stop the server cleanly (matches existing SIGINT behavior — no change expected here).

- [ ] **Step 6: Commit**

```bash
git add static/app.js static/style.css templates/index.html
git commit -m "feat: add live per-node mining detail panel to browser visualizer"
```
