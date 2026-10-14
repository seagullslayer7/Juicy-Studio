"""Read the bundled guides inside Juicy Studio, with topic navigation and search."""
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QTextDocument, QTextCursor, QTextBlockFormat, QTextCharFormat, QPainter, QFont
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QLineEdit, QTextBrowser, QPushButton, QSplitter
from appearance import color

WELCOME = '''# Welcome to Juicy Studio

Your project brings editing, censorship, subtitles and enhancement together.
Choose a guide on the left, or search within the current page above.

## Start a project

1. Open **File → Projects…** to create or reopen a project.
2. In **Edit**, import a video and double-click it to append it to the timeline.
3. Select a clip to trim it, split at the playhead, or adjust its speed and volume.
4. Save with **Ctrl+S**. A project references your original media; keep those files available.

## Move between workspaces

Use **Censor** to review and adjust censor regions. Open **Subtitles & Translation**
to transcribe dialogue, edit lines or translate. These changes stay with the
project and follow your cuts. **Enhance** offers upscaling and restoration;
compare a short preview before exporting the entire video.

## Preview and export

Click the **speaker icon** for preview volume. Preview volume does not change
the exported audio; use **Clip volume** for that. Export the timeline to MP4 or
MKV from Edit. Burn subtitles into the picture for permanent captions, or use
an MKV subtitle track when you want to switch them on and off.

## Keep your workspace tidy

Open **File → Storage & uninstall…** to clear temporary files, speech alignments
or logs. Ordinary cache cleanup preserves models, projects and subtitle edits.
Full removal also deletes projects and exports inside the installation folder:
copy anything you want to keep elsewhere first.

## Current editor limits

Video and audio lanes currently organize a linked sequence. Overlapping layers
and independent audio mixing are still planned. The Editing guide explains the
current features and limits.
'''

TOPICS = [('Getting started', None), ('Editing & projects', 'docs/EDITOR-DEVELOPMENT.md'),
          ('Enhancement', 'docs/ENHANCE-DEVELOPMENT.md'), ('Full README', 'README.md'),
          ('Release notes', 'RELEASE-NOTES.md'), ('Third-party software', 'THIRD-PARTY.md')]


class GuideBrowser(QTextBrowser):
    def loadResource(self, kind, url):
        if kind == QTextDocument.ResourceType.ImageResource:
            path = self.document().baseUrl().resolved(url).toLocalFile()
            if not path: return None
            image = QImage(path)
            if image.isNull() and Path(path).suffix.lower() == '.svg':
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    image = QImage(renderer.defaultSize(),QImage.Format.Format_ARGB32_Premultiplied)
                    image.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(image); renderer.render(painter); painter.end()
            if not image.isNull():
                width = min(660,max(220,self.viewport().width()-44))
                return image.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation) if image.width() > width else image
        return super().loadResource(kind, url)


