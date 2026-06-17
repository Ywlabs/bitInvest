"""리포트용 ADD_BUY / HOLD 판단 근거 서술."""

from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from core.strategy.budget import MonthlyBudget
from core.strategy.tiers import resolve_add_buy_tier
from services.signal_store import get_cooldown_status, has_pending_signal


def build_execution_status_lines(
    *,
    score: dict[str, Any],
    decision: dict[str, Any],
    settings: Settings | None = None,
) -> list[str]:
    """리포트용 — 현재 시점 매매 실행 가능 여부 (쿨다운·예산 포함)."""
    settings = settings or get_settings()
    cooldown = get_cooldown_status("ADD_BUY", settings.signal_cooldown_hours)
    recommend = bool(score.get("recommend_add_buy"))
    recommended = float(score.get("recommended_krw") or 0)
    blocked = bool(score.get("blocked"))
    pending = has_pending_signal("ADD_BUY")

    lines = ["[매매 실행 상태]"]

    if pending:
        lines.append("  현재 상태       : pending 신호 존재 — TradingWorker 처리 대기")
        if recommended > 0:
            lines.append(f"  예상 매수 금액 : {recommended:,.0f}원")
        lines.append("")
        return lines

    if recommend and recommended > 0 and not blocked:
        if cooldown["in_cooldown"]:
            lines.extend(
                [
                    "  현재 상태       : 매수 조건 충족 — 쿨다운으로 신호·실매수 보류",
                    f"  종합 점수       : {score.get('total_score', '-')} (ADD_BUY 권장)",
                    f"  예상 매수 금액 : {recommended:,.0f}원",
                    f"  쿨다운 설정     : {settings.signal_cooldown_hours:g}시간",
                    f"  직전 신호       : #{cooldown['last_signal_id']} ({cooldown['last_signal_at']})",
                    f"  다음 가능 시각  : {cooldown['next_available_at']}",
                    f"  남은 대기       : 약 {cooldown['remaining_hours']:.1f}시간",
                ]
            )
            if decision.get("executed"):
                lines.append(
                    f"  최근 실매수     : 신호 #{decision.get('signal_id')} "
                    f"{decision.get('buy_amount_krw', 0):,.0f}원 "
                    f"(uuid={decision.get('order_uuid', '-')})"
                )
            lines.append("")
            return lines

        lines.extend(
            [
                "  현재 상태       : 매수 조건 충족 — 신호 생성·실매수 가능",
                f"  예상 매수 금액 : {recommended:,.0f}원",
                "",
            ]
        )
        return lines

    if blocked:
        reasons = ", ".join(score.get("block_reasons") or [])
        lines.append(f"  현재 상태       : 매수 보류 — {reasons}")
    elif not recommend:
        lines.append(
            f"  현재 상태       : 매수 조건 미충족 "
            f"(종합 {score.get('total_score', '-')} / "
            f"기준 {score.get('effective_min_score', '-')})"
        )
    elif recommended <= 0:
        lines.append("  현재 상태       : 점수 충족 — 월 예산·최소주문 미달로 금액 산정 불가")
    else:
        lines.append(f"  현재 상태       : {decision.get('action', 'HOLD')}")

    lines.append("")
    return lines


def _is_cooldown_blocked(score: dict[str, Any], settings: Settings) -> bool:
    if bool(score.get("blocked")):
        return False
    if not score.get("recommend_add_buy") or float(score.get("recommended_krw") or 0) <= 0:
        return False
    if has_pending_signal("ADD_BUY"):
        return False
    return get_cooldown_status("ADD_BUY", settings.signal_cooldown_hours)["in_cooldown"]


def _score_tier_label(score: float, settings: Settings) -> str:
    tier = resolve_add_buy_tier(score, settings)
    if tier is None:
        return "등급 없음 (점수 부족)"
    return (
        f"{tier.label} ({tier.key}) — {tier.min_score}점+ → 배율 ×{tier.size_multiplier:.1f}"
    )


def _gate_line(passed: bool, label: str, detail: str = "") -> str:
    mark = "통과" if passed else "미통과"
    suffix = f" — {detail}" if detail else ""
    return f"    [{mark}] {label}{suffix}"


