const API = '';

function formatPrice(price) {
    if (!price) return '--';
    if (price >= 1) return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return '$' + price.toFixed(6);
}

function formatLarge(num) {
    if (!num) return '--';
    if (num >= 1e12) return '$' + (num / 1e12).toFixed(2) + 'T';
    if (num >= 1e9) return '$' + (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return '$' + (num / 1e6).toFixed(2) + 'M';
    return '$' + num.toLocaleString();
}

function formatChange(val) {
    if (val === null || val === undefined) return '--';
    const cls = val >= 0 ? 'positive' : 'negative';
    return `<span class="${cls}">${val >= 0 ? '+' : ''}${val.toFixed(2)}%</span>`;
}

function drawSparkline(prices) {
    if (!prices || prices.length < 2) return '';
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const w = 120, h = 40;
    let svg = `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">`;
    svg += '<polyline points="';
    prices.forEach((p, i) => {
        const x = (i / (prices.length - 1)) * w;
        const y = h - ((p - min) / range) * h;
        svg += `${x},${y} `;
    });
    const color = prices[prices.length - 1] >= prices[0] ? '#0ecb81' : '#f6465d';
    svg += `" fill="none" stroke="${color}" stroke-width="1.5"/>`;
    svg += '</svg>';
    return svg;
}

function drawPriceChart(candles) {
    const canvas = document.getElementById('priceChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = 350;
    const closes = candles.map(c => c.close);
    if (closes.length < 2) return;
    const min = Math.min(...closes) * 0.999;
    const max = Math.max(...closes) * 1.001;
    const range = max - min || 1;
    const stepX = canvas.width / (closes.length - 1);

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.beginPath();
    ctx.strokeStyle = '#2b2f36';
    ctx.lineWidth = 0.5;
    for (let i = 1; i < 5; i++) {
        const y = (canvas.height / 5) * i;
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
    }
    ctx.stroke();

    ctx.beginPath();
    ctx.strokeStyle = '#f0b90b';
    ctx.lineWidth = 2;
    closes.forEach((value, index) => {
        const x = index * stepX;
        const y = canvas.height - ((value - min) / range) * (canvas.height - 40) - 20;
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
}

if (window.location.pathname === '/' || window.location.pathname === '') {
    async function loadCoins() {
        try {
            const resp = await fetch(API + '/api/coins');
            const coins = await resp.json();
            const tbody = document.getElementById('coinTableBody');
            tbody.innerHTML = coins.map((c, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td>
                        <span class="coin-name" onclick="window.location.href='/coin?symbol=${(c.symbol || '').toUpperCase()}USDT'">${c.name}</span>
                        <span class="coin-symbol">${(c.symbol || '').toUpperCase()}</span>
                    </td>
                    <td>${formatPrice(c.current_price)}</td>
                    <td>${formatChange(c.price_change_percentage_1h_in_currency)}</td>
                    <td>${formatChange(c.price_change_percentage_24h_in_currency)}</td>
                    <td>${formatChange(c.price_change_percentage_7d_in_currency)}</td>
                    <td>${formatLarge(c.total_volume)}</td>
                    <td>${formatLarge(c.market_cap)}</td>
                    <td><img src="${c.sparkline_in_7d?.price ? 'data:image/svg+xml,' + encodeURIComponent(drawSparkline(c.sparkline_in_7d.price)) : ''}" class="sparkline" alt="chart"></td>
                    <td><button class="trade-btn" onclick="window.location.href='/coin?symbol=${(c.symbol || '').toUpperCase()}USDT'">TRADE</button></td>
                </tr>
            `).join('');
        } catch (e) {
            document.getElementById('coinTableBody').innerHTML = '<tr><td colspan="10" class="loading-row">Failed to load data. Retrying...</td></tr>';
            setTimeout(loadCoins, 5000);
        }
    }

    async function loadStats() {
        try {
            const resp = await fetch('https://api.coingecko.com/api/v3/global');
            const data = await resp.json();
            const d = data.data;
            document.getElementById('totalMcap').textContent = formatLarge(d.total_market_cap.usd);
            document.getElementById('totalVolume').textContent = formatLarge(d.total_volume.usd);
            document.getElementById('btcDom').textContent = d.market_cap_percentage.btc.toFixed(1) + '%';
        } catch (e) {}

        try {
            const resp = await fetch('https://api.alternative.me/fng/?limit=1');
            const data = await resp.json();
            document.getElementById('fearGreedValue').textContent = data.data[0].value + ' - ' + data.data[0].value_classification;
        } catch (e) {}
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadCoins();
        loadStats();
    });
}

if (window.location.pathname === '/coin') {
    const params = new URLSearchParams(window.location.search);
    const symbol = params.get('symbol') || 'BTCUSDT';

    async function loadCoinData() {
        try {
            const resp = await fetch(API + '/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, type: 'auto' })
            });
            const data = await resp.json();
            const snap = data.data_snapshot;
            if (!snap) return;

            const price = snap.price_data || {};
            document.getElementById('coinName').textContent = symbol;
            document.getElementById('coinPrice').textContent = formatPrice(price.price);
            const change = price.change_pct;
            document.getElementById('coinChange').innerHTML = formatChange(change);
            document.getElementById('coinChange').className = 'price-change ' + (change >= 0 ? 'positive' : 'negative');

            const cg = snap.coingecko || {};
            document.getElementById('statHigh').textContent = formatPrice(price.high || cg.high_24h);
            document.getElementById('statLow').textContent = formatPrice(price.low || cg.low_24h);
            document.getElementById('statATH').textContent = formatPrice(cg.ath);
            document.getElementById('statATL').textContent = formatPrice(cg.atl);
            document.getElementById('statMCap').textContent = formatLarge(cg.market_cap);
            document.getElementById('statVol').textContent = formatLarge(price.volume || cg.total_volume);
            document.getElementById('statSupply').textContent = cg.circ_supply ? (cg.circ_supply / 1e6).toFixed(2) + 'M' : '--';
            document.getElementById('statMaxSupply').textContent = cg.max_supply ? (cg.max_supply / 1e6).toFixed(2) + 'M' : 'Unlimited';

            const news = snap.news || [];
            document.getElementById('newsFeed').innerHTML = news.map(n => `
                <div class="news-item">
                    <div class="news-headline">${n.headline}</div>
                    <div class="news-summary">${n.summary}</div>
                </div>
            `).join('') || '<p class="placeholder">No news available</p>';

            const fg = snap.fear_greed || {};
            document.getElementById('sentimentData').innerHTML = `
                <div class="stat-row"><span>Fear & Greed</span><span>${fg.value || '--'} - ${fg.classification || '--'}</span></div>
            `;

            const tech = snap.technicals || {};
            if (tech.current_price) {
                drawPriceChart([{ close: tech.current_price }, { close: tech.current_price }]);
            }
        } catch (e) {
            console.error(e);
        }
    }

    async function generateTradePlan() {
        document.getElementById('tradePlan').innerHTML = '<p class="placeholder">Generating analysis...</p>';
        try {
            const resp = await fetch(API + '/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, type: 'auto' })
            });
            const data = await resp.json();
            document.getElementById('tradePlan').textContent = data.trade_plan || 'Analysis failed.';
        } catch (e) {
            document.getElementById('tradePlan').innerHTML = '<p class="placeholder">Failed to generate plan. Try again.</p>';
        }
    }

    window.generateTradePlan = generateTradePlan;
    window.loadChart = function() { generateTradePlan(); };
    document.addEventListener('DOMContentLoaded', loadCoinData);
}

const searchInput = document.getElementById('globalSearch') || document.getElementById('coinSearch');
if (searchInput) {
    searchInput.addEventListener('input', async function(e) {
        const query = this.value.trim();
        if (query.length < 1) {
            const dropdown = document.getElementById('searchDropdown');
            if (dropdown) dropdown.classList.add('hidden');
            return;
        }
        try {
            const resp = await fetch(`https://api.coingecko.com/api/v3/search?query=${query}`);
            const data = await resp.json();
            const coins = data.coins?.slice(0, 8) || [];
            const dropdown = document.getElementById('searchDropdown');
            if (!dropdown) return;
            dropdown.innerHTML = coins.map(c => `
                <div class="search-result" onclick="window.location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">
                    <span class="search-result-name">${c.name}</span>
                    <span class="search-result-symbol">${c.symbol.toUpperCase()}</span>
                </div>
            `).join('');
            dropdown.classList.remove('hidden');
        } catch (e) {}
    });
}

