# Wrap-Based Pricing and Cascade Logic Documentation

## CRITICAL: Read Before Modifying Price/Product Update Code

This document explains the complex pricing logic for wrap=9900 (weighed items) and wrap=10000 (packaged items). **All future code changes MUST preserve this logic.**

---

## Table of Contents
1. [Wrap Types Overview](#wrap-types-overview)
2. [WDF (Weight Division Factor)](#wdf-weight-division-factor)
3. [Parent vs Child Detection](#parent-vs-child-detection)
4. [Multiple SKUs per (item_code, units)](#multiple-skus-per-item_code-units)
5. [Wrap=10000 Isolation](#wrap10000-isolation)
6. [Cascade Logic (Parent → Children)](#cascade-logic-parent--children)
7. [Real-World Examples](#real-world-examples)
8. [Code Locations](#code-locations)
9. [Common Bugs and How They Were Fixed](#common-bugs-and-how-they-were-fixed)

---

## Wrap Types Overview

| Wrap | Type | Examples | WDF Used? | Cascade? |
|------|------|----------|-----------|----------|
| **9900** | Weighed items (by weight) | KGS, 500GM, 250GM, 100GM | ✅ Yes | ✅ Parent→Children |
| **10000** | Packaged items (by unit) | BAG, PKT, 18KG, CASE | ❌ No | ❌ None |

### Key Difference:
- **wrap=9900**: Price is per-KG, children get `selling_price = MRP ÷ WDF`
- **wrap=10000**: Price is per-unit, `selling_price = MRP` (no division)

---

## WDF (Weight Division Factor)

WDF tells you how many smaller units fit into 1 KG:

```
WDF=1:   1 KG = 1 unit           (parent - whole KG)
WDF=2:   1 KG = 2 × 500GM        (child)
WDF=4:   1 KG = 4 × 250GM        (child)
WDF=10:  1 KG = 10 × 100GM       (child)
```

### Price Calculation:
```python
# Parent (WDF=1): selling_price = MRP
# Child (WDF>1):  selling_price = MRP ÷ WDF

# Example: MRP = 10.00 AED per KG
WDF=1  → selling = 10.00 ÷ 1  = 10.00 AED (1 KG)
WDF=2  → selling = 10.00 ÷ 2  = 5.00 AED  (500GM)
WDF=4  → selling = 10.00 ÷ 4  = 2.50 AED  (250GM)
WDF=10 → selling = 10.00 ÷ 10 = 1.00 AED  (100GM)
```

---

## Parent vs Child Detection

### ❌ WRONG: SKU-based detection
```python
# DO NOT USE - SKU can be anything from CSV!
is_parent = str(item.sku) == str(item.item_code)
```

### ✅ CORRECT: WDF-based detection
```python
wdf = item.weight_division_factor or Decimal('1')
is_parent = wdf == Decimal('1')
```

### Why WDF-based?
- SKU comes from CSV during bulk-item-creation (can be ANY value)
- WDF is always set correctly based on unit size
- Reliable detection regardless of SKU format

### Example:
| item_code | SKU | WDF | is_parent |
|-----------|-----|-----|-----------|
| 9900313 | 9900465 | 1 | ✅ True (1 KG) |
| 9900313 | 9900313500 | 2 | ❌ False (500GM) |

---

## Multiple SKUs per (item_code, units)

### Problem:
Some item_codes have multiple SKUs with the SAME units but different WDF:

| item_code | SKU | units | WDF | Size |
|-----------|-----|-------|-----|------|
| 9900127 | 9900127250 | KGS | 4 | 250GM |
| 9900127 | 9900127100 | KGS | 10 | 100GM |

### Solution: Store LIST of items per key
```python
# OLD (BUGGY): Only one item per key
items_map[(item_code, units)] = item  # ❌ Overwrites!

# NEW (FIXED): List of all matching items
items_map[(item_code, units)] = [item1, item2, ...]  # ✅ All items
```

### Processing Loop:
```python
# Process EACH item that matches (item_code, units)
items_list = items_map.get((item_code, units), [])
for item in items_list:
    # Calculate selling_price using THIS item's WDF
    wdf = item.weight_division_factor or Decimal('1')
    selling_price = mrp / wdf
    # Create/update ItemOutlet for THIS item
```

---

## Wrap=10000 Isolation

### Problem:
wrap=10000 items (BAG, PKT) were being affected by wrap=9900 cascade.

### Example:
| item_code | SKU | units | wrap | Expected Behavior |
|-----------|-----|-------|------|-------------------|
| 9900606 | 9900606 | KGS | 9900 | Cascade to children |
| 9900606 | 6291107830049 | BAG | 10000 | **NO cascade** - separate item |

### Solution: Filter cascade by wrap
```python
# Only cascade to wrap=9900 children
sibling_items = Item.objects.filter(
    item_code=item_code,
    platform=platform,
    wrap='9900'  # ✅ Only wrap=9900
).exclude(weight_division_factor=Decimal('1'))
```

### Key Rules:
1. wrap=10000 items are **NEVER** affected by wrap=9900 cascade
2. wrap=10000 items update **independently** with their own MRP
3. Same item_code can have BOTH wrap=9900 (KGS) and wrap=10000 (BAG) variants

---

## Cascade Logic (Parent → Children)

### When Does Cascade Trigger?
```python
# ONLY from Parent (WDF=1) TO Children (WDF>1)
wdf = item.weight_division_factor or Decimal('1')
is_parent = wdf == Decimal('1')

if item.wrap == '9900' and is_parent:
    # Find children and cascade
```

### SKU Pattern Check (REMOVED - Dec 2024)
~~Only cascade to children whose **SKU starts with item_code**~~

**UPDATE (Dec 15, 2024):** SKU pattern check was removed. Now uses WDF-only check:
```python
# Only cascade to CHILDREN (WDF > 1), not to other parents
child_wdf = child_item.weight_division_factor or Decimal('1')
if child_wdf == Decimal('1'):
    continue  # Skip - this is another parent
```

**Example - item_code 9900422:**
| SKU | WDF | Will Cascade? |
|-----|-----|---------------|
| 9900448 | 1 | ❌ No (parent) |
| 9900422500 | 2 | ✅ Yes (child) |
| 9900445500 | 2 | ✅ Yes (child) |

All children (WDF > 1) with same item_code will cascade, regardless of SKU naming.

### What Gets Cascaded?
1. **MRP**: Children get same MRP as parent
2. **Selling Price**: `child_selling = MRP ÷ child_wdf`
3. **Cost**: Children get same cost as parent
4. **Stock**: `child_stock = parent_stock × child_wdf`

### Bidirectional Cascade Bug (FIXED):
```python
# ❌ WRONG: Cascade from ANY item (causes child→parent cascade)
if item.wrap == '9900':
    # This caused child updates to cascade BACK to parent!

# ✅ CORRECT: Only cascade FROM parent TO children
if item.wrap == '9900' and is_parent:
    sibling_items = Item.objects.filter(...).exclude(weight_division_factor=Decimal('1'))
```

---

## Real-World Examples

### Example 1: 9900313/9900465 (Parent/Child)
```
item_code=9900313:
├── SKU=9900465, Units=KGS., WDF=1, wrap=9900 → PARENT
│   CSV: MRP=9.95
│   Result: selling_price=9.95
│
└── SKU=9900313500, Units=KGS, WDF=2, wrap=9900 → CHILD
    Cascaded: MRP=9.95 (from parent)
    Result: selling_price = 9.95 ÷ 2 = 4.98
```

### Example 2: 9900606 (KGS + BAG)
```
item_code=9900606:
├── SKU=9900606, Units=KGS, WDF=1, wrap=9900
│   CSV: MRP=4.95
│   Result: selling_price=4.95
│
└── SKU=6291107830049, Units=BAG, wrap=10000 ← SEPARATE ITEM
    CSV: MRP=57.00 (different row in CSV)
    Result: selling_price=57.00 (NO cascade from KGS)
```

### Example 3: 9900127 (Multiple SKUs, Same Units)
```
item_code=9900127, units=KGS:
├── SKU=9900127250, WDF=4 (250GM)
│   CSV Row: item_code=9900127, units=KGS, mrp=11.95
│   Result: selling_price = 11.95 ÷ 4 = 2.99
│
└── SKU=9900127100, WDF=10 (100GM)
    SAME CSV Row: item_code=9900127, units=KGS, mrp=11.95
    Result: selling_price = 11.95 ÷ 10 = 1.20

Both SKUs updated from ONE CSV row!
```

---

## Code Locations

### views.py - product_update function:

| Line Range | Purpose |
|------------|---------|
| ~920-936 | items_map building (stores LIST per key) |
| ~939-941 | Flatten items for bulk fetch |
| ~1017-1018 | Process ALL items in list |
| ~1070-1076 | WDF-based parent detection |
| ~1078-1099 | Platform-specific selling_price (Pasons vs Talabat) |
| ~1105-1120 | wrap=10000 handling (no WDF division) |
| ~1194-1196 | Cascade trigger (parent only) |
| ~1197-1293 | Cascade to children |

### Key Functions:
- `compute_data_hash()` - Hash-based change detection
- `update_item_outlet_hash()` - Update hash after changes
- `PricingCalculator.calculate_talabat_price()` - Talabat margin calculation

---

## Common Bugs and How They Were Fixed

### Bug 1: SKU-based Parent Detection
**Problem**: `is_parent = SKU == item_code` failed when SKU was custom.
**Fix**: Use WDF: `is_parent = wdf == Decimal('1')`

### Bug 2: Single Item per (item_code, units)
**Problem**: Only first SKU got ItemOutlet when multiple SKUs had same units.
**Fix**: Changed `items_map[key] = item` to `items_map[key] = [list]`

### Bug 3: wrap=10000 Affected by Cascade
**Problem**: BAG items got KGS prices due to cascade.
**Fix**: Added `wrap='9900'` filter to cascade query.

### Bug 4: Bidirectional Cascade
**Problem**: Child updates cascaded back to parent, swapping prices.
**Fix**: Only cascade when `is_parent = (wdf == Decimal('1'))`

### Bug 5: Cascade Saving Individually (Performance)
**Problem**: Each sibling saved individually → 5+ minutes for large CSVs.
**Fix**: Pre-fetch all siblings, collect updates, bulk_update at end.

### Bug 6: Different Products Sharing Same item_code (Dec 2024)
**Problem**: ERP sometimes assigns same item_code to different products (e.g., Paya, With Bone, Boneless all under 9900422).

**Solution**: Use WDF to determine parent vs child:
- WDF=1 → Parent (won't receive cascade)
- WDF>1 → Child (will receive cascade)

```python
child_wdf = child_item.weight_division_factor or Decimal('1')
if child_wdf == Decimal('1'):
    continue  # Skip - this is another parent
```

**Result**: All children (WDF > 1) with same item_code receive cascade. Parents (WDF=1) don't cascade to each other.

---

## Platform Differences

| Platform | Selling Price Formula |
|----------|----------------------|
| **Pasons** | `selling = MRP ÷ WDF` (no margin) |
| **Talabat** | `selling = (MRP ÷ WDF) + margin` |

### Code:
```python
if platform == 'talabat':
    base_price = (mrp / wdf).quantize(Decimal('0.01'))
    selling_price = calc.calculate_talabat_price(base_price, margin)
else:  # Pasons
    selling_price = (mrp / wdf).quantize(Decimal('0.01'))
```

---

## Checklist for Future Changes

Before modifying price/product update code:

- [ ] Does change preserve WDF-based parent detection?
- [ ] Does change handle multiple SKUs per (item_code, units)?
- [ ] Does change keep wrap=10000 isolated from wrap=9900 cascade?
- [ ] Does cascade only go from parent (WDF=1) to children (WDF>1)?
- [ ] Does cascade check WDF (only cascade to WDF > 1)?
- [ ] Does change work for BOTH Pasons and Talabat platforms?
- [ ] Are bulk operations used (not individual saves in loops)?

---

## Test Cases

After any changes, verify these items at store_id=100001:

| item_code | Expected Behavior |
|-----------|-------------------|
| 9900313 | Parent (9900465) and child (9900313500) both have ItemOutlet |
| 9900127 | BOTH SKUs (9900127250, 9900127100) have ItemOutlet |
| 9900606 | KGS and BAG have DIFFERENT MRPs (not cascaded) |
| 9900613 | KGS and BAG have DIFFERENT MRPs (not cascaded) |
| 9900422 | Different products (Paya, With Bone, Boneless) have INDEPENDENT prices |

---

*Last Updated: December 15, 2024*
*Bug 6 Fix: SKU pattern check for different products under same item_code*
*Related Files: integration/views.py, integration/models.py*
