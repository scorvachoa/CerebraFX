window.CerebraMath=(function(){
"use strict";

function clamp01(x){return Math.min(1,Math.max(0,x));}
function clamp(x,a,b){return Math.min(b,Math.max(a,x));}
function num(v,d){var n=parseFloat(v);return isFinite(n)?n:d;}
function hexA(hex,a){
  var c=String(hex||'#6c63ff').replace('#','');
  if(c.length===3)c=c[0]+c[0]+c[1]+c[1]+c[2]+c[2];
  var r=parseInt(c.substr(0,2),16),g=parseInt(c.substr(2,2),16),b=parseInt(c.substr(4,2),16);
  return 'rgba('+r+','+g+','+b+','+a+')';
}
function hexL(hex,f){
  var c=String(hex).replace('#','');
  if(c.length===3)c=c[0]+c[0]+c[1]+c[1]+c[2]+c[2];
  var r=parseInt(c.substr(0,2),16),g=parseInt(c.substr(2,2),16),b=parseInt(c.substr(4,2),16);
  r=Math.round(r+(255-r)*f);g=Math.round(g+(255-g)*f);b=Math.round(b+(255-b)*f);
  return 'rgb('+r+','+g+','+b+')';
}

var PALETTE=['#6c63ff','#ff6b6b','#00d4ff','#ffd93d','#51cf66','#ff922b','#cc5de8','#20c997','#ff6b9d','#5aa9ff'];

var HELPERS=[
"var sin=Math.sin,cos=Math.cos,tan=Math.tan,asin=Math.asin,acos=Math.acos,atan=Math.atan,atan2=Math.atan2;",
"var sinh=Math.sinh,cosh=Math.cosh,tanh=Math.tanh,asinh=Math.asinh,acosh=Math.acosh,atanh=Math.atanh;",
"var sqrt=Math.sqrt,cbrt=Math.cbrt,abs=Math.abs,exp=Math.exp,expm1=Math.expm1,log1p=Math.log1p;",
"var ln=Math.log,log2=Math.log2,log10=Math.log10,log=Math.log10;",
"var floor=Math.floor,ceil=Math.ceil,round=Math.round,trunc=Math.trunc,sign=Math.sign;",
"var min=Math.min,max=Math.max,pow=Math.pow,hypot=Math.hypot;",
"var sec=function(a){return 1/Math.cos(a);},csc=function(a){return 1/Math.sin(a);},cot=function(a){return 1/Math.tan(a);};",
"var sech=function(a){return 1/Math.cosh(a);},csch=function(a){return 1/Math.sinh(a);},coth=function(a){return 1/Math.tanh(a);};",
"var fact=function(n){n=Math.round(n);if(n<0)return NaN;if(n>170)return Infinity;var r=1;for(var i=2;i<=n;i++)r*=i;return r;};",
"var gamma=function(z){if(z<0.5)return Math.PI/(Math.sin(Math.PI*z)*gamma(1-z));z-=1;var g=[1.0,0.5772156649015329,-0.6558780715202538,-0.0420026350340952,0.1665386113822915,-0.0421977345555443,-0.009621971527877,0.007218943246663,-0.0011651675918591,-0.0002152416741149,0.0001280502823882,-0.0000201348547807];var a=0.99999999999980993,t=z+7.5,sum=g[0];for(var i=1;i<g.length;i++)sum+=g[i]/(z+i);return Math.sqrt(2*Math.PI)*Math.pow(t,z+0.5)*Math.exp(-t)*sum;};",
"var erf=function(x){var s=x<0?-1:1;x=Math.abs(x);var a1=0.254829592,a2=-0.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p=0.3275911;var t=1/(1+p*x);return s*(1-((((a5*t+a4)*t+a3)*t+a2)*t+a1)*t*Math.exp(-x*x));};",
"var erfc=function(x){return 1-erf(x);};",
"var e=Math.E,pi=Math.PI,PI=Math.PI,tau=2*Math.PI,phi=1.618033988749895;"
];

function tokenize(s){
  var toks=[],i=0,n=s.length;
  while(i<n){
    var ch=s[i];
    if(ch===' '||ch==='\t'){i++;continue;}
    if(ch==='\u00B2'){toks.push({t:'op',v:'^'},{t:'num',v:'2'});i++;continue;}
    if(ch==='\u00B3'){toks.push({t:'op',v:'^'},{t:'num',v:'3'});i++;continue;}
    if(/[0-9.]/.test(ch)){
      var j=i;
      while(j<n&&/[0-9.]/.test(s[j]))j++;
      if(j<n&&/^[eE][+-]?\d/.test(s.substr(j,3))){
        var k=j+1;if(s[k]==='+'||s[k]==='-')k++;
        while(k<n&&/[0-9]/.test(s[k]))k++;
        j=k;
      }
      toks.push({t:'num',v:s.slice(i,j)});i=j;continue;
    }
    if(/[a-zA-Z_\u03C0\u03B8\u03C6]/.test(ch)){
      var j=i;
      while(j<n&&/[a-zA-Z0-9_\u03C0\u03B8\u03C6]/.test(s[j]))j++;
      toks.push({t:'id',v:s.slice(i,j)});i=j;continue;
    }
    if('+-*/^%!'.indexOf(ch)>=0){toks.push({t:'op',v:ch});i++;continue;}
    if(ch==='('||ch===')'){toks.push({t:'paren',v:ch});i++;continue;}
    if(ch===','){toks.push({t:'comma',v:','});i++;continue;}
    toks.push({t:'op',v:ch});i++;
  }
  return toks;
}

function preprocessExpr(raw){
  var s=String(raw||'').replace(/×/g,'*').replace(/÷/g,'/').replace(/−/g,'-').replace(/\u221E/g,'Infinity');
  s=s.replace(/(\d+(?:\.\d+)?|\)|[a-zA-Z_][a-zA-Z0-9_]*)\s*!/g,'fact($1)');
  var toks=tokenize(s);
  var out=[],prev=null;
  var FN_NAMES={'sin':1,'cos':1,'tan':1,'asin':1,'acos':1,'atan':1,'atan2':1,'sinh':1,'cosh':1,'tanh':1,'asinh':1,'acosh':1,'atanh':1,'sqrt':1,'cbrt':1,'abs':1,'exp':1,'expm1':1,'log1p':1,'ln':1,'log2':1,'log10':1,'log':1,'floor':1,'ceil':1,'round':1,'trunc':1,'sign':1,'min':1,'max':1,'pow':1,'hypot':1,'sec':1,'csc':1,'cot':1,'sech':1,'csch':1,'coth':1,'fact':1,'gamma':1,'erf':1,'erfc':1};
  function valEnd(t){return t&&(t.t==='num'||t.t==='id'||(t.t==='paren'&&t.v===')')||(t.t==='op'&&t.v==='!'));}
  function valStart(t){return t&&(t.t==='num'||t.t==='id'||(t.t==='paren'&&t.v==='('));}
  for(var i=0;i<toks.length;i++){
    var t=toks[i];
    if(valEnd(prev)&&valStart(t)){
      var isCall=prev.t==='id'&&t.t==='paren'&&t.v==='('&&FN_NAMES[prev.v]===1;
      if(!isCall)out.push('*');
    }
    if(t.t==='op'&&t.v==='^')out.push('**');
    else if(t.t==='id'&&t.v==='\u03C0')out.push('PI');
    else if(t.t==='id'&&t.v==='\u03C6')out.push('phi');
    else out.push(t.v);
    prev=t;
  }
  return out.join('');
}

var fnCache={};
function compileFn(expr,varname){
  var key=varname+'|'+expr;
  if(key in fnCache)return fnCache[key];
  var f=null;
  try{
    var body=preprocessExpr(expr);
    f=new Function(varname,HELPERS.join('\n')+'\nreturn ('+body+');');
  }catch(e){f=null;}
  fnCache[key]=f;
  return f;
}
function compileFn2(expr){
  var key='xy|'+expr;
  if(key in fnCache)return fnCache[key];
  var f=null;
  try{
    var body=preprocessExpr(expr);
    f=new Function('x','y',HELPERS.join('\n')+'\nreturn ('+body+');');
  }catch(e){f=null;}
  fnCache[key]=f;
  return f;
}

function niceNum(range,round){
  if(!(range>0))range=1;
  var exp=Math.floor(Math.log10(range));
  var f=range/Math.pow(10,exp);
  var nf;
  if(round){nf=f<1.5?1:(f<3?2:(f<7?5:10));}
  else{nf=f<=1?1:(f<=2?2:(f<=5?5:10));}
  return nf*Math.pow(10,exp);
}
function roundTo(v,step){
  var d=Math.max(0,-Math.floor(Math.log10(step)));
  return parseFloat(v.toFixed(d));
}
function niceTicks(min,max){
  var range=max-min;
  if(range<=0)range=1;
  var step=niceNum(range/7,false);
  var start=Math.ceil(min/step)*step;
  var vals=[];
  for(var v=start;v<=max+step*0.01;v+=step)vals.push(roundTo(v,step));
  if(!vals.length)vals.push(0);
  return vals;
}
function logTicks(min,max){
  var vals=[];
  if(min<=0)min=1e-9;
  if(max<=min)max=min*10;
  var e0=Math.floor(Math.log10(min));
  var e1=Math.ceil(Math.log10(max));
  for(var e=e0;e<=e1;e++){
    var base=Math.pow(10,e);
    if(base>=min&&base<=max)vals.push(base);
  }
  return vals;
}
function fmtTick(v){
  if(v===0)return '0';
  if(Math.abs(v)>=1e5||Math.abs(v)<1e-3)return v.toExponential(1).replace('e+','e').replace(/\.0+e/,'e');
  if(Math.abs(v)>=1)return String(parseFloat(v.toFixed(4)));
  return String(parseFloat(v.toFixed(3)));
}

function makeT(W,H,xmin,xmax,ymin,ymax,logx,logy){
  var x0=logx?Math.log10(Math.max(xmin,1e-12)):xmin;
  var x1=logx?Math.log10(Math.max(xmax,1e-12)):xmax;
  var y0=logy?Math.log10(Math.max(ymin,1e-12)):ymin;
  var y1=logy?Math.log10(Math.max(ymax,1e-12)):ymax;
  if(x1<=x0){x1=x0+1;}
  if(y1<=y0){y1=y0+1;}
  return {
    tx:function(x){
      if(logx&&x<=0)return null;
      var v=logx?Math.log10(x):x;
      return (v-x0)/(x1-x0)*W;
    },
    ty:function(y){
      if(logy&&y<=0)return null;
      var v=logy?Math.log10(y):y;
      return H-(v-y0)/(y1-y0)*H;
    }
  };
}

function drawFrame(ctx,W,H,scene,xmin,xmax,ymin,ymax,t){
  ctx.fillStyle='rgba(10,10,30,0.9)';
  ctx.fillRect(0,0,W,H);
  var tx=t.tx,ty=t.ty;
  var xticks=t.logx?logTicks(xmin,xmax):niceTicks(xmin,xmax);
  var yticks=t.logy?logTicks(ymin,ymax):niceTicks(ymin,ymax);
  ctx.strokeStyle='rgba(255,255,255,0.06)';
  ctx.lineWidth=1;
  for(var i=0;i<xticks.length;i++){
    var px=tx(xticks[i]);
    if(px===null)continue;
    ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,H);ctx.stroke();
  }
  for(var i=0;i<yticks.length;i++){
    var py=ty(yticks[i]);
    if(py===null)continue;
    ctx.beginPath();ctx.moveTo(0,py);ctx.lineTo(W,py);ctx.stroke();
  }
  var px0=t.logx?tx(1):tx(0);
  var py0=t.logy?ty(1):ty(0);
  ctx.strokeStyle='rgba(255,255,255,0.35)';
  ctx.lineWidth=2;
  if(px0!==null&&px0>=0&&px0<=W){ctx.beginPath();ctx.moveTo(px0,0);ctx.lineTo(px0,H);ctx.stroke();}
  if(py0!==null&&py0>=0&&py0<=H){ctx.beginPath();ctx.moveTo(0,py0);ctx.lineTo(W,py0);ctx.stroke();}
  ctx.font='18px Inter,sans-serif';
  ctx.fillStyle='rgba(255,255,255,0.42)';
  ctx.textAlign='center';
  for(var i=0;i<xticks.length;i++){
    var v=xticks[i];
    var px=tx(v);
    if(px===null)continue;
    if(py0!==null&&py0>=0&&py0<=H&&px>=4&&px<=W-4)ctx.fillText(fmtTick(v),px,py0+26);
  }
  ctx.textAlign='left';
  for(var i=0;i<yticks.length;i++){
    var v=yticks[i];
    var py=ty(v);
    if(py===null)continue;
    if(px0!==null&&px0>=0&&px0<=W&&py>=8&&py<=H-4)ctx.fillText(fmtTick(v),px0+10,py+6);
  }
  if(!t.logx&&px0!==null&&px0>=0&&px0<=W&&py0!==null&&py0>=0&&py0<=H)ctx.fillText('0',px0+10,py0+26);
  ctx.font='bold 26px Inter,sans-serif';
  ctx.fillStyle='rgba(255,255,255,0.7)';
  ctx.textAlign='left';
  if(px0===null||px0>=W*0.86){ctx.fillText('x',W-30,H-20);}
  if(py0===null||py0<=H*0.12){ctx.fillText('y',14,30);}
}

