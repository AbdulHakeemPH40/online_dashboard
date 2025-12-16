# Color Scheme Documentation
## Pasons Group Ecommerce Dashboard

**Documented:** December 10, 2025  
**File:** `templates/item_deletion.html`  
**Purpose:** Complete color scheme reference for the dashboard interface

---

## 🎨 Primary Color Palette

### Brand Colors
| Color | Hex Code | Usage | CSS Variable |
|-------|----------|--------|--------------|
| **Primary Blue** | `#0066CC` | Active tabs, focus states, primary actions | `--primary-blue` |
| **Danger Red** | `#C62828` | Delete buttons, danger actions, warnings | `--danger-red` |
| **Warning Orange** | `#FF9500` | Warning icons, alert boxes | `--warning-orange` |
| **Success Green** | `#28a745` | Success messages, positive actions | `--success-green` |

### Text Colors
| Color | Hex Code | Usage | Examples |
|-------|----------|--------|----------|
| **Primary Text** | `#333333` | Main headings, labels, important text | Page titles, form labels, table headers |
| **Secondary Text** | `#666666` | Secondary text, descriptions | Tab buttons, table stats, help text |
| **Muted Text** | `#999999` | Placeholders, disabled states | Input placeholders, disabled buttons |
| **Light Text** | `#555555` | Table headers, subtle text | Column headers, metadata |

### Background Colors
| Color | Hex Code | Usage | Context |
|-------|----------|--------|---------|
| **White** | `#FFFFFF` | Main backgrounds, cards | Form sections, tables, modals |
| **Light Gray** | `#F5F5F5` | Secondary backgrounds | Filter panels, table headers |
| **Lighter Gray** | `#F9F9F9` | Hover states | Table row hover effects |
| **Off White** | `#FFF8E1` | Warning backgrounds | Alert boxes, warning containers |
| **Light Blue** | `#E3F2FD` | Info backgrounds | Bulk actions bar, info sections |

### Border Colors
| Color | Hex Code | Usage | Components |
|-------|----------|--------|------------|
| **Light Border** | `#E5E5E5` | Subtle dividers | Table borders, section dividers |
| **Medium Border** | `#D0D0D0` | Form borders, cards | Input borders, container borders |
| **Dark Border** | `#C5C5C5` | Focus borders, active states | Input focus, button borders |
| **Warning Border** | `#FFD54F` | Warning borders | Alert box borders |
| **Info Border** | `#BBDEFB` | Info borders | Bulk actions bar borders |

---

## 🎯 Component-Specific Color Schemes

### 1. Navigation & Tabs
```css
/* Active Tab */
.tab-button.active {
    color: #0066CC;
    border-bottom-color: #0066CC;
    font-weight: 600;
}

/* Inactive Tab */
.tab-button {
    color: #666666;
    border-bottom: 2px solid transparent;
}

/* Tab Hover */
.tab-button:hover {
    color: #0066CC;
}
```

### 2. Form Elements
```css
/* Input Fields */
.form-control, .form-select {
    border: 1px solid #C5C5C5;
    color: #333333;
    background: #FFFFFF;
}

/* Input Focus */
.form-control:focus, .form-select:focus {
    border-color: #0066CC;
    box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.1);
}

/* Input Placeholder */
.form-control::placeholder {
    color: #999999;
}
```

### 3. Buttons
```css
/* Primary Button */
.btn-primary {
    background-color: #0066CC;
    color: white;
    border: 1px solid #0055AA;
}

.btn-primary:hover {
    background-color: #0055AA;
}

/* Secondary Button */
.btn-secondary {
    background-color: #F5F5F5;
    color: #333333;
    border: 1px solid #C5C5C5;
}

.btn-secondary:hover {
    background-color: #E5E5E5;
}

/* Danger Button */
.btn-danger {
    background-color: #C62828;
    color: white;
    border: 1px solid #B71C1C;
}

.btn-danger:hover {
    background-color: #B71C1C;
}
```

### 4. Tables
```css
/* Table Header */
.data-table thead {
    background-color: #F5F5F5;
}

.data-table th {
    color: #555555;
    border-bottom: 1px solid #E5E5E5;
}

/* Table Body */
.data-table tbody tr {
    border-bottom: 1px solid #E5E5E5;
}

.data-table tbody tr:hover {
    background-color: #F9F9F9;
}

.data-table td {
    color: #333333;
}
```

