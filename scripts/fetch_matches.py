# -*- coding: utf-8 -*-
"""HUSH.GG — 라이엇 API에서 새 내전 경기를 찾아 data/ 에 추가 (GitHub Actions용)

환경 변수
  RIOT_API_KEY : 라이엇 API 키 (저장소 Secrets)
  BANS         : (선택) 밴 목록. 예) "51: 아리, 리 신, 오공\n52: 자야, 렐"
  EXCLUDE      : (선택) 넣지 않을 경기 ID. 예) "KR_1234567890, KR_2345678901"
동작
  1) data/accounts.json 의 멤버 계정마다 마지막 경기 이후 토너먼트 경기 목록 조회
  2) 처음 보는 경기만 경기 정보 + 타임라인을 받아 내전 경기인지 확인
     (5분 이상 · 등록된 멤버 계정 5명 이상 · 사용자 설정/토너먼트 게임)
  3) 시작 시간 순으로 경기 번호를 붙여 data/games.json · data/api_details.json 에 추가
  4) 처음 보는 계정은 소환사명으로 자동 등록 (accounts.json 의 "auto": true — 이름을 고쳐주세요)
"""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
ROOT = os.path.join(HERE, '..')
BASE = 'https://asia.api.riotgames.com'
KEY = os.environ.get('RIOT_API_KEY', '').strip()
POS = {'TOP': 'TOP', 'JUNGLE': 'JUG', 'MIDDLE': 'MID', 'BOTTOM': 'ADC', 'UTILITY': 'SUP'}
POSO = ['TOP', 'JUG', 'MID', 'ADC', 'SUP']
SKIP_ITEMS = {2003, 2031, 2033, 2055, 2138, 2139, 2140, 3340, 3363, 3364, 2010, 2422, 2150, 2151, 2152}
PING_KEYS = ['allInPings', 'assistMePings', 'basicPings', 'commandPings', 'dangerPings', 'enemyMissingPings',
             'enemyVisionPings', 'getBackPings', 'holdPings', 'needVisionPings', 'onMyWayPings', 'pushPings',
             'retreatPings', 'visionClearedPings']
MON = {'DRAGON': 'D', 'BARON_NASHOR': 'B', 'RIFTHERALD': 'H', 'HORDE': 'G', 'ATAKHAN': 'A'}
SUMMARY = []


def log(s):
    print(s); SUMMARY.append(s)


def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


def save(name, obj, compact=False):
    with open(os.path.join(DATA, name), 'w', encoding='utf-8') as f:
        if compact: json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
        else: json.dump(obj, f, ensure_ascii=False, indent=1)


def get(path, params=None):
    url = BASE + path + ('?' + urllib.parse.urlencode(params) if params else '')
    for _ in range(8):
        req = urllib.request.Request(url, headers={'X-Riot-Token': KEY, 'User-Agent': 'HUSH.GG-actions'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                time.sleep(1.3)
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get('Retry-After', '10')) + 1); continue
            if e.code in (500, 502, 503, 504):
                time.sleep(5); continue
            if e.code == 404:
                return None
            if e.code in (401, 403):
                sys.exit('[오류] API 키가 없거나 만료됐습니다 (HTTP %d). 저장소 Secrets 의 RIOT_API_KEY 를 확인하세요.' % e.code)
            sys.exit('[오류] HTTP %d %s' % (e.code, path))
        except urllib.error.URLError:
            time.sleep(5)
    sys.exit('[오류] 라이엇 서버 응답 없음')


def champ_kr_map(games):
    """영문 챔피언 ID → 한글 이름. 사이트에서 이미 쓰는 표기(예: 이즈리얼·초가스·리 신)를 우선"""
    s = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    m = re.search(r'const CMAP\s*=\s*', s)
    cmap, _ = json.JSONDecoder().raw_decode(s[m.end():])
    used = {p['champ'] for g in games for p in g['t1'] + g['t2']}
    out = {}
    for kr, en in cmap.items():
        k = en.lower()
        if k not in out or (kr in used and out[k] not in used): out[k] = kr
    return out


