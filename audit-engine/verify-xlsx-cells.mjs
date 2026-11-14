// Local parity utility, not production HTTP code.
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {workbookCells,compareWorkbookCut,VERSION} from './xlsx-web-core.mjs';
const args=process.argv.slice(2);if(!args.length||args.length%2)throw Error('Expected workbook / JSON-cut pairs');const results=[];
for(let i=0;i<args.length;i+=2){
 const bytes=new Uint8Array(await readFile(args[i])),json=await readFile(args[i+1]),cut=JSON.parse(json),hash=createHash('sha256').update(bytes).digest('hex');
 if(hash!==cut.provenance?.original_sha256)throw Error('Original workbook digest mismatch');
 const rebuilt=await workbookCells(bytes),match=compareWorkbookCut(rebuilt,cut);
 results.push({...match,original_sha256:hash,json_sha256:createHash('sha256').update(json).digest('hex'),adapter_version:VERSION});
}
process.stdout.write(JSON.stringify({schema:'mindtec-xlsx-cell-parity/1',verified:true,archives:results}));
