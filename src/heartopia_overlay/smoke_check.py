"""打包驗證入口：視窗保持隱藏，不要求安裝 Python 或啟動遊戲。"""
import json
import pathlib
import traceback


def run(report_path):
    root = None
    app = None
    result = {'ok': False}
    try:
        import tkinter as tk
        from .assist import Assist
        from .target import load_target
        from .win.dpi import ensure_dpi_aware
        ensure_dpi_aware()
        root = tk.Tk()
        root.withdraw()
        failures = []
        root.report_callback_exception = lambda kind, value, tb: failures.append(str(value))
        app = Assist(root,persist=False)
        assert not app.auto_color_allowed(), '首次啟動自動選色必須關閉'
        from .version import APP_NAME
        assert APP_NAME in root.title()
        root.update_idletasks()
        import tempfile
        from PIL import Image,ImageDraw
        from .image_conversion import convert_image, ColorAdjustments, target_image
        from .grid_calibration import measure_grid
        from .palette_calibration import calibrate_palette
        from .game_color import observe_palette
        from .session import pack_grid,unpack_grid
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp)/'arbitrary.png'
            Image.new('RGBA',(317,83),(*app.palette.by_index(0).rgb,255)).save(source)
            app.target = load_target(source,unrestricted=True)
            adjusted_source = Image.new('RGBA',(2,1),(220,220,220,255))
            adjusted_source.putpixel((1,0),(0,0,0,0))
            adjusted = convert_image(adjusted_source,2,1,'拉伸',adjustments=ColorAdjustments(whites=75,blacks=30,temperature=-10))
            exported = pathlib.Path(tmp)/'adjusted.png'
            target_image(adjusted).save(exported,format='PNG')
            assert load_target(exported,unrestricted=True).cells==adjusted.cells
            assert adjusted.cells[0][1] is None
            import zipfile
            report = pathlib.Path(tmp)/'diagnostics.zip'
            app.log.export(report,'smoke check')
            with zipfile.ZipFile(report) as archive:
                assert archive.testzip() is None and 'current-session.jsonl' in archive.namelist()
        from .paths import bundled
        assert bundled('docs','guide','index.html').is_file()
        for name in ('prepare','align','draw','convert','diagnostics'):
            assert bundled('docs','guide','assets',name+'.png').is_file()
        import win32security
        from .assist_help import diagnostic_report
        assert '快捷鍵' in diagnostic_report(app)
        assert not root.attributes('-topmost')
        assert (app.target.w,app.target.h)==(317,83)
        converted = convert_image(Image.new('RGB',(80,50),'orange'),20,10,crop=(10,5,70,45))
        assert (converted.w,converted.h)==(20,10)
        assert unpack_grid(pack_grid(converted)).cells==converted.cells
        grid = Image.new('RGB',(800,600),'white')
        draw = ImageDraw.Draw(grid)
        for x in range(10,800,40):
            draw.rectangle((x,0,x+3,599),fill='#9e9e9e')
        for y in range(10,600,40):
            draw.rectangle((0,y,799,y+3),fill='#9e9e9e')
        measured = measure_grid(grid,(0,0,800,600),(800,600))
        assert abs(measured.pitch-40)<.01
        palette_image = Image.new('RGB',(1920,1080),'#76594e')
        draw = ImageDraw.Draw(palette_image)
        for color in app.palette.by_group(2):
            x = 1727 if color.slot%2 else 1850
            y = 411+91*((color.slot-1)//2)
            draw.rectangle((x-18,y-20,x+18,y+20),fill=color.rgb)
        draw.rectangle((1774,295,1814,357),outline='white',width=3)
        calibration,group = calibrate_palette(palette_image,(1680,280,1915,825),palette_image.size,app.palette)
        import numpy as np
        assert group==2 and observe_palette(np.asarray(palette_image),app.palette,calibration).group==2
        assert app.row_entry.winfo_class()=='TEntry' and app.col_entry.winfo_class()=='TEntry'
        app.clip = (0,0,800,600)
        app.render()
        app.ui_scale.set('200%')
        app.resize_ui()
        root.update_idletasks()
        from .assist_theme import THEMES
        for name in THEMES:
            app.theme_name.set(name)
            app.change_theme()
            root.update_idletasks()
        assert app.row_entry.winfo_class()=='TEntry'
        app.render()
        import sys
        assert 'heartopia_overlay.game_color_control' not in sys.modules, '選色控制器應在使用時才載入'
        from . import game_color_control,grid_calibration_dialog,palette_calibration_dialog
        assert game_color_control.GameColorControl and grid_calibration_dialog.GridCalibrationDialog
        assert palette_calibration_dialog.PaletteCalibrationDialog
        assert len(app.palette.colors)==125
        assert app.map_photo is not None
        assert not failures, failures
        result = {'ok': True, 'palette_colors': 125, 'image_preview': True,
                  'arbitrary_dimensions': [app.target.w,app.target.h],
                  'ui_scale_200_percent': True, 'optional_color_control_loaded_lazily': True,
                  'conversion_and_crop': True,'pixel_snapshot_roundtrip': True,
                  'color_adjustments':True,'png_export_roundtrip':True,
                  'grid_calibration': True,'palette_calibration': True,
                  'single_color_selection_available': True,'game_input_executed': False,
                  'themes': list(THEMES),'version':__import__('heartopia_overlay.version',fromlist=['VERSION']).VERSION}
        import ctypes
        result.update(diagnostic_export=True,offline_guide=True,main_window_topmost=False,
                      console_attached=bool(ctypes.windll.kernel32.GetConsoleWindow()))
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if root is not None:
            if app is not None:
                app.picker.close()
            root.destroy()
        pathlib.Path(report_path).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1
