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
