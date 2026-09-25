const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function candidates(report){ return report?.prime_candidates ?? report?.candidates ?? []; }
function status(report){ const m=typeof report?.market_status==='string'?report.market_status:report?.market_status?.state; return {market:m??'UNKNOWN',action:report?.action_status??report?.market_action_status??'PROVISIONAL'}; }
export function renderDashboard({mode='empty',report=null,history={}}={}){
 if(!report) return `<main class="shell"><h1>Market Intelligence Hub</h1><div class="empty">No valid report available.</div></main>`;
 const s=status(report), rows=candidates(report);
 const cards=[['Prime',report.highest_conviction??rows[0]?.symbol],['Best Fundamental',report.best_fundamental_gem],['Early',report.best_early_candidate],['Momentum',report.best_momentum_hunter]].map(([t,v])=>`<article class="card"><span>${esc(t)}</span><strong>${esc(v)}</strong></article>`).join('');
 const table=rows.map(c=>`<tr data-symbol="${esc(c.symbol)}"><td><button class="symbol-link" data-symbol="${esc(c.symbol)}">${esc(c.symbol)}</button></td><td>${esc(c.core_fundamental_score)}</td><td>${esc(c.daily_valuation_score)}</td><td>${esc(c.technical_score)}</td><td>${esc(c.tape_score)}</td><td>${esc(c.news_score)}</td><td>${esc(c.daily_opportunity_score)}</td><td>${esc(c.label)}</td></tr>`).join('');
 return `<main class="shell"><header><div><h1>Market Intelligence Hub</h1><p>${esc(report.report_id)}</p></div><div class="status"><b>${esc(s.market)}</b><b>${esc(s.action)}</b>${mode==='provisional'?'<em>Provisional — final audit unavailable</em>':''}</div></header><section class="cards">${cards}</section><section class="panel"><h2>Ranking</h2><div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Fund.</th><th>Val.</th><th>Tech.</th><th>Tape</th><th>News</th><th>Final</th><th>Label</th></tr></thead><tbody>${table||'<tr><td colspan="8">No qualified candidates</td></tr>'}</tbody></table></div></section><section class="panel" id="detail"><h2>Symbol Detail</h2><p>Select a symbol to inspect scores and history.</p></section></main>`;
}
export function renderSymbolDetail(symbol,report,history={}){
 const c=candidates(report).find(x=>x.symbol===symbol); if(!c) return '<p>Symbol not found.</p>';
 const h=history[symbol]??[];
 return `<h2>${esc(symbol)}</h2><div class="detail-grid"><div><b>Entry</b><span>${esc(c.entry)}</span></div><div><b>Stop</b><span>${esc(c.stop)}</span></div><div><b>Targets</b><span>${esc((c.targets??[]).join(' / '))}</span></div><div><b>R/R</b><span>${esc(c.risk_reward)}</span></div><div><b>Catalyst</b><span>${esc(c.catalyst)}</span></div><div><b>Main Risk</b><span>${esc(c.main_risk)}</span></div></div><h3>History</h3><ul class="history">${h.map(x=>`<li>${esc(x.date)} — ${esc(x.label)} — Fund ${esc(x.core_fundamental_score)} / Tech ${esc(x.technical_score)} / Tape ${esc(x.tape_score)}</li>`).join('')||'<li>No history yet</li>'}</ul>`;
}