### 5. Alert Boxes
```css
/* Warning Alert */
.alert-box {
    background-color: #FFF8E1;
    border: 1px solid #FFD54F;
}

.alert-box-title {
    color: #E65100;
}

.alert-box-text {
    color: #666666;
}

.alert-box i {
    color: #FF9500;
}
```

### 6. Bulk Actions Bar
```css
.bulk-actions-bar {
    background: #E3F2FD;
    border: 1px solid #BBDEFB;
}

.bulk-actions-info {
    color: #0066CC;
}
```

---

## 📱 Responsive Color Adaptations

### Mobile Breakpoints
- **Max-width: 768px**: Maintains all colors but adjusts spacing
- **Max-width: 480px**: Slightly muted colors for better mobile visibility
- **Tablet (769px-1024px)**: Full color palette with adjusted layouts

### Mobile-Specific Adjustments
```css
/* Smaller text colors remain consistent */
@media (max-width: 480px) {
    .page-header h2 { font-size: 16px; color: #333333; }
    .tab-button { font-size: 12px; }
    .form-control { font-size: 13px; }
    .btn { font-size: 13px; }
}
```

---

## 🔄 Color Consistency Rules

### 1. Text Hierarchy
- **Primary**: `#333333` - Most important text (headings, labels)
- **Secondary**: `#666666` - Supporting text (descriptions, stats)
- **Muted**: `#999999` - Least important (placeholders, disabled)

### 2. Interactive Elements
- **Default**: `#666666` (tabs, secondary buttons)
- **Hover**: `#0066CC` (consistent across all interactive elements)
- **Active**: `#0066CC` with visual indicators (borders, backgrounds)

### 3. State Indicators
- **Success**: `#28a745` (green for positive actions)
- **Warning**: `#FF9500` (orange for cautions)
- **Danger**: `#C62828` (red for destructive actions)
- **Info**: `#0066CC` (blue for informational elements)

### 4. Background Layers
- **Layer 1 (Base)**: `#FFFFFF` (main content areas)
- **Layer 2 (Elevated)**: `#F5F5F5` (secondary sections)
- **Layer 3 (Highlighted)**: `#E3F2FD` (special attention areas)

---

## 🎨 CSS Custom Properties (Recommended)

For better maintainability, consider implementing CSS custom properties:

```css
:root {
    /* Brand Colors */
    --color-primary: #0066CC;
    --color-danger: #C62828;
    --color-warning: #FF9500;
    --color-success: #28a745;
    
    /* Text Colors */
    --color-text-primary: #333333;
    --color-text-secondary: #666666;
    --color-text-muted: #999999;
    --color-text-light: #555555;
    
    /* Background Colors */
    --color-bg-primary: #FFFFFF;
    --color-bg-secondary: #F5F5F5;
    --color-bg-tertiary: #F9F9F9;
    --color-bg-warning: #FFF8E1;
    --color-bg-info: #E3F2FD;
    
    /* Border Colors */
    --color-border-light: #E5E5E5;
    --color-border-medium: #D0D0D0;
    --color-border-dark: #C5C5C5;
    --color-border-warning: #FFD54F;
    --color-border-info: #BBDEFB;
}
```

---

## 📋 Implementation Checklist

### Color Scheme Verification
- [ ] All text colors meet WCAG contrast ratios
- [ ] Interactive elements have consistent hover states
- [ ] Warning/danger elements use appropriate colors
- [ ] Mobile responsive colors maintain visibility
- [ ] Form elements have clear focus indicators

### Cross-Template Consistency
- [ ] Button colors match across all templates
- [ ] Alert/notification colors are consistent
- [ ] Table styling matches dashboard theme
- [ ] Form input styling is uniform
- [ ] Modal/dialog colors align with main theme

---

## 🔍 Related Files

### CSS Files
- `static/css/base.css` - Base styles and utilities
- `static/css/retro_modern.css` - Retro-modern theme variables
- `static/css/dashboard.css` - Dashboard-specific styles
- `static/css/modal.css` - Modal component styles

### Template Files
- `templates/base.html` - Base template with global styles
- `templates/item_deletion.html` - Current color scheme reference
- `templates/dashboard.html` - Main dashboard interface
- `templates/bulk_item_creation.html` - Bulk operations styling

---

**Documented by:** AI Assistant  
**Last Updated:** December 10, 2025  
**Status:** ✅ Complete Color Scheme Reference