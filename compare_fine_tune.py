import json
import os

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MODEL_NAME = "HuggingFaceTB/SmolLM2-135M-Instruct"

ADAPTER_DIR = "adapters/smollm2-135m-healthcare-lora"

TEST_FILE = "fine_tune_test.jsonl"

OUTPUT_FILE = "fine_tune_comparison.md"


# --------------------------------------------------
# CPU configuration
# --------------------------------------------------

torch.set_num_threads(6)

DEVICE = "cpu"


# --------------------------------------------------
# Load test dataset
# --------------------------------------------------

records = []

with open(TEST_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

print(f"Loaded {len(records)} held-out questions.")


# --------------------------------------------------
# Extract question + expected answer
# --------------------------------------------------

test_cases = []

for record in records:
    messages = record["messages"]

    question = ""
    expected_answer = ""

    for message in messages:
        if message["role"] == "user":
            question = message["content"]

        elif message["role"] == "assistant":
            expected_answer = message["content"]

    test_cases.append(
        {
            "question": question,
            "expected": expected_answer,
        }
    )


# --------------------------------------------------
# Load tokenizer
# --------------------------------------------------

print("\nLoading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


# --------------------------------------------------
# Load BASE model
# --------------------------------------------------

print("Loading base model...")

base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME
)

base_model.to(DEVICE)
base_model.eval()


# --------------------------------------------------
# Load FINE-TUNED model
# --------------------------------------------------

print("Loading fine-tuned LoRA adapter...")

fine_tuned_base = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME
)

fine_tuned_model = PeftModel.from_pretrained(
    fine_tuned_base,
    ADAPTER_DIR
)

fine_tuned_model.to(DEVICE)
fine_tuned_model.eval()


# --------------------------------------------------
# Generate answer
# --------------------------------------------------

def generate_answer(model, question):
    prompt = (
        "You are a healthcare coverage assistant. "
        "Answer clearly, empathetically, and conservatively. "
        "Do not invent plan-specific facts. "
        "If plan-specific information is unavailable, "
        "tell the user to check their plan documents or "
        "contact the insurer. "
        "Use a brief disclaimer when discussing coverage or costs.\n\n"
        f"User: {question}\n"
        "Assistant:"
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=256,
    )

    inputs = {
        key: value.to(DEVICE)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]

    answer = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    ).strip()

    return answer


# --------------------------------------------------
# Simple evaluation helpers
# --------------------------------------------------

def score_tone(answer):
    answer_lower = answer.lower()

    positive = [
        "you can",
        "generally",
        "usually",
        "may",
        "depends",
        "check your plan",
        "contact your insurer",
    ]

    return min(
        5,
        1 + sum(term in answer_lower for term in positive)
    )


def score_disclaimer(answer):
    answer_lower = answer.lower()

    terms = [
        "check your plan",
        "plan documents",
        "contact your insurer",
        "depends on your specific plan",
        "coverage depends",
        "cannot guarantee",
    ]

    matches = sum(term in answer_lower for term in terms)

    if matches >= 2:
        return 5
    elif matches == 1:
        return 4
    else:
        return 2


def score_terminology(answer):
    answer_lower = answer.lower()

    terms = [
        "deductible",
        "copay",
        "coinsurance",
        "referral",
        "out-of-network",
        "allowed amount",
        "coverage",
        "eligibility",
        "authorization",
    ]

    matches = sum(term in answer_lower for term in terms)

    if matches >= 2:
        return 5
    elif matches == 1:
        return 4
    else:
        return 3


def score_correctness(answer, expected):
    answer_words = set(
        answer.lower().replace(".", "").replace(",", "").split()
    )

    expected_words = set(
        expected.lower().replace(".", "").replace(",", "").split()
    )

    if not answer_words:
        return 1

    overlap = len(answer_words & expected_words) / len(expected_words)

    if overlap >= 0.35:
        return 5
    elif overlap >= 0.20:
        return 4
    elif overlap >= 0.10:
        return 3
    else:
        return 2


# --------------------------------------------------
# Run comparison
# --------------------------------------------------

results = []

print("\nRunning base vs fine-tuned comparison...\n")

for index, case in enumerate(test_cases, start=1):

    question = case["question"]
    expected = case["expected"]

    print(f"Question {index}/5")
    print(question)

    print("Generating base answer...")
    base_answer = generate_answer(
        base_model,
        question
    )

    print("Generating fine-tuned answer...")
    fine_tuned_answer = generate_answer(
        fine_tuned_model,
        question
    )

    results.append(
        {
            "question": question,
            "expected": expected,
            "base": base_answer,
            "fine_tuned": fine_tuned_answer,
        }
    )

    print("Done.\n")


# --------------------------------------------------
# Create Markdown comparison
# --------------------------------------------------

markdown = []

markdown.append("# Day 15 — Fine-Tuning Comparison")
markdown.append("")
markdown.append(
    "Base model vs LoRA fine-tuned model evaluation "
    "on 5 held-out questions from Day 14."
)
markdown.append("")

