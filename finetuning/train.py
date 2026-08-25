import os
import torch
from datasets import load_dataset
from trl import SFTConfig, SFTTrainer
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, train_on_responses_only

def main():
    max_seq_length = 2048
    model_name = "meta-llama/Llama-3.2-3B-Instruct"

    # 1. Load Base Model in 4-bit
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        load_in_4bit=True,
    )

    tokenizer = get_chat_template(
        tokenizer,
        chat_template="llama-3.1",
    )

    # 2. Add LoRA Adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # 3. Load Datasets
    train_ds = load_dataset("json", data_files="data/finetune/train.jsonl", split="train")
    eval_ds = load_dataset("json", data_files="data/finetune/val.jsonl", split="train")

    def format_prompts(batch):
        texts = [
            tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False)
            for convo in batch["messages"]
        ]
        return {"text": texts}

    train_ds = train_ds.map(format_prompts, batched=True)
    eval_ds = eval_ds.map(format_prompts, batched=True)

    # 4. Training Arguments
    training_args = SFTConfig(
        output_dir="./procurement_checkpoints",
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_ratio=0.05,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=5,
        dataset_text_field="text",
        max_length=max_seq_length,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        args=training_args,
    )

    # Train only on assistant outputs
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|start_header_id|>user<|end_header_id|>\n\n",
        response_part="<|start_header_id|>assistant<|end_header_id|>\n\n",
    )

    trainer.train()

    # 5. Export weights
    os.makedirs("models/adapters", exist_ok=True)
    os.makedirs("models/merged_16bit", exist_ok=True)

    model.save_pretrained("models/adapters")
    tokenizer.save_pretrained("models/adapters")

    model.save_pretrained_merged(
        "models/merged_16bit",
        tokenizer,
        save_method="merged_16bit",
    )
    print("Training finished. Adapter and merged 16-bit weights exported successfully.")

if __name__ == "__main__":
    main()