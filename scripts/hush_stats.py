# -*- coding: utf-8 -*-
"""HUSH.GG 통계 빌드 (GitHub Actions용) — data/games.json → 사이트 데이터
엑셀 파이프라인(build18.py)과 같은 계산: CP v2 · ELO v3(50경기까지 고정) · 선수/챔피언 집계
"""
import json, os, sys
from collections import defaultdict, OrderedDict
HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,'..','data')
def nm_fix(n): return n
K=20;DIV=400;ALPHA=0.25;M=0.30;BETA=0.10;S=5
def clamp(v,lo,hi):return max(lo,min(hi,v))
GAMESRC=json.load(open(os.path.join(DATA,'games.json'),encoding='utf-8'))
NG=len(GAMESRC)
# ── 정규화 경기 → 엑셀과 같은 행 구조(PS) · 블록 구조 ──
PS=[]; blocks=[]
POSO=['TOP','JUG','MID','ADC','SUP']
for g in GAMESRC:
    mn,sc=g['mn'],g['sc']; m=mn+sc/60
    t1win=g['t1'][0]['vd']=='승'
    win,lose=(g['t1'],g['t2']) if t1win else (g['t2'],g['t1'])
    rows=[]
    for team,res in ((win,'승'),(lose,'패')):
        tk=sum(p['k'] for p in team); td=sum(p['dmg'] for p in team)
        for p in sorted(team,key=lambda p:POSO.index(p['pos'])):
            r=[None]*46
            r[0]=int(g['date'].replace('.','')); r[4]=mn; r[6]=sc; r[8]=p['pos']; r[9]=p['name']; r[10]=p['champ']; r[11]=res
            r[13],r[14],r[15]=p['k'],p['d'],p['a']; r[16]=p['vs']; r[17]=p['dmg']; r[18]=p['dt']; r[19]=p['gold']; r[20]=p['cc']; r[21]=p['piwa']
            r[34]=p['vs']/m; r[35]=p['dmg']/m; r[36]=p['dmg']/td if td else 0; r[37]=(p['k']+p['a'])/tk if tk else 0
            r[38]=p['dmg']/p['gold'] if p['gold'] else 0; r[39]=p['gold']/m; r[40]=p['dt']/m; r[41]=p['cc']/m; r[42]=p['piwa']/m*10
            r[43]=(p['k']+p['a'])/p['d'] if p['d'] else 99
            if p.get('dv'): r[34:44]=p['dv']
            r[44]=p['mit']/m if isinstance(p.get('mit'),(int,float)) else None; r[45]=g['no']   # 엑셀 시절 경기: 엑셀 계산값 그대로 (골드 이상값 보정 등 재현)
            rows.append(r)
    PS+=rows
    pr=[]
    for i in range(5):
        r=[None]*40
        if i<len(g['t1']):
            a=g['t1'][i]; r[0],r[1],r[2],r[3],r[5],r[6],r[7],r[8],r[9],r[10],r[11],r[12],r[28]=a['pos'],a['name'],a['champ'],a['vd'],a['k'],a['d'],a['a'],a['vs'],a['dmg'],a['dt'],a['gold'],a['cc'],a['cs']
        if i<len(g['t2']):
            b=g['t2'][i]; r[14],r[15],r[16],r[17],r[19],r[20],r[21],r[22],r[23],r[24],r[25],r[26],r[29]=b['pos'],b['name'],b['champ'],b['vd'],b['k'],b['d'],b['a'],b['vs'],b['dmg'],b['dt'],b['gold'],b['cc'],b['cs']
        pr.append(r)
    for j,bn in enumerate(g.get('bans',[])[:10]): pr[0][30+j]=bn
    blocks.append((r[0] if False else int(g['date'].replace('.','')),mn,sc,pr))
