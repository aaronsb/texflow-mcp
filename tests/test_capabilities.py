"""Tests for system capability detection."""

from unittest.mock import patch

from texflow.capabilities import (
    SystemCapabilities,
    check_capabilities,
    format_capabilities,
    format_missing_warnings,
    reset_cache,
)


class TestSystemCapabilities:
    def setup_method(self):
        reset_cache()

    def test_check_capabilities_returns_dataclass(self):
        caps = check_capabilities()
        assert isinstance(caps, SystemCapabilities)

    def test_engines_detected(self):
        caps = check_capabilities()
        assert "xelatex" in caps.engines
        assert "pdflatex" in caps.engines
        assert "lualatex" in caps.engines

    def test_tools_detected(self):
        caps = check_capabilities()
        assert "biber" in caps.tools
        assert "kpsewhich" in caps.tools
        assert "pygmentize" in caps.tools

    def test_distribution_detected(self):
        caps = check_capabilities()
        assert caps.tex_distribution != ""

    def test_package_check(self):
        caps = check_capabilities(packages=["amsmath", "graphicx"])
        assert "amsmath" in caps.packages
        assert "graphicx" in caps.packages

    def test_package_check_additive(self):
        caps = check_capabilities(packages=["amsmath"])
        assert "amsmath" in caps.packages
        caps2 = check_capabilities(packages=["graphicx"])
        assert "amsmath" in caps2.packages
        assert "graphicx" in caps2.packages

    def test_caching(self):
        caps1 = check_capabilities()
        caps2 = check_capabilities()
        assert caps1 is caps2

    def test_reset_cache(self):
        caps1 = check_capabilities()
        reset_cache()
        caps2 = check_capabilities()
        assert caps1 is not caps2


class TestFormatMissingWarnings:
    def test_no_warnings_when_all_present(self):
        caps = SystemCapabilities(
            engines={"xelatex": True},
            tools={"biber": True},
            packages={"amsmath": True},
        )
        warnings = format_missing_warnings(caps, needed_packages=["amsmath"])
        assert warnings == []

    def test_missing_engine_warning(self):
        caps = SystemCapabilities(
            engines={"xelatex": False, "pdflatex": True},
            tools={},
            packages={},
        )
        warnings = format_missing_warnings(caps)
        assert any("xelatex" in w for w in warnings)

    def test_missing_tool_warning(self):
        caps = SystemCapabilities(
            engines={},
            tools={"pygmentize": False, "biber": True},
            packages={},
        )
        warnings = format_missing_warnings(caps)
        assert any("pygmentize" in w for w in warnings)

    def test_missing_package_warning(self):
        caps = SystemCapabilities(
            engines={},
            tools={},
            packages={"foobar-nonexistent": False, "amsmath": True},
        )
        warnings = format_missing_warnings(caps, needed_packages=["foobar-nonexistent"])
        assert any("foobar-nonexistent" in w for w in warnings)

    def test_no_needed_packages_skips_package_check(self):
        caps = SystemCapabilities(
            engines={},
            tools={},
            packages={"foo": False},
        )
        warnings = format_missing_warnings(caps)
        assert not any("package" in w.lower() for w in warnings)


class TestFormatCapabilities:
    def test_format_includes_distribution(self):
        caps = SystemCapabilities(
            engines={"xelatex": True},
            tools={"biber": True},
            tex_distribution="TeX Live 2026",
        )
        result = format_capabilities(caps)
        assert "TeX Live 2026" in result

    def test_format_includes_engines(self):
        caps = SystemCapabilities(
            engines={"xelatex": True, "pdflatex": False},
            tools={},
        )
        result = format_capabilities(caps)
        assert "xelatex: installed" in result
        assert "pdflatex: not found" in result

    def test_format_includes_tools(self):
        caps = SystemCapabilities(
            engines={},
            tools={"biber": True, "pygmentize": False},
        )
        result = format_capabilities(caps)
        assert "biber: installed" in result
        assert "pygmentize: not found" in result

    def test_format_includes_packages(self):
        caps = SystemCapabilities(
            engines={},
            tools={},
            packages={"amsmath": True, "foobar": False},
        )
        result = format_capabilities(caps)
        assert "amsmath: available" in result
        assert "foobar: not found" in result

    def test_format_no_packages_section_when_empty(self):
        caps = SystemCapabilities(engines={}, tools={})
        result = format_capabilities(caps)
        assert "Packages:" not in result


class TestMissingKpsewhich:
    def setup_method(self):
        reset_cache()

    def test_packages_false_when_kpsewhich_missing(self):
        with patch("texflow.capabilities.shutil.which", side_effect=lambda x: None if x == "kpsewhich" else "/usr/bin/" + x):
            reset_cache()
            caps = check_capabilities(packages=["amsmath"])
            assert caps.packages["amsmath"] is False
