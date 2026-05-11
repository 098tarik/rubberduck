"""Model catalog with capability metadata for recommendation scoring."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelSpec:
    # Ollama pull name  e.g. "llama3.2:3b"
    name: str
    display_name: str
    param_billions: float
    # Minimum RAM (CPU-only) to run comfortably
    min_ram_gb: float
    # Minimum VRAM for full GPU offload (0 = runs fine CPU-only)
    min_vram_gb: float
    # 1–10 relative quality score
    quality_score: float
    # 1–10 speed score (higher = faster)
    speed_score: float
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    context_k: int = 4  # context window in thousands of tokens
    # e.g. "coding", "reasoning", "general", "multilingual"
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Curated catalog — covers the most popular Ollama library models as of 2025
# ---------------------------------------------------------------------------
CATALOG: list[ModelSpec] = [
    # ── Llama 3 family ──────────────────────────────────────────────────────
    ModelSpec(
        name="llama3.2:1b",
        display_name="Llama 3.2 1B",
        param_billions=1.2,
        min_ram_gb=2.0,
        min_vram_gb=0.0,
        quality_score=3.5,
        speed_score=10.0,
        strengths=["ultra-fast", "runs on any hardware", "tiny footprint"],
        weaknesses=["limited reasoning", "short context", "basic knowledge"],
        use_cases=["simple chat", "text completion", "on-device / edge"],
        context_k=128,
        tags=["general", "edge"],
    ),
    ModelSpec(
        name="llama3.2:3b",
        display_name="Llama 3.2 3B",
        param_billions=3.2,
        min_ram_gb=3.5,
        min_vram_gb=0.0,
        quality_score=5.5,
        speed_score=9.0,
        strengths=["fast", "good for basic tasks", "low memory"],
        weaknesses=["struggles with complex reasoning", "limited depth"],
        use_cases=["chat assistant", "summarisation", "lightweight coding help"],
        context_k=128,
        tags=["general", "edge"],
    ),
    ModelSpec(
        name="llama3.1:8b",
        display_name="Llama 3.1 8B",
        param_billions=8.0,
        min_ram_gb=6.0,
        min_vram_gb=6.0,
        quality_score=7.0,
        speed_score=7.5,
        strengths=["well-rounded", "good instruction following", "popular ecosystem"],
        weaknesses=["mid-tier reasoning", "not specialised"],
        use_cases=["general assistant", "writing", "moderate coding"],
        context_k=128,
        tags=["general"],
    ),
    ModelSpec(
        name="llama3.1:70b",
        display_name="Llama 3.1 70B",
        param_billions=70.0,
        min_ram_gb=48.0,
        min_vram_gb=40.0,
        quality_score=9.0,
        speed_score=3.0,
        strengths=["near-GPT-4 quality", "strong reasoning", "long context"],
        weaknesses=["very high VRAM/RAM requirement", "slow on CPU"],
        use_cases=["complex analysis", "code generation", "research"],
        context_k=128,
        tags=["general", "reasoning"],
    ),
    # ── Mistral / Mixtral ────────────────────────────────────────────────────
    ModelSpec(
        name="mistral:7b",
        display_name="Mistral 7B",
        param_billions=7.2,
        min_ram_gb=5.5,
        min_vram_gb=5.5,
        quality_score=7.0,
        speed_score=7.5,
        strengths=["excellent instruction following", "fast", "strong at code"],
        weaknesses=["smaller knowledge base than Llama 70B"],
        use_cases=["coding assistant", "writing", "instruction tasks"],
        context_k=32,
        tags=["general", "coding"],
    ),
    ModelSpec(
        name="mixtral:8x7b",
        display_name="Mixtral 8x7B (MoE)",
        param_billions=46.7,  # total params; active ~12.9B per token
        min_ram_gb=32.0,
        min_vram_gb=26.0,
        quality_score=8.5,
        speed_score=5.0,
        strengths=["mixture-of-experts efficiency", "GPT-3.5 quality", "multilingual"],
        weaknesses=["large download (~26 GB)", "needs lots of RAM"],
        use_cases=["complex reasoning", "multilingual tasks", "long documents"],
        context_k=32,
        tags=["general", "multilingual"],
    ),
    # ── Phi ─────────────────────────────────────────────────────────────────
    ModelSpec(
        name="phi3.5:3.8b",
        display_name="Phi 3.5 Mini 3.8B",
        param_billions=3.8,
        min_ram_gb=4.0,
        min_vram_gb=3.5,
        quality_score=6.5,
        speed_score=8.5,
        strengths=["punches above its weight", "strong reasoning for size", "long context"],
        weaknesses=["can be verbose", "limited world knowledge"],
        use_cases=["coding", "reasoning tasks", "on-device assistant"],
        context_k=128,
        tags=["coding", "reasoning", "edge"],
    ),
    ModelSpec(
        name="phi4:14b",
        display_name="Phi 4 14B",
        param_billions=14.0,
        min_ram_gb=10.0,
        min_vram_gb=9.0,
        quality_score=8.5,
        speed_score=5.5,
        strengths=["state-of-the-art for size", "strong at math & reasoning", "long context"],
        weaknesses=["newer — fewer community resources"],
        use_cases=["STEM reasoning", "coding", "complex Q&A"],
        context_k=16,
        tags=["coding", "reasoning"],
    ),
    # ── Gemma ────────────────────────────────────────────────────────────────
    ModelSpec(
        name="gemma3:2b",
        display_name="Gemma 3 2B",
        param_billions=2.0,
        min_ram_gb=2.5,
        min_vram_gb=0.0,
        quality_score=5.0,
        speed_score=9.5,
        strengths=["very fast", "multimodal capable", "low memory"],
        weaknesses=["limited depth", "basic reasoning"],
        use_cases=["quick chat", "summarisation", "mobile / edge"],
        context_k=128,
        tags=["general", "edge"],
    ),
    ModelSpec(
        name="gemma3:9b",
        display_name="Gemma 3 9B",
        param_billions=9.0,
        min_ram_gb=7.0,
        min_vram_gb=7.0,
        quality_score=7.5,
        speed_score=7.0,
        strengths=["strong instruction following", "multimodal", "good coding"],
        weaknesses=["mid-tier at large-scale reasoning"],
        use_cases=["assistant", "vision tasks", "code review"],
        context_k=128,
        tags=["general", "coding"],
    ),
    ModelSpec(
        name="gemma3:27b",
        display_name="Gemma 3 27B",
        param_billions=27.0,
        min_ram_gb=20.0,
        min_vram_gb=16.0,
        quality_score=8.5,
        speed_score=4.5,
        strengths=["excellent quality for size", "multimodal", "long context"],
        weaknesses=["slow on CPU", "large VRAM needed"],
        use_cases=["research assistant", "vision-language", "complex tasks"],
        context_k=128,
        tags=["general", "reasoning"],
    ),
    # ── Qwen ─────────────────────────────────────────────────────────────────
    ModelSpec(
        name="qwen2.5:7b",
        display_name="Qwen 2.5 7B",
        param_billions=7.0,
        min_ram_gb=5.5,
        min_vram_gb=5.0,
        quality_score=7.5,
        speed_score=7.5,
        strengths=["top coding performance for size", "multilingual (CJK)", "long context"],
        weaknesses=["may need extra prompting for English-only tasks"],
        use_cases=["coding", "multilingual chat", "data analysis"],
        context_k=128,
        tags=["coding", "multilingual"],
    ),
    ModelSpec(
        name="qwen2.5-coder:7b",
        display_name="Qwen 2.5 Coder 7B",
        param_billions=7.0,
        min_ram_gb=5.5,
        min_vram_gb=5.0,
        quality_score=8.0,
        speed_score=7.5,
        strengths=["best-in-class coding at 7B", "FIM / completion support", "multi-language code"],
        weaknesses=["less capable for general chat"],
        use_cases=["code generation", "debugging", "code review"],
        context_k=128,
        tags=["coding"],
    ),
    # ── DeepSeek ─────────────────────────────────────────────────────────────
    ModelSpec(
        name="deepseek-r1:8b",
        display_name="DeepSeek R1 8B",
        param_billions=8.0,
        min_ram_gb=6.0,
        min_vram_gb=6.0,
        quality_score=7.5,
        speed_score=6.5,
        strengths=["chain-of-thought reasoning", "math & logic", "transparent thinking"],
        weaknesses=["verbose outputs", "slower than non-reasoning models"],
        use_cases=["math", "logic puzzles", "step-by-step reasoning"],
        context_k=128,
        tags=["reasoning"],
    ),
    ModelSpec(
        name="deepseek-r1:32b",
        display_name="DeepSeek R1 32B",
        param_billions=32.0,
        min_ram_gb=22.0,
        min_vram_gb=20.0,
        quality_score=9.0,
        speed_score=3.5,
        strengths=["near-GPT-4o reasoning", "excellent math & code", "long CoT"],
        weaknesses=["very slow on CPU", "high memory requirement"],
        use_cases=["complex math", "advanced coding", "research"],
        context_k=128,
        tags=["reasoning", "coding"],
    ),
    # ── Code Llama ───────────────────────────────────────────────────────────
    ModelSpec(
        name="codellama:7b",
        display_name="Code Llama 7B",
        param_billions=7.0,
        min_ram_gb=5.5,
        min_vram_gb=5.0,
        quality_score=6.5,
        speed_score=7.5,
        strengths=["FIM code completion", "multiple languages", "mature tooling"],
        weaknesses=["older than Qwen 2.5 Coder", "weaker reasoning"],
        use_cases=["code completion", "fill-in-middle", "IDE integration"],
        context_k=16,
        tags=["coding"],
    ),
    # ── Nomic / Embedding (shown for awareness, low weight in chat scoring) ──
    ModelSpec(
        name="nomic-embed-text",
        display_name="Nomic Embed Text",
        param_billions=0.137,
        min_ram_gb=0.5,
        min_vram_gb=0.0,
        quality_score=8.0,  # top embedding quality
        speed_score=10.0,
        strengths=["state-of-the-art embeddings", "tiny", "blazing fast"],
        weaknesses=["embedding only — not a chat model"],
        use_cases=["RAG / semantic search", "vector database", "similarity"],
        context_k=8,
        tags=["embedding"],
    ),
]
