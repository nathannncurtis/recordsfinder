import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction,
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox,
    QPushButton, QLabel, QLineEdit, QScrollArea,
    QWidget, QMessageBox, QFileDialog, QGroupBox
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from config import (
    get_icon_path, get_app_path,
    read_scan_config, write_scan_config,
    read_user_config, write_user_config,
    get_enabled_folders
)


class AddFolderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Folder")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Label (display name):"))
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("e.g. Client Services")
        layout.addWidget(self.label_edit)

        layout.addWidget(QLabel("UNC Path:"))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"e.g. \\server\share\folder")
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            self.path_edit.setText(path)

    def get_values(self):
        return self.label_edit.text().strip(), self.path_edit.text().strip()


class ConfigureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Records Finder - Configure Folders")
        self.setMinimumSize(500, 400)
        self.checkboxes = []

        main_layout = QVBoxLayout(self)

        main_layout.addWidget(QLabel("Select which folders to search when finding records:"))

        # Scrollable area for folder checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.scroll_widget)
        main_layout.addWidget(scroll)

        # Add New Folder button
        add_btn = QPushButton("Add New Folder...")
        add_btn.clicked.connect(self.add_new_folder)
        main_layout.addWidget(add_btn)

        # Save / Cancel
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_and_close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        self.load_folders()

    def load_folders(self):
        # Clear existing checkboxes
        for cb in self.checkboxes:
            self.scroll_layout.removeWidget(cb)
            cb.deleteLater()
        self.checkboxes = []

        scan_cfg = read_scan_config()
        enabled = set(get_enabled_folders())

        for folder in scan_cfg.get("folders", []):
            path = folder.get("path", "")
            label = folder.get("label", path)
            cb = QCheckBox(f"{label}  ({path})")
            cb.setProperty("folder_path", path)
            cb.setChecked(path in enabled)
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)

    def add_new_folder(self):
        dialog = AddFolderDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            label, path = dialog.get_values()
            if not path:
                QMessageBox.warning(self, "Missing Path", "Please enter a folder path.")
                return
            if not label:
                label = os.path.basename(path) or path

            # Add to shared scan config
            scan_cfg = read_scan_config()
            existing_paths = [f.get("path", "") for f in scan_cfg.get("folders", [])]
            if path in existing_paths:
                QMessageBox.information(self, "Already Exists", "This folder is already in the list.")
                return

            scan_cfg.setdefault("folders", []).append({"path": path, "label": label})
            if write_scan_config(scan_cfg):
                self.load_folders()
                # Auto-check the newly added folder
                if self.checkboxes:
                    self.checkboxes[-1].setChecked(True)
            else:
                QMessageBox.warning(
                    self, "Error",
                    "Could not save to the shared configuration.\n"
                    "Check that the network share is accessible."
                )

    def save_and_close(self):
        enabled = []
        for cb in self.checkboxes:
            if cb.isChecked():
                enabled.append(cb.property("folder_path"))

        if write_user_config({"enabled_folders": enabled}):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Could not save configuration.")


class TrayApp:
    def __init__(self):
        icon_path = get_icon_path()
        self.icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.tray = QSystemTrayIcon(self.icon)
        self.tray.setToolTip("Records Finder")

        menu = QMenu()

        configure_action = QAction("Configure Folders", menu)
        configure_action.triggered.connect(self.open_configure)
        menu.addAction(configure_action)

        update_action = QAction("Check for Updates", menu)
        update_action.triggered.connect(self.check_updates)
        menu.addAction(update_action)

        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

        self.config_dialog = None

    def open_configure(self):
        if self.config_dialog and self.config_dialog.isVisible():
            self.config_dialog.activateWindow()
            return
        self.config_dialog = ConfigureDialog()
        self.config_dialog.show()

    def check_updates(self):
        checker_path = os.path.join(get_app_path(), 'update_checker.exe')
        if os.path.exists(checker_path):
            subprocess.Popen([checker_path], shell=False)
        else:
            QMessageBox.warning(
                None, "Records Finder",
                "Update checker not found."
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        sys.exit(1)

    tray = TrayApp()
    sys.exit(app.exec_())
