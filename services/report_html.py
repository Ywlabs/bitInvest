"""일일 리포트 HTML 대시보드 렌더링."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from config import Settings, get_settings
from core.strategy.budget import MonthlyBudget
from core.strategy.report_narrative import (
    _is_cooldown_blocked,
    build_decision_narrative,
    build_execution_status_lines,
)


def _esc(value: Any) -> str:
    if value is None:
        return "-"
    return html.escape(str(value))


def _fmt_num(val: Any, fmt: str = ",.2f") -> str:
    if val is None or val == "-":
        return "-"
    try:
        return format(float(val), fmt)
    except (TypeError, ValueError):
        return _esc(val)


def _fmt_krw(val: Any) -> str:
    if val is None:
        return "-"
    try:
        return f"{float(val):,.0f}"
    except (TypeError, ValueError):
        return _esc(val)


def _lines_to_html_block(lines: list[str]) -> str:
    """텍스트 블록을 읽기 쉬운 HTML로."""
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            items.append(f'<h3 class="sub-title">{_esc(stripped.strip("[]"))}</h3>')
        else:
            items.append(f'<p class="mono-line">{_esc(stripped)}</p>')
    return "\n".join(items)


def render_daily_report(
    *,
    report_date: str,
    created_at: str,
    market: dict[str, Any],
    analysis: dict[str, Any],
    decision: dict[str, Any],
    account: dict[str, Any],
    signal_id: int | None,
    signal_created: bool,
    trigger_reason: str,
    errors: list[str],
    settings: Settings | None = None,
) -> str:
    """대시보드 형태 HTML 문자열 생성."""
    settings = settings or get_settings()
    budget = MonthlyBudget(settings)
    score = analysis.get("score") or {}
    technical = analysis.get("technical") or {}

    total_score = float(score.get("total_score") or 0)
    max_score = float(score.get("max_possible") or 24)
    effective_min = float(score.get("effective_min_score") or settings.add_buy_min_score)
    recommend = bool(score.get("recommend_add_buy"))
    pct = min(100.0, (total_score / max_score * 100) if max_score else 0)

    cooldown_blocked = _is_cooldown_blocked(score, settings)
    action = "HOLD (쿨다운)" if cooldown_blocked else decision.get("action", "-")
    buy_amount = (
        float(score.get("recommended_krw") or 0)
        if cooldown_blocked
        else float(decision.get("buy_amount_krw") or 0)
    )
    executed = decision.get("executed", False)
    dry_run = decision.get("dry_run", settings.dry_run)

    status_class = "badge-ok" if recommend and not score.get("blocked") else "badge-warn"
    if score.get("blocked"):
        status_class = "badge-danger"

    exec_lines = build_execution_status_lines(score=score, decision=decision, settings=settings)
    narrative_lines = build_decision_narrative(
        score=score,
        technical=technical,
        decision=decision,
        account=account,
        trigger_reason=trigger_reason,
    )

    breakdown = score.get("breakdown") or []
    breakdown_html = ""
    if breakdown:
        chips = [
            f'<span class="chip"><b>+{_fmt_num(b.get("points"), ".1f")}</b> '
            f'{_esc(b.get("factor"))} — {_esc(b.get("reason"))}</span>'
            for b in breakdown
        ]
        breakdown_html = '<div class="chips">' + "".join(chips) + "</div>"
    else:
        breakdown_html = '<p class="muted">가점 요인 없음</p>'

    holdings = account.get("holdings") or []
    holdings_rows = ""
    for h in holdings:
        holdings_rows += (
            "<tr>"
            f"<td>{_esc(h.get('currency'))}</td>"
            f"<td class='num'>{_fmt_num(h.get('total'), '.8f')}</td>"
            f"<td class='num'>{_fmt_krw(h.get('avg_buy_price'))}</td>"
            "</tr>"
        )
    if not holdings_rows:
        holdings_rows = "<tr><td colspan='3' class='muted'>보유 코인 없음</td></tr>"

    tech_rows = [
        ("RSI (14)", _fmt_num(technical.get("rsi_14"), ".1f")),
        ("MACD hist", _fmt_num(technical.get("macd_hist"), ",.0f")),
        ("7일 수익률", f"{_fmt_num(technical.get('return_7d_pct'))}%"),
        ("30일 수익률", f"{_fmt_num(technical.get('return_30d_pct'))}%"),
        ("200MA 이격", f"{_fmt_num(technical.get('dist_ma200_pct'))}%"),
        ("52주 Drawdown", f"{_fmt_num(technical.get('drawdown_52w_pct'))}%"),
        ("ATR (14)", f"{_fmt_num(technical.get('atr_14_pct'))}%"),
        ("거래량 비율", f"{_fmt_num(technical.get('volume_ratio'), '.2f')}x"),
        ("주봉 추세", _esc(technical.get("weekly_trend"))),
        ("구조 bias", _esc(technical.get("structure_bias"))),
        ("ADX (14)", _fmt_num(technical.get("adx_14"), ".1f")),
        ("볼린저 %B", _fmt_num(technical.get("bb_pct_b"), ".2f")),
    ]
    tech_grid = "".join(
        f'<div class="stat"><span class="label">{label}</span><span class="value">{val}</span></div>'
        for label, val in tech_rows
    )

    errors_html = ""
    if errors:
        errs = "".join(f"<li>{_esc(e)}</li>" for e in errors)
        errors_html = f'<section class="card card-danger"><h2>오류</h2><ul>{errs}</ul></section>'

    kimchi = market.get("kimchi_premium_pct")
    kimchi_txt = f"{kimchi:+.2f}%" if kimchi is not None else "-"
    live_tag = (
        '<span class="tag">실시간 재계산</span>' if analysis.get("live_recomputed") else ""
    )

    generated = created_at
    try:
        generated = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        pass

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>bitInvest 리포트 {report_date}</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --border: #2d3a4f;
      --text: #e8eef7;
      --muted: #8b9cb3;
      --accent: #3b82f6;
      --ok: #22c55e;
      --warn: #f59e0b;
      --danger: #ef4444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", "Malgun Gothic", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 1.25rem;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
    header {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.5rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
    }}
    h1 {{ font-size: 1.5rem; font-weight: 700; }}
    .meta {{ color: var(--muted); font-size: 0.875rem; }}
    .tag {{
      display: inline-block;
      background: #243044;
      color: var(--accent);
      font-size: 0.75rem;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      margin-left: 0.5rem;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .kpi {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem;
    }}
    .kpi .label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
    .kpi .value {{ font-size: 1.35rem; font-weight: 700; margin-top: 0.25rem; }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem;
      margin-bottom: 1rem;
    }}
    .card h2 {{ font-size: 1rem; margin-bottom: 0.75rem; color: var(--accent); }}
    .card-danger {{ border-color: var(--danger); }}
    .sub-title {{ font-size: 0.9rem; color: var(--muted); margin: 0.75rem 0 0.35rem; }}
    .mono-line {{ font-size: 0.85rem; margin: 0.15rem 0; font-family: Consolas, monospace; }}
    .muted {{ color: var(--muted); font-size: 0.875rem; }}
    .badge {{
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
    }}
    .badge-ok {{ background: rgba(34,197,94,0.2); color: var(--ok); }}
    .badge-warn {{ background: rgba(245,158,11,0.2); color: var(--warn); }}
    .badge-danger {{ background: rgba(239,68,68,0.2); color: var(--danger); }}
    .score-bar {{
      height: 10px;
      background: #243044;
      border-radius: 5px;
      overflow: hidden;
      margin: 0.5rem 0 1rem;
    }}
    .score-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--ok));
      width: {pct:.1f}%;
    }}
    .chips {{ display: flex; flex-direction: column; gap: 0.35rem; }}
    .chip {{
      font-size: 0.8rem;
      background: #243044;
      padding: 0.35rem 0.6rem;
      border-radius: 6px;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 0.75rem;
    }}
    .stat .label {{ display: block; font-size: 0.7rem; color: var(--muted); }}
    .stat .value {{ font-size: 0.95rem; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
    th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-weight: 500; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .narrative {{ font-size: 0.85rem; }}
    footer {{ margin-top: 2rem; text-align: center; color: var(--muted); font-size: 0.75rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>bitInvest 일일 대시보드</h1>
        <p class="meta">{report_date} · 생성 {generated}{live_tag}</p>
      </div>
      <div>
        <span class="badge {status_class}">{"ADD_BUY 권장" if recommend else "관망"}</span>
        {"<span class='badge badge-warn'>DRY_RUN</span>" if dry_run else ""}
      </div>
    </header>

    <div class="kpis">
      <div class="kpi">
        <div class="label">BTC (업비트)</div>
        <div class="value">{_fmt_krw(market.get("btc_krw"))}원</div>
      </div>
      <div class="kpi">
        <div class="label">종합 점수</div>
        <div class="value">{_fmt_num(total_score, ".1f")} / {_fmt_num(max_score, ".1f")}</div>
      </div>
      <div class="kpi">
        <div class="label">권장 추가매수</div>
        <div class="value">{_fmt_krw(score.get("recommended_krw"))}원</div>
      </div>
      <div class="kpi">
        <div class="label">월 예산 잔여</div>
        <div class="value">{_fmt_krw(budget.remaining())}원</div>
      </div>
    </div>

    <section class="card">
      <h2>종합 점수</h2>
      <div class="score-bar"><div class="score-fill"></div></div>
      <p>최소 기준 <b>{_fmt_num(effective_min, ".1f")}</b>점 · 신뢰도 {_fmt_num(score.get("confidence"), ".2f")}
      {" · 등급 " + _esc(score.get("add_buy_tier_label")) if score.get("add_buy_tier_label") else ""}</p>
      {breakdown_html}
    </section>

    <div class="grid-2">
      <section class="card">
        <h2>시장 스냅샷</h2>
        <table>
          <tr><td>수집 시각</td><td class="num">{_esc(market.get("captured_at", "-"))}</td></tr>
          <tr><td>USD/KRW</td><td class="num">{_fmt_num(market.get("usd_krw"))}</td></tr>
          <tr><td>BTC/USD (환산)</td><td class="num">{_fmt_num(market.get("btc_usd_implied"))}</td></tr>
          <tr><td>김치 프리미엄</td><td class="num">{kimchi_txt}</td></tr>
        </table>
      </section>
      <section class="card">
        <h2>신호 / 매매 요약</h2>
        <table>
          <tr><td>신호 ID</td><td class="num">{signal_id or "-"}</td></tr>
          <tr><td>결정</td><td class="num"><b>{_esc(action)}</b></td></tr>
          <tr><td>추가매수 금액</td><td class="num">{_fmt_krw(buy_amount)}원</td></tr>
          <tr><td>실주문 체결</td><td class="num">{"예" if executed else "아니오"}</td></tr>
        </table>
      </section>
    </div>

    <section class="card">
      <h2>매매 실행 상태</h2>
      <div class="narrative">{_lines_to_html_block(exec_lines)}</div>
    </section>

    <section class="card">
      <h2>기술적 지표</h2>
      <div class="stat-grid">{tech_grid}</div>
    </section>

    <section class="card">
      <h2>판단 근거</h2>
      <div class="narrative">{_lines_to_html_block(narrative_lines)}</div>
    </section>

    <section class="card">
      <h2>계좌 현황</h2>
      <table>
        <tr><td>원화 잔고</td><td class="num">{_fmt_krw(account.get("krw_balance"))}원</td></tr>
        <tr><td>총 평가액</td><td class="num">{_fmt_krw(account.get("total_eval_amount"))}원</td></tr>
        <tr><td>코인 손익</td><td class="num">{_fmt_krw(account.get("total_pnl"))}원 ({_fmt_num(account.get("total_pnl_rate"), "+.2f")}%)</td></tr>
      </table>
      <h3 class="sub-title">보유 코인</h3>
      <table>
        <thead><tr><th>코인</th><th>수량</th><th>평단</th></tr></thead>
        <tbody>{holdings_rows}</tbody>
      </table>
    </section>

    {errors_html}

    <footer>bitInvest · 업비트 BTC 종합점수 ADD_BUY · DCA 별도 운영</footer>
  </div>
</body>
</html>"""
