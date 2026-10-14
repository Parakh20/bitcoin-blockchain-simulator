"""Unit tests for the protocol primitives: keys, hashing, scripts, UTXO trie, blocks."""
import block_data
import helpers
import pow_mechanism
import settings
from script_engine import ScriptEngine
from transaction_data import Txn
from utxo_set import UtxoSet


def test_key_pair_is_secp256k1_hex():
    keys = helpers.generate_key_pair()
    assert len(keys["private"]) == 64  # 32-byte private key
    assert len(keys["public"]) == 128  # 64-byte uncompressed public key (x || y)


def test_hash160_and_double_sha256_lengths():
    assert len(helpers.compute_hash160("abc")) == 40
    assert len(helpers.compute_double_sha256("abc")) == 64


def test_invert_bytes_reverses_byte_order():
    assert helpers.invert_bytes("0a0b0c") == "0C0B0A"


def test_base58_round_trip():
    value = "00ff10a3b4"
    encoded = helpers.Base58Encoder.encode(value)
    assert set(encoded) <= set(helpers.ALPHABET)
    assert int(helpers.Base58Encoder.decode(encoded), 16) == int(value, 16)


def test_merkle_root_is_deterministic_and_order_sensitive():
    hashes = [helpers.compute_double_sha256(str(i)) for i in range(5)]
    root = helpers.compute_merkle_root(list(hashes))
    assert root == helpers.compute_merkle_root(list(hashes))
    assert root != helpers.compute_merkle_root(list(reversed(hashes)))
    assert helpers.compute_merkle_root([]) is None


def test_p2pkh_accepts_valid_signature_and_rejects_tampering():
    keys = helpers.generate_key_pair()
    other = helpers.generate_key_pair()
    message = "serialized-transaction"
    pub_key_script = helpers.generate_pub_key_script(keys["public"])
    script_sig = helpers.generate_signature_script(keys, message)

    assert ScriptEngine.execute_p2pkh(script_sig, pub_key_script, message)
    assert not ScriptEngine.execute_p2pkh(script_sig, pub_key_script, "tampered")
    other_script = helpers.generate_pub_key_script(other["public"])
    assert not ScriptEngine.execute_p2pkh(script_sig, other_script, message)


def test_coinbase_txn_pays_mining_reward_to_miner():
    keys = helpers.generate_key_pair()
    txn = Txn.create_coinbase_txn(keys)
    assert len(txn.inputs) == 1
    assert txn.outputs[0].amount == settings.MINING_REWARD
    assert txn.outputs[0].locking_script == helpers.generate_pub_key_script(keys["public"])
    assert txn.transaction_id == txn.clone().transaction_id


def test_utxo_trie_add_spend_and_restore_output():
    txn = Txn.create_coinbase_txn(helpers.generate_key_pair())
    utxos = UtxoSet(depth=2)

    utxos.add_transaction(txn)
    assert utxos.has_output(txn.transaction_id, 0)
    assert utxos.get_transaction(txn.transaction_id) is txn

    utxos.remove_output(txn.transaction_id, 0)
    assert not utxos.has_output(txn.transaction_id, 0)

    utxos.add_output(txn.transaction_id, 0)  # e.g. undone during a reorg
    assert utxos.has_output(txn.transaction_id, 0)

    utxos.remove_transaction(txn)
    assert utxos.get_transaction(txn.transaction_id) is False


def test_proof_of_work_finds_hash_below_target():
    keys = helpers.generate_key_pair()
    block = block_data.MinedBlock([Txn.create_coinbase_txn(keys)], "0" * 64)
    pow_worker = pow_mechanism.ProofOfWork(block)

    nonce, result = 0, None
    while not isinstance(result, pow_mechanism.MiningResult):
        result = pow_worker.mine(nonce)
        if isinstance(result, tuple):  # progress checkpoint, keep going
            nonce = result[0]

    assert result.block_hash < pow_worker.target
    assert result.block_hash.startswith("0" * block.difficulty_bits)
    assert result.block_hash == pow_worker.calculate_block_hash(result.nonce)
