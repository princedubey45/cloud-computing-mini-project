import os
import sys
import glob
import json
import hashlib

ALLOWED_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events"
}

REQUIRED_KEYS = {"intent", "date", "time", "place"}


def clean_shards(input_dir="datasets/teacher", output_file="datasets/v1/train.jsonl", sha_file="datasets/v1/train.sha256"):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    shard_files = sorted(glob.glob(os.path.join(input_dir, "shard-*.jsonl")))
    if not shard_files:
        print(f"No shard files found in {input_dir}")
        return

    all_records = []
    seen_ids = set()
    total_input = 0

    for sf in shard_files:
        with open(sf, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_input += 1
                rec = json.loads(line)
                all_records.append(rec)

    # Sort primarily by id to ensure deterministic processing
    all_records.sort(key=lambda r: r.get("id", ""))

    rejected_a = 0  # not valid JSON
    rejected_b = 0  # keys not exactly intent, date, time, place
    rejected_c = 0  # intent not in the eight allowed
    rejected_d = 0  # slot not null and not substring of command
    rejected_e = 0  # duplicate commands (keep smallest id)
    kept_records = []

    seen_commands = set()

    for rec in all_records:
        cmd_id = rec.get("id")
        text = rec.get("text", "")
        raw = rec.get("teacher_raw", "")

        # (e) Duplicate command check (keep smallest id, which is encountered first due to sorting)
        norm_text = text.strip().lower()
        if norm_text in seen_commands:
            rejected_e += 1
            continue

        # (a) Check valid JSON
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(parsed, dict):
                rejected_a += 1
                continue
        except Exception:
            rejected_a += 1
            continue

        # (b) Keys must be exactly intent, date, time, place
        if set(parsed.keys()) != REQUIRED_KEYS:
            rejected_b += 1
            continue

        # Check types: date, time, place must be string or None; intent must be string
        if not isinstance(parsed["intent"], str):
            rejected_b += 1
            continue
        valid_slot_types = True
        for slot in ("date", "time", "place"):
            if parsed[slot] is not None and not isinstance(parsed[slot], str):
                valid_slot_types = False
                break
        if not valid_slot_types:
            rejected_b += 1
            continue

        # (c) Intent must be one of the eight
        if parsed["intent"] not in ALLOWED_INTENTS:
            rejected_c += 1
            continue

        # (d) Slot values must be null or text that appears in the command
        valid_slots = True
        cmd_lower = text.lower()
        for slot in ("date", "time", "place"):
            val = parsed[slot]
            if val is not None:
                if val.lower() not in cmd_lower:
                    valid_slots = False
                    break
        if not valid_slots:
            rejected_d += 1
            continue

        # Passed all checks!
        seen_commands.add(norm_text)
        kept_records.append({
            "id": cmd_id,
            "text": text,
            "intent": parsed["intent"],
            "date": parsed["date"],
            "time": parsed["time"],
            "place": parsed["place"],
            "target_json": json.dumps(parsed, ensure_ascii=False)
        })

    # Sort final records by id
    kept_records.sort(key=lambda r: r["id"])

    # Write output
    sha256 = hashlib.sha256()
    with open(output_file, "w", encoding="utf-8") as out_f:
        for r in kept_records:
            line = json.dumps(r, ensure_ascii=False) + "\n"
            out_f.write(line)
            sha256.update(line.encode("utf-8"))

    computed_hash = sha256.hexdigest()
    with open(sha_file, "w", encoding="utf-8") as sha_f:
        sha_f.write(f"{computed_hash}  train.jsonl\n")

    print("========================================")
    print("DATASET CLEANING SUMMARY (Task 1)")
    print("========================================")
    print(f"Total Input Records      : {total_input}")
    print(f"(a) Invalid JSON         : {rejected_a}")
    print(f"(b) Invalid Keys/Types   : {rejected_b}")
    print(f"(c) Invalid Intent       : {rejected_c}")
    print(f"(d) Hallucinated Slots   : {rejected_d}")
    print(f"(e) Duplicate Commands   : {rejected_e}")
    print(f"Records Kept             : {len(kept_records)}")
    print("----------------------------------------")
    check_sum = rejected_a + rejected_b + rejected_c + rejected_d + rejected_e + len(kept_records)
    print(f"Validation (Sum of parts): {check_sum} == {total_input} ({'MATCH' if check_sum == total_input else 'MISMATCH'})")
    print(f"SHA-256 Checksum         : {computed_hash}")
    print("========================================")


if __name__ == "__main__":
    clean_shards()
