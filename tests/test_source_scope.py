"""檢查公開套件範圍，以及遊戲輸入操作與單次選色控制器的邊界。"""
import ast
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def test_source_contains_one_public_package():
    packages={path.name for path in (ROOT/'src').iterdir()
              if path.is_dir() and not path.name.startswith('.') and path.name!='__pycache__'}
    assert packages=={'heartopia_overlay'}


def test_game_input_primitives_are_confined_to_single_color_controller():
    calls={}
    primitives={'mouse_event','keybd_event','SendInput','PostMessage','PostMessageW','PostMessageA',
                'SetCursorPos','SetPhysicalCursorPos'}
    for path in (ROOT/'src').rglob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        found={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call)
               and isinstance(node.func,ast.Attribute) and node.func.attr in primitives}
        if found:
            calls[path.relative_to(ROOT).as_posix()]=found
    assert set(calls)=={'src/heartopia_overlay/game_color_control.py'}
    assert calls['src/heartopia_overlay/game_color_control.py']<={'mouse_event','SetPhysicalCursorPos'}


def test_source_export_omits_private_and_generated_directories():
    spec=importlib.util.spec_from_file_location('prepare_source',ROOT/'scripts/prepare_source.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paths={path.relative_to(ROOT).as_posix() for path in module.source_files(ROOT)}
    assert not any(path.startswith(('local-archive/','experiments/','build/','dist/')) for path in paths)
    assert 'src/heartopia_overlay/game_color_control.py' in paths
    assert 'src/heartopia_overlay/swatch_detection.py' in paths
