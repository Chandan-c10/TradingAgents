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
