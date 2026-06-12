"""
현재 트리거 설정 및 실시간 지표 평가 결과 출력.

사용법:
    python scripts/show_triggers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_settings  # noqa: E402
from core.triggers import TriggerEngine  # noqa: E402
from core.workers.analysis_worker import AnalysisWorker  # noqa: E402
from services.exchange_rate import collect_market_snapshot  # noqa: E402
from services.onchain_client import fetch_onchain_metrics  # noqa: E402


def main() -> int:
    cfg = get_settings()
    print("=== 트리거 설정 (.env) ===")
    print(f"  BTC 하락 매수     : {cfg.trigger_btc_dip_pct}%  (enabled={cfg.trigger_btc_dip_enabled})")
    print(f"  BTC 상승 익절검토 : +{cfg.trigger_btc_surge_pct}%  (enabled={cfg.trigger_btc_surge_enabled})")
    print(f"  김프 낮음 매수    : {cfg.trigger_kimchi_low_pct}% 이하  (enabled={cfg.trigger_kimchi_low_enabled})")
    print(f"  김프 높음 보류    : {cfg.trigger_kimchi_high_pct}% 이상  (enabled={cfg.trigger_kimchi_high_enabled})")
    print(f"  환율 급등 관망    : +{cfg.trigger_usd_krw_spike_pct}%  (enabled={cfg.trigger_usd_krw_spike_enabled})")
    print(f"  온체인 유입       : {cfg.trigger_onchain_inflow_btc} BTC  (enabled={cfg.trigger_onchain_enabled})")
    print(f"  수익률 익절       : +{cfg.trigger_profit_sell_pct}%  (enabled={cfg.trigger_profit_sell_enabled})")
    print(f"  매수 최소 원화    : {cfg.trigger_min_krw_for_buy:,.0f} KRW")
    print(f"  신호 쿨다운       : {cfg.signal_cooldown_hours} 시간")
    print()

    print("=== 현재 시장 지표 (저장 없이 평가만) ===")
    worker = AnalysisWorker()
    try:
        snapshot = collect_market_snapshot(cfg.default_ticker)
        data = snapshot.to_dict()
        onchain = fetch_onchain_metrics().to_dict()
        metrics = worker._build_metrics(0, data, onchain)  # noqa: SLF001
        metrics.update(worker._fetch_account_metrics())  # noqa: SLF001

        print(f"  USD/KRW         : {metrics['usd_krw']:,.2f}")
        print(f"  BTC/KRW         : {metrics['btc_krw']:,.0f}")
        if metrics.get("kimchi_premium_pct") is not None:
            print(f"  김치 프리미엄   : {metrics['kimchi_premium_pct']:+.2f}%")
        if metrics.get("btc_krw_change_pct") is not None:
            print(f"  BTC 직전대비    : {metrics['btc_krw_change_pct']:+.2f}%")
        if metrics.get("usd_krw_change_pct") is not None:
            print(f"  환율 직전대비   : {metrics['usd_krw_change_pct']:+.2f}%")
        if metrics.get("account_pnl_rate_pct") is not None:
            print(f"  계좌 수익률     : {metrics['account_pnl_rate_pct']:+.2f}%")
        print()

        result = TriggerEngine().evaluate(metrics)
        if result.fired:
            print("[신호 발생 예측]")
            print(f"  대표 트리거 : {result.trigger_type}")
            print(f"  사유        : {result.reason}")
            print("  충족 규칙:")
            for hit in result.all_hits:
                print(f"    - [{hit.category}] {hit.trigger_type}: {hit.reason}")
        else:
            print("[신호 없음] 현재 조건 미충족")
    except Exception as exc:  # noqa: BLE001
        print(f"  오류: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
