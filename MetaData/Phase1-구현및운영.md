# bitInvest Phase 1 — 구현 및 운영 가이드

> 장기 설계 아이디어: [`개발설계아이디어.md`](개발설계아이디어.md)  
> 프로젝트 진입점: [`README.md`](../README.md)

---

## 1. 현재 단계 (Phase 1)

| 항목 | 상태 |
|------|------|
| Analysis / Trading / Report Worker | 구현 완료 |
| SQLite 신호 큐 (`trading_signals`) | 구현 완료 |
| 종합 점수 기반 ADD_BUY | 구현 완료 |
| Windows 배치 + 작업 스케줄러 | 구현 완료 |
| LangGraph 멀티 에이전트 | 미구현 (Phase 2+) |
| ATR 동적 SL/TP | 미구현 |
| 실주문 API | 미구현 (`DRY_RUN` 기본) |
| GitHub Actions 자동화 | **보류** (업비트 IP 화이트리스트와 충돌) |

업비트 **DCA(4만원 / 4시간)** 는 업비트 앱 설정으로 유지하고, 본 Agent는 **조건 충족 시 추가 매수(ADD_BUY)** 만 판단한다. **매도 전략 없음.**

---

## 2. 아키텍처

```
AnalysisWorker  →  trading_signals (pending)  →  TradingWorker  →  trade_decisions
       ↓                                                    ↓
  market.db (스냅샷·지표)                          monthly_add_buy_ledger
       ↓
 ReportWorker  →  reports/report_YYYY-MM-DD.txt
```

### Worker 역할

| Worker | 스크립트 | 역할 |
|--------|----------|------|
| **Analysis** | `scripts/run_analysis_watch.py` | 시세·지표 수집, 종합 점수 계산, ADD_BUY 신호 생성 |
| **Trading** | `scripts/run_trading_consumer.py` | `pending` 신호 1건 소비, 예산·점수 검증 후 매수 판단 |
| **Report** | `scripts/run_report.py` | 일일 리포트 (DB + 텍스트 파일) |

각 스크립트는 **1회 실행 후 종료**. 내장 루프 없음.

### 파이프라인 통합 실행

| 명령 | 동작 |
|------|------|
| `python scripts/run_pipeline.py` | Analysis → (기본) Trading 강제 시도 → Report |
| `python scripts/run_pipeline.py --event-only` | 신호 있을 때만 Trading (운영 권장) |
| `python scripts/run_pipeline.py --force` | 신호 없어도 Trading 강제 |

---

## 3. 종합 점수 및 매수 판단 기준

구현: `core/strategy/scoring.py`, `core/triggers/engine.py`, `core/workers/trading_worker.py`

### 3.1 가점 요인 (최대 12점)

| 요인 | 조건 | 점수 |
|------|------|------|
| RSI(14) | ≤ 30 (과매도) | +2.0 |
| | ≤ 40 (약과매도) | +1.0 |
| MACD | 히스토그램 음→양 전환 | +2.0 |
| | 음수 구간 하락 둔화 | +1.0 |
| 200일선 이격 | ≤ -15% | +2.0 |
| | ≤ -8% | +1.0 |
| 7일 수익률 | ≤ -8% | +1.5 |
| 30일 수익률 | ≤ -15% | +1.0 |
| 김프 | ≤ `SCORE_KIMCHI_FAVORABLE_PCT` (기본 1.0%) | +1.5 |
| 온체인 | 순유출 우세 (데이터 있을 때) | +1.0 |

### 3.2 보류(차단) 요인

| 요인 | 조건 (기본값) |
|------|----------------|
| RSI 과매수 | RSI ≥ 70 |
| 김프 과열 | ≥ `SCORE_KIMCHI_BLOCK_PCT` (2.5%) |
| 환율 급등 | USD/KRW 직전 대비 ≥ `SCORE_USD_KRW_BLOCK_PCT` (0.5%) |
| 온체인 유입 | `TRIGGER_ONCHAIN_ENABLED=true` 이고 유입 ≥ 500 BTC |

### 3.3 신호 생성 조건 (Analysis)

