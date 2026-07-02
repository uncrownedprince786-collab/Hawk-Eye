const API = '';
let coinPage = 1;

function formatPrice(p) {
    if (!p) return '--';
    if (p >= 1) return '$' + p.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
    return '$' + p.toFixed(6);
}
function formatLarge(n) {
    if (!n) return '--';
    if (n >= 1e12) return '$' + (n/1e12).toFixed(2) + 'T';
    if (n >= 1e9) return '$' + (n/1e9).toFixed(2) + 'B';
    if (n >= 1e6) return '$' + (n/1e6).toFixed(2) + 'M';
    return '$' + n.toLocaleString();
}
function formatChange(v) {
    if (v === null || v === undefined) return '--';
    const cls = v >= 0 ? 'positive' : 'negative';
    return `<span class="${cls}">${v>=0?'+':''}${v.toFixed(2)}%</span>`;
}
function sparklineSVG(prices) {
    if (!prices || prices.length < 2) return '';
    const min = Math.min(...prices), max = Math.max(...prices), range = max-min||1, w=120, h=40;
    const color = prices[prices.length-1] >= prices[0] ? '#0ecb81' : '#f6465d';
    const pts = prices.map((p,i) => `${(i/(prices.length-1))*w},${h-((p-min)/range)*h}`).join(' ');
    return `<svg width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}

// Landing Page
if (window.location.pathname === '/' || window.location.pathname === '') {
    function showSection(name) {
        document.querySelectorAll('.section').forEach(s => s.classList.add('hidden'));
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.getElementById(name + 'Section').classList.remove('hidden');
        event.target.classList.add('active');
        if (name === 'gainers') loadGainers();
        if (name === 'losers') loadLosers();
        if (name === 'stocks') loadStocks();
        if (name === 'news') loadNews();
    }
    window.showSection = showSection;

    async function loadCoins(page = 1) {
        try {
            const resp = await fetch(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=50&page=${page}&sparkline=true&price_change_percentage=1h,24h,7d`);
            const coins = await resp.json();
            const tbody = document.getElementById('coinTableBody');
            if (page === 1) tbody.innerHTML = '';
            tbody.innerHTML += coins.map((c,i) => `
                <tr>
                    <td>${(page-1)*50 + i + 1}</td>
                    <td><span class="coin-name" onclick="window.location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">${c.name}</span><span class="coin-symbol">${c.symbol.toUpperCase()}</span></td>
                    <td>${formatPrice(c.current_price)}</td>
                    <td>${formatChange(c.price_change_percentage_1h_in_currency)}</td>
                    <td>${formatChange(c.price_change_percentage_24h_in_currency)}</td>
                    <td>${formatChange(c.price_change_percentage_7d_in_currency)}</td>
                    <td>${formatLarge(c.total_volume)}</td>
                    <td>${formatLarge(c.market_cap)}</td>
                    <td>${sparklineSVG(c.sparkline_in_7d?.price)}</td>
                    <td><button class="trade-btn" onclick="window.location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">TRADE</button></td>
                </tr>
            `).join('');
        } catch(e) {
            document.getElementById('coinTableBody').innerHTML = '<tr><td colspan="10" class="loading-row">Failed. Retrying...</td></tr>';
            setTimeout(() => loadCoins(page), 5000);
        }
    }

    window.loadMoreCoins = function() { coinPage++; loadCoins(coinPage); };

    async function loadGainers() {
        try {
            const resp = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_desc&per_page=20&sparkline=false&price_change_percentage=24h');
            const coins = await resp.json();
            document.getElementById('gainersBody').innerHTML = coins.map((c,i) => `
                <tr><td>${i+1}</td><td><span class="coin-name" onclick="window.location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">${c.name}</span><span class="coin-symbol">${c.symbol.toUpperCase()}</span></td><td>${formatPrice(c.current_price)}</td><td>${formatChange(c.price_change_percentage_24h_in_currency)}</td><td>${formatLarge(c.total_volume)}</td><td>${formatLarge(c.market_cap)}</td></tr>
            `).join('');
        } catch(e) { document.getElementById('gainersBody').innerHTML = '<tr><td colspan="6">Failed.</td></tr>'; }
    }

    async function loadLosers() {
        try {
            const resp = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_asc&per_page=20&sparkline=false&price_change_percentage=24h');
            const coins = await resp.json();
            document.getElementById('losersBody').innerHTML = coins.map((c,i) => `
                <tr><td>${i+1}</td><td><span class="coin-name" onclick="window.location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">${c.name}</span><span class="coin-symbol">${c.symbol.toUpperCase()}</span></td><td>${formatPrice(c.current_price)}</td><td>${formatChange(c.price_change_percentage_24h_in_currency)}</td><td>${formatLarge(c.total_volume)}</td><td>${formatLarge(c.market_cap)}</td></tr>
            `).join('');
        } catch(e) { document.getElementById('losersBody').innerHTML = '<tr><td colspan="6">Failed.</td></tr>'; }
    }

    async function loadStocks() {
        const stocks = ['AAPL','MSFT','GOOGL','AMZN','NVDA','TSLA','META','JPM','V','JNJ','WMT','PG','MA','UNH','HD','BAC','DIS','NFLX','ADBE','CRM'];
        document.getElementById('stocksBody').innerHTML = '<tr><td colspan="7" class="loading-row">Loading stocks...</td></tr>';
        try {
            const symbols = stocks.join(',');
            const resp = await fetch(`https://api.coingecko.com/api/v3/simple/price?ids=&vs_currencies=usd`);
            let html = '';
            for (const sym of stocks) {
                try {
                    const r = await fetch(`https://finnhub.io/api/v1/quote?symbol=${sym}&token=d92fcnpr01qraam0nuigd92fcnpr01qraam0nuj0`);
                    const d = await r.json();
                    if (d.c) {
                        const change = d.dp || 0;
                        html += `<tr><td>${sym}</td><td><span class="coin-name" onclick="window.location.href='/coin?symbol=${sym}'">${sym}</span></td><td>$${d.c.toFixed(2)}</td><td>${formatChange(change)}</td><td>--</td><td>--</td><td>--</td></tr>`;
                    }
                } catch(e) {}
            }
            document.getElementById('stocksBody').innerHTML = html || '<tr><td colspan="7">Stock data unavailable.</td></tr>';
        } catch(e) { document.getElementById('stocksBody').innerHTML = '<tr><td colspan="7">Failed to load stocks.</td></tr>'; }
    }

    async function loadNews() {
        try {
            const resp = await fetch('https://newsdata.io/api/1/news?apikey=pub_1726eded7cae428f8533ca7ca5acd8da&q=crypto&language=en&size=12');
            const data = await resp.json();
            document.getElementById('newsGrid').innerHTML = data.results?.map(a => `
                <div class="news-card"><h3>${a.title}</h3><p>${(a.description||'').slice(0,200)}</p><small style="color:#848e9c;">${a.source_id} | ${new Date(a.pubDate).toLocaleDateString()}</small></div>
            `).join('') || '<p>No news available.</p>';
        } catch(e) { document.getElementById('newsGrid').innerHTML = '<p>Failed to load news.</p>'; }
    }

    async function loadStats() {
        try {
            const r = await fetch('https://api.coingecko.com/api/v3/global');
            const d = await r.json();
            document.getElementById('totalMcap').textContent = formatLarge(d.data.total_market_cap.usd);
            document.getElementById('totalVolume').textContent = formatLarge(d.data.total_volume.usd);
            document.getElementById('btcDom').textContent = d.data.market_cap_percentage.btc.toFixed(1) + '%';
        } catch(e) {}
        try {
            const r = await fetch('https://api.alternative.me/fng/?limit=1');
            const d = await r.json();
            document.getElementById('fearGreedVal').textContent = d.data[0].value + ' - ' + d.data[0].value_classification;
        } catch(e) {}
    }

    document.addEventListener('DOMContentLoaded', () => { loadCoins(); loadStats(); });
}

