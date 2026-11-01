# 2026-09-10 아침 루틴 미실행 — 셸(리눅스 워크스페이스) 마운트 실패

## 결론
**오늘(2026-09-10, 목) 아침 루틴은 한 단계도 실행되지 못했다.** 데이터·트래커·상태 파일은
**전혀 건드리지 않았다**(오염 없음). `morning_state_20260910.json` 은 생성되지 않았다.
마지막 정상 실행은 `morning_state_20260909.json`.

## 원인
스케줄 태스크 세션의 셸 도구(`mcp__workspace__bash`)가 워크스페이스 부팅 단계에서
**5회 연속 동일 오류로 실패**했다. 재시도로 해결되지 않는 인프라 결함이다.

```
resume: RPC error -1: failed to mount .../uploads (및 .../memory)
        source path is under Plan9 share "c" which is not mounted
create: RPC error -1: ensure user: user <session> already exists unexpectedly: uid=2047 gid=2047
```

즉 **사용자 PC의 C: 드라이브 공유가 VM에 마운트되지 않은 상태**에서 워크스페이스가
resume/create 양쪽 다 실패했다. `loop`·`fable` 폴더의 파일 읽기(파일 도구)는 정상이었으나
**Python·Node 실행 경로가 전무**했다.

## 실행하지 못한 단계
| 단계 | 명령 | 상태 |
|---|---|---|
| 1 | `python3 references/scripts/morning_run.py` | 미실행 (0-A~0-G, 1~2단계 전부) |
| 3~5 | 개선 루프 · `loop-goal-verifier` | 미실행 (채점 자체가 없어 판정 대상 없음) |
| 6 | `루프엔지니어링_2026-09-10.docx` | 미생성 |
| 6 | `데일리브리핑_2026-09-10.pdf` | 미생성 |
| 7 | `python3 references/scripts/send_daily_mail.py` | 미실행 |

## 이 결손이 표본에 미치는 영향
- **트랙 A·B·C, Rule CB, Rule LV OOS, Rule EG(트랙 D) 트래커에 2026-09-10 행이 없다.**
  0-A/0-E/0-F/0-G 는 밀린 날짜를 회수하는 경로가 있으므로(`--catchup`, `--all`,
  `close_bet_record.py --all`, `lv_oos.py`) **다음 실행에서 자동 회수된다.**
- **0-B 오늘(T) 관심신호 수집은 회수 불가**다. 장전 윈도(09:00 이전)를 놓쳤으므로
  2026-09-10 신호는 사후수집(post_hoc) 표기 대상이거나 결손으로 남는다.
  → CLAUDE.md §2 "0-B 실패 시 대체 소스로 채우지 않는다" 원칙 적용. 결손으로 기록.
- **오늘자 추천은 존재하지 않으므로 내일 채점 대상(신규 브리핑)도 없다.**
  다음 실행에서 `scoring.new_target == false` 가 뜨면 정상이며,
  **iteration 미증가 · N 대장 무변동**으로 처리한다(없는 실패에 가설을 만들지 않는다).

## 다음 실행에서 할 일
1. 셸이 살아 있는지 먼저 확인한다(`echo ok`). 죽어 있으면 세션을 재시작한다.
2. `python3 references/scripts/morning_run.py` 를 평소대로 실행한다.
   러너의 밀린-날짜 회수 경로가 09-10 공백을 메운다.
3. 무결성 검사에서 09-10 결손 경고가 뜨면 **데이터 손상이 아니라 미실행**임을 확인하고
   `repair_data.py --fix` 로 억지로 채우지 않는다.
4. 다음 보고서 (A) 채점 섹션과 9절(데이터 검증 결과)에
   **"2026-09-10 결손 — 셸 마운트 실패로 루틴 미실행, 0-B 회수 불가"** 를 명시한다.

## 하지 않은 것 (의도적)
- 손으로 선정을 재계산하지 않았다(CLAUDE.md §2 — 보고서·브리핑 간 수치 불일치의 원인).
- `loop-log.md`·`analysis-method.md`·`current-holdings.md`·트래커 CSV 를 수정하지 않았다
  (§8-4 — 절차가 규정한 항목만 갱신. 미실행은 갱신 사유가 아니다).
- 반쪽 산출물(.docx/.pdf)을 만들지 않았고 메일도 보내지 않았다(§7 — 2종 모두 없으면 미발송).

---

## 추가 기록 — 2026-09-10 06:40 KST 수동 재시도도 실패

사용자가 데스크톱 세션에서 "아침 루틴 실행"을 직접 호출했으나 **동일 원인으로 다시 실패**했다.
자동 스케줄 실행(06:21)에 이은 2차 실패이며, 약 20분 간격으로도 자연 복구되지 않았다.