1. 보류 사유 없음
2. 종합 점수 ≥ `ADD_BUY_MIN_SCORE` (기본 5.0)
3. 권장 금액 > 0
4. 동일 `ADD_BUY` pending 신호 없음
5. `SIGNAL_COOLDOWN_HOURS`(기본 8시간) 내 최근 신호 없음

### 3.4 최종 매수 판단 (Trading)

| 검사 | 내용 |
|------|------|
| 신호 타입 | `ADD_BUY` 또는 `MANUAL` |
| 점수/보류 | 차단 없음, 최소 점수 이상 |
| 월 예산 | `MONTHLY_ADD_BUY_BUDGET_KRW` 잔여 |
| 1회 금액 | `ADD_BUY_MIN_ORDER_KRW` ~ `ADD_BUY_MAX_PER_ORDER_KRW` |
| 가용 원화 | `krw_balance` 충분 |

### 3.5 점수별 매수 금액 (월 예산 비율)

| 종합 점수 | 월 한도 사용 비율 |
|-----------|-------------------|
| 5 ~ 6.9 | 25% |
| 7 ~ 8.9 | 50% |
| 9 이상 | 100% |

1회 상한: `ADD_BUY_MAX_PER_ORDER_KRW` (기본 50만원)

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

로그: `logs/analysis.log`, `logs/trading.log`, `logs/report.log`, `logs/pipeline.log`  
(`logs/` 는 `.gitignore` 대상)

### 4.2 권장 스케줄

| 작업 이름 | 배치 | 주기 |
|-----------|------|------|
| `bitInvest-Analysis` | `run_analysis.bat` | 1시간마다 |
| `bitInvest-Trading` | `run_trading.bat` | 15분마다 |
| `bitInvest-Report` | `run_report.bat` | 매일 23:00 |

### 4.3 스케줄러 등록 (PowerShell)

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

리포트 텍스트: `reports/report_YYYY-MM-DD.txt`

---

## 6. 환경 변수

전체 목록: `.env.example`

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `UPBIT_ACCESS_KEY` | 업비트 Access Key | (필수) |
| `UPBIT_SECRET_KEY` | 업비트 Secret Key | (필수) |
| `DRY_RUN` | 실주문 없이 시뮬레이션 | `true` |
| `MONTHLY_ADD_BUY_BUDGET_KRW` | 월 추가 매수 한도 | `1000000` |
| `ADD_BUY_MIN_SCORE` | 최소 종합 점수 | `5` |
| `ADD_BUY_MIN_ORDER_KRW` | 1회 최소 주문액 | `100000` |
| `ADD_BUY_MAX_PER_ORDER_KRW` | 1회 최대 주문액 | `500000` |
| `SIGNAL_COOLDOWN_HOURS` | 동일 신호 쿨다운 | `8` |
| `STRATEGY_SELL_ENABLED` | 매도 전략 | `false` |
| `SCORE_KIMCHI_FAVORABLE_PCT` | 김프 가점 기준 | `1.0` |
| `SCORE_KIMCHI_BLOCK_PCT` | 김프 차단 기준 | `2.5` |
| `SCORE_USD_KRW_BLOCK_PCT` | 환율 급등 차단 | `0.5` |
| `TRIGGER_ONCHAIN_ENABLED` | 온체인 차단 사용 | `false` |

---

## 7. 보안

- `.env`는 Git에 올리지 않음
- 업비트 API: **출금 권한 비활성**, 조회·주문만 허용 권장
- **IP 화이트리스트** 등록 시, Agent가 실행되는 PC/서버 IP만 허용
- `DRY_RUN=true`로 충분히 검증 후 실주문 검토

---

## 8. Phase 2+ 로드맵 (설계)

| 항목 | 파일 (예정) |
|------|-------------|
| ATR SL/TP, Kill-switch | `services/risk_manager.py` |
| LangGraph 오케스트레이션 | `core/graph.py` |
| 실주문 | `UpbitClient.place_order` |
| 온체인·매크로 실구현 | `services/onchain_client.py` 등 |
| Self-Reflection 학습 루프 | LangGraph + Vector DB |

자세한 장기 비전: [`개발설계아이디어.md`](개발설계아이디어.md)
