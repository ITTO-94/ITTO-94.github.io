# HUSH.GG 자동 업데이트

| 파일 | 하는 일 |
|---|---|
| `.github/workflows/update.yml` | Actions 실행 설정 (버튼 실행 / 예약 실행) |
| `scripts/fetch_matches.py` | 라이엇 API에서 새 내전 경기를 찾아 `data/`에 추가 |
| `scripts/hush_stats.py` | CP v2 · ELO · 선수/챔피언 통계 계산 (엑셀 시절과 같은 공식) |
| `scripts/build_site.py` | 계산 결과로 `index.html`의 데이터 부분만 교체 |
| `data/games.json` | 전체 경기 기록 (1~50경기는 엑셀+API 교정본) |
| `data/api_details.json` | 아이템·룬·타임라인 등 상세 기록 |
| `data/accounts.json` | 라이엇 계정 → HUSH 선수명 |
| `data/state.json` | 마지막으로 가져온 경기 시각 |
| `data/elo_frozen50.json` | 50경기까지 ELO 고정값 |

- 새 멤버 계정은 처음 경기에서 소환사명으로 자동 등록되고 `"auto": true` 표시가 붙습니다. `accounts.json`에서 `name`을 HUSH 선수명으로 고친 뒤 Actions를 한 번 더 실행하면 반영됩니다.
- 밴은 실행할 때 입력칸에 `51: 아리, 리 신, 오공; 52: 자야, 렐` 형식으로 넣습니다.
- 선수 리포트 · Just Joke · 오늘의 경기 시딩은 자동으로 바뀌지 않습니다.
