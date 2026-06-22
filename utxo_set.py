class UtxoNode:
    # Node for the UTXO Trie.
    def __init__(self):
        self.children = {}
        self.end_list = {}

    def __repr__(self):
        return f"{self.children} {self.end_list}"

class UtxoSet:
    # Manages the Unspent Transaction Output (UTXO) set using a Trie structure.
    def __init__(self, depth=2):
        self.depth = depth
        self.root_node = UtxoNode()

    def add_transaction(self, txn, node=None, index=0):
        # Adds a transaction to the UTXO set.
        if index == 0:
            node = self.root_node

        if index == self.depth:
            # Store transaction and all its outputs as unspent initially
            node.end_list[txn.transaction_id] = {
                'vout': [x for x in range(len(txn.outputs))],
                'txn': txn
            }
            return

        char = txn.transaction_id[index]
        if char not in node.children:
            node.children[char] = UtxoNode()

        self.add_transaction(txn, node.children[char], index+1)

    def add_output(self, transaction_id, output_index, node=None, index=0):
        # Adds a specific output back to the UTXO set (e.g., during reorg).
        if index == 0:
            node = self.root_node

        if index == self.depth:
            if transaction_id in node.end_list:
                node.end_list[transaction_id]['vout'].append(output_index)
            return

        char = transaction_id[index]
        if char not in node.children:
            node.children[char] = UtxoNode()

        self.add_output(transaction_id, output_index, node.children[char], index+1)

    def has_output(self, transaction_id, output_index, node=None, index=0):
        # Checks if a specific output exists in the UTXO set.
        if index == 0:
            node = self.root_node

        if index == self.depth:
            if transaction_id in node.end_list:
                if output_index in node.end_list[transaction_id]['vout']:
                    return True
            return False

        char = transaction_id[index]
        if char not in node.children:
            return False

        return self.has_output(transaction_id, output_index, node.children[char], index+1)

    def get_transaction(self, transaction_id, node=None, index=0):
        # Retrieves a transaction by ID.
        if index == 0:
            node = self.root_node

        if index == self.depth:
            if transaction_id in node.end_list:
                return node.end_list[transaction_id]['txn']
            return False

        char = transaction_id[index]
        if char not in node.children:
            return False

        return self.get_transaction(transaction_id, node.children[char], index+1)

    def remove_output(self, transaction_id, output_index, node=None, index=0):
        # Removes a specific output from the UTXO set (marks as spent).
        if index == 0:
            node = self.root_node

        if index == self.depth:
            if transaction_id in node.end_list:
                if output_index in node.end_list[transaction_id]['vout']:
                    node.end_list[transaction_id]['vout'].remove(output_index)
            return

        char = transaction_id[index]
        if char not in node.children:
            return

        self.remove_output(transaction_id, output_index, node.children[char], index+1)

    def remove_transaction(self, txn, node=None, index=0):
        # Removes an entire transaction from the UTXO set.
        if index == 0:
            node = self.root_node
        if index == self.depth:
            if txn.transaction_id in node.end_list:
                node.end_list.pop(txn.transaction_id, None)
            return
        
        char = txn.transaction_id[index]
        if char not in node.children:
            return

        self.remove_transaction(txn, node.children[char], index+1)

    def display(self, node=None, index=0):
        # Prints the UTXO set content.
        if index == 0:
            node = self.root_node

        if index == self.depth:
            print(node.end_list)
            return

        for key in node.children:
            print(key, end=" -> ")
            self.display(node.children[key], index+1)

if __name__ == '__main__':
    pass