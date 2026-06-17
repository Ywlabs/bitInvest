# bitInvest Phase 1 — 구현 및 운영 가이드

> 장기 설계 아이디어: [`개발설계아이디어.md`](개발설계아이디어.md)  
> 프로젝트 진입점: [`README.md`](../README.md)

---

## 1. 현재 단계 (Phase 2-Pro)

| 항목 | 상태 |
|------|------|
| Analysis / Trading / Report Worker | ✅ 구현·운영 |
| SQLite 신호 큐 (`trading_signals`) | ✅ |
| 종합 점수 v2 (팩터 합성, 최대 24점) | ✅ `core/strategy/scoring.py` |
| TA 엔진 v2 (`tools/indicators/`) | ✅ |
| 월 잔여 페이싱 + 등급별 배율 | ✅ `ADD_BUY_REMAINING_PCT`, tier multipliers |
| 실주문 API (시장가 매수) | ✅ `UpbitClient.buy_market_krw` (`DRY_RUN` 기본) |
| 배치 실행 이력 (`job_runs`) | ✅ `services/job_log_store.py` |
| **일일 Summary 리포트 (HTML)** | ✅ `services/daily_summary.py` + `report_html.py` |
| **Windows 토스트 알림** | ✅ `services/desktop_notify.py` (배치별 ON/OFF) |
| Windows 작업 스케줄러 등록 | ✅ `scripts/batch/register_tasks.ps1` |
| LangGraph 멀티 에이전트 | 미구현 (Phase 3+) |
| ATR 동적 SL/TP / Kill-switch | 미구현 |
| GitHub Actions 자동화 | **보류** (업비트 IP 화이트리스트) |

업비트 **DCA(4만원 / 4시간)** 는 업비트 앱 설정으로 유지. 본 Agent는 **조건 충족 시 ADD_BUY** 만 판단. **매도 없음.**

> **Trading 배치 주기는 4시간이 아님** — DCA가 4시간이고, Agent Trading은 **15분마다** `pending` 신호 확인.

---

## 2. 아키텍처

```
AnalysisWorker  →  trading_signals (pending)  →  TradingWorker  →  trade_decisions
       ↓                                                    ↓
  market.db (스냅샷·지표)                          monthly_add_buy_ledger
       ↓
 ReportWorker  →  reports/report_YYYY-MM-DD.html  (+ daily_reports JSON)
```

### Worker 역할

| Worker | 스크립트 | 역할 |
|--------|----------|------|
| **Analysis** | `scripts/run_analysis_watch.py` | 시세·지표 수집, 종합 점수, ADD_BUY 신호 생성 |
| **Trading** | `scripts/run_trading_consumer.py` | `pending` 신호 1건 소비 → 예산·점수 검증 → 매수 판단 |
| **Report** | `scripts/run_report.py` | **일자별 Summary 집계** + 마감 시점 대시보드 HTML |

각 스크립트는 **1회 실행 후 종료**. 주기 실행은 **작업 스케줄러**가 담당.

### Report 구성 (2층)

| 층 | 내용 |
|----|------|
| **일일 Summary** | 해당 날짜 DB 집계 — 배치 횟수, BTC 시고·종가, 신호·매매 목록, 타임라인 |
| **마감 시점 현황** | 리포트 생성 시점 재계산 점수 + 최신 `trade_decisions` 기준 상세 (실행 가능 여부, 판단 근거) |

구현: `services/daily_summary.py` (집계), `services/report_html.py` (렌더), `core/strategy/report_narrative.py` (서술)

### 파이프라인 통합 실행

| 명령 | 동작 |
|------|------|
| `python scripts/run_pipeline.py` | Analysis → (기본) Trading 강제 시도 → Report |
| `python scripts/run_pipeline.py --event-only` | 신호 있을 때만 Trading (운영 권장) |
| `python scripts/run_pipeline.py --force` | 신호 없어도 Trading 강제 |

---

## 3. 종합 점수 및 매수 판단 기준

구현: `core/strategy/scoring.py`, `core/triggers/engine.py`, `core/workers/trading_worker.py`