function roundRect(ctx,x,y,w,h,r){
  r=Math.min(r,w/2,h/2);
  ctx.beginPath();
  ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);
  ctx.arcTo(x,y,x+w,y,r);
  ctx.closePath();
}

function strokePts(ctx,pts){
  ctx.beginPath();
  for(var i=0;i<pts.length;i++){
    if(i===0)ctx.moveTo(pts[i].x,pts[i].y);else ctx.lineTo(pts[i].x,pts[i].y);
  }
  ctx.stroke();
}

function drawPolyline(ctx,pts,color,W){
  if(pts.length<2)return;
  ctx.save();
  ctx.strokeStyle=color;ctx.globalAlpha=0.16;ctx.lineWidth=8;ctx.lineJoin='round';ctx.lineCap='round';
  strokePts(ctx,pts);
  var grad=ctx.createLinearGradient(0,0,W,0);
  grad.addColorStop(0,color);grad.addColorStop(1,hexL(color,0.35));
  ctx.globalAlpha=1;ctx.strokeStyle=grad;ctx.lineWidth=3.5;
  strokePts(ctx,pts);
  ctx.restore();
}

function drawHead(ctx,x,y,color){
  ctx.save();
  ctx.shadowColor=color;ctx.shadowBlur=20;
  ctx.fillStyle=color;
  ctx.beginPath();ctx.arc(x,y,7.5,0,Math.PI*2);ctx.fill();
  ctx.shadowBlur=0;
  ctx.fillStyle='#fff';
  ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();
  ctx.restore();
}

