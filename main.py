"""
업비트 계좌 연동 확인용 엔트리 포인트.

사용법:
    python main.py              # 계좌 요약 출력
    python main.py --test       # 연결 테스트만
    python main.py --raw        # 원본 잔고 JSON 출력
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from config import get_settings
from tools.upbit_client import UpbitClient, UpbitConnectionError


def print_account_summary(client: UpbitClient) -> None:
    """계좌 요약을 콘솔에 출력."""
    summary = client.get_account_summary()
    settings = get_settings()

    print("=" * 50)
    print("  업비트 계좌 연동 확인")
    print("=" * 50)
    print(f"  모드        : {'DRY-RUN (조회만)' if settings.dry_run else 'LIVE'}")
    print(f"  기본 티커   : {settings.default_ticker}")
    print("-" * 50)
    print(f"  원화 잔고   : {summary.krw_balance:,.0f} KRW")
    print(f"  원화 잠금   : {summary.krw_locked:,.0f} KRW")
    print(f"  총 평가액   : {summary.total_eval_amount:,.0f} KRW")
    print(f"  코인 손익   : {summary.total_pnl:+,.0f} KRW ({summary.total_pnl_rate:+.2f}%)")
    print("-" * 50)

    if not summary.holdings:
        print("  보유 코인   : 없음")
    else:
        print("  보유 코인:")
        for h in summary.holdings:
            print(
                f"    - {h.currency:6s}  "
                f"수량 {h.total:.8f}  "
                f"(가용 {h.available:.8f}, 잠금 {h.locked:.8f})  "
                f"평단 {h.avg_buy_price:,.0f} KRW"
            )

    print("=" * 50)


def main() -> int:
    parser = argparse.ArgumentParser(description="업비트 계좌 연동 확인")
    parser.add_argument("--test", action="store_true", help="API 연결 테스트만 수행")
    parser.add_argument("--raw", action="store_true", help="원본 잔고 JSON 출력")
    args = parser.parse_args()

    try:
        client = UpbitClient()
    except Exception as exc:
        print(f"[오류] 설정 로드 실패: {exc}", file=sys.stderr)
        print("\n.env.example 을 참고해 .env 파일을 생성해 주세요.", file=sys.stderr)
        return 1

    try:
        if args.test:
            client.test_connection()
            print("[성공] 업비트 API 연결 및 계좌 조회 권한 확인 완료")
            return 0

        if args.raw:
            raw = client.get_raw_balances()
            print(json.dumps(raw, ensure_ascii=False, indent=2))
            return 0

        client.test_connection()
        print_account_summary(client)
        return 0

    except UpbitConnectionError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
