# Mining Hash Computation Visualization — Design

## Goal

The existing live browser visualizer (`live_visualizer.py`, `templates/index.html`, `static/app.js`) only shows a coarse event feed and a block tree. It gives no insight into the actual proof-of-work process: nonce attempts, hash comparisons against the difficulty target, hashrate, or the fields that make up a winning block hash. This design adds a live, per-node mining detail panel that surfaces that process as it happens.

## Background

- `pow_mechanism.py`'s `ProofOfWork.mine(start_nonce)` already loops nonce attempts and returns early every 1000 nonces (as a bare `int`) so the caller can check for newly received blocks. That checkpoint value is currently discarded — never used for anything but resuming the loop.
- `settings.BITS = 3` (current difficulty) means a block typically takes only ~4096 hash attempts on average, so each node will emit a handful of progress checkpoints per block — a safe rate for SSE.
- `miner_node.py`'s `perform_proof_of_work()` already branches on `isinstance(result, int)` (progress) vs not (finished, a `MiningResult` or `None` if interrupted).
- `event_bus.py` is an existing thread-safe pub/sub hub; `live_visualizer.py`'s `/events` SSE route already streams every published event to every connected browser tab.

## Changes

### 1. `pow_mechanism.py` — checkpoint returns hash too

`mine()`'s periodic-checkpoint branch currently returns `nonce` alone:

```python
if nonce % 1000 == 0:
    return nonce
```

Change to return `(nonce, current_hash)`:

```python
if nonce % 1000 == 0:
    return (nonce, current_hash)
```

The 1000-nonce interval is unchanged (per explicit decision — no new constant).

### 2. `miner_node.py` — publish `mining_progress`, enrich `block_mined`

`perform_proof_of_work()`'s loop currently does:

```python
while True:
    result = self.pow_worker.mine(nonce)
    if isinstance(result, int):
        nonce = result
        self.process_message_queue()
    else:
        break
```

Change the progress branch to unpack the tuple and publish a `mining_progress` event before resuming:

```python
while True:
    result = self.pow_worker.mine(nonce)
    if isinstance(result, tuple):
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
        break
```

`self.ledger.consensus.longest_chain_height + 1` is the height this node is currently racing to mine (consistent with how `block_mined` reports `self.ledger.consensus.longest_chain_height` *after* `append_block`).

The existing `block_mined` publish in `perform_proof_of_work()` gains four fields so the browser can show why the winning hash qualifies:

```python
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
```

No change to `handle_incoming_block`'s `block_received` event — a receiving node didn't do the mining work, so it has no nonce-attempt history to show; the existing fields are sufficient there.

### 3. `static/app.js` — per-node mining state + hashrate

Add a `miningByNode` map (`pub_key_hash -> { nonce, hash, target, height, lastNonce, lastTimestamp, hashrate, lastBlockHash, lastBlockNonce, won }`), updated on two event types:

- `mining_progress`: update `nonce`, `hash`, `target`, `height`; compute hashrate from the delta against the previous `(nonce, timestamp)` pair for that node (`(nonce - lastNonce) / ((now - lastTimestamp) / 1000)` attempts/sec), then store the new pair for the next delta.
- `block_mined`: mark that node's entry as having just won (`won = true`, store `lastBlockHash`/`lastBlockNonce`/`target`/`merkle_root`), to drive a brief highlight; the panel keeps it showing the win until the node's next `mining_progress` event arrives for the next height.

Re-render the mining panel on every `mining_progress` and `block_mined` event, in addition to the existing feed/tree updates (no change to existing `appendToFeed`/`recordBlock`/`renderTree` logic).

### 4. `templates/index.html` / `static/style.css` — mining panel

Add a third panel (`#mining-panel`) alongside the existing feed and tree panels, containing one card per node (keyed by pub-key-hash, first-seen order). Each card shows:
- short node id
- height being raced for
- live nonce counter
- live hash attempt (truncated, monospace) next to the target (truncated, monospace) for visual hash-vs-target comparison
- computed hashrate (attempts/sec)
- a "won block N" highlight state showing the final qualifying hash, nonce, and merkle root when that node's `block_mined` fires

Cards are created lazily the first time a node's `mining_progress` or `block_mined` event is seen (nodes are not known up front by the browser). Styling reuses the existing dark/monospace aesthetic in `style.css`, adding a distinct highlight style (e.g. border/background flash) for the "just won" state.

## Data Flow

```
ProofOfWork.mine() checkpoint (nonce, hash)
  -> Miner.perform_proof_of_work() publishes "mining_progress"
  -> event_bus.bus (existing pub/sub)
  -> Flask /events SSE route (existing, unchanged)
  -> EventSource in app.js
  -> miningByNode[node] updated, mining panel re-rendered
```

```
ProofOfWork.mine() success -> MiningResult
  -> Miner.perform_proof_of_work() publishes enriched "block_mined"
  -> (same SSE path)
  -> miningByNode[node] marked won, mining panel shows final hash/target/nonce/merkle_root
  -> existing recordBlock()/renderTree() block-tree logic unchanged
```

## Testing

- `test_miner_events.py` (existing, covers `event_bus` publishes from `miner_node.py`) gets two additions:
  - assert a `mining_progress` event is published with `type`, `node`, `height`, `nonce`, `hash`, `target` keys present, during a mining run forced to take more than 1000 nonces (mock/force low difficulty target to guarantee a checkpoint fires before success — or directly unit-test the `(nonce, current_hash)` tuple return from `ProofOfWork.mine()` in isolation, which is simpler and doesn't depend on timing).
  - assert the existing `block_mined` event now also carries `nonce`, `bits`, `target`, `merkle_root`.
- No new test file — these are additions to the existing event-publishing test, consistent with how `block_mined`/`block_received`/`txn_created`/`txn_received` are already covered there.
- Manual verification: run `python live_visualizer.py`, open the browser, confirm the mining panel appears, updates live nonce/hash/hashrate per node, and highlights on each block win — same manual-check pattern used for the original visualizer (Task 6 of the prior plan).

## Out of Scope

- No change to mining performance, difficulty, or the 1000-nonce checkpoint interval (explicit decision).
- No persistence of mining history across page reloads — this is a live view only, consistent with the existing visualizer's scope.
- No change to `block_received` event fields — only the mining node has nonce-attempt data to show.
- No authentication/access control on the visualizer (matches existing scope — localhost-only, portfolio/demo project).