function drawLegend(ctx,items,W){
  var y=48;
  for(var i=0;i<items.length;i++){
    var it=items[i];
    ctx.font='bold 22px Inter,sans-serif';
    var w=ctx.measureText(it.label).width+30;
    var x=W-20-w;
    ctx.fillStyle='rgba(0,0,0,0.4)';
    roundRect(ctx,x-8,y-24,w+16,32,8);ctx.fill();
    ctx.fillStyle=it.color;
    roundRect(ctx,x,y-14,12,12,3);ctx.fill();
    ctx.fillStyle='rgba(255,255,255,0.95)';
    ctx.fillText(it.label,x+18,y);
    y+=44;
  }
}

function autoY(fns,xmin,xmax){
  var lo=Infinity,hi=-Infinity;
  var N=400;
  for(var k=0;k<fns.length;k++){
    var f=compileFn(fns[k].expr,fns[k].var||'x');
    if(!f)continue;
    for(var i=0;i<=N;i++){
      var x=xmin+(xmax-xmin)*i/N;
      try{
        var y=f(x);
        if(isFinite(y)){if(y<lo)lo=y;if(y>hi)hi=y;}
      }catch(e){}
    }
  }
  if(!isFinite(lo)||!isFinite(hi)){lo=-5;hi=5;}
  if(hi-lo<1e-6){lo-=1;hi+=1;}
  var pad=(hi-lo)*0.12;
  return [lo-pad,hi+pad];
}

function renderPoints(ctx,W,H,scene,p,color,all){
  var xs=[],ys=[];
  for(var i=0;i<all.length;i++){var q=all[i];if(q){xs.push(q.x);ys.push(q.y);}}
  if(!xs.length)return;
  var xmin=num(scene.graph_xmin,Math.min.apply(null,xs));
  var xmax=num(scene.graph_xmax,Math.max.apply(null,xs));
  var ymin=num(scene.graph_ymin,Math.min.apply(null,ys));
  var ymax=num(scene.graph_ymax,Math.max.apply(null,ys));
  var px=(xmax-xmin)*0.12||1,py=(ymax-ymin)*0.12||1;
  xmin-=px;xmax+=px;ymin-=py;ymax+=py;
  if(xmax<=xmin){xmin-=1;xmax+=1;}
  if(ymax<=ymin){ymin-=1;ymax+=1;}
  var t=makeT(W,H,xmin,xmax,ymin,ymax,false,false);
  drawFrame(ctx,W,H,scene,xmin,xmax,ymin,ymax,t);
  var limit=Math.floor(all.length*p);
  var pts=[];
  for(var i=0;i<=limit;i++){
    var q=all[i];
    if(!q){if(pts.length>1){drawPolyline(ctx,pts,color,W);pts=[];}continue;}
    var sx=t.tx(q.x),sy=t.ty(q.y);
    if(sx===null||sy===null){if(pts.length>1){drawPolyline(ctx,pts,color,W);pts=[];}continue;}
    pts.push({x:sx,y:sy});
  }
  if(pts.length>1)drawPolyline(ctx,pts,color,W);
  if(pts.length&&p<0.999)drawHead(ctx,pts[pts.length-1].x,pts[pts.length-1].y,color);
  if(scene.graph_label&&p>0.03)drawLegend(ctx,[{label:scene.graph_label,color:color}],W);
}

