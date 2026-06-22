# Live Browser Visualizer — Design

## Purpose

Run the existing blockchain simulator forever, with randomly generated transactions, while streaming live events (transactions created/received, blocks mined/received) to a browser page that shows a scrolling event feed and a live-updating block tree. Stops only when the process is killed (Ctrl+C).

## Non-goals

- No manual transaction injection from the browser (fully autonomous, per user decision).
- No persistence across restarts — state lives in memory for the life of the process, same as the existing `demo.py`/`simulation.py` scripts.
- No changes to consensus, mining, UTXO, or validation logic. This is purely an observability layer bolted onto the existing simulator.

## Architecture

### New files

| File | Purpose |
|---|---|
| `event_bus.py` | Thread-safe pub/sub. `EventBus.publish(event: dict)` fans the event out to all current subscribers. `EventBus.subscribe()` returns a new per-client `queue.Queue` that receives every event published after subscription. Implemented with a lock-protected list of subscriber queues — no external dependency. |
| `live_visualizer.py` | Entry point script. Bootstraps 5 `Miner` nodes via `PeerNetwork`, generates and distributes the genesis block, starts one daemon thread per miner (`mine_continuously`), starts one daemon thread running the random-transaction loop, and runs a Flask app in the main thread. |
| `templates/index.html` | Single HTML page: a left panel with a scrolling event feed, a right panel with the live block tree. Loads `static/app.js` and `static/style.css`. |
| `static/app.js` | Opens `new EventSource('/events')`. On each message, parses the JSON event, appends a line to the feed panel, and — for `block_mined`/`block_received` events — updates an in-memory JS model of the block tree and re-renders it. |
| `static/style.css` | Minimal layout/styling for the two panels. |

### Modified files

`miner_node.py` gains four one-line additions (no control-flow changes) that call `event_bus.publish(...)` at points where the script already prints a status line:

1. In `create_transaction`, after a transaction is successfully built — publish `{"type": "txn_created", "from": <pub_key_hash>, "to": <receiver_address>, "amount": <amount>}`.
2. In `handle_incoming_transaction` — publish `{"type": "txn_received", "node": <pub_key_hash>, "txn_id": <transaction_id>}`.
3. In `perform_proof_of_work`, after a block is successfully mined — publish `{"type": "block_mined", "node": <pub_key_hash>, "height": <consensus height>, "hash": <block_hash>, "parent": <previous_hash>, "txns": <len(transactions)>}`.
4. In `handle_incoming_block`, after a block is successfully appended — publish `{"type": "block_received", "node": <pub_key_hash>, "hash": <block_hash>, "parent": <previous_hash>, "txns": <len(transactions)>}`.

Existing `print()` statements and all return values/control flow are untouched. `demo.py`, `simulation.py`, `test_scenario_1.py`, `test_scenario_2.py` are unaffected — they don't import `event_bus` and continue to work exactly as before. Height for the `block_mined`/`block_received` event is read from `self.ledger.consensus.longest_chain_height` (already tracked by `ConsensusMechanism`) rather than added as new state.

`requirements.txt` gains one line: `flask`.

## Event flow

```
Miner threads (mine_continuously / process_message_queue)
        │  publish(event_dict)
        ▼
   event_bus (in-process, thread-safe queue fan-out)
        │  each SSE client has its own subscriber queue
        ▼
Flask /events endpoint (SSE, text/event-stream)
        │  one queue.get() loop per connected browser tab
        ▼
Browser EventSource → app.js → DOM updates
```

## Random transaction loop

A daemon thread runs forever:

1. Sleep a random interval between 3 and 8 seconds.
2. Pick a random sender node and a random different receiver node from `PeerNetwork.nodes`.
3. Pick a random amount between 1 and 5.
4. Call `sender.create_transaction(receiver.pub_key_hash, amount)`.
5. If it returns `False` (insufficient funds — `create_transaction` already guards against overspending), do nothing special; just loop again next tick.

No new validation logic is introduced — this reuses `Miner.create_transaction`, which already checks available UTXOs via `Ledger.get_available_inputs`.

## Web UI

- `GET /` — renders `templates/index.html`.
- `GET /events` — SSE endpoint. Subscribes to `event_bus`, then loops forever yielding `data: <json>\n\n` for each event pulled off its queue.
- Page layout: two panels side by side.
  - **Event feed** (left): newest event prepended to a scrolling `<ul>`, each line color-coded by event type (txn vs block).
  - **Block tree** (right): blocks grouped into rows by height; each block is a small box showing its short hash (first 10 chars), txn count, and a "parent: <short parent hash>" label underneath. New rows append as `block_mined`/`block_received` events arrive. No SVG connector lines — the parent-hash label is sufficient to read the tree structure, which keeps the renderer simple and avoids brittle layout math.

## Shutdown behavior

- All miner threads and the random-transaction thread are created with `daemon=True`.
- Flask's development server (`app.run()`) runs in the main thread, blocking.
- Ctrl+C raises `KeyboardInterrupt` in the main thread, Flask's server exits, the process exits, and daemon threads are torn down automatically by the interpreter. No explicit coordinated shutdown is needed because there is no persistent state to flush.

## Testing approach

- Manual verification: run `live_visualizer.py`, confirm the Flask server starts, open the page in a browser, confirm the event feed receives events within the first random-interval window, confirm at least one block appears in the tree panel within ~30 seconds (BITS=3 mining time observed in prior demo runs).
- Confirm Ctrl+C cleanly stops the process (no orphaned threads/hung process).
- Confirm `demo.py` and `simulation.py` still run correctly after the `miner_node.py` event-hook additions (regression check — same exit-0 verification used previously).