// Coin Detail Page
if (window.location.pathname === '/coin') {
    const params = new URLSearchParams(window.location.search);
    const symbol = params.get('symbol') || 'BTCUSDT';

    async function loadCoinData() {
        try {
            const resp = await fetch(API + '/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol })
            });
            const data = await resp.json();
            const snap = data.data_snapshot;
            if (!snap) return;
            const price = snap.price_data;
            document.getElementById('coinName').textContent = symbol;
            document.getElementById('coinPrice').textContent = formatPrice(price.price);
            const ch = price.change_pct || 0;
            document.getElementById('coinChange').innerHTML = (ch>=0?'+':'') + ch.toFixed(2) + '%';
            document.getElementById('coinChange').className = 'price-change ' + (ch>=0?'positive':'negative');
            const cg = snap.coingecko || {};
            document.getElementById('statHigh').textContent = formatPrice(cg.high_24h);
            document.getElementById('statLow').textContent = formatPrice(cg.low_24h);
            document.getElementById('statATH').textContent = formatPrice(cg.ath);
            document.getElementById('statATL').textContent = formatPrice(cg.atl);
            document.getElementById('statMCap').textContent = formatLarge(cg.market_cap);
            document.getElementById('statVol').textContent = formatLarge(cg.total_volume);
            document.getElementById('statSupply').textContent = cg.circ_supply ? (cg.circ_supply/1e6).toFixed(2)+'M' : '--';
            document.getElementById('statMaxSupply').textContent = cg.max_supply ? (cg.max_supply/1e6).toFixed(2)+'M' : 'Unlimited';
            const news = snap.news || [];
            document.getElementById('newsFeed').innerHTML = news.length ? news.map(n => `<div class="news-item"><div class="news-headline">${n.headline}</div><div class="news-summary">${n.summary}</div></div>`).join('') : '<p class="placeholder">No news</p>';
            const fg = snap.fear_greed || {};
            document.getElementById('sentimentData').innerHTML = `<div class="stat-row"><span>Fear & Greed</span><span>${fg.value||'--'} - ${fg.classification||'--'}</span></div>`;
            const tech = snap.technicals_1d || {};
            if (tech.recent_candles) drawChart(tech.recent_candles);
        } catch(e) { console.error(e); }
    }

    function drawChart(candles) {
        const canvas = document.getElementById('priceChart');
        if (!canvas) return;
        canvas.width = canvas.offsetWidth || 800;
        canvas.height = 350;
        const ctx = canvas.getContext('2d');
        const closes = candles.map(c => c.close);
        if (closes.length < 2) return;
        const min = Math.min(...closes)*0.999, max = Math.max(...closes)*1.001, range = max-min||1;
        ctx.fillStyle = '#0c0e11'; ctx.fillRect(0,0,canvas.width,canvas.height);
        ctx.beginPath(); ctx.strokeStyle = '#f0b90b'; ctx.lineWidth = 2;
        closes.forEach((c,i) => { const x = i*(canvas.width/(closes.length-1)), y = canvas.height-((c-min)/range)*(canvas.height-40)-20; i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
        ctx.stroke();
        ctx.fillStyle = '#eaecef'; ctx.font = '14px sans-serif';
        ctx.fillText('$'+closes[closes.length-1].toLocaleString(), 10, 30);
    }

    async function generateTradePlan() {
        document.getElementById('tradePlan').innerHTML = '<p class="placeholder">Generating...</p>';
        try {
            const resp = await fetch(API + '/analyze', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({symbol})
            });
            const data = await resp.json();
            document.getElementById('tradePlan').textContent = data.trade_plan || 'Failed.';
        } catch(e) { document.getElementById('tradePlan').innerHTML = '<p class="placeholder">Error.</p>'; }
    }

    window.generateTradePlan = generateTradePlan;
    window.loadChart = () => generateTradePlan();
    document.addEventListener('DOMContentLoaded', loadCoinData);
}

// Global Search
const searchInput = document.getElementById('globalSearch') || document.getElementById('coinSearch');
if (searchInput) {
    searchInput.addEventListener('input', async function() {
        const q = this.value.trim();
        if (q.length < 1) { const dd = document.getElementById('searchDropdown'); if(dd) dd.classList.add('hidden'); return; }
        try {
            const r = await fetch(`https://api.coingecko.com/api/v3/search?query=${q}`);
            const d = await r.json();
            const coins = d.coins?.slice(0,8) || [];
            const dd = document.getElementById('searchDropdown');
            if (!dd) return;
            dd.innerHTML = coins.map(c => `<div class="search-result" onclick="window.location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'"><span class="search-result-name">${c.name}</span><span class="search-result-symbol">${c.symbol.toUpperCase()}</span></div>`).join('');
            dd.classList.remove('hidden');
        } catch(e) {}
    });
}