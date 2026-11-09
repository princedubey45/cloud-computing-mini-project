# CS3081 Cloud Computing: Mini Project
## Knowledge Distillation and Deployment of a Lightweight Command-Parsing Language Model on a Local Cloud

**Student Name:** Prince Kumar Dubey  
**Roll Number:** 230101081  
**Email:** prin230101081@iiitmanipur.ac.in  
**Institution:** Indian Institute of Information Technology Manipur  
**GitHub Repository:** [https://github.com/princedubey45/cloud-computing-mini-project](https://github.com/princedubey45/cloud-computing-mini-project)  
**Final Submission Tag:** `final`

---

## Quickstart Instructions

The entire system is reproducible and orchestrated using a standard `Makefile`.

### 1. Build and Deploy (`make up`)
Deploy the complete local cloud environment in at most three commands:
```bash
make up
```
This performs:
1. Creates the local Kubernetes cluster from `cluster/k3d.yaml`.
2. Deploys SeaweedFS S3 storage in the `data` namespace.
3. Deploys the application, secrets, service, Traefik ingress, and HPA in the `app` namespace.

The service will be live and serving traffic at `http://localhost:8080/parse`.

---

### 2. Fine-Tuning the Student Model (`make train`)
Train the student language model (`EleutherAI/pythia-70m`) using sequence-level knowledge distillation:
```bash
# Full training on cleaned teacher dataset
make train

# Verification mode: train on subset of 50 records
make train SUBSET=50
```

---

### 3. Running Unit Tests and Linting
Validate the codebase against quality gates:
```bash
# Run unit test suite (5 test cases)
make test

# Run code style and linting checks
make lint
```

---

### 4. Running Load Testing and Benchmarking
Execute the Locust load test through the Ingress controller:
```bash
locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8080 --csv results/loadtest
```

---

### 5. Tearing Down the Cluster (`make down`)
Clean up all cluster resources and persistent containers:
```bash
make down
```

---

## Repository Structure
```
├── cluster/
│   └── k3d.yaml                  # Local Kubernetes cluster configuration
├── prompts/
│   └── teacher_prompt.txt        # Prompt instructing Phi-3.5 teacher
├── worker/
│   ├── worker.py                 # Sharded teacher inference worker
│   └── clean.py                  # Dataset cleaning & checksum script
├── datasets/
│   └── v1/train.jsonl            # Cleaned distillation dataset & SHA-256
├── training/
│   ├── config.yaml               # Hyperparameters & pinned library versions
│   ├── train.py                  # PyTorch student training script
│   └── loss.csv                  # Epoch loss tracking
├── service/
│   ├── app.py                    # FastAPI inference service (/parse, /healthz, /readyz)
│   ├── Dockerfile                # Slim container build (< 2 GB, CPU wheels)
│   ├── requirements.txt          # Pinned dependency specifications
│   └── test_service.py           # Comprehensive pytest suite
├── k8s/
│   ├── deployment.yaml           # Deployment with rolling update & resource limits
│   ├── service.yaml              # ClusterIP service
│   ├── ingress.yaml              # Traefik Ingress routing
│   ├── hpa.yaml                  # Horizontal Pod Autoscaler (1-2 replicas, 70% CPU)
│   ├── secret.yaml               # Kubernetes Secret for S3 credentials
│   └── seaweedfs.yaml            # SeaweedFS deployment in data namespace
├── network/
│   ├── subnets.md                # Subnetting derivations and stateless NACL reasoning
│   └── nacl.json                 # Stateless NACL rules for public subnet
├── tools/
│   ├── score.py                  # Scoring script for predictions
│   ├── locustfile.py             # Locust load test benchmark
│   └── nacl_sim.py               # Stateless NACL simulator
├── results/                      # Evaluation reports, logs, and benchmark CSVs
├── report/
│   └── report.pdf                # 8-page comprehensive architectural report
├── 230101081.pdf                 # 3-page handwritten reflection document
├── AI_USE.md                     # Statement of AI usage and validation procedures
└── Makefile                      # Build, deployment, test, and teardown targets
```
