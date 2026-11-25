# -*- coding: utf-8 -*-
"""HUSH.GG — data/ 로 통계를 다시 계산해 index.html 데이터 부분만 교체 (GitHub Actions용)
 - 선수 리포트 · Just Joke · 디자인 · 기능 코드는 건드리지 않음
 - 새 경기가 생겼을 때만 '지난 업데이트' 기준값(ELO 변동 · 티어리스트 순위 변동 · NEW 표시)을 갱신
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
DATA = os.path.join(ROOT, 'data')
INDEX = os.path.join(ROOT, 'index.html')


def blob(s, name):
    m = re.search(r'(?:const|var|let) ' + name + r'\s*=\s*', s)
    if not m: raise SystemExit(f'index.html 에서 {name} 를 찾지 못했습니다')
    obj, end = json.JSONDecoder().raw_decode(s[m.end():])
    return obj, m.end(), m.end() + end


def put(s, name, value):
    _, a, b = blob(s, name)
    return s[:a] + json.dumps(value, ensure_ascii=False, separators=(',', ':')) + s[b:]


def lane_ranks(games, details):
    """티어리스트 라인별 순위 (사이트 renderChampion 의 laneRanks 와 같은 계산)"""
    total = len(games); agg = {}
    for g in details:
        for r in g['players']:
            k = r['champ'] + '|' + r['pos']
            a = agg.setdefault(k, dict(champ=r['champ'], pos=r['pos'], games=0, wins=0))
            a['games'] += 1; a['wins'] += 1 if r['team'] == 'win' else 0
    def ban_rate(c):
        b = sum(1 for g in games if g.get('bans') and c in g['bans'])
        return round(b / total * 10000) / 100 if total else 0
    # 성과 점수: 그 챔피언으로 낸 평균 CP가 포지션 평균 대비 얼마나 높은지 (판수 적으면 50으로 수렴)
    cs, ps = {}, {}
    for g in details:
        for r in g['players']:
            k = r['champ'] + '|' + r['pos']
            c = cs.setdefault(k, [0, 0]); c[0] += r['cp']; c[1] += 1
            q = ps.setdefault(r['pos'], [0, 0]); q[0] += r['cp']; q[1] += 1
    def perf(champ, pos):
        c, q = cs.get(champ + '|' + pos), ps.get(pos)
        if not c or not q or not q[1]: return 50
        pa = q[0] / q[1]; raw = max(0, min(100, 50 + (c[0] / c[1] - pa) / pa * 100))
        return 50 + (raw - 50) * c[1] / (c[1] + 3)
    rows = []
    for a in agg.values():
        bg = round(ban_rate(a['champ']) * total / 100)
        shrunk = (a['wins'] + 3 * 0.5) / (a['games'] + 3) * 100
        presence = min(100, (a['games'] + bg) / total * 100 * 1.5)
        rows.append(dict(a, score=shrunk * 0.55 + presence * 0.3 + perf(a['champ'], a['pos']) * 0.15))
    out = {}
    for pos in ['TOP', 'JUG', 'MID', 'ADC', 'SUP']:
        pool = sorted([r for r in rows if r['pos'] == pos and r['games'] >= 2], key=lambda r: -r['score'])
        for i, r in enumerate(pool): out[r['champ'] + '|' + pos] = i + 1
    return out


def main():
    s = open(INDEX, encoding='utf-8').read()
    old_games, _, _ = blob(s, 'GAMES')
    old_details, _, _ = blob(s, 'GAME_DETAILS')
    old_players, _, _ = blob(s, 'PLAYERS')

    out = os.path.join(DATA, '_build.json')
    subprocess.run([sys.executable, os.path.join(HERE, 'hush_stats.py'), out], check=True)
    b = json.load(open(out, encoding='utf-8')); os.remove(out)
    details = json.load(open(os.path.join(DATA, 'api_details.json'), encoding='utf-8'))
    games_src = json.load(open(os.path.join(DATA, 'games.json'), encoding='utf-8'))

    if len(b['GAMES']) > len(old_games):
        print(f'새 경기 {len(b["GAMES"]) - len(old_games)}판 → 지난 업데이트 기준값 갱신')
        s = put(s, 'ELO_PREV', {n: p['elo'] for n, p in old_players.items()})
        s = put(s, 'CHAMP_PREV', lane_ranks(old_games, old_details))
        s = re.sub(r'var PREV_GAMES = \d+;', f'var PREV_GAMES = {len(old_games)};', s)
        # 오늘의 경기: 마지막 경기 날짜가 더 최근이면 그날 마지막 경기 로스터로 교체 (시딩 점수 없음 → ELO 기준 표시)
        last = games_src[-1]
        md, a0, a1 = None, None, None
        mm = re.search(r"var MATCHDAY = \{\s*date: '([\d.]+)'", s)
        if mm and last['date'] > mm.group(1):
            i = s.index('var MATCHDAY = {'); j = s.index('};', i) + 2
            side = lambda t: ', '.join(f"{p['pos']}:{{n:'{p['name']}'}}" for p in t)
            s = s[:i] + ("var MATCHDAY = {\n  date: '%s',\n  teams: {\n    a: {%s},\n    b: {%s}\n  },\n  power: null\n};"
                         % (last['date'], side(last['t1']), side(last['t2']))) + s[j:]
            print('오늘의 경기 →', last['date'])
    for k in ['PLAYERS', 'GAMES', 'GAME_DETAILS', 'MATCHUPS', 'CHAMP_STATS', 'ELO_HISTORY']:
        s = put(s, k, b[k])
    s = put(s, 'API_DETAILS', details)
    open(INDEX, 'w', encoding='utf-8').write(s)
    print(f"완료: {len(b['GAMES'])}경기 · {len(b['PLAYERS'])}명 · 상세 {len(details)}경기")


if __name__ == '__main__':
    main()
