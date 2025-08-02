#!/usr/bin/env python3
"""
BLS PDF Parsing Script for Employment Statistics Re-analysis
Extracts employment data from BLS Employment Situation PDF reports
"""

import pandas as pd
import re
import glob
import pathlib
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BLSPDFParser:
    """Parses BLS Employment Situation PDF reports to extract NFP data"""
    
    def __init__(self, pdf_dir: str = "data_raw/bls_pdf", output_dir: str = "data_processed"):
        self.pdf_dir = pathlib.Path(pdf_dir)
        self.output_dir = pathlib.Path(output_dir)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to import tabula-py
        try:
            import tabula
            self.tabula = tabula
            self.tabula_available = True
        except ImportError:
            logger.warning("tabula-py not available. PDF parsing will be limited to text extraction.")
            self.tabula_available = False
    
    def extract_filename_info(self, pdf_path: str) -> Optional[Dict[str, str]]:
        """
        Extract date and release version from filename
        Expected format: empsit_YYYY_MM_v[1-3].pdf
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with year, month, version, and date
        """
        filename = pathlib.Path(pdf_path).name
        
        # Pattern: empsit_YYYY_MM_v[1-3].pdf
        pattern = r'empsit_(\d{4})_(\d{2})_v(\d)\.pdf'
        match = re.search(pattern, filename)
        
        if match:
            year, month, version = match.groups()
            return {
                'year': year,
                'month': month,
                'version': version,
                'date': f"{year}-{month}-01",
                'filename': filename
            }
        
        # Alternative pattern: YYYY_MM_employment_v[1-3].pdf
        pattern2 = r'(\d{4})_(\d{2})_employment_v(\d)\.pdf'
        match2 = re.search(pattern2, filename)
        
        if match2:
            year, month, version = match2.groups()
            return {
                'year': year,
                'month': month,
                'version': version,
                'date': f"{year}-{month}-01",
                'filename': filename
            }
        
        logger.warning(f"Could not parse filename: {filename}")
        return None
    
    def parse_pdf_with_tabula(self, pdf_path: str) -> Optional[Dict]:
        """
        Parse PDF using tabula-py to extract table data
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with extracted data or None if failed
        """
        if not self.tabula_available:
            return None
            
        try:
            # Extract tables from PDF - focus on page 3 where Table B-1 usually is
            tables = self.tabula.read_pdf(pdf_path, pages=[3, 4, 5], lattice=True, multiple_tables=True)
            
            for i, df in enumerate(tables):
                if df is None or df.empty:
                    continue
                    
                # Look for "Total nonfarm" row
                for col in df.columns:
                    mask = df[col].astype(str).str.contains('Total nonfarm', case=False, na=False)
                    if mask.any():
                        nonfarm_row = df[mask]
                        
                        # Extract numeric values from the row
                        numeric_cols = []
                        for col_name in df.columns:
                            if col_name != col:  # Skip the industry name column
                                try:
                                    # Clean and convert values
                                    vals = nonfarm_row[col_name].astype(str).str.replace(',', '').str.replace('r', '')
                                    vals = vals.str.extract(r'(-?\d+(?:\.\d+)?)', expand=False)
                                    numeric_vals = pd.to_numeric(vals, errors='coerce')
                                    if not numeric_vals.isna().all():
                                        numeric_cols.append({
                                            'column': col_name,
                                            'value': numeric_vals.iloc[0]
                                        })
                                except Exception as e:
                                    continue
                        
                        if numeric_cols:
                            # Return the last (most recent) numeric column
                            latest_value = numeric_cols[-1]['value']
                            return {
                                'nonfarm_payroll': int(latest_value * 1000) if latest_value < 1000 else int(latest_value),
                                'table_index': i,
                                'source_column': numeric_cols[-1]['column']
                            }
                            
        except Exception as e:
            logger.error(f"Failed to parse PDF with tabula: {e}")
            
        return None
    
    def parse_pdf_text_fallback(self, pdf_path: str) -> Optional[Dict]:
        """
        Fallback method to extract text and find employment numbers
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with extracted data or None if failed
        """
        try:
            # Try using PyPDF2 or pdfplumber as fallback
            try:
                import pdfplumber
                
                with pdfplumber.open(pdf_path) as pdf:
                    text = ""
                    for page in pdf.pages[:10]:  # First 10 pages
                        text += page.extract_text() or ""
                        
            except ImportError:
                try:
                    import PyPDF2
                    
                    with open(pdf_path, 'rb') as file:
                        reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in reader.pages[:10]:
                            text += page.extract_text()
                            
                except ImportError:
                    logger.error("No PDF parsing library available (tabula-py, pdfplumber, or PyPDF2)")
                    return None
            
            # Look for employment numbers in text
            # Pattern: "Total nonfarm payroll employment rose by 123,000"
            patterns = [
                r'Total nonfarm payroll employment (?:rose|increased|fell|decreased) by ([\d,]+)',
                r'Nonfarm payroll employment (?:rose|increased|fell|decreased) by ([\d,]+)',
                r'Total nonfarm.*?(\d{1,3}(?:,\d{3})*)',
                r'payroll employment.*?(\d{1,3}(?:,\d{3})*)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Take the first reasonable match
                    for match in matches:
                        try:
                            value = int(match.replace(',', ''))
                            if 10000 <= value <= 1000000:  # Reasonable range for NFP
                                return {
                                    'nonfarm_payroll': value,
                                    'extraction_method': 'text_pattern',
                                    'pattern_used': pattern
                                }
                        except ValueError:
                            continue
                            
        except Exception as e:
            logger.error(f"Failed to parse PDF text: {e}")
            
        return None
    
    def parse_single_pdf(self, pdf_path: str) -> Optional[Dict]:
        """
        Parse a single PDF file
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with parsed data or None if failed
        """
        file_info = self.extract_filename_info(pdf_path)
        if not file_info:
            return None
            
        logger.info(f"Parsing {pdf_path}")
        
        # Try tabula first, then fallback to text extraction
        result = self.parse_pdf_with_tabula(pdf_path)
        if result is None:
            result = self.parse_pdf_text_fallback(pdf_path)
            
        if result is None:
            logger.error(f"Failed to extract data from {pdf_path}")
            return None
            
        # Combine file info with parsed data
        result.update(file_info)
        result['pdf_path'] = str(pdf_path)
        
        logger.info(f"Extracted NFP value: {result['nonfarm_payroll']:,} for {result['date']} (v{result['version']})")
        
        return result
    
    def parse_all_pdfs(self) -> pd.DataFrame:
        """
        Parse all PDF files in the directory
        
        Returns:
            DataFrame with all parsed data
        """
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {self.pdf_dir}")
            return pd.DataFrame()
            
        logger.info(f"Found {len(pdf_files)} PDF files to parse")
        
        results = []
        for pdf_path in pdf_files:
            result = self.parse_single_pdf(str(pdf_path))
            if result:
                results.append(result)
                
        if not results:
            logger.error("No data extracted from any PDF files")
            return pd.DataFrame()
            
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Pivot to get releases by version
        pivot_df = df.pivot_table(
            index='date',
            columns='version',
            values='nonfarm_payroll',
            aggfunc='first'
        ).reset_index()
        
        # Rename columns
        pivot_df.columns = ['date'] + [f'release{col}' for col in pivot_df.columns[1:]]
        
        # Convert date column
        pivot_df['date'] = pd.to_datetime(pivot_df['date'])
        
        logger.info(f"Successfully parsed {len(results)} records into {len(pivot_df)} unique dates")
        
        return pivot_df
    
    def save_parsed_data(self, df: pd.DataFrame) -> pathlib.Path:
        """
        Save parsed data to file
        
        Args:
            df: DataFrame to save
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / "bls_releases.parquet"
        df.to_parquet(output_path, index=False)
        
        # Also save as CSV for inspection
        csv_path = self.output_dir / "bls_releases.csv"
        df.to_csv(csv_path, index=False)
        
        logger.info(f"Saved parsed data to {output_path} and {csv_path}")
        
        return output_path


def main():
    """Main execution function"""
    try:
        parser = BLSPDFParser()
        
        # Parse all PDFs
        df = parser.parse_all_pdfs()
        
        if df.empty:
            logger.error("No data was parsed from PDF files")
            return 1
            
        # Save results
        output_path = parser.save_parsed_data(df)
        
        # Print summary
        print(f"\n=== BLS PDF Parsing Summary ===")
        print(f"PDF files processed: {len(glob.glob('data_raw/bls_pdf/*.pdf'))}")
        print(f"Unique dates parsed: {len(df)}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Output saved to: {output_path}")
        
        # Show sample of parsed data
        print(f"\nSample of parsed data:")
        print(df.head())
        
        return 0
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())