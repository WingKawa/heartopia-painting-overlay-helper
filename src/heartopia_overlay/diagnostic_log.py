"""有容量上限的本機診斷紀錄，不保存作品內容或一般鍵盤輸入。"""
from collections import deque
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import platform
import sys
import threading
import traceback
import zipfile


class DiagnosticLog:
    def __init__(self,directory=None,*,max_bytes=512*1024,backups=2):
        self.directory = Path(directory) if directory else None
        self.events = deque(maxlen=1000)
        self.states = {}
        self.lock = threading.RLock()
        self.write_error = None
        self.logger = logging.Logger(f'assist-{id(self)}',level=logging.INFO)
        self.handler = None
        self.closed = False
        if self.directory:
            owner = self
            class Handler(RotatingFileHandler):
                def handleError(self,record):
                    owner.write_error = type(sys.exc_info()[1]).__name__
            try:
                self.directory.mkdir(parents=True,exist_ok=True)
                self.handler = Handler(self.directory/'assist.jsonl',maxBytes=max_bytes,
                                       backupCount=backups,encoding='utf-8')
                self.handler.setFormatter(logging.Formatter('%(message)s'))
                self.logger.addHandler(self.handler)
            except OSError as error:
                self.write_error = type(error).__name__
        from .version import VERSION
        self.record('startup',version=VERSION,windows=platform.version(),
                    python=platform.python_version(),architecture=platform.machine(),frozen=bool(getattr(sys,'frozen',False)))

    def clean(self,value):
        """例外堆疊以替代符號隱去本機使用者與程式路徑。"""
        text = str(value)
        from .paths import userdata
        for path,label in ((str(Path.home()),'<USER>'),(str(userdata()),'<APP>')):
            text = text.replace(path,label).replace(path.replace('\\','/'),label)
        return text[:16000]

    def record(self,event,**fields):
        with self.lock:
            if self.closed:
                return
            fields = {key:self.clean(value) if isinstance(value,str) else value for key,value in fields.items()}
            line = json.dumps(dict(time=datetime.now(timezone.utc).isoformat(),event=event,**fields),
                              ensure_ascii=False,default=str,allow_nan=False)
            self.events.append(line)
            if self.handler:
                self.logger.info(line)

    def state(self,event,**fields):
        with self.lock:
            if self.states.get(event)!=fields:
                self.states[event] = dict(fields)
                self.record(event,**fields)

    def exception(self,event,error,tb=None):
        self.record(event,type=type(error).__name__,traceback=''.join(traceback.format_exception(type(error),error,tb or error.__traceback__)))

    def export(self,path,report):
        """僅封裝已知紀錄檔及檢查資訊，不掃描使用者資料夾。"""
        with self.lock:
            if self.directory and Path(path).resolve() in {(self.directory/name).resolve() for name in ('assist.jsonl','assist.jsonl.1','assist.jsonl.2')}:
                raise ValueError('請另存為 ZIP，不要覆蓋正在使用的紀錄檔。')
            if self.handler:
                self.handler.flush()
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('diagnostics.txt',self.clean(report))
                archive.writestr('current-session.jsonl','\n'.join(self.events)+'\n')
                archive.writestr('README.txt','本檔案由使用者手動匯出。時間為 UTC。包含環境、連線、工具操作及錯誤紀錄；不包含作品、截圖或一般打字內容。\n'
                                 f'本機紀錄寫入狀態：{self.write_error or "正常"}\n')
                if self.directory:
                    for name in ('assist.jsonl','assist.jsonl.1','assist.jsonl.2'):
                        source = self.directory/name
                        if source.is_file():
                            archive.write(source,'logs/'+name)

    def close(self):
        with self.lock:
            if self.handler:
                self.handler.close()
            self.closed = True
