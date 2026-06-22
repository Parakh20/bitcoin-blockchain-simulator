from collections import deque
from threading import Lock, current_thread
import time

import helpers
import block_data
import transaction_data
import txn_output
import txn_input
import p2p_network
from utxo_set import UtxoSet
from chain_manager import Ledger
from pow_mechanism import ProofOfWork

class Miner:
    # Represents a miner node in the network.
    def __init__(self):
        self.keys = helpers.generate_key_pair()
        self.pub_key_hash = helpers.compute_hash160(self.keys['public'])
        
        self.waiting_txn_pool = []
        self.lock = Lock()
        self.message_queue = deque()
        
        self.utxo_set = UtxoSet()
        self.ledger = Ledger(self.utxo_set, self)

        self.received_transaction_ids = []
        self.pow_worker = None
        self.is_running = True

    def __str__(self):
        return str(self.ledger)

    def display(self, padding=""):
        print(padding, "##########---------- Miner Node ----------##########")
        print(padding, f"[@] Private Key : {self.keys['private']}")
        print(padding, f"[@] Public Key : {self.keys['public']}")
        print(padding, f"[@] Pub Key Hash : {self.pub_key_hash}")

        print(padding, "[@] Ledger")
        self.ledger.display(padding + "    ")

    def mine_continuously(self):
        # Main mining loop.
        while self.is_running:
            if not self.waiting_txn_pool:
                time.sleep(5)
                self.process_message_queue()
                continue

            current_pool = self.waiting_txn_pool.copy()
            self.waiting_txn_pool = []

            coinbase_txn = transaction_data.Txn.create_coinbase_txn(self.keys)
            self.current_block = block_data.MinedBlock([coinbase_txn] + [txn for txn in current_pool], self.ledger.last_block_hash)
            self.perform_proof_of_work()

    def receive_transaction_id(self, txn_data):
        # Records a received transaction ID (for wallet tracking).
        self.received_transaction_ids.append(txn_data)

    def create_transaction(self, receiver_address, amount):
        # Creates and broadcasts a new transaction.
        outputs = []
        outputs.append(txn_output.TxnOutput(amount, receiver_address))
        
        input_txn_ids, total_amount = self.ledger.get_available_inputs(amount)
        if (not input_txn_ids) or (total_amount < amount):
            # Not enough funds
            return False
        
        is_change_output_self = False
        if total_amount > amount:
            is_change_output_self = True
            outputs.append(txn_output.TxnOutput(total_amount - amount, self.pub_key_hash))

        inputs = []
        for i in input_txn_ids:
            signature_script = helpers.generate_signature_script(self.keys, i[0])
            inputs.append(txn_input.TxnInput(i[0], i[1], signature_script))

        new_txn = transaction_data.Txn(inputs, outputs)
        
        with self.lock:
            self.message_queue.append(("txn", new_txn))

        if is_change_output_self:
            self.received_transaction_ids.append((new_txn.transaction_id, len(new_txn.outputs)-1))

        with self.lock:
            # Notify receiver (simulation shortcut)
            p2p_network.PeerNetwork.nodes[p2p_network.PeerNetwork.address_map[receiver_address]].receive_transaction_id((new_txn.transaction_id, 0))

        with self.lock:
            for n in p2p_network.PeerNetwork.nodes:
                if n != self:
                    n.message_queue.append(("txn", new_txn))
        return True

    @staticmethod
    def generate_genesis_block(keys):
        # Generates the genesis block.
        coinbase_txn = transaction_data.Txn.create_coinbase_txn(keys)
        genesis_block = block_data.MinedBlock.generate_genesis(coinbase_txn)

        genesis_block.previous_hash = "0"*64
        # Hardcoded hash for consistency in simulation
        genesis_block.block_hash = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"

        return genesis_block

    def store_genesis_block(self, genesis_block):
        # Stores the genesis block in the ledger.
        return self.ledger.append_block(genesis_block, is_genesis=True)

    def broadcast_transaction(self, txn):
        # Broadcasts a transaction to the network.
        p2p_network.PeerNetwork.broadcast_transaction(txn, self)

    def handle_incoming_transaction(self, txn):
        # Validates and adds a received transaction to the pool.
        is_valid = self.ledger.validate_transaction(txn)
        if not is_valid:
            print(f"T: {current_thread().name} TXN Invalid")
        self.waiting_txn_pool.append(txn)

    def perform_proof_of_work(self):
        # Performs Proof of Work for the current block.
        self.pow_worker = ProofOfWork(self.current_block)
        nonce = 0
        while True:
            result = self.pow_worker.mine(nonce)
            if isinstance(result, int):
                # Mining interrupted or paused to check messages
                nonce = result
                self.process_message_queue()
            else:
                # Mining successful or stopped
                break

        if result is None:
            return

        self.current_block.nonce = result.nonce
        self.current_block.block_hash = result.block_hash
        self.current_block.display()
        print("T: ", current_thread().name, "[MINED] [BLOCK]")
        self.ledger.append_block(self.current_block)
        p2p_network.PeerNetwork.broadcast_block(self.current_block, self)

    def process_message_queue(self):
        # Processes messages from the queue.
        while len(self.message_queue):
            with self.lock:
                msg_type, msg = self.message_queue.popleft()
            
            if msg_type == "txn":
                print("T: ", current_thread().name, "[RECEIVED] [TXN]")
                txn_copy = msg.clone()
                self.handle_incoming_transaction(txn_copy)
            elif msg_type == "block":
                print("T: ", current_thread().name, "[RECEIVED] [BLOCK]")
                block_copy = msg.clone()
                self.handle_incoming_block(block_copy)
            elif msg_type == "new_txn":
                print("T: ", current_thread().name, "[CREATED] [TXN]")
                receiver_address, amount = msg[0], msg[1]
                self.create_transaction(receiver_address, amount)

    def send_message(self, message):
        # Adds a message to the queue.
        with self.lock:
            self.message_queue.append(message)

    def handle_incoming_block(self, block):
        # Handles a received block.
        success = self.ledger.append_block(block)
        if not success:
            print("[?] Block validation failed or not added")
        else:
            if self.pow_worker is not None:
                self.pow_worker.stop_mining = True