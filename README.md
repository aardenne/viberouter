# VibeRouter - Intelligent Local LLM Router

**A production-grade router for local LLM setups optimized for multi-node GPU clusters like NVIDIA DGX Spark.**

[![Version](https://img.shields.io/badge/version-0.4.0-blue)](https://github.com/aardenne/viberouter/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com/)
[![CI](https://github.com/aardenne/viberouter/actions/workflows/ci.yml/badge.svg)](https://github.com/aardenne/viberouter/actions)
[![Downloads](https://img.shields.io/pypi/dm/viberouter)](https://pypi.org/project/viberouter/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## 🌟 Features

- 🤖 **Intelligent Task Classification** — Automatically categorizes requests (coding, vision, reasoning, etc.)
- ⚖️ **Advanced Load Balancing** — Weighted Round Robin, Least Connections, Least Loaded strategies
- 🔄 **Auto-Fallback System** — Seamlessly routes around unhealthy nodes
- 📊 **Real-time Monitoring** — Web dashboard with live metrics and WebSocket updates
- 🛠️ **Powerful CLI** — Manage nodes, run benchmarks, and test routing from terminal
- 🔌 **OpenAI-Compatible** — Works with vLLM, Ollama, LM Studio, and any OpenAI API
- 🔒 **Zero Secrets in Code** — Environment variables and secure config management
- 📈 **Prometheus Metrics** — Built-in monitoring for production deployments

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VibeRouter Core                         │
├─────────────────────────────────────────────────────────────┤
│  Task Classifier  │  Load Balancer  │  Auto-Fallback       │
│  (Heuristics +    │  (WRR /         │  (Health Checks +    │
│   LLM Optional)   │   LeastConn)    │   Circuit Breaker)   │
└──────────┬────────┴────────┬────────┴──────────┬───────────┘
           │                  │                   │
┌──────────▼──────────────────▼───────────────────▼───────────┐
│                    Node Routing                             │
├──────────────────────┬──────────────────────────────────────┤
│    GB10 #1 (Nemotron)│       GB10 #2 (Qwen3.6-35B)         │
│    Vision / Latency  │       Coding / Heavy Reasoning       │
│    :30000            │       :8081                          │
└──────────────────────┴──────────────────────────────────────┘
```

---

## 📦 Installation

### From PyPI (Recommended)
```bash
pip install viberouter
```

### From Source
```bash
git clone https://github.com/aardenne/viberouter.git
cd viberouter
pip install -e .
```

### Development Setup
```bash
pip install -e ".[dev]"
```

---

## ⚡ Quick Start

### 1. Configure Your Nodes
Create a `config.yaml` file:
```yaml
# Global settings
log_level: INFO
metrics_port: 9090
dashboard_port: 8080
strategy: weighted_round_robin

# Your LLM nodes
nodes:
  - name: gb10_2
    url: http://localhost:8081/v1
    model: Qwen3.6-35B-A3B-NVFP4
    weight: 3
    max_connections: 12
    timeout: 60
    
  - name: gb10_1
    url: http://localhost:30000/v1
    model: Qwen3-Nemotron
    weight: 5
    max_connections: 20
    timeout: 30
```

### 2. Run the CLI
```bash
# Check node status
viberouter status

# Route a prompt
viberouter route "Write a Python function to calculate fibonacci numbers"

# Run benchmarks
viberouter benchmark

# View configuration
viberouter config
```

### 3. Start the Web Dashboard
```bash
uvicorn viberouter.api:app --host 0.0.0.0 --port 8080 --reload
```

Open [http://localhost:8080](http://localhost:8080) in your browser.

---

## 🎯 Example Use Cases

### 1. Coding Tasks → GB10 #2 (Qwen3.6-35B)
```bash
viberouter route "Create a FastAPI endpoint for user authentication"
# → Routed to: gb10_2 (Qwen3.6-35B) - High capacity for code generation
```

### 2. Vision Tasks → GB10 #1 (Nemotron)
```bash
viberouter route "Analyze this image and describe the content"
# → Routed to: gb10_1 (Nemotron) - Optimized for vision/latency
```

### 3. Heavy Reasoning → Automatic Fallback
```bash
viberouter route "Explain quantum computing in detail with mathematical proofs"
# → Routed to: gb10_2 (Qwen3.6-35B) - Handles long context (131K tokens)
```

### 4. Load-Balanced Chat
```bash
viberouter route "Tell me about the latest AI developments"
# → Routed based on current load (Least Connections strategy)
```

---

## 📊 Web Dashboard

The built-in dashboard provides:

- 🟢 **Real-time Node Health** — See which nodes are healthy/unhealthy
- 📈 **Load Monitoring** — Visual load bars for each node
- 📝 **Request Metrics** — Total requests, errors, tokens processed
- 🔌 **WebSocket Updates** — Live updates without page refresh

![Dashboard Preview](https://via.placeholder.com/800x400.png?text=VibeRouter+Dashboard+Preview)

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VIBEROUTER_LOG_LEVEL` | Logging level | `INFO` |
| `VIBEROUTER_METRICS_PORT` | Prometheus metrics port | `9090` |
| `VIBEROUTER_DASHBOARD_PORT` | Web dashboard port | `8080` |
| `VIBEROUTER_STRATEGY` | Routing strategy | `weighted_round_robin` |
| `VIBEROUTER_FALLBACK_ENABLED` | Enable auto-fallback | `true` |
| `VIBEROUTER_FALLBACK_THRESHOLD` | Failures before marking unhealthy | `3` |

### Routing Strategies

- **`weighted_round_robin`** — Distributes traffic based on node weights (default)
- **`least_connections`** — Routes to node with fewest active connections
- **`least_loaded`** — Routes to node with lowest current load

---

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=viberouter --cov-report=html
```

---

## 🔒 Security

- ✅ No hardcoded secrets or API keys
- ✅ Environment variables for sensitive config
- ✅ Health checks prevent routing to unhealthy nodes
- ✅ Timeout protection against hanging requests
- ✅ Rate limiting support (via `max_connections`)

---

## 📈 Why This Matters

**Local LLMs are powerful, but managing multiple models and nodes is hard.**

VibeRouter solves the pain points of local AI infrastructure:

1. **Resource Optimization** — Automatically distributes workloads to the best available node
2. **Fault Tolerance** — Seamlessly handles node failures without manual intervention
3. **Performance Monitoring** — Real-time visibility into system health and metrics
4. **Developer Experience** — Simple CLI and beautiful dashboard for day-to-day operations

**Built for:**
- Developers running multiple local LLMs
- Teams managing GB10/DGX Spark clusters
- Researchers benchmarking different models
- Anyone who wants their local AI infrastructure to "just work"

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Made with ❤️ by [4R Consultancy](https://4rconsultancy.nl)**

*Intelligent routing for local LLMs.*