function drawGraph(canvasId,scene,progress){
  var cv=document.getElementById(canvasId);if(!cv)return;
  var ctx=cv.getContext('2d');
  var W=cv.width,H=cv.height;
  var p=clamp01(progress);
  var gt=scene.graph_type||'function';
  var xmin=num(scene.graph_xmin,-5),xmax=num(scene.graph_xmax,5);
  if(xmax<=xmin)xmax=xmin+1;
  var logx=scene.graph_logx===true,logy=scene.graph_logy===true;
  var color=scene.themeColor||'#6c63ff';

  if(gt==='parametric'){return drawParametric(ctx,W,H,scene,p,color);}
  if(gt==='polar'){return drawPolar(ctx,W,H,scene,p,color);}
  if(gt==='inequality'){return drawInequality(ctx,W,H,scene,p,color,xmin,xmax,logx,logy);}
  if(gt==='implicit'){return drawImplicit(ctx,W,H,scene,p,color);}
  if(gt==='scatter'){return drawScatter(ctx,W,H,scene,p,color);}
  if(gt==='bar'){return drawBars(ctx,W,H,scene,p,color);}

  var fns=[];
  var raw=scene.graph_func||'x';
  if(Array.isArray(raw)){
    var labels=Array.isArray(scene.graph_label)?scene.graph_label:[];
    for(var i=0;i<raw.length;i++)fns.push({expr:String(raw[i]),label:labels[i]||'',color:PALETTE[i%PALETTE.length]});
  }else{
    fns.push({expr:String(raw),label:scene.graph_label||'',color:color});
  }
  fns=fns.filter(function(f){return f.expr.trim();});
  if(!fns.length)fns.push({expr:'x',label:'',color:color});

  var yr=autoY(fns,xmin,xmax);
  var ymin=num(scene.graph_ymin,yr[0]),ymax=num(scene.graph_ymax,yr[1]);
  if(ymax<=ymin)ymax=ymin+1;
  if(logy&&ymin<=0)ymin=Math.max(yr[0],0.01);

  var t=makeT(W,H,xmin,xmax,ymin,ymax,logx,logy);
  drawFrame(ctx,W,H,scene,xmin,xmax,ymin,ymax,t);

  var N=600;
  var items=[];
  for(var fi=0;fi<fns.length;fi++){
    var fn=fns[fi];
    var f=compileFn(fn.expr,'x');
    if(!f)continue;
    var limit=Math.floor(N*p);
    var pts=[],prevY=null;
    var jump=(ymax-ymin)*0.7;
    for(var i=0;i<=limit;i++){
      var x=xmin+(xmax-xmin)*i/N;
      var px=t.tx(x);
      if(px===null){prevY=null;continue;}
      var y;
      try{y=f(x);}catch(e){prevY=null;continue;}
      if(!isFinite(y)){prevY=null;continue;}
      if(prevY!==null&&Math.abs(y-prevY)>jump)prevY=null;
      var py=t.ty(y);
      if(py===null){prevY=y;continue;}
      pts.push({x:px,y:py});
      prevY=y;
    }
    if(pts.length>1)drawPolyline(ctx,pts,fn.color,W);
    if(pts.length&&p<0.999)drawHead(ctx,pts[pts.length-1].x,pts[pts.length-1].y,fn.color);
    if(fn.label)items.push({label:fn.label,color:fn.color});
  }
  if(items.length&&p>0.03)drawLegend(ctx,items,W);
}

function drawParametric(ctx,W,H,scene,p,color){
  var parts=(typeof scene.graph_func==='string'?scene.graph_func.split(';'):scene.graph_func).map(function(s){return String(s).trim();});
  var xf=compileFn(parts[0]||'cos(t)','t');
  var yf=compileFn(parts[1]||'sin(t)','t');
  var t0=num(scene.tMin,0),t1=num(scene.tMax,2*Math.PI);
  var N=600,all=[];
  for(var i=0;i<=N;i++){
    var t=t0+(t1-t0)*i/N,x,y;
    if(!xf||!yf){all.push(null);continue;}
    try{x=xf(t);y=yf(t);}catch(e){all.push(null);continue;}
    all.push((isFinite(x)&&isFinite(y))?{x:x,y:y}:null);
  }
  renderPoints(ctx,W,H,scene,p,color,all);
}

function drawPolar(ctx,W,H,scene,p,color){
  var rf=compileFn(String(scene.graph_func||'1'),'theta');
  var t0=num(scene.tMin,0),t1=num(scene.tMax,2*Math.PI);
  var N=720,all=[];
  for(var i=0;i<=N;i++){
    var th=t0+(t1-t0)*i/N,r;
    if(!rf){all.push(null);continue;}
    try{r=rf(th);}catch(e){all.push(null);continue;}
    all.push((isFinite(r))?{x:r*Math.cos(th),y:r*Math.sin(th)}:null);
  }
  renderPoints(ctx,W,H,scene,p,color,all);
}

function drawInequality(ctx,W,H,scene,p,color,xmin,xmax,logx,logy){
  var f=compileFn(String(scene.graph_func||'x'),'x');
  var sign=scene.graph_inequality||'<';
  var below=sign.indexOf('>')<0;
  var N=500,ys=[];
  for(var i=0;i<=N;i++){
    var x=xmin+(xmax-xmin)*i/N,y;
    try{y=f?f(x):0;}catch(e){y=null;}
    ys.push(isFinite(y)?y:null);
  }
  var lo=Infinity,hi=-Infinity;
  for(var i=0;i<ys.length;i++){var y=ys[i];if(y!==null){if(y<lo)lo=y;if(y>hi)hi=y;}}
  if(!isFinite(lo)||!isFinite(hi)){lo=-5;hi=5;}
  if(lo>0)lo=0;if(hi<0)hi=0;
  var pad=(hi-lo)*0.12||1;
  var ymin=num(scene.graph_ymin,lo-pad),ymax=num(scene.graph_ymax,hi+pad);
  if(ymax<=ymin)ymax=ymin+1;
  var t=makeT(W,H,xmin,xmax,ymin,ymax,logx,logy);
  drawFrame(ctx,W,H,scene,xmin,xmax,ymin,ymax,t);
  var limit=Math.floor(N*p);
  var curve=[];
  for(var i=0;i<=limit;i++){
    var x=xmin+(xmax-xmin)*i/N,y=ys[i];
    var px=t.tx(x);
    if(px===null){curve=[];continue;}
    if(y===null){curve=[];continue;}
    var py=t.ty(y);
    if(py===null)continue;
    curve.push({x:px,y:py});
  }
  if(curve.length>1){
    var edge=below?H:0;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(curve[0].x,edge);
    for(var k=0;k<curve.length;k++)ctx.lineTo(curve[k].x,curve[k].y);
    ctx.lineTo(curve[curve.length-1].x,edge);
    ctx.closePath();
    var gf=ctx.createLinearGradient(0,edge>H/2?edge:edge,0,edge>H/2?0:H);
    gf.addColorStop(0,hexA(color,0.3));gf.addColorStop(1,hexA(color,0.02));
    ctx.fillStyle=gf;ctx.fill();
    ctx.restore();
  }
  var pts=[],prevY=null,jump=(ymax-ymin)*0.7;
  for(var i=0;i<=limit;i++){
    var x=xmin+(xmax-xmin)*i/N,px=t.tx(x);
    if(px===null){prevY=null;continue;}
    var y=ys[i];
    if(y===null){prevY=null;continue;}
    if(prevY!==null&&Math.abs(y-prevY)>jump)prevY=null;
    var py=t.ty(y);
    if(py===null){prevY=y;continue;}
    pts.push({x:px,y:py});
    prevY=y;
  }
  if(pts.length>1)drawPolyline(ctx,pts,color,W);
  if(scene.graph_label&&p>0.03)drawLegend(ctx,[{label:scene.graph_label,color:color}],W);
}

