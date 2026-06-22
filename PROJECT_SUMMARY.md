# Project Summary — Bitcoin Blockchain Simulator (for resume/portfolio extraction)

## One-line description
A from-scratch, multi-threaded simulation of core Bitcoin protocol mechanics (wallets, transactions, mining, consensus) in Python, with a live browser-based visualizer streaming real-time blockchain activity over Server-Sent Events.

## What it does
- Simulates a peer-to-peer Bitcoin network: multiple miner nodes generate wallets, broadcast and validate transactions, mine blocks via Proof-of-Work, and reach consensus on the longest chain — including fork detection and reorganization.
- Ships two ways to observe it: a CLI demo that prints an ASCII chain tree after a fixed run, and a live web dashboard (`live_visualizer.py`) that runs forever, generates random transactions autonomously, and streams every transaction/block event to a browser in real time via Server-Sent Events (SSE).

## Core technical components (one line each)
| Component | What it does |
|---|---|
| `helpers.py` | ECDSA (secp256k1) key generation, double-SHA256, hash160, Base58Check encoding, Merkle root computation |
| `script_engine.py` | P2PKH script execution — signs and cryptographically verifies transactions against a `scriptPubKey` |
| `transaction_data.py` / `txn_input.py` / `txn_output.py` | Transaction model: ID derivation, Bitcoin-style serialization, coinbase transaction construction |
| `utxo_set.py` | UTXO set implemented as an n-depth trie keyed on transaction ID prefix (not a flat map) for sharded, sublinear lookups |
| `block_data.py` | Block header construction, Merkle root calculation, genesis block generation |
| `pow_mechanism.py` | Hashcash-style Proof-of-Work — nonce search for a block hash below a difficulty target |
| `consensus.py` | Block tree management, longest-chain selection, fork/orphan detection, common-ancestor lookup for reorgs |
| `chain_manager.py` | Ledger: transaction/block validation, UTXO settlement, mempool refresh, reorg execution as an explicit diff (not a full rescan) |
| `p2p_network.py` | In-process star-topology network simulating peer broadcast of transactions and blocks |
| `miner_node.py` | `Miner` class — wallet, mining loop, message-queue processing; wires the above into one node |
| `event_bus.py` | Thread-safe pub/sub hub (lock-protected subscriber list of `queue.Queue`s) decoupling simulation threads from the web layer |
| `live_visualizer.py` | Flask app: bootstraps 5 miner nodes on daemon threads, runs an autonomous random-transaction generator thread, serves a live dashboard and an SSE endpoint |
| `static/app.js`, `templates/index.html` | Browser UI: live-scrolling event feed + a self-assembling block tree rendered from streamed events |

## Notable engineering decisions (good resume/interview talking points)
1. **UTXO trie over a flat hash map** — shards lookups by transaction-ID prefix, mirroring how production chain-state databases (e.g. LevelDB-backed UTXO sets) partition by key prefix, trading a small constant-depth walk for bounded bucket size.
2. **Reorg as an explicit diff, not a rescan** — on a chain-tip change, the consensus layer computes the exact `blocks_to_remove`/`blocks_to_add` sets between the old and new chain tips and applies only that diff to the UTXO set, instead of replaying the whole chain from genesis.
3. **Event-bus pattern for observability without invasive changes** — added a live web UI to an existing multi-threaded simulator by inserting four one-line `publish()` calls at points that already succeeded, with zero changes to control flow, return values, or existing `print()` statements — proven via full regression runs of the pre-existing CLI scripts after the change.
4. **SSE over WebSockets/polling** — chose Server-Sent Events for one-way server→browser event streaming: simpler than WebSockets for a unidirectional feed, no extra client library, and trivial to implement with a Flask generator response.
5. **Thread-safe fan-out pub/sub built from primitives** — `event_bus.py` uses a lock-protected list of per-subscriber `queue.Queue` objects rather than a pub/sub library, keeping the dependency surface minimal while remaining correctly thread-safe (lock is only held to snapshot subscribers, not during queue I/O, avoiding lock contention during fan-out).
6. **Daemon-thread lifecycle, no coordinated shutdown** — the live visualizer's miner threads and the random-transaction thread are all daemon threads; Ctrl+C is the only stop mechanism, deliberately avoiding shutdown-coordination complexity since there's no persistent state to flush.

## Development process used on this project
- Recovered and completed a partially-broken existing codebase (several core modules were referenced but missing) by reconciling against the author's own reference implementation, verifying byte-identical overlap before merging in the missing pieces.
- Found and fixed two real concurrency/runtime bugs through actual end-to-end execution (not just static review): a script that hung forever because a shutdown flag was never set, and a script that crashed with an `IndexError` due to a default argument that didn't match hardcoded test data.
- Designed the live-visualizer feature through a structured process: brainstormed requirements and constraints into a written design spec, turned the spec into a fully detailed implementation plan (every task fully specified, no placeholders), then executed the plan via a controller/subagent pattern — a fresh implementer per task, followed by an independent code-review pass per task (spec compliance + code quality), with all decisions and review verdicts logged before merging.
- One review cycle caught a genuine bug in the implementation plan's own test code (an event-queue draining/ordering bug in an integration test) before it was committed — fixed the test logic without touching the already-correct production code it was testing.

## Tech stack
Python 3, `ecdsa` (secp256k1 signing), `threading`/`queue` (concurrency, pub/sub), Flask (web server, SSE), vanilla JavaScript + CSS (browser UI, no frontend framework), `pytest` (testing), Git.

## Suggested resume bullet (example, edit to taste)
> Built a multi-threaded Bitcoin protocol simulator in Python (ECDSA wallets, P2PKH script verification, Proof-of-Work mining, UTXO-trie ledger, longest-chain consensus with reorg) and a live browser dashboard streaming real-time mining/transaction events over Server-Sent Events to 5 concurrently mining nodes.
