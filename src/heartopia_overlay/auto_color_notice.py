"""自動選色的首次啟用說明；預設關閉，不代表官方授權。"""
import tkinter as tk
from tkinter import ttk
from .assist_layout import fit_dialog, pause_overlay_for_dialog

NOTICE_VERSION = 1
NOTICE_TEXT = (
    '啟用後，每次按下選色按鈕或 F7，工具會等待你切回遊戲，再執行腳本，移動並點擊滑鼠以切換畫筆顏色。'
    '執行期間請暫停操作滑鼠，等待完成；可按 Esc 取消。\n\n'
    '遊戲營運方可能將此行為認定為不允許的自動化操作，並採取警告、停權或其他帳號處置。'
    '本工具為非官方第三方工具，未取得遊戲營運方的使用許可或背書。是否允許使用，以適用版本的最新官方協議、公告及營運方判定為準。'
    '請自行評估是否啟用，並承擔相關風險。\n\n'
    '不啟用也可使用疊層與取色功能，並自行在遊戲內選色。\n\n'
)


def ask_auto_color_consent(root,show_policy):
    window = tk.Toplevel(root)
    window.title('啟用自動選色')
    window.transient(root)
    pause_overlay_for_dialog(root,window)
    panel = ttk.Frame(window,padding=20)
    panel.pack(fill='both',expand=True)
    panel.columnconfigure(0,weight=1)
    panel.rowconfigure(1,weight=1)
    ttk.Label(panel,text='啟用前，請了解自動選色的操作與風險。').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,12))
    colors = getattr(root,'_assist_theme_colors',{})
    text = tk.Text(panel,wrap='word',width=64,height=15,font='TkDefaultFont',
                   bg=colors.get('panel','white'),fg=colors.get('text','black'),
                   relief='flat',padx=10,pady=10)
    text.insert('1.0',NOTICE_TEXT)
    text.configure(state='disabled')
    text.grid(row=1,column=0,sticky='nsew')
    scroll = ttk.Scrollbar(panel,orient='vertical',command=text.yview)
    scroll.grid(row=1,column=1,sticky='ns')
    text.configure(yscrollcommand=scroll.set)
    ttk.Button(panel,text='官方規章與資料使用說明',command=show_policy).grid(row=2,column=0,columnspan=2,sticky='w',pady=12)
    result = [False]
    def finish(accepted=False):
        result[0] = accepted
        window.destroy()
    buttons = ttk.Frame(panel)
    buttons.grid(row=3,column=0,columnspan=2,sticky='e')
    cancel = ttk.Button(buttons,text='取消',command=finish)
    cancel.pack(side='left',padx=8)
    ttk.Button(buttons,text='了解風險並啟用',command=lambda:finish(True),style='Primary.TButton').pack(side='left')
    window.protocol('WM_DELETE_WINDOW',finish)
    window.bind('<Escape>',lambda event:finish())
    dpi = root.winfo_fpixels('1i')/96
    fit_dialog(window,root,round(720*dpi),round(600*dpi))
    window.grab_set()
    cancel.focus_set()
    window.wait_window()
    return result[0]