var implicitCache=new WeakMap();
function drawImplicit(ctx,W,H,scene,p,color){
  var xmin=num(scene.graph_xmin,-5),xmax=num(scene.graph_xmax,5);
  var ymin=num(scene.graph_ymin,xmin),ymax=num(scene.graph_ymax,xmax);
  if(xmax<=xmin)xmax=xmin+1;
  if(ymax<=ymin)ymax=ymin+1;
  var t=makeT(W,H,xmin,xmax,ymin,ymax,false,false);
  drawFrame(ctx,W,H,scene,xmin,xmax,ymin,ymax,t);
  var f=compileFn2(String(scene.graph_func||'x*x+y*y-1'));
  if(!f)return;
  var target=num(scene.graph_implicit_eq!=null?scene.graph_implicit_eq:scene.graph_equals,0);
  var pts;
  if(implicitCache.has(ctx.canvas)){pts=implicitCache.get(ctx.canvas);}
  else{
    pts=[];
    var cols=240,rows=150;
    var dx=(xmax-xmin)/cols,dy=(ymax-ymin)/rows;
    function g(x,y){try{var v=f(x,y)-target;return isFinite(v)?v:0;}catch(e){return 0;}}
    for(var cy=0;cy<=rows;cy++){
      var y0=ymin+cy*dy;
      for(var cx=0;cx<=cols;cx++){
        var x0=xmin+cx*dx;
        var v00=g(x0,y0),v10=g(x0+dx,y0),v01=g(x0,y0+dy);
        if(cx<cols&&v00*v10<0){var xint=x0-v00*dx/(v10-v00);pts.push({x:xint,y:y0+dy/2});}
        if(cy<rows&&v00*v01<0){var yint=y0-v00*dy/(v01-v00);pts.push({x:x0+dx/2,y:yint});}
      }
    }
    implicitCache.set(ctx.canvas,pts);
  }
  var limit=Math.floor(pts.length*p);
  ctx.save();
  ctx.fillStyle=hexA(color,0.95);
  ctx.shadowColor=color;ctx.shadowBlur=6;
  for(var i=0;i<limit;i++){
    var q=pts[i];
    var px=t.tx(q.x),py=t.ty(q.y);
    if(px===null||py===null)continue;
    ctx.fillRect(px-1.6,py-1.6,3.2,3.2);
  }
  ctx.restore();
  if(scene.graph_label&&p>0.05)drawLegend(ctx,[{label:scene.graph_label,color:color}],W);
}

function drawScatter(ctx,W,H,scene,p,color){
  var raw=scene.graph_points||[];
  var all=raw.map(function(q){
    if(Array.isArray(q))return {x:num(q[0],0),y:num(q[1],0)};
    return {x:num(q&&q.x,0),y:num(q&&q.y,0)};
  });
  if(!all.length){drawFrame(ctx,W,H,scene,-5,5,-5,5,makeT(W,H,-5,5,-5,5,false,false));return;}
  var xs=[],ys=[];
  for(var i=0;i<all.length;i++){xs.push(all[i].x);ys.push(all[i].y);}
  var xmin=num(scene.graph_xmin,Math.min.apply(null,xs)),xmax=num(scene.graph_xmax,Math.max.apply(null,xs));
  var ymin=num(scene.graph_ymin,Math.min.apply(null,ys)),ymax=num(scene.graph_ymax,Math.max.apply(null,ys));
  var px=(xmax-xmin)*0.15||1,py=(ymax-ymin)*0.15||1;
  xmin-=px;xmax+=px;ymin-=py;ymax+=py;
  if(xmax<=xmin){xmin-=1;xmax+=1;}
  if(ymax<=ymin){ymin-=1;ymax+=1;}
  var t=makeT(W,H,xmin,xmax,ymin,ymax,false,false);
  drawFrame(ctx,W,H,scene,xmin,xmax,ymin,ymax,t);
  var limit=Math.floor(all.length*p);
  ctx.save();
  for(var i=0;i<limit;i++){
    var q=all[i],sx=t.tx(q.x),sy=t.ty(q.y);
    if(sx===null||sy===null)continue;
    ctx.shadowColor=color;ctx.shadowBlur=12;
    ctx.fillStyle=hexA(color,0.9);
    ctx.beginPath();ctx.arc(sx,sy,7,0,Math.PI*2);ctx.fill();
    ctx.shadowBlur=0;
    ctx.strokeStyle='rgba(255,255,255,0.9)';ctx.lineWidth=2;
    ctx.beginPath();ctx.arc(sx,sy,7,0,Math.PI*2);ctx.stroke();
  }
  ctx.restore();
  if(scene.graph_label&&p>0.05)drawLegend(ctx,[{label:scene.graph_label,color:color}],W);
}

