import json
import torch

from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MODEL_NAME = "HuggingFaceTB/SmolLM2-135M-Instruct"
TRAIN_FILE = "fine_tune_train.jsonl"
OUTPUT_DIR = "adapters/smollm2-135m-healthcare-lora"


# --------------------------------------------------
# CPU configuration
# --------------------------------------------------

torch.set_num_threads(6)


# --------------------------------------------------
# Load JSONL dataset
# --------------------------------------------------

records = []

with open(TRAIN_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

print(f"Loaded {len(records)} training examples.")


# --------------------------------------------------
# Convert messages into training text
# --------------------------------------------------

def format_example(example):
    messages = example["messages"]

    text_parts = []

    for message in messages:
        role = message["role"]
        content = message["content"]

        text_parts.append(
            f"{role}: {content}"
        )

    return "\n".join(text_parts)


texts = [format_example(record) for record in records]

dataset = Dataset.from_dict({
    "text": texts
})


# --------------------------------------------------
# Load tokenizer
# --------------------------------------------------

print("Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


# --------------------------------------------------
# Tokenize dataset
# --------------------------------------------------

def tokenize_function(example):
    return tokenizer(
        example["text"],
        truncation=True,
        max_length=128,
        padding=False,
    )


tokenized_dataset = dataset.map(
    tokenize_function,
    remove_columns=["text"],
)

print("Dataset tokenization complete.")


# --------------------------------------------------
# Load base model
# --------------------------------------------------

print("Loading base model...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME
)

model.config.pad_token_id = tokenizer.pad_token_id
model.config.use_cache = False


# --------------------------------------------------
# Configure LoRA
# --------------------------------------------------

lora_config = LoraConfig(
    r=4,
    lora_alpha=8,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=[
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
    ],
)


# --------------------------------------------------
# Apply LoRA
# --------------------------------------------------

model = get_peft_model(
    model,
    lora_config
)

model.print_trainable_parameters()


# --------------------------------------------------
# Training configuration
# --------------------------------------------------

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,

    # Fast CPU-friendly training
    num_train_epochs=1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=1,

    learning_rate=2e-4,

    logging_steps=1,

    save_strategy="epoch",

    report_to="none",

    # CPU only
    fp16=False,
    bf16=False,

    # Windows
    dataloader_num_workers=0,

    eval_strategy="no",

    save_total_limit=1,
)


# --------------------------------------------------
# Data collator
# --------------------------------------------------

data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)


# --------------------------------------------------
# Trainer
# --------------------------------------------------

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=data_collator,
)


# --------------------------------------------------
# Start training
# --------------------------------------------------

print()
print("========================================")
print("Starting LoRA fine-tuning...")
print("Model: SmolLM2-135M-Instruct")
print("Examples: 25")
print("Epochs: 1")
print("Max length: 128")
print("========================================")
print()

trainer.train()


# --------------------------------------------------
# Save adapter
# --------------------------------------------------

print()
print("Saving LoRA adapter...")

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print()
print("========================================")
print("Fine-tuning completed successfully!")
print(f"Adapter saved to: {OUTPUT_DIR}")
print("========================================")