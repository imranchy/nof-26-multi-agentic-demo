from __future__ import annotations

import plotly.express as px
import streamlit as st

from app.runtime import MultiAgentRuntime


st.set_page_config(page_title="NoF 2026 Multi-Agent Digital Twin", page_icon="🛰️", layout="wide")


@st.cache_resource
def get_runtime() -> MultiAgentRuntime:
    return MultiAgentRuntime(forecast_mode="live", use_llm=True)


runtime = get_runtime()
frame = runtime.frame
highest_risk = frame.loc[frame.failure_probability.idxmax()]

st.title("Multi-Agent Digital Twin for SLA Management")
st.caption("NoF 2026 demonstrator · predictive network state + deterministic PCA/MBA/SAA control analysis + Mistral semantic orchestration")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Simulated active policy", runtime.tools.controller["active_policy"])
c2.metric("SC capacity", f"{runtime.tools.network['subcarrier_capacity_gbps']} Gbps")
c3.metric("SCs per access node", str(runtime.tools.network["subcarriers_per_leaf"]))
c4.metric("Highest-risk interval", str(highest_risk.time))

st.subheader("Network digital twin")
left, right = st.columns(2)

with left:
    traffic = frame[["time", "enterprise_gbps", "ran_gbps", "pon_gbps"]].copy()
    traffic = traffic.melt(id_vars="time", var_name="Service", value_name="Gbps")
    traffic["Service"] = traffic["Service"].map({
        "enterprise_gbps": "Enterprise", "ran_gbps": "RAN", "pon_gbps": "PON"
    })
    fig = px.line(traffic, x="time", y="Gbps", color="Service", title="Day-ahead traffic forecast")
    fig.update_layout(height=330, xaxis_title="Time", legend_title="Service")
    fig.update_xaxes(nticks=10)
    st.plotly_chart(fig, use_container_width=True)

with right:
    risk = frame[["time", "failure_probability", "predicted_state"]].copy()
    risk["Failure-prone risk (%)"] = 100 * risk["failure_probability"]
    fig = px.line(risk, x="time", y="Failure-prone risk (%)", title="Predicted SLA failure risk over time")
    fig.update_layout(height=330, xaxis_title="Time", yaxis_range=[0, 100])
    fig.update_xaxes(nticks=10)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Risk is the predicted probability of the simulator-derived Failure-prone SLA state; it is not a generic model-confidence score.")

st.divider()
head1, head2, head3 = st.columns([5, 1, 1])
with head1:
    st.subheader("Operator assistant")
    st.caption("Ask naturally about traffic, SLA risk, network state, policy trade-offs, SC constraints, timestamps, or time ranges.")
with head2:
    show_trace = st.toggle("Technical trace", value=False)
with head3:
    if st.button("Reset", use_container_width=True):
        runtime.reset()
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if show_trace and message.get("audit"):
            with st.expander("Technical trace"):
                st.json(message["audit"])

query = st.chat_input("Ask the digital twin")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant"):
        try:
            response = runtime.ask(query)
            st.markdown(response.answer)
            audit = {
                "prompt_versions": {
                    "tool_router": "v1-direct-tools",
                    "explainer": "v1",
                },
                "tool_plan": [{"tool": step.tool_name, "arguments": step.arguments} for step in response.plan.steps],
                "routing_audit": response.routing_audit,
                "grounding_passed": response.grounding_passed,
                "grounding_issues": response.grounding_issues,
                "evidence": response.evidence,
                "trace": [event.__dict__ for event in response.trace],
            }
            if show_trace:
                with st.expander("Technical trace"):
                    st.json(audit)
            st.session_state.messages.append({"role": "assistant", "content": response.answer, "audit": audit})
        except Exception as exc:
            text = f"The demonstrator could not complete the request: {exc}"
            st.error(text)
            st.session_state.messages.append({"role": "assistant", "content": text})

st.caption("v1 scope: predicted traffic/SLA risk, temporal analysis, PCA/MBA/SAA policy replay, and operator SC constraints. Physical-layer analysis, GNPy, RAG, and network actuation are intentionally out of scope.")
