from helpers import invert_bytes, compute_merkle_root
import pow_mechanism as proof_system
import settings

class MinedBlock:
    # Represents a block in the blockchain, containing transactions and metadata.
    def __init__(self, transactions=None, previous_hash="0"*64):
        if transactions is None:
            transactions = []
        self.transactions = transactions
        self.nonce = 0
        self.block_hash = ""
        self.previous_hash = previous_hash
        self.difficulty_bits = settings.BITS
        self.merkle_tree_root = self.calculate_merkle_root()

    def __str__(self):
        return (f"hash: {self.block_hash}\n"
                f"prev-hash: {self.previous_hash}\n"
                f"merkle_root: {self.merkle_tree_root}\n"
                f"nonce: {self.nonce}\n")

    def display(self, padding=""):
        # Prints the block details to stdout.
        print(f"{padding}##########---------- Block ----------##########")
        print(f"{padding}[@] Nonce : {self.nonce}")
        print(f"{padding}[@] Hash : {self.block_hash}")
        print(f"{padding}[@] Prev Block Hash : {self.previous_hash}")
        print(f"{padding}[@] Bits : {self.difficulty_bits}")
        print(f"{padding}[@] Merkle Root : {self.merkle_tree_root}")
        for txn in self.transactions:
            txn.display(padding + "    ")
        print()

    def update_block_info(self, previous_hash, transactions, nonce):
        # Updates the block with new information.
        self.block_hash = ""
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.nonce = nonce
        self.merkle_tree_root = self.calculate_merkle_root()

    def serialize_header(self, nonce):
        # Serializes the block header for hashing.
        serialized = invert_bytes(self.previous_hash)
        serialized += invert_bytes(self.merkle_tree_root)
        
        # Handle bits hex string
        bits_hex = hex(settings.BITS)[2:]
        if len(bits_hex) % 2 != 0:
            bits_hex = '0' + bits_hex
        serialized += invert_bytes(bits_hex)
        
        # Handle nonce hex string
        nonce_hex = hex(nonce)[2:]
        if len(nonce_hex) % 2 != 0:
            nonce_hex = '0' + nonce_hex
        serialized += invert_bytes(nonce_hex)
        
        return serialized

    def calculate_merkle_root(self):
        # Calculates the Merkle root of the transactions in the block.
        txn_hashes = [txn.transaction_id for txn in self.transactions]
        return compute_merkle_root(txn_hashes, settings.MERKLE_TREE_ARITY)

    def clone(self):
        # Creates a deep copy of the block.
        txn_clones = [txn.clone() for txn in self.transactions]
        new_block = MinedBlock(txn_clones, self.previous_hash)
        new_block.nonce = self.nonce
        new_block.block_hash = self.block_hash
        new_block.difficulty_bits = self.difficulty_bits
        new_block.merkle_tree_root = self.merkle_tree_root
        return new_block

    @staticmethod
    def generate_genesis(coinbase_txn):
        # Generates the genesis block.
        block = MinedBlock()
        block.update_block_info("0"*64, [coinbase_txn], 0)
        return block