- `device_bash` 3회 연속 동일 오류:
  `sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared`
  (`mnt/loop`, `mnt/fable` 둘 다 마운트 실패)
- 파일 도구(`device_list_dir` · `device_stage_files` · `device_commit_files`)는 **정상**.
  즉 읽기·쓰기는 되지만 **Python·Node 실행 경로가 없다**(1차 실패와 동일한 양상).

### 컴퓨터 사용(GUI)으로 우회 시도 → 불가
`computer_resolve_access` 로 Windows PowerShell 접근을 확인한 결과,
**터미널·IDE 계열은 'click' 등급으로만 허용**된다 — 보고 클릭할 수는 있으나
**타이핑·키 입력·붙여넣기가 금지**된다. 따라서 GUI 터미널로 `morning_run.py` 를
실행하는 경로는 존재하지 않는다. 스크립트 파일을 만들어 더블클릭으로 실행시키는
방식은 이 제한을 우회하는 것이므로 **의도적으로 시도하지 않았다**.

### 데이터 상태 (1차 기록과 동일 — 변경 없음)
본 재시도에서도 데이터·트래커·상태 파일은 **전혀 건드리지 않았다**.
`morning_state_20260910.json` 미생성. 마지막 정상 실행은 여전히 `morning_state_20260909.json`.

### 0-B 윈도
06:40 시점 기준 장전 윈도(09:00)까지 여유가 있었다.
**세션을 재시작해 셸이 살아나면 09:00 이전에 `morning_run.py` 를 돌려 0-B 를 살릴 수 있다.**
09:00 을 넘기면 1차 기록대로 2026-09-10 0-B 는 결손 처리한다.

### 사용자에게 안내한 복구 절차
1. Claude 데스크톱 앱에서 이 작업을 **새 세션으로 다시 시작**(또는 "이 컴퓨터에 연결" 재실행).
   워크스페이스 VM 이 C: 공유를 다시 마운트하면 셸이 살아난다.
2. 새 세션에서 `echo ok` 로 셸 생존을 먼저 확인한 뒤 평소대로 "아침 루틴 실행".
3. 러너의 밀린-날짜 회수 경로(`--catchup` 등)가 09-10 공백을 메운다.
   `repair_data.py --fix` 로 억지로 채우지 않는다.

---

## 추가 기록 — 2026-09-10 06:42 KST 3차 시도도 실패

같은 데스크톱 세션에서 사용자가 다시 "아침 루틴 실행"을 호출했다. **동일 원인으로 3차 실패.**
06:21(자동) → 06:40(수동) → 06:42(수동)로 약 21분에 걸쳐 세 번 모두 같은 오류이며,
**자연 복구되지 않는다**는 것이 확인됐다.

- `device_bash` 3회 호출 전부:
  `sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared`
- `get_device_info` 정상 (`connectedFolders: C:\agent\Claude\loop`, appVersion 1.49585.0).
  `device_list_dir` · `device_stage_files` 정상. **읽기·쓰기만 되고 실행 경로가 없다.**
- 이 세션은 1차·2차와 **다른 세션**이다. 즉 "세션 재시작"만으로는 복구되지 않았다.
  워크스페이스 VM 의 C: 공유 마운트 자체가 계정 단위로 죽어 있는 것으로 보인다.

### 검토했으나 하지 않은 우회 (의도적)
- **클라우드 컨테이너에서 `morning_run.py` 대행 실행** — 기각.
  패널·트래커 수십 개 파일을 올렸다 내리는 과정에서 §6 안전교체(`safe_io`)·무결성 검사가
  사용자 PC 사본 기준으로 성립하지 않고, 표본 이력 오염 위험이 실행 이득보다 크다.
  자격증명 파일을 컨테이너로 올리는 것도 금지 사항이다.
- **손 계산 선정** — §2 금지(보고서·브리핑 수치 불일치의 원인).

### 데이터 상태 (변경 없음)
데이터·트래커·상태 파일 **미변경**. `morning_state_20260910.json` 여전히 미생성.
마지막 정상 실행 `morning_state_20260909.json`.
본 파일(`_INCIDENT_...md`) 외에는 어떤 파일도 쓰지 않았다.

### 0-B 윈도
06:42 기준 09:00 까지 약 2시간 18분 남음. 마운트가 살아나면 그 전에 실행해 0-B 를 살릴 수 있다.

---

## 추가 기록 — 2026-09-10 22:38 KST 4차 확인 (원격 세션)

사용자가 "계속 에러가 난다"며 문의. 이 세션(클라우드 원격 세션, device "jang" 연결)에서
`loop`·`fable` 폴더 접근 권한을 다시 받아 확인한 결과 **동일 오류가 그대로 재현**됐다.

