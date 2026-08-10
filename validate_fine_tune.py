import json
from pathlib import Path


FILES = [
    "fine_tune_dataset.jsonl",
    "fine_tune_train.jsonl",
    "fine_tune_test.jsonl",
]


def validate_file(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"{filename} does not exist")

    count = 0

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{filename} line {line_number}: invalid JSON: {exc}"
                )

            # Check top-level schema
            if "messages" not in record:
                raise ValueError(
                    f"{filename} line {line_number}: missing 'messages'"
                )

            if not isinstance(record["messages"], list):
                raise ValueError(
                    f"{filename} line {line_number}: "
                    "'messages' must be a list"
                )

            # Check message structure
            for message in record["messages"]:
                if not isinstance(message, dict):
                    raise ValueError(
                        f"{filename} line {line_number}: "
                        "message must be an object"
                    )

                if "role" not in message or "content" not in message:
                    raise ValueError(
                        f"{filename} line {line_number}: "
                        "message needs 'role' and 'content'"
                    )

                if message["role"] not in {
                    "system",
                    "user",
                    "assistant",
                }:
                    raise ValueError(
                        f"{filename} line {line_number}: "
                        f"invalid role '{message['role']}'"
                    )

                if not isinstance(message["content"], str):
                    raise ValueError(
                        f"{filename} line {line_number}: "
                        "'content' must be a string"
                    )

            count += 1

    print(f"{filename}: VALID - {count} examples")
    return count


dataset_count = validate_file("fine_tune_dataset.jsonl")
train_count = validate_file("fine_tune_train.jsonl")
test_count = validate_file("fine_tune_test.jsonl")


# Day 14 requirements
assert dataset_count == 30, (
    f"Expected 30 dataset examples, got {dataset_count}"
)

assert train_count == 25, (
    f"Expected 25 training examples, got {train_count}"
)

assert test_count == 5, (
    f"Expected 5 test examples, got {test_count}"
)

assert train_count + test_count == dataset_count, (
    "Train + test counts do not equal full dataset count"
)


print()
print("All JSONL files passed validation.")
print("Day 14 dataset requirements are satisfied.")