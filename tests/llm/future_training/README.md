# Future LLM fine-tuning area

No fine-tuning is used in NoF v1.

If a later experiment fine-tunes Mistral, keep the base model unchanged and store LoRA/QLoRA training data and adapter metadata here (or in a dedicated external model directory). Do **not** train on `operator_10_categories_v1.json`; that 100-query benchmark is the held-out evaluation set and must remain uncontaminated for before/after comparisons.

A future training dataset should contain separate natural-language operator utterances/conversation context mapped to structured tool plans. Network calculations remain in deterministic tools and must not become LLM training targets.
