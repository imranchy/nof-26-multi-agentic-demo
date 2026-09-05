from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.runtime import MultiAgentRuntime


st.set_page_config(
    page_title="Multi-Agent Digital Twin",
    page_icon="📡",
    layout="wide",
)

st.title("Multi-Agent Digital Twin for SLA Management")

st.markdown(
    """
    <style>
    /* Leave room so the final response is not hidden behind the input */
    .stMainBlockContainer {
        padding-bottom: 7rem;
    }

    /* Keep the operator chat input at the bottom of the screen */
    div[data-testid="stChatInput"] {
        position: fixed;
        bottom: 1rem;
        left: 3rem;
        right: 3rem;
        z-index: 1000;
        background: var(--background-color);
    }

    /* Enlarge dashboard metric headings */
    div[data-testid="stMetricLabel"] p {
        font-size: 1.35rem !important;
        font-weight: 600 !important;
    }

    /* Enlarge dashboard metric values */
    div[data-testid="stMetricValue"] {
        font-size: 3rem !important;
    }

    /* Enlarge duration and occurrence captions */
    div[data-testid="stCaptionContainer"] p {
        font-size: 1.15rem !important;
    }

    /* Enlarge persistent navigation labels */
    div[data-testid="stSegmentedControl"] button p {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
    }

    /* Increase user and assistant message text */
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li {
        font-size: 1.2rem !important;
        line-height: 1.65 !important;
    }

    /* Keep the tool-used caption visually secondary */
    div[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] p {
        font-size: 1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Conference mode intentionally exposes one validated configuration.
forecast_mode = "prepared"
use_llm = True
runtime_key = "conference"

if st.session_state.get("runtime_key") != runtime_key:
    with st.spinner("Loading agents and models..."):
        st.session_state.runtime = MultiAgentRuntime(
            forecast_mode=forecast_mode,
            use_llm=use_llm,
        )
        st.session_state.runtime_key = runtime_key
        st.session_state.messages = []

runtime: MultiAgentRuntime = st.session_state.runtime
df = runtime.frame

# Unlike st.tabs(), this value survives Streamlit script reruns.
st.session_state.setdefault("active_view", "Network Overview")

counts = df["predicted_state"].value_counts()

# idxmax returns the earliest interval when several intervals share
# the same maximum Failure-prone score.
peak = df.loc[df["failure_probability"].idxmax()]


def duration(intervals: int) -> str:
    """Convert a number of five-minute intervals into a duration."""
    minutes = intervals * 5
    return f"{minutes // 60} h {minutes % 60:02d} min"


def readable_layout(layout: str) -> str:
    """Convert an internal allocation code into an operator-readable label."""
    layout_names = {
        "EE|P|R": "Enterprise 2 · PON 1 · RAN 1",
        "E|PP|R": "Enterprise 1 · PON 2 · RAN 1",
        "E|P|RR": "Enterprise 1 · PON 1 · RAN 2",
    }
    return layout_names.get(str(layout), str(layout))


TOOL_LABELS = {
    "summarize_day_ahead": "Day-ahead forecast summary",
    "find_next_sla_risk": "Next SLA-risk detection",
    "find_highest_risk": "Highest-risk interval search",
    "find_service_peak": "Service peak analysis",
    "rank_service_intervals": "Service-demand ranking",
    "diagnose_highest_risk": "Highest-risk diagnosis",
    "recommend_subcarrier_allocation": (
        "Subcarrier allocation recommendation"
    ),
    "check_allocation_feasibility": (
        "Allocation feasibility assessment"
    ),
    "compare_service_loads": "Service traffic comparison",
    "get_state_distribution": "SLA-state distribution",
    "validate_forecast": "Forecast guardrail validation",
    "decline_out_of_scope": "Scope validation",
}


normal_count = int(counts.get("normal", 0))
degraded_count = int(counts.get("degraded", 0))
failure_count = int(counts.get("failure_prone", 0))


active_view = st.segmented_control(
    "Application view",
    options=[
        "Network Overview",
        "Operator Assistant",
        "Agent Evidence",
    ],
    key="active_view",
    label_visibility="collapsed",
)


if active_view == "Network Overview":
    # Dashboard summary indicators
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Normal intervals",
        f"{normal_count} ({100 * normal_count / len(df):.1f}%)",
        help="Five-minute intervals classified as normal.",
    )
    c1.caption(duration(normal_count))

    c2.metric(
        "Degraded intervals",
        f"{degraded_count} ({100 * degraded_count / len(df):.1f}%)",
        help=(
            "Five-minute intervals with predicted service "
            "degradation."
        ),
    )
    c2.caption(duration(degraded_count))

    c3.metric(
        "Failure-prone intervals",
        f"{failure_count} ({100 * failure_count / len(df):.1f}%)",
        help=(
            "Five-minute intervals predicted to be at risk "
            "of SLA failure."
        ),
    )
    c3.caption(duration(failure_count))

    c4.metric(
        "Peak failure risk",
        f"{peak.failure_probability:.2f} / 1.00",
        help=(
            "Maximum Random Forest score assigned to the "
            "Failure-prone class. This score is used to rank "
            "forecast intervals and is not guaranteed to be "
            "a calibrated real-world probability."
        ),
    )
    c4.caption(f"Occurs at {peak.time}")

    with st.expander("How to read this Network Overview"):
        st.markdown(
            """
### Headline indicators

Each prepared day-ahead forecast contains **288 five-minute intervals**.

- **Normal intervals** are periods classified as operating normally
- **Degraded intervals** are periods where service degradation is predicted
- **Failure-prone intervals** are periods predicted to be at risk of SLA failure
- The duration below each state equals the number of intervals in that state
  multiplied by five minutes. These periods are not necessarily continuous.
- **Peak failure risk** is the highest Random Forest Failure-prone score during
  the forecast day. The time underneath shows when this maximum occurs

### Traffic forecast chart

The first chart shows the predicted traffic demand throughout the day. These
day-ahead predictions were generated by the trained XGBoost regression models:

- **Enterprise** represents enterprise-service traffic
- **RAN** represents Radio Access Network traffic
- **PON** represents Passive Optical Network traffic
- The x-axis shows the time of day
- The y-axis shows predicted traffic in **Gbps**

This chart helps identify traffic peaks and changes in which service contributes
most to the total network load

### SLA-state chart

Each point represents one five-minute forecast interval assessed by the
Random Forest SLA classifier:

- **Green** means Normal
- **Orange** means Degraded
- **Red** means Failure-prone
- The vertical position represents the model's Failure-prone score from 0 to 1
- Higher points indicate stronger model evidence of Failure-prone operation

The point colour shows the predicted SLA state, while its height shows the
specific score assigned to the Failure-prone class

The dashboard indicators are calculated dynamically from the loaded XGBoost
day-ahead forecasts and the Random Forest classifier outputs. They represent a
prepared demonstration scenario.
"""
        )

    # Day-ahead service traffic forecast
    chart_df = df.melt(
        id_vars=[
            "minute_of_day",
            "time",
        ],
        value_vars=[
            "enterprise_gbps",
            "ran_gbps",
            "pon_gbps",
        ],
        var_name="Service",
        value_name="Traffic (Gbps)",
    )

    service_labels = {
        "enterprise_gbps": "Enterprise",
        "ran_gbps": "RAN",
        "pon_gbps": "PON",
    }

    chart_df["Service"] = chart_df["Service"].replace(
        service_labels
    )

    tickvals = list(range(0, 1440, 120))
    ticktext = [
        f"{minute // 60:02d}:00"
        for minute in tickvals
    ]

    fig = px.line(
        chart_df,
        x="minute_of_day",
        y="Traffic (Gbps)",
        color="Service",
        hover_data={
            "time": True,
            "minute_of_day": False,
        },
        title="Day-ahead multi-service traffic forecast",
    )

    fig.update_layout(
        height=600,
        font=dict(size=17),
        title_font=dict(size=24),
        legend=dict(
            font=dict(size=17),
            title_font=dict(size=18),
        ),
        hoverlabel=dict(font_size=16),
        margin=dict(
            l=40,
            r=40,
            t=80,
            b=40,
        ),
    )

    fig.update_xaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        title="Time",
        tickfont=dict(size=16),
        title_font=dict(size=19),
    )

    fig.update_yaxes(
        title="Traffic (Gbps)",
        tickfont=dict(size=16),
        title_font=dict(size=19),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    # SLA state and Failure-prone score
    state_colors = {
        "normal": "#22c55e",
        "degraded": "#f59e0b",
        "failure_prone": "#ef4444",
    }

    state_labels = {
        "normal": "Normal",
        "degraded": "Degraded",
        "failure_prone": "Failure-prone",
    }

    risk_chart_df = df.copy()

    risk_chart_df["SLA state"] = risk_chart_df[
        "predicted_state"
    ].replace(state_labels)

    display_state_colors = {
        "Normal": state_colors["normal"],
        "Degraded": state_colors["degraded"],
        "Failure-prone": state_colors["failure_prone"],
    }

    risk_fig = px.scatter(
        risk_chart_df,
        x="minute_of_day",
        y="failure_probability",
        color="SLA state",
        color_discrete_map=display_state_colors,
        hover_data={
            "time": True,
            "total_gbps": ":.2f",
            "prediction_confidence": ":.2f",
            "minute_of_day": False,
        },
        labels={
            "failure_probability": "Failure-prone score",
            "total_gbps": "Total traffic (Gbps)",
            "prediction_confidence": "Classifier confidence",
        },
        title="SLA state and Failure-prone score",
    )

    risk_fig.update_traces(
        marker=dict(size=9)
    )

    risk_fig.update_layout(
        height=600,
        font=dict(size=17),
        title_font=dict(size=24),
        legend=dict(
            font=dict(size=17),
            title_font=dict(size=18),
        ),
        hoverlabel=dict(font_size=16),
        margin=dict(
            l=40,
            r=40,
            t=80,
            b=40,
        ),
    )

    risk_fig.update_xaxes(
        tickvals=tickvals,
        ticktext=ticktext,
        title="Time",
        tickfont=dict(size=16),
        title_font=dict(size=19),
    )

    risk_fig.update_yaxes(
        title="Failure-prone score",
        range=[0, 1],
        tickfont=dict(size=16),
        title_font=dict(size=19),
    )

    st.plotly_chart(
        risk_fig,
        use_container_width=True,
    )

    # Compact operator-facing risk and allocation table
    risk_table = df.loc[
        df["predicted_state"] != "normal",
        [
            "time",
            "predicted_state",
            "total_gbps",
            "failure_probability",
            "candidate_layout",
            "estimated_overflow_gbps",
        ],
    ].copy()

    risk_table["predicted_state"] = risk_table[
        "predicted_state"
    ].replace(state_labels)

    risk_table["candidate_layout"] = risk_table[
        "candidate_layout"
    ].map(readable_layout)

    st.dataframe(
        risk_table,
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "time": st.column_config.TextColumn(
                "Time",
                width="small",
                help="Five-minute forecast interval.",
            ),
            "predicted_state": st.column_config.TextColumn(
                "State",
                width="small",
                help="SLA state predicted by the classifier.",
            ),
            "total_gbps": st.column_config.NumberColumn(
                "Total traffic (Gbps)",
                format="%.2f",
                width="small",
                help="Combined Enterprise, RAN and PON traffic.",
            ),
            "failure_probability": st.column_config.NumberColumn(
                "Failure-risk score",
                format="%.2f",
                width="small",
                help=(
                    "Random Forest score for the Failure-prone class. "
                    "It ranks forecast intervals by risk and is not a "
                    "guaranteed real-world probability."
                ),
            ),
            "candidate_layout": st.column_config.TextColumn(
                "Suggested allocation",
                width="large",
                help=(
                    "Suggested distribution of four 25-Gbps "
                    "subcarriers across Enterprise, PON, and "
                    "RAN services."
                ),
            ),
            "estimated_overflow_gbps": (
                st.column_config.NumberColumn(
                    "Overflow (Gbps)",
                    format="%.2f",
                    width="small",
                    help=(
                        "Predicted traffic that the suggested allocation "
                        "cannot accommodate."
                    ),
                )
            ),
        },
    )

    with st.expander("How to interpret this table"):
        st.markdown(
            """
Each row represents one **five-minute forecast interval** classified as
Degraded or Failure-prone.

- **Time** — start of the five-minute interval
- **State** — SLA condition predicted by the Random Forest classifier
- **Total traffic** — combined Enterprise, RAN and PON demand
- **Failure-risk score** — model score from 0 to 1. Higher values indicate
  stronger model evidence of Failure-prone operation; it is not a guaranteed
  real-world probability
- **Suggested allocation** — distribution of the four available 25-Gbps
  subcarriers across Enterprise, PON and RAN
- **Overflow** — predicted demand that cannot be accommodated by the
  suggested allocation

An overflow of **0.00 Gbps** means all predicted service demand can be
accommodated. A value above zero means at least one service exceeds its assigned
capacity, even if another service has unused capacity.

For example, **Enterprise 1 · PON 1 · RAN 2** provides 25 Gbps to Enterprise,
25 Gbps to PON and 50 Gbps to RAN. Large overflow values indicate that external
capacity, traffic offloading or rerouting may be required.

These are advisory model outputs for the prepared demonstration scenario.
Allocation changes require operator approval.
"""
        )



if active_view == "Operator Assistant":
    for message in st.session_state.messages:
        avatar = (
            "🧑‍💻"
            if message["role"] == "user"
            else "🤖"
        )

        with st.chat_message(
            message["role"],
            avatar=avatar,
        ):
            st.markdown(message["content"])

            if (
                message["role"] == "assistant"
                and message.get("tool_name")
            ):
                previous_tool_name = message["tool_name"]
                previous_tool_label = TOOL_LABELS.get(
                    previous_tool_name,
                    previous_tool_name,
                )
                st.caption(
                    f"🔧 Tool used: {previous_tool_label} "
                    f"(`{previous_tool_name}`)"
                )

    query = st.chat_input(
        "Ask about forecasts, SLA risk, causes, confidence, or recovery"
    )

    if query:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": query,
            }
        )

        with st.chat_message(
            "user",
            avatar="🧑‍💻",
        ):
            st.markdown(query)

        with st.chat_message(
            "assistant",
            avatar="🤖",
        ):
            tool_status = st.status(
                "Mistral is selecting a specialist tool...",
                expanded=True,
            )

            try:
                result = runtime.ask(query)

            except RuntimeError as exc:
                error_text = str(exc)

                tool_status.update(
                    label="Tool execution failed",
                    state="error",
                    expanded=True,
                )

                st.error(error_text)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text}
                )

            else:
                tool_name = result.evidence.get(
                    "selected_tool",
                    "unknown_tool",
                )
                tool_arguments = result.evidence.get(
                    "tool_arguments",
                    {},
                )
                tool_label = TOOL_LABELS.get(
                    tool_name,
                    tool_name,
                )

                tool_status.write(
                    f"**Selected tool:** `{tool_name}`"
                )
                if tool_arguments:
                    tool_status.write(
                        f"**Arguments:** `{tool_arguments}`"
                    )
                tool_status.write(
                    "**Guardrail validation:** passed"
                )
                tool_status.update(
                    label=f"Completed: {tool_label}",
                    state="complete",
                    expanded=False,
                )

                st.markdown(result.answer)
                st.caption(
                    f"🔧 Tool used: {tool_label} "
                    f"(`{tool_name}`)"
                )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result.answer,
                        "tool_name": tool_name,
                        "tool_arguments": tool_arguments,
                    }
                )
                st.session_state.last_result = result.to_dict()


if active_view == "Agent Evidence":
    if "last_result" in st.session_state:
        visible_result = dict(
            st.session_state.last_result
        )

        # Keep internal execution traces out of the conference UI.
        visible_result.pop("trace", None)

        st.json(visible_result)

    else:
        st.info(
            "Ask the operator assistant a question to display its "
            "structured plan, validated evidence, and warnings."
        )
