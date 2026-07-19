import json
import os
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_fii_dii_flows() -> str:
    """
    Retrieve the latest published FII (Foreign Institutional Investor) and DII
    (Domestic Institutional Investor) net cash-market flow figures for Indian
    equities, sourced from NSE's daily FII/DII report. Only meaningful for
    India-listed instruments — skip this for non-Indian tickers.

    Unlike other data tools here, this isn't fetched live per call: the host
    application pre-fetches the latest scraped row once per session (there is
    no per-request vendor to query) and hands it over via environment
    variable, so this simply formats whatever was provided — or reports it as
    unavailable if the host hasn't set it (e.g. no scrape has run yet).

    Returns:
        str: A formatted summary of FII/DII net buy/sell figures (INR crores)
        for the most recent published trading day, or a message noting the
        data is unavailable.
    """
    raw = os.environ.get("FII_DII_TODAY_JSON")
    if not raw:
        return (
            "FII/DII flow data is unavailable for this session "
            "(not applicable to non-Indian instruments, or no data has been fetched yet)."
        )
    try:
        data = json.loads(raw)
    except ValueError:
        return "FII/DII flow data is unavailable (malformed data)."

    date = data.get("date", "unknown date")
    lines = [f"## NSE FII/DII Cash Market Flows — {date}"]

    fii_net = data.get("fii_net")
    if fii_net is not None:
        stance = "net buyers" if fii_net >= 0 else "net sellers"
        lines.append(
            f"- **FII/FPI:** Buy ₹{data.get('fii_buy'):.2f} Cr, Sell ₹{data.get('fii_sell'):.2f} Cr, "
            f"Net {fii_net:+.2f} Cr ({stance})"
        )
    dii_net = data.get("dii_net")
    if dii_net is not None:
        stance = "net buyers" if dii_net >= 0 else "net sellers"
        lines.append(
            f"- **DII:** Buy ₹{data.get('dii_buy'):.2f} Cr, Sell ₹{data.get('dii_sell'):.2f} Cr, "
            f"Net {dii_net:+.2f} Cr ({stance})"
        )

    if len(lines) == 1:
        return "FII/DII flow data is unavailable (no recognizable figures in the fetched data)."
    return "\n".join(lines)


@tool
def get_past_research_history() -> str:
    """
    Retrieve this desk's own past research sessions for the SAME instrument —
    what was previously predicted (rating, entry/target/stop, confidence) and,
    where the outcome has since resolved, whether real price action actually
    hit the target, hit the stop, or expired unresolved. Call this early when
    analyzing any symbol: a track record of past predictions being validated
    or invalidated is direct evidence about how reliable this desk's analysis
    has been on this specific instrument.

    Like get_fii_dii_flows, this isn't fetched live per call: the host
    application pre-fetches past matching sessions once per run and hands
    them over via environment variable, so this simply formats whatever was
    provided — or reports no history if this is the first time the
    instrument has been analyzed, or the host hasn't set it.

    Returns:
        str: A markdown table of up to 5 past sessions for this instrument
        (most recent first), or a message noting no history is available.
    """
    raw = os.environ.get("PAST_SESSIONS_JSON")
    if not raw:
        return "No past research history found for this instrument (first time analyzing it, or none yet resolved)."
    try:
        sessions = json.loads(raw)
    except ValueError:
        return "Past research history is unavailable (malformed data)."

    if not isinstance(sessions, list) or not sessions:
        return "No past research history found for this instrument."

    lines = [
        "## Past Research History (this instrument)",
        "| Date | Rating | Confidence | Entry | Target | Stop | Outcome |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in sessions:
        status = s.get("outcome_status") or "pending"
        outcome = status
        if status in ("target_hit", "stop_hit") and s.get("outcome_price") is not None:
            outcome = f"{status} @ {s['outcome_price']}"
        if status == "target_hit":
            outcome += " ✅"
        elif status == "stop_hit":
            outcome += " ❌"
        lines.append(
            f"| {s.get('analysis_date', '?')} | {s.get('final_rating', '?')} | "
            f"{s.get('confidence_score', '?')} | {s.get('entry_price', '?')} | "
            f"{s.get('target_price_1', '?')} | {s.get('stop_loss_price', '?')} | {outcome} |"
        )
    return "\n".join(lines)


@tool
def get_macro_indicators(
    indicator: Annotated[
        str,
        "Macro indicator: a friendly alias such as 'cpi', 'core_pce', "
        "'unemployment', 'fed_funds_rate', '10y_treasury', 'yield_curve', "
        "'real_gdp', 'vix', or a raw FRED series ID such as 'CPIAUCSL'.",
    ],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format; the end of the window"],
    look_back_days: Annotated[
        int | None, "Trailing window length in days; omit for a 1-year window"
    ] = None,
) -> str:
    """
    Retrieve a macroeconomic indicator time series from FRED (Federal Reserve
    Economic Data): policy rates, Treasury yields, inflation, labor, and growth.
    Returns the series title, units, frequency, the latest value, the change
    over the window, and a recent observation table. Uses the configured
    macro_data vendor.

    Args:
        indicator (str): Friendly alias or raw FRED series ID
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Trailing window length; omit for a 1-year window

    Returns:
        str: A formatted markdown report of the macro series
    """
    return route_to_vendor("get_macro_indicators", indicator, curr_date, look_back_days)
