import hashlib
import threading

from script_engine import ScriptEngine
from consensus import ConsensusMechanism
from helpers import compute_double_sha256
import settings

class Ledger:
    # Manages the blockchain ledger, including the UTXO set and block validation.
    def __init__(self, utxo_set, miner_node):
        self.utxo_set = utxo_set
        self.miner_node = miner_node

        self.last_block_hash = "0"*64
        self.consensus = ConsensusMechanism(orphan_threshold=3)

    def __str__(self):
        return self.consensus.print_tree(self.consensus.root)

    def display(self, padding=""):
        print(padding, self.utxo_set.display())

    def append_block(self, block, is_genesis=False):
        # Adds a block to the ledger.
        if is_genesis:
            self.last_block_hash = block.block_hash
            reorg_actions = self.consensus.add_block(block)
            if reorg_actions:
                print("[?] Error: No reorganization expected in genesis")
            
            # Genesis block special handling: remove inputs (none) and add outputs
            # Actually genesis has no inputs to remove usually, but following logic:
            for txn in block.transactions[1:]:
                for inp in txn.inputs:
                    self.utxo_set.remove_output(inp.transaction_id, inp.output_index)
            for txn in block.transactions:
                self.utxo_set.add_transaction(txn)

            self.refresh_transaction_pool(block.transactions[1:])
        else:
            if not self.validate_block(block):
                return False
            self.integrate_block(block)
        return True

    def validate_transaction(self, txn):
        # Verifies a transaction against the current UTXO set.
        total_input_amount = 0
        for inp in txn.inputs:
            if not self.utxo_set.has_output(inp.transaction_id, inp.output_index):
                return False
    
            output_txn = self.utxo_set.get_transaction(inp.transaction_id).outputs[inp.output_index]
            if not ScriptEngine.execute_p2pkh(
                inp.unlocking_script,
                output_txn.locking_script,
                inp.transaction_id
                ):
                return False

            total_input_amount += output_txn.amount 

        total_output_amount = 0.0
        for out in txn.outputs:
            total_output_amount += out.amount

        if total_output_amount > total_input_amount:
            return False

        return True

    def validate_block(self, block):
        # Validates a block's hash, merkle root, and transactions.
        serialized_header = block.serialize_header(block.nonce)
        
        # Verify block hash
        calculated_hash = compute_double_sha256(serialized_header)
        if not (calculated_hash == block.block_hash and 
            block.merkle_tree_root == block.calculate_merkle_root()):
            return False

        # Verify transactions
        # block.transactions[0] is coinbase [ASSUMPTION]
        coinbase_fees = 0.0
        for txn in block.transactions[1:]:
            input_amount = 0.0
            for inp in txn.inputs:
                if not self.utxo_set.has_output(inp.transaction_id, inp.output_index):
                    return False

                output_txn = self.utxo_set.get_transaction(inp.transaction_id).outputs[inp.output_index]
                if not ScriptEngine.execute_p2pkh(
                    inp.unlocking_script,
                    output_txn.locking_script,
                    inp.transaction_id
                    ):
                    return False

                input_amount += output_txn.amount 

            output_amount = 0.0
            for out in txn.outputs:
                output_amount += out.amount

            if output_amount > input_amount:
                return False
            coinbase_fees += (input_amount - output_amount)

        # Verify coinbase transaction
        coinbase = block.transactions[0]
        # Coinbase should have 1 input with dummy values and 1 output
        if not ((len(coinbase.inputs) == 1) and (int(coinbase.inputs[0].transaction_id, 16) == 0)
                        and (int(coinbase.inputs[0].output_index) == -1)
                        and (len(coinbase.outputs) == 1)):
            return False
        
        if coinbase.outputs[0].amount > coinbase_fees + settings.MINING_REWARD:
            return False

        return True

    def refresh_transaction_pool(self, confirmed_txns):
        # Removes confirmed transactions from the node's waiting pool.
        confirmed_map = {txn.transaction_id: True for txn in confirmed_txns}

        new_pool = []
        for txn in self.miner_node.waiting_txn_pool:
            if txn.transaction_id not in confirmed_map:
                new_pool.append(txn)

        self.miner_node.waiting_txn_pool = new_pool

    def integrate_block(self, block):
        # Adds the block to the chain and handles any reorgs.
        if block.previous_hash == self.last_block_hash:
            # Extending the main chain
            self.last_block_hash = block.block_hash
            reorg_actions = self.consensus.add_block(block)
            if reorg_actions:
                print("[?] Error: Chain can't be reorganized when new block adds in longest chain")
            
            for txn in block.transactions[1:]:
                for inp in txn.inputs:
                    self.utxo_set.remove_output(inp.transaction_id, inp.output_index)
            for txn in block.transactions:
                self.utxo_set.add_transaction(txn)

            self.refresh_transaction_pool(block.transactions[1:])
        else:
            # Fork detected
            reorg_actions = self.consensus.add_block(block)
            if reorg_actions:
                self.handle_reorg(reorg_actions)
            else:
                # Block added to side chain, no UTXO update needed yet
                pass

    def handle_reorg(self, reorg_actions):
        # Handles blockchain reorganization.
        # Removing blocks from the old main chain
        for block_node in reorg_actions['blocks_to_remove']:
            block = block_node.block
            for txn in block.transactions:
                self.utxo_set.remove_transaction(txn)

            for txn in block.transactions[1:]:
                for inp in txn.inputs:
                    self.utxo_set.add_output(inp.transaction_id, inp.output_index)

        # Adding blocks from the new main chain
        for block_node in reorg_actions['blocks_to_add']:
            block = block_node.block
            for txn in block.transactions[1:]:
                for inp in txn.inputs:
                    self.utxo_set.remove_output(inp.transaction_id, inp.output_index)
            
            for txn in block.transactions:
                self.utxo_set.add_transaction(txn)

    def redistribute_orphan_transactions(self):
        # Redistributes transactions from orphaned blocks.
        orphan_blocks = self.consensus.identify_orphans()
        if orphan_blocks:
            for block in orphan_blocks:
                for txn in block.transactions:
                    # Check if inputs are still valid
                    valid_inputs = True
                    for inp in txn.inputs:
                        if not self.utxo_set.has_output(inp.transaction_id, inp.output_index):
                            valid_inputs = False
                            break
                    
                    if valid_inputs:
                        # Redistribute to the network
                        self.miner_node.network.broadcast_transaction(txn, self.miner_node)

    def get_available_inputs(self, amount_needed):
        # Finds available inputs to satisfy a required amount.
        amount_found = 0
        input_txn_ids = []

        for (txnid, vout) in self.miner_node.received_transaction_ids:
            if self.utxo_set.has_output(txnid, vout):
                if amount_found >= amount_needed:
                    break
                amount_found += self.utxo_set.get_transaction(txnid).outputs[vout].amount
                input_txn_ids.append((txnid, vout))

        return input_txn_ids, amount_found
