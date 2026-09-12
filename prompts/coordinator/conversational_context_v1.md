# Conversational context routing v2

Interpret the relationship between the current utterance and supplied structured
memory semantically. Do not rely on literal phrase matching.

Return a context interpretation only; native function calling selects the analytical tool afterward:

- `relation`: `standalone` or `followup`
- `inherit`: zero or more of `intent`, `time`, `policy`, `objective`, `constraints`
- `relative_time.offset_minutes`: only for relative temporal references

The model identifies the meaning; deterministic Python applies inheritance,
precedence, constraint merging, and clock arithmetic.

## Precedence

Explicit information in the current turn overrides inherited state. Inherited
state overrides configured defaults. Do not let prior assistant prose become
authoritative state.

## Relative time

For a relative temporal follow-up, inherit `time` and convert the linguistic
relationship into an integer minute offset. Do not calculate the resulting clock
time yourself.

These utterances have the same semantic interpretation:

- English: `And one hour later?`
- Italian: `E un'ora dopo?`
- Portuguese: `E uma hora depois?`

They should yield an offset of `+60` minutes when they refer to the previous
operator timestamp.

Likewise, semantically equivalent formulations such as `60 minutes after that`,
`60 minuti dopo`, or `60 minutos depois` should map to the same structured
offset when context makes the reference unambiguous.

## Intent changes at inherited time

A follow-up may inherit a timestamp while changing analytical intent.

English: `At that time, what is the SLA risk?`
Italian: `A quell'ora, qual è il rischio SLA?`
Portuguese: `Naquele horário, qual é o risco de SLA?`

These inherit `time` but select the SLA prediction capability rather than
reusing the previous tool.

## Explicit policy override

A policy explicitly named in the current utterance overrides an inherited
policy while other missing context may still be inherited.

English: `Use PCA instead. Show the outcome.`
Italian: `Usa invece PCA. Mostrami il risultato.`
Portuguese: `Use PCA em vez disso. Mostre o resultado.`

If the prior timestamp is unambiguous, inherit only that time and select the
single-policy counterfactual capability with `policy=PCA`.

## Additive SC constraints

When the current utterance semantically adds a new SC constraint to an existing
constraint set, inherit `constraints` and emit only the newly explicit counts in
the current step. Python performs the deterministic merge.

English: `Also reserve one SC for PON.`
Italian: `Riserva anche una SC per PON.`
Portuguese: `Reserve também uma SC para PON.`

## Standalone isolation

An unrelated request with its own complete intent and arguments is standalone,
even when previous memory exists. It must not inherit prior intent, time,
policy, objective, or constraints.
