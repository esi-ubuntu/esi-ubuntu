const REPORT_ID=/^\d{4}-\d{2}-\d{2}-IR-TSE-1200$/;
const scoreNames=['core_fundamental_score','daily_valuation_score','technical_score','tape_score','news_score','daily_opportunity_score'];
const topAllowed={
 scout:new Set(['schema_version','report_id','market','generated_at','agent','market_status','candidates','top_5','best_early_candidate','best_momentum_hunter','best_potential_prime','data_quality']),
 auditor:new Set(['schema_version','report_id','market','generated_at','agent','scout_report_found','scout_validation','missed_candidates','finalists','market_action_status','data_quality']),
 final:new Set(['schema_version','report_id','market','generated_at','market_status','action_status','prime_candidates','best_fundamental_gem','best_early_candidate','best_momentum_hunter','highest_conviction','key_risks','key_catalysts','data_quality']),
 fundamental:new Set(['schema_version','market','symbol','core_fundamental_score','classification','last_reviewed_at','previous_score','change','change_reason','change_date','evidence'])
};
const required={
 scout:['schema_version','report_id','market','generated_at','agent','market_status','candidates','top_5','data_quality'],
 auditor:['schema_version','report_id','market','generated_at','agent','scout_report_found','scout_validation','missed_candidates','finalists','market_action_status','data_quality'],
 final:['schema_version','report_id','market','generated_at','market_status','action_status','prime_candidates','data_quality'],
 fundamental:['schema_version','market','symbol','core_fundamental_score','classification','last_reviewed_at','evidence']
};
function candidateErrors(c,p){
 const e=[];
 for(const k of scoreNames){ if(k in c && (typeof c[k]!=='number'||c[k]<0||c[k]>100)) e.push(`${p}.${k} must be 0..100`); }
 if(typeof c.symbol!=='string'||!c.symbol) e.push(`${p}.symbol required`);
 if(c.risk_reward!==null && typeof c.risk_reward!=='number') e.push(`${p}.risk_reward must be number|null`);
 const prime=['PRIME_CANDIDATE','POTENTIAL_PRIME','HIGH_CONVICTION'];
 if(prime.includes(c.label) && !(c.core_fundamental_score>=70 && c.technical_score>=70 && c.tape_score>=65 && c.risk_reward>=2 && c.critical_news_risk===false)) e.push(`${p}.${c.label} thresholds not met`);
 if(c.label==='MOMENTUM_HUNTER' && !(c.technical_score>=75 && c.tape_score>=75 && c.risk_reward>=2 && c.critical_news_risk===false)) e.push(`${p}.MOMENTUM_HUNTER thresholds not met`);
 if(c.label==='FUNDAMENTAL_GEM' && !(c.core_fundamental_score>=80)) e.push(`${p}.FUNDAMENTAL_GEM threshold not met`);
 if(c.label==='EARLY_CANDIDATE' && !(c.core_fundamental_score>=70)) e.push(`${p}.EARLY_CANDIDATE fundamental threshold not met`);
 return e;
}
export function validateDocument(kind,value){
 const errors=[];
 if(!topAllowed[kind]) return {valid:false,errors:[`unknown kind ${kind}`]};
 if(!value||typeof value!=='object'||Array.isArray(value)) return {valid:false,errors:['document must be object']};
 for(const k of required[kind]) if(!(k in value)) errors.push(`${k} is required`);
 for(const k of Object.keys(value)) if(!topAllowed[kind].has(k)) errors.push(`unexpected top-level field: ${k}`);
 if(value.schema_version!=='1.0') errors.push('schema_version must equal 1.0');
 if(kind!=='fundamental'){
   if(!REPORT_ID.test(value.report_id??'')) errors.push('report_id must match YYYY-MM-DD-IR-TSE-1200');
   if(value.market!=='iran_stock') errors.push('market must be iran_stock');
 } else if(!['iran_stock','crypto'].includes(value.market)) errors.push('market invalid');
 const arrays = kind==='scout' ? ['candidates'] : kind==='auditor' ? ['missed_candidates','finalists'] : kind==='final' ? ['prime_candidates'] : [];
 for(const name of arrays){
   if(!Array.isArray(value[name])) errors.push(`${name} must be array`);
   else value[name].forEach((c,i)=>errors.push(...candidateErrors(c,`${name}[${i}]`)));
 }
 if(kind==='fundamental'){
   if(typeof value.core_fundamental_score!=='number'||value.core_fundamental_score<0||value.core_fundamental_score>100) errors.push('core_fundamental_score must be 0..100');
   if(typeof value.previous_score==='number' && value.previous_score!==value.core_fundamental_score){
     const delta=value.core_fundamental_score-value.previous_score;
     if(value.change!==delta) errors.push('change must equal score delta');
     if(!value.change_reason?.trim()) errors.push('change_reason required when score changes');
     if(!value.change_date?.trim()) errors.push('change_date required when score changes');
     if(!Array.isArray(value.evidence)||value.evidence.length===0) errors.push('evidence required when score changes');
   }
 }
 return {valid:errors.length===0,errors};
}
export function validateFundamentalTransition(previous,next){
 const base=validateDocument('fundamental',next); const errors=[...base.errors];
 if(previous?.core_fundamental_score!==next?.core_fundamental_score){
   if(next.previous_score!==previous?.core_fundamental_score) errors.push('previous_score must equal prior core_fundamental_score');
   const delta=(next?.core_fundamental_score??0)-(previous?.core_fundamental_score??0);
   if(next.change!==delta) errors.push('change must equal score delta');
   if(!next.change_reason?.trim()) errors.push('change_reason required when score changes');
   if(!next.change_date?.trim()) errors.push('change_date required when score changes');
   if(!Array.isArray(next.evidence)||next.evidence.length===0) errors.push('evidence required when score changes');
 }
 return {valid:errors.length===0,errors};
}