function drawBars(ctx,W,H,scene,p,color){
  var raw=scene.graph_bars||scene.graph_func||[];
  if(!Array.isArray(raw))raw=[raw];
  var labels=(Array.isArray(scene.graph_bar_labels)?scene.graph_bar_labels:[]).length
    ?scene.graph_bar_labels
    :(Array.isArray(scene.graph_label)?scene.graph_label:[]);
  var vals=raw.map(function(b){return (typeof b==='object'&&b!==null)?num(b.value,0):num(b,0);});
  if(!vals.length){drawFrame(ctx,W,H,scene,0,1,0,1,makeT(W,H,0,1,0,1,false,false));return;}
  var maxv=Math.max.apply(null,vals.map(Math.abs))||1;
  var ymin=num(scene.graph_ymin,vals.some(function(v){return v<0;})?-maxv*1.15:0);
  var ymax=num(scene.graph_ymax,maxv*1.15);
  if(ymax<=ymin)ymax=ymin+1;
  var t=makeT(W,H,0,vals.length,ymin,ymax,false,false);
  drawFrame(ctx,W,H,scene,0,vals.length,ymin,ymax,t);
  var zeroY=t.ty(0),bw=(W/vals.length)*0.6;
  for(var i=0;i<vals.length;i++){
    var v=vals[i];
    var thresh=vals.length>1?i/(vals.length-1):0;
    var grow=clamp01((p-thresh)*Math.max(2,vals.length));
    if(grow<=0)continue;
    var fullH=(t.ty(0)-t.ty(v));
    var h=fullH*grow;
    var cx=(i+0.5)*W/vals.length,x=cx-bw/2;
    var top=Math.min(zeroY,zeroY-h),ht=Math.abs(h);
    ctx.fillStyle=hexA(color,0.85);
    roundRect(ctx,x,top,bw,ht,6);ctx.fill();
    ctx.strokeStyle=hexA(color,1);ctx.lineWidth=1.5;ctx.stroke();
    if(ht>32){
      ctx.fillStyle='rgba(255,255,255,0.92)';ctx.font='bold 22px Inter,sans-serif';ctx.textAlign='center';
      ctx.fillText(fmtTick(v),cx,top-10);
    }
  }
  for(var i=0;i<labels.length;i++){
    var cx=(i+0.5)*W/labels.length;
    ctx.fillStyle='rgba(255,255,255,0.6)';ctx.font='20px Inter,sans-serif';ctx.textAlign='center';
    ctx.fillText(String(labels[i]),cx,H-12);
  }
}

function normStr(s){return String(s||'').toLowerCase().replace(/\s+/g,'').normalize('NFD').replace(/[\u0300-\u036f]/g,'');}

function drawGrid(ctx,cx,cy,S,faint){
  var c1=faint?'rgba(255,255,255,0.06)':'rgba(255,255,255,0.1)';
  var c2=faint?'rgba(255,255,255,0.18)':'rgba(255,255,255,0.25)';
  ctx.strokeStyle=c1;ctx.lineWidth=1;
  for(var g=-3;g<=3;g++){
    ctx.beginPath();ctx.moveTo(cx+g*100,cy-300);ctx.lineTo(cx+g*100,cy+300);ctx.stroke();
    ctx.beginPath();ctx.moveTo(cx-300,cy+g*100);ctx.lineTo(cx+300,cy+g*100);ctx.stroke();
  }
  ctx.strokeStyle=c2;ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(cx-300,cy);ctx.lineTo(cx+300,cy);ctx.stroke();
  ctx.beginPath();ctx.moveTo(cx,cy-300);ctx.lineTo(cx,cy+300);ctx.stroke();
}

