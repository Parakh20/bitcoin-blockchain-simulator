from block_data import MinedBlock

class BlockNode:
    # Represents a node in the block tree (for consensus/fork resolution).
    def __init__(self, children=None, parent=None, height=0, block=None):
        if children is None:
            children = []
        self.children = children
        self.parent = parent
        self.height = height
        if block is None:
            self.block = MinedBlock()
        else:
            self.block = block

    def __str__(self):
        parent_hash = "0"*64 if self.parent is None else self.parent.block.block_hash
        s = f" p: {parent_hash} h: {self.height} id: {self.block.block_hash}"
        children_str = "\n\t".join([str(x) for x in self.children])
        s += f" child: -> \n{'\t'*(self.height+1)}[{children_str}]"
        return s

class ConsensusMechanism:
    # Manages the consensus rules, including longest chain selection and reorgs.
    def __init__(self, orphan_threshold):
        self.root = None
        self.orphan_threshold = orphan_threshold

        self.longest_chain_height = 0
        self.second_longest_head_height = 0
        self.longest_chain_head = None

    def add_block(self, block):
        # Adds a block to the tree and checks for reorgs.
        if block.previous_hash == "0"*64:
            self.root = BlockNode([], None, 0, block)
        else:
            return self._recursive_add(self.root, block)
        return []

    def _recursive_add(self, current_node, block):
        reorg_actions = []
        if current_node.block.block_hash == block.previous_hash:
            new_node = BlockNode([], current_node, current_node.height + 1, block)
            current_node.children.append(new_node)

            if current_node.height + 1 > self.longest_chain_height:
                self.longest_chain_height = current_node.height + 1

                if self.longest_chain_head is not None:
                    if self.longest_chain_head.block.block_hash != current_node.block.block_hash:
                        # Reorganization detected
                        common_ancestor = self.find_common_ancestor(new_node, self.longest_chain_head)
                        blocks_to_remove = self.get_path_nodes(common_ancestor, self.longest_chain_head)
                        blocks_to_add = self.get_path_nodes(common_ancestor, new_node)
                        
                        reorg_actions = {
                            'blocks_to_remove': blocks_to_remove,
                            'blocks_to_add': blocks_to_add
                        }
                        print("REORGANIZE DETECTED")
                        self.second_longest_head_height = self.longest_chain_head.height

                self.longest_chain_head = new_node
            
            return reorg_actions

        for child in current_node.children:
            result = self._recursive_add(child, block) 
            if result: # If reorg actions returned
                return result
        return reorg_actions

    def get_path_nodes(self, start_node, end_node):
        # Returns a list of nodes from end_node up to (but not including) start_node.
        nodes = []
        current = end_node
        while current.block.block_hash != start_node.block.block_hash:
            nodes.append(current)
            current = current.parent
        return nodes

    def identify_orphans(self):
        # Identifies orphan chains that can be pruned.
        end_block = self.longest_chain_head
        
        orphan_chains = []
        if (self.longest_chain_height - self.second_longest_head_height) > self.orphan_threshold:
            current = end_block
            while current.height > 0:
                if len(current.parent.children) > 1:
                    for child in current.parent.children:
                        if child.block.block_hash != current.block.block_hash:
                            orphan_chains.append(child)
                    # Prune the orphans from the tree
                    current.parent.children = [end_block]
                current = current.parent

        return self.flatten_chains(orphan_chains)

    def flatten_chains(self, chains):
        # Flattens a list of chain heads into a list of blocks.
        nodes = []
        for chain_head in chains:
            nodes.extend(self._collect_nodes(chain_head))
        return [n.block for n in nodes]

    def _collect_nodes(self, start_node):
        nodes = [start_node]
        for child in start_node.children:
            nodes.extend(self._collect_nodes(child))
        return nodes

    def find_common_ancestor(self, branch_a, branch_b):
        # Finds the common ancestor of two branches.
        branch_a_ids = []
        branch_b_ids = []

        ptr_a = branch_a
        ptr_b = branch_b
        
        while ptr_a.height > 0:
            if ptr_a.block.block_hash in branch_b_ids:
                return ptr_a
            elif ptr_b.block.block_hash in branch_a_ids:
                return ptr_b
            
            branch_a_ids.append(ptr_a.block.block_hash)
            branch_b_ids.append(ptr_b.block.block_hash)

            ptr_a = ptr_a.parent
            ptr_b = ptr_b.parent

        # Fallback if one reached root
        if ptr_a.height == 0:
            while ptr_b.height > 0:
                if ptr_b.block.block_hash in branch_a_ids:
                    return ptr_b
                ptr_b = ptr_b.parent

        # Should not happen if they share a genesis
        print("[?] Pointers reached root without common ancestor (should be genesis)")
        return self.root

    def print_tree(self, start_node):
        print(start_node)
        return ""

if __name__ == '__main__':
    pass