"""
Finance Module Models - Entry Point
All financial models organized by domain
"""

# Core Configuration Models
from .core import (
    FinanceSettings,
    FiscalYear,
    FinancialPeriod,
)

# Multi-Currency Support
from .currency import (
    Currency,
    ExchangeRate,
)

# Chart of Accounts
from .accounts import (
    AccountCategory,
    Account,
)

# Tax Management
from .tax import (
    TaxCode,
    TaxGroup,
    TaxGroupItem,
)

# Journal Entries & Transactions
from .journal import (
    JournalEntry,
    JournalEntryLine,
)

# Inventory Cost Integration
from .inventory_costing import (
    InventoryCostLayer,
    InventoryCostConsumption,
    LandedCost,
    LandedCostAllocation,
)

# Bank & Reconciliation
from .bank import (
    BankAccount,
    BankStatement,
    BankTransaction,
    BankReconciliation,
    ReconciliationAdjustment,
    ReconciliationRule,
    ReconciliationLog,
)

# Vendor Management
from .vendors import (
    Vendor,
    VendorContact,
    Bill,
    BillItem,
)

# Customer Invoicing
from .invoicing import (
    Invoice,
    InvoiceItem,
)

# Payment Processing
from .payments import (
    Payment,
    PaymentApplication,
)

# CRM Integration
from .crm_integration import (
    CustomerFinancialProfile,
    LeadFinancialData,
)

# Organization & Projects
from .organization import (
    Project,
    ProjectTeamMember,
    Department,
    Location,
)

# Budgeting & Planning
from .budgeting import (
    BudgetTemplate,
    BudgetTemplateItem,
    Budget,
    BudgetItem,
)

# All models for convenience
__all__ = [
    # Core Configuration
    'FinanceSettings',
    'FiscalYear', 
    'FinancialPeriod',
    
    # Multi-Currency
    'Currency',
    'ExchangeRate',
    
    # Chart of Accounts
    'AccountCategory',
    'Account',
    
    # Tax Management
    'TaxCode',
    'TaxGroup',
    'TaxGroupItem',
    
    # Journal Entries
    'JournalEntry',
    'JournalEntryLine',
    
    # Inventory Costing
    'InventoryCostLayer',
    'InventoryCostConsumption',
    'LandedCost',
    'LandedCostAllocation',
    
    # Bank Reconciliation
    'BankAccount',
    'BankStatement',
    'BankTransaction',
    'BankReconciliation',
    'ReconciliationAdjustment',
    'ReconciliationRule',
    'ReconciliationLog',
    
    # Vendors & Bills
    'Vendor',
    'VendorContact',
    'Bill',
    'BillItem',
    
    # Customer Invoicing
    'Invoice',
    'InvoiceItem',
    
    # Payments
    'Payment',
    'PaymentApplication',
    
    # CRM Integration
    'CustomerFinancialProfile',
    'LeadFinancialData',
    
    # Organization
    'Project',
    'ProjectTeamMember',
    'Department',
    'Location',
    
    # Budgeting
    'BudgetTemplate',
    'BudgetTemplateItem',
    'Budget',
    'BudgetItem',
]