function drawVisual(canvasId,scene,progress){
  var cv=document.getElementById(canvasId);
  if(!cv)return;
  var ctx=cv.getContext('2d');
  var S=700,cx=S/2,cy=S/2;
  ctx.fillStyle='rgba(10,10,30,0.85)';
  ctx.fillRect(0,0,S,S);
  var formula=scene.formula||'';
  var sceneText=scene.text||'';
  var fml=normStr(formula);
  var txt=normStr(sceneText);
  var both=fml+'|'+txt;
  var p=Math.min(1,Math.max(0,progress));
  var accent=scene.themeColor||'#6c63ff';

  if(scene.visual_type==='graph_theory'||scene.graph_nodes||scene.graph_edges){
    var nodes=scene.graph_nodes||[];
    var edges=scene.graph_edges||[];
    var dir=scene.graph_directed===true;
    var NN=nodes.length||5;
    var R=Math.min(250,Math.max(180,280-NN*12));
    var total=Math.floor(p*(NN+edges.length));
    if(!nodes.length)for(var g=0;g<NN;g++)nodes.push('v'+(g+1));
    var positions=[];
    for(var g=0;g<NN;g++){
      var a=2*Math.PI*g/NN-Math.PI/2;
      positions.push({x:cx+R*Math.cos(a),y:cy+R*Math.sin(a),label:nodes[g]});
    }
    ctx.strokeStyle='rgba(255,255,255,0.1)';ctx.lineWidth=1;
    ctx.beginPath();ctx.arc(cx,cy,R+30,0,Math.PI*2);ctx.stroke();
    var drawEdges=Math.min(edges.length,Math.max(0,total));
    for(var g=0;g<drawEdges;g++){
      var e=edges[g];var eis=typeof e==='string'?e.split('-'):e;
      var ei=parseInt(eis[0])||0,ej=parseInt(eis[1])||0;
      var pi=positions[ei%NN],pj=positions[ej%NN];
      ctx.strokeStyle=hexA(accent,0.7);ctx.lineWidth=3;
      ctx.beginPath();ctx.moveTo(pi.x,pi.y);ctx.lineTo(pj.x,pj.y);ctx.stroke();
      if(dir){
        var dx=pj.x-pi.x,dy=pj.y-pi.y,ad=Math.sqrt(dx*dx+dy*dy);
        if(ad>1){dx/=ad;dy/=ad;
          ctx.fillStyle=hexA(accent,0.85);
          ctx.beginPath();ctx.moveTo(pj.x,pj.y);
          ctx.lineTo(pj.x-dx*18-dy*10,pj.y-dy*18+dx*10);
          ctx.lineTo(pj.x-dx*18+dy*10,pj.y-dy*18-dx*10);
          ctx.closePath();ctx.fill();
        }
      }
    }
    var drawNodes=Math.min(nodes.length,Math.max(0,total-edges.length));
    for(var g=0;g<drawNodes;g++){
      var pos=positions[g];
      var rad=22;
      ctx.fillStyle=hexA(accent,0.2);ctx.strokeStyle=accent;ctx.lineWidth=3;
      ctx.beginPath();ctx.arc(pos.x,pos.y,rad,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.fillStyle='#fff';ctx.font='bold 18px Inter,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
      ctx.fillText(pos.label,pos.x,pos.y);
    }
    return;
  }

  if(fml.indexOf('\\sin')>=0||fml.indexOf('\\cos')>=0||fml.indexOf('\\tan')>=0||
    (both.indexOf('seno')>=0||both.indexOf('coseno')>=0||both.indexOf('tangente')>=0||
     (both.indexOf('angulo')>=0&&both.indexOf('triangulo')<0&&both.indexOf('rectangulo')<0))){
    ctx.strokeStyle='rgba(255,255,255,0.12)';ctx.lineWidth=1;
    ctx.beginPath();ctx.arc(cx,cy,200,0,Math.PI*2);ctx.stroke();
    ctx.beginPath();ctx.moveTo(cx-250,cy);ctx.lineTo(cx+250,cy);ctx.stroke();
    ctx.beginPath();ctx.moveTo(cx,cy-250);ctx.lineTo(cx,cy+250);ctx.stroke();
    var angle=Math.PI/3*p;
    ctx.strokeStyle=accent;ctx.lineWidth=4;
    ctx.beginPath();ctx.arc(cx,cy,200,0,angle);ctx.stroke();
    ctx.fillStyle=accent;
    ctx.beginPath();ctx.arc(cx+200*Math.cos(angle),cy-200*Math.sin(angle),8,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='rgba(255,255,255,0.6)';ctx.font='24px Inter,sans-serif';ctx.textAlign='center';
    if(p>0.1)ctx.fillText('\u03B8',cx+80,cy-20);
    return;
  }

  if(both.indexOf('triang')>=0||both.indexOf('catet')>=0||both.indexOf('pitag')>=0||both.indexOf('hipoten')>=0||both.indexOf('rectangulo')>=0||fml.indexOf('a^2+b^2')>=0){
    var sz=250*p;
    var Ax=cx-sz,Ay=cy+sz;   // ángulo recto (abajo-izquierda)
    var Bx=cx+sz,By=cy+sz;   // base derecha
    var Cx=cx-sz,Cy=cy-sz;   // vértice superior
    ctx.strokeStyle=accent;ctx.lineWidth=5;
    ctx.beginPath();ctx.moveTo(Ax,Ay);ctx.lineTo(Bx,By);ctx.lineTo(Cx,Cy);ctx.closePath();ctx.stroke();
    ctx.fillStyle=hexA(accent,0.12);ctx.fill();
    if(p>0.3){
      ctx.fillStyle='rgba(255,255,255,0.5)';ctx.font='bold 30px Inter,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
      // arista a (base AB)
      ctx.fillText('a',cx,cy+sz+52);
      // arista b (cateto vertical AC)
      ctx.fillText('b',cx-sz-52,cy);
      // hipotenusa c (BC), etiqueta fuera del triángulo (arriba-derecha)
      ctx.fillText('c',cx+52,cy-52);
      // marcador de ángulo recto en A
      ctx.strokeStyle='rgba(255,255,255,0.5)';ctx.lineWidth=3;
      ctx.beginPath();ctx.moveTo(Ax+32,Ay);ctx.lineTo(Ax+32,Ay-32);ctx.lineTo(Ax,Ay-32);ctx.stroke();
      // etiquetas de vértices A, B, C en las esquinas
      ctx.fillStyle='rgba(255,255,255,0.85)';ctx.font='bold 26px Inter,sans-serif';
      ctx.fillText('A',Ax-34,Ay+40);
      ctx.fillText('B',Bx+34,By+40);
      ctx.fillText('C',Cx-34,Cy-40);
    }
    return;
  }

  if(fml.indexOf('\\sqrt')>=0||both.indexOf('raiz')>=0){
    drawGrid(ctx,cx,cy,S,true);
    var limit=200*p;
    ctx.strokeStyle=accent;ctx.lineWidth=4;ctx.shadowColor=accent;ctx.shadowBlur=15;
    ctx.beginPath();ctx.moveTo(cx-250,cy+80);
    ctx.lineTo(cx-250+40,cy-60);ctx.lineTo(cx-250+80,cy+80);
    ctx.lineTo(cx-250+limit,cy+80);
    ctx.stroke();ctx.shadowBlur=0;
    ctx.fillStyle='#fff';ctx.font='bold 100px Inter,sans-serif';ctx.textAlign='center';
    ctx.fillText('x',cx-250+limit/2,cy+70);
    return;
  }

  if(fml.indexOf('^')>=0||fml.indexOf('potenc')>=0||fml.indexOf('exponent')>=0||fml.indexOf('cuadrado')>=0||fml.indexOf('cubo')>=0){
    drawGrid(ctx,cx,cy,S,false);
    var pts=[];
    for(var px=-300;px<=300;px+=3){
      var xn=px/60;var yn=xn*xn;
      if(Math.abs(yn)>5)continue;
      pts.push({x:cx+px,y:cy-yn*60});
    }
    var drawTo=Math.floor(p*pts.length);
    ctx.strokeStyle=accent;ctx.lineWidth=4;ctx.shadowColor=accent;ctx.shadowBlur=12;
    ctx.beginPath();
    for(var k=0;k<drawTo&&k<pts.length;k++){
      if(k===0)ctx.moveTo(pts[k].x,pts[k].y);else ctx.lineTo(pts[k].x,pts[k].y);
    }
    ctx.stroke();ctx.shadowBlur=0;
    if(p>0.02){
      ctx.fillStyle='rgba(255,255,255,0.8)';ctx.font='bold 28px Inter,sans-serif';ctx.textAlign='right';
      ctx.fillText('y = x\u00B2',cx+280,cy-270);
    }
    return;
  }

  if(fml.indexOf('\\int')>=0||fml.indexOf('integral')>=0||fml.indexOf('area')>=0){
    drawGrid(ctx,cx,cy,S,false);
    var pts=[];
    for(var px=-250;px<=250;px+=2){
      var xn=px/80;var yn=0.5*xn*xn+0.5;
      pts.push({x:cx+px,y:cy-yn*80});
    }
    var drawTo=Math.floor(p*pts.length);
    if(drawTo>1){
      ctx.fillStyle=hexA(accent,0.28);
      ctx.beginPath();ctx.moveTo(pts[0].x,cy);
      for(var k=0;k<drawTo;k++)ctx.lineTo(pts[k].x,pts[k].y);
      ctx.lineTo(pts[drawTo-1].x,cy);ctx.closePath();ctx.fill();
    }
    ctx.strokeStyle=accent;ctx.lineWidth=3;ctx.shadowColor=accent;ctx.shadowBlur=10;
    ctx.beginPath();
    for(var k=0;k<drawTo;k++){
      if(k===0)ctx.moveTo(pts[k].x,pts[k].y);else ctx.lineTo(pts[k].x,pts[k].y);
    }
    ctx.stroke();ctx.shadowBlur=0;
    if(p>0.05){
      ctx.fillStyle='rgba(255,255,255,0.8)';ctx.font='bold 26px Inter,sans-serif';ctx.textAlign='center';
      ctx.fillText('\u222B f(x) dx',cx,cy-260);
    }
    return;
  }

  if(fml.indexOf('\\frac')>=0||fml.indexOf('divis')>=0||fml.indexOf('fraccion')>=0||fml.indexOf('frac')>=0){
    var lineW=250*p;
    ctx.strokeStyle=accent;ctx.lineWidth=5;
    ctx.beginPath();ctx.moveTo(cx-lineW,cy);ctx.lineTo(cx+lineW,cy);ctx.stroke();
    ctx.fillStyle='rgba(255,255,255,0.7)';ctx.font='bold 60px Inter,sans-serif';ctx.textAlign='center';
    if(p>0.1)ctx.fillText('n',cx,cy-40);
    if(p>0.3)ctx.fillText('m',cx,cy+80);
    ctx.fillStyle=hexA(accent,0.18);
    ctx.beginPath();ctx.arc(cx-140,cy-30,60,0,Math.PI*2);ctx.fill();
    ctx.beginPath();ctx.arc(cx+140,cy+40,60,0,Math.PI*2);ctx.fill();
    return;
  }

  if(fml.indexOf('\\lim')>=0||both.indexOf('limite')>=0){
    drawGrid(ctx,cx,cy,S,false);
    var pts=[];
    for(var px=-300;px<=300;px+=2){
      var xn=px/60;var yn=1/(xn+0.001);
      if(Math.abs(yn)>5)continue;
      pts.push({x:cx+px,y:cy-yn*50});
    }
    var drawTo=Math.floor(p*pts.length);
    ctx.strokeStyle='#ff6b6b';ctx.lineWidth=3;ctx.shadowColor='#ff6b6b';ctx.shadowBlur=10;
    ctx.beginPath();
    for(var k=0;k<drawTo&&k<pts.length;k++){
      if(k===0)ctx.moveTo(pts[k].x,pts[k].y);else ctx.lineTo(pts[k].x,pts[k].y);
    }
    ctx.stroke();ctx.shadowBlur=0;
    ctx.setLineDash([8,6]);
    ctx.strokeStyle='rgba(255,255,255,0.3)';ctx.lineWidth=2;
    ctx.beginPath();ctx.moveTo(cx,cy-300);ctx.lineTo(cx,cy+300);ctx.stroke();
    ctx.setLineDash([]);
    if(p>0.02){
      ctx.fillStyle='rgba(255,255,255,0.7)';ctx.font='bold 26px Inter,sans-serif';ctx.textAlign='center';
      ctx.fillText('l\u00EDmite',cx-200,cy-250);
    }
    return;
  }

  if(fml.indexOf('matrix')>=0||fml.indexOf('begin{bmatrix}')>=0||fml.indexOf('begin{pmatrix}')>=0||fml.indexOf('begin{vmatrix}')>=0){
    var sz=120*p;
    ctx.strokeStyle=accent;ctx.lineWidth=4;ctx.shadowColor=accent;ctx.shadowBlur=10;
    ctx.beginPath();
    ctx.moveTo(cx-sz*1.5,cy-sz*1.5);ctx.lineTo(cx-sz*1.5,cy+sz*1.5);
    ctx.moveTo(cx+sz*1.5,cy-sz*1.5);ctx.lineTo(cx+sz*1.5,cy+sz*1.5);
    ctx.stroke();ctx.shadowBlur=0;
    ctx.strokeStyle='rgba(255,255,255,0.15)';ctx.lineWidth=1;
    for(var r=0;r<3;r++)for(var c=0;c<3;c++){
      ctx.fillStyle='rgba(255,255,255,0.6)';ctx.font='32px Inter,sans-serif';ctx.textAlign='center';
      var vals=['a','b','c','d','e','f','g','h','i'];
      ctx.fillText(vals[r*3+c],cx+(c-1)*sz,cy+(r-1)*sz+12);
    }
    return;
  }

  ctx.fillStyle=hexA(accent,0.1);
  ctx.beginPath();ctx.arc(cx,cy,280,0,Math.PI*2);ctx.fill();
  ctx.fillStyle=hexA('#00d4ff',0.08);
  ctx.beginPath();ctx.arc(cx-80,cy-80,200,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='rgba(255,255,255,0.85)';
  var fs=Math.max(36,Math.min(64,Math.floor(700/((formula||'').length+1)*1.2)));
  ctx.font='bold '+fs+'px Inter,sans-serif';
  ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.shadowColor=accent;ctx.shadowBlur=20;
  ctx.fillText(formula||'Matem\u00E1ticas',cx,cy);
  ctx.shadowBlur=0;
}

window.drawGraph=drawGraph;
window.drawVisual=drawVisual;
window.compileMathExpr=compileFn;

return {
  drawGraph:drawGraph,
  drawVisual:drawVisual,
  compile:compileFn,
  preprocess:preprocessExpr
};

})();
