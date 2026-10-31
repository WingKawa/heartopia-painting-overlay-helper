# 開發說明

程式入口為 `run_assist.py`，Python 套件位於 `src/heartopia_overlay`。工具以 Tkinter 建立主視窗及獨立的疊層視窗，讓玩家依參考格子手動繪畫。

## 模組分工

| 範圍 | 模組 |
| --- | --- |
| 主介面、主題與排版 | `assist.py`、`assist_ui.py`、`assist_layout.py`、`assist_theme.py` |
| 作品、小地圖與疊層幾何 | `target.py`、`composition.py`、`manual_overlay.py`、`overlay_raster.py` |
| 圖片轉色與裁切 | `image_conversion.py`、`conversion_dialog.py`、`crop_selection.py` |
| 格線與色盤校正 | `grid_calibration*.py`、`palette_calibration*.py`、`swatch_detection.py` |
| 輸入觀察與拖曳同步 | `color_picker.py`、`right_drag_events.py`、`drag_sync.py` |
| 可選的單次選色 | `auto_color_notice.py`、`game_color.py`、`game_color_control.py` |
| 視窗、DPI 與暫時截圖 | `win/window.py`、`win/dpi.py`、`win/screen.py` |
| 狀態與問題回報 | `session.py`、`diagnostic_log.py`、`assist_help.py`、`interaction_metrics.py` |

## 座標與輸入

視窗、截圖及疊層位置使用螢幕實體像素。取得座標前需設定 DPI awareness；修改視窗或輸入處理時應檢查多螢幕及不同 DPI 的情況。

輸入 hook 觀察快捷鍵、取色與拖曳；取色模式會攔截用來選取疊層格子的點擊。右鍵同步只調整疊層位置，不向遊戲傳送畫布拖曳操作。

主動移動及點擊遊戲游標的程式集中於 `game_color_control.py`，需由玩家啟用自動選色，再按 F7 或選色按鈕觸發。每次操作前檢查遊戲焦點、視窗尺寸、色盤及中止條件。此功能不填畫畫布；修改時須保留預設關閉、啟用說明與取消機制。

## 資料與狀態

`data/palette.json` 定義 125 色及色號；[色盤量測資料](../data/palette_sources/2026-10-31/README.md) 提供可重建的來源。

作品像素快照與設定存放於 `config/assist_state.json`。改動顏色 index、座標或保存格式時，需檢查既有工作階段的相容性。設定及診斷紀錄寫入執行檔旁的目錄，不寫入封裝資源目錄。

## 測試

安裝 `requirements-dev.txt` 後執行 `python -m pytest`。部分測試會建立 Tk 視窗，需在有桌面環境的 Windows 執行；遊戲互動以替身模擬，不會點擊實際遊戲。

測試涵蓋圖片轉色、裁切、格線與色盤辨識、拖曳事件、輸入中止、工作階段還原及封裝。`test_source_scope.py` 檢查輸入操作的模組邊界，`test_purity.py` 確認色盤與幾何模組不依賴遊戲視窗或輸入 API。

建置、授權收集與發行步驟見 [BUILDING.md](BUILDING.md)。