def norm(rid):
    return (rid or '').replace(' ', '').lower()


def to_game(no, m, t, accounts, ckr):
    """API 경기 → games.json 한 경기 + api_details 한 경기"""
    info = m['info']
    parts = info['participants']
    def nm(p):
        a = accounts.get(p['puuid'])
        if not a:
            # 미리 등록한 새 멤버 (accounts.json 의 "riot:게임명#태그" 항목) → 실제 계정(puuid)으로 옮겨 등록
            rid = f"{p.get('riotIdGameName')}#{p.get('riotIdTagline')}"
            key = next((k for k in accounts if k.startswith('riot:') and norm(k[5:]) == norm(rid)), None)
            if key:
                a = {'name': accounts.pop(key)['name'], 'riotId': rid}
                accounts[p['puuid']] = a
                log(f"  ✓ 새 멤버 계정 연결: {rid} → '{a['name']}'")
                return a['name']
        if not a:
            a = {'name': p.get('riotIdGameName') or p['puuid'][:8], 'riotId': f"{p.get('riotIdGameName')}#{p.get('riotIdTagline')}", 'auto': True}
            accounts[p['puuid']] = a
            log(f"  ⚠ 처음 보는 계정 → '{a['name']}' 으로 임시 등록 ({a['riotId']}) — accounts.json 에서 HUSH 선수명으로 고쳐주세요")
        return a['name']
    names = {p['participantId']: nm(p) for p in parts}
    dur = info['gameDuration']
    teams = {100: [], 200: []}
    for p in parts:
        ch = ckr.get(p['championName'].lower(), p['championName'])
        teams[p['teamId']].append(dict(pos=POS.get(p.get('teamPosition'), 'SUP'), name=names[p['participantId']], champ=ch,
            vd='승' if p['win'] else '패', k=p['kills'], d=p['deaths'], a=p['assists'], vs=p['visionScore'],
            dmg=p['totalDamageDealtToChampions'], dt=p['totalDamageTaken'], gold=p['goldEarned'], cc=p['timeCCingOthers'],
            cs=p['totalMinionsKilled'] + p['neutralMinionsKilled'], piwa=p.get('visionWardsBoughtInGame', 0),
            mit=p.get('damageSelfMitigated', 0)))
    for k in teams: teams[k].sort(key=lambda x: POSO.index(x['pos']))
    # 한국 시간 기준 날짜. 새벽 6시 전에 시작한 판은 전날 내전으로 묶는다 (자정 넘겨 이어진 내전이 다른 날로 갈라지지 않게)
    st = time.gmtime(info['gameStartTimestamp'] / 1000 + 9 * 3600 - 6 * 3600)
    game = dict(no=no, date=time.strftime('%Y.%m.%d', st), mn=dur // 60, sc=dur % 60, bans=[], t1=teams[100], t2=teams[200],
                match=m['metadata']['matchId'], start=info['gameStartTimestamp'])

    # ── 상세(아이템·룬·타임라인) ──
    pid = {p['participantId']: p for p in parts}
    winteam = [p['teamId'] for p in parts if p['win']][0]
    gd, kills, objs, skills, buys, f15 = [], [], [], {}, {}, None
    if t:
        frames = t['info']['frames']
        for f in frames:
            s = {100: 0, 200: 0}
            for k, v in f['participantFrames'].items(): s[pid[int(k)]['teamId']] += v['totalGold']
            gd.append(s[winteam] - s[300 - winteam])
        if len(frames) > 15: f15 = frames[15]['participantFrames']
        for f in frames:
            for e in f['events']:
                ty, ts = e['type'], round(e['timestamp'] / 1000)
                if ty == 'CHAMPION_KILL':
                    vic = e['victimId']
                    kills.append([ts, e['position']['x'], e['position']['y'], names.get(e.get('killerId', 0)), names[vic],
                                  [names[a] for a in e.get('assistingParticipantIds', []) if a in names], 1 if pid[vic]['teamId'] != winteam else 0])
                elif ty == 'ELITE_MONSTER_KILL':
                    code = MON.get(e['monsterType'], 'M'); sub = e.get('monsterSubType', '')
                    if sub == 'ELDER_DRAGON': code = 'E'
                    objs.append([ts, code, sub.replace('_DRAGON', '').lower(), 1 if e.get('killerTeamId') == winteam else 0, names.get(e.get('killerId'))])
                elif ty == 'BUILDING_KILL':
                    objs.append([ts, 'T' if e['buildingType'] == 'TOWER_BUILDING' else 'I', (e.get('laneType', '') or '').replace('_LANE', '').lower(),
                                 1 if e['teamId'] != winteam else 0, names.get(e.get('killerId'))])
                elif ty == 'SKILL_LEVEL_UP' and e.get('levelUpType') == 'NORMAL' and e['participantId'] in names:
                    skills.setdefault(e['participantId'], []).append('QWER'[e['skillSlot'] - 1])
                elif ty == 'ITEM_PURCHASED' and e['participantId'] in names and e['itemId'] not in SKIP_ITEMS:
                    buys.setdefault(e['participantId'], []).append([e['itemId'], ts])
                elif ty == 'ITEM_UNDO' and e['participantId'] in buys and e.get('beforeId'):
                    b = buys[e['participantId']]
                    for i in range(len(b) - 1, -1, -1):
                        if b[i][0] == e['beforeId']: b.pop(i); break
    rows = []
    for p in parts:
        i = p['participantId']; c = p.get('challenges', {}); sty = p['perks']['styles']
        r = dict(n=names[i], ch=p['championName'], lv=p['champLevel'], win=1 if p['win'] else 0, pos=p.get('teamPosition', ''),
                 it=[p['item%d' % k] for k in range(6)], tr=p['item6'], sp=[p['summoner1Id'], p['summoner2Id']],
                 ru=dict(ks=sty[0]['selections'][0]['perk'], p=sty[0]['style'], s=sty[1]['style'],
                         pk=[x['perk'] for x in sty[0]['selections']] + [x['perk'] for x in sty[1]['selections']],
                         st=[p['perks']['statPerks'].get(k) for k in ('offense', 'flex', 'defense')]),
                 mk=[p['doubleKills'], p['tripleKills'], p['quadraKills'], p['pentaKills']], ls=p['largestKillingSpree'],
                 fb=2 if p['firstBloodKill'] else (1 if p['firstBloodAssist'] else 0),
                 ft=2 if p['firstTowerKill'] else (1 if p['firstTowerAssist'] else 0),
                 sk=c.get('soloKills', 0), ssh=c.get('skillshotsHit', 0), ssd=c.get('skillshotsDodged', 0),
                 sav=c.get('saveAllyFromDeath', 0), imm=c.get('enemyChampionImmobilizations', 0),
                 cw=p.get('detectorWardsPlaced', 0), wp=p['wardsPlaced'], wk=p['wardsKilled'],
                 tdd=p['totalTimeSpentDead'], ll=p['longestTimeSpentLiving'], mit=p['damageSelfMitigated'],
                 hs=p['totalHealsOnTeammates'] + p['totalDamageShieldedOnTeammates'],
                 tur=p['damageDealtToTurrets'], obd=p['damageDealtToObjectives'],
                 drg=c.get('dragonTakedowns', 0), bar=c.get('baronTakedowns', 0), her=c.get('riftHeraldTakedowns', 0),
                 stl=p.get('objectivesStolen', 0), pl=c.get('turretPlatesTaken', 0), tk=p.get('turretTakedowns', 0),
                 png={k.replace('Pings', ''): p[k] for k in PING_KEYS if p.get(k)},
                 so=''.join(skills.get(i, [])[:18]), bo=buys.get(i, []))
        r['pngT'] = sum(r['png'].values())
        if f15:
            me = f15[str(i)]
            opp = [q for q in parts if q['teamId'] != p['teamId'] and q.get('teamPosition') == p.get('teamPosition')]
            if opp and p.get('teamPosition'):
                o = f15[str(opp[0]['participantId'])]
                r['gd15'] = me['totalGold'] - o['totalGold']
                r['csd15'] = (me['minionsKilled'] + me['jungleMinionsKilled']) - (o['minionsKilled'] + o['jungleMinionsKilled'])
                r['xpd15'] = me['xp'] - o['xp']
        rows.append(r)
    detail = dict(m=m['metadata']['matchId'], v='.'.join(info['gameVersion'].split('.')[:2]), dur=dur, gd=gd, k=kills, o=objs, p=rows)
    return game, detail


