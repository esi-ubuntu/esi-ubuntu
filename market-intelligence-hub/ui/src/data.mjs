export function selectCurrentReport(index){
  if(index?.latest_valid_final?.path) return {mode:'final',date:index.latest_valid_final.date,path:index.latest_valid_final.path};
  const rows=[...(index?.reports??[])].filter(r=>r.scout_available).sort((a,b)=>a.date.localeCompare(b.date));
  const row=rows.at(-1); return row?{mode:'provisional',date:row.date,path:row.scout_path}:null;
}
export function reportAssetPath(selected){
  const name=String(selected.path??'').split('/').filter(Boolean).at(-1);
  if(!selected.date||!name) throw new Error('invalid selected report path');
  return `reports/${selected.date}/${name}`;
}
export async function loadDashboardData(base='./data'){
  const index=await fetch(`${base}/report-index.json`).then(r=>{if(!r.ok) throw new Error(`index ${r.status}`); return r.json();});
  const selected=selectCurrentReport(index); if(!selected) return {mode:'empty',report:null,index,history:{}};
  const rel=reportAssetPath(selected);
  const report=await fetch(`${base}/${rel}`).then(r=>{if(!r.ok) throw new Error(`report ${r.status}`); return r.json();});
  const history=await fetch(`${base}/symbol-history.json`).then(r=>r.ok?r.json():{}).catch(()=>({}));
  return {...selected,report,index,history};
}
