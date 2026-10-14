"""Compact preview volume control shared by editing and enhancement."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QWidget, QVBoxLayout, QSlider, QLabel, QWidgetAction, QPushButton, QStyle


class VolumeControl:
    def __init__(self, owner, host, callback, value=65):
        self.host = host
        self.previous = value or 65
        self.button = QPushButton(owner)
        self.button.setFixedWidth(36)
        self.button.setAccessibleName('Preview volume')
        self.menu = QMenu(owner)
        panel = QWidget(); layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10); layout.setSpacing(8)
        self.label = QLabel(); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setObjectName('previewVolume'); self.slider.setRange(0, 100); self.slider.setValue(value)
        self.slider.setFixedSize(26, 112); self.slider.setAccessibleName('Preview volume')
        self.slider.setToolTip('Preview volume only. Exported audio is unchanged.')
        layout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignHCenter)
        self.mute = QPushButton('Mute'); self.mute.setToolTip('Mute or restore the previous preview volume')
        layout.addWidget(self.mute)
        entry = QWidgetAction(self.menu); entry.setDefaultWidget(panel); self.menu.addAction(entry)
        self.button.clicked.connect(lambda: self.menu.popup(self.button.mapToGlobal(self.button.rect().bottomLeft())))
        self.mute.clicked.connect(self.toggle_mute)
        self.slider.valueChanged.connect(callback)
        self.slider.valueChanged.connect(self.update)
        self.update(value)

    def update(self, value):
        if value: self.previous = value
        self.label.setText(f'{value}%'); self.mute.setText('Unmute' if value == 0 else 'Mute')
        icon = QStyle.StandardPixmap.SP_MediaVolumeMuted if value == 0 else QStyle.StandardPixmap.SP_MediaVolume
        self.button.setProperty('mediaIcon', icon.value); self.button.setIcon(self.host.media_icon(icon))
        self.button.setToolTip(f'Preview volume · {value}%')

    def toggle_mute(self):
        self.slider.setValue(0 if self.slider.value() else self.previous)