DATE_FIX={}
# ═══ CP v2 (파이프라인 직접 계산 · 2026-11-13 이명우 확정) ═══
# 엑셀 CP 열(33)은 쓰지 않고 아래 공식으로 다시 계산해 r[33]에 덮어씀.
#  ① 기준값 = 내전 전체 포지션별 평균 (매 업데이트 자동 갱신, 2020 고정값 폐지)
#  ② 항목별 상한: 기준값 × 배수에서 만점 (DPM·CCPM·DTPM·PiWA ×2, VSPM ×1.75, DPG ×2.1, KP는 100%)
#  ③ PiWA 포지션별 기준 (엑셀 수식의 탑 기준 고정 오류 수정)
#  ④ 생존(데스) 항목 추가: 덜 죽을수록 점수 (데스가 평균의 2배면 0점)
#  ⑤ KP 가중치 상향 (정글 0.75 · 미드 0.5 · 원딜 0.75 · 서폿 1.0)
#  ⑥ 포지션별 가중치 총합 7로 통일 · 전체 스케일 1.2608 고정 (기존 CP와 비슷한 숫자대)
#  ⑦ 챔프별 수동 보정: USE_CHAMP_ADJ로 켜고 끔 (기본 끔)
CPW={'TOP':dict(DPM=2,VSPM=1.25,KP=0.5,CCPM=1,DTPM=0.75,DPG=0.5,PIWA=0.5,DEATH=0.5),
     'JUG':dict(DPM=1.5,VSPM=2,KP=0.75,CCPM=0.75,DTPM=0.5,DPG=0.25,PIWA=0.75,DEATH=0.5),
     'MID':dict(DPM=2.5,VSPM=1.75,KP=0.5,CCPM=0.5,DTPM=0.5,DPG=0.75,PIWA=0.5,DEATH=0.5),
     'ADC':dict(DPM=2.75,VSPM=1.5,KP=0.75,CCPM=0.5,DTPM=0.25,DPG=0.75,PIWA=0.5,DEATH=0.5),
     'SUP':dict(DPM=1,VSPM=2.5,KP=1.0,CCPM=1,DTPM=0.5,DPG=0.5,PIWA=0.75,DEATH=0.5)}
CPMULT=dict(DPM=2,VSPM=1.75,CCPM=2,DTPM=2,DPG=2.1,PIWA=2,D=2)
CP_SCALE=1.2608
USE_CHAMP_ADJ=False
CHAMP_ADJ={"마오카이":-0.15,"애쉬":-0.1,"유미":0.05,"바드":-0.05,"카르마":0.05,"룰루":0.05,"모르가나":-0.15,"피오라":0.1,"샤코":-0.1,"벨코즈":-0.05,"브라움":-0.05,"오공":0.1,"케이틀린":0.05,"럭스":-0.05,"레오나":-0.05,"모데카이저":0.05,"클레드":0.05,"람머스":0.05,"사일러스":0.05,"판테온":0.05,"세나":-0.1,"갱플랭크":0.05,"리 신":0.1}
def _cpstats(r):
    # CCPM은 원본 CC초에서 직접 계산 — 녹턴은 궁 시야차단이 CC로 과대 집계돼 1/5 보정 (엑셀 수식에 의존하지 않음)
    _m=r[4]+(r[6]/60 if isinstance(r[6],(int,float)) else 0)
    _cc=(r[20]/_m if _m else 0)/(5 if r[10]=='녹턴' else 1)
    return dict(DPM=r[35],VSPM=r[34],KP=r[37],CCPM=_cc,DTPM=r[40],DPG=r[38],PIWA=r[42],D=r[14])
_CPROWS=PS[:NG*10]
_CPAVG={}
for _p in ['TOP','JUG','MID','ADC','SUP']:
    _rs=[_cpstats(r) for r in _CPROWS if r[8]==_p]
    _CPAVG[_p]={k:(sum(x[k] for x in _rs)/len(_rs) if _rs else 1) for k in ['DPM','VSPM','KP','CCPM','DTPM','DPG','PIWA','D']}
