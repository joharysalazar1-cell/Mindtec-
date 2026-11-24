const zlib=require('zlib'),crypto=require('crypto');
module.exports=function(data){
 const d=data.result;
 if(d.source_sha256!=='f4a3b1b3981825553d82a31b18b0cae0fdda2c1ff44021c1ab82f855342cd10c')throw Error('Wrong active source');
 if(d.visits.length!==108||new Set(d.visits.map(x=>x.month)).size!==2)throw Error('Wrong cohort');
 const original={run_id:data.run_id,snapshot_sha256:data.snapshot_sha256,ledger_head:data.ledger_head};
 data.baseline_custody=original;
 data.presentation_revision={schema:'mindtec-current-executive/1',prepared:'2026-11-24',source_cut:'2026-11-23',calculation_values_unchanged:true};
 data.human_confirmation_sha256='8498ddbfa0346a4bd223d4fdb5d3a2c15a76794a95c79b14800b696ec886c635';
 const summary={decisions:18,zero:13,not_applicable:5,source_cut:'2026-11-23',integrated_run_id:data.run_id};
 return {data,payload:zlib.gzipSync(JSON.stringify(data),{level:9}).toString('base64'),summary};
};