> 상세 팩터 표·등급 배율: [`README.md`](../README.md) 「종합 점수 (Phase 2-Pro)」 참고.

### 3.1 신호 생성 조건 (Analysis)

1. 보류 사유 없음
2. 종합 점수 ≥ `ADD_BUY_MIN_SCORE` (기본 5.0) + ATR 레짐 가산
3. 권장 금액 > 0
4. 동일 `ADD_BUY` pending 신호 없음
5. `SIGNAL_COOLDOWN_HOURS`(기본 8시간) 내 최근 신호 없음

### 3.2 최종 매수 판단 (Trading)

| 검사 | 내용 |
|------|------|
| 신호 타입 | `ADD_BUY` 또는 `MANUAL` |
| 점수/보류 | 차단 없음, 최소 점수 이상 |
| 월 예산 | `MONTHLY_ADD_BUY_BUDGET_KRW` 잔여 |
| 1회 금액 | `월 잔여 × ADD_BUY_REMAINING_PCT × 등급배율 × ATR배율`, 상한 `ADD_BUY_MAX_PER_ORDER_KRW` |
| 가용 원화 | `krw_balance` 충분 |
| 실행 | `DRY_RUN=false` 시 `buy_market_krw()` 시장가 매수 |

---

## 4. Windows 자동 실행 (배치 + 스케줄러)

### 4.1 배치 파일

경로: `scripts/batch/`

| 파일 | 실행 내용 |
|------|-----------|
| `run_analysis.bat` | AnalysisWorker 1회 |
| `run_trading.bat` | TradingWorker 1회 |
| `run_report.bat` | ReportWorker 1회 |
| `run_pipeline.bat` | 통합 파이프라인 (`--event-only`) |
| `register_tasks.ps1` | 작업 스케줄러 3건 일괄 등록 (VBS 숨김 실행) |
| `launch_worker.vbs` | 콘솔 창 없이 Worker 1회 실행 |

배치·매매 이력: `data/market.db` (`job_runs` 테이블). CLI: `python scripts/show_job_log.py`

### 4.2 권장 스케줄

| 작업 이름 | 배치 | 주기 |
|-----------|------|------|
| `bitInvest-Analysis` | `run_analysis.bat` | 1시간마다 |
| `bitInvest-Trading` | `run_trading.bat` | 15분마다 |
| `bitInvest-Report` | `run_report.bat` | 매일 23:00 |

### 4.3 스케줄러 등록 (권장)

```powershell
.\scripts\batch\register_tasks.ps1
```

`register_tasks.ps1`은 `wscript.exe //B launch_worker.vbs`로 등록해 **cmd 창이 뜨지 않음**.

수동 등록 예시 (`.bat` 직접 연결 시 창이 잠깐 보일 수 있음):

```powershell
schtasks /create /tn "bitInvest-Analysis" /tr "D:\Develop\workspace-bitcoin\scripts\batch\run_analysis.bat" /sc hourly /mo 1 /f
schtasks /create /tn "bitInvest-Trading" /tr "D:\Develop\workspace-bitcoin\scripts\batch\run_trading.bat" /sc minute /mo 15 /f
schtasks /create /tn "bitInvest-Report" /tr "D:\Develop\workspace-bitcoin\scripts\batch\run_report.bat" /sc daily /st 23:00 /f
```

확인:

```powershell
schtasks /query /fo TABLE | findstr bitInvest
```

수동 실행:

```powershell
schtasks /run /tn "bitInvest-Analysis"
```

삭제:

```powershell
schtasks /delete /tn "bitInvest-Analysis" /f
schtasks /delete /tn "bitInvest-Trading" /f
schtasks /delete /tn "bitInvest-Report" /f
```

### 4.4 운영 전제

- **PC가 켜져 있어야** 스케줄이 동작함 (절전/종료 시 중단)
- 업비트 Open API **IP 화이트리스트** 사용 시, 등록된 IP에서만 실행 가능
- GitHub Actions 등 **동적 IP** 환경은 업비트 IP 제한과 맞지 않아 당분간 사용하지 않음

---

## 5. 데이터 저장소

경로: `data/market.db` (SQLite)

