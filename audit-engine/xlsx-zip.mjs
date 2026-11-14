// Bounded OPC ZIP reader. No filesystem, Node imports, network or XML evaluation.
// Format: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
export const VERSION='mindtec-xlsx-zip/1.0.0';
const table=Uint32Array.from({length:256},(_,n)=>{for(let j=0;j<8;j++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
export function crc32(bytes){let n=0xffffffff;for(const b of bytes)n=table[(n^b)&255]^(n>>>8);return (n^0xffffffff)>>>0;}
const requireZip=(ok,reason)=>{if(!ok)throw Error('XLSX ZIP: '+reason);};
export function openWorkbookZip(input){
 requireZip(input instanceof Uint8Array,'bytes required');
 requireZip(input.length>=22&&input.length<=25000000,'compressed size limit');
 // Own the input so a caller cannot change a checked header during async reads.
 const bytes=input.slice(),v=new DataView(bytes.buffer),size=bytes.length;
 const u16=p=>v.getUint16(p,true),u32=p=>v.getUint32(p,true);
 const range=(p,n,end=size)=>requireZip(Number.isInteger(p)&&p>=0&&n>=0&&p+n<=end,'truncated or overlapping record');
 let end=-1;
 for(let p=size-22;p>=Math.max(0,size-22-65535);p--)if(u32(p)===0x06054b50&&p+22+u16(p+20)===size){end=p;break;}
 requireZip(end>=0,'end record missing');
 requireZip(u16(end+4)===0&&u16(end+6)===0&&u16(end+8)===u16(end+10),'multidisk unsupported');
 const count=u16(end+10),cdSize=u32(end+12),cdStart=u32(end+16);
 requireZip(count>0&&count<=10000&&count!==65535&&cdSize!==0xffffffff&&cdStart!==0xffffffff,'entry limit or ZIP64 unsupported');
 requireZip(cdStart+cdSize===end,'central directory boundary');
 function extra(p,n){
  const stop=p+n;range(p,n);while(p<stop){range(p,4,stop);const id=u16(p),len=u16(p+2);p+=4;range(p,len,stop);requireZip(id!==1,'ZIP64 unsupported');p+=len;}
 }
 function nameAt(p,n,flags){
  const raw=bytes.subarray(p,p+n);let name;
  if(flags&0x800){try{name=new TextDecoder('utf-8',{fatal:true}).decode(raw);}catch{throw Error('XLSX ZIP: invalid UTF-8 part name');}}
  else {requireZip(raw.every(b=>b>=32&&b<127),'non-ASCII legacy part name unsupported');name=String.fromCharCode(...raw);}
  requireZip(name.length>0&&!/[\\:\x00-\x1f\x7f]/.test(name)&&!name.startsWith('/')&&name.replace(/\/$/,'').split('/').every(p=>p&&p!=='.'&&p!=='..'),'unsafe part name');
  return name;
 }
 const entries=new Map();let p=cdStart,total=0;
 for(let i=0;i<count;i++){
  range(p,46,end);requireZip(u32(p)===0x02014b50,'central header signature');
  const flags=u16(p+8),method=u16(p+10),crc=u32(p+16),compressed=u32(p+20),expanded=u32(p+24),nl=u16(p+28),el=u16(p+30),cl=u16(p+32),offset=u32(p+42);
  range(p+46,nl+el+cl,end);
  requireZip((flags&~0x080e)===0&&(method===0||method===8),'encryption, flags or compression unsupported');
  requireZip(method===8||(flags&6)===0,'invalid stored compression flags');
  requireZip(u16(p+34)===0&&offset!==0xffffffff&&compressed!==0xffffffff&&expanded<=100000000,'part size, disk or ZIP64 unsupported');
  requireZip(((u32(p+38)>>>16)&0xf000)!==0xa000,'symbolic link unsupported');
  const name=nameAt(p+46,nl,flags);requireZip(!entries.has(name),'duplicate part name');
  extra(p+46+nl,el);total+=expanded;requireZip(total<=200000000,'expanded workbook size limit');
  entries.set(name,{name,flags,method,crc,compressed,expanded,offset});p+=46+nl+el+cl;
 }
 requireZip(p===end,'central directory entry count');
 let physical=0;
 for(const e of [...entries.values()].sort((a,b)=>a.offset-b.offset)){
  p=e.offset;requireZip(p===physical,'overlapping, hidden or prefixed local part');range(p,30,cdStart);requireZip(u32(p)===0x04034b50,'local header signature');
  const nl=u16(p+26),el=u16(p+28);range(p+30,nl+el,cdStart);
  requireZip(u16(p+6)===e.flags&&u16(p+8)===e.method&&nameAt(p+30,nl,e.flags)===e.name,'local/central header mismatch');extra(p+30+nl,el);
  for(const [local,actual] of [[u32(p+14),e.crc],[u32(p+18),e.compressed],[u32(p+22),e.expanded]])requireZip(local===actual||((e.flags&8)&&local===0),'local/central size or CRC mismatch');
  e.start=p+30+nl+el;range(e.start,e.compressed,cdStart);physical=e.start+e.compressed;
  if(e.flags&8){
   // Descriptor CRC may itself equal the optional descriptor signature.
   let match=false;for(const skip of [0,4]){if(skip&&physical+4<=cdStart&&u32(physical)!==0x08074b50)continue;if(physical+skip+12>cdStart)continue;const q=physical+skip;if(u32(q)===e.crc&&u32(q+4)===e.compressed&&u32(q+8)===e.expanded){physical=q+12;match=true;break;}}
   requireZip(match,'invalid data descriptor');
  }
  if(e.name.endsWith('/'))requireZip(e.expanded===0,'nonempty directory part');
 }
 requireZip(physical===cdStart,'unaccounted bytes before central directory');
 async function read(name){
  const e=entries.get(name);requireZip(e,'part missing');let out;
  if(e.method===0){requireZip(e.compressed===e.expanded,'stored size mismatch');out=bytes.slice(e.start,e.start+e.compressed);}
  else {
   const stream=new Blob([bytes.subarray(e.start,e.start+e.compressed)]).stream().pipeThrough(new DecompressionStream('deflate-raw')),reader=stream.getReader();let n=0;const chunks=[];
   try{while(true){const part=await reader.read();if(part.done)break;n+=part.value.length;requireZip(n<=e.expanded&&n<=100000000,'actual expansion exceeds declared size');chunks.push(part.value);}out=new Uint8Array(n);let at=0;for(const chunk of chunks){out.set(chunk,at);at+=chunk.length;}}
   catch(error){try{await reader.cancel();}catch{}throw error;}finally{reader.releaseLock();}
  }
  requireZip(out.length===e.expanded,'expanded size mismatch');requireZip(crc32(out)===e.crc,'CRC mismatch');return out;
 }
 // Expose immutable copies of metadata, never the checked backing bytes.
 return Object.freeze({version:VERSION,expanded_bytes:total,parts:Object.freeze([...entries.values()].map(e=>Object.freeze({name:e.name,compressed:e.compressed,expanded:e.expanded,crc32:e.crc}))),read});
}
