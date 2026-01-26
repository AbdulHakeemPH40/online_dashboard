#!/usr/bin/env python3
"""
clean_price_keep_zero_stock.py

Keep the original six columns and apply the following filters:

1️⃣  Remove rows where Sell.Price is blank OR = 0 (or 0.00).
2️⃣  Remove rows where Stock is blank.
    – KEEP rows where Stock = 0 (or any other numeric value).

Result: only rows with a positive Sell.Price and a non‑blank Stock remain.
"""

import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd

# Suppress warnings to keep console clean
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# ----------------------------------------------------------------------
# 1️⃣  Load the source sheet (Excel or CSV)
# ----------------------------------------------------------------------
def load_sheet(file_path: Path, sheet_name: str = None) -> pd.DataFrame:
    """Read an Excel/CSV file and return a single DataFrame (first sheet if not given)."""
    def pick_one(df_obj):
        if isinstance(df_obj, dict):
            if sheet_name:
                return df_obj[sheet_name]
            return next(iter(df_obj.values()))
        return df_obj

    # Try common Excel engines
    for engine in ("openpyxl", "xlrd", "pyxlsb"):
        try:
            raw = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
            return pick_one(raw)
        except Exception:
            continue

    # CSV fallback
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(file_path, encoding=enc)
        except Exception:
            continue

    raise ValueError("Could not read the file.")


# ----------------------------------------------------------------------
# 2️⃣  Save the cleaned DataFrame
# ----------------------------------------------------------------------
def save_file(df: pd.DataFrame, file_path: Path, sheet_name: str = "Sheet1"):
    """Write the DataFrame to an Excel or CSV file."""
    if file_path.suffix.lower() == ".csv":
        df.to_csv(file_path, index=False)
    else:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)


# ----------------------------------------------------------------------
# 3️⃣  Core cleaning – keep rows where price > 0 and stock is NOT blank
# ----------------------------------------------------------------------
def clean_price_keep_zero_stock(df: pd.DataFrame) -> pd.DataFrame:
    """
    1️⃣  Locate the required columns (case‑insensitive).
    2️⃣  Convert Sell.Price and Stock to numeric (blank → NaN).
    3️⃣  Keep rows where:
            • Sell.Price > 0
            • Stock is NOT NaN   (zero is allowed)
    """
    # ----- 1️⃣  Find the exact column names (allow small spelling differences) -----
    needed = {
        "item code": None, 
        "unit": None,
        "sell.price": None, 
        "cost pr.": None, 
        "stock": None
    }
    for col in df.columns:
        key = col.strip().lower()
        if key in needed:
            needed[key] = col

    missing = [k for k, v in needed.items() if v is None]
    if missing:
        raise KeyError(f"Missing required column(s): {', '.join(missing)}")

    # Re‑order exactly as you need
    df = df[[
        needed["item code"], 
        needed["unit"],
        needed["sell.price"], 
        needed["cost pr."], 
        needed["stock"]
    ]].copy()

    # ----- 2️⃣  Convert to numeric (invalid strings → NaN) -----
    # Use the mapped column names to avoid creating new columns or warnings
    price_col = needed["sell.price"]
    stock_col = needed["stock"]

    df.loc[:, price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df.loc[:, stock_col] = pd.to_numeric(df[stock_col], errors="coerce")

    # ----- 3️⃣  Apply the two filters -----
    #   • price must be > 0 (blank or 0 are removed)
    #   • stock must NOT be NaN (blank removed) – zero is kept
    keep_mask = (df[price_col] > 0) & (~df[stock_col].isna())
    df = df[keep_mask].reset_index(drop=True)

    # ----- 4️⃣  Rename headers for export -----
    df = df.rename(columns={
        needed["item code"]: "item_code",
        needed["unit"]: "units",
        needed["sell.price"]: "mrp",
        needed["cost pr."]: "cost",
        needed["stock"]: "stock"
    })

    # ----- 5️⃣  Convert item_code to integer (remove .00) -----
    item_code_col = "item_code"
    df[item_code_col] = pd.to_numeric(df[item_code_col], errors="coerce")
    df[item_code_col] = df[item_code_col].fillna(0).astype(int)

    return df


# ----------------------------------------------------------------------
# 4️⃣  CLI
# ----------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove rows where Sell.Price is 0/blank and where Stock is blank "
                    "(keep Stock = 0)."
    )
    parser.add_argument("-i", "--input", type=Path,
                        required=True,
                        help="Source workbook (.xlsx or .csv).")
    parser.add_argument("-o", "--output", type=Path,
                        required=True,
                        help="File to write cleaned data.")
    parser.add_argument("-s", "--sheet", type=str, default=None,
                        help="Sheet name (default: first sheet).")
    return parser.parse_args()


def process_cleaning(input_path: Path, output_path: Path, sheet_name: str = None):
    """Functional entry point for Django integration"""
    df = load_sheet(input_path, sheet_name=sheet_name)
    cleaned = clean_price_keep_zero_stock(df)
    save_file(cleaned, output_path, sheet_name=sheet_name or "Sheet1")
    return output_path


def main():
    args = parse_args()
    try:
        process_cleaning(args.input, args.output, args.sheet)
    except Exception as e:
        sys.exit(1)


if __name__ == "__main__":
    main()