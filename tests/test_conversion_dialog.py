def test_conversion_dialog_async_preview_apply_and_cancel():
    import subprocess
    import sys
    subprocess.run([sys.executable,'-c',
                    "import sys; sys.path.insert(0,'src'); from tests.test_conversion_dialog import check_dialog; check_dialog()"],check=True)


def check_dialog():
    import tempfile
    import pathlib
    import time
    import tkinter as tk
    from PIL import Image
    from heartopia_overlay.conversion_dialog import ConversionDialog
    root = tk.Tk()
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    applied = []
    def wait_for(predicate):
        deadline = time.monotonic()+8
        while not predicate() and time.monotonic()<deadline:
            root.update()
            time.sleep(.01)
        assert predicate()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)/'photo.jpg'
            Image.new('RGB',(30,20),(123,47,190)).save(path)
            dialog = ConversionDialog(root,path,applied.append)
            dialog.window.withdraw()
            wait_for(lambda: dialog.result is not None)
            assert (dialog.result.w,dialog.result.h)==(30,20)
            original_cells = dialog.result.cells
            dialog.size_presets.choice.set('16:9　30×18')
            dialog.size_presets.select()
            wait_for(lambda:dialog.result is not None)
            assert (dialog.result.w,dialog.result.h)==(30,18)
            dialog.width.set('30')
            dialog.height.set('20')
            wait_for(lambda:dialog.result is not None)
            assert dialog.size_presets.choice.get()=='自訂尺寸'
            assert dialog.result.cells==original_cells
            dialog.adjustments['brightness'].set(80)
            assert dialog.result is None
            assert str(dialog.apply_button.cget('state'))=='disabled'
            wait_for(lambda: dialog.result is not None)
            assert dialog.result.cells!=original_cells
            from unittest.mock import patch
            from heartopia_overlay.target import load_target
            saved = pathlib.Path(tmp)/'adjusted.png'
            latest = dialog.result
            with patch('heartopia_overlay.conversion_dialog.filedialog.asksaveasfilename',return_value=str(saved)):
                dialog.save_as()
            assert load_target(saved,unrestricted=True).cells==latest.cells
            assert dialog.result is latest and not applied and not dialog.closed
            with patch('heartopia_overlay.conversion_dialog.filedialog.asksaveasfilename',return_value=''):
                dialog.save_as()
            with patch('heartopia_overlay.conversion_dialog.filedialog.asksaveasfilename',return_value=str(pathlib.Path(tmp)/'missing'/'out.png')):
                dialog.save_as()
            assert dialog.status.get().startswith('儲存失敗')
            assert dialog.result is latest
            dialog.reset_adjustments()
            assert str(dialog.save_button.cget('state'))=='disabled'
            wait_for(lambda: dialog.result is not None)
            assert all(value.get()==0 for value in dialog.adjustments.values())
            assert dialog.result.cells==original_cells
            dialog.width.set('13')
            assert dialog.result is None
            assert str(dialog.apply_button.cget('state'))=='disabled'
            dialog.request()
            # 連續兩次設定，舊的工作即使先完成也不可變成可套用結果。
            dialog.width.set('17')
            dialog.request()
            wait_for(lambda: dialog.result is not None)
            assert dialog.result.w==17
            assert len(dialog.photos)==2
            # 預覽座標與原圖座標換算後，拖曳選區會使目前結果失效並重新轉換。
            from types import SimpleNamespace
            dialog.lock_ratio.set(False)
            dialog.crop_enabled.set(True)
            dialog.crop_model.box=(0,0,15,20)
            dialog.crop_options_changed()
            wait_for(lambda: dialog.result is not None)
            ox,oy,sx,sy = dialog.source_display
            def point(x,y):
                return SimpleNamespace(x=ox+x*sx,y=oy+y*sy)
            dialog.crop_start(point(7,10))
            dialog.crop_move(point(20,10))
            assert dialog.result is None
            dialog.crop_end(point(20,10))
            wait_for(lambda: dialog.result is not None)
            assert dialog.crop_model.box==(13,0,28,20)
            assert len(dialog.original.find_withtag('crop'))>0
            dialog.crop_enabled.set(False)
            dialog.crop_options_changed()
            wait_for(lambda: dialog.result is not None)
            dialog.apply()
            assert len(applied)==1 and applied[0].w==17
            dialog = ConversionDialog(root,path,applied.append)
            dialog.window.withdraw()
            dialog.close()
            assert len(applied)==1
            transparent = pathlib.Path(tmp)/'transparent.png'
            image = Image.new('RGBA',(2,1),(255,255,255,255))
            image.putpixel((1,0),(0,0,0,0))
            image.save(transparent)
            before = transparent.read_bytes()
            dialog = ConversionDialog(root,transparent,applied.append)
            dialog.window.withdraw()
            wait_for(lambda: dialog.result is not None)
            with patch('heartopia_overlay.conversion_dialog.filedialog.asksaveasfilename',return_value=str(saved)):
                dialog.save_as()
            with Image.open(saved) as exported:
                assert exported.size==(2,1)
                assert exported.convert('RGBA').getpixel((1,0))[3]==0
            assert load_target(saved,unrestricted=True).cells==dialog.result.cells
            assert transparent.read_bytes()==before
            dialog.close()
            assert not errors
    finally:
        root.destroy()
