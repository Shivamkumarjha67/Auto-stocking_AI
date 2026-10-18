"""
AutoStock-AI: Google Colab + ngrok Model Serving Script
======================================================
Run this script inside your Google Colab notebook after fine-tuning with Unsloth.
It launches a high-throughput, OpenAI-compatible FastAPI server and exposes it
securely over the internet via an ngrok tunnel.

Usage in Google Colab:
1. !pip install fastapi uvicorn pyngrok unsloth
2. Paste your ngrok auth token below: ngrok.set_auth_token("YOUR_NGROK_TOKEN")
3. Run: python serve_colab.py
4. Copy the public https://xxxx.ngrok-free.app URL.
5. In AutoStock-AI local .env:
   USE_LOCAL_MODEL=true
   LOCAL_LLM_URL=https://xxxx.ngrok-free.app/v1
"""

import os
import re
import json
import torch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from pyngrok import ngrok
from unsloth import FastLanguageModel

# 1. Configuration
MODEL_PATH = "models/merged_16bit"  # Path to exported merged weights or adapter
PORT = 8000
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN", "")

app = FastAPI(title="AutoStock-AI LLaMA 3.2 Inference Server")

print("[1/3] Loading fine-tuned model into VRAM...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_PATH if os.path.exists(MODEL_PATH) else "models/adapters",
    max_seq_length=2048,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)
print("[2/3] Model ready for high-speed inference.")

def extract_json_block(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    return brace.group(0) if brace else text

@app.get("/health")
def health():
    return {"status": "ok", "model": "procurement-llama-3.2-3b-finetuned"}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 512)
    temperature = data.get("temperature", 0.0)

    # Format using LLaMA chat template
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=(temperature > 0.0),
            temperature=max(temperature, 1e-4),
            pad_token_id=tokenizer.eos_token_id
        )

    prompt_len = inputs["input_ids"].shape[1]
    raw_response = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True).strip()

    # Clean to pure JSON
    clean_json = extract_json_block(raw_response)

    return JSONResponse({
        "id": "chatcmpl-autostock-colab",
        "object": "chat.completion",
        "model": "procurement-llama-finetuned",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": clean_json
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": prompt_len,
            "completion_tokens": len(outputs[0]) - prompt_len,
            "total_tokens": len(outputs[0])
        }
    })

if __name__ == "__main__":
    if NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    public_url = ngrok.connect(PORT)
    print(f"\n=======================================================")
    print(f" 🚀 AutoStock-AI Colab Endpoint Live!")
    print(f" Public URL: {public_url}")
    print(f" Put this in your local AutoStock-AI .env file:")
    print(f" USE_LOCAL_MODEL=true")
    print(f" LOCAL_LLM_URL={public_url}/v1")
    print(f"=======================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

