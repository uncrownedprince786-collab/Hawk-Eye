const API = '';
let coinPage = 1;
function fP(p){if(!p)return'--';return p>=1?'$'+p.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):'$'+p.toFixed(6)}
function fL(n){if(!n)return'--';if(n>=1e12)return'$'+(n/1e12).toFixed(2)+'T';if(n>=1e9)return'$'+(n/1e9).toFixed(2)+'B';if(n>=1e6)return'$'+(n/1e6).toFixed(2)+'M';return'$'+n.toLocaleString()}
function fC(v){if(v===null||v===undefined)return'--';const c=v>=0?'positive':'negative';return`<span class="${c}">${v>=0?'+':''}${v.toFixed(2)}%</span>`}
function spark(p){if(!p||p.length<2)return'';const mn=Math.min(...p),mx=Math.max(...p),r=mx-mn||1,w=120,h=40;const cl=p[p.length-1]>=p[0]?'#0ecb81':'#f6465d';const pts=p.map((v,i)=>`${(i/(p.length-1))*w},${h-((v-mn)/r)*h}`).join(' ');return`<svg width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${cl}" stroke-width="1.5"/></svg>`}
const L='<div class="loader"></div>';

if(location.pathname==='/'||location.pathname===''){
  window.showSection=function(n){
    document.querySelectorAll('.section').forEach(s=>s.classList.add('hidden'));
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.getElementById(n+'Section').classList.remove('hidden');
    event.target.classList.add('active');
    if(n==='gainers')loadGainers();
    if(n==='losers')loadLosers();
    if(n==='stocks')loadStocks();
    if(n==='news')loadGeneralNews();
  };
  async function loadCoins(page=1){
    const tb=document.getElementById('coinTableBody');
    if(page===1)tb.innerHTML=`<tr><td colspan="10" class="loading-row">${L} Loading coins...</td></tr>`;
    try{
      const r=await fetch(API+'/api/coins?page='+page+'&per_page=50');
      const coins=await r.json();
      if(page===1)tb.innerHTML='';
      tb.innerHTML+=coins.map((c,i)=>`
        <tr><td>${(page-1)*50+i+1}</td>
        <td><span class="coin-name" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">${c.name}</span><span class="coin-symbol">${c.symbol.toUpperCase()}</span></td>
        <td>${fP(c.current_price)}</td><td>${fC(c.price_change_percentage_1h_in_currency)}</td><td>${fC(c.price_change_percentage_24h_in_currency)}</td><td>${fC(c.price_change_percentage_7d_in_currency)}</td><td>${fL(c.total_volume)}</td><td>${fL(c.market_cap)}</td><td>${spark(c.sparkline_in_7d?.price)}</td>
        <td><button class="trade-btn" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">TRADE</button></td></tr>
      `).join('');
    }catch(e){tb.innerHTML='<tr><td colspan="10" class="loading-row">Failed. Retrying...</td></tr>';setTimeout(()=>loadCoins(page),5000)}
  }
  window.loadMoreCoins=function(){coinPage++;loadCoins(coinPage)};
  async function loadGainers(){
    document.getElementById('gainersBody').innerHTML=`<tr><td colspan="6" class="loading-row">${L} Loading...</td></tr>`;
    try{
      const r=await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_desc&per_page=20&sparkline=false&price_change_percentage=24h');
      const c=await r.json();
      document.getElementById('gainersBody').innerHTML=c.map((c,i)=>`<tr><td>${i+1}</td><td><span class="coin-name" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">${c.name}</span><span class="coin-symbol">${c.symbol.toUpperCase()}</span></td><td>${fP(c.current_price)}</td><td>${fC(c.price_change_percentage_24h_in_currency)}</td><td>${fL(c.total_volume)}</td><td>${fL(c.market_cap)}</td><td><button class="trade-btn" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">TRADE</button></td></tr>`).join('');
    }catch(e){document.getElementById('gainersBody').innerHTML='<tr><td colspan="7">Failed.</td></tr>'}
  }
  async function loadLosers(){
    document.getElementById('losersBody').innerHTML=`<tr><td colspan="6" class="loading-row">${L} Loading...</td></tr>`;
    try{
      const r=await fetch('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=percent_change_24h_asc&per_page=20&sparkline=false&price_change_percentage=24h');
      const c=await r.json();
      document.getElementById('losersBody').innerHTML=c.map((c,i)=>`<tr><td>${i+1}</td><td><span class="coin-name" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">${c.name}</span><span class="coin-symbol">${c.symbol.toUpperCase()}</span></td><td>${fP(c.current_price)}</td><td>${fC(c.price_change_percentage_24h_in_currency)}</td><td>${fL(c.total_volume)}</td><td>${fL(c.market_cap)}</td><td><button class="trade-btn" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'">TRADE</button></td></tr>`).join('');
    }catch(e){document.getElementById('losersBody').innerHTML='<tr><td colspan="7">Failed.</td></tr>'}
  }
  async function loadStocks(){
    const syms=['AAPL','MSFT','GOOGL','AMZN','NVDA','TSLA','META','JPM','V','JNJ','WMT','PG','MA','UNH','HD','BAC','DIS','NFLX','ADBE','CRM'];
    document.getElementById('stocksBody').innerHTML=`<tr><td colspan="8" class="loading-row">${L} Loading stocks...</td></tr>`;
    let h='';
    for(const s of syms){
      try{
        const r=await fetch(API+'/api/stock/'+s);
        const d=await r.json();
        if(d.c){const ch=d.dp||0;h+=`<tr><td>${s}</td><td><span class="coin-name" onclick="location.href='/coin?symbol=${s}'">${s}</span></td><td>$${d.c.toFixed(2)}</td><td>${fC(ch)}</td><td>--</td><td>--</td><td>--</td><td><button class="trade-btn" onclick="location.href='/coin?symbol=${s}'">TRADE</button></td></tr>`}
      }catch(e){}
    }
    document.getElementById('stocksBody').innerHTML=h||'<tr><td colspan="8">Stock data unavailable.</td></tr>'
  }
  async function loadGeneralNews(){
    document.getElementById('newsGrid').innerHTML=`${L}<p>Loading trading news...</p>`;
    try{
      const r=await fetch(API+'/api/news');
      const d=await r.json();
      if(Array.isArray(d)&&d.length>0){
        document.getElementById('newsGrid').innerHTML=d.slice(0,12).map(a=>`<div class="news-card"><h3>${a.headline||a.title}</h3><p>${(a.summary||a.description||'').slice(0,200)}</p><small style="color:#848e9c;">${a.source||a.source_id}</small></div>`).join('');
      }else if(d.results){
        document.getElementById('newsGrid').innerHTML=d.results.slice(0,12).map(a=>`<div class="news-card"><h3>${a.title}</h3><p>${(a.description||'').slice(0,200)}</p><small style="color:#848e9c;">${a.source_id}</small></div>`).join('');
      }else{
        document.getElementById('newsGrid').innerHTML='<p>No trading news available.</p>';
      }
    }catch(e){document.getElementById('newsGrid').innerHTML='<p>News unavailable.</p>'}
  }
  async function loadStats(){
    try{const r=await fetch('https://api.coingecko.com/api/v3/global');const d=await r.json();document.getElementById('totalMcap').textContent=fL(d.data.total_market_cap.usd);document.getElementById('totalVolume').textContent=fL(d.data.total_volume.usd);document.getElementById('btcDom').textContent=d.data.market_cap_percentage.btc.toFixed(1)+'%'}catch(e){}
    try{const r=await fetch('https://api.alternative.me/fng/?limit=1');const d=await r.json();document.getElementById('fearGreedVal').textContent=d.data[0].value+' - '+d.data[0].value_classification}catch(e){}
  }
  addEventListener('DOMContentLoaded',()=>{loadCoins();loadStats()});
}

