"""Hardware capability detection for model recommendation."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class GPUInfo:
    name: str
    vram_gb: float
    gpu_type: str  # "nvidia" | "amd" | "apple" | "intel" | "unknown"


@dataclass
class HardwareProfile:
    platform: str           # "linux" | "darwin" | "windows"
    cpu_cores: int
    cpu_threads: int
    ram_gb: float
    gpus: list[GPUInfo] = field(default_factory=list)

    @property
    def total_vram_gb(self) -> float:
        return sum(g.vram_gb for g in self.gpus)

    @property
    def primary_gpu(self) -> GPUInfo | None:
        return self.gpus[0] if self.gpus else None

    @property
    def has_discrete_gpu(self) -> bool:
        return any(g.gpu_type in ("nvidia", "amd") for g in self.gpus)

    @property
    def has_apple_silicon(self) -> bool:
        return any(g.gpu_type == "apple" for g in self.gpus)

    # Effective memory available for a model (GPU-first, fall back to RAM)
    @property
    def effective_memory_gb(self) -> float:
        if self.total_vram_gb > 0:
            return self.total_vram_gb
        # CPU-only: models can use system RAM (allow up to 80% for model)
        return self.ram_gb * 0.8


# ---------------------------------------------------------------------------
# RAM helpers
# ---------------------------------------------------------------------------

def _to_gb(value: int, divisor: int) -> float:
    return round(value / divisor, 1)


def _ram_gb_linux() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return _to_gb(kb, 1024 ** 2)
    except OSError:
        pass
    return 0.0


def _ram_gb_macos() -> float:
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        return _to_gb(int(out), 1024 ** 3)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def _ram_gb_windows() -> float:
    try:
        out = subprocess.check_output(
            ["wmic", "OS", "get", "TotalVisibleMemorySize", "/Value"],
            text=True,
        )
        match = re.search(r"TotalVisibleMemorySize=(\d+)", out)
        if match:
            return _to_gb(int(match.group(1)), 1024 ** 2)
    except (OSError, subprocess.SubprocessError):
        pass

    # Newer Windows versions may not have wmic available.
    # Fall back to PowerShell/CIM for total physical memory in bytes.
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
            ],
            text=True,
        ).strip()
        match = re.fullmatch(r"(\d+)", out)
        if match:
            return _to_gb(int(match.group(1)), 1024 ** 3)
    except (OSError, subprocess.SubprocessError):
        pass

    return 0.0


def _detect_ram_gb() -> float:
    sys = platform.system()
    if sys == "Linux":
        return _ram_gb_linux()
    if sys == "Darwin":
        return _ram_gb_macos()
    if sys == "Windows":
        return _ram_gb_windows()
    return 0.0


# ---------------------------------------------------------------------------
# CPU helpers
# ---------------------------------------------------------------------------

def _detect_cpu() -> tuple[int, int]:
    """Return (physical_cores, logical_threads)."""
    import os

    threads = os.cpu_count() or 1

    # Try to get physical cores on Linux
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                cores = len({
                    line.split(":")[1].strip()
                    for line in f
                    if line.startswith("core id")
                })
            if cores:
                return cores, threads
        except OSError:
            pass

    # macOS
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.physicalcpu"], text=True
            ).strip()
            return int(out), threads
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    return threads, threads


# ---------------------------------------------------------------------------
# GPU helpers
# ---------------------------------------------------------------------------

def _detect_nvidia() -> list[GPUInfo]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        )
        gpus = []
        for line in out.strip().splitlines():
            parts = line.split(",")
            if len(parts) == 2:
                name = parts[0].strip()
                vram_mb = float(parts[1].strip())
                gpus.append(GPUInfo(name=name, vram_gb=round(vram_mb / 1024, 1), gpu_type="nvidia"))
        return gpus
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def _detect_amd() -> list[GPUInfo]:
    if not shutil.which("rocm-smi"):
        return []
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            text=True,
            timeout=10,
        )
        import json

        data = json.loads(out)
        gpus = []
        for card_id, info in data.items():
            if not isinstance(info, dict):
                continue
            vram_bytes = int(info.get("VRAM Total Memory (B)", 0))
            name = info.get("Card Series", f"AMD GPU {card_id}")
            gpus.append(
                GPUInfo(
                    name=name,
                    vram_gb=round(vram_bytes / (1024 ** 3), 1),
                    gpu_type="amd",
                )
            )
        return gpus
    except (OSError, subprocess.SubprocessError, ValueError, Exception):
        return []


def _detect_apple_silicon() -> list[GPUInfo]:
    if platform.system() != "Darwin":
        return []
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"],
            text=True,
            timeout=10,
        )
        # Apple Silicon shares RAM with GPU; report system RAM as unified memory
        chip_match = re.search(r"Chip:\s*(.+)", out)
        chip = chip_match.group(1).strip() if chip_match else "Apple Silicon"
        if "Apple" not in chip:
            return []
        ram_gb = _ram_gb_macos()
        return [GPUInfo(name=chip, vram_gb=ram_gb, gpu_type="apple")]
    except (OSError, subprocess.SubprocessError):
        return []


def _detect_intel_arc() -> list[GPUInfo]:
    """Basic detection via lspci on Linux."""
    if platform.system() != "Linux" or not shutil.which("lspci"):
        return []
    try:
        out = subprocess.check_output(["lspci"], text=True, timeout=10)
        gpus = []
        for line in out.splitlines():
            if "VGA" in line or "Display" in line or "3D" in line:
                if "Intel" in line and ("Arc" in line or "Iris" in line or "UHD" in line):
                    # Intel integrated / Arc — VRAM not easily queryable without level0 tools
                    gpus.append(GPUInfo(name=line.split(":")[-1].strip(), vram_gb=0.0, gpu_type="intel"))
        return gpus
    except (OSError, subprocess.SubprocessError):
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_hardware() -> HardwareProfile:
    """Detect current machine's CPU, RAM and GPU capabilities."""
    sys = platform.system()
    platform_name = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(sys, sys.lower())

    physical_cores, threads = _detect_cpu()
    ram_gb = _detect_ram_gb()

    gpus: list[GPUInfo] = []

    # Priority: NVIDIA > AMD > Apple Silicon > Intel
    gpus.extend(_detect_nvidia())
    if not gpus:
        gpus.extend(_detect_amd())
    if not gpus:
        gpus.extend(_detect_apple_silicon())
    if not gpus:
        gpus.extend(_detect_intel_arc())

    return HardwareProfile(
        platform=platform_name,
        cpu_cores=physical_cores,
        cpu_threads=threads,
        ram_gb=ram_gb,
        gpus=gpus,
    )
