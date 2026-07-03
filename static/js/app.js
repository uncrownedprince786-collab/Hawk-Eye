const API='';let coinPage=1;const L='<div class="loader"></div>';
const fP=p=>p?p>=1?'$'+p.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'$'+p.toFixed(6):'--';
const fL=n=>n?n>=1e12?'$'+(n/1e12).toFixed(2)+'T':n>=1e9?'$'+(n/1e9).toFixed(2)+'B':n>=1e6?'$'+(n/1e6).toFixed(2)+'M':'$'+n.toLocaleString():'--';
const fC=v=>v===null||v===undefined?'--':'<span class="'+(v>=0?'positive':'negative')+'">'+(v>=0?'+':'')+v.toFixed(2)+'%</span>';
const spark=p=>{if(!p||p.length<2)return'';const mn=Math.min(...p),mx=Math.max(...p),r=mx-mn||1,w=100,h=36;const cl=p[p.length-1]>=p[0]?'#0ecb81':'#f6465d';return'<svg width="'+w+'" height="'+h+'"><polyline points="'+p.map((v,i)=>(i/(p.length-1))*w+','+(h-((v-mn)/r)*h)).join(' ')+'" fill="none" stroke="'+cl+'" stroke-width="1.5"/></svg>';};

// Theme (default dark)
(function(){
  const btn=document.getElementById('themeToggle');
  if(!btn)return;
  let theme=localStorage.getItem('hawk-theme')||'dark';
  document.body.className=theme;
  btn.textContent=theme==='dark'?'☀️':'🌙';
  btn.addEventListener('click',()=>{
    theme=document.body.className==='dark'?'light':'dark';
    document.body.className=theme;
    localStorage.setItem('hawk-theme',theme);
    btn.textContent=theme==='dark'?'☀️':'🌙';
  });
})();

