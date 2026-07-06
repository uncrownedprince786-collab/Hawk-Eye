var API = '', coinPage = 1;
var L = '<div class="loader w-5 h-5 border-2 border-gray-300 border-t-emerald-500 rounded-full mx-auto"></div>';
function fP(p) { return p ? (p >= 1 ? '$' + p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '$' + p.toFixed(6)) : '--'; }
function fL(n) { return n ? (n >= 1e12 ? '$' + (n / 1e12).toFixed(2) + 'T' : n >= 1e9 ? '$' + (n / 1e9).toFixed(2) + 'B' : n >= 1e6 ? '$' + (n / 1e6).toFixed(2) + 'M' : '$' + n.toLocaleString()) : '--'; }
function fC(v) { if (v == null) return '--'; var c = v >= 0 ? 'text-emerald-500' : 'text-red-500'; return '<span class="' + c + '">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '%</span>'; }
function spark(p, sym) {
  if (!p || p.length < 2) return '';
  var mn = Math.min.apply(null, p), mx = Math.max.apply(null, p), r = mx - mn || 1;
  if (sym && (sym.includes('USDT') || sym.includes('USDC') || sym.includes('BUSD') || sym.includes('DAI'))) {
    var mid = (mn + mx) / 2;
    mn = mid * 0.98; mx = mid * 1.02; r = mx - mn || 1;
  }
  var w = 120, h = 40;
  var first = p[0], last = p[p.length - 1];
  var cl = last >= first ? '#10b981' : '#ef4444';
  var pts = p.map(function (v, i) { return (i / (p.length - 1)) * w + ',' + (h - ((v - mn) / r) * h); }).join(' ');
  return '<svg width="' + w + '" height="' + h + '"><polyline points="' + pts + '" fill="none" stroke="' + cl + '" stroke-width="1.5"/></svg>';
}

if (location.pathname === '/' || location.pathname === '') {

  async function loadOverview() {
    try {
      var r = await fetch('https://api.coingecko.com/api/v3/global');
      var d = await r.json();
      var data = d.data;
      document.getElementById('totalMcap').textContent = fL(data.total_market_cap.usd);
      document.getElementById('totalVolume').textContent = fL(data.total_volume.usd);
      document.getElementById('btcDom').textContent = data.market_cap_percentage.btc.toFixed(1) + '%';
      document.getElementById('mcapCard').textContent = fL(data.total_market_cap.usd);
      document.getElementById('mcapChange').textContent = (data.market_cap_change_percentage_24h_usd ? data.market_cap_change_percentage_24h_usd.toFixed(2) + '%' : '--');
      document.getElementById('volCard').textContent = fL(data.total_volume.usd);
      document.getElementById('volChange').textContent = data.total_volume.usd_24h_change ? data.total_volume.usd_24h_change.toFixed(2) + '%' : '--';
    } catch (e) { }
    try {
      var r2 = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true');
      var btc = await r2.json();
      document.getElementById('btcPriceCard').textContent = fP(btc.bitcoin.usd);
      if (btc.bitcoin.usd_24h_change) {
        var ch = btc.bitcoin.usd_24h_change;
        document.getElementById('btcChange').textContent = (ch >= 0 ? '+' : '') + ch.toFixed(2) + '%';
        document.getElementById('btcChange').className = 'text-xs mt-1 ' + (ch >= 0 ? 'text-emerald-500' : 'text-red-500');
      }
    } catch (e) { }
    try {
      var r3 = await fetch('https://api.alternative.me/fng/?limit=1');
      var d3 = await r3.json();
      var fg = d3.data[0];
      document.getElementById('fearGreedFull').textContent = fg.value + ' - ' + fg.value_classification;
      document.getElementById('fgValue').textContent = fg.value;
      document.getElementById('fgClass').textContent = fg.value_classification;
    } catch (e) { }
  }

  async function loadCoins(page) {
    page = page || 1;
    var tb = document.getElementById('coinTableBody');
    if (page === 1) tb.innerHTML = '<tr><td colspan="10" class="text-center py-12">' + L + '</td></tr>';
    try {
      var r = await fetch(API + '/api/coins?page=' + page + '&per_page=50');
      var coins = await r.json();
      if (page === 1) tb.innerHTML = '';
      tb.innerHTML += coins.map(function (c, i) {
        var sym = c.symbol.toUpperCase();
        return '<tr class="border-b border-gray-100 hover:bg-gray-50 transition cursor-pointer" onclick="location.href=\'/coin?symbol=' + sym + 'USDT\'"><td class="py-3 px-4 text-gray-400 text-xs">' + ((page - 1) * 50 + i + 1) + '</td><td class="py-3 px-4"><div class="flex items-center gap-2"><img class="coin-icon" src="' + (c.image || '') + '" onerror="this.style.display=\'none\'"><div><div class="font-medium text-gray-900">' + c.name + '</div><div class="text-gray-500 text-xs">' + sym + '</div></div></div></td><td class="py-3 px-4 text-right font-semibold text-gray-900">' + fP(c.current_price) + '</td><td class="py-3 px-4 text-right font-medium">' + fC(c.price_change_percentage_1h_in_currency) + '</td><td class="py-3 px-4 text-right font-medium">' + fC(c.price_change_percentage_24h_in_currency) + '</td><td class="py-3 px-4 text-right font-medium">' + fC(c.price_change_percentage_7d_in_currency) + '</td><td class="py-3 px-4 text-right text-gray-500 hidden md:table-cell">' + fL(c.total_volume) + '</td><td class="py-3 px-4 text-right text-gray-500 hidden md:table-cell">' + fL(c.market_cap) + '</td><td class="py-3 px-4 hidden lg:table-cell">' + spark(c.sparkline_in_7d ? c.sparkline_in_7d.price : null, sym) + '</td><td class="py-3 px-4"><button class="border border-emerald-500 text-emerald-600 hover:bg-emerald-50 text-xs font-semibold px-3 py-1.5 rounded-lg transition" onclick="event.stopPropagation();location.href=\'/coin?symbol=' + sym + 'USDT\'">TRADE</button></td></tr>';
      }).join('');
    } catch (e) {
      tb.innerHTML = '<tr><td colspan="10" class="text-center py-12 text-red-500">Failed. Retrying...</td></tr>';
      setTimeout(function () { loadCoins(page); }, 5000);
    }
  }
  window.loadMoreCoins = function () { coinPage++; loadCoins(coinPage); };

  async function loadSideBoxes() {
    var gb = document.getElementById('gainersBox'), lb = document.getElementById('losersBox'), tb = document.getElementById('trendingBox');
    gb.innerHTML = L; lb.innerHTML = L; tb.innerHTML = L;
    try {
      var r1 = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_desc&per_page=5&sparkline=false&price_change_percentage=24h');
      var gainers = await r1.json();
      gb.innerHTML = gainers.length ? gainers.map(function (c) { return '<div class="flex items-center justify-between"><div class="flex items-center gap-2"><img class="coin-icon w-5 h-5" src="' + (c.image || '') + '" onerror="this.style.display=\'none\'"><a href="/coin?symbol=' + c.symbol.toUpperCase() + 'USDT" class="font-medium text-gray-900 hover:text-emerald-500">' + c.symbol.toUpperCase() + '</a></div><span class="text-emerald-500 font-medium text-xs">' + fC(c.price_change_percentage_24h_in_currency) + '</span></div>'; }).join('') : '<p class="text-gray-400 text-xs">No data</p>';
    } catch (e) { gb.innerHTML = '<p class="text-gray-400 text-xs">Unavailable</p>'; }
    try {
      var r2 = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_asc&per_page=5&sparkline=false&price_change_percentage=24h');
      var losers = await r2.json();
      lb.innerHTML = losers.length ? losers.map(function (c) { return '<div class="flex items-center justify-between"><div class="flex items-center gap-2"><img class="coin-icon w-5 h-5" src="' + (c.image || '') + '" onerror="this.style.display=\'none\'"><a href="/coin?symbol=' + c.symbol.toUpperCase() + 'USDT" class="font-medium text-gray-900 hover:text-emerald-500">' + c.symbol.toUpperCase() + '</a></div><span class="text-red-500 font-medium text-xs">' + fC(c.price_change_percentage_24h_in_currency) + '</span></div>'; }).join('') : '<p class="text-gray-400 text-xs">No data</p>';
    } catch (e) { lb.innerHTML = '<p class="text-gray-400 text-xs">Unavailable</p>'; }
    try {
      var r3 = await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=5&sparkline=false');
      var trending = await r3.json();
      tb.innerHTML = trending.length ? trending.map(function (c) { return '<div class="flex items-center justify-between"><div class="flex items-center gap-2"><img class="coin-icon w-5 h-5" src="' + (c.image || '') + '" onerror="this.style.display=\'none\'"><a href="/coin?symbol=' + c.symbol.toUpperCase() + 'USDT" class="font-medium text-gray-900 hover:text-emerald-500">' + c.name + '</a></div><span class="text-gray-500 text-xs">' + fP(c.current_price) + '</span></div>'; }).join('') : '<p class="text-gray-400 text-xs">No data</p>';
    } catch (e) { tb.innerHTML = '<p class="text-gray-400 text-xs">Unavailable</p>'; }
  }

  async function loadSidebarNews() {
    var s = document.getElementById('sidebarNews');
    if (!s) return;
    s.innerHTML = L;
    try {
      var r = await fetch(API + '/api/news');
      var d = await r.json();
      var items = [];
      if (Array.isArray(d) && d.length > 0) items = d;
      else if (d.results) items = d.results;
      s.innerHTML = items.slice(0, 12).map(function (a) {
        var title = a.headline || a.title || '';
        var summary = (a.summary || a.description || '').trim();
        if (summary === title) summary = '';
        var source = a.source || a.source_id || '';
        var html = '<div class="pb-3 border-b border-gray-100 last:border-b-0">';
        html += '<div class="text-gray-900 font-medium text-xs leading-tight hover:text-emerald-500 cursor-pointer">' + title + '</div>';
        if (summary) html += '<div class="text-gray-500 text-xs mt-1 leading-relaxed">' + summary.slice(0, 120) + '</div>';
        if (source) html += '<div class="text-gray-400 text-xs mt-1">' + source + '</div>';
        html += '</div>';
        return html;
      }).join('');
    } catch (e) { s.innerHTML = '<p class="text-gray-400 text-xs">News unavailable</p>'; }
  }

  var si = document.getElementById('globalSearch'); if (si) { si.addEventListener('input', async function () { var q = this.value.trim(); if (q.length < 1) { document.getElementById('searchDropdown').classList.add('hidden'); return } try { var r = await fetch('https://api.coingecko.com/api/v3/search?query=' + q); var d = await r.json(); var coins = (d.coins || []).slice(0, 8); var dd = document.getElementById('searchDropdown'); dd.innerHTML = coins.map(function (c) { return '<div class="flex items-center gap-3 p-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100" onclick="location.href=\'/coin?symbol=' + c.symbol.toUpperCase() + 'USDT\'"><img src="' + c.thumb + '" class="w-7 h-7 rounded-full"><div><div class="text-sm font-medium text-gray-900">' + c.name + '</div><div class="text-gray-500 text-xs">' + c.symbol.toUpperCase() + '</div></div></div>'; }).join(''); dd.classList.remove('hidden'); } catch (e) { } }) }

  document.addEventListener('DOMContentLoaded', function () { loadCoins(); loadOverview(); loadSideBoxes(); loadSidebarNews(); });
}

if (location.pathname === '/coin') {
  var p = new URLSearchParams(location.search), sym = p.get('symbol') || 'BTCUSDT';
  function initChart() { var isCrypto = sym.endsWith('USDT') || sym.endsWith('USD') || sym === 'BTCUSDT'; var symbol = isCrypto ? 'BINANCE:' + sym.replace('USDT', '') + 'USDT' : sym; new TradingView.widget({ container_id: 'tvChart', autosize: true, symbol: symbol, interval: '60', timezone: 'Etc/UTC', theme: 'dark', style: '1', locale: 'en', toolbar_bg: '#f1f3f6', enable_publishing: false, hide_side_toolbar: false, allow_symbol_change: true, studies: ['RSI@tv-basicstudies', 'MACD@tv-basicstudies'], disabled_features: ['header_symbol_search'], enabled_features: ['study_templates'] }); }
  initChart();
  async function loadCoinData() { document.getElementById('newsFeed').innerHTML = L; try { var r = await fetch(API + '/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: sym }) }); var d = await r.json(); var sn = d.data_snapshot; if (!sn) return; var pr = sn.price_data; document.getElementById('coinName').textContent = sym; document.getElementById('coinPrice').textContent = fP(pr.price); var ch = pr.change_pct || 0; var changeEl = document.getElementById('coinChange'); changeEl.innerHTML = (ch >= 0 ? '+' : '') + ch.toFixed(2) + '%'; changeEl.className = 'text-sm font-semibold px-2.5 py-1 rounded-lg ' + (ch >= 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'); var cg = sn.coingecko || {}; document.getElementById('priceStats').innerHTML = '<div class="flex justify-between py-1.5 border-b border-gray-100"><span class="text-gray-500">24h High</span><span class="font-medium">' + fP(cg.high_24h) + '</span></div><div class="flex justify-between py-1.5 border-b border-gray-100"><span class="text-gray-500">24h Low</span><span class="font-medium">' + fP(cg.low_24h) + '</span></div><div class="flex justify-between py-1.5 border-b border-gray-100"><span class="text-gray-500">All-Time High</span><span class="font-medium">' + fP(cg.ath) + '</span></div><div class="flex justify-between py-1.5 border-b border-gray-100"><span class="text-gray-500">All-Time Low</span><span class="font-medium">' + fP(cg.atl) + '</span></div><div class="flex justify-between py-1.5 border-b border-gray-100"><span class="text-gray-500">Market Cap</span><span class="font-medium">' + fL(cg.market_cap) + '</span></div><div class="flex justify-between py-1.5 border-b border-gray-100"><span class="text-gray-500">Volume 24h</span><span class="font-medium">' + fL(cg.total_volume) + '</span></div><div class="flex justify-between py-1.5"><span class="text-gray-500">Circ Supply</span><span class="font-medium">' + (cg.circulating_supply ? (cg.circulating_supply / 1e6).toFixed(2) + 'M' : '--') + '</span></div>'; var newsResp = await fetch(API + '/api/news?symbol=' + sym); var newsData = await newsResp.json(); var nw = Array.isArray(newsData) ? newsData : (sn.news || []); document.getElementById('newsFeed').innerHTML = nw.length ? nw.map(function (n) { return '<div class="pb-2 border-b border-gray-100"><div class="text-blue-500 text-xs font-medium hover:underline cursor-pointer">' + (n.headline || n.title) + '</div><div class="text-gray-500 text-xs mt-0.5">' + (n.summary || n.description || '').slice(0, 120) + '</div></div>'; }).join('') : '<p class="text-gray-400 text-xs">No news</p>'; var fg = sn.fear_greed || {}; document.getElementById('sentimentData').innerHTML = '<div class="text-2xl font-bold ' + (fg.value < 30 ? 'text-emerald-500' : fg.value > 70 ? 'text-red-500' : 'text-gray-500') + '">' + (fg.value || '--') + '</div><div class="text-xs text-gray-500 mt-1">' + (fg.classification || '') + '</div>'; loadOrderBook(sym); } catch (e) { console.error(e); } }
  async function loadOrderBook(symbol) { var ob = document.getElementById('orderBook'); if (!ob) return; ob.innerHTML = L; try { var r = await fetch('https://api.binance.com/api/v3/depth?symbol=' + symbol + '&limit=12'); var d = await r.json(); var html = '<div class="grid grid-cols-2 gap-2 text-xs"><div><div class="text-emerald-600 font-semibold mb-1">Bids</div>'; for (var i = Math.min(11, d.bids.length - 1); i >= 0; i--) { if (d.bids[i]) html += '<div class="flex justify-between text-emerald-600/80"><span>' + parseFloat(d.bids[i][0]).toFixed(2) + '</span><span>' + parseFloat(d.bids[i][1]).toFixed(4) + '</span></div>'; } html += '</div><div><div class="text-red-600 font-semibold mb-1">Asks</div>'; for (var i = 0; i < Math.min(12, d.asks.length); i++) { if (d.asks[i]) html += '<div class="flex justify-between text-red-600/80"><span>' + parseFloat(d.asks[i][0]).toFixed(2) + '</span><span>' + parseFloat(d.asks[i][1]).toFixed(4) + '</span></div>'; } html += '</div></div>'; ob.innerHTML = html; setTimeout(function () { loadOrderBook(symbol); }, 5000); } catch (e) { ob.innerHTML = '<p class="text-gray-400 text-xs">Order book unavailable. Retrying...</p>'; setTimeout(function () { loadOrderBook(symbol); }, 5000); } }
  async function generateTradePlan() { document.getElementById('tradePlan').innerHTML = '<div class="text-center py-8">' + L + '<p class="text-gray-500 text-xs mt-2">Analyzing market data...</p></div>'; try { var r = await fetch(API + '/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: sym }) }); var d = await r.json(); document.getElementById('tradePlan').textContent = d.trade_plan || 'Analysis failed. Please try again.'; } catch (e) { document.getElementById('tradePlan').innerHTML = '<p class="text-red-500 text-sm">Error generating plan. Please retry.</p>'; } }
  window.generateTradePlan = generateTradePlan;
  var si = document.getElementById('coinSearch'); if (si) { si.addEventListener('input', async function () { var q = this.value.trim(); if (q.length < 1) return; try { var r = await fetch('https://api.coingecko.com/api/v3/search?query=' + q); var d = await r.json(); if (d.coins && d.coins.length > 0) { location.href = '/coin?symbol=' + d.coins[0].symbol.toUpperCase() + 'USDT'; } } catch (e) { } }); }
  document.addEventListener('DOMContentLoaded', loadCoinData);
}
