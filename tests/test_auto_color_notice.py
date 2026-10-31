from types import SimpleNamespace
import pytest
from heartopia_overlay.assist import Assist
from heartopia_overlay.auto_color_notice import NOTICE_VERSION
from heartopia_overlay.assist_help import open_guide


class Value:
    def __init__(self,value=None):
        self.value=value
    def get(self):
        return self.value
    def set(self,value):
        self.value=value


def instance():
    app=Assist.__new__(Assist)
    app.root=object()
    app.auto_color_enabled=Value(False)
    app.auto_color_notice_version=0
    app.selected_color=7
    app.game_selection=None
    app.status=Value()
    app.button={}
    app.game_color_button=SimpleNamespace(configure=lambda **kw:app.button.update(kw))
    app.record_event=lambda *args,**kw:None
    app.save_session=lambda:True
    return app


@pytest.mark.parametrize('enabled,version',[(False,0),(False,NOTICE_VERSION),(True,0),(True,True)])
def test_f7_cannot_start_without_explicit_current_consent(enabled,version):
    app=instance()
    app.auto_color_enabled.set(enabled)
    app.auto_color_notice_version=version
    app.resolve_game=lambda:pytest.fail('must not access the game')
    app.select_game_color()
    assert app.game_selection is None
    assert '尚未啟用' in app.status.get()


@pytest.mark.parametrize('accepted',[False,True])
def test_first_enable_requires_consent_before_saving(monkeypatch,accepted):
    app=instance()
    app.auto_color_enabled.set(True)
    def consent(*args):
        assert not app.auto_color_allowed()
        return accepted
    monkeypatch.setattr('heartopia_overlay.auto_color_notice.ask_auto_color_consent',consent)
    saved=[]
    app.save_session=lambda:saved.append(app.auto_color_allowed()) or True
    app.change_auto_color()
    assert saved==[accepted]
    assert app.auto_color_allowed() is accepted
    assert app.button['state']==('normal' if accepted else 'disabled')


def test_disable_cancels_pending_action_and_reenable_remembers_consent(monkeypatch):
    app=instance()
    app.auto_color_notice_version=NOTICE_VERSION
    cancelled=[]
    def finish(message):
        cancelled.append(message)
        app.game_selection=None
    app.game_selection=SimpleNamespace(finish=finish)
    app.change_auto_color()
    assert cancelled and app.button['state']=='disabled'
    monkeypatch.setattr('heartopia_overlay.auto_color_notice.ask_auto_color_consent',lambda *args:pytest.fail('already accepted'))
    app.auto_color_enabled.set(True)
    app.change_auto_color()
    assert app.auto_color_allowed()
    app.selected_color=None
    app.update_game_color_button()
    assert app.button['state']=='disabled'


def test_policy_button_opens_the_policy_section(monkeypatch):
    opened=[]
    monkeypatch.setattr('webbrowser.open',lambda url,**kw:opened.append(url) or True)
    assert open_guide(instance(),'rules-and-privacy')
    assert opened[0].endswith('/docs/guide/index.html#rules-and-privacy')


def test_notice_buttons_remain_visible_and_close_defaults_to_cancel():
    # Other GUI tests create/destroy interpreters and patch Tcl paths. Check this
    # real dialog in a fresh process so interpreter state cannot leak into it.
    import subprocess
    import sys
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    script="import runpy,sys; sys.path.insert(0,'src'); runpy.run_path('tests/test_auto_color_notice.py')['_check_notice_layout']()"
    subprocess.run([sys.executable,'-c',script],cwd=root,check=True,timeout=30)


def _check_notice_layout():
    import tkinter as tk
    from tkinter import ttk
    from heartopia_overlay.auto_color_notice import ask_auto_color_consent
    root=tk.Tk()
    root.geometry('800x650+20+20')
    root.update()
    checked=[]
    def inspect():
        try:
            window=next(child for child in root.winfo_children() if isinstance(child,tk.Toplevel))
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            buttons=[child for child in descendants(window) if isinstance(child,ttk.Button)]
            root.update_idletasks()
            for button in buttons:
                assert 0<=button.winfo_rooty()-window.winfo_rooty()
                assert button.winfo_rooty()+button.winfo_height()<=window.winfo_rooty()+window.winfo_height()
            checked.append(True)
            next(button for button in buttons if button.cget('text')=='取消').invoke()
        except Exception as error:
            checked.append(error)
            for child in root.winfo_children():
                child.destroy()
    try:
        for scale in (1,2):
            root.tk.call('tk','scaling',scale)
            root.after(150,inspect)
            assert ask_auto_color_consent(root,lambda:None) is False
        assert checked==[True,True]
    finally:
        root.destroy()
