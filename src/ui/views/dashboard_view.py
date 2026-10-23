"""
Dashboard View: Executive KPIs, Today's Sales, Payment Splits, Stock Alerts, and Recent Bills.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QGridLayout
)

from src.services.reporting_service import ReportingService
from src.services.settings_service import SettingsService


class DashboardView(QWidget):
    def __init__(self, reporting_service: ReportingService, settings_service: SettingsService, parent=None):
        super().__init__(parent)
        self.reporting_service = reporting_service
        self.settings_service = settings_service

        self._init_ui()
        self.refresh_metrics()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Title
        hdr_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = QLabel("Store Overview & Performance")
        self.title_lbl.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(self.title_lbl)

        self.shop_meta_lbl = QLabel()
        self.shop_meta_lbl.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(self.shop_meta_lbl)
        hdr_layout.addLayout(title_box)

        hdr_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh Data")
        self.refresh_btn.setObjectName("SecondaryBtn")
        self.refresh_btn.clicked.connect(self.refresh_metrics)
        hdr_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(hdr_layout)

        # 4 Metric Stat Cards
        cards_grid = QGridLayout()
        cards_grid.setHorizontalSpacing(14)
        cards_grid.setVerticalSpacing(14)

        # Card 1: Today Revenue
        self.rev_card, self.rev_val = self._create_stat_card("TODAY'S SALES", "₹ 0.00", "#16A34A")
        cards_grid.addWidget(self.rev_card, 0, 0)

        # Card 2: Completed Bills
        self.bills_card, self.bills_val = self._create_stat_card("BILLS COMPLETED", "0", "#2563EB")
        cards_grid.addWidget(self.bills_card, 0, 1)

        # Card 3: Items Sold
        self.items_card, self.items_val = self._create_stat_card("ITEMS SOLD TODAY", "0.00", "#0F172A")
        cards_grid.addWidget(self.items_card, 0, 2)

        # Card 4: Low Stock Alerts
        self.stock_card, self.stock_val = self._create_stat_card("LOW STOCK ALERTS", "0", "#DC2626")
        cards_grid.addWidget(self.stock_card, 0, 3)

        main_layout.addLayout(cards_grid)

        # Lower Split: Payment Method Breakdown, Chart, and Recent Transactions
        lower_layout = QHBoxLayout()
        lower_layout.setSpacing(14)

        # 1. Payment Methods Box
        pay_frame = QFrame()
        pay_frame.setStyleSheet("QFrame { background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; } QLabel { border: none; background: transparent; }")
        p_layout = QVBoxLayout(pay_frame)
        p_layout.setContentsMargins(14, 14, 14, 14)

        p_title = QLabel("TODAY'S COLLECTIONS")
        p_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        p_layout.addWidget(p_title)

        self.cash_lbl = QLabel("Cash: ₹ 0.00")
        self.cash_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #0F172A; padding: 3px 0;")
        p_layout.addWidget(self.cash_lbl)

        self.upi_lbl = QLabel("UPI: ₹ 0.00")
        self.upi_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #2563EB; padding: 3px 0;")
        p_layout.addWidget(self.upi_lbl)

        self.card_lbl = QLabel("Card: ₹ 0.00")
        self.card_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #9333EA; padding: 3px 0;")
        p_layout.addWidget(self.card_lbl)

        p_layout.addStretch()
        lower_layout.addWidget(pay_frame, 1)

        # 2. Matplotlib 7-Day Sales Trend Canvas
        chart_frame = QFrame()
        chart_frame.setStyleSheet("QFrame { background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; } QLabel { border: none; background: transparent; }")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(12, 12, 12, 12)

        chart_title = QLabel("7-DAY SALES REVENUE TREND")
        chart_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        chart_layout.addWidget(chart_title)

        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

        self.chart_figure = Figure(figsize=(4.2, 2.2), dpi=90, facecolor="#FFFFFF")
        self.chart_canvas = FigureCanvas(self.chart_figure)
        chart_layout.addWidget(self.chart_canvas)
        lower_layout.addWidget(chart_frame, 2)

        # 3. Recent Transactions Table
        txns_frame = QFrame()
        txns_frame.setStyleSheet("QFrame { background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; } QLabel { border: none; background: transparent; }")
        tx_layout = QVBoxLayout(txns_frame)
        tx_layout.setContentsMargins(14, 14, 14, 14)

        tx_title = QLabel("RECENT SALES TRANSACTIONS")
        tx_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        tx_layout.addWidget(tx_title)

        self.tx_table = QTableWidget()
        self.tx_table.setColumnCount(4)
        self.tx_table.setHorizontalHeaderLabels(["Invoice", "Time", "Customer", "Amount (₹)"])
        self.tx_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tx_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tx_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tx_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        tx_layout.addWidget(self.tx_table)

        lower_layout.addWidget(txns_frame, 2)

        main_layout.addLayout(lower_layout)

    def _create_stat_card(self, title: str, initial_val: str, val_color: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("StatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)

        t_lbl = QLabel(title)
        t_lbl.setObjectName("StatCardTitle")
        layout.addWidget(t_lbl)

        v_lbl = QLabel(initial_val)
        v_lbl.setObjectName("StatCardValue")
        v_lbl.setStyleSheet(f"color: {val_color};")
        layout.addWidget(v_lbl)

        return card, v_lbl

    def refresh_metrics(self):
        try:
            shop = self.settings_service.get_shop_info()
            self.shop_meta_lbl.setText(
                f"{shop.get('name', 'Retail')} | Profile: {shop.get('business_profile', 'general').capitalize()} | "
                f"GSTIN: {shop.get('gstin', 'Unregistered')} | State: {shop.get('state_name', 'Tamil Nadu')}"
            )
        except Exception:
            self.shop_meta_lbl.setText("Ready")

        try:
            kpis = self.reporting_service.get_dashboard_summary()
            self.rev_val.setText(f"₹ {kpis['today_revenue']:,.2f}")
            self.bills_val.setText(str(kpis["today_bills_count"]))
            self.items_val.setText(f"{kpis['today_items_sold']:,.2f}")
            self.stock_val.setText(str(kpis["low_stock_count"]))

            # Payment splits
            methods = kpis.get("payment_methods", {})
            self.cash_lbl.setText(f"Cash: ₹ {methods.get('CASH', 0.0):,.2f}")
            self.upi_lbl.setText(f"UPI / QR: ₹ {methods.get('UPI', 0.0):,.2f}")
            self.card_lbl.setText(f"Card: ₹ {methods.get('CARD', 0.0):,.2f}")

            # Recent txns table
            txns = kpis.get("recent_transactions", [])
            self.tx_table.setRowCount(len(txns))
            for row, t in enumerate(txns):
                self.tx_table.setItem(row, 0, QTableWidgetItem(t["invoice_number"]))
                self.tx_table.setItem(row, 1, QTableWidgetItem(t["date"]))
                self.tx_table.setItem(row, 2, QTableWidgetItem(t["customer"]))
                self.tx_table.setItem(row, 3, QTableWidgetItem(f"₹ {t['grand_total']:,.2f}"))

            # Render Matplotlib 7-Day Trend Chart
            try:
                trend = self.reporting_service.get_7_day_sales_trend(7)
                self.chart_figure.clear()
                ax = self.chart_figure.add_subplot(111)
                dates = [d["date"] for d in trend]
                revenues = [d["revenue"] for d in trend]

                bars = ax.bar(dates, revenues, color="#2563EB", width=0.55, edgecolor="#1D4ED8", alpha=0.9)
                ax.set_ylabel("Revenue (₹)", fontsize=8, color="#64748B")
                ax.tick_params(axis='both', which='major', labelsize=7.5)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('#E2E8F0')
                ax.spines['bottom'].set_color('#E2E8F0')
                ax.grid(axis='y', linestyle='--', alpha=0.3)

                for bar in bars:
                    h = bar.get_height()
                    if h > 0:
                        ax.annotate(f"₹{int(h)}",
                            xy=(bar.get_x() + bar.get_width() / 2, h),
                            xytext=(0, 2), textcoords="offset points",
                            ha='center', va='bottom', fontsize=6.5, color="#1E293B")

                self.chart_figure.tight_layout()
                self.chart_canvas.draw()
            except Exception:
                pass

        except Exception as exc:
            pass
