const feedEl = document.getElementById('feed');
const treeEl = document.getElementById('tree');

// height (int) -> array of { hash, parent, txns }
const blocksByHeight = {};

const source = new EventSource('/events');

source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    appendToFeed(event);

    if (event.type === 'block_mined' || event.type === 'block_received') {
        recordBlock(event);
        renderTree();
    }
};

function appendToFeed(event) {
    const li = document.createElement('li');
    li.className = event.type.startsWith('block') ? 'block' : 'txn';
    li.textContent = describeEvent(event);
    feedEl.insertBefore(li, feedEl.firstChild);
}

function describeEvent(event) {
    switch (event.type) {
        case 'txn_created':
            return `TXN CREATED  ${short(event.from)} -> ${short(event.to)}  amount=${event.amount}`;
        case 'txn_received':
            return `TXN RECEIVED by ${short(event.node)}  id=${short(event.txn_id)}`;
        case 'block_mined':
            return `BLOCK MINED by ${short(event.node)}  height=${event.height}  hash=${short(event.hash)}  txns=${event.txns}`;
        case 'block_received':
            return `BLOCK RECEIVED by ${short(event.node)}  height=${event.height}  hash=${short(event.hash)}  txns=${event.txns}`;
        default:
            return JSON.stringify(event);
    }
}

function short(value) {
    return value ? String(value).slice(0, 10) : '(none)';
}

function recordBlock(event) {
    const height = event.height;
    if (!blocksByHeight[height]) {
        blocksByHeight[height] = [];
    }
    const exists = blocksByHeight[height].some((b) => b.hash === event.hash);
    if (!exists) {
        blocksByHeight[height].push({ hash: event.hash, parent: event.parent, txns: event.txns });
    }
}

function renderTree() {
    treeEl.innerHTML = '';
    const heights = Object.keys(blocksByHeight).map(Number).sort((a, b) => a - b);
    for (const height of heights) {
        const row = document.createElement('div');
        row.className = 'tree-row';
        for (const block of blocksByHeight[height]) {
            const box = document.createElement('div');
            box.className = 'block-box';
            box.textContent = `h${height} ${short(block.hash)}... (txns:${block.txns}) parent:${short(block.parent)}...`;
            row.appendChild(box);
        }
        treeEl.appendChild(row);
    }
}