- `device_bash` 로 `ls`, `echo ok` 등 **어떤 명령도 실행 불가**:
  `sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared`
  → 마운트 실패가 아니라 **셸 자체가 기동하지 않는다**(명령 종류 무관).
- `get_device_info` 정상 (appVersion 1.49585.0, platform win32).
  `device_request_folder_access` · `device_list_dir` · `device_stage_files` 모두 정상.
- 06:21 → 06:40 → 06:42 → 22:38, **약 16시간에 걸쳐 4회 모두 동일 오류**.
  세션을 바꿔도, 시간이 지나도 자연 복구되지 않는다.

### 판정
Claude 데스크톱 앱의 Cowork 워크스페이스 VM(WSL2 기반)이 **호스트 C: 드라이브 공유를
잃은 상태로 고착**됐다. 앱 재시작·세션 재시작 수준으로는 복구되지 않았으므로
**WSL 서브시스템 자체를 내렸다 올리거나 PC를 재부팅**해야 한다.

### 0-B 윈도
22:38 기준 **2026-09-10 장전 윈도(09:00) 완전 종료**. 1차 기록대로
**2026-09-10 0-B 는 결손 확정**. 나머지 트래커(0-A/0-E/0-F/0-G)는 다음 실행의
밀린-날짜 회수 경로로 자동 복구된다.

### 다음 실행 시 유의
- 다음 정상 실행에서 `scoring.new_target == false` 가 뜨는 것은 정상이다
  (09-10 추천이 없으므로 채점 대상이 없다). iteration 미증가·N 대장 무변동으로 처리.
- 보고서 (A) 채점 섹션·9절에 **"2026-09-10 결손 — 셸 마운트 실패로 루틴 미실행,
  0-B 회수 불가"** 를 명시한다. `repair_data.py --fix` 로 채우지 않는다.

---

## 추가 기록 — 2026-09-10 23:0x KST 5차 확인 (원격 세션, 폴더 재승인 후)

사용자가 "모닝 루틴 에러, 해결해달라"고 재요청. `C:\agent\Claude` 상위 폴더로
접근 권한을 새로 받아(`granted: C:\agent\Claude`) 다시 확인했으나 **결과 동일**.

- `device_bash`: `ls $HOME/mnt/` · `echo` 모두 실패 —
  `sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared`
  부가 안내: `mnt/Claude failed to mount and cannot be reached from this shell`.
- 파일 도구(`device_list_dir`·`device_stage_files`·`device_commit_files`) 정상.
- 06:21 → 06:40 → 06:42 → 22:38 → 23:0x, **5회 연속 동일**.
  상위 폴더로 권한을 새로 부여해도 마운트가 살아나지 않는다
  → 폴더 권한 문제가 아니라 **VM의 드라이브 공유 계층 고장**임이 재확인됐다.

### GUI 우회 재확인 → 여전히 불가
`computer_resolve_access("터미널")` 결과 `tier: "click"`, `isSentinel: true`.
`restrictedTierNote`: 터미널·IDE는 click 등급으로만 부여 가능하며 **타이핑·키입력·붙여넣기 금지**.
따라서 원격에서 `wsl --shutdown` 을 대신 실행할 경로는 없다. **사용자 조작이 필요하다.**

### 복구 절차 (사용자 실행, 1~2분)
1. Claude 데스크톱 앱 **완전 종료**(트레이 아이콘까지).
2. Windows PowerShell 또는 명령 프롬프트에서:
   ```
   wsl --shutdown
   ```
   (선택) `wsl --status` 로 내려간 것 확인. 그래도 안 되면 **PC 재부팅**.
3. Claude 데스크톱 앱 재실행 → 작업에서 `C:\agent\Claude` 폴더 연결 확인.
4. 새 세션에서 `echo ok` 로 셸 생존 확인 후 "아침 루틴 실행".

### 데이터 상태 (변경 없음)
이 세션에서도 데이터·트래커·상태 파일은 **읽기만** 했고 수정하지 않았다.
`morning_state_20260910.json` 미생성. 마지막 정상 실행 `morning_state_20260909.json`.
2026-09-10 0-B 는 **결손 확정**(장전 윈도 종료).

---

## 해결 — 2026-09-10 23:2x KST 셸 복구 확인 및 회수 실행 완료

### 셸 상태
`wsl --shutdown` 계열 복구 이후 **마운트가 정상화됐다.**
`echo ok` 정상 · `python3 3.10.12` · `node v22.23.2` · `mnt/loop`·`mnt/fable` 모두 접근 가능.
5회 연속 실패의 원인이던 `no Plan9 drive shares mounted` 오류는 재현되지 않는다.