markdown.append("## Models")
markdown.append("")
markdown.append(
    "- Base: `HuggingFaceTB/SmolLM2-135M-Instruct`"
)
markdown.append(
    "- Fine-tuned: Base model + "
    "`smollm2-135m-healthcare-lora`"
)
markdown.append("- Training method: LoRA")
markdown.append("- Training examples: 25")
markdown.append("- Held-out test examples: 5")
markdown.append("")


# --------------------------------------------------
# Individual comparisons
# --------------------------------------------------

total_base = {
    "tone": 0,
    "correctness": 0,
    "disclaimer": 0,
    "terminology": 0,
}

total_ft = {
    "tone": 0,
    "correctness": 0,
    "disclaimer": 0,
    "terminology": 0,
}


for index, result in enumerate(results, start=1):

    base_tone = score_tone(result["base"])
    base_correctness = score_correctness(
        result["base"],
        result["expected"]
    )
    base_disclaimer = score_disclaimer(
        result["base"]
    )
    base_terminology = score_terminology(
        result["base"]
    )

    ft_tone = score_tone(result["fine_tuned"])
    ft_correctness = score_correctness(
        result["fine_tuned"],
        result["expected"]
    )
    ft_disclaimer = score_disclaimer(
        result["fine_tuned"]
    )
    ft_terminology = score_terminology(
        result["fine_tuned"]
    )

    total_base["tone"] += base_tone
    total_base["correctness"] += base_correctness
    total_base["disclaimer"] += base_disclaimer
    total_base["terminology"] += base_terminology

    total_ft["tone"] += ft_tone
    total_ft["correctness"] += ft_correctness
    total_ft["disclaimer"] += ft_disclaimer
    total_ft["terminology"] += ft_terminology

    markdown.append(f"## Question {index}")
    markdown.append("")
    markdown.append(f"**Question:** {result['question']}")
    markdown.append("")

    markdown.append("### Expected answer")
    markdown.append("")
    markdown.append(result["expected"])
    markdown.append("")

    markdown.append("### Base model")
    markdown.append("")
    markdown.append(result["base"] or "(No answer generated.)")
    markdown.append("")

    markdown.append("### Fine-tuned model")
    markdown.append("")
    markdown.append(
        result["fine_tuned"] or "(No answer generated.)"
    )
    markdown.append("")

    markdown.append("### Scores")
    markdown.append("")
    markdown.append(
        "| Metric | Base | Fine-tuned |"
    )
    markdown.append(
        "|---|---:|---:|"
    )
    markdown.append(
        f"| Tone | {base_tone}/5 | {ft_tone}/5 |"
    )
    markdown.append(
        f"| Correctness | {base_correctness}/5 | "
        f"{ft_correctness}/5 |"
    )
    markdown.append(
        f"| Disclaimer usage | {base_disclaimer}/5 | "
        f"{ft_disclaimer}/5 |"
    )
    markdown.append(
        f"| Terminology clarity | {base_terminology}/5 | "
        f"{ft_terminology}/5 |"
    )
    markdown.append("")


# --------------------------------------------------
# Overall scores
# --------------------------------------------------

markdown.append("## Overall Results")
markdown.append("")

markdown.append(
    "| Metric | Base | Fine-tuned |"
)
markdown.append(
    "|---|---:|---:|"
)

markdown.append(
    f"| Tone | {total_base['tone']}/25 | "
    f"{total_ft['tone']}/25 |"
)

markdown.append(
    f"| Correctness | {total_base['correctness']}/25 | "
    f"{total_ft['correctness']}/25 |"
)

markdown.append(
    f"| Disclaimer usage | {total_base['disclaimer']}/25 | "
    f"{total_ft['disclaimer']}/25 |"
)

markdown.append(
    f"| Terminology clarity | "
    f"{total_base['terminology']}/25 | "
    f"{total_ft['terminology']}/25 |"
)

markdown.append("")


# --------------------------------------------------
# Conclusion
# --------------------------------------------------

base_total = sum(total_base.values())
ft_total = sum(total_ft.values())

markdown.append("## Conclusion")
markdown.append("")

if ft_total > base_total:
    markdown.append(
        "The LoRA fine-tuned model performed better overall on "
        "the five held-out questions. The comparison suggests "
        "that fine-tuning improved consistency with the desired "
        "healthcare coverage assistant behavior."
    )
elif ft_total < base_total:
    markdown.append(
        "The base model performed better overall on the five "
        "held-out questions. This suggests that additional "
        "prompt engineering or retrieval work may provide more "
        "benefit than the current small LoRA fine-tuning run."
    )
else:
    markdown.append(
        "The base and fine-tuned models produced similar overall "
        "scores on the five held-out questions. With this small "
        "dataset and one training epoch, the benefit of fine-tuning "
        "was limited. More prompt or retrieval tuning may be "
        "worth considering."
    )

markdown.append("")
markdown.append(
    "Scores use a simple comparison rubric based on the expected "
    "answers and the required behavioral criteria. They are intended "
    "as a lightweight evaluation for this exercise."
)


# --------------------------------------------------
# Save comparison
# --------------------------------------------------

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:
    f.write("\n".join(markdown))


print()
print("========================================")
print("Comparison completed successfully!")
print(f"Saved to: {OUTPUT_FILE}")
print("========================================")