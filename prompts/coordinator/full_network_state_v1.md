# Full network-state routing

Use `get_network_state_at_time` when the operator asks for:
- network state
- network status
- operator state
- operator snapshot
- complete network state
- current state
- active-policy state
- SC state together with traffic/SLA information
- "what is happening?"
- "what's going on?"

Extract the requested timestamp.

## Policy references

The phrase "active policy" or "active-policy" is NOT a policy identifier.

It means:
use the currently configured simulated active policy.

Do not pass:
- ACTIVE
- ACTIVE-POLICY
- CURRENT
- DEFAULT

as a policy identifier.

Only pass an explicit policy argument when the operator names one of:
- PCA
- MBA
- SAA

Examples:

"Show the active-policy network state at 05:55."
→ get_network_state_at_time
→ timestamp = 05:55
→ no explicit policy argument

"Show the network at 20:00 under MBA."
→ get_network_state_at_time
→ timestamp = 20:00
→ policy = MBA