def _missed_conditions(technical: dict[str, Any], score: dict[str, Any], settings: Settings) -> list[str]:
    """가점은 없었지만 참고할 조건."""
    missed: list[str] = []
    factors = {b.get("factor") for b in (score.get("breakdown") or [])}

    rsi = technical.get("rsi_14")
    if rsi is not None and rsi > 40 and "RSI" not in factors:
        missed.append(f"RSI {rsi:.1f} — 과매도 구간(≤40) 아님, RSI 가점 없음")

    if not technical.get("capitulation"):
        missed.append("투매형 캔들(급락+대량) 미발생 — CAPITULATION 가점 없음")

    vol_ratio = technical.get("volume_ratio")
    ret_1d = technical.get("return_1d_pct")
    if vol_ratio is not None and vol_ratio < settings.score_volume_confirm_ratio:
        missed.append(f"거래량 {vol_ratio:.2f}x — 동반 하락 확인 기준({settings.score_volume_confirm_ratio}x) 미달")

    if ret_1d is not None and ret_1d >= 0 and "VOLUME" not in factors:
        missed.append(f"전일 대비 {ret_1d:+.1f}% — 하락일 아님, 거래량 동반 조정 가점 없음")

    bb_b = technical.get("bb_pct_b")
    if bb_b is not None and bb_b > 0.1 and "BOLLINGER" not in factors:
        missed.append(f"볼린저 %B {bb_b:.2f} — 하단 밴드 근접 아님")

    if technical.get("weekly_trend") != "bull":
        missed.append(f"주봉 {technical.get('weekly_trend', '-')} — 강세 가점 제한적")

    if not technical.get("rsi_bullish_divergence") and not technical.get("macd_bullish_divergence"):
        missed.append("RSI/MACD 강세 다이버전스 없음")

    macd_hist = technical.get("macd_hist")
    macd_prev = technical.get("macd_hist_prev")
    if macd_hist is not None and macd_prev is not None:
        if not (macd_prev < 0 <= macd_hist) and "MACD" not in factors:
            missed.append("MACD 히스토그램 상향 전환 없음")

    return missed[:6]


def _amount_breakdown(
    score: dict[str, Any],
    buy_krw: float,
    settings: Settings,
    budget: MonthlyBudget,
) -> list[str]:
    """매수 금액 산정 단계."""
    total = float(score.get("total_score") or 0)
    mult = float(score.get("atr_size_multiplier") or 1.0)
    tier = budget.resolve_tier(total)

    lines = [
        f"    ① ADD_BUY 등급 : {_score_tier_label(total, settings)}",
    ]
    if tier:
        paced_base = budget.remaining() * settings.add_buy_remaining_pct
        after_tier = paced_base * tier.size_multiplier
        after_atr = after_tier * mult
        lines.append(
            f"    ② 페이싱 기준   : 잔여 {budget.remaining():,.0f}원 × "
            f"{settings.add_buy_remaining_pct:.0%} = {paced_base:,.0f}원"
        )
        lines.append(f"    ③ 등급 배율     : ×{tier.size_multiplier:.1f} → {after_tier:,.0f}원")
        if mult < 1.0:
            lines.append(f"    ④ ATR 배율      : ×{mult:.2f} → {after_atr:,.0f}원")
        lines.append(f"    ⑤ 절대 상한     : max {settings.add_buy_max_per_order_krw:,.0f}원")
    lines.append(f"    → 최종 주문액   : {buy_krw:,.0f}원 (최소 {settings.add_buy_min_order_krw:,.0f}원)")
    return lines


