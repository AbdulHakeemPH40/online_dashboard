# Complete Business Workflow - Pasons ERP

## 📋 STEP-BY-STEP BUSINESS PROCESS

### **STEP 1: Initial Item Creation** (One-time setup)
**URL**: `http://127.0.0.1:8000/integration/bulk-item-creation/`
**Purpose**: Create new items in the system
**Frequency**: First time only, when adding new products

**What happens:**
- Creates new `Item` records
- Creates corresponding `ItemOutlet` records
- Sets initial MRP, cost, stock, selling_price
- Applies initial margins (17% wrap=9900, 15% wrap=10000, or custom)
- Platform isolation enforced

---

### **STEP 2: Daily Price Updates** (Regular operations)
**URL**: `http://127.0.0.1:8000/integration/product-update/`
**Purpose**: Update MRP → automatically recalculate selling_price
**Frequency**: Every day

**Platform Logic:**
- **Pasons**: MRP = Selling Price (same price, no margin)
- **Talabat**: MRP + Margin + Smart Rounding = Selling Price

**Margin Application:**
- **wrap=9900**: 17% margin (weight-based items)
- **wrap=10000**: 15% margin (regular items)
- **Custom margins**: User can set via CSV or rules-update-price

**What gets updated:**
- `outlet_mrp` → New MRP from CSV
- `outlet_selling_price` → **AUTO-CALCULATED** from MRP + margin + rounding
- Platform & outlet isolated (only selected platform affected)

---

### **STEP 3: Custom Margin Updates** (As needed)
**URL**: `http://127.0.0.1:8000/integration/rules-update-price/`
**Purpose**: Apply custom margins to Talabat items
**Frequency**: When needed (override default 15%/17%)

**Logic:**
- Allows custom margin percentages (0-100%)
- Only affects Talabat platform
- Overrides default margins
- Recalculates selling_price with new margin

---

### **STEP 4: Promotion Updates** (Special events)
**URL**: `http://127.0.0.1:8000/integration/bulk-item-creation/` (during promotions)
**Purpose**: Update prices during weekend/midweek/special promotions
**Frequency**: When promotions are active

**CRITICAL BEHAVIOR - Both prices update:**
1. **Selling Price**: Updated with new MRP + margin calculation
2. **Promo Price**: Also gets updated automatically
3. **Auto-adjustment**: Both prices adjust together

**Logic:**
- Regular selling_price gets recalculated from new MRP
- Promotion system also updates promo_price
- Both prices stay synchronized
- Platform isolation maintained

---

## 🔄 ADDITIONAL PROCESSING

### **Cost Price Conversion**
**What happens during updates:**
- `outlet_cost` → Updated from CSV
- `outlet_converted_cost` → **AUTO-CALCULATED** based on wrap type:
  - **wrap=9900**: cost ÷ weight_division_factor
  - **wrap=10000**: cost (as-is)

### **Stock Status Validation**
**What gets checked:**
- Stock quantity validation
- Outer case quantity compliance
- Minimum quantity requirements
- Status lock enforcement (CLS/BLS)
- `is_active_in_outlet` status management

---

## 📊 COMPLETE UPDATE MATRIX

| Update Type | Selling Price | Promo Price | Cost Conversion | Stock Validation |
|-------------|---------------|-------------|-----------------|------------------|
| **Initial Creation** | ✅ Calculated | ❌ Not set | ✅ Calculated | ✅ Validated |
| **Daily MRP Update** | ✅ Recalculated | ❌ Preserved | ❌ Unchanged | ❌ Unchanged |
| **Cost Update** | ❌ Unchanged | ❌ Unchanged | ✅ Recalculated | ❌ Unchanged |
| **Stock Update** | ❌ Unchanged | ❌ Unchanged | ❌ Unchanged | ✅ Validated |
| **Promotion Update** | ✅ Recalculated | ✅ **AUTO-ADJUSTED** | ✅ If cost included | ✅ If stock included |

---

## 🎯 KEY INSIGHTS

### **Promotion Period Behavior:**
- **Regular updates**: Only selling_price changes
- **Promotion updates**: **BOTH selling_price AND promo_price change together**
- **Auto-adjustment**: Promotion system keeps both prices synchronized

### **Platform Isolation:**
- **Pasons**: No margins, exact MRP prices
- **Talabat**: Margins + smart rounding applied
- **Updates**: Only affect selected platform/outlet

### **Wrap Item Logic:**
- **wrap=9900**: Base price = MRP ÷ weight_division_factor, then margin
- **wrap=10000**: Base price = MRP, then margin
- **Cost conversion**: Applied based on wrap type

### **Zero Margin Special Case:**
- **0% margin**: Exact prices (no .00 → .99 conversion)
- **Non-zero margins**: Smart rounding applied (.25, .49, .75, .99)

This complete workflow ensures all pricing, cost conversion, and stock validation work together seamlessly across your business operations!