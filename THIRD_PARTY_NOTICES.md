# 第三方元件與素材

本專案程式碼採用 [MIT License](LICENSE)。第三方元件依其各自授權散布；MIT 不授予遊戲商標、遊戲畫面或其他第三方作品的權利。

## 執行環境與套件

| 元件 | 授權與聲明 |
| --- | --- |
| Python | PSF 授權及 Python 發行版附帶的元件聲明。 |
| Tcl/Tk | Tcl/Tk 授權，隨 GUI 執行環境散布。 |
| Pillow | MIT-CMU，以及 wheel 附帶影像函式庫的授權。 |
| NumPy | BSD-3-Clause，以及 wheel 附帶 OpenBLAS、LAPACK、GCC runtime 等元件的授權。 |
| mss | MIT。 |
| pywin32 | 依散布元件保留對應授權原文。 |
| PyInstaller | GPL 及 bootloader exception；runtime hooks 另適用 Apache-2.0 等條款。 |

免安裝版的 `THIRD_PARTY_LICENSES` 包含從建置環境收集的授權原文與版本清單。更新套件或原生函式庫後需重新收集並檢查對應聲明，詳見 [建置說明](docs/BUILDING.md)。

本程式透過 Pillow 使用 FreeType 程式碼，部分功能基於 FreeType Team 的成果（https://freetype.org）。相關版權與授權原文保留於 Pillow 的 LICENSE。

This product includes software developed by the OpenSSL Project for use in the OpenSSL Toolkit. (http://www.openssl.org/)

## 色盤資料

`data/palette.json` 由 `scripts/measure_palette.py` 根據遊戲色盤截圖及指定取樣範圍產生。[量測資料](data/palette_sources/2026-10-31/README.md) 包含截圖、SHA256、座標及逐色結果，可重新產生並驗證色盤。

量測值代表截圖中色盤 UI 的顏色，不是直接取得遊戲記憶體中的資料，也不代表畫布上的實際渲染色。

## 教學與測試圖片

- 遊戲截圖用於教學及辨識測試。畫面、名稱及商標的權利屬於各原權利人。
- 工具教學截圖中的小屋範例由 `scripts/guide_demo.py` 繪製；功能檢查截圖來自該示範環境。
- 截圖上的教學標示不改變原始遊戲素材的權利歸屬。

本工具與遊戲營運方無隸屬或背書關係。軟體授權不代表遊戲營運方允許使用第三方工具。
