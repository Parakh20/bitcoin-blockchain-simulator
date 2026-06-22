import block_data
import event_bus
import miner_node
import p2p_network
import settings
import transaction_data


def reset_network():
    p2p_network.PeerNetwork.nodes = []
    p2p_network.PeerNetwork.address_map = {}


def bootstrap_two_funded_nodes():
    reset_network()
    p2p_network.PeerNetwork.initialize_nodes(num_nodes=2)
    miner_a, miner_b = p2p_network.PeerNetwork.nodes

    genesis = miner_node.Miner.generate_genesis_block(miner_a.keys)
    miner_a.receive_transaction_id((genesis.transactions[0].transaction_id, 0))

    for i, m in enumerate(p2p_network.PeerNetwork.nodes):
        p2p_network.PeerNetwork.address_map[m.pub_key_hash] = i
        m.store_genesis_block(genesis.clone())

    return miner_a, miner_b


def test_full_event_cycle(monkeypatch):
    monkeypatch.setattr(settings, "BITS", 1)
    miner_a, miner_b = bootstrap_two_funded_nodes()
    sub = event_bus.bus.subscribe()

    # 1. create_transaction publishes txn_created
    assert miner_a.create_transaction(miner_b.pub_key_hash, 5) is True
    txn_created = sub.get(timeout=1)
    assert txn_created == {
        "type": "txn_created",
        "from": miner_a.pub_key_hash,
        "to": miner_b.pub_key_hash,
        "amount": 5,
    }

    # 2. draining miner_a's own queue publishes txn_received
    miner_a.process_message_queue()
    txn_received = sub.get(timeout=1)
    assert txn_received["type"] == "txn_received"
    assert txn_received["node"] == miner_a.pub_key_hash

    # 3. mining the pending txn publishes block_mined
    pending_txn = miner_a.waiting_txn_pool[0]
    coinbase_txn = transaction_data.Txn.create_coinbase_txn(miner_a.keys)
    miner_a.current_block = block_data.MinedBlock(
        [coinbase_txn, pending_txn], miner_a.ledger.last_block_hash
    )
    miner_a.perform_proof_of_work()
    block_mined = sub.get(timeout=10)
    assert block_mined["type"] == "block_mined"
    assert block_mined["node"] == miner_a.pub_key_hash
    assert block_mined["hash"] == miner_a.current_block.block_hash
    assert block_mined["height"] == 1
    assert block_mined["txns"] == 2

    # 4. a peer receiving that block (on a fresh pair of nodes) publishes
    #    block_received -- isolated from the events asserted above.
    reset_network()
    miner_c, miner_d = bootstrap_two_funded_nodes()
    sub2 = event_bus.bus.subscribe()
    miner_c.create_transaction(miner_d.pub_key_hash, 5)
    miner_c.process_message_queue()
    pending = miner_c.waiting_txn_pool[0]
    coinbase = transaction_data.Txn.create_coinbase_txn(miner_c.keys)
    miner_c.current_block = block_data.MinedBlock(
        [coinbase, pending], miner_c.ledger.last_block_hash
    )
    miner_c.perform_proof_of_work()
    txn_created_2 = sub2.get(timeout=1)
    assert txn_created_2["type"] == "txn_created"
    txn_received_2 = sub2.get(timeout=1)
    assert txn_received_2["type"] == "txn_received"
    block_mined_2 = sub2.get(timeout=10)
    assert block_mined_2["type"] == "block_mined"

    miner_d.handle_incoming_block(miner_c.current_block.clone())
    block_received = sub2.get(timeout=1)
    assert block_received["type"] == "block_received"
    assert block_received["node"] == miner_d.pub_key_hash
    assert block_received["hash"] == miner_c.current_block.block_hash
    assert block_received["height"] == 1
    assert block_received["txns"] == 2
