"""
Backup and Disaster Recovery View.
Provides manual backup generation, automated history listing, SHA-256 verification, and database restoration.
"""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog
)

from src.services.backup_service import BackupService
from src.services.auth_service import UserSession


class BackupView(QWidget):
    def __init__(self, backup_service: BackupService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.backup_service = backup_service
        self.current_session = current_session

        self._init_ui()
        self.refresh_backups()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Database Backup & Disaster Recovery")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Safeguard business records, generate hot backups, and perform verified database restorations")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.backup_btn = QPushButton("💾 Create Database Backup Now")
        self.backup_btn.setObjectName("PrimaryBtn")
        self.backup_btn.clicked.connect(self._handle_create_backup)
        top_bar.addWidget(self.backup_btn)

        layout.addLayout(top_bar)

        # Backups Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "File Name", "Size (KB)", "SHA-256 Checksum", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh_backups(self):
        try:
            backups = self.backup_service.list_backups()
            self.table.setRowCount(len(backups))

            for row, b in enumerate(backups):
                self.table.setItem(row, 0, QTableWidgetItem(b["timestamp"]))
                self.table.setItem(row, 1, QTableWidgetItem(b["file_name"]))
                size_kb = f"{(b['file_size'] / 1024):.1f} KB"
                self.table.setItem(row, 2, QTableWidgetItem(size_kb))
                self.table.setItem(row, 3, QTableWidgetItem(b["checksum"]))

                st_item = QTableWidgetItem(b["status"])
                st_item.setForeground(Qt.darkGreen if b["status"] == "SUCCESS" else Qt.red)
                self.table.setItem(row, 4, st_item)

                # Actions
                act_box = QWidget()
                act_layout = QHBoxLayout(act_box)
                act_layout.setContentsMargins(6, 4, 6, 4)
                act_layout.setSpacing(6)
                act_layout.setAlignment(Qt.AlignCenter)

                v_btn = QPushButton("Verify")
                v_btn.setObjectName("TableActionBtn")
                v_btn.setFixedHeight(28)
                v_btn.setMinimumWidth(55)
                v_btn.clicked.connect(lambda _, p=b["file_path"]: self._handle_verify(p))
                act_layout.addWidget(v_btn)

                r_btn = QPushButton("Restore")
                r_btn.setObjectName("TableActionDangerBtn")
                r_btn.setFixedHeight(28)
                r_btn.setMinimumWidth(55)
                r_btn.clicked.connect(lambda _, p=b["file_path"]: self._handle_restore(p))
                act_layout.addWidget(r_btn)

                self.table.setCellWidget(row, 5, act_box)

        except Exception as e:
            pass

    def _handle_create_backup(self):
        try:
            res = self.backup_service.create_backup(self.current_session, backup_type="MANUAL")
            QMessageBox.information(
                self,
                "Backup Created",
                f"Hot backup completed successfully!\nFile: {Path(res['file_path']).name}\nSize: {res['file_size']} bytes\nSHA256: {res['checksum_sha256'][:16]}..."
            )
            self.refresh_backups()
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def _handle_verify(self, file_path: str):
        ok, msg = self.backup_service.verify_backup(file_path)
        if ok:
            QMessageBox.information(self, "Backup Integrity Verified", f"Status: PASS\nDetails: {msg}")
        else:
            QMessageBox.critical(self, "Verification Failed", f"Status: FAIL\nReason: {msg}")

    def _handle_restore(self, file_path: str):
        reply = QMessageBox.warning(
            self,
            "Confirm Database Restoration",
            "WARNING: Restoring will overwrite the current active database with data from the backup!\n\n"
            "An automatic pre-restoration snapshot of current data will be taken first.\n\n"
            "Do you wish to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.backup_service.restore_backup(self.current_session, file_path)
                QMessageBox.information(self, "Restoration Successful", "Database restored and verified successfully.")
                self.refresh_backups()
            except Exception as e:
                QMessageBox.critical(self, "Restoration Error", str(e))
