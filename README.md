# bitInvest

업비트 BTC **종합 점수 기반 추가 매수(ADD_BUY)** 에이전트 워커 프로젝트입니다.

업비트에 설정된 **DCA(4만원 / 4시간)** 는 그대로 두고, 시장·기술적·매크로 지표를 종합해 **조건이 맞을 때만** 별도 추가 매수를 판단합니다. **매도 전략은 사용하지 않습니다.**

저장소: [https://github.com/Ywlabs/bitInvest](https://github.com/Ywlabs/bitInvest)

---

## 주요 특징

- **3분할 Worker**: Analysis → Trading → Report
- **이벤트 기반 신호 큐**: SQLite `trading_signals` 테이블
- **종합 점수(CompositeScorer)**: RSI, MACD, MA200, 김프, 환율 변동 등
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
├── tools/                  # 업비트 클라이언트, 기술 지표
├── scripts/                # 실행 스크립트
├── data/market.db          # SQLite (git 제외)
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
| `MONTHLY_ADD_BUY_BUDGET_KRW` | 월 추가 매수 한도 | `1000000` |
| `ADD_BUY_MIN_SCORE` | 최소 종합 점수 | `5` |
| `ADD_BUY_MIN_ORDER_KRW` | 1회 최소 주문액 | `100000` |
| `ADD_BUY_MAX_PER_ORDER_KRW` | 1회 최대 주문액 | `500000` |
| `SIGNAL_COOLDOWN_HOURS` | 동일 신호 쿨다운 | `8` |
| `STRATEGY_SELL_ENABLED` | 매도 전략 사용 여부 | `false` |

전체 목록은 `.env.example`을 참고하세요.

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
```

---

## SQLite 데이터베이스

경로: `data/market.db`

| 테이블 | 용도 |
|--------|------|
| `market_snapshots` | 시세·환율·김프 스냅샷 |
| `metric_snapshots` | RSI, 환율 등 시계열 지표 |
| `trading_signals` | ADD_BUY 신호 큐 |
| `trade_decisions` | 매매 판단 기록 |
| `monthly_add_buy_ledger` | 월 추가 매수 집행 내역 |
| `daily_reports` | 일일 리포트 JSON |

DB Browser for SQLite 등으로 열어 조회할 수 있습니다.

---

## 보안

- **`.env`는 Git에 올리지 마세요.** (`.gitignore`에 포함됨)
- API 키가 노출되었다면 업비트에서 **즉시 재발급**하세요.
- `DRY_RUN=true`로 충분히 검증한 뒤 실주문을 고려하세요.

---

## 라이선스

이 저장소의 LICENSE 파일을 참고하세요.