// ============ HOMEPAGE ============
if(location.pathname==='/'||location.pathname===''){
  window.showSection=n=>{document.querySelectorAll('.section').forEach(s=>s.classList.add('hidden'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.getElementById(n+'Section').classList.remove('hidden');event.target.classList.add('active');if(n==='gainers')loadGainers();if(n==='losers')loadLosers();if(n==='stocks')loadStocks();};
  async function loadCoins(page=1){const tb=document.getElementById('coinTableBody');if(page===1)tb.innerHTML='<tr><td colspan="10">'+L+'</td></tr>';try{const r=await fetch(API+'/api/coins?page='+page+'&per_page=50');const c=await r.json();if(page===1)tb.innerHTML='';tb.innerHTML+=c.map((c,i)=>'<tr><td>'+((page-1)*50+i+1)+'</td><td><img class="coin-icon" src="'+(c.image||'')+'" onerror="this.style.display=\'none\'"><span class="coin-name" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'">'+c.name+'</span><span class="symbol">'+c.symbol.toUpperCase()+'</span></td><td>'+fP(c.current_price)+'</td><td>'+fC(c.price_change_percentage_1h_in_currency)+'</td><td>'+fC(c.price_change_percentage_24h_in_currency)+'</td><td>'+fC(c.price_change_percentage_7d_in_currency)+'</td><td>'+fL(c.total_volume)+'</td><td>'+fL(c.market_cap)+'</td><td>'+spark(c.sparkline_in_7d?.price)+'</td><td><button class="trade-btn" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'">TRADE</button></td></tr>').join('');}catch(e){tb.innerHTML='<tr><td colspan="10">Failed. Retrying...</td></tr>';setTimeout(()=>loadCoins(page),5000);}}
  window.loadMoreCoins=()=>{coinPage++;loadCoins(coinPage);};
  async function loadGainers(){document.getElementById('gainersBody').innerHTML='<tr><td colspan="7">'+L+'</td></tr>';try{const r=await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_desc&per_page=20&sparkline=false&price_change_percentage=24h');const c=await r.json();document.getElementById('gainersBody').innerHTML=c.map((c,i)=>'<tr><td>'+(i+1)+'</td><td><img class="coin-icon" src="'+(c.image||'')+'" onerror="this.style.display=\'none\'"><span class="coin-name" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'">'+c.name+'</span></td><td>'+fP(c.current_price)+'</td><td>'+fC(c.price_change_percentage_24h_in_currency)+'</td><td>'+fL(c.total_volume)+'</td><td>'+fL(c.market_cap)+'</td><td><button class="trade-btn" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'">TRADE</button></td></tr>').join('');}catch(e){document.getElementById('gainersBody').innerHTML='<tr><td colspan="7">Failed.</td></tr>';}}
  async function loadLosers(){document.getElementById('losersBody').innerHTML='<tr><td colspan="7">'+L+'</td></tr>';try{const r=await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_asc&per_page=20&sparkline=false&price_change_percentage=24h');const c=await r.json();document.getElementById('losersBody').innerHTML=c.map((c,i)=>'<tr><td>'+(i+1)+'</td><td><img class="coin-icon" src="'+(c.image||'')+'" onerror="this.style.display=\'none\'"><span class="coin-name" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'">'+c.name+'</span></td><td>'+fP(c.current_price)+'</td><td>'+fC(c.price_change_percentage_24h_in_currency)+'</td><td>'+fL(c.total_volume)+'</td><td>'+fL(c.market_cap)+'</td><td><button class="trade-btn" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'">TRADE</button></td></tr>').join('');}catch(e){document.getElementById('losersBody').innerHTML='<tr><td colspan="7">Failed.</td></tr>';}}
  async function loadStocks(){const syms=['AAPL','MSFT','GOOGL','AMZN','NVDA','TSLA','META','JPM','V','JNJ','WMT','PG','MA','UNH','HD','BAC','DIS','NFLX','ADBE','CRM'];document.getElementById('stocksBody').innerHTML='<tr><td colspan="8">'+L+'</td></tr>';let h='';for(const s of syms){try{const r=await fetch(API+'/api/stock/'+s);const d=await r.json();if(d.c){const ch=d.dp||0;h+='<tr><td>'+s+'</td><td><span class="coin-name" onclick="location.href=\'/coin?symbol='+s+'\'">'+s+'</span></td><td>$'+d.c.toFixed(2)+'</td><td>'+fC(ch)+'</td><td>--</td><td>--</td><td>--</td><td><button class="trade-btn" onclick="location.href=\'/coin?symbol='+s+'\'">TRADE</button></td></tr>';}}catch(e){}}document.getElementById('stocksBody').innerHTML=h||'<tr><td colspan="8">Stock data unavailable.</td></tr>';}
  async function loadSidebarNews(){const grid=document.getElementById('newsGrid');grid.innerHTML=L;try{const r=await fetch(API+'/api/news');const d=await r.json();if(Array.isArray(d)&&d.length>0){grid.innerHTML=d.slice(0,20).map(a=>'<div class="news-item"><div class="news-headline">'+(a.headline||a.title)+'</div><div class="news-summary">'+(a.summary||a.description||'').slice(0,180)+'</div><div class="news-source">'+(a.source||a.source_id||'')+'</div></div>').join('');}else if(d.results){grid.innerHTML=d.results.slice(0,20).map(a=>'<div class="news-item"><div class="news-headline">'+a.title+'</div><div class="news-summary">'+(a.description||'').slice(0,180)+'</div><div class="news-source">'+(a.source_id||'')+'</div></div>').join('');}else{grid.innerHTML='<p>No trading news available.</p>';}}catch(e){grid.innerHTML='<p>News unavailable.</p>';}}
  async function loadStats(){try{const r=await fetch('https://api.coingecko.com/api/v3/global');const d=await r.json();document.getElementById('totalMcap').textContent=fL(d.data.total_market_cap.usd);document.getElementById('totalVolume').textContent=fL(d.data.total_volume.usd);document.getElementById('btcDom').textContent=d.data.market_cap_percentage.btc.toFixed(1)+'%';}catch(e){}try{const r=await fetch('https://api.alternative.me/fng/?limit=1');const d=await r.json();const fg=d.data[0];document.getElementById('fearGreedVal').textContent=fg.value+' - '+fg.value_classification;}catch(e){}}
  addEventListener('DOMContentLoaded',()=>{loadCoins();loadStats();loadSidebarNews();});
}

// ============ COIN PAGE ============
if(location.pathname==='/coin'){
  const p=new URLSearchParams(location.search),sym=p.get('symbol')||'BTCUSDT';
  let tvWidget=null;

  function initChart(){
    const isCrypto=sym.endsWith('USDT')||sym.endsWith('USD')||sym==='BTCUSDT';
    const symbol=isCrypto?'BINANCE:'+sym.replace('USDT','')+'USDT':sym;
    tvWidget=new TradingView.widget({
      "container_id":"tvChart",
      "autosize":true,
      "symbol":symbol,
      "interval":"60",
      "timezone":"Etc/UTC",
      "theme":"dark",
      "style":"1",
      "locale":"en",
      "toolbar_bg":"#f1f3f6",
      "enable_publishing":false,
      "hide_side_toolbar":false,
      "allow_symbol_change":false,
      "studies":["RSI@tv-basicstudies","MACD@tv-basicstudies"],
      "disabled_features":["header_symbol_search","header_compare"],
      "enabled_features":["study_templates"]
    });
  }

  async function loadCoinData(){
    document.getElementById('newsFeed').innerHTML=L;
    try{
      const r=await fetch(API+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:sym})});
      const d=await r.json();
      const sn=d.data_snapshot;
      if(!sn)return;
      const pr=sn.price_data;
      document.getElementById('coinName').textContent=sym;
      document.getElementById('coinPrice').textContent=fP(pr.price);
      const ch=pr.change_pct||0;
      document.getElementById('coinChange').innerHTML=(ch>=0?'+':'')+ch.toFixed(2)+'%';
      document.getElementById('coinChange').className='price-change '+(ch>=0?'positive':'negative');
      const cg=sn.coingecko||{};
      document.getElementById('priceStats').innerHTML='<div class="stat-row"><span>24h High</span><span>'+fP(cg.high_24h)+'</span></div><div class="stat-row"><span>24h Low</span><span>'+fP(cg.low_24h)+'</span></div><div class="stat-row"><span>All-Time High</span><span>'+fP(cg.ath)+'</span></div><div class="stat-row"><span>All-Time Low</span><span>'+fP(cg.atl)+'</span></div><div class="stat-row"><span>Market Cap</span><span>'+fL(cg.market_cap)+'</span></div><div class="stat-row"><span>24h Volume</span><span>'+fL(cg.total_volume)+'</span></div><div class="stat-row"><span>Circ. Supply</span><span>'+(cg.circ_supply?(cg.circ_supply/1e6).toFixed(2)+'M':'--')+'</span></div><div class="stat-row"><span>Max Supply</span><span>'+(cg.max_supply?(cg.max_supply/1e6).toFixed(2)+'M':'Unlimited')+'</span></div>';
      // coin-specific news
      const newsResp=await fetch(API+'/api/news?symbol='+sym);const newsData=await newsResp.json();const nw=Array.isArray(newsData)?newsData:(sn.news||[]);document.getElementById('newsFeed').innerHTML=nw.length?nw.map(n=>'<div class="news-item"><div class="news-headline">'+(n.headline||n.title)+'</div><div class="news-summary">'+(n.summary||n.description||'').slice(0,180)+'</div><div class="news-source">'+(n.source||n.source_id||'')+'</div></div>').join(''):'<p>No news.</p>';
      const fg=sn.fear_greed||{};document.getElementById('sentimentData').innerHTML='<div class="stat-row"><span>Fear & Greed</span><span>'+(fg.value||'--')+' - '+(fg.classification||'--')+'</span></div>';
      // order book
      loadOrderBook(sym);
    }catch(e){console.error(e);}
  }

  async function loadOrderBook(symbol){
    const ob=document.getElementById('orderBook');
    if(!ob)return;
    ob.innerHTML=L;
    try{
      const r=await fetch('https://api.binance.com/api/v3/depth?symbol='+symbol+'&limit=10');
      const d=await r.json();
      let html='<div style="font-size:11px;color:var(--text2);margin-bottom:4px">Bids / Asks</div>';
      for(let i=9;i>=0;i--){if(d.bids[i])html+='<div class="order-row bid"><span>'+parseFloat(d.bids[i][0]).toFixed(2)+'</span><span>'+parseFloat(d.bids[i][1]).toFixed(4)+'</span></div>';}
      html+='<div style="border-top:1px solid var(--border);margin:4px 0"></div>';
      for(let i=0;i<10;i++){if(d.asks[i])html+='<div class="order-row ask"><span>'+parseFloat(d.asks[i][0]).toFixed(2)+'</span><span>'+parseFloat(d.asks[i][1]).toFixed(4)+'</span></div>';}
      ob.innerHTML=html;
    }catch(e){ob.innerHTML='<p>Order book unavailable.</p>';}
    // refresh every 5s
    setTimeout(()=>loadOrderBook(symbol),5000);
  }

  async function generateTradePlan(){document.getElementById('tradePlan').innerHTML='<p>Generating...</p>';try{const r=await fetch(API+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:sym})});const d=await r.json();document.getElementById('tradePlan').textContent=d.trade_plan||'Failed.';}catch(e){document.getElementById('tradePlan').innerHTML='<p>Error.</p>';}}
  window.generateTradePlan=generateTradePlan;
  initChart();
  addEventListener('DOMContentLoaded',loadCoinData);
}

// Search
const si=document.getElementById('globalSearch')||document.getElementById('coinSearch');if(si){si.addEventListener('input',async function(){const q=this.value.trim();if(q.length<1){const dd=document.getElementById('searchDropdown');if(dd)dd.classList.add('hidden');return;}try{const r=await fetch('https://api.coingecko.com/api/v3/search?query='+q);const d=await r.json();const coins=d.coins?.slice(0,8)||[];const dd=document.getElementById('searchDropdown');if(!dd)return;dd.innerHTML=coins.map(c=>'<div class="search-result" onclick="location.href=\'/coin?symbol='+c.symbol.toUpperCase()+'USDT\'"><img src="'+c.thumb+'" style="width:20px;height:20px"><span>'+c.name+'</span><span style="color:var(--text2);font-size:12px">'+c.symbol.toUpperCase()+'</span></div>').join('');dd.classList.remove('hidden');}catch(e){}});}