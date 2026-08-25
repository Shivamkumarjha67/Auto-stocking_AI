import json
import math
import re
import torch
from typing import List, Optional, Literal
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

class LineItem(BaseModel):
    sku: str
    quantity: int
    unit_price: float
    delivery_tier: str

class PurchaseOrder(BaseModel):
    vendor_id: str
    line_items: List[LineItem]
    total_amount: float
    status: str

class AgentOutput(BaseModel):
    action: Literal["accept_and_order", "negotiate_counter", "reject_and_escalate", "clarify_ambiguity"]
    reasoning: str
    draft_response: str
    purchase_order: Optional[PurchaseOrder] = None

def extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    return brace_match.group(0) if brace_match else text

def evaluate_model(model_path: str = "models/merged_16bit", val_file: str = "data/finetune/val.jsonl"):
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="auto"
    )

    with open(val_file, "r", encoding="utf-8") as f:
        val_data = [json.loads(line) for line in f if line.strip()]

    schema_success, math_success = 0, 0

    with torch.inference_mode():
        for sample in val_data:
            messages = sample["messages"][:2]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )

            prompt_len = inputs["input_ids"].shape[1]
            raw_response = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True)

            try:
                cleaned_json = extract_json(raw_response)
                parsed = AgentOutput.model_validate_json(cleaned_json)
                schema_success += 1

                if parsed.purchase_order and parsed.purchase_order.line_items:
                    calc_sum = sum(i.quantity * i.unit_price for i in parsed.purchase_order.line_items)
                    if math.isclose(parsed.purchase_order.total_amount, calc_sum, rel_tol=1e-3, abs_tol=0.01):
                        math_success += 1
                else:
                    math_success += 1
            except Exception:
                pass

    total = len(val_data)
    if total > 0:
        print(f"Validation on {total} samples:")
        print(f"Schema Compliance: {schema_success / total * 100:.1f}%")
        print(f"Math Precision: {math_success / total * 100:.1f}%")

if __name__ == "__main__":
    evaluate_model()