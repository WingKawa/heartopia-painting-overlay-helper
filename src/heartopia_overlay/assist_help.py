"""初次使用教學與唯讀的連線／輸入檢查。"""
import os
import tkinter as tk
from tkinter import ttk, filedialog
import win32api
import win32con
import win32gui
from .assist_layout import fit_dialog
from .win.window import get_client_rect


def open_guide(app,section=None):
    import webbrowser
    from .paths import bundled
    guide = bundled('docs','guide','index.html')
    try:
        if not guide.is_file():
            raise OSError('找不到離線圖文教學檔案')
        url = guide.resolve().as_uri()+('#'+section if section else '')
        if not webbrowser.open(url,new=2):
            raise OSError('無法開啟預設瀏覽器')
        app.record_event('guide_opened')
        return True
    except OSError as error:
        app.record_event('guide_error',error=str(error))
        app.status.set(f'無法開啟教學：{error}')
        return False


def elevated(pid):
    import win32security
    process = win32api.OpenProcess(0x1000,False,pid)
    try:
        token = win32security.OpenProcessToken(process,win32con.TOKEN_QUERY)
        try:
            return bool(win32security.GetTokenInformation(token,win32security.TokenElevation))
        finally:
            token.Close()
    finally:
        process.Close()


def diagnostic_report(app):
    from .version import VERSION
    import win32process
    lines = [f'版本：{VERSION}',f'工具視窗：{app.root.state()}',f'遊戲連線：{app.connection_text.get()}',
             f'快捷鍵：{app.last_shortcut}',f'曾收到右鍵：{getattr(app,"right_seen",False)}',
             f'右鍵按下：{bool(win32api.GetAsyncKeyState(win32con.VK_RBUTTON)&0x8000)}',
             f'同步移動：{app.sync_drag.get()}；方向鍵微調：{app.arrow_nudge.get()}',
             f'疊層顯示：{app.enabled}；對齊模式：{app.aligning}']
    picker = getattr(app,'picker',None)
    if getattr(picker,'right_drag_events',None) is not None:
        lines.append('右鍵同步：滑鼠事件累計（按下／移動／放開）；攔截器失效時使用輪詢備援。')
    lines.append('快捷鍵／取色／方向鍵攔截器：'+(str(picker.error) if getattr(picker,'error',None) else
                 '運作中' if getattr(picker,'thread',None) and picker.thread.is_alive() else '未啟用'))
    try:
        tool_admin = elevated(os.getpid())
        lines.append(f'工具以系統管理員執行：{tool_admin}')
        if app.hwnd and win32gui.IsWindow(app.hwnd):
            rect = get_client_rect(app.hwnd)
            lines.extend([f'遊戲標題：{win32gui.GetWindowText(app.hwnd)}',f'遊戲客戶區：{rect.width}×{rect.height}',
                          f'遊戲在前景：{win32gui.GetForegroundWindow()==app.hwnd}'])
            _,pid = win32process.GetWindowThreadProcessId(app.hwnd)
            game_admin = elevated(pid)
            lines.append(f'遊戲以系統管理員執行：{game_admin}')
            if game_admin and not tool_admin:
                lines.append('遊戲權限高於工具，Windows 可能限制輸入偵測與選色。')
    except Exception as error:
        lines.append(f'權限／視窗資訊無法讀取：{error}')
    lines.append('筆電／多媒體鍵盤：若功能鍵沒有收到，請確認 F5～F9 是否需要搭配 Fn。')
    if getattr(app,'log',None):
        lines.append('診斷紀錄：'+('僅保存在記憶體' if not app.log.directory else '已啟用本機循環紀錄（最多約1.5MB）'))
        if app.log.write_error:
            lines.append('本機紀錄無法寫入，仍可匯出目前記憶體紀錄：'+app.log.write_error)
    return '\n'.join(lines)


class Diagnostics:
    def __init__(self,app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title('功能檢查')
        self.window.transient(app.root)
        pane = ttk.Frame(self.window,padding=16)
        pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='可切回遊戲測試 F5～F9 與右鍵，再回來查看是否收到。',wraplength=650).pack(anchor='w')
        ttk.Label(pane,text='重現問題後按「匯出診斷紀錄…」，將 ZIP 交給開發者分析。',wraplength=650).pack(anchor='w',pady=4)
        self.text = tk.Text(pane,width=80,height=19,wrap='word')
        self.text.pack(fill='both',expand=True,pady=10)
        ttk.Button(pane,text='複製檢查資訊',command=self.copy).pack(side='left')
        ttk.Button(pane,text='匯出診斷紀錄…',command=self.export,style='Primary.TButton').pack(side='left',padx=8)
        ttk.Button(pane,text='關閉',command=self.close).pack(side='right')
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.timer = None
        self.previous = None
        self.refresh()
        fit_dialog(self.window,app.root,760,550)

    def refresh(self):
        report = diagnostic_report(self.app)
        if report!=self.previous:
            c = self.app.theme_colors
            self.text.configure(state='normal',bg=c['panel'],fg=c['text'],insertbackground=c['text'])
            self.text.delete('1.0','end')
            self.text.insert('1.0',report)
            self.text.configure(state='disabled')
            self.previous = report
        self.timer = self.window.after(300,self.refresh)

    def copy(self):
        self.window.clipboard_clear()
        self.window.clipboard_append(diagnostic_report(self.app))

    def export(self):
        from datetime import datetime
        path = filedialog.asksaveasfilename(parent=self.window,title='匯出診斷紀錄',
                initialfile='Heartopia-診斷紀錄-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip',
                defaultextension='.zip',filetypes=[('ZIP壓縮檔','*.zip')],confirmoverwrite=True)
        if not path:
            return
        try:
            self.app.record_event('diagnostics_export')
            self.app.log.export(path,diagnostic_report(self.app))
            self.app.status.set('已匯出診斷紀錄，可將 ZIP 交給開發者。')
        except (OSError,ValueError) as error:
            self.app.status.set(f'匯出診斷紀錄失敗：{error}')

    def close(self):
        if self.timer:
            self.window.after_cancel(self.timer)
        self.window.destroy()
