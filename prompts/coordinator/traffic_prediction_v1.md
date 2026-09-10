# Traffic prediction routing v1

Use `get_traffic_forecast` for requests about expected, predicted, forecast, anticipated, upcoming, offered, or per-service traffic at a timestamp.

Examples include:
- "What traffic do you expect at 21:15?"
- "What demand do you forecast for 14:05?"
- "How busy do we expect the services to be at 12:35?"

Extract the requested timestamp.

A traffic request alone does not request SLA risk, blocking, congestion, SC allocation, or policy advice. Do not add those capabilities unless explicitly requested.