### 새로 확인된 제약 — 클라우드 세션 경로의 45초 상한
이 세션은 데스크톱 워크스페이스 셸이 아니라 **원격 브리지의 `device_bash`** 로 PC 셸을 부른다.
이 경로는 **호출당 45초 하드 상한**이며, **백그라운드 프로세스가 호출 종료와 함께 죽는다**
(`bwrap --die-with-parent`, `setsid`·`nohup`·`disown` 모두 무효 — 실측).
따라서 `morning_run.py` 를 **한 번의 호출로 끝까지 돌릴 수 없다**
(중기모멘텀 `--update` 한 단계만 예산 240초, 최초 실행은 40초에서 rc=124 로 잘림).

**우회 절차(이번에 쓴 방법, 재사용 가능):** 러너가 부르는 하위 스크립트는 전부 멱등이므로
**무거운 단계를 먼저 개별로 돌려 캐시를 채운 뒤 러너를 한 번 통과**시킨다.
1. `ensure_data.ensure(T, 33)` 반복 → done=True (코스피·패널 회수)
2. `extend_panel.py --base <최신 panel_close> --dates <일자> --budget 36` 반복 → rc=0 후 ensure 가 finalize
3. `rebuild_ohlc_panel.py 25~36` 반복 → `panel_ohlc_2y.csv` 최신화(rc=0 까지)
4. `mid_momentum_shadow.py --update/--record/--score/--report`, `tv_shadow.py`,
   `regime_shadow.py`, `eg_picks.py --record`, `news_top5.py` 개별 예열
5. `python3 references/scripts/morning_run.py` 1회 → 40초 내 완주

또한 샌드박스가 세션마다 초기화돼 **yfinance 미설치**로 코스피 보충이 막혔다.
`ensure_data` 의 자동 설치(180초 타임아웃)가 이 경로에서는 실패하므로
`python3 -m pip install -q yfinance --break-system-packages` 를 먼저 수동 실행했다.

### 회수 실행 결과 (rc=0)
- `morning_state_20260910.json` **생성됨**. `integrity.post.rc = 1`(오류 0 · 경고 1).
  남은 경고는 "패널 최종일(20260910)이 오늘 이상" 하나뿐이며, 장 마감 후(23시대) 실행이라 정상이다.
- `scoring.new_target = false` — "20260909 은 이미 채점 완료 — 신규 대상 없음".
  1차 기록의 예상대로이며 **경량 모드(개선 루프 이월) · iteration 미증가 · N 대장 무변동**으로 처리한다.
- 패널 회수: `panel_close_0910.csv` 25,877행 · 201종 · 최종 20260910.
  `panel_ohlc_2y.csv` 98,696행 · 201종 · 20240325~20260910. 코스피 종가 09-09·09-10 보충.
- 트래커 회수: Rule CB `close_bet_band_tracker.csv` 에 2026-09-08 행 1건 기록
  (stage2 매수2종 +2.56% · 코스피 +1.40% · 초과 +1.16%p).
  `mid_momentum_shadow.csv`·`eg_track_tracker.csv` 20260910 행 기록.
  LV OOS 누적 13일(20260821~20260908) 정상 산출.
- `repair_data.py --fix` 로 억지로 채우지 않았다. 1차 실행에서 뜬 rc=2 는
  **오염이 아니라 `panel_ohlc_2y.csv` 미갱신**이었고, `rebuild_ohlc_panel.py` 로 정규 갱신했다.

### ⚠ 0-B 시점 이탈 — 보고서에 반드시 명시할 것
러너가 `attention.B_ok = true` 로 기록했으나, 이 수집은 **장전 윈도(09:00 이전)가 아니라
당일 23시대에 이뤄졌다.** 즉 `raw_20260910.csv` 는 존재하지만 **정규 0-B 표본이 아니다.**
1차 기록의 "0-B 결손 확정" 판단은 유효하며, 이 행을 정상 표본으로 취급해서는 안 된다.
→ 다음 보고서 (A) 채점 섹션·9절에 **"2026-09-10 0-B 사후수집(23시대) — 장전 윈도 이탈,
정규 표본 아님"** 을 명시한다. 이 행을 근거로 한 방법 개선은 하지 않는다.

### 하지 않은 것
- `루프엔지니어링_2026-09-10.docx`·`데일리브리핑_2026-09-10.pdf` 미생성, 메일 미발송.
  사용자가 요청한 것은 **밀린 날짜 회수**까지이며, 장 마감 후 시점에 당일 브리핑을 만드는 것은
  용도에 맞지 않는다. 산출물이 필요하면 별도로 지시받아 생성한다.
