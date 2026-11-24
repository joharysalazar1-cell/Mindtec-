const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
function summarize(pairs){
 if(!pairs.length)return {n:0};
 if(pairs.some(p=>!Number.isFinite(p.audit)||!Number.isFinite(p.panel)))throw Error('Finite numeric pairs required');
 const x=pairs.map(p=>p.audit),y=pairs.map(p=>p.panel),n=x.length,dx=x.map((v,i)=>y[i]-v),mx=mean(x),my=mean(y),bias=mean(dx),mae=mean(dx.map(Math.abs)),rmse=Math.sqrt(mean(dx.map(x=>x*x)));
 const ssx=x.reduce((s,v)=>s+(v-mx)**2,0),ssy=y.reduce((s,v)=>s+(v-my)**2,0),ssxy=x.reduce((s,v,i)=>s+(v-mx)*(y[i]-my),0),ssd=dx.reduce((s,v)=>s+(v-bias)**2,0),r=n>=3&&ssx>0&&ssy>0?ssxy/Math.sqrt(ssx*ssy):null;
 const cccDen=ssx/n+ssy/n+(mx-my)**2;
 return {n,bias,mae,rmse,varianceAudit:n>1?ssx/(n-1):null,variancePanel:n>1?ssy/(n-1):null,varianceDifference:n>1?ssd/(n-1):null,covariance:n>1?ssxy/(n-1):null,pearson:r,rSquared:r===null?null:r*r,concordance:cccDen>0?2*(ssxy/n)/cccDen:null,meanAudit:mx,meanPanel:my,rmseSquaredDecompositionError:rmse**2-bias**2-ssd/n};
}
module.exports={summarize};