# ── 피해 경감(MIT) 반영: 51경기부터 (2026-11-26 이명우 확정 — 이전 경기 CP는 그대로) ──
#  받은 딜(DTPM) 가중치 일부를 '분당 피해 경감'으로 옮김 → 포지션별 가중치 총합은 그대로(점수대 유지)
CP_MIT_FROM=50
MIT_SPLIT={'TOP':(0.4,0.35),'JUG':(0.3,0.2),'MID':(0.35,0.15),'ADC':(0.15,0.1),'SUP':(0.3,0.2)}   # (DTPM, MIT)
_MITAVG={}
for _p in ['TOP','JUG','MID','ADC','SUP']:
    _ms=[r[44] for r in _CPROWS if r[8]==_p and isinstance(r[44],(int,float))]
    _MITAVG[_p]=sum(_ms)/len(_ms) if _ms else 0
def cp_v2(r):
    p=r[8]; s=_cpstats(r); w=dict(CPW[p]); a=_CPAVG[p]; sc=7.0/sum(w.values()); v=0
    use_mit = r[45] and r[45]>CP_MIT_FROM and isinstance(r[44],(int,float)) and _MITAVG[p]
    if use_mit:
        w['DTPM'],wm=MIT_SPLIT[p]
        v+=wm*sc*min(r[44]/(2*_MITAVG[p]),1.0)
    for key in ['DPM','VSPM','CCPM','DTPM','DPG','PIWA']:
        v+=w[key]*sc*(min(s[key]/(CPMULT[key]*a[key]),1.0) if a[key] else 0)
    v+=w['KP']*sc*min(s['KP'],1.0)
    v+=w['DEATH']*sc*(1-min(s['D']/(CPMULT['D']*a['D']),1.0) if a['D'] else 1)
    v*=CP_SCALE
    if USE_CHAMP_ADJ and r[10] in CHAMP_ADJ: v*=1+CHAMP_ADJ[r[10]]
    return v
for r in _CPROWS: r[33]=cp_v2(r)
def mins(r):return r[4]+(r[6]/60 if isinstance(r[6],(int,float)) else 0)
cs_map={}
for gi,(_,_,_,pr) in enumerate(blocks):
    for r in pr:
        if r[1]:cs_map[(gi,nm_fix(r[1]))]=r[28]
        if r[15]:cs_map[(gi,nm_fix(r[15]))]=r[29]
games=[]
for gi in range(NG):
    ch=PS[gi*10:(gi+1)*10]
    wins=[(r[9],r[33]) for r in ch if r[11]=='승']
    loses=[(r[9],r[33]) for r in ch if r[11]=='패']
    cps=[r[33] for r in ch if isinstance(r[33],(int,float))]
    games.append((wins,loses,sum(cps)/len(cps) if cps else 0))
elo=defaultdict(lambda:1000.0);streak={};hist=defaultdict(lambda:[1000])
# ELO_FREEZE: 50경기까지의 ELO는 기존 값 고정 (2026-11-25 이명우 확정 — API 교정으로 수치가 바뀌어도 ELO는 유지)
#  · 고정 대상 = elo_frozen50.json 에 있는 선수 (11/19 대타 교정 대상 게스트 6명은 제외 → 새로 계산)
_FZ=json.load(open(os.path.join(DATA,'elo_frozen50.json'),encoding='utf-8')) if os.path.exists(os.path.join(DATA,'elo_frozen50.json')) else None
for _gix,(wins,loses,cp_avg) in enumerate(games):
    if _FZ and _gix==_FZ['after']:
        for _n,_h in _FZ['hist'].items(): elo[_n]=float(_h[-1]); hist[_n]=list(_h)
        for _n,_st in _FZ['streak'].items(): streak[_n]=tuple(_st)
    wA=sum(elo[n] for n,_ in wins)/5;lA=sum(elo[n] for n,_ in loses)/5
    eW=1/(1+10**((lA-wA)/DIV))
    for n,cp in wins:
        perf=clamp((cp-cp_avg)/cp_avg*ALPHA,-M,M) if cp_avg>0 and isinstance(cp,(int,float)) else 0
        st=streak.get(n,('',0));sc=(1+min(st[1]-1,S)*BETA) if st[0]=='W' and st[1]>=2 else 1.0
        elo[n]+=K*(1-eW)*(1+perf)*sc
    for n,cp in loses:
        perf=clamp((cp-cp_avg)/cp_avg*ALPHA,-M,M) if cp_avg>0 and isinstance(cp,(int,float)) else 0
        st=streak.get(n,('',0));sc=(1+min(st[1]-1,S)*BETA) if st[0]=='L' and st[1]>=2 else 1.0
        elo[n]+=K*(0-(1-eW))*(1-perf)*sc
    for n,_ in wins:
        st=streak.get(n,('',0));streak[n]=('W',st[1]+1 if st[0]=='W' else 1);hist[n].append(round(elo[n]))
    for n,_ in loses:
        st=streak.get(n,('',0));streak[n]=('L',st[1]+1 if st[0]=='L' else 1);hist[n].append(round(elo[n]))
