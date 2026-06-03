# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

### Changed

### Fixed

---

## [1.0.0] - 2026-06-03

### Added

- Core routing engine with multi-strategy model selection
- Smart task classifier (complexity + type + context window)
- Provider pool with cost/speed/quality/performance profiles
- Four routing strategies: cost_optimized, speed_optimized, quality_optimized, balanced
- Batch routing for multiple tasks
- Automatic fallback chain when providers fail
- Real-time cost tracking and performance analytics
- CLI tool with interactive mode, cost reports, and benchmarking
- Full test suite (23 tests, 100% passing)
- CI/CD pipeline (GitHub Actions)
- PyPI package publishing support

### Changed

- [BREAKING] Initial release — stable API for routing decisions

### Technical Details

- Built and tested on Python 3.11+
- Uses tiktoken for token estimation
- HTTPX for async HTTP requests
- Rich for terminal UI rendering
- Supports OpenAI, Anthropic, OpenRouter, and local models (vLLM, llama.cpp)

### Contributors

- [Mark Aardenne](https://github.com/aardenne) — Architecture & Implementation

[Unreleased]: https://github.com/aardenne/viberouter/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/aardenne/viberouter/releases/tag/v1.0.0