| 테이블 | 용도 |
|--------|------|
| `market_snapshots` | 시세·환율·김프 스냅샷 |
| `metric_snapshots` | RSI, 환율 등 시계열 지표 |
| `trading_signals` | ADD_BUY 신호 큐 |
| `trade_decisions` | 매매 판단 기록 |
| `monthly_add_buy_ledger` | 월 추가 매수 집행 내역 |
| `daily_reports` | 일일 리포트 JSON |
| `job_runs` | Analysis / Trading / Report / Pipeline 배치 실행 이력 |

리포트 HTML: `reports/report_YYYY-MM-DD.html` (브라우저 대시보드, 타임라인 `<details>` 접기)

---

## 6. Windows 데스크톱 알림

구현: `services/desktop_notify.py` (`winotify`), `services/job_logger.py`에서 배치 완료 시 호출.

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `NOTIFY_ENABLED` | 알림 전체 스위치 | `true` |
| `NOTIFY_ON_BATCH_ANALYSIS` | Analysis 배치 완료 | `false` (빈도 높음) |
| `NOTIFY_ON_BATCH_TRADING` | Trading 배치 완료 | `true` |
| `NOTIFY_ON_BATCH_REPORT` | Report 완료 (HTML 경로 포함) | `true` |
| `NOTIFY_ON_SIGNAL` | ADD_BUY 신호 생성 | `false` |
| `NOTIFY_ON_BUY` | 실매수 체결 | `false` |
| `NOTIFY_ON_ERROR` | Worker 오류 | `true` |

Report 알림 클릭 시 해당 일자 HTML 리포트를 기본 브라우저로 연다.

테스트: `python scripts/test_notify.py`

---

## 7. 환경 변수

전체 목록: `.env.example`

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `UPBIT_ACCESS_KEY` | 업비트 Access Key | (필수) |
| `UPBIT_SECRET_KEY` | 업비트 Secret Key | (필수) |
| `DRY_RUN` | 실주문 없이 시뮬레이션 | `true` |
| `MONTHLY_ADD_BUY_BUDGET_KRW` | 월 추가 매수 한도 | `500000` |
| `ADD_BUY_MIN_SCORE` | 최소 종합 점수 | `5` |
| `ADD_BUY_REMAINING_PCT` | 1회 = 월 잔여 × 비율 | `0.15` |
| `ADD_BUY_MIN_ORDER_KRW` | 1회 최소 주문액 | `30000` |
| `ADD_BUY_MAX_PER_ORDER_KRW` | 1회 최대 주문액 | `50000` |
| `SIGNAL_COOLDOWN_HOURS` | 동일 신호 쿨다운 | `8` |
| `STRATEGY_SELL_ENABLED` | 매도 전략 | `false` |
| `SCORE_KIMCHI_FAVORABLE_PCT` | 김프 가점 기준 | `1.0` |
| `SCORE_KIMCHI_BLOCK_PCT` | 김프 차단 기준 | `2.5` |
| `SCORE_USD_KRW_BLOCK_PCT` | 환율 급등 차단 | `0.5` |
| `TRIGGER_ONCHAIN_ENABLED` | 온체인 차단 사용 | `false` |

알림 변수는 위 §6 참고. 전체 목록: `.env.example`

---

## 8. 보안

- `.env`는 Git에 올리지 않음
- 업비트 API: **출금 권한 비활성**, 조회·주문만 허용 권장
- **IP 화이트리스트** 등록 시, Agent가 실행되는 PC/서버 IP만 허용
- `DRY_RUN=true`로 충분히 검증 후 실주문 검토

---

## 9. Phase 2+ 로드맵 (설계)

| 항목 | 파일 (예정) |
|------|-------------|
| ATR SL/TP, Kill-switch | `services/risk_manager.py` |
| LangGraph 오케스트레이션 | `core/graph.py` |
| 실주문 | `UpbitClient.place_order` |
| 온체인·매크로 실구현 | `services/onchain_client.py` 등 |
| Self-Reflection 학습 루프 | LangGraph + Vector DB |

자세한 장기 비전: [`개발설계아이디어.md`](개발설계아이디어.md)