if _FZ and len(games)==_FZ['after']:
    for _n,_h in _FZ['hist'].items(): elo[_n]=float(_h[-1]); hist[_n]=list(_h)
ELO_FINAL={n:round(v) for n,v in elo.items()}
by=defaultdict(list);order=[]
for gi in range(NG):
    for r in PS[gi*10:(gi+1)*10]:
        if r[9] not in by:order.append(r[9])
        by[r[9]].append((gi,r))
def mean(xs):return sum(xs)/len(xs) if xs else 0
PLAYERS=OrderedDict()
for nm in order:
    recs=by[nm];rows=[r for _,r in recs];n=len(rows)
    wins=sum(1 for r in rows if r[11]=='승')
    posc=defaultdict(int)
    for r in rows:posc[r[8]]+=1
    pos=max(posc.items(),key=lambda x:x[1])[0]
    cps=[r[33] for r in rows]
    gpm=mean([r[19]/mins(r) for r in rows]);dpg=mean([r[17]/r[19] for r in rows if r[19]])
    css=[cs_map[(gi,nm)]/mins(r) for gi,r in recs if isinstance(cs_map.get((gi,nm)),(int,float)) and mins(r)]
    sk=sum(r[13] for r in rows);sd=sum(r[14] for r in rows);sa=sum(r[15] for r in rows)
    champ=OrderedDict()
    for r in rows:
        c=r[10]
        if c not in champ:champ[c]={"games":0,"wins":0,"k":0,"d":0,"a":0}
        champ[c]["games"]+=1;champ[c]["wins"]+=(1 if r[11]=='승' else 0)
        champ[c]["k"]+=r[13];champ[c]["d"]+=r[14];champ[c]["a"]+=r[15]
    most=sorted(champ.items(),key=lambda x:-x[1]["games"])
    PLAYERS[nm]={"name":nm,"pos":pos,"games":n,"wins":wins,"losses":n-wins,"wr":round(wins/n*100),
      "elo":ELO_FINAL[nm],
      "kda":round((sk+sa)/sd,2) if sd else float(sk+sa),
      "k":round(mean([r[13] for r in rows]),1),"d":round(mean([r[14] for r in rows]),1),"a":round(mean([r[15] for r in rows]),1),
      "dpm":round(mean([r[35] for r in rows])),"vspm":round(mean([r[34] for r in rows]),2),
      "kp":round(mean([r[37] for r in rows])*100),"dtpm":round(mean([r[40] for r in rows])),
      "gpm":round(gpm),"ccpm":round(mean([r[41] for r in rows]),2),"dpg":round(dpg,2),
      "piwa":round(mean([r[42] for r in rows]),2),"dpmPct":round(mean([r[36] for r in rows])*100,1),
      "cs_per_min":round(mean(css),1) if css else 0,
      "cp_avg":round(mean(cps),2),"cp_best":round(max(cps),2),"cp_worst":round(min(cps),2),
      "champPool":len(champ),
      "mostChamps":[[c,d] for c,d in most]}
