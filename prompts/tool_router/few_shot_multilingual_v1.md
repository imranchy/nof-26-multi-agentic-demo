# Multilingual few-shot routing examples v1

These examples teach intent and argument extraction. Concrete values vary deliberately. Do not memorize them.

## 1. Traffic prediction -> get_traffic_forecast
- EN: `What traffic do you expect at 21:15?` -> `get_traffic_forecast(time="21:15")`
- IT: `Che traffico prevedi alle 18:10?` -> `get_traffic_forecast(time="18:10")`
- PT: `Que tráfego é esperado às 09:30?` -> `get_traffic_forecast(time="09:30")`
- DE: `Welchen Verkehr erwarten wir um 14:05?` -> `get_traffic_forecast(time="14:05")`
- FR: `Quel trafic est prévu à 16h20 ?` -> `get_traffic_forecast(time="16:20")`
- ES: `¿Qué tráfico se espera a las 20:00?` -> `get_traffic_forecast(time="20:00")`

## 2. SLA risk/state -> get_sla_prediction
- EN: `What is the predicted SLA state at 12:35?` -> `get_sla_prediction(time="12:35")`
- IT: `Qual è il rischio SLA alle 14:05?` -> `get_sla_prediction(time="14:05")`
- PT: `Qual é o estado SLA previsto às 16:20?` -> `get_sla_prediction(time="16:20")`
- DE: `Wie hoch ist das Failure-prone-Risiko um 18:10?` -> `get_sla_prediction(time="18:10")`
- FR: `Quel est l'état SLA prévu à 21h15 ?` -> `get_sla_prediction(time="21:15")`
- ES: `¿Cuál es el riesgo SLA a las 23:10?` -> `get_sla_prediction(time="23:10")`

## 3. Full network state -> get_network_state_at_time
- EN: `Show me the complete network state at 16:20.` -> `get_network_state_at_time(time="16:20")`
- IT: `Mostrami lo stato completo della rete alle 07:45.` -> `get_network_state_at_time(time="07:45")`
- PT: `Mostre o estado completo da rede às 12:35.` -> `get_network_state_at_time(time="12:35")`
- DE: `Zeige den vollständigen Netzzustand um 20:00.` -> `get_network_state_at_time(time="20:00")`
- FR: `Montre-moi l'état complet du réseau à 18h10.` -> `get_network_state_at_time(time="18:10")`
- ES: `Muéstrame el estado completo de la red a las 09:30.` -> `get_network_state_at_time(time="09:30")`

## 4. Balanced policy comparison -> compare_policies_at_time
- EN: `Which allocation policy would you use at 21:15?` -> `compare_policies_at_time(time="21:15", objective="balanced")`
- IT: `Quale politica di allocazione useresti alle 18:10?` -> `compare_policies_at_time(time="18:10", objective="balanced")`
- PT: `Qual política de alocação você usaria às 14:05?` -> `compare_policies_at_time(time="14:05", objective="balanced")`
- DE: `Welche Zuweisungsstrategie würdest du um 16:20 verwenden?` -> `compare_policies_at_time(time="16:20", objective="balanced")`
- FR: `Quelle politique d'allocation choisirais-tu à 12h35 ?` -> `compare_policies_at_time(time="12:35", objective="balanced")`
- ES: `¿Qué política de asignación usarías a las 20:00?` -> `compare_policies_at_time(time="20:00", objective="balanced")`

## 5. Objective-aware policy -> compare_policies_at_time
- EN: `At 20:00, minimize blocking.` -> `compare_policies_at_time(time="20:00", objective="min_blocking")`
- IT: `Alle 14:05, minimizza le riconfigurazioni.` -> `compare_policies_at_time(time="14:05", objective="min_reconfiguration")`
- PT: `Às 18:10, priorize o SLA.` -> `compare_policies_at_time(time="18:10", objective="sla_priority")`
- DE: `Minimiere um 21:15 die Blockierung.` -> `compare_policies_at_time(time="21:15", objective="min_blocking")`
- FR: `À 16h20, privilégie la stabilité et réduisez les reconfigurations.` -> `compare_policies_at_time(time="16:20", objective="min_reconfiguration")`
- ES: `A las 23:10, prioriza estrictamente el SLA.` -> `compare_policies_at_time(time="23:10", objective="sla_priority")`

## 6. Named-policy counterfactual -> simulate_policy_at_time
- EN: `What happens if we use PCA at 21:15?` -> `simulate_policy_at_time(time="21:15", policy="PCA")`
- IT: `Cosa succede se usiamo MBA alle 18:10?` -> `simulate_policy_at_time(time="18:10", policy="MBA")`
- PT: `O que acontece se usarmos SAA às 14:05?` -> `simulate_policy_at_time(time="14:05", policy="SAA")`
- DE: `Wie würde PCA um 16:20 abschneiden?` -> `simulate_policy_at_time(time="16:20", policy="PCA")`
- FR: `Quel serait le résultat avec MBA à 12h35 ?` -> `simulate_policy_at_time(time="12:35", policy="MBA")`
- ES: `¿Qué resultado obtendríamos con SAA a las 20:00?` -> `simulate_policy_at_time(time="20:00", policy="SAA")`

