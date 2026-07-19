"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured,
)


def create_portfolio_manager(llm):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Research Manager's investment plan: **{research_plan}**
- Trader's transaction proposal: **{trader_plan}**
{lessons_line}
**Risk Analysts Debate History:**
{history}

---

Be decisive and ground every conclusion in specific evidence from the analysts.

In addition to the rating and summary above, provide:
- **bullish_scenario**: one concise paragraph on what has to go right for this position to work out, grounded in specific catalysts from the debate.
- **bearish_scenario**: one concise paragraph on what would invalidate this thesis, grounded in specific risks from the debate.
- **key_risks**: 2-5 concrete, specific risks (not generic boilerplate), each traceable to something in the analysts' reports or the risk debate.
- **confidence_score**: 0-100, based on how much the risk debate converged versus stayed split, and how much corroborating evidence exists. A sharply divided debate should score low even with a decisive rating.
- **time_horizon**: exactly one of "Swing (days-weeks)", "Short-term (weeks-months)", or "Long-term (months+)" — never imply an intraday or scalp horizon, this analysis is not suited for that timeframe.

Omit any of the five fields above you genuinely cannot support with real evidence from the debate — do not guess or fabricate a value just to fill the field.{get_language_instruction()}"""

        final_trade_decision, decision_obj = invoke_structured(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
            "confidence_score": decision_obj.confidence_score if decision_obj else None,
            "time_horizon": decision_obj.time_horizon.value if decision_obj and decision_obj.time_horizon else None,
            "bullish_scenario": decision_obj.bullish_scenario if decision_obj else None,
            "bearish_scenario": decision_obj.bearish_scenario if decision_obj else None,
            "key_risks": decision_obj.key_risks if decision_obj else None,
        }

    return portfolio_manager_node
