"""四種介面主題；只調整工具介面，不改變作品或遊戲疊層的色彩。"""
from tkinter import ttk


THEMES = {
    '清爽青綠': dict(bg='#f1f5f3', panel='#ffffff', text='#273a31', muted='#596e61',
                 line='#d9e4dc', soft='#e5f1e9', accent='#216b4d', on='#ffffff', map='#e5ece7'),
    '沉靜墨藍': dict(bg='#141d2a', panel='#1d2939', text='#edf2fb', muted='#b0bfd5',
                 line='#384b64', soft='#293b54', accent='#a8c5ff', on='#182d4a', map='#101924'),
    '純白': dict(bg='#f3f4f5', panel='#ffffff', text='#242629', muted='#60656c',
               line='#d5d8dc', soft='#e9ecef', accent='#343b45', on='#ffffff', map='#e8eaed'),
    '純黑': dict(bg='#111214', panel='#1b1d20', text='#f0f1f2', muted='#b4b8be',
               line='#41454c', soft='#2d3035', accent='#e1e4e8', on='#191b1e', map='#101113'),
}
DEFAULT_THEME = '清爽青綠'


def configure_controls(root, colors, factor=1):
    """大拖曳鈕與勾號使用狀態圖片，隨 DPI／介面倍率調整。"""
    from PIL import Image, ImageDraw, ImageTk
    style = ttk.Style(root)
    scale = root.winfo_fpixels('1i')/96*factor
    key = (tuple(colors.items()),round(scale,4))
    cache = getattr(root,'_assist_control_images',{})
    if key not in cache:
        serial = len(cache)
        size = max(18,round(22*scale))
        def picture(width,height,paint):
            image = Image.new('RGBA',(width*3,height*3))
            paint(ImageDraw.Draw(image),3)
            return ImageTk.PhotoImage(image.resize((width,height),Image.Resampling.LANCZOS),master=root)
        def thumb(draw,s):
            draw.ellipse((s,s,(size-1)*s,(size-1)*s),fill=colors['accent'],outline=colors['panel'],width=max(1,round(2*scale*s)))
        slider = picture(size,size,thumb)
        track_height = max(3,round(4*scale))
        track = picture(12,track_height,lambda d,s:d.rectangle((0,0,12*s,track_height*s),fill=colors['line']))
        check_size = max(18,round(20*scale))
        def checkbox(selected):
            def paint(draw,s):
                edge = (check_size-1)*s
                draw.rounded_rectangle((s,s,edge,edge),radius=3*scale*s,
                                       fill=colors['accent'] if selected else colors['panel'],
                                       outline=colors['accent'] if selected else colors['muted'],width=max(1,round(scale*s)))
                if selected:
                    draw.line([(check_size*.23*s,check_size*.51*s),(check_size*.43*s,check_size*.72*s),
                               (check_size*.79*s,check_size*.29*s)],fill=colors['on'],width=max(2,round(2.3*scale*s)),joint='curve')
            return picture(check_size,check_size,paint)
        off,on = checkbox(False),checkbox(True)
        prefix = f'Assist{serial}'
        slider_element,track_element,check_element = (prefix+'.Horizontal.Scale.slider',prefix+'.Horizontal.Scale.trough',prefix+'.Checkbutton.indicator')
        style.element_create(slider_element,'image',slider)
        style.element_create(track_element,'image',track,border=2,sticky='ew')
        style.element_create(check_element,'image',off,('selected',on),border=0,sticky='')
        cache[key] = (slider_element,track_element,check_element,(slider,track,off,on))
        root._assist_control_images = cache
    slider_element,track_element,check_element,_ = cache[key]
    style.layout('Horizontal.TScale',[(track_element,{'sticky':'ew','children':[(slider_element,{'side':'left','sticky':''})]})])
    style.layout('TCheckbutton',[('Checkbutton.padding',{'sticky':'nswe','children':[
        (check_element,{'side':'left','sticky':''}),
        ('Checkbutton.focus',{'side':'left','sticky':'w','children':[('Checkbutton.label',{'sticky':'nswe'})]})]})])
    style.configure('TCheckbutton',padding=(4,6),indicatormargin=(0,0,8,0))
    padding = tuple(round(value*scale) for value in (18,8))
    selected_padding = tuple(round(value*scale) for value in (22,12))
    style.configure('TNotebook.Tab',padding=padding)
    style.map('TNotebook.Tab',padding=[('selected',selected_padding),('!selected',padding)],
              background=[('selected',colors['accent']),('active',colors['soft'])],
              foreground=[('selected',colors['on']),('!selected',colors['muted'])])


