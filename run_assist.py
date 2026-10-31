"""啟動繪畫疊層小幫手，並記錄啟動與執行錯誤。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
if __name__ == "__main__":
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        from heartopia_overlay.smoke_check import run
        raise SystemExit(run(sys.argv[2]))
    from heartopia_overlay.diagnostic_log import DiagnosticLog
    from heartopia_overlay.paths import userdata
    log = DiagnosticLog(userdata('logs'))
    try:
        from heartopia_overlay.assist import main
        main(log=log)
    except Exception as error:
        log.exception('startup_or_runtime_error',error)
        import ctypes
        from heartopia_overlay.version import APP_NAME
        ctypes.windll.user32.MessageBoxW(None,
            '程式啟動或執行失敗。\n診斷紀錄位於程式旁的 logs 資料夾。\n\n'+type(error).__name__,
            APP_NAME,16)
        raise SystemExit(1)
    finally:
        log.close()
