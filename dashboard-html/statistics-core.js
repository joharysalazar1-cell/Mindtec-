// Numeric routines shared by the standalone dashboard and regression tests.
const AuditStatistics=(()=>{
 function errors(pairs){if(!pairs.length)return {n:0,bias:null,mae:null,rmse:null};let ds=pairs.map(p=>p.published-p.reference);return {n:ds.length,bias:ds.reduce((a,b)=>a+b,0)/ds.length,mae:ds.reduce((a,b)=>a+Math.abs(b),0)/ds.length,rmse:Math.sqrt(ds.reduce((a,b)=>a+b*b,0)/ds.length)}}
 function chiSquareTail1(x){if(x<=0)return 1;let z=Math.sqrt(x/2),t=1/(1+.5*z);return Math.max(0,Math.min(1,t*Math.exp(-z*z-1.26551223+t*(1.00002368+t*(.37409196+t*(.09678418+t*(-.18628806+t*(.27886807+t*(-1.13520398+t*(1.48851587+t*(-.82215223+t*.17087277)))))))))))}
 function mcnemar(b,c){if(![b,c].every(x=>Number.isInteger(x)&&x>=0))throw Error('McNemar needs nonnegative integer counts');let n=b+c;if(!n)return {discordant:0,chi2:0,df:1,pExact:1,pAsymptotic:null};let limit=Math.min(b,c),logs=[],logTerm=-n*Math.log(2);for(let k=0;k<=limit;k++){if(k)logTerm+=Math.log(n-k+1)-Math.log(k);logs.push(logTerm)}let max=Math.max(...logs),p=Math.min(1,2*Math.exp(max)*logs.reduce((a,l)=>a+Math.exp(l-max),0)),chi2=(b-c)**2/n;return {discordant:n,chi2,df:1,pExact:p,pAsymptotic:n>=25?chiSquareTail1(chi2):null}}
 function holm(items){let sorted=items.filter(r=>Number.isFinite(r.p)).slice().sort((a,b)=>a.p-b.p||String(a.id).localeCompare(String(b.id))),adjusted={},previous=0;sorted.forEach((r,i)=>{previous=Math.max(previous,Math.min(1,(sorted.length-i)*r.p));adjusted[r.id]=previous});return adjusted}
 return {errors,chiSquareTail1,mcnemar,holm};
})();
if(typeof module!=='undefined')module.exports=AuditStatistics;
