# Bitcoin Blockchain Simulator

A Python implementation of the core mechanics of the Bitcoin protocol: ECDSA-based wallets, P2PKH script verification, Hashcash-style Proof of Work, an n-depth UTXO trie, Merkle-rooted blocks, and longest-chain consensus with reorganization — all driven by a multi-threaded, in-process peer network. It's built to be read end-to-end: every subsystem is a small, single-purpose module rather than a framework, so you can trace a transaction from signing through mining to UTXO settlement without jumping through abstraction layers.

## Architecture

| Module | Responsibility |
|---|---|
| `helpers.py` | ECDSA key generation, hash160/double-SHA256, Base58 encoding, Merkle root computation |
| `script_engine.py` | P2PKH script execution — signs and verifies transactions against `scriptPubKey` |
| `txn_input.py` / `txn_output.py` | Transaction input/output models and their Bitcoin-style serialization |
| `transaction_data.py` | `Txn` class: transaction ID derivation, serialization, coinbase transaction creation |
| `utxo_set.py` | UTXO set as an n-depth trie keyed on transaction ID, for sublinear lookup/spend tracking |
| `block_data.py` | `MinedBlock`: header serialization, Merkle root, genesis block construction |
| `pow_mechanism.py` | Proof-of-Work loop — searches for a nonce producing a hash below the difficulty target |
| `consensus.py` | Block tree, longest-chain selection, fork detection, and reorg/orphan bookkeeping |
| `chain_manager.py` | `Ledger`: block/transaction validation, UTXO settlement, reorg execution, mempool refresh |
| `p2p_network.py` | In-process star-topology network — transaction/block broadcast between nodes |
| `miner_node.py` | `Miner`: wallet, mining loop, message queue processing, wraps ledger + network + PoW |
| `chain_visualizer.py` | ASCII tree renderer for the consensus block tree (height, hash, tx count) |
| `event_bus.py` | Thread-safe pub/sub used to stream simulation events to the live browser visualizer |
| `live_visualizer.py` | Flask app: runs the simulator forever with random transactions, serves a live browser UI (event feed + block tree) over Server-Sent Events |
| `settings.py` | Tunable constants: PoW difficulty (`BITS`), mining reward, Merkle tree arity |
| `demo.py` | Spins up 3 nodes, mines blocks, broadcasts transactions, prints the final chain |
| `simulation.py`, `test_scenario_1.py`, `test_scenario_2.py` | Larger multi-node scenarios with more transactions and longer mining windows |

## Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python demo.py
```

The demo runs for about 30 seconds: it creates 3 miner nodes, distributes a genesis block, sends two transactions, lets the network mine them into blocks, then shuts down cleanly and prints the resulting chain.

## Live browser visualizer

`live_visualizer.py` runs the simulator indefinitely with 5 nodes and randomly generated transactions, and serves a live view in your browser:

```bash
python live_visualizer.py
```

Open `http://127.0.0.1:5000`. The left panel shows a live event feed (transactions and blocks as they happen); the right panel shows the block tree growing in real time. Press Ctrl+C in the terminal to stop.

## Example output

```
[*] Spinning up 3 miner nodes...
[*] Genesis block distributed to all nodes.
[*] Miners running. Broadcasting transactions...
T:  Thread-1 (start_miner_thread) [CREATED] [TXN]
T:  Thread-1 (start_miner_thread) [RECEIVED] [TXN]
T:  Thread-3 (start_miner_thread) [RECEIVED] [TXN]
T:  Thread-2 (start_miner_thread) [RECEIVED] [TXN]
##########---------- Block ----------##########
[@] Nonce : 54359
[@] Hash : 0000378980a270424a8b087d116b15177a082b97dd7023a3c22b14a480572082
[@] Prev Block Hash : 000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f
[@] Bits : 3
[@] Merkle Root : b8432e13d7e1490d9c90240a536b1cc258b495bdafd3917a26829321efb05588
    ...
T:  Thread-1 (start_miner_thread) [MINED] [BLOCK]
T:  Thread-2 (start_miner_thread) [RECEIVED] [BLOCK]
T:  Thread-3 (start_miner_thread) [RECEIVED] [BLOCK]
    ...
T:  Thread-2 (start_miner_thread) [MINED] [BLOCK]
    ...

[*] Final chain state (as seen by node 0):
[Height 0] 0000000000... | txns: 1
└── [Height 1] 0000378980... | txns: 2
    └── [Height 2] 00009a6eb0... | txns: 2
```

For larger, longer-running scenarios with more nodes and transactions, see `simulation.py`, `test_scenario_1.py`, and `test_scenario_2.py` (the latter accepts an optional node-count argument, e.g. `python test_scenario_2.py 5`).

## Design decisions

**UTXO trie over a flat map.** `utxo_set.py` indexes UTXOs by walking the first `depth` hex characters of a transaction ID into a trie, rather than keying a single dict on the full ID. This bounds the size of any one lookup bucket and is closer to how production UTXO databases (e.g. LevelDB-backed `chainstate`) shard by key prefix, at the cost of a small constant-depth tree walk per lookup instead of a single hash.

**Static difficulty, not an adjustment algorithm.** `settings.BITS` fixes the number of leading zero bits required in a block hash. Real Bitcoin retargets every 2016 blocks to hold a ~10 minute interval; this simulator runs far too few blocks for a retarget window to be meaningful, so difficulty is a tunable constant instead — raising `BITS` directly trades off demo runtime against PoW realism.

**Star-topology in-process network.** `p2p_network.py` broadcasts directly between `Miner` objects in the same process rather than using sockets. This keeps the consensus and validation logic (`chain_manager.py`, `consensus.py`) decoupled from any transport concern, so the same `Ledger`/`ConsensusMechanism` code would work unchanged behind a real network layer.

**Reorg as an explicit diff, not a rescan.** `ConsensusMechanism.add_block` walks up from the new block and the current chain head to their common ancestor and returns the exact `blocks_to_remove` / `blocks_to_add` sets. `Ledger.handle_reorg` applies that diff directly to the UTXO trie (re-adding spent outputs from the abandoned branch, removing outputs consumed by the new branch) instead of replaying the whole chain from genesis.
