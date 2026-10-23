"""
Reports and Financial Analytics View.
Includes Sales Trends, Product Velocity, GST Tax Summaries, Inventory Valuations,
Gross/Net Profit & Loss Statements, and one-click Excel exports.
"""

from datetime import date, timedelta
from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QFileDialog, QMessageBox, QFrame
)

from src.services.reporting_service import ReportingService


class ReportsView(QWidget):
    def __init__(self, reporting_service: ReportingService, parent=None):
        super().__init__(parent)
        self.reporting_service = reporting_service

        self._init_ui()
        self.refresh_all_reports()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Bar
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Business Reports & Financial Analytics")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        title_box.addWidget(title)

        sub = QLabel("Generate tax-compliant GST summaries, sales metrics, inventory valuations, and P&L statements")
        sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(sub)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.refresh_btn = QPushButton("Refresh Reports")
        self.refresh_btn.setObjectName("SecondaryBtn")
        self.refresh_btn.clicked.connect(self.refresh_all_reports)
        top_bar.addWidget(self.refresh_btn)

        layout.addLayout(top_bar)

        # Global Date Filter
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Reporting Period From:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(date.today() - timedelta(days=30))
        self.from_date.dateChanged.connect(self.refresh_all_reports)
        filter_bar.addWidget(self.from_date)

        filter_bar.addWidget(QLabel("To:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(date.today())
        self.to_date.dateChanged.connect(self.refresh_all_reports)
        filter_bar.addWidget(self.to_date)

        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # Reports Tabs
        self.tabs = QTabWidget()

        # Tab 1: Product Velocity
        tab_prod = QWidget()
        tp_layout = QVBoxLayout(tab_prod)
        tp_top = QHBoxLayout()
        tp_top.addWidget(QLabel("<b>Product-Wise Sales Summary</b>"))
        tp_top.addStretch()
        exp_prod_btn = QPushButton("Export to Excel")
        exp_prod_btn.setObjectName("SecondaryBtn")
        exp_prod_btn.clicked.connect(self._export_product_sales)
        tp_top.addWidget(exp_prod_btn)
        tp_layout.addLayout(tp_top)

        self.prod_table = QTableWidget()
        self.prod_table.setColumnCount(5)
        self.prod_table.setHorizontalHeaderLabels(["Product Name", "HSN/SAC", "Qty Sold", "Taxable (₹)", "Revenue (₹)"])
        self.prod_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.prod_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.prod_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.prod_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.prod_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        tp_layout.addWidget(self.prod_table)
        self.tabs.addTab(tab_prod, "Product-Wise Sales")

        # Tab 2: GST Tax Summary
        tab_tax = QWidget()
        tt_layout = QVBoxLayout(tab_tax)
        tt_top = QHBoxLayout()
        tt_top.addWidget(QLabel("<b>Statutory GST Tax Summary (For GSTR-1)</b>"))
        tt_top.addStretch()
        exp_tax_btn = QPushButton("Export to Excel")
        exp_tax_btn.setObjectName("SecondaryBtn")
        exp_tax_btn.clicked.connect(self._export_gst_summary)
        tt_top.addWidget(exp_tax_btn)
        tt_layout.addLayout(tt_top)

        self.tax_table = QTableWidget()
        self.tax_table.setColumnCount(7)
        self.tax_table.setHorizontalHeaderLabels([
            "GST Rate", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total Tax (₹)", "Gross Total (₹)"
        ])
        self.tax_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tt_layout.addWidget(self.tax_table)
        self.tabs.addTab(tab_tax, "GST Tax Breakdown")

        # Tab 3: Inventory Valuation
        tab_val = QWidget()
        tv_layout = QVBoxLayout(tab_val)
        tv_top = QHBoxLayout()
        tv_top.addWidget(QLabel("<b>Current Inventory Valuation & Holding Margins</b>"))
        tv_top.addStretch()
        exp_val_btn = QPushButton("Export to Excel")
        exp_val_btn.setObjectName("SecondaryBtn")
        exp_val_btn.clicked.connect(self._export_inventory_valuation)
        tv_top.addWidget(exp_val_btn)
        tv_layout.addLayout(tv_top)

        self.val_kpi_lbl = QLabel()
        self.val_kpi_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B; padding: 6px 0;")
        tv_layout.addWidget(self.val_kpi_lbl)

        self.val_table = QTableWidget()
        self.val_table.setColumnCount(6)
        self.val_table.setHorizontalHeaderLabels([
            "Product Name", "Available Stock", "Unit Cost (₹)", "Selling Price (₹)", "Cost Value (₹)", "Retail Value (₹)"
        ])
        self.val_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.val_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.val_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.val_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.val_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.val_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        tv_layout.addWidget(self.val_table)
        self.tabs.addTab(tab_val, "Inventory Valuation")

        # Tab 4: Profit & Loss Statement
        tab_pl = QWidget()
        tpl_layout = QVBoxLayout(tab_pl)
        tpl_layout.setSpacing(12)

        pl_title = QLabel("<b>Estimated Profit & Loss Statement</b>")
        tpl_layout.addWidget(pl_title)

        pl_card = QFrame()
        pl_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px;")
        pl_box = QVBoxLayout(pl_card)
        pl_box.setSpacing(10)

        self.pl_rev_lbl = QLabel("Taxable Sales Revenue: ₹ 0.00")
        self.pl_rev_lbl.setStyleSheet("font-size: 14px; font-weight: 600;")
        pl_box.addWidget(self.pl_rev_lbl)

        self.pl_cogs_lbl = QLabel("Less: Cost of Goods Sold (COGS): ₹ 0.00")
        self.pl_cogs_lbl.setStyleSheet("font-size: 14px; color: #DC2626;")
        pl_box.addWidget(self.pl_cogs_lbl)

        self.pl_gross_lbl = QLabel("Estimated Gross Profit: ₹ 0.00")
        self.pl_gross_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #2563EB; border-top: 1px solid #E2E8F0; padding-top: 6px;")
        pl_box.addWidget(self.pl_gross_lbl)

        self.pl_exp_lbl = QLabel("Less: Operating Expenses: ₹ 0.00")
        self.pl_exp_lbl.setStyleSheet("font-size: 14px; color: #DC2626;")
        pl_box.addWidget(self.pl_exp_lbl)

        self.pl_net_lbl = QLabel("Estimated Net Profit: ₹ 0.00")
        self.pl_net_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #16A34A; border-top: 2px solid #CBD5E1; padding-top: 8px;")
        pl_box.addWidget(self.pl_net_lbl)

        tpl_layout.addWidget(pl_card)
        tpl_layout.addStretch()
        self.tabs.addTab(tab_pl, "Profit & Loss")

        layout.addWidget(self.tabs)

    def refresh_all_reports(self):
        f_date = self.from_date.date().toPython()
        t_date = self.to_date.date().toPython()

        # 1. Product Sales
        prod_rows = self.reporting_service.get_product_sales_summary(f_date, t_date)
        self.prod_table.setRowCount(len(prod_rows))
        for r, row in enumerate(prod_rows):
            self.prod_table.setItem(r, 0, QTableWidgetItem(row["product_name"]))
            self.prod_table.setItem(r, 1, QTableWidgetItem(row["hsn"]))
            self.prod_table.setItem(r, 2, QTableWidgetItem(f"{row['quantity']:.2f}"))
            self.prod_table.setItem(r, 3, QTableWidgetItem(f"₹ {row['taxable']:,.2f}"))
            self.prod_table.setItem(r, 4, QTableWidgetItem(f"₹ {row['revenue']:,.2f}"))

        # 2. GST Tax Breakdown
        gst_summary = self.reporting_service.get_gst_tax_summary(f_date, t_date)
        b_rows = gst_summary.get("breakdown", [])
        self.tax_table.setRowCount(len(b_rows))
        for r, row in enumerate(b_rows):
            self.tax_table.setItem(r, 0, QTableWidgetItem(f"{row['gst_rate']:.1f}%"))
            self.tax_table.setItem(r, 1, QTableWidgetItem(f"₹ {row['taxable']:,.2f}"))
            self.tax_table.setItem(r, 2, QTableWidgetItem(f"₹ {row['cgst']:,.2f}"))
            self.tax_table.setItem(r, 3, QTableWidgetItem(f"₹ {row['sgst']:,.2f}"))
            self.tax_table.setItem(r, 4, QTableWidgetItem(f"₹ {row['igst']:,.2f}"))
            self.tax_table.setItem(r, 5, QTableWidgetItem(f"₹ {row['total_tax']:,.2f}"))
            self.tax_table.setItem(r, 6, QTableWidgetItem(f"₹ {row['total_gross']:,.2f}"))

        # 3. Inventory Valuation
        val = self.reporting_service.get_inventory_valuation()
        self.val_kpi_lbl.setText(
            f"Total Inventory Cost Value: <b>₹ {val['total_cost_value']:,.2f}</b> | "
            f"Retail Valuation: <b>₹ {val['total_retail_value']:,.2f}</b> | "
            f"Estimated Gross Margin: <b>₹ {val['estimated_gross_profit']:,.2f}</b>"
        )
        val_items = val.get("items", [])
        self.val_table.setRowCount(len(val_items))
        for r, row in enumerate(val_items):
            self.val_table.setItem(r, 0, QTableWidgetItem(row["product_name"]))
            self.val_table.setItem(r, 1, QTableWidgetItem(f"{row['quantity']:.2f}"))
            self.val_table.setItem(r, 2, QTableWidgetItem(f"₹ {row['unit_cost']:,.2f}"))
            self.val_table.setItem(r, 3, QTableWidgetItem(f"₹ {row['selling_price']:,.2f}"))
            self.val_table.setItem(r, 4, QTableWidgetItem(f"₹ {row['cost_value']:,.2f}"))
            self.val_table.setItem(r, 5, QTableWidgetItem(f"₹ {row['retail_value']:,.2f}"))

        # 4. Profit & Loss
        pl = self.reporting_service.get_profit_and_loss(f_date, t_date)
        self.pl_rev_lbl.setText(f"Taxable Sales Revenue: ₹ {pl['taxable_sales_revenue']:,.2f}")
        self.pl_cogs_lbl.setText(f"Less: Cost of Goods Sold (COGS): ₹ {pl['cost_of_goods_sold']:,.2f}")
        self.pl_gross_lbl.setText(f"Estimated Gross Profit: ₹ {pl['estimated_gross_profit']:,.2f}")
        self.pl_exp_lbl.setText(f"Less: Operating Expenses: ₹ {pl['operating_expenses']:,.2f}")
        self.pl_net_lbl.setText(f"Estimated Net Operating Profit: ₹ {pl['estimated_net_profit']:,.2f}")

    def _export_product_sales(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Product Sales Summary", "product_sales_report.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            f_date = self.from_date.date().toPython()
            t_date = self.to_date.date().toPython()
            rows = self.reporting_service.get_product_sales_summary(f_date, t_date)
            data = [[r["product_name"], r["hsn"], r["quantity"], r["taxable"], r["revenue"]] for r in rows]
            self.reporting_service.export_report_to_excel(
                headers=["Product Name", "HSN/SAC", "Quantity Sold", "Taxable Value (₹)", "Revenue (₹)"],
                data_rows=data,
                sheet_title="Product Sales",
                output_file_path=file_path,
            )
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{file_path}")

    def _export_gst_summary(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export GST Summary", "gst_tax_summary.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            f_date = self.from_date.date().toPython()
            t_date = self.to_date.date().toPython()
            gst = self.reporting_service.get_gst_tax_summary(f_date, t_date)
            data = [[r["gst_rate"], r["taxable"], r["cgst"], r["sgst"], r["igst"], r["total_tax"], r["total_gross"]] for r in gst.get("breakdown", [])]
            self.reporting_service.export_report_to_excel(
                headers=["GST Rate (%)", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "IGST (₹)", "Total Tax (₹)", "Gross Total (₹)"],
                data_rows=data,
                sheet_title="GST Tax Summary",
                output_file_path=file_path,
            )
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{file_path}")

    def _export_inventory_valuation(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Inventory Valuation", "inventory_valuation.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            val = self.reporting_service.get_inventory_valuation()
            data = [[i["product_name"], i["sku"], i["quantity"], i["unit_cost"], i["selling_price"], i["cost_value"], i["retail_value"]] for i in val.get("items", [])]
            self.reporting_service.export_report_to_excel(
                headers=["Product Name", "SKU", "Available Stock", "Unit Cost (₹)", "Selling Price (₹)", "Cost Valuation (₹)", "Retail Valuation (₹)"],
                data_rows=data,
                sheet_title="Inventory Valuation",
                output_file_path=file_path,
            )
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{file_path}")
