"""
User Authentication and RBAC Administration View.
Manage cashiers, inventory managers, administrators, and passwords.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QComboBox, QMessageBox, QFormLayout
)

from src.services.auth_service import AuthService, UserSession


class AddUserDialog(QDialog):
    def __init__(self, auth_service: AuthService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.current_session = current_session

        self.setWindowTitle("Create New User Account")
        self.setFixedSize(400, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()

        self.name_input = QLineEdit()
        form.addRow("Full Name *:", self.name_input)

        self.user_input = QLineEdit()
        form.addRow("Username *:", self.user_input)

        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        form.addRow("Password *:", self.pass_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Cashier", "Inventory Manager", "Administrator"])
        form.addRow("Assigned Role *:", self.role_combo)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryBtn")
        cancel.clicked.connect(self.reject)
        btn_box.addWidget(cancel)

        save = QPushButton("Create User")
        save.setObjectName("PrimaryBtn")
        save.clicked.connect(self._handle_save)
        btn_box.addWidget(save)

        layout.addLayout(btn_box)

    def _handle_save(self):
        name = self.name_input.text().strip()
        user = self.user_input.text().strip()
        pwd = self.pass_input.text()
        role = self.role_combo.currentText()

        if not name or not user or not pwd:
            QMessageBox.warning(self, "Validation Error", "All fields are required.")
            return

        try:
            self.auth_service.create_user(
                current_session=self.current_session,
                username=user,
                password=pwd,
                full_name=name,
                role_names=[role],
                is_admin=(role == "Administrator"),
            )
            QMessageBox.information(self, "User Created", f"Account '{user}' successfully provisioned.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error Creating User", str(e))


class UsersView(QWidget):
    def __init__(self, auth_service: AuthService, current_session: UserSession, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.current_session = current_session

        self._init_ui()
        self.refresh_users()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("User Accounts & Role Permissions")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Manage cashier log-ins, store manager roles, and access privileges")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.add_user_btn = QPushButton("+ Add New User")
        self.add_user_btn.setObjectName("PrimaryBtn")
        self.add_user_btn.clicked.connect(self._open_add_dialog)
        top_bar.addWidget(self.add_user_btn)

        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Username", "Full Name", "Roles", "Status", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh_users(self):
        try:
            users = self.auth_service.list_users(self.current_session)
            self.table.setRowCount(len(users))

            for row, u in enumerate(users):
                self.table.setItem(row, 0, QTableWidgetItem(str(u["id"])))
                self.table.setItem(row, 1, QTableWidgetItem(u["username"]))
                self.table.setItem(row, 2, QTableWidgetItem(u["full_name"]))
                self.table.setItem(row, 3, QTableWidgetItem(", ".join(u["roles"])))

                status_item = QTableWidgetItem("Active" if u["is_active"] else "Inactive")
                status_item.setForeground(Qt.darkGreen if u["is_active"] else Qt.red)
                self.table.setItem(row, 4, status_item)

                btn_toggle = QPushButton("Deactivate" if u["is_active"] else "Activate")
                btn_toggle.setObjectName("TableActionDangerBtn" if u["is_active"] else "TableActionBtn")
                btn_toggle.setFixedHeight(28)
                btn_toggle.setMinimumWidth(80)
                btn_toggle.clicked.connect(lambda _, uid=u["id"], st=u["is_active"]: self._toggle_status(uid, not st))

                act_box = QWidget()
                act_layout = QHBoxLayout(act_box)
                act_layout.setContentsMargins(6, 4, 6, 4)
                act_layout.setAlignment(Qt.AlignCenter)
                act_layout.addWidget(btn_toggle)
                self.table.setCellWidget(row, 5, act_box)

        except Exception as e:
            pass

    def _toggle_status(self, user_id: int, new_status: bool):
        try:
            self.auth_service.set_user_active_status(self.current_session, user_id, new_status)
            self.refresh_users()
        except Exception as e:
            QMessageBox.critical(self, "Status Error", str(e))

    def _open_add_dialog(self):
        dlg = AddUserDialog(self.auth_service, self.current_session, parent=self)
        if dlg.exec():
            self.refresh_users()
