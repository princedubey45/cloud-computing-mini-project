import os
import sys
import json
import urllib.request
import urllib.error

SHARD_INDEX = int(os.environ.get("SHARD_INDEX", 0))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", 2))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
TEACHER_MODEL = os.environ.get("TEACHER_MODEL", "phi3.5")
INPUT_FILE = os.environ.get("INPUT_FILE", "data/commands_pool.jsonl")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "datasets/teacher")
PROMPT_FILE = os.environ.get("PROMPT_FILE", "prompts/teacher_prompt.txt")


def load_prompt():
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "Extract 4-key JSON with intent, date, time, place."


def query_ollama(system_prompt, user_command):
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": TEACHER_MODEL,
        "prompt": f"{system_prompt}\n\nCommand: {user_command}\nJSON:",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "seed": 42
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        return f'{{"intent": "unknown", "date": null, "time": null, "place": null}}'


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(OUTPUT_DIR, f"shard-{SHARD_INDEX}.jsonl")
    system_prompt = load_prompt()

    print(f"[Worker {SHARD_INDEX}/{SHARD_COUNT}] Reading {INPUT_FILE} -> {out_file}")

    with open(INPUT_FILE, "r", encoding="utf-8") as in_f, open(out_file, "w", encoding="utf-8") as out_f:
        for line_num, line in enumerate(in_f):
            line = line.strip()
            if not line:
                continue
            if line_num % SHARD_COUNT == SHARD_INDEX:
                rec = json.loads(line)
                cmd_id = rec.get("id")
                text = rec.get("text")
                raw_reply = query_ollama(system_prompt, text)
                out_rec = {
                    "id": cmd_id,
                    "text": text,
                    "teacher_raw": raw_reply
                }
                out_f.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
                out_f.flush()

    print(f"[Worker {SHARD_INDEX}] Finished processing shard.")


if __name__ == "__main__":
    main()
