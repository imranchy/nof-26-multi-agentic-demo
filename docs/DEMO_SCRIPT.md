# Suggested Live Demo

The UI intentionally contains no scripted demo buttons. Type natural operator questions so that Mistral's semantic routing and follow-up handling are visible.

A compact sequence can be:

```text
Find the highest-risk interval today and tell me what the RF predicts there.
Which policy is preferable at that time?
What happens if I reserve two subcarriers for RAN?
Compare this interval with 18:10.
Why should I trust that recommendation?
```

Other useful free-form examples:

```text
Give me both the XGBoost forecast and RF classification at 21:15.
Which policy has the absolute lowest blocking at 21:15?
Which policy causes the fewest reconfigurations?
What changed between 18:10 and 21:15?
Summarize the network from 18:00 to 22:00.
Why did the recommended policy change between these two times?
How does the recommended policy change across the day?
```

Do not use physical-layer/fiber-cut queries as a claimed capability. If asked, the system should explicitly state that the required telemetry/model is unavailable.
