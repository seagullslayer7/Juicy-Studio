"""Prevent invisible dark-theme README text and missing bundled SVG images."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QApplication
from help_ui import HelpDialog
from appearance import color, apply_theme, normalize

class GuideRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.old_palette=self.app.palette();self.old_style=self.app.styleSheet()
        apply_theme(self.app,'',normalize({}))
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'README.md').write_text('# Guide\n\n<p style="color:black">Readable paragraph.</p>\n\n| Feature | Value |\n| --- | --- |\n| Editor | Available |\n\n![Graphic](banner.svg)\n',encoding='utf-8')
        (self.root/'banner.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="180"><rect width="800" height="180" fill="#ff9f24"/></svg>',encoding='utf-8')
        self.dialog=HelpDialog(None,self.root);self.dialog.show();self.app.processEvents();self.dialog.topics.setCurrentRow(3)

    def tearDown(self):
        self.dialog.close();self.app.processEvents();self.temp.cleanup()
        self.app.setPalette(self.old_palette);self.app.setStyleSheet(self.old_style)

    def test_body_and_table_text_have_visible_foreground(self):
        body=self.dialog.browser.toPlainText()
        self.assertIn('Readable paragraph.',body);self.assertIn('Available',body)
        block=self.dialog.browser.document().begin();checked=0
        while block.isValid():
            fragment=block.begin()
            while not fragment.atEnd():
                item=fragment.fragment()
                if item.isValid() and item.text().strip() and not block.blockFormat().headingLevel():
                    self.assertEqual(item.charFormat().foreground().color().name(),color('text').name());checked+=1
                fragment+=1
            block=block.next()
        self.assertGreater(checked,2)

    def test_svg_resource_is_rendered_without_missing_image_placeholder(self):
        image=self.dialog.browser.loadResource(QTextDocument.ResourceType.ImageResource,QUrl('banner.svg'))
        self.assertIsInstance(image,QImage);self.assertFalse(image.isNull());self.assertLessEqual(image.width(),660)

    def test_search_finds_table_content(self):
        self.dialog.search.setText('Available')
        self.assertEqual(self.dialog.browser.textCursor().selectedText(),'Available')
