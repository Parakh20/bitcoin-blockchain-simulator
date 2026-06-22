import miner_node

class PeerNetwork:
    # Simulates a P2P network with star topology.
    nodes  = [] 
    address_map = {} # pub_key_hash -> index in nodes

    def __init__(self):
        pass

    @staticmethod
    def add_node(n):
        PeerNetwork.nodes.append(n)

    @staticmethod
    def initialize_nodes(num_nodes):
        for i in range(num_nodes):
            PeerNetwork.nodes.append(miner_node.Miner())

    @staticmethod
    def broadcast_transaction(txn, src_node):
        for n in PeerNetwork.nodes:
            if n != src_node:
                n.send_message(("txn", txn))

    @staticmethod
    def broadcast_block(block, src_node):
        for n in PeerNetwork.nodes:
            if n != src_node:
                n.send_message(("block", block))

if __name__ == '__main__':
    pass