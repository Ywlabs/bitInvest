# bitInvest

업비트 BTC **종합 점수 기반 추가 매수(ADD_BUY)** 에이전트 워커 프로젝트입니다.

업비트에 설정된 **DCA(4만원 / 4시간)** 는 그대로 두고, 시장·기술적·매크로 지표를 종합해 **조건이 맞을 때만** 별도 추가 매수를 판단합니다. **매도 전략은 사용하지 않습니다.**

저장소: [https://github.com/Ywlabs/bitInvest](https://github.com/Ywlabs/bitInvest)

---

## 주요 특징

- **3분할 Worker**: Analysis → Trading → Report
- **이벤트 기반 신호 큐**: SQLite `trading_signals` 테이블
- **종합 점수(CompositeScorer)**: 팩터 합성 — MTF, 모멘텀, 구조, Drawdown, 거래량, 매크로
- **TA 엔진 v2**: Wilder RSI/ATR, ADX, 볼린저, VWAP, OBV, 다이버전스, 시장 구조
- **월간 예산 한도**: `MONTHLY_ADD_BUY_BUDGET_KRW`
- **DRY_RUN 기본**: 실주문 없이 판단·기록만 수행

---

## 아키텍처

```
AnalysisWorker  →  trading_signals (pending)  →  TradingWorker  →  trade_decisions
       ↓                                                    ↓
  market.db (스냅샷·지표)                          monthly_add_buy_ledger
       ↓
 ReportWorker  →  reports/report_YYYY-MM-DD.txt
```

| Worker | 역할 |
|--------|------|
| **Analysis** | 시세·지표 수집, 종합 점수 계산, ADD_BUY 신호 생성 |
| **Trading** | `pending` 신호 소비, 예산·점수 검증 후 매수 판단 |
| **Report** | 일일 리포트 생성 (DB + 텍스트 파일) |

각 스크립트는 **1회 실행 후 종료**됩니다. 주기 감시가 필요하면 작업 스케줄러 등에서 반복 호출하세요.

---

## 프로젝트 구조

```
bitInvest/
├── main.py                 # 업비트 계좌 조회 CLI
├── config.py               # .env 기반 설정
├── core/
│   ├── pipeline.py         # Worker 오케스트레이터
│   ├── strategy/           # 종합 점수, 월 예산
│   ├── triggers/           # ADD_BUY 트리거 엔진
│   └── workers/            # Analysis / Trading / Report
├── services/               # SQLite, 환율, 신호 큐
├── tools/
│   ├── upbit_client.py
│   └── indicators/         # TA 엔진 (ta_math, structure, mtf, pipeline)
├── scripts/                # 실행 스크립트
│   └── batch/              # Windows 스케줄러용 (VBS 숨김 실행)
├── data/                   # market.db (git 제외)
└── reports/                # 일일 리포트 (git 제외)
```

---

## 설치

```powershell
cd D:\Develop\workspace-bitcoin
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

`.env.example`을 복사해 `.env`를 만듭니다.

```powershell
copy .env.example .env
```

`.env`에 업비트 API 키와 전략 설정을 입력합니다.

---

## 환경 변수 (요약)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `UPBIT_ACCESS_KEY` | 업비트 Access Key | (필수) |
| `UPBIT_SECRET_KEY` | 업비트 Secret Key | (필수) |
| `DRY_RUN` | 실주문 없이 시뮬레이션 | `true` |
| `MONTHLY_ADD_BUY_BUDGET_KRW` | 월 추가 매수 한도 | `500000` |
| `ADD_BUY_MIN_SCORE` | 최소 종합 점수 | `5` |
| `ADD_BUY_REMAINING_PCT` | 1회 = 월 잔여 × 비율 | `0.15` |
| `ADD_BUY_TIER_LOW_MULTIPLIER` | 저등급 배율 | `0.8` |
| `ADD_BUY_TIER_MID_MULTIPLIER` | 중등급 배율 | `1.0` |
| `ADD_BUY_TIER_HIGH_MULTIPLIER` | 고등급 배율 | `1.2` |
| `ADD_BUY_TIER_MID_MIN_SCORE` | 중등급 최소 점수 | `7` |
| `ADD_BUY_TIER_HIGH_MIN_SCORE` | 고등급 최소 점수 | `9` |
| `ADD_BUY_MIN_ORDER_KRW` | 1회 최소 주문액 | `30000` |
| `ADD_BUY_MAX_PER_ORDER_KRW` | 1회 절대 상한 | `50000` |
| `SIGNAL_COOLDOWN_HOURS` | 동일 신호 쿨다운 | `8` |
| `STRATEGY_SELL_ENABLED` | 매도 전략 사용 여부 | `false` |
| `SCORE_WEEKLY_BEAR_BLOCK_ENABLED` | 주봉 약세 시 차단 | `true` |
| `ATR_HIGH_RATIO` | 고변동 ATR 비율 임계 | `1.5` |
| `ATR_HIGH_SIZE_MULTIPLIER` | 고변동 시 매수 금액 배율 | `0.5` |

전체 목록은 `.env.example`을 참고하세요.

---

## 종합 점수 (Phase 2-Pro)

팩터 합성 엔진. 최대 **24점**. 기본 최소 **5점** + ATR 레짐 가산.

**ADD_BUY 금액 (월 잔여 페이싱, `.env` 설정)**

| 등급 | 점수 | 배율 |
|------|------|------|
| 저 | `MIN_SCORE` ~ 중등급 미만 | ×0.8 |
| 중 | `TIER_MID_MIN_SCORE`(7) ~ 고등급 미만 | ×1.0 |
| 고 | `TIER_HIGH_MIN_SCORE`(9)+ | ×1.2 |

**1회 금액** = `int(월 잔여 × REMAINING_PCT(15%) × 등급배율 × ATR배율)`, 1회 상한 5만 원.

월 한도 `MONTHLY_ADD_BUY_BUDGET_KRW`(기본 50만) 내에서만 집행. 예산이 줄수록 1회 금액도 자동 축소.

| 팩터 | 내용 | 상한 |
|------|------|------|
| **MTF** | 주봉 약세 차단, 강세·정렬 가점 | 1.5 |
| **Momentum** | RSI, MACD, MA200, ADX, 정배열 | 9.5 |
| **Structure** | 지지·Higher Low, 다이버전스, 볼린저 | 5.0 |
| **Vol/DD** | Drawdown, 투매·축적, VWAP | 5.0 |
| **Macro** | 김프, 환율, 온체인 | 2.5 |

지표 엔진: `tools/indicators/` — `ta_math.py`(순수 수학), `pipeline.py`(조립).

---

## 실행 방법

```powershell
# 계좌 연동 확인
python main.py

# 종합 점수만 확인
python scripts/show_score.py

# Analysis: 감시 1회 (조건 충족 시 신호 생성)
python scripts/run_analysis_watch.py

# Trading: pending 신호 1건 처리
python scripts/run_trading_consumer.py

# Report: 일일 리포트 생성
python scripts/run_report.py

# 통합 테스트 (watch + consumer + report)
python scripts/run_pipeline.py
python scripts/run_pipeline.py --event-only   # 신호 있을 때만 Trading
```

### Windows 주기 실행 (작업 스케줄러, 창 없음)

배치·매매 이력은 `data/market.db`에 저장됩니다. `logs/` 파일은 사용하지 않습니다.

```powershell
# 수동 1회 (콘솔 출력 필요 시)
python scripts/run_analysis_watch.py
python scripts/run_trading_consumer.py
python scripts/run_report.py

# 배치 1회 (창 최소화 — VBS 경유)
scripts\batch\run_analysis.bat

# 작업 스케줄러 등록 — 콘솔 창 없음 (권장)
.\scripts\batch\register_tasks.ps1

# 이력 조회
python scripts/show_job_log.py
python scripts/show_job_log.py --job trading --limit 20
```

권장 주기: Analysis 1시간 / Trading 15분 / Report 매일 23:00.

> 기존에 `.bat`을 직접 등록했다면 `register_tasks.ps1`로 다시 등록하세요.  
> `.bat` 대신 `wscript.exe //B launch_worker.vbs`를 쓰면 순간적으로 뜨던 cmd 창이 사라집니다.

---

## SQLite 데이터베이스

### `data/market.db` — 매매·시장 데이터

| 테이블 | 용도 |
|--------|------|
| `market_snapshots` | 시세·환율·김프 스냅샷 |
| `metric_snapshots` | RSI, 환율 등 시계열 지표 |
| `trading_signals` | ADD_BUY 신호 큐 |
| `trade_decisions` | 매매 판단 기록 |
| `monthly_add_buy_ledger` | 월 추가 매수 집행 내역 |
| `daily_reports` | 일일 리포트 JSON |
| `job_runs` | Analysis/Trading/Report/Pipeline 배치 실행 이력 |

CLI: `python scripts/show_job_log.py`

DB Browser for SQLite 등으로 열어 조회할 수 있습니다.

---

## 보안

- **`.env`는 Git에 올리지 마세요.** (`.gitignore`에 포함됨)
- API 키가 노출되었다면 업비트에서 **즉시 재발급**하세요.
- `DRY_RUN=true`로 충분히 검증한 뒤 `.env`에서 `DRY_RUN=false`로 실매수 전환
- 실매수 전: `python scripts/preflight_check.py`
- 실주문: `UpbitClient.buy_market_krw()` — 시장가 매수 (원화 금액)

---

## 라이선스

이 저장소의 LICENSE 파일을 참고하세요.