if(location.pathname==='/coin'){
  const p=new URLSearchParams(location.search);
  const sym=p.get('symbol')||'BTCUSDT';
  let chartData = [];

  async function loadCoinData(){
    document.getElementById('priceChart').style.display='none';
    document.getElementById('newsFeed').innerHTML=L+' Loading coin news...';
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
      document.getElementById('statHigh').textContent=fP(cg.high_24h);
      document.getElementById('statLow').textContent=fP(cg.low_24h);
      document.getElementById('statATH').textContent=fP(cg.ath);
      document.getElementById('statATL').textContent=fP(cg.atl);
      document.getElementById('statMCap').textContent=fL(cg.market_cap);
      document.getElementById('statVol').textContent=fL(cg.total_volume);
      document.getElementById('statSupply').textContent=cg.circ_supply?(cg.circ_supply/1e6).toFixed(2)+'M':'--';
      document.getElementById('statMaxSupply').textContent=cg.max_supply?(cg.max_supply/1e6).toFixed(2)+'M':'Unlimited';
      
      const newsResp = await fetch(API+'/api/news?symbol='+sym);
      const newsData = await newsResp.json();
      const nw = Array.isArray(newsData) ? newsData : (sn.news||[]);
      document.getElementById('newsFeed').innerHTML=nw.length?nw.map(n=>`<div class="news-item"><div class="news-headline">${n.headline||n.title}</div><div class="news-summary">${n.summary||n.description||''}</div></div>`).join(''):'<p class="placeholder">No news</p>';

      const fg=sn.fear_greed||{};
      document.getElementById('sentimentData').innerHTML=`<div class="stat-row"><span>Fear & Greed</span><span>${fg.value||'--'} - ${fg.classification||'--'}</span></div>`;
      const tech=sn.technicals_1d||{};
      if(tech.recent_candles&&tech.recent_candles.length>1){
        chartData = tech.recent_candles;
        document.getElementById('priceChart').style.display='block';
        drawChart();
        startLiveUpdates();
      }
    }catch(e){console.error(e)}
  }

  function drawChart(){
    const cv=document.getElementById('priceChart');
    if(!cv)return;
    const W=cv.width=cv.offsetWidth||800, H=cv.height=350;
    const ctx=cv.getContext('2d');
    const closes=chartData.map(c=>c.close);
    if(closes.length<2)return;
    const mn=Math.min(...closes)*0.999, mx=Math.max(...closes)*1.001, r=mx-mn||1;
    ctx.clearRect(0,0,W,H);
    // Grid lines
    ctx.strokeStyle='#1e2729';ctx.lineWidth=0.5;
    for(let i=0;i<=4;i++){const y=(H/4)*i;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke()}
    // Price line
    ctx.beginPath();ctx.strokeStyle='#f0b90b';ctx.lineWidth=2;
    chartData.forEach((c,i)=>{
      const x=i*(W/(chartData.length-1)), y=H-((c.close-mn)/r)*(H-40)-20;
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    });
    ctx.stroke();
    // Labels
    ctx.fillStyle='#eaecef';ctx.font='12px sans-serif';
    ctx.fillText('$'+mx.toFixed(2),5,15);
    ctx.fillText('$'+mn.toFixed(2),5,H-5);
    // Latest price
    const last=closes[closes.length-1];
    ctx.fillStyle='#f0b90b';ctx.font='bold 14px sans-serif';
    ctx.fillText('$'+last.toLocaleString(),W-150,25);
  }

  let liveInterval;
  function startLiveUpdates(){
    if(liveInterval)clearInterval(liveInterval);
    liveInterval=setInterval(async ()=>{
      try{
        const r=await fetch(API+'/api/price/'+sym);
        const d=await r.json();
        if(d.price&&chartData.length>0){
          chartData[chartData.length-1].close=d.price;
          drawChart();
        }
      }catch(e){}
    },10000);
  }

  async function generateTradePlan(){
    document.getElementById('tradePlan').innerHTML=L+'<p class="placeholder">Generating...</p>';
    try{
      const r=await fetch(API+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:sym})});
      const d=await r.json();
      document.getElementById('tradePlan').textContent=d.trade_plan||'Failed.';
    }catch(e){document.getElementById('tradePlan').innerHTML='<p class="placeholder">Error.</p>'}
  }
  window.generateTradePlan=generateTradePlan;
  window.loadChart=()=>generateTradePlan();
  addEventListener('DOMContentLoaded',loadCoinData);
}

const si=document.getElementById('globalSearch')||document.getElementById('coinSearch');
if(si){
  si.addEventListener('input',async function(){
    const q=this.value.trim();
    if(q.length<1){const dd=document.getElementById('searchDropdown');if(dd)dd.classList.add('hidden');return}
    try{
      const r=await fetch('https://api.coingecko.com/api/v3/search?query='+q);
      const d=await r.json();
      const coins=d.coins?.slice(0,8)||[];
      const dd=document.getElementById('searchDropdown');
      if(!dd)return;
      dd.innerHTML=coins.map(c=>`<div class="search-result" onclick="location.href='/coin?symbol=${c.symbol.toUpperCase()}USDT'"><span class="search-result-name">${c.name}</span><span class="search-result-symbol">${c.symbol.toUpperCase()}</span></div>`).join('');
      dd.classList.remove('hidden');
    }catch(e){}
  });
}
