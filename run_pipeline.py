#!/usr/bin/env python3
"""
Employment Statistics Re-analysis Pipeline Runner
Orchestrates the complete data processing pipeline
"""

import subprocess
import sys
import logging
import pathlib
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_command(command, description, required=True):
    """Run a command and handle errors"""
    logger.info(f"Starting: {description}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"✓ Completed: {description}")
            if result.stdout.strip():
                print(result.stdout)
        else:
            logger.error(f"✗ Failed: {description}")
            if result.stderr:
                print(f"Error: {result.stderr}")
            if required:
                sys.exit(1)
                
    except subprocess.TimeoutExpired:
        logger.error(f"✗ Timeout: {description}")
        if required:
            sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Exception in {description}: {e}")
        if required:
            sys.exit(1)

def main():
    """Run the complete pipeline"""
    print("=== Employment Statistics Re-analysis Pipeline ===")
    print(f"Started at: {datetime.now()}")
    
    # Step 1: Download FRED data
    run_command(
        "python scripts/01_download_fred.py",
        "FRED data download"
    )
    
    # Step 2: Parse BLS PDFs (optional - requires PDF files)
    run_command(
        "python scripts/02_parse_bls_pdf.py",
        "BLS PDF parsing",
        required=False
    )
    
    # Step 3: Merge revisions
    run_command(
        "python scripts/03_merge_revisions.py", 
        "Revision merging"
    )
    
    # Step 4: X-13 seasonal adjustment (optional - requires R)
    run_command(
        "Rscript scripts/04_x13_recalc.R",
        "X-13-ARIMA seasonal adjustment",
        required=False
    )
    
    # Step 5: Data quality check
    run_command(
        "python analysis/data_quality_check.py",
        "Data quality validation"
    )
    
    print(f"\n=== Pipeline completed at: {datetime.now()} ===")
    
    # Show final outputs
    output_files = [
        "data_processed/nfp_revisions.feather",
        "data_processed/nfp_revisions.csv", 
        "data_processed/quality_report.json"
    ]
    
    print("\nOutput files:")
    for file in output_files:
        if pathlib.Path(file).exists():
            size = pathlib.Path(file).stat().st_size / 1024
            print(f"  ✓ {file} ({size:.1f} KB)")
        else:
            print(f"  ✗ {file} (not found)")

if __name__ == "__main__":
    main()