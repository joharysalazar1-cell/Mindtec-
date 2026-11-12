const assert=require('assert'),fs=require('fs'),S=require('./statistics-core.js');
const close=(a,b,t=1e-12)=>assert(Math.abs(a-b)<=t,`${a} != ${b}`);
let m=S.errors([{published:10,reference:8},{published:4,reference:5}]);close(m.bias,.5);close(m.mae,1.5);close(m.rmse,Math.sqrt(2.5));assert.strictEqual(m.n,2);assert.strictEqual(S.errors([]).mae,null);
let test=S.mcnemar(1,9);close(test.chi2,6.4);close(test.pExact,22/1024);assert.strictEqual(test.pAsymptotic,null);close(S.mcnemar(0,45).pExact,2**-44);close(S.mcnemar(25,25).pExact,1);assert.strictEqual(S.mcnemar(0,0).pExact,1);assert.throws(()=>S.mcnemar(-1,5));
let h=S.holm([{id:'a',p:.01},{id:'b',p:.04},{id:'c',p:.03}]);close(h.a,.03);close(h.b,.06);close(h.c,.06);
const values=[0,.1,1,3.841458820694124,10,45,100].map(x=>({x,p:S.chiSquareTail1(x)}));
fs.writeFileSync('statistics-numeric-validation.json',JSON.stringify({values,mcnemar: test,errors:m,holm:h},null,2));console.log('Error metrics, exact McNemar, Holm, zero-discordance and invalid-count checks: OK');
