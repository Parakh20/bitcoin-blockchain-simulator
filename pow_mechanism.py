import sys
from helpers import compute_double_sha256

class MiningResult:
    # Stores the result of a successful mining attempt.
    def __init__(self, nonce, block_hash):
        self.nonce = nonce
        self.block_hash = block_hash

class ProofOfWork:
    # Handles the Proof of Work algorithm.
    def __init__(self, block):
        self.stop_mining = False
        self.block = block
        # Target is a number that the block hash must be less than.
        # We represent it as a string for comparison here, matching original logic.
        # The target is determined by the difficulty bits.
        self.target = "0" * block.difficulty_bits + "1" + "0" * (64 - block.difficulty_bits)

    def mine(self, start_nonce):
        # Attempts to find a nonce that results in a hash lower than the target.
        # Returns a MiningResult if successful, or the last checked nonce if interrupted.
        for nonce in range(start_nonce + 1, sys.maxsize):
            if self.stop_mining:
                return None 
            
            current_hash = self.calculate_block_hash(nonce)
            if current_hash < self.target:
                return MiningResult(nonce, current_hash)

            # Return progress every 1000 iterations to allow checking for new blocks
            if nonce % 1000 == 0:
                return nonce

    def calculate_block_hash(self, nonce):
        # Calculates the hash of the block header with the given nonce.
        return compute_double_sha256(self.block.serialize_header(nonce))

if __name__ == '__main__':
    pass