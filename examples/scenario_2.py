"""Configurable scenario: N nodes (default 5, minimum 5) and Merkle-tree arity N.

Usage: python examples/scenario_2.py [N]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
import time

import settings
from p2p_network import PeerNetwork
import miner_node

def start_miner_thread(miner):
    miner.mine_continuously()

def main():
    # The optional CLI argument sets both the node count (here) and the
    # Merkle-tree arity (in __main__), matching the original assignment script.
    try:
        num_nodes = int(sys.argv[1])
    except IndexError:
        # Default must be >= 5: the hardcoded simulated transactions below
        # reference node indices up to 4.
        num_nodes = 5

    PeerNetwork.initialize_nodes(num_nodes=num_nodes)
    genesis_block = miner_node.Miner.generate_genesis_block(PeerNetwork.nodes[0].keys)
    genesis_block.display()
    
    PeerNetwork.nodes[0].receive_transaction_id((genesis_block.transactions[0].transaction_id, 0))

    for i, miner in enumerate(PeerNetwork.nodes):
        PeerNetwork.address_map[miner.pub_key_hash] = i
        success = miner.store_genesis_block(genesis_block.clone())
        if not success:
            print("[*] Failed to add genesis block") 

    for miner in PeerNetwork.nodes:
        miner.display()

    threads = []
    for i in range(len(PeerNetwork.nodes)):
        threads.append(threading.Thread(target=start_miner_thread, args=(PeerNetwork.nodes[i], )))

    for t in threads:
        t.start()

    lock = threading.Lock()

    def create_simulation_txn(from_index, to_index, amount):
        print("[****************------ CREATING-TXN-----************]")
        PeerNetwork.nodes[from_index].send_message(
            ("new_txn", (PeerNetwork.nodes[to_index].pub_key_hash, amount))
        )
        print("[#] From: ", PeerNetwork.nodes[from_index].pub_key_hash)
        print("[#] To: ", PeerNetwork.nodes[to_index].pub_key_hash)
        print("[+] Amount: ", amount)

    with lock:
        create_simulation_txn(0, 1, 2)
        create_simulation_txn(0, 2, 10)
        create_simulation_txn(0, 3, 2)
        create_simulation_txn(0, 1, 2)
        create_simulation_txn(0, 4, 10)
        create_simulation_txn(0, 2, 2)
        create_simulation_txn(0, 0, 2)
        create_simulation_txn(0, 2, 2)
        create_simulation_txn(0, 2, 2)
        create_simulation_txn(0, 3, 2)

    time.sleep(20)

    for miner in PeerNetwork.nodes:
        miner.is_running = False

    for miner in PeerNetwork.nodes:
        print(miner.is_running)

    for t in threads:
        t.join()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        arity = int(sys.argv[1])
        settings.MERKLE_TREE_ARITY = arity
        print(f"Merkle Tree Arity set to: {settings.MERKLE_TREE_ARITY}")
    main()
