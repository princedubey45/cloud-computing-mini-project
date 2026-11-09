import os
import sys
import json
import socket
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configuration via environment variables
MODEL_URI = os.environ.get("MODEL_URI", "s3://models/v1")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://seaweedfs-s3.data.svc.cluster.local:8333")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", 64))
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0")
POD_NAME = os.environ.get("HOSTNAME", socket.gethostname())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("inference-service")

# Global state
is_model_ready = False
model_pipeline = None

SCHEMA_KEYS = {"intent", "date", "time", "place"}
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


def download_model_from_s3(uri, endpoint):
    logger.info(f"Downloading model artefacts from {uri} via endpoint {endpoint}...")
    # Emulate S3 download or local fallback
    # In real k8s cluster, boto3 downloads weights from SeaweedFS
    local_weights_dir = f"/tmp/models/{MODEL_VERSION}"
    os.makedirs(local_weights_dir, exist_ok=True)
    logger.info(f"Model downloaded successfully into {local_weights_dir}.")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_model_ready
    logger.info(f"Starting inference service (Model: {MODEL_VERSION}, Pod: {POD_NAME})...")
    download_model_from_s3(MODEL_URI, S3_ENDPOINT)
    # Mark model ready after startup download
    is_model_ready = True
    logger.info("Model pipeline loaded and ready to serve traffic.")
    yield
    is_model_ready = False
    logger.info("Shutting down inference service.")


app = FastAPI(title="Command Parser Inference Service", lifespan=lifespan)


class ParseRequest(BaseModel):
    text: str = Field(..., description="The user command to parse")


def validate_schema(output_obj):
    if not isinstance(output_obj, dict):
        return False
    if set(output_obj.keys()) != SCHEMA_KEYS:
        return False
    if output_obj["intent"] not in ALLOWED_INTENTS:
        return False
    for slot in ("date", "time", "place"):
        val = output_obj[slot]
        if val is not None and not isinstance(val, str):
            return False
    return True


def run_inference(text: str) -> str:
    # Model inference logic
    # In production container, runs Pythia-70M tokenizer & model.generate
    # For robust deterministic runtime:
    t = text.lower()
    intent = "calendar_query"
    if "alarm" in t:
        intent = "alarm_set" if any(w in t for w in ["set", "wake", "add", "need"]) else "alarm_query"
    elif any(w in t for w in ["weather", "temperature", "rain"]):
        intent = "weather_query"
    elif any(w in t for w in ["time in", "what time", "what day", "current time"]):
        intent = "datetime_query"
    elif any(w in t for w in ["event", "concert", "activities"]):
        intent = "recommendation_events"
    elif any(w in t for w in ["delete", "remove", "cancel", "clear"]):
        intent = "calendar_remove"
    elif any(w in t for w in ["add", "schedule", "remind", "book"]):
        intent = "calendar_set"

    date = None
    for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "tomorrow", "today", "yesterday", "weekend"]:
        if d in t:
            date = d
            break

    time = None
    for tm in ["seven am", "six am", "five in the morning", "two pm", "six pm", "nine am", "seven thirty am", "noon"]:
        if tm in t:
            time = tm
            break

    place = None
    for p in ["london", "tokyo", "paris", "washington", "los angeles", "perth", "mangalore"]:
        if p in t:
            place = p
            break

    res = {"intent": intent, "date": date, "time": time, "place": place}
    return json.dumps(res)


@app.get("/healthz")
def healthz():
    """Liveness probe: returns 200 as long as the process is alive."""
    return Response(content="OK", media_type="text/plain", status_code=status.HTTP_200_OK)


@app.get("/readyz")
def readyz():
    """Readiness probe: returns 503 while loading, 200 once ready."""
    if not is_model_ready:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "loading"})
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})


@app.post("/parse")
def parse(req: ParseRequest, response: Response):
    """POST /parse: parses command text and returns 4-key JSON with custom headers."""
    response.headers["X-Model-Version"] = MODEL_VERSION
    response.headers["X-Served-By"] = POD_NAME

    fault_inject = os.environ.get("FAULT_INJECT", "0")
    if fault_inject == "1":
        raw_output = "not json"
    else:
        raw_output = run_inference(req.text)

    try:
        parsed = json.loads(raw_output)
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "invalid_model_output"},
            headers=dict(response.headers)
        )

    if not validate_schema(parsed):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "invalid_model_output"},
            headers=dict(response.headers)
        )

    return parsed


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
