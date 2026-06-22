import threading
import time

from p2p_network import PeerNetwork
import miner_node
from chain_visualizer import ChainVisualizer

NUM_NODES = 3
MINE_WINDOW_SECONDS = 15


def start_miner_thread(miner):
    miner.mine_continuously()


def main():
    print(f"[*] Spinning up {NUM_NODES} miner nodes...")
    PeerNetwork.initialize_nodes(num_nodes=NUM_NODES)

    genesis_block = miner_node.Miner.generate_genesis_block(PeerNetwork.nodes[0].keys)
    PeerNetwork.nodes[0].receive_transaction_id((genesis_block.transactions[0].transaction_id, 0))

    for i, miner in enumerate(PeerNetwork.nodes):
        PeerNetwork.address_map[miner.pub_key_hash] = i
        miner.store_genesis_block(genesis_block.clone())

    print("[*] Genesis block distributed to all nodes.")

    threads = [threading.Thread(target=start_miner_thread, args=(m,)) for m in PeerNetwork.nodes]
    for t in threads:
        t.start()

    print("[*] Miners running. Broadcasting transactions...")
    PeerNetwork.nodes[0].send_message(("new_txn", (PeerNetwork.nodes[1].pub_key_hash, 10)))
    time.sleep(MINE_WINDOW_SECONDS)

    PeerNetwork.nodes[1].send_message(("new_txn", (PeerNetwork.nodes[2].pub_key_hash, 5)))
    time.sleep(MINE_WINDOW_SECONDS)

    for miner in PeerNetwork.nodes:
        miner.is_running = False
    for t in threads:
        t.join()

    print("\n[*] Final chain state (as seen by node 0):")
    ChainVisualizer.render(PeerNetwork.nodes[0].ledger.consensus)


if __name__ == '__main__':
    main()
