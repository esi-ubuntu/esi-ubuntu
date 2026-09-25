import { loadDashboardData } from './data.mjs'; import { renderDashboard, renderSymbolDetail } from './app.mjs';
const root=document.querySelector('#app');
try{ const state=await loadDashboardData('./data'); root.innerHTML=renderDashboard(state); root.addEventListener('click',e=>{const b=e.target.closest?.('[data-symbol]'); if(!b)return; document.querySelector('#detail').innerHTML=renderSymbolDetail(b.dataset.symbol,state.report,state.history);}); }
catch(e){ root.innerHTML=`<main class="shell"><h1>Market Intelligence Hub</h1><div class="error">${e.message}</div></main>`; }
