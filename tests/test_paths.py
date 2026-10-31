"""模擬封裝環境，驗證唯讀資源與使用者資料使用不同根目錄。"""
import importlib
import pathlib
import sys

import pytest

from heartopia_overlay import paths


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """模擬 PyInstaller onefile：exe 在 tmp/app，資料解壓到 tmp/extract。"""
    exe = tmp_path / "app" / "HeartopiaPaintingOverlayHelper.exe"
    extract = tmp_path / "extract"
    exe.parent.mkdir(parents=True)
    extract.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(extract), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe.parent, extract


def test_source_layout_finds_the_data_dir():
    assert paths.bundled("data", "palette.json").exists()
    assert paths.bundled("docs", "guide", "index.html").exists()


def test_frozen_data_comes_from_the_extraction_dir(frozen):
    _, extract = frozen
    assert paths.bundled("data", "palette.json") == extract / "data" / "palette.json"


def test_frozen_config_sits_next_to_the_exe(frozen):
    """設定檔若寫進解壓目錄，每次啟動都會不見。"""
    exe_dir, extract = frozen
    got = paths.userdata("config", "ui_coords.json")
    assert got == exe_dir / "config" / "ui_coords.json"
    assert extract not in got.parents


def test_frozen_flag_is_reported(frozen):
    assert paths.is_frozen()


def test_not_frozen_by_default():
    assert not paths.is_frozen()


def test_entry_script_avoids_relative_imports():
    """PyInstaller 以頂層 __main__ 執行入口，須使用絕對匯入。"""
    src = (pathlib.Path(__file__).parent.parent / "run_assist.py").read_text(encoding="utf-8")
    assert "from heartopia_overlay." in src
    assert "from ." not in src


def test_spec_uses_the_absolute_import_entry_point():
    spec = (pathlib.Path(__file__).parent.parent / "assist.spec").read_text(
        encoding="utf-8")
    import ast
    tree=ast.parse(spec)
    analysis=next(node for node in ast.walk(tree) if isinstance(node,ast.Call)
                  and isinstance(node.func,ast.Name) and node.func.id=='Analysis')
    assert ast.literal_eval(analysis.args[0])==['run_assist.py']
    assert "__main__.py" not in spec.split("Analysis(")[1].split(")")[0]


def test_spec_bundles_manual_palette_and_offline_guide():
    spec = (pathlib.Path(__file__).parent.parent / "assist.spec").read_text(
        encoding="utf-8")
    assert "data/palette.json" in spec
    assert "docs/guide" in spec