def apply_bans(games, text):
    if not text.strip(): return
    for line in re.split(r'[\n;]+', text):
        mm = re.match(r'\s*#?(\d+)\s*[:：]\s*(.+)', line)
        if not mm: continue
        no, bans = int(mm.group(1)), [b.strip() for b in re.split(r'[,，/]', mm.group(2)) if b.strip()]
        g = [x for x in games if x['no'] == no]
        if g:
            g[0]['bans'] = bans[:10]; log(f"  밴 입력: #{no} {', '.join(bans[:10])}")
        else:
            log(f"  ⚠ 밴 입력 무시: #{no} 경기가 없음")


def main():
    games = load('games.json', [])
    details = load('api_details.json', {})
    accounts = load('accounts.json', {})
    state = load('state.json', {})
    have = {g.get('match') for g in games if g.get('match')}
    exclude = {x.strip() for x in os.environ.get('EXCLUDE', '').replace('\n', ',').split(',') if x.strip()}
    new = []
    if KEY:
        since = int(state.get('lastStart', 0) // 1000) + 1
        log(f"■ 새 경기 찾기 (기준 시각 {time.strftime('%Y-%m-%d %H:%M', time.gmtime(since + 9*3600))} KST 이후 · 계정 {sum(1 for k in accounts if not k.startswith('riot:'))}개)")
        cand = set()
        for pu in [k for k in accounts if not k.startswith('riot:')]:
            ids = get(f'/lol/match/v5/matches/by-puuid/{pu}/ids', {'type': 'tourney', 'startTime': since, 'count': 100}) or []
            cand.update(ids)
        cand = sorted(c for c in cand if c not in have and c not in exclude)
        log(f"  후보 {len(cand)}개")
        for mid in cand:
            m = get(f'/lol/match/v5/matches/{mid}')
            if not m: continue
            info = m['info']
            pend = {norm(k[5:]) for k in accounts if k.startswith('riot:')}
            known = sum(1 for p in info['participants'] if p['puuid'] in accounts or norm(f"{p.get('riotIdGameName')}#{p.get('riotIdTagline')}") in pend)
            if info['gameDuration'] < 300:
                log(f"  - {mid} 제외: {info['gameDuration']}초 (다시하기/로비 테스트)"); continue
            if known < 5:
                log(f"  - {mid} 제외: 등록된 멤버 {known}명뿐 (내전 아님)"); continue
            t = get(f'/lol/match/v5/matches/{mid}/timeline')
            new.append((info['gameStartTimestamp'], mid, m, t))
        new.sort()
        ckr = champ_kr_map(games)
        for ts, mid, m, t in new:
            no = len(games) + 1
            g, d = to_game(no, m, t, accounts, ckr)
            games.append(g); details[str(no)] = d
            state['lastStart'] = max(state.get('lastStart', 0), ts)
            log(f"  + #{no} {g['date']} {g['mn']}:{g['sc']:02d}  {mid}")
        if not new: log('  새 경기 없음')
    else:
        log('■ RIOT_API_KEY 가 없어 경기 조회는 건너뜀')
    apply_bans(games, os.environ.get('BANS', ''))
    save('games.json', games, compact=True)
    save('api_details.json', details, compact=True)
    save('accounts.json', accounts)
    save('state.json', state)
    nb = [g['no'] for g in games[-10:] if not g.get('bans')]
    if nb: log(f"  ℹ 밴이 비어 있는 최근 경기: {', '.join('#%d' % n for n in nb)} — 다음 실행 때 BANS 칸에 입력하세요")
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write('\n'.join('- ' + s if not s.startswith('■') else '### ' + s[2:] for s in SUMMARY) + '\n')


if __name__ == '__main__':
    main()
