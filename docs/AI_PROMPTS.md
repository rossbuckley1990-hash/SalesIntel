# SalesIntel AI Prompt Standard

SalesIntel AI output must read like a senior commercial analyst briefing Mitie Fire & Security leadership. It must not read like generic AI prose.

## Central Contract

All backend AI prompt surfaces use `backend/app/intelligence/prompt_contract.py`.

The shared contract defines:

- The active prompt version.
- The preferred commercial vocabulary.
- The required answer frame.
- The rules for known, inferred, estimated and unknown information.
- The requirement to return strict JSON only.

Prompt changes should update the central contract unless the rule is specific to one endpoint.

## Required Answer Frame

Every AI result should answer:

1. What is this?
2. Why does it matter?
3. What is the commercial value?
4. What is the risk?
5. What should Mitie do next?
6. What is known vs inferred vs estimated?
7. What evidence supports this?

## Preferred Language

Use commercially sharp terms where relevant:

- executive attention required
- margin protection required
- self-delivery capture opportunity
- strategic must-win
- commercial review recommended
- mobilisation risk
- forecast confidence
- buyer driver
- competitor threat
- next best action
- asset data risk
- scope confirmation required

Do not force these phrases when unsupported. Evidence and confidence must still govern the output.

## Unknowns

Unknowns are not failures. They are decision-support signals.

When a fact is not evidenced, SalesIntel should say:

- what is unknown
- why it is unknown
- whether it needs user confirmation
- the next best action to resolve it

The AI must not convert unknowns into false certainty.

## Endpoint Expectations

### Opportunity Analysis

Output should identify commercial value, margin pressure, mobilisation risk, buyer drivers, competitor threat and next best action.

### Executive Summary

Output should be suitable for MD, FD and GSD review. It should cover pipeline position, weighted pipeline, margin position, urgent deadlines, strategic must-wins, Red risks, finance attention items, self-delivery capture opportunities and leadership actions for this week.

### Internet Intelligence

Output must use public, source-attributed information only. It must not imply private system access. If web evidence does not prove buyer intent, SalesIntel should state the limitation and recommend source confirmation.

### Standing-Start Opportunity Research

Output must produce field-level intelligence for every core opportunity field. Each value must be labelled known, inferred, estimated or unknown. Revenue and margin estimates must include rationale.

## Validation

Tests in `backend/tests/test_ai_prompt_contract.py` verify that all AI prompt surfaces use the central commercial contract and that structured JSON schemas constrain executive-facing text length.