def build_decision_narrative(
    *,
    score: dict[str, Any],
    technical: dict[str, Any],
    decision: dict[str, Any],
    account: dict[str, Any],
    trigger_reason: str = "",
) -> list[str]:
    """ADD_BUY/HOLD 판단 근거를 리포트용 문장 목록으로 반환."""
    settings = get_settings()
    budget = MonthlyBudget(settings)

    total = float(score.get("total_score") or 0)
    effective_min = float(score.get("effective_min_score") or settings.add_buy_min_score)
    base_min = settings.add_buy_min_score
    blocked = bool(score.get("blocked"))
    block_reasons: list[str] = list(score.get("block_reasons") or [])
    action = decision.get("action", "HOLD")
    buy_krw = float(decision.get("buy_amount_krw") or 0)
    krw = float(account.get("krw_balance") or 0)

    lines: list[str] = ["[판단 근거 — ADD_BUY 상세]"]

    # --- 1. 한 줄 요약 ---
    if _is_cooldown_blocked(score, settings):
        lines.append(
            f"  결론: HOLD — 매수 조건 충족(종합 {total:.1f}점)이나 "
            f"쿨다운 {settings.signal_cooldown_hours:g}시간 제약으로 이번 실행 보류"
        )
    elif action == "ADD_BUY":
        top = sorted(score.get("breakdown") or [], key=lambda x: x.get("points", 0), reverse=True)[:3]
        top_txt = ", ".join(f"{t.get('factor')}(+{t.get('points', 0):.1f})" for t in top)
        lines.append(
            f"  결론: ADD_BUY — 종합 {total:.1f}점이 기준 {effective_min:.1f}점 이상이며, "
            f"차단 조건 없음. 핵심 요인: {top_txt}"
        )
    else:
        lines.append(f"  결론: HOLD — {decision.get('reason', '조건 미충족')}")

    # --- 2. 게이트 체크리스트 ---
    lines.append("")
    lines.append("  [판정 게이트]")
    lines.append(_gate_line(not blocked, "차단(보류) 요인 없음", "없음" if not block_reasons else ""))
    for reason in block_reasons:
        lines.append(f"         ↳ 차단: {reason}")

    weekly = technical.get("weekly_trend")
    weekly_ok = not (settings.score_weekly_bear_block_enabled and weekly == "bear")
    lines.append(
        _gate_line(
            weekly_ok,
            "주봉 MTF",
            f"추세={weekly}, 200주선 {technical.get('weekly_dist_ma200_pct', 0):+.1f}%",
        )
    )

    rsi = technical.get("rsi_14")
    rsi_block = rsi is not None and rsi >= 70
    lines.append(
        _gate_line(
            not rsi_block,
            "RSI 과매수 차단",
            f"RSI={rsi:.1f}" if rsi is not None else "-",
        )
    )

    lines.append(
        _gate_line(
            total >= effective_min,
            f"종합 점수 ≥ 최소 기준 ({effective_min:.1f})",
            f"{total:.1f}점 (기본 {base_min:.1f}"
            + (f" + ATR가산 {effective_min - base_min:.1f}" if effective_min > base_min else "")
            + ")",
        )
    )

    lines.append(
        _gate_line(
            bool(score.get("recommend_add_buy")),
            "예산·금액 산정 가능",
            f"권장 {score.get('recommended_krw', 0):,.0f}원",
        )
    )

    if action == "ADD_BUY":
        lines.append(_gate_line(krw >= buy_krw or buy_krw <= krw, "가용 원화", f"{krw:,.0f}원"))
        lines.append(
            _gate_line(budget.can_spend(buy_krw) or buy_krw > 0, "월 추가매수 잔여", f"{budget.remaining():,.0f}원")
        )

    # --- 3. 가점 요인 (팩터별) ---
    breakdown = score.get("breakdown") or []
    if breakdown:
        lines.append("")
        lines.append("  [가점 요인 — 왜 점수가 올랐는가]")
        groups: dict[str, list[dict[str, Any]]] = {}
        group_map = {
            "WEEKLY": "① 멀티 타임프레임",
            "RSI": "② 모멘텀",
            "MACD": "② 모멘텀",
            "MA200": "② 모멘텀",
            "MOMENTUM": "② 모멘텀",
            "ADX": "② 모멘텀",
            "MA_STACK": "② 모멘텀",
            "SUPPORT": "③ 시장 구조",
            "STRUCTURE": "③ 시장 구조",
            "DIVERGENCE": "③ 시장 구조",
            "BOLLINGER": "③ 시장 구조",
            "DRAWDOWN": "④ 조정·거래량",
            "CAPITULATION": "④ 조정·거래량",
            "VOLUME": "④ 조정·거래량",
            "VWAP": "④ 조정·거래량",
            "KIMCHI": "⑤ 매크로",
            "ONCHAIN": "⑤ 매크로",
        }
        for item in breakdown:
            factor = item.get("factor", "?")
            header = group_map.get(factor, "⑥ 기타")
            groups.setdefault(header, []).append(item)

        for header in sorted(groups.keys()):
            lines.append(f"    {header}")
            for item in groups[header]:
                lines.append(
                    f"      +{item.get('points', 0):.1f} [{item.get('factor')}] {item.get('reason', '')}"
                )

    # --- 4. 미충족 조건 ---
    missed = _missed_conditions(technical, score, settings)
    if missed:
        lines.append("")
        lines.append("  [미충족 조건 — 이번에 가점이 없었던 이유]")
        for m in missed:
            lines.append(f"    · {m}")

    # --- 5. 금액 산정 ---
    if action == "ADD_BUY" and buy_krw > 0:
        lines.append("")
        lines.append("  [매수 금액 산정 과정]")
        lines.extend(_amount_breakdown(score, buy_krw, settings, budget))

    # --- 6. 실행 ---
    lines.append("")
    lines.append("  [실행]")
    if _is_cooldown_blocked(score, settings):
        lines.append("    최종 액션       : HOLD (쿨다운 — 조건 충족, 실매수 보류)")
        lines.append(
            f"    예상 매수 금액 : {score.get('recommended_krw', 0):,.0f}원 "
            f"(쿨다운 해제 후 신호 생성 가능)"
        )
    else:
        lines.append(f"    신호 사유       : {trigger_reason or decision.get('reason', '-')}")
        lines.append(f"    최종 액션       : {action}")
        if decision.get("order_uuid"):
            lines.append(f"    주문 UUID       : {decision.get('order_uuid')}")
        if decision.get("execution_note"):
            lines.append(f"    실행 메모       : {decision.get('execution_note')}")
        if decision.get("executed"):
            lines.append(f"    체결 요청       : 완료 ({decision.get('buy_amount_krw', 0):,.0f}원)")
        elif action == "ADD_BUY" and decision.get("dry_run", True):
            lines.append("    DRY_RUN         : True — 실주문 없이 판단·기록만 수행")
        elif action == "ADD_BUY":
            lines.append("    체결 요청       : 실패 또는 미실행")

    lines.append("")
    return lines
