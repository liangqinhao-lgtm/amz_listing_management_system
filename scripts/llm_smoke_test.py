import os
import time
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from infrastructure.llm import get_llm_service, LLMRequest

def main():
    os.environ.setdefault("LLM_SERVICE_MODE", "direct")
    svc = get_llm_service()
    system_prompt = "You are a helpful assistant."
    user_prompt = "Say OK"
    req = LLMRequest(
        task_type="smoke_test",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=False,
        temperature=0.1
    )
    t0 = time.perf_counter()
    resp = svc.generate(req)
    dur = time.perf_counter() - t0
    payload = {
        "provider": resp.provider,
        "model": resp.model,
        "duration_seconds": round(dur, 3),
        "usage": resp.usage,
        "content_preview": str(resp.content)[:200]
    }
    print(json.dumps(payload, ensure_ascii=False))

if __name__ == "__main__":
    main()
