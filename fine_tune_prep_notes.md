# Day 14 - Fine-Tuning Preparation Notes

## Goal

Prepare a small, high-quality dataset for a healthcare coverage chatbot.
The dataset focuses on consistent tone, clear insurance terminology,
appropriate disclaimers, and avoiding unsupported plan-specific claims.

## Fine-Tuning vs Prompting vs RAG

### Prompting

Use prompting when the desired behavior can be controlled by instructions.

Examples:
- Define insurance terms in plain language.
- Use an empathetic tone.
- Include a short disclaimer.
- Follow a response structure.

Prompting is usually the first approach because it is fast and inexpensive.

### RAG

Use Retrieval-Augmented Generation when the chatbot needs external,
changing, or plan-specific factual information.

Examples:
- Current plan benefits.
- Specific deductibles and copays.
- Provider network information.
- Current formularies.
- Plan exclusions.
- Member-specific documents.

Fine-tuning should NOT be used as the primary solution for storing
frequently changing factual information.

### Fine-Tuning

Use fine-tuning when the model repeatedly fails to follow a desired
behavior even after good prompting.

Good use cases:
- Consistent empathetic tone.
- Consistent terminology.
- Consistent disclaimer behavior.
- Stable answer structure.
- Domain-specific communication style.

Poor use cases:
- Adding current plan facts.
- Storing frequently changing insurance information.
- Replacing a retrieval system for plan documents.

## Full Fine-Tuning vs PEFT

Full fine-tuning updates many or all model parameters and can require
significant compute and memory.

Parameter-Efficient Fine-Tuning (PEFT) updates a smaller portion of
the model.

LoRA (Low-Rank Adaptation) is a common PEFT technique that trains
small adapter parameters instead of updating the entire model.

QLoRA combines quantization with LoRA to reduce memory requirements.

## Recurring Issues Fine-Tuning Can Fix

1. Inconsistent empathetic tone.
2. Forgetting to define insurance terminology in plain language.
3. Inconsistent use of coverage disclaimers.
4. Inconsistent response structure.

## Problems Fine-Tuning Cannot Reliably Fix

1. Missing plan documents.
2. Incorrect or outdated provider-network information.
3. Current deductible/copay values that were never supplied to the model.
4. Retrieval failures from a knowledge base.
5. Frequently changing plan-specific facts.

## Dataset Quality Bar

The dataset should:
- Use the target messages schema.
- Contain realistic user questions.
- Demonstrate the desired tone.
- Demonstrate correct terminology.
- Avoid invented plan-specific facts.
- Include appropriate disclaimers.
- Contain diverse coverage questions.

## Dataset Split

Total curated examples: 30

Training examples: 25

Held-out test examples: 5

The five held-out examples must NOT be used for training.
They are reserved for Day 15 comparison/evaluation.
