from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget,
    QPushButton, QLabel, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import pyqtSignal


class ProfileManagerWindow(QDialog):
    profile_saved = pyqtSignal()

    def __init__(self, profile_manager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager

        self.setWindowTitle("Gestor de perfiles")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Perfiles disponibles:"))

        self.profile_list = QListWidget()
        layout.addWidget(self.profile_list)

        btn_layout = QHBoxLayout()

        self.btn_activate = QPushButton("Activar")
        self.btn_close = QPushButton("Cerrar")

        self.btn_activate.clicked.connect(self._activate_profile)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_activate)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self._load_profiles()

    def _load_profiles(self):
        """Carga perfiles desde ProfileManager."""
        self.profile_list.clear()

        profiles = self.profile_manager.profiles.keys()

        if not profiles:
            self.profile_list.addItem("⚠ No hay perfiles")
            self.btn_activate.setEnabled(False)
            return

        for name in profiles:
            self.profile_list.addItem(name)

    def _activate_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Perfil", "Selecciona un perfil")
            return

        profile_name = item.text()

        if self.profile_manager.load_profile(profile_name):
            self.profile_saved.emit()
            self.close()

        
