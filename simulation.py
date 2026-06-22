import threading
import time
import sys

import settings
from p2p_network import PeerNetwork
import miner_node

def start_miner_thread(miner):
    miner.mine_continuously()

def main():
    PeerNetwork.initialize_nodes(num_nodes=3)
    genesis_block = miner_node.Miner.generate_genesis_block(PeerNetwork.nodes[0].keys)
    genesis_block.display()
    
    # Simulate receiving the genesis transaction
    PeerNetwork.nodes[0].receive_transaction_id((genesis_block.transactions[0].transaction_id, 0))

    # Distribute genesis block to all nodes
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

    # Simulate transactions
    lock = threading.Lock()

    def create_simulation_txn(from_index, to_index, amount):
        print("[****************------ CREATING-TXN-----************]")
        
        # Directly injecting message to simulate user action
        PeerNetwork.nodes[from_index].send_message(
            ("new_txn", (PeerNetwork.nodes[to_index].pub_key_hash, amount))
        )
        
        print("[#] From: ", PeerNetwork.nodes[from_index].pub_key_hash)
        print("[#] To: ", PeerNetwork.nodes[to_index].pub_key_hash)
        print("[+] Amount: ", amount)

    with lock:
        create_simulation_txn(0, 1, 10)
        create_simulation_txn(0, 2, 10)
    
    time.sleep(10)
    with lock:
        create_simulation_txn(1, 2, 5)
        create_simulation_txn(2, 0, 5)

    time.sleep(20)

    # Stop mining
    for miner in PeerNetwork.nodes:
        miner.is_running = False

    for miner in PeerNetwork.nodes:
        miner.display()
        print(miner)

    for t in threads:
        t.join()

if __name__ == '__main__':
    main()
