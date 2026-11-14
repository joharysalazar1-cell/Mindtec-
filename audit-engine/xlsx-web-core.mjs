import {openWorkbookZip} from './xlsx-zip.mjs';
import {SAXParser} from './vendor/sax-1.6.1.mjs';
export const VERSION='mindtec-invoice-xlsx-js/1.0.0';
const M='http://schemas.openxmlformats.org/spreadsheetml/2006/main',R='http://schemas.openxmlformats.org/officeDocument/2006/relationships',P='http://schemas.openxmlformats.org/package/2006/relationships';
const check=(ok,why)=>{if(!ok)throw Error('XLSX cells: '+why);};
const is=(n,local,uri=M)=>n?.local===local&&n.uri===uri;
const attr=(n,key,uri='')=>Object.values(n.attributes).find(a=>a.local===key&&a.uri===uri)?.value;
function xml(bytes,handlers){
 let encoding='utf-8';
 if(bytes[0]===255&&bytes[1]===254||bytes[0]===60&&bytes[1]===0)encoding='utf-16le';
 else if(bytes[0]===254&&bytes[1]===255||bytes[0]===0&&bytes[1]===60)encoding='utf-16be';
 const decoder=new TextDecoder(encoding,{fatal:true}),parser=new SAXParser(true,{xmlns:true,strictEntities:true,trim:false,normalize:false}),stack=[];let elements=0,attributes=new Set(),lastCR=false;
 const valid=s=>check(!/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/u.test(s),'invalid XML character');
 parser.onerror=()=>{throw Error('XLSX cells: malformed XML');};
 parser.ondoctype=parser.onsgmldeclaration=()=>{throw Error('XLSX cells: DTD and entities are not supported');};
 parser.onopentagstart=()=>{attributes=new Set();};
 parser.onattribute=a=>{const key=a.uri+'|'+a.local;check(!attributes.has(key),'duplicate XML attribute');attributes.add(key);valid(a.value);};
 parser.onopentag=n=>{check(++elements<=2000000&&stack.length<128,'XML structural limit');stack.push(n);handlers.open?.(n,stack);};
 parser.onclosetag=()=>{handlers.close?.(stack.at(-1),stack);stack.pop();};
 parser.ontext=parser.oncdata=s=>{valid(s);handlers.text?.(s,stack);};
 for(let at=0;at<bytes.length;at+=16384){
  let text=decoder.decode(bytes.subarray(at,at+16384),{stream:true});
  if(at===0){const decl=text.match(/^\s*<\?xml\s[^?]*\?>/);if(decl){check(!/version\s*=\s*['"](?!1\.0['"])/.test(decl[0]),'unsupported XML version');const e=decl[0].match(/encoding\s*=\s*['"]([^'"]+)['"]/i)?.[1].toLowerCase();if(e)check(e===encoding||e==='utf-16'&&encoding.startsWith('utf-16'),'unsupported or conflicting XML encoding');}}
  // XML 1.0 line ending normalization, including a CR/LF split across chunks.
  if(lastCR&&text.startsWith('\n'))text=text.slice(1);lastCR=text.endsWith('\r');text=text.replace(/\r\n?/g,'\n');valid(text);parser.write(text);
 }
 const tail=decoder.decode();if(tail)parser.write(tail);parser.close();
}
function safeText(current,text){check(current.length+text.length<=1000000,'individual cell text limit');return current+text;}
function cellValue(cell,strings){
 let value=cell.hasV?(cell.value||null):cell.hasInline?cell.inline:null;
 if(value===null)return null;
 if(cell.type==='s'){check(/^[0-9]+$/.test(value)&&Number(value)<strings.length,'invalid shared string index');return strings[Number(value)];}
 if(cell.type==='b'){check(value==='0'||value==='1','invalid boolean value');return value==='1';}
 if(['inlineStr','str','e','d'].includes(cell.type))return value;
 // Python's preserved adapter leaves a nonnumeric token as text; retain that
 // behavior rather than silently coercing it to zero. Unsafe integers fail.
 const token=value.trim();if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(token))return value;
 const number=Number(token);check(Number.isFinite(number),'nonfinite worksheet number');check(!Number.isInteger(number)||Number.isSafeInteger(number),'integer exceeds exact JavaScript range');return number;
}
export async function workbookCells(bytes){
 const zip=openWorkbookZip(bytes),strings=[];let string=null;
 if(zip.parts.some(p=>p.name==='xl/sharedStrings.xml'))xml(await zip.read('xl/sharedStrings.xml'),{
  open(n,s){if(s.length===1)check(is(n,'sst'),'invalid shared strings root');if(s.length===2&&is(n,'si')){check(strings.length<1000000,'shared string count limit');string='';}},
  text(t){if(string!==null)string=safeText(string,t);},
  close(n,s){if(s.length===2&&is(n,'si')){strings.push(string);string=null;}}
 });
 const sheets=[];let sheetContainers=0;
 xml(await zip.read('xl/workbook.xml'),{open(n,s){
  if(s.length===1)check(is(n,'workbook'),'invalid workbook root');
  if(s.length===2&&is(n,'workbookPr'))check(!['1','true'].includes(attr(n,'date1904')),'unsupported 1904 date system');
  if(s.length===2&&is(n,'sheets'))check(++sheetContainers===1,'duplicate sheet container');
  if(s.length===3&&is(s[1],'sheets')&&is(n,'sheet')){const name=attr(n,'name');check(typeof name==='string','sheet name required');if(name.toLowerCase().includes('facturas'))sheets.push({name,id:attr(n,'id',R)});}
 }});
 check(sheets.length===1,'expected exactly one invoice-items worksheet');const sheet=sheets[0],rels=new Map();
 xml(await zip.read('xl/_rels/workbook.xml.rels'),{open(n,s){
  if(s.length===1)check(is(n,'Relationships',P),'invalid relationships root');
  if(s.length===2){check(is(n,'Relationship',P),'invalid relationship element');const id=attr(n,'Id'),target=attr(n,'Target');check(id&&target&&!rels.has(id),'missing or duplicate workbook relationship');check(attr(n,'TargetMode')!=='External','external workbook relationship');rels.set(id,target);}
 }});
 let target=rels.get(sheet.id);check(target,'worksheet relationship missing');target=target.replace(/^\//,'');if(!target.startsWith('xl/'))target='xl/'+target;
 check(!/[\\:]/.test(target)&&target.split('/').every(p=>p&&p!=='.'&&p!=='..'),'unsafe worksheet relationship');
 let headers=null,columns=null,row=null,cell=null,previous=0,formulaCells=0,dataContainers=0;const rows=[];
 xml(await zip.read(target),{
  open(n,s){
   if(s.length===1)check(is(n,'worksheet'),'invalid worksheet root');
   if(s.length===2&&is(n,'sheetData'))check(++dataContainers===1,'duplicate worksheet data');
   if(s.length===3&&is(s[1],'sheetData')&&is(n,'row')){const r=attr(n,'r');check(/^[1-9][0-9]{0,6}$/.test(r??'')&&Number(r)>previous&&Number(r)<=1048576,'invalid, duplicate or unordered row');previous=Number(r);row={source_row:previous,values:new Map()};}
   if(s.length===4&&row&&is(n,'c')){
    const address=attr(n,'r')?.match(/^([A-Z]{1,3})([1-9][0-9]{0,6})$/);check(address&&Number(address[2])===row.source_row,'cell address does not match row');let col=0;for(const a of address[1])col=col*26+a.charCodeAt(0)-64;check(col<=16384&&!row.values.has(address[1]),'invalid or duplicate cell');
    const type=attr(n,'t')??'n';check(['n','s','b','inlineStr','str','e','d'].includes(type),'unsupported cell type');cell={column:address[1],type,value:'',inline:'',hasV:false,hasInline:false,hasF:false};
   }
   if(s.length===5&&cell){
    if(is(n,'v')){check(!cell.hasV,'duplicate cell value');cell.hasV=true;}
    if(is(n,'is')){check(!cell.hasInline,'duplicate inline string');cell.hasInline=true;}
    if(is(n,'f')){check(!cell.hasF,'duplicate formula');cell.hasF=true;formulaCells++;}
   }
   if(s.length>5&&cell&&is(s[4],'v'))check(false,'nested value element');
  },
  text(t,s){if(cell&&s.length>=5){if(is(s[4],'v'))cell.value=safeText(cell.value,t);if(is(s[4],'is'))cell.inline=safeText(cell.inline,t);}},
  close(n,s){
   if(s.length===4&&cell&&is(n,'c')){row.values.set(cell.column,cellValue(cell,strings));cell=null;}
   if(s.length===3&&row&&is(n,'row')){if(headers===null){columns=[...row.values.keys()];headers=[...row.values.values()];}else rows.push({source_row:row.source_row,cells:columns.map(c=>row.values.get(c)??null)});row=null;}
  }
 });
 check(dataContainers===1&&headers!==null&&headers.length>0,'worksheet header required');
 return {headers,rows,worksheet:sheet.name,date_system:'excel_1900',formula_cells_using_cached_values:formulaCells,adapter_version:VERSION};
}
export function compareWorkbookCut(rebuilt,cut){
 check(cut&&Array.isArray(cut.headers)&&Array.isArray(cut.rows),'JSON cut required');
 const same=(a,b)=>typeof a===typeof b&&a===b;
 check(rebuilt.headers.length===cut.headers.length&&rebuilt.headers.every((v,i)=>same(v,cut.headers[i])),'header mismatch');
 check(rebuilt.rows.length===cut.rows.length,'row count mismatch');
 for(let i=0;i<rebuilt.rows.length;i++){const a=rebuilt.rows[i],b=cut.rows[i];check(a.source_row===b.source_row&&Array.isArray(b.cells)&&a.cells.length===b.cells.length&&a.cells.every((v,j)=>same(v,b.cells[j])),'typed cell or source row mismatch');}
 const p=cut.provenance;check(p&&p.worksheet===rebuilt.worksheet&&p.date_system===rebuilt.date_system&&p.formula_cells_using_cached_values===rebuilt.formula_cells_using_cached_values,'worksheet provenance mismatch');
 return {matched:true,rows:rebuilt.rows.length,columns:rebuilt.headers.length,cells:rebuilt.rows.length*rebuilt.headers.length,formula_cells_using_cached_values:rebuilt.formula_cells_using_cached_values};
}