class HelpDialog(QDialog):
    def __init__(self, host, root):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.root = Path(root); self.setWindowTitle('Juicy Studio · User guide')
        self.resize(1060, 760); self.setMinimumSize(780, 520)
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 18, 20, 18); layout.setSpacing(14)
        header = QHBoxLayout(); title = QLabel('Juicy Studio · Guide'); title.setObjectName('paneTitle')
        title.setStyleSheet(f'font-size: 20px; font-weight: 600; color: {color("accent_text").name()};')
        header.addWidget(title, 1); self.search = QLineEdit(); self.search.setPlaceholderText('Find in this guide…'); self.search.setClearButtonEnabled(True); self.search.setMaximumWidth(280)
        header.addWidget(self.search); self.next = QPushButton('Next'); self.next.setToolTip('Find the next match (Enter)'); header.addWidget(self.next); layout.addLayout(header)
        body = QSplitter(Qt.Orientation.Horizontal)
        self.topics = QListWidget(); self.topics.setMinimumWidth(180); self.topics.setMaximumWidth(260)
        for title, _ in TOPICS: self.topics.addItem(title)
        body.addWidget(self.topics)
        self.browser = GuideBrowser(); self.browser.setOpenLinks(False); self.browser.setOpenExternalLinks(False)
        font = QFont('Segoe UI',11)
        self.browser.setFont(font); self.browser.document().setDefaultFont(font)
        self.browser.setStyleSheet('QTextBrowser { border: none; padding: 18px; }')
        self.browser.document().setDefaultStyleSheet(f'h1, h2, h3 {{ color: {color("accent_text").name()}; }} a {{ color: {color("accent_text").name()}; }} p, li {{ line-height: 145%; }} pre {{ background-color: {color("field").name()}; }}')
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(self.root) + '/'))
        body.addWidget(self.browser); body.setSizes([200, 800]); body.setStretchFactor(1, 1); layout.addWidget(body, 1)
        footer = QHBoxLayout(); self.result = QLabel(''); self.result.setObjectName('muted'); footer.addWidget(self.result, 1)
        close = QPushButton('Close'); close.clicked.connect(self.close); footer.addWidget(close); layout.addLayout(footer)
        self.topics.currentRowChanged.connect(self.show_topic); self.browser.anchorClicked.connect(self.open_link)
        self.search.textChanged.connect(self.find_first); self.search.returnPressed.connect(self.find_next); self.next.clicked.connect(self.find_next)
        self.topics.setCurrentRow(0)

    def show_topic(self, index):
        if index < 0: return
        filename = TOPICS[index][1]
        try: text = (self.root / filename).read_text(encoding='utf-8') if filename else WELCOME
        except OSError: text = '# Guide unavailable\n\nThis guide was not included in this installation.'
        page = self.root / filename if filename else self.root / 'README.md'
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(page.parent) + '/'))
        self.browser.setMarkdown(text)
        # Markdown/HTML fragments can retain black text despite a dark palette.
        # Give every fragment an explicit foreground, then style headings/links.
        document_cursor = QTextCursor(self.browser.document())
        document_cursor.select(QTextCursor.SelectionType.Document)
        foreground = QTextCharFormat(); foreground.setForeground(color('text'))
        document_cursor.mergeCharFormat(foreground)
        # Qt's Markdown reader does not apply HTML paragraph CSS reliably.
        # Format its document blocks directly for comfortable reading.
        block = self.browser.document().begin()
        while block.isValid():
            cursor = QTextCursor(block); fmt = block.blockFormat()
            heading = fmt.headingLevel()
            fmt.setTopMargin(16 if heading else 3); fmt.setBottomMargin(8 if heading else 7)
            image_block = False; images = block.begin()
            while not images.atEnd():
                if images.fragment().isValid() and images.fragment().charFormat().isImageFormat(): image_block = True
                images += 1
            fmt.setLineHeight(100 if image_block else 135, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            cursor.setBlockFormat(fmt)
            if heading:
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                foreground = QTextCharFormat(); foreground.setForeground(color('accent_text')); cursor.mergeCharFormat(foreground)
            fragment = block.begin()
            while not fragment.atEnd():
                item = fragment.fragment()
                if item.isValid() and item.charFormat().isAnchor():
                    cursor.setPosition(item.position()); cursor.setPosition(item.position()+item.length(), QTextCursor.MoveMode.KeepAnchor)
                    foreground = QTextCharFormat(); foreground.setForeground(color('accent_text')); cursor.mergeCharFormat(foreground)
                fragment += 1
            block = block.next()
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)
        self.find_first()

    def find_first(self, *_):
        cursor = self.browser.textCursor(); cursor.movePosition(cursor.MoveOperation.Start); self.browser.setTextCursor(cursor)
        self.find_next()

    def find_next(self):
        query = self.search.text().strip()
        if not query: self.result.clear(); return
        found = self.browser.find(query)
        if not found:
            cursor = self.browser.textCursor(); cursor.movePosition(cursor.MoveOperation.Start); self.browser.setTextCursor(cursor)
            found = self.browser.find(query)
        self.result.setText('' if found else 'No matching text in this guide.')

    def open_link(self, url):
        if url.scheme() in ('https', 'http'): QDesktopServices.openUrl(url); return
        if url.toString().startswith('#'):
            self.browser.scrollToAnchor(url.fragment()); return
        resolved = self.browser.document().baseUrl().resolved(url)
        path = Path(resolved.toLocalFile())
        for index, (_, filename) in enumerate(TOPICS):
            if filename and path == self.root / filename:
                self.topics.setCurrentRow(index)
                if resolved.fragment(): self.browser.scrollToAnchor(resolved.fragment())
                return
