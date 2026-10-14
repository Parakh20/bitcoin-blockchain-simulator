import block_data
import helpers
import pow_mechanism
import transaction_data


def test_mine_returns_nonce_and_hash_tuple_at_checkpoint():
    keys = helpers.generate_key_pair()
    coinbase_txn = transaction_data.Txn.create_coinbase_txn(keys)
    block = block_data.MinedBlock([coinbase_txn], "0" * 64)

    pow_worker = pow_mechanism.ProofOfWork(block)
    pow_worker.target = "0" * 64  # impossible target: no hash can be lower

    result = pow_worker.mine(0)

    assert result == (1000, pow_worker.calculate_block_hash(1000))
