"""File → Projects: current draft, saved/recent projects and recovery copies."""
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTabWidget, QListWidget, QListWidgetItem, QFileDialog, QPushButton
from subtitle_ui import action
from subtitle_document import timestamp
from project_library import recent, describe
from ui_icons import tool_icon


class ProjectBrowser(QDialog):
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.choice=None
        self.setWindowTitle('Juicy Studio · Projects');self.resize(820,570)
        layout=QVBoxLayout(self);layout.setContentsMargins(20,20,20,20);layout.setSpacing(12)
        title=QLabel('Your projects');title.setObjectName('sectionTitle');layout.addWidget(title)
        intro=QLabel('Open a project to keep Edit, Censor, Subtitles & Translation, and Enhance together.');intro.setWordWrap(True);intro.setObjectName('muted');layout.addWidget(intro)
        self.search=QLineEdit();self.search.setPlaceholderText('Search projects…');self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.filter);layout.addWidget(self.search)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.projects=QListWidget();self.recovery=QListWidget()
        self.tabs.addTab(self.projects,'Projects');self.tabs.addTab(self.recovery,'Recovery')
        for widget in (self.projects,self.recovery):
            widget.setSpacing(5);widget.currentItemChanged.connect(self.selection);widget.itemDoubleClicked.connect(lambda _:self.open_selected())
        paths=recent(editor.root)
        if editor.path:paths.insert(0,str(editor.path))
        if editor.autosave.exists():paths.insert(0,str(editor.autosave))
        paths += [str(p) for p in (editor.root/'projects').glob('*.juicy')]
        seen=set()
        for path in paths:
            key=str(Path(path).resolve()).casefold()
            if key in seen:continue
            seen.add(key);self.add(self.projects,path,Path(path)==editor.autosave)
        recovery=editor.root/'cache/editor-projects/recovery'
        for path in sorted(recovery.glob('*.juicy'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:self.add(self.recovery,str(path))
        self.details=QLabel('Select a project, or create a new one.');self.details.setWordWrap(True);self.details.setObjectName('muted');layout.addWidget(self.details)
        row=QHBoxLayout();row.addWidget(action('New project',self.new,'Start an empty editing project'))
        row.addWidget(action('Browse…',self.browse,'Open a .juicy project from another folder'));row.addStretch()
        self.open_button=action('Open project',self.open_selected,'Open the selected project across the workspaces',True);row.addWidget(self.open_button)
        row.addWidget(action('Close',self.reject));layout.addLayout(row)
        self.tabs.currentChanged.connect(lambda _:self.selection())
        if self.projects.count():self.projects.setCurrentRow(0)
        else:self.open_button.setEnabled(False)
    def add(self,widget,path,draft=False):
        entry=describe(path);entry['draft']=draft
        label=entry['name']+(' · current draft' if draft else '')
        if not entry['error']:
            label+='\n'+f'{entry["clips"]} clips · {timestamp(entry["duration"]).replace(",",".")} · '+datetime.fromtimestamp(entry['modified']).strftime('%b %d, %Y %H:%M')
            if entry['missing']:label+=f' · {entry["missing"]} missing sources'
        else:label+='\nProject file unavailable'
        item=QListWidgetItem(tool_icon('save'),label);item.setData(Qt.ItemDataRole.UserRole,entry);item.setToolTip(entry['path']);widget.addItem(item)
    def selection(self,*_):
        item=self.tabs.currentWidget().currentItem()
        if not hasattr(self,'open_button'):return
        entry=item.data(Qt.ItemDataRole.UserRole) if item and not item.isHidden() else None
        self.open_button.setEnabled(bool(entry and not entry['error']))
        if entry:self.details.setText(entry['error'] or entry['path']+('\nMissing media can be relinked after opening.' if entry['missing'] else '\nSource media is referenced; opening does not move your videos.'))
    def filter(self,text):
        for widget in (self.projects,self.recovery):
            for i in range(widget.count()):widget.item(i).setHidden(text.casefold() not in widget.item(i).text().casefold())
        self.selection()
    def open_selected(self):
        item=self.tabs.currentWidget().currentItem()
        if not item:return
        entry=item.data(Qt.ItemDataRole.UserRole)
        if entry['error']:return
        self.choice=(entry['path'],entry['draft'] or self.tabs.currentWidget()==self.recovery);self.accept()
    def new(self):self.choice=('new',False);self.accept()
    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,'Open project',str(self.editor.root/'projects'),'Juicy Studio projects (*.juicy)')
        if path:self.choice=(path,False);self.accept()