## 7. Hard SC constraints -> analyze_constrained_allocation
- EN: `Keep RAN on 2 SCs at 19:00.` -> `analyze_constrained_allocation(time="19:00", constraints=[{"service":"ran","subcarriers":2}])`
- IT: `Mantieni PON su 1 SC alle 21:15.` -> `analyze_constrained_allocation(time="21:15", constraints=[{"service":"pon","subcarriers":1}])`
- PT: `Reserve 2 SCs para Enterprise às 18:10.` -> `analyze_constrained_allocation(time="18:10", constraints=[{"service":"enterprise","subcarriers":2}])`
- DE: `Reserviere um 14:05 zwei SCs für RAN.` -> `analyze_constrained_allocation(time="14:05", constraints=[{"service":"ran","subcarriers":2}])`
- FR: `Réserve un SC pour PON à 16h20.` -> `analyze_constrained_allocation(time="16:20", constraints=[{"service":"pon","subcarriers":1}])`
- ES: `Mantén Enterprise en 2 SC a las 12:35.` -> `analyze_constrained_allocation(time="12:35", constraints=[{"service":"enterprise","subcarriers":2}])`

## 8. Conversational follow-up -> inherit only referenced state
The following examples assume the immediately preceding setup turn has been executed and stored in authoritative state.
- EN setup: `Keep RAN on 2 SCs at 19:00.` Follow-up: `Also reserve one SC for PON.` -> `analyze_constrained_allocation(constraints=[{"service":"pon","subcarriers":1}])`
- IT setup: `Che traffico prevedi alle 09:00?` Follow-up: `E un'ora dopo?` -> `get_traffic_forecast(relative_time_offset_minutes=60)`
- PT setup: `Que tráfego você espera às 08:15?` Follow-up: `Naquele horário, qual é o risco SLA?` -> `get_sla_prediction()`
- DE setup: `Welche Politik würdest du um 18:30 wählen?` Follow-up: `Nimm stattdessen PCA und zeige das Ergebnis.` -> `simulate_policy_at_time(policy="PCA")`
- FR setup: `Montre l'état du réseau à 18h10.` Follow-up: `Et une heure plus tard ?` -> `get_network_state_at_time(relative_time_offset_minutes=60)`
- ES setup: `Mantén RAN en 2 SC a las 19:00.` Follow-up: `Reserva también un SC para PON.` -> `analyze_constrained_allocation(constraints=[{"service":"pon","subcarriers":1}])`

## 9. Temporal comparison -> compare_network_states
- EN: `Compare the network at 18:10 and 21:15.` -> `compare_network_states(time_a="18:10", time_b="21:15")`
- IT: `Confronta la rete alle 09:30 e alle 14:05.` -> `compare_network_states(time_a="09:30", time_b="14:05")`
- PT: `Compare a rede às 12:35 e às 16:20.` -> `compare_network_states(time_a="12:35", time_b="16:20")`
- DE: `Vergleiche den Netzzustand um 07:45 und 18:10.` -> `compare_network_states(time_a="07:45", time_b="18:10")`
- FR: `Compare le réseau à 16h20 et à 20h00.` -> `compare_network_states(time_a="16:20", time_b="20:00")`
- ES: `Compara la red a las 20:00 y 23:10.` -> `compare_network_states(time_a="20:00", time_b="23:10")`

## 10. Ranked risk/extrema discovery -> find_risk_intervals
- EN: `Find the three highest-risk intervals today.` -> `find_risk_intervals(metric="failure_probability", top_k=3)`
- IT: `Trova i cinque intervalli con il traffico più alto.` -> `find_risk_intervals(metric="total_gbps", top_k=5)`
- PT: `Encontre os três intervalos com maior bloqueio.` -> `find_risk_intervals(metric="blocking", top_k=3)`
- DE: `Finde die zwei Intervalle mit den meisten Rekonfigurationen.` -> `find_risk_intervals(metric="reconfiguration", top_k=2)`
- FR: `Trouve les trois intervalles présentant le risque le plus élevé.` -> `find_risk_intervals(metric="failure_probability", top_k=3)`
- ES: `Encuentra los cinco intervalos con mayor carga.` -> `find_risk_intervals(metric="total_gbps", top_k=5)`

## 11. Continuous range summary -> summarize_time_range
- EN: `Summarize network behavior from 18:00 to 22:00.` -> `summarize_time_range(start_time="18:00", end_time="22:00")`
- IT: `Riassumi il comportamento della rete dalle 19:00 alle 23:00 minimizzando il blocking.` -> `summarize_time_range(start_time="19:00", end_time="23:00", objective="min_blocking")`
- PT: `Resuma a rede das 08:00 às 12:00.` -> `summarize_time_range(start_time="08:00", end_time="12:00")`
- DE: `Fasse das Netzverhalten von 14:00 bis 18:00 zusammen.` -> `summarize_time_range(start_time="14:00", end_time="18:00")`
- FR: `Résume le comportement du réseau de 10h00 à 14h00.` -> `summarize_time_range(start_time="10:00", end_time="14:00")`
- ES: `Resume el comportamiento de la red de 20:00 a 23:30.` -> `summarize_time_range(start_time="20:00", end_time="23:30")`

## 12. Out-of-scope boundaries -> decline_* functions
- EN: `Make me coffee.` -> `decline_out_of_scope()`
- IT: `Che tempo farà domani?` -> `decline_out_of_scope()`
- PT: `Envie um e-mail para a minha equipa.` -> `decline_out_of_scope()`
- DE: `Wie hoch ist der OSNR um 21:15?` -> `decline_physical_layer()`
- FR: `Calcule le BER optique à 18h10.` -> `decline_physical_layer()`
- ES: `Reinicia físicamente el router.` -> `decline_out_of_scope()`
