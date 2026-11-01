# 2026-09-30 아침 루틴 미실행 — 셸(리눅스 워크스페이스) 마운트 실패 재발

## 결론
**오늘(2026-09-30, 수) 아침 루틴은 한 단계도 실행되지 못했다** (자동 스케줄 실행, 06:16 KST 경).
데이터·트래커·상태 파일은 **전혀 건드리지 않았다**(오염 없음).
`morning_state_20260930.json` 미생성. 마지막 정상 실행은 `morning_state_20260929.json` (09-29 06:40 KST).

## 원인
`device_bash` 가 2회 연속 동일 오류로 실패 — 2026-09-10 사고와 같은 양상:
```
sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared
[Note: mnt/loop, mnt/fable failed to mount and cannot be reached from this shell.]
A Windows update released September 8 prevents Claude's workspace from reaching your files.
Install the latest Windows update and restart your computer.
```
파일 도구(`device_list_dir`·`device_stage_files`·`device_commit_files`)는 정상 → 읽기·쓰기만 되고
**Python·Node 실행 경로가 없다.**

## 실행하지 못한 단계
| 단계 | 상태 |
|---|---|
| 1 `morning_run.py` (0-A~0-D, 1~2단계) | 미실행 |
| 3~5 개선 루프 | 미실행 (판정 대상 없음) |
| 4 `루프엔지니어링_2026-09-30.docx` | 미생성 |
| 5 `데일리브리핑_2026-09-30.pdf` | 미생성 |
| 6 `send_daily_mail.py` | 미실행 |
| 8 `mark_done.py` | 미실행 (완료 표식 없음 — 의도적) |

## 하지 않은 것 (의도적, 09-10 선례 동일)
- 클라우드 컨테이너 대행 실행: 기각 (safe_io·무결성 검사 불성립, 자격증명 업로드 금지, 표본 오염 위험).
- 손 계산 선정: CLAUDE.md §2 금지.
- 반쪽 산출물·메일 발송 없음. 트래커/로그 미수정.

## 복구 절차 (사용자 조작 필요)
1. 오류 문구대로 **최신 Windows 업데이트 설치 후 PC 재시작**.
   (09-10 에는 Claude 앱 완전 종료 → `wsl --shutdown` → 앱 재실행으로 복구됨. 재발 시 업데이트가 근본 해결.)
2. 새 세션에서 `echo ok` 로 셸 생존 확인 후 "아침 루틴 실행".
3. 09:00 이전에 재실행하면 0-B(오늘 관심신호) 를 살릴 수 있다. 넘기면 09-30 0-B 는 결손 처리.
4. 0-A/0-E/0-F/0-G 밀린 날짜는 러너 회수 경로가 자동 복구. `repair_data.py --fix` 로 억지로 채우지 않는다.
5. 다음 보고서 (A) 채점·9절에 "2026-09-30 결손 — 셸 마운트 실패로 루틴 미실행" 명시.

---

## 해결 — 2026-09-30 19:4x KST (원격 세션)

### 1차 원인(마운트) — 해소됨
앱이 2.16120.0 으로 올라간 뒤 `device_bash` 정상(`echo ok`, `mnt/loop`·`mnt/fable` 접근 가능).

### 2차 원인(새로 발견) — 셸 VM 디스크 100%
`/sessions`(9.8G) 가 **Avail 0**. 1,498개 세션 디렉터리 중 타 세션 잔재가 9.3G 를 차지(우리 세션은 280K, 삭제 권한 없음).
`$TMPDIR=$HOME/tmp`·`~/.local`·`~/.cache`·`~/.config` 가 전부 이 디스크라 **마운트가 살아나도 루틴이 깨진다**:
- `pip install yfinance` → `OSError [Errno 28] No space left on device` → 코스피 보충 불가
- `soffice` PDF 변환 → `Unspecified Application Error`(프로필·dconf 생성 실패)
`/tmp` 는 루트 디스크(3.7G 여유)라 쓸 수 있다.

### 조치
1. `references/scripts/ensure_data.py` — `$TMPDIR` 쓰기 불가 시 `/tmp` 로, yfinance 설치 실패 시 `/tmp/pylib` `--target` 설치 + `PYTHONPATH` 등록(백업 `_bak_ensure_data_20260930.py`).
2. `fable/gen_appendix.py` — soffice 호출에 `HOME=/tmp/lohome TMPDIR=/tmp` (백업 `_bak_gen_appendix_20260930.py`).
3. `CLAUDE.md` §10 에 과제 행 추가(백업 `CLAUDE_bak_20260930.md`).

### 회수 실행 결과
- `ensure_data`: 코스피 20260929·20260930 보충, `panel_close_0930.csv` 28,289행·201종.
- `backtest/rebuild_ohlc_panel.py 32` ×3 → `panel_ohlc_2y.csv` 99,548행·201종·~20260930. (4회차가 새 사이클을 시작해 `_ohlc_rebuild_part.csv` 를 헤더만 남겨 리셋)
- `morning_run.py --skip-collect` **rc=0**, 20260929 채점 완료, `morning_state_20260930.json` 생성.
  사후 무결성 오류 1건(picks5 가 current-holdings.md 에 없음)은 브리핑 미작성 상태라 정상.
- **0-B(09-30)는 수집하지 않았다(--skip-collect) → 결손 확정.** 장 마감 후 사후수집으로 표본을 오염시키지 않기 위함. 0-C 뉴스 5선도 그래서 미생성.
- kospi_close.csv 는 0930 행이 0929 앞에 붙었다(09-10 회수와 같은 현상, 날짜 키로 읽으므로 무해).

### 하지 않은 것
09-30 브리핑·루프 보고서·메일 — 장 마감 후라 당일 브리핑 용도가 없다(09-10 선례). 10-01 05:30 루틴이 정상 경로로 만든다.
