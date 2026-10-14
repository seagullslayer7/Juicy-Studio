"""Storage controls and the installed app's registered uninstaller."""
from pathlib import Path
import subprocess
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QMessageBox
from subtitle_ui import action
from storage_cleanup import CATEGORIES, inventory, clear

def show_maintenance(host, root):
    if host.process is not None:
        host.set_status('Finish or cancel processing before cleaning storage.'); return
    dialog = QDialog(host); dialog.setWindowTitle('Storage & uninstall'); dialog.resize(580, 430)
    layout = QVBoxLayout(dialog)
    heading = QLabel('Keep your workspace tidy'); heading.setObjectName('paneTitle'); layout.addWidget(heading)
    text = QLabel('Clear rebuildable files from this installation. Models, saved projects, subtitle edits, censor reviews and exported videos are preserved.'); text.setWordWrap(True); layout.addWidget(text)
    choices = {}
    for name in CATEGORIES:
        checkbox = QCheckBox(name); checkbox.setChecked(name != 'Processing logs'); layout.addWidget(checkbox); choices[name] = checkbox
    summary = QLabel(); summary.setWordWrap(True); layout.addWidget(summary)
    def selected(): return [name for name, checkbox in choices.items() if checkbox.isChecked()]
    def refresh():
        try:
            files, blocked = inventory(root, selected()); summary.setText(f'{len(files):,} files · {sum(size for _, size in files)/1024**2:,.1f} MB reclaimable' + (f'\n{len(blocked)} linked paths will be skipped.' if blocked else ''))
        except (OSError, ValueError) as exc: summary.setText(str(exc))
    def cleanup():
        if not selected(): return
        files, _ = inventory(root, selected())
        if QMessageBox.question(dialog, 'Clear selected storage?', f'Remove {len(files):,} rebuildable files ({sum(s for _, s in files)/1024**2:,.1f} MB)? Playback will pause. They are regenerated when needed.') != QMessageBox.StandardButton.Yes: return
        if not host.subtitles.commit_edit(): return
        host.project_session.sync_subtitles(host.subtitles.doc); host.project_session.sync_censors(host.state)
        host.editor.changed()
        for loader in (host.waveform, host.editor.waveform_loader): loader.close()
        host.editor.waveform_pending.clear(); host.editor.waveform_active = None; host.editor.waveforms.clear()
        for player in (host.player, host.subtitles.player, host.editor.player, host.enhance.original, host.enhance.enhanced):
            player.stop(); player.setSource(QUrl())
        host.project_session.leave(); host.invalidate_preview(switch=False)
        removed, failures = clear(root, selected())
        host.editor.refresh(); host.editor.seek(host.editor.position)
        if host.workspaces.currentIndex() != 3:
            if host.editor.doc['clips']: host.project_session.prepare()
            else: host.select_video(host.queue.currentRow())
        refresh(); host.set_status(f'Cleared {removed/1024**2:,.1f} MB.' + (f' {len(failures)} files or linked paths were skipped.' if failures else ''))
        if failures: QMessageBox.information(dialog, 'Some files were preserved', '\n'.join(failures[:12]))
    layout.addWidget(action('Clear selected storage…', cleanup, 'Preview and confirm removal of generated files'))
    layout.addSpacing(16)
    uninstall = Path(root) / 'unins000.exe'
    note = QLabel('Uninstall app: removes installed application files and keeps your data.\nRemove app and all local data: also removes this installation’s runtime, models, caches, settings, projects and exports. Files outside this installation folder are never removed.'); note.setWordWrap(True); layout.addWidget(note)
    def launch(purge=False):
        detail = 'Remove Juicy Studio and ALL data stored inside this installation, including projects and exports? Save anything you want to keep elsewhere first.' if purge else 'Uninstall Juicy Studio? Models, settings, projects and exports will remain.'
        if QMessageBox.warning(dialog, 'Uninstall Juicy Studio', detail, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes: return
        if not host.subtitles.commit_edit(): return
        host.project_session.sync_subtitles(host.subtitles.doc); host.project_session.sync_censors(host.state)
        host.editor.changed()
        subprocess.Popen([str(uninstall)] + (['/PURGEDATA=1'] if purge else []), cwd=root)
        dialog.accept(); host.close()
    for title, purge in [('Uninstall app…', False), ('Remove app and all local data…', True)]:
        button = action(title, lambda checked=False, purge=purge: launch(purge), 'Launch the Windows uninstaller'); button.setEnabled(uninstall.is_file()); layout.addWidget(button)
    if not uninstall.is_file():
        label = QLabel('Uninstall is available in installed builds. This source or portable copy can be removed manually after closing it.'); label.setWordWrap(True); layout.addWidget(label)
    for checkbox in choices.values(): checkbox.toggled.connect(refresh)
    refresh(); dialog.exec()
