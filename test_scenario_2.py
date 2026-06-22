import threading
import time
import sys

import settings
from p2p_network import PeerNetwork
import miner_node

def start_miner_thread(miner):
    miner.mine_continuously()

def main():
    # Expecting number of nodes as first argument (after arity which is handled in __main__)
    # But original code used sys.argv[1] for num_nodes in main(), but also sys.argv[1] for arity in __main__?
    # Original code:
    # if __name__ == '__main__':
    #     arity = int(sys.argv[1])
    #     config.arity = arity
    #     main()
    # def main():
    #     Network.create_nodes(num_nodes=int(sys.argv[1]))
    
    # This implies sys.argv[1] is used for BOTH arity and num_nodes? Or maybe the user meant to pass two args?
    # Let's assume sys.argv[1] is num_nodes based on main(), and maybe arity was intended to be a different arg or the same.
    # If I run `python test1.py 3`, arity=3 and num_nodes=3.
    
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
