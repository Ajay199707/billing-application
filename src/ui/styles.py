"""
Modern and Professional QSS (Qt Style Sheet) for Windows Desktop Billing Application.
Fresh Emerald & Clean Mint Supermarket Palette:
- Soft Mint White body background (#F4FBF7)
- Deep Forest Green and Emerald accents (#064E3B, #059669)
- Crisp white cards with soft sage borders (#D1FAE5)
- High-contrast, fatigue-reducing typography and accessible buttons.
"""

APP_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #F4FBF7;
    color: #0F172A;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #1E293B;
}

/* Sidebar Navigation Drawer */
#SidebarWidget {
    background-color: #E6F7EF;
    border-right: 1px solid #A7F3D0;
    min-width: 210px;
    max-width: 240px;
}

#SidebarWidget QPushButton {
    background-color: transparent;
    color: #065F46;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    margin: 2px 8px;
}

#SidebarWidget QPushButton:hover {
    background-color: #D1FAE5;
    color: #064E3B;
}

#SidebarWidget QPushButton:checked, #SidebarWidget QPushButton[active="true"] {
    background-color: #059669;
    color: #FFFFFF;
    font-weight: 700;
}

/* App Header & Cards */
#HeaderCard {
    background-color: #FFFFFF;
    border-bottom: 1px solid #D1FAE5;
    padding: 8px 16px;
}

#StatCard {
    background-color: #FFFFFF;
    border: 1px solid #D1FAE5;
    border-radius: 8px;
    padding: 16px;
}

#StatCardTitle {
    color: #047857;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

#StatCardValue {
    color: #064E3B;
    font-size: 24px;
    font-weight: 800;
    margin-top: 4px;
}

/* Tables */
QTableWidget, QTableView {
    background-color: #FFFFFF;
    border: 1px solid #D1FAE5;
    border-radius: 6px;
    gridline-color: #ECFDF5;
    selection-background-color: #D1FAE5;
    selection-color: #065F46;
    font-size: 13px;
}

QTableWidget::item, QTableView::item {
    padding: 6px 10px;
    border-bottom: 1px solid #ECFDF5;
}

QHeaderView::section {
    background-color: #ECFDF5;
    color: #065F46;
    padding: 8px 10px;
    font-weight: 700;
    border: none;
    border-bottom: 2px solid #A7F3D0;
}

/* Input Fields & Combos */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background-color: #FFFFFF;
    border: 1px solid #A7F3D0;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    color: #0F172A;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
    border: 1.5px solid #059669;
    outline: none;
    background-color: #FCFDFD;
}

/* Primary Action Buttons */
QPushButton#PrimaryBtn {
    background-color: #059669;
    color: #FFFFFF;
    font-weight: 700;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton#PrimaryBtn:hover {
    background-color: #047857;
}

QPushButton#PrimaryBtn:pressed {
    background-color: #065F46;
}

/* Success Buttons */
QPushButton#SuccessBtn {
    background-color: #10B981;
    color: #FFFFFF;
    font-weight: 700;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton#SuccessBtn:hover {
    background-color: #059669;
}

QPushButton#SuccessBtn:pressed {
    background-color: #047857;
}

/* Danger Buttons */
QPushButton#DangerBtn {
    background-color: #EF4444;
    color: #FFFFFF;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton#DangerBtn:hover {
    background-color: #DC2626;
}

/* Secondary Buttons */
QPushButton#SecondaryBtn {
    background-color: #FFFFFF;
    color: #065F46;
    font-weight: 600;
    border: 1px solid #A7F3D0;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton#SecondaryBtn:hover {
    background-color: #ECFDF5;
    border-color: #059669;
}

/* Compact Table Action Buttons */
QPushButton#TableActionBtn {
    background-color: #ECFDF5;
    color: #047857;
    font-weight: 700;
    border: 1px solid #A7F3D0;
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 12px;
    min-height: 24px;
}

QPushButton#TableActionBtn:hover {
    background-color: #059669;
    color: #FFFFFF;
    border-color: #059669;
}

QPushButton#TableActionDangerBtn {
    background-color: #FEF2F2;
    color: #DC2626;
    font-weight: 700;
    border: 1px solid #FECACA;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    min-height: 24px;
}

QPushButton#TableActionDangerBtn:hover {
    background-color: #DC2626;
    color: #FFFFFF;
    border-color: #DC2626;
}

/* Big Checkout Button */
QPushButton#CheckoutBtn {
    background-color: #059669;
    color: #FFFFFF;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 0.5px;
    padding: 14px 20px;
    border-radius: 8px;
    border: 1px solid #047857;
}

QPushButton#CheckoutBtn:hover {
    background-color: #047857;
}

QPushButton#CheckoutBtn:pressed {
    background-color: #065F46;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #D1FAE5;
    background: #FFFFFF;
    border-radius: 6px;
}

QTabBar::tab {
    background: #ECFDF5;
    color: #065F46;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    color: #059669;
    font-weight: 700;
    border-bottom: 2px solid #059669;
}
"""
