# 建置與發行

## 環境

建置 Windows x64 執行檔需在 Windows x64 上執行，並安裝含 Tcl/Tk 的 Python。已驗證的建置環境為 Python 3.10.8、Tcl/Tk 8.6.12 及 PyInstaller 6.22.2。

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-build.txt
.\venv\Scripts\python.exe -m pytest
```

軟體名稱與版本定義位於 `src/heartopia_overlay/version.py`，免安裝資料夾、EXE 及 ZIP 檔名由其中的 `APP_ID`、`VERSION` 產生。

## Windows 免安裝版

```powershell
.\venv\Scripts\python.exe -m PyInstaller assist.spec --distpath build/release-dist --workpath build/release-work
.\venv\Scripts\python.exe scripts/collect_third_party_notices.py build/release-notices
.\venv\Scripts\python.exe scripts/package_assist.py
```

ZIP 與 SHA256 檔會輸出到 `dist`。ZIP 包含 EXE、執行環境、離線教學、文字說明、MIT 授權及第三方授權原文，不包含使用者設定或診斷紀錄。

封裝腳本會執行已建置 EXE 的 `--smoke-test`，檢查啟動、轉圖、PNG 匯出、格線與色盤校正、離線教學和診斷匯出。此檢查不操作遊戲，也不代替實際遊戲測試。

封裝與授權收集不會覆蓋既有輸出。相同版本重建時，應先檢查並移走前次產物，或透過 `--source`、`--notices`、`--output` 指定新路徑。啟動檢查報告保存在 `build/release-checks`；若報告已存在，封裝會停止以避免誤用前次結果。

## 第三方授權

`scripts/collect_third_party_notices.py` 會從建置環境收集 Python、Tk、Pillow、NumPy、mss、pywin32 及 PyInstaller 等授權文字與版本。Tcl 授權原文存放於 `docs/licenses`；若建置環境的 Tcl 版本不同，需加入對應版本原文後才能封裝。

更新依賴後，應重新收集聲明並檢查實際包含的原生函式庫。遊戲素材與第三方授權範圍見 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

## 原始碼封裝

```powershell
.\venv\Scripts\python.exe scripts/prepare_source.py build/source-export
```

此腳本依明確清單複製來源、測試、文件及色盤資料，另產生 `SOURCE_MANIFEST.json`。輸出不包含 `.git`、虛擬環境、使用者設定、診斷紀錄或建置產物；不會修改 Git 索引。

## GitHub Release 與教學網站

1. 完成測試與乾淨解壓縮後的啟動檢查，確認教學、檔名及版號一致。
2. 為要發布的 commit 建立版本 tag，例如 `v0.1.1`，並建立對應 Release。
3. 附上免安裝 ZIP 及 `.zip.sha256`；可參考 `docs/release/RELEASE_NOTES_0.1.1.md` 撰寫功能與限制說明。
4. GitHub 自動產生的 `Source code` 壓縮檔是原始碼；README 的一般使用者下載入口應指向免安裝資產。

圖文教學是獨立靜態網站，入口為 `docs/guide/index.html`。儲存庫管理者可將 Pages 來源設為 GitHub Actions，再手動執行 `Publish guide (manual)` 工作流程；部署成功後才將網站網址加入 README。離線教學使用相同檔案。
