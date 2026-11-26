// HUSH.GG 선수 분석 리포트용 근거 자료(dossier) 뽑기 — 사이트 계산 함수를 그대로 사용
// 사용: node tools/report_dossier.js index.html out.txt [--since 50] [--names 이또,생불]
//  --since N : N번 경기 이후 출전한 선수만 (리포트 asof 기준 갱신 대상 찾기)
//  아무 옵션 없으면: 저장된 리포트의 asof 보다 최근 경기에 나온 선수 + 리포트가 없는 선수
const { chromium } = require('playwright'); const fs=require('fs'); const path=require('path');
const args=process.argv.slice(2); const idx=path.resolve(args[0]); const outp=args[1];
function opt(k){ const i=args.indexOf(k); return i>=0?args[i+1]:null; }
(async()=>{ const b=await chromium.launch(); const p=await b.newPage();
 await p.goto('file://'+idx,{waitUntil:'domcontentloaded'}); await p.waitForTimeout(800);
 const r=await p.evaluate(([since,namesArg])=>{
  var want=null;
  if(namesArg) want=namesArg.split(',');
  else {
    want=[];
    Object.keys(PLAYERS).forEach(function(n){
      var R=PLAYER_REPORTS[n], asof=(since!==null)?+since:((R&&typeof R==='object'&&R.asof)||0);
      var played=GAME_DETAILS.some(function(g){ return g.no>asof && g.players.some(function(x){return x.name===n;}); });
      if(played || !(R&&typeof R==='object')) want.push(n);
    });
  }
  var head='# 최신 경기 #'+GAMES.length+' ('+GAMES[GAMES.length-1].date+') · 대상 '+want.length+'명: '+want.join(', ')+'\n';
  try{ var miss={}; Object.keys(PLAYERS).forEach(function(n){ var c=phChamp(n); if(c && !(c.id in CHAMP_SKIN)) miss[c.id]=1; }); var ml=Object.keys(miss); head+='# 헤더 일러스트 스킨 미등록: '+(ml.length?ml.join(', '):'없음')+'\n'; }catch(e){}
  head+='\n';
  var PK={TOP:'탑',JUG:'정글',MID:'미드',ADC:'원딜',SUP:'서폿'};
  var MA={}; GAME_DETAILS.forEach(function(g){ ['win','lose'].forEach(function(t){ var x=g.players.filter(function(p){return p.team===t}).sort(function(a,b){return b.cp-a.cp})[0]; if(!x)return; MA[x.name]=MA[x.name]||{mvp:0,ace:0}; MA[x.name][t==='win'?'mvp':'ace']++; }); });
  function rel(n,same){ var rec={}; GAME_DETAILS.forEach(function(g){ var me=g.players.filter(function(p){return p.name===n})[0]; if(!me)return; g.players.forEach(function(p){ if(p.name===n)return; if((p.team===me.team)!==same)return; var o=rec[p.name]=rec[p.name]||{name:p.name,games:0,wins:0}; o.games++; if(me.team==='win')o.wins++; }); }); return Object.keys(rec).map(function(k){var o=rec[k];o.wr=o.wins/o.games*100;return o;}); }
  var out=[];
  var names=Object.keys(PLAYERS).filter(function(n){ return !want || want.indexOf(n)>=0; }).sort(function(a,b){return PLAYERS[b].games-PLAYERS[a].games;});
  names.forEach(function(n){
   var P0=PLAYERS[n], L=[];
   var rows=playerRows(n); rows.sort(function(a,b){return a.no-b.no;});
   var ri=playerRankInfo(n), pr=posRecord(n);
   L.push('### '+n+' | 주'+PK[P0.pos]+' | '+P0.games+'전 '+P0.wins+'승('+P0.wr+'%) | ELO '+P0.elo+' '+(tierOf(P0.elo).name||JSON.stringify(tierOf(P0.elo)))+' | ELO순위 '+ri.eloRank+'/'+ri.total+' | MVP '+((MA[n]||{}).mvp||0)+' ACE '+((MA[n]||{}).ace||0)+' | 날짜 '+rows[0].date+'~'+rows[rows.length-1].date+' ('+new Set(rows.map(function(r){return r.date})).size+'회 참가)');
   L.push('라인: '+Object.keys(pr).filter(function(k){return pr[k].g}).map(function(k){return PK[k]+' '+pr[k].g+'전'+pr[k].w+'승'}).join(', '));
   L.push('통산: KDA '+P0.kda+' ('+P0.k+'/'+P0.d+'/'+P0.a+') CP '+P0.cp_avg+' (best '+P0.cp_best+' worst '+P0.cp_worst+') DPM '+P0.dpm+' 딜비중 '+P0.dpmPct+'% KP '+P0.kp+'% VSPM '+P0.vspm+' CSPM '+P0.cs_per_min+' GPM '+P0.gpm+' 챔프 '+P0.champPool+'종');
   // champs
   var cm={}; rows.forEach(function(r){var c=r.p.champ+'('+PK[r.p.pos]+')'; var o=cm[c]=cm[c]||{g:0,w:0,cp:0,k:0,d:0,a:0}; o.g++; if(r.p.team==='win')o.w++; o.cp+=r.p.cp;o.k+=r.p.k;o.d+=r.p.d;o.a+=r.p.a;});
   L.push('챔프: '+Object.keys(cm).sort(function(a,b){return cm[b].g-cm[a].g||cm[b].w-cm[a].w}).slice(0,7).map(function(c){var o=cm[c];return c+' '+o.g+'전'+o.w+'승 CP'+(o.cp/o.g).toFixed(2)+' '+(o.k/o.g).toFixed(1)+'/'+(o.d/o.g).toFixed(1)+'/'+(o.a/o.g).toFixed(1)}).join('; '));
   try{ var r6=radar6(n); L.push('레이더6: '+JSON.stringify(r6)); }catch(e){}
   // scouting ranks main pos & other pos with >=3 games
   Object.keys(pr).filter(function(k){return pr[k].g>=3}).forEach(function(pos){
     var good=[],bad=[]; Object.keys(SC2_DEF).forEach(function(m){ try{ if(sc2Neutral(pos,m)) return; var x=sc2Rank(n,pos,m,true); if(!x) return;
       var lb=SC2_DEF[m][0]+' '+x.rank+'/'+x.total+'('+sc2Fmt(m,x.v)+' ~'+sc2Fmt(m,x.avg)+')';
       if(x.rank<=2) good.push(lb); else if(x.rank>=x.total-1) bad.push(lb); }catch(e){} });
     if(good.length||bad.length) L.push('스카우팅['+PK[pos]+'] 강: '+good.join(', ')+' | 약: '+bad.join(', '));
   });
   // win vs loss cp
   var wr=rows.filter(function(r){return r.p.team==='win'}), lr=rows.filter(function(r){return r.p.team!=='win'});
   var av=function(a,f){return a.length?(a.reduce(function(s,r){return s+f(r)},0)/a.length):0};
   L.push('승/패 CP '+av(wr,function(r){return r.p.cp}).toFixed(2)+'/'+av(lr,function(r){return r.p.cp}).toFixed(2)+' 승/패 데스 '+av(wr,function(r){return r.p.d}).toFixed(1)+'/'+av(lr,function(r){return r.p.d}).toFixed(1));
   // after loss/win
   var al=[0,0],aw=[0,0]; for(var i=1;i<rows.length;i++){var prev=rows[i-1].p.team==='win', w=rows[i].p.team==='win'; if(prev){aw[0]++;if(w)aw[1]++;}else{al[0]++;if(w)al[1]++;}}
   // streaks
   var mw=0,ml=0,cw=0,cl=0; rows.forEach(function(r){if(r.p.team==='win'){cw++;cl=0;}else{cl++;cw=0;} mw=Math.max(mw,cw);ml=Math.max(ml,cl);});
   var cs=currentStreak(n);
   L.push('패배 다음판 '+al[1]+'/'+al[0]+'승, 승리 다음판 '+aw[1]+'/'+aw[0]+'승 | 최장연승 '+mw+' 최장연패 '+ml+' | 현재 '+cs.n+(cs.type==='W'?'연승':'연패'));
   // recent 10
   var r10=rows.slice(-10); L.push('최근'+r10.length+': '+r10.filter(function(r){return r.p.team==='win'}).length+'승 CP '+av(r10,function(r){return r.p.cp}).toFixed(2)+' | 최근 경기: '+rows.slice(-4).map(function(r){return '#'+r.no+' '+r.p.champ+'('+PK[r.p.pos]+') '+r.p.k+'/'+r.p.d+'/'+r.p.a+' '+(r.p.team==='win'?'승':'패')+' CP'+r.p.cp}).join(', '));
   try{ var c=consistencyRank(n); if(c) L.push('꾸준함 '+c.rank+'/'+c.total);}catch(e){}
   try{ L.push('경기시간: '+durationHtml(n).replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').replace('⏱️ 경기 시간별 성적','').trim()); }catch(e){}
   var duo=rel(n,true).filter(function(d){return d.games>=3}).sort(function(a,b){return b.wr-a.wr||b.games-a.games});
   if(duo.length) L.push('듀오(3판+): 베스트 '+duo.slice(0,3).map(function(d){return d.name+' '+d.games+'전'+d.wins+'승'}).join(', ')+' / 워스트 '+duo.slice(-2).map(function(d){return d.name+' '+d.games+'전'+d.wins+'승'}).join(', '));
   var riv=rel(n,false).filter(function(d){return d.games>=3}).sort(function(a,b){return b.wr-a.wr||b.games-a.games});
   if(riv.length) L.push('상대전(3판+): 먹잇감 '+riv.slice(0,3).map(function(d){return d.name+' '+d.games+'전'+d.wins+'승'}).join(', ')+' / 천적 '+riv.slice(-3).map(function(d){return d.name+' '+d.games+'전'+d.wins+'승'}).join(', '));
   try{ var bd=botDuoHtml(n).replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim(); if(bd) L.push('바텀듀오: '+bd.slice(0,260)); }catch(e){}
   // game badges
   var gbc={}; rows.forEach(function(r){ try{ (gameBadges(r.no)[n]||[]).forEach(function(x){gbc[x.t]=(gbc[x.t]||0)+1}); }catch(e){} });
   if(Object.keys(gbc).length) L.push('판별배지: '+Object.keys(gbc).sort(function(a,b){return gbc[b]-gbc[a]}).map(function(k){return k+'×'+gbc[k]}).join(', '));
   try{ L.push('개인최고: '+personalBests(n).slice(0,5).map(function(x){return x.label+' '+x.val+(x.r?'(#'+x.r.no+' '+x.r.p.champ+')':'')}).join(', ')); }catch(e){}
   try{ L.push('비슷한선수: '+similarPlayers(n,2).map(function(x){return x.name+' '+x.sim}).join(', ')); }catch(e){}
   var api=apiRowsOf(n); L.push('API경기 '+api.length);
   var R=PLAYER_REPORTS[n]; L.push('기존리포트: '+(R&&typeof R==='object'?JSON.stringify(R):'없음 (새로 작성)'));
   out.push(L.join('\n'));
  });
  return head+out.join('\n\n'); }, [opt('--since'), opt('--names')]);
 fs.writeFileSync(outp,r); console.log(r.split('\n')[0]); await b.close(); })();
