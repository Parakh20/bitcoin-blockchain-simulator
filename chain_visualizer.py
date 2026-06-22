class ChainVisualizer:
    # Renders the block tree tracked by ConsensusMechanism as an ASCII tree.

    @staticmethod
    def render(consensus):
        if consensus.root is None:
            print("[empty chain]")
            return
        print(ChainVisualizer._describe(consensus.root))
        ChainVisualizer._render_children(consensus.root, "")

    @staticmethod
    def _describe(node):
        block = node.block
        short_hash = (block.block_hash or "0" * 10)[:10]
        return f"[Height {node.height}] {short_hash}... | txns: {len(block.transactions)}"

    @staticmethod
    def _render_children(node, prefix):
        for i, child in enumerate(node.children):
            is_last = (i == len(node.children) - 1)
            branch = "└── " if is_last else "├── "
            print(f"{prefix}{branch}{ChainVisualizer._describe(child)}")

            extension = "    " if is_last else "│   "
            ChainVisualizer._render_children(child, prefix + extension)


if __name__ == '__main__':
    pass
