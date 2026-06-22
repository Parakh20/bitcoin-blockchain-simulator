const feedEl = document.getElementById('feed');
const treeEl = document.getElementById('tree');
const miningEl = document.getElementById('mining');

// height (int) -> array of { hash, parent, txns }
const blocksByHeight = {};

// node (pub_key_hash) -> { height, nonce, hash, target, hashrate,
//                          lastNonce, lastTimestamp, won, wonNonce, wonHash, wonMerkleRoot }
const miningByNode = {};
// preserves first-seen order of nodes for stable card ordering
const nodeOrder = [];

const source = new EventSource('/events');

source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    if (event.type !== 'mining_progress') {
        appendToFeed(event);
    }

    if (event.type === 'block_mined' || event.type === 'block_received') {
        recordBlock(event);
        renderTree();
    }

    if (event.type === 'mining_progress') {
        recordMiningProgress(event);
        renderMining();
    }

    if (event.type === 'block_mined') {
        recordMiningWin(event);
        renderMining();
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

function ensureNodeTracked(node) {
    if (!miningByNode[node]) {
        miningByNode[node] = {
            height: null,
            nonce: null,
            hash: null,
            target: null,
            hashrate: null,
            lastNonce: null,
            lastTimestamp: null,
            won: false,
            wonNonce: null,
            wonHash: null,
            wonMerkleRoot: null,
        };
        nodeOrder.push(node);
    }
    return miningByNode[node];
}

function recordMiningProgress(event) {
    const entry = ensureNodeTracked(event.node);
    const now = Date.now();

    if (entry.lastNonce !== null && entry.lastTimestamp !== null) {
        const nonceDelta = event.nonce - entry.lastNonce;
        const secondsDelta = (now - entry.lastTimestamp) / 1000;
        if (secondsDelta > 0 && nonceDelta > 0) {
            entry.hashrate = nonceDelta / secondsDelta;
        }
    }

    entry.lastNonce = event.nonce;
    entry.lastTimestamp = now;
    entry.height = event.height;
    entry.nonce = event.nonce;
    entry.hash = event.hash;
    entry.target = event.target;
    entry.won = false;
}

function recordMiningWin(event) {
    const entry = ensureNodeTracked(event.node);
    entry.won = true;
    entry.wonNonce = event.nonce;
    entry.wonHash = event.hash;
    entry.wonMerkleRoot = event.merkle_root;
    entry.target = event.target;
    entry.height = event.height;
}

function renderMining() {
    miningEl.innerHTML = '';
    for (const node of nodeOrder) {
        const entry = miningByNode[node];
        const card = document.createElement('div');
        card.className = entry.won ? 'mining-card won' : 'mining-card';

        const hashrateText = entry.hashrate ? `${entry.hashrate.toFixed(0)} h/s` : '...';

        if (entry.won) {
            card.innerHTML = `
                <div class="mining-node">${short(node)}</div>
                <div class="mining-row"><span>won block</span><span>height ${entry.height}</span></div>
                <div class="mining-row"><span>nonce</span><span>${entry.wonNonce}</span></div>
                <div class="mining-row"><span>hash</span><span>${short(entry.wonHash)}</span></div>
                <div class="mining-row"><span>target</span><span>${short(entry.target)}</span></div>
                <div class="mining-row"><span>merkle root</span><span>${short(entry.wonMerkleRoot)}</span></div>
            `;
        } else {
            card.innerHTML = `
                <div class="mining-node">${short(node)}</div>
                <div class="mining-row"><span>height</span><span>${entry.height ?? '...'}</span></div>
                <div class="mining-row"><span>nonce</span><span>${entry.nonce ?? '...'}</span></div>
                <div class="mining-row"><span>hash</span><span>${short(entry.hash)}</span></div>
                <div class="mining-row"><span>target</span><span>${short(entry.target)}</span></div>
                <div class="mining-row"><span>hashrate</span><span>${hashrateText}</span></div>
            `;
        }

        miningEl.appendChild(card);
    }
}
