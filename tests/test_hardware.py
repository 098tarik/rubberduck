"""Tests for hardware detection helpers."""

from unittest.mock import patch

from app import hardware


def test_ram_gb_windows_uses_wmic_when_available():
    with patch(
        "app.hardware.subprocess.check_output",
        return_value="TotalVisibleMemorySize=33554432\r\r\n\r\r\n",
    ):
        assert hardware._ram_gb_windows() == 32.0


def test_ram_gb_windows_falls_back_to_powershell_when_wmic_unavailable():
    with patch(
        "app.hardware.subprocess.check_output",
        side_effect=[OSError("wmic not found"), "17179869184\r\n"],
    ):
        assert hardware._ram_gb_windows() == 16.0


def test_ram_gb_windows_returns_zero_when_all_probes_fail():
    with patch(
        "app.hardware.subprocess.check_output",
        side_effect=OSError("not available"),
    ):
        assert hardware._ram_gb_windows() == 0.0
