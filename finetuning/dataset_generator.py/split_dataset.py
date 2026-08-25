import json
import random
from pathlib import Path

def split_procurement_dataset(
    input_file: str = "data/raw/procurement_clean_unique.jsonl",
    output_dir: str = "data/finetune",
    train_ratio: float = 0.9,
    seed: int = 42
):
    random.seed(seed)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    random.shuffle(lines)
    split_idx = int(len(lines) * train_ratio)
    
    train_data = lines[:split_idx]
    val_data = lines[split_idx:]

    with open(output_path / "train.jsonl", "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item) + "\n")

    with open(output_path / "val.jsonl", "w", encoding="utf-8") as f:
        for item in val_data:
            f.write(json.dumps(item) + "\n")

    print(f"Split complete: {len(train_data)} train samples, {len(val_data)} validation samples.")

if __name__ == "__main__":
    split_procurement_dataset()