def apply_theme(app, name):
    """共用 ttk 樣式亦套用至轉圖與校正彈窗。"""
    name = name if name in THEMES else DEFAULT_THEME
    c = THEMES[name]
    app.theme_name.set(name)
    app.theme_colors = c
    app.root._assist_theme_colors = c
    style = ttk.Style(app.root)
    # Windows 原生佈景會忽略部分背景與字色；clam 支援完整的控制項配色。
    if style.theme_use() != 'clam':
        style.theme_use('clam')
    style.configure('.', background=c['bg'], foreground=c['text'],
                    bordercolor=c['line'], lightcolor=c['line'], darkcolor=c['line'],
                    troughcolor=c['soft'], selectbackground=c['accent'], selectforeground=c['on'])
    style.configure('TButton', background=c['panel'], foreground=c['text'], padding=(12, 7), borderwidth=1)
    style.map('TButton', background=[('disabled', c['bg']), ('pressed', c['soft']), ('active', c['soft'])],
              foreground=[('disabled', c['muted'])])
    style.configure('Primary.TButton', background=c['accent'], foreground=c['on'])
    style.map('Primary.TButton', background=[('disabled', c['soft']), ('pressed', c['accent']), ('active', c['accent'])],
              foreground=[('disabled', c['muted']), ('!disabled', c['on'])])
    style.configure('Note.TLabel', foreground=c['muted'])
    style.configure('TLabelframe', borderwidth=1, relief='solid')
    style.configure('TLabelframe', background=c['panel'])
    for widget in ('TFrame', 'TLabel', 'TCheckbutton', 'TRadiobutton'):
        style.configure('Card.'+widget, background=c['panel'])
    style.configure('CardNote.TLabel', background=c['panel'], foreground=c['muted'])
    style.configure('TLabelframe.Label', background=c['panel'], foreground=c['accent'], padding=(0, 4))
    style.configure('TNotebook', tabmargins=(0, 0, 0, 8), borderwidth=0)
    style.configure('TNotebook.Tab', padding=(18, 9), background=c['soft'], foreground=c['muted'])
    style.map('TNotebook.Tab', background=[('selected', c['panel']), ('active', c['soft'])],
              foreground=[('selected', c['accent'])])
    for widget in ('TEntry', 'TSpinbox', 'TCombobox'):
        style.configure(widget, fieldbackground=c['panel'], background=c['soft'],
                        foreground=c['text'], insertcolor=c['text'], padding=5, arrowcolor=c['text'])
        style.map(widget, fieldbackground=[('readonly', c['panel']), ('disabled', c['bg'])],
                  foreground=[('disabled', c['muted']), ('readonly', c['text'])],
                  selectbackground=[('readonly', c['panel'])], selectforeground=[('readonly', c['text'])])
    for widget in ('TCheckbutton', 'TRadiobutton'):
        style.configure(widget, padding=(4, 5), indicatorbackground=c['panel'], indicatorforeground=c['accent'])
        style.map(widget, background=[('active', c['soft'])],
                  indicatorbackground=[('selected', c['accent'])], indicatorforeground=[('selected', c['on'])])
    style.configure('Horizontal.TScale', background=c['bg'], troughcolor=c['soft'])
    for widget in ('Vertical.TScrollbar', 'Horizontal.TScrollbar'):
        style.configure(widget, background=c['line'], arrowcolor=c['muted'], borderwidth=0)
    app.root.configure(background=c['bg'])
    app.root.option_add('*TCombobox*Listbox.background', c['panel'])
    app.root.option_add('*TCombobox*Listbox.foreground', c['text'])
    app.root.option_add('*TCombobox*Listbox.selectBackground', c['accent'])
    app.root.option_add('*TCombobox*Listbox.selectForeground', c['on'])
    # Tk 會重用已開啟過的下拉選單，需同步更新既有的清單。
    def refresh_menus(parent):
        for child in parent.winfo_children():
            if isinstance(child, ttk.Combobox):
                listing = str(child)+'.popdown.f.l'
                if app.root.tk.call('winfo', 'exists', listing):
                    app.root.tk.call(listing, 'configure', '-background', c['panel'],
                                     '-foreground', c['text'], '-selectbackground', c['accent'],
                                     '-selectforeground', c['on'])
            refresh_menus(child)
    refresh_menus(app.root)
    if hasattr(app, 'layout'):
        app.layout.view.configure(background=c['bg'])
        app.minimap.configure(background=c['map'])
    if hasattr(app, 'swatch') and getattr(app, 'selected_color', None) is None:
        app.swatch.configure(background=c['soft'], foreground=c['text'])
    configure_controls(app.root,c,getattr(getattr(app,'layout',None),'factor',1))
    return c