GAMES=[];DETAILS=[];MATCHUPS=[];BANS_ALL=[]
for gi,(date,mn,sc_,pr) in enumerate(blocks):
    dstr=f"{str(date)[:4]}.{str(date)[4:6]}.{str(date)[6:]}"
    dstr=DATE_FIX.get(gi+1,dstr)
    tstr=f"{mn:02d}:{sc_:02d}";dur=round(mn+sc_/60,2)
    t1=[];t2=[]
    for r in pr:
        if r[1]:t1.append(dict(pos=r[0],name=nm_fix(r[1]),champ=r[2],vd=r[3],k=r[5],d=r[6],a=r[7],vs=r[8],dmg=r[9],dt=r[10],gold=r[11],cc=r[12],cs=r[28]))
        if r[15]:t2.append(dict(pos=r[14],name=nm_fix(r[15]),champ=r[16],vd=r[17],k=r[19],d=r[20],a=r[21],vs=r[22],dmg=r[23],dt=r[24],gold=r[25],cc=r[26],cs=r[29]))
    t1win=t1[0]['vd']=='승'
    win,lose=(t1,t2) if t1win else (t2,t1)
    bans=[pr[0][c] for c in range(30,40) if pr[0][c]]
    BANS_ALL.append(bans)
    GAMES.append({"no":gi+1,"date":dstr,"time":tstr,
      "win":[f"{p['name']}({p['pos']})" for p in win],"lose":[f"{p['name']}({p['pos']})" for p in lose],
      "winChamps":[p['champ'] for p in win],"loseChamps":[p['champ'] for p in lose],"bans":bans,"blueWin":t1win})
    psmap={r[9]:r for r in PS[gi*10:(gi+1)*10]}
    dps=[]
    for p in (win+lose):
        r=psmap[p['name']]
        dps.append({"name":p['name'],"pos":p['pos'],"champ":p['champ'],
          "team":"win" if p in win else "lose","k":p['k'],"d":p['d'],"a":p['a'],"vs":p['vs'],
          "dmg":p['dmg'],"dt":p['dt'],"gold":p['gold'],"cc":p['cc'],"cs":p['cs'],
          "cp":round(r[33],2),"dpm":round(r[35],0),"kda":round(r[43],2),"piwa":round(r[42],2)})
    DETAILS.append({"no":gi+1,"date":dstr,"durMin":dur,"players":dps})
    wB={p['pos']:p['champ'] for p in win};lB={p['pos']:p['champ'] for p in lose}
    for po in ['TOP','JUG','MID','ADC','SUP']:
        if po in wB and po in lB:MATCHUPS.append({"pos":po,"win":wB[po],"lose":lB[po]})
cagg=defaultdict(list)
for gi in range(NG):
    for r in PS[gi*10:(gi+1)*10]:cagg[r[10]].append((gi,r))
CHAMP_STATS=OrderedDict()
for c,recs in cagg.items():
    rows=[r for _,r in recs]
    css=[cs_map[(gi,r[9])]/mins(r) for gi,r in recs if isinstance(cs_map.get((gi,r[9])),(int,float))]
    CHAMP_STATS[c]={"pos":__import__("collections").Counter([r[8] for r in rows]).most_common(1)[0][0],
      "players":sorted(set(r[9] for r in rows)),
      "dpm":round(mean([r[35] for r in rows])),"vspm":round(mean([r[34] for r in rows]),2),
      "kp":round(mean([r[37] for r in rows])*100),"dtpm":round(mean([r[40] for r in rows])),
      "gpm":round(mean([r[19]/mins(r) for r in rows])),"ccpm":round(mean([r[41] for r in rows]),2),
      "dpg":round(mean([r[17]/r[19] for r in rows if r[19]]),2),
      "piwa":round(mean([r[42] for r in rows]),2),"dpmPct":round(mean([r[36] for r in rows])*100,1),
      "cp":round(mean([r[33] for r in rows]),2),
      "cs_per_min":round(mean(css),1) if css else 0}
json.dump({"PLAYERS":PLAYERS,"GAMES":GAMES,"GAME_DETAILS":DETAILS,"MATCHUPS":MATCHUPS,
  "CHAMP_STATS":CHAMP_STATS,"ELO_HISTORY":{n:hist[n] for n in order},"NG":NG},
  open(sys.argv[1] if len(sys.argv)>1 else 'build.json','w',encoding='utf-8'),ensure_ascii=False)
print(f"빌드: {len(PLAYERS)}명 / {NG}게임")
