#!/usr/bin/env python3
"""
FRED Data Download Script for Employment Statistics Re-analysis
Downloads PAYEMS (Total Nonfarm Payroll Employment) from FRED with timestamped snapshots
"""

import pandas as pd
import requests
import datetime
import pathlib
import logging
import sys
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FREDDataDownloader:
    """Downloads and manages FRED employment data snapshots"""
    
    def __init__(self, base_dir: str = "data_raw/fred_snapshots"):
        self.base_dir = pathlib.Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.fred_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS"
        
    def download_payems(self, date_suffix: Optional[str] = None) -> pd.DataFrame:
        """
        Download PAYEMS data from FRED
        
        Args:
            date_suffix: Optional date suffix for filename. If None, uses current date.
            
        Returns:
            DataFrame with DATE and PAYEMS columns
        """
        try:
            logger.info(f"Downloading PAYEMS data from FRED...")
            response = requests.get(self.fred_url, timeout=30)
            response.raise_for_status()
            
            # Parse CSV data
            df = pd.read_csv(pd.io.common.StringIO(response.text), parse_dates=["DATE"])
            
            # Remove any rows with missing values
            df = df.dropna()
            
            # Validate data
            if len(df) == 0:
                raise ValueError("Downloaded data is empty")
                
            logger.info(f"Successfully downloaded {len(df)} records")
            logger.info(f"Date range: {df['DATE'].min()} to {df['DATE'].max()}")
            
            return df
            
        except requests.RequestException as e:
            logger.error(f"Failed to download data from FRED: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing FRED data: {e}")
            raise
    
    def save_snapshot(self, df: pd.DataFrame, date_suffix: Optional[str] = None) -> pathlib.Path:
        """
        Save DataFrame as timestamped snapshot
        
        Args:
            df: DataFrame to save
            date_suffix: Optional date suffix. If None, uses current date.
            
        Returns:
            Path to saved file
        """
        if date_suffix is None:
            date_suffix = datetime.date.today().strftime("%Y%m%d")
            
        filename = f"PAYEMS_{date_suffix}.csv"
        filepath = self.base_dir / filename
        
        # Save with timestamp and metadata
        df_with_meta = df.copy()
        df_with_meta.attrs['download_date'] = datetime.datetime.now().isoformat()
        df_with_meta.attrs['source'] = 'FRED'
        df_with_meta.attrs['series_id'] = 'PAYEMS'
        
        df.to_csv(filepath, index=False)
        logger.info(f"Saved snapshot to {filepath}")
        
        return filepath
    
    def get_latest_snapshot(self) -> Optional[pd.DataFrame]:
        """
        Load the most recent snapshot
        
        Returns:
            Most recent DataFrame or None if no snapshots exist
        """
        snapshot_files = list(self.base_dir.glob("PAYEMS_*.csv"))
        
        if not snapshot_files:
            logger.warning("No snapshots found")
            return None
            
        # Sort by filename (date) and get the latest
        latest_file = sorted(snapshot_files)[-1]
        logger.info(f"Loading latest snapshot: {latest_file}")
        
        return pd.read_csv(latest_file, parse_dates=["DATE"])
    
    def compare_with_previous(self, current_df: pd.DataFrame) -> dict:
        """
        Compare current data with previous snapshot
        
        Args:
            current_df: Current DataFrame to compare
            
        Returns:
            Dictionary with comparison statistics
        """
        previous_df = self.get_latest_snapshot()
        
        if previous_df is None:
            return {"status": "no_previous_data"}
        
        # Find overlapping date range
        common_dates = set(current_df['DATE']).intersection(set(previous_df['DATE']))
        
        if not common_dates:
            return {"status": "no_overlap"}
        
        # Merge on common dates
        comparison = pd.merge(
            current_df[current_df['DATE'].isin(common_dates)][['DATE', 'PAYEMS']],
            previous_df[previous_df['DATE'].isin(common_dates)][['DATE', 'PAYEMS']],
            on='DATE',
            suffixes=('_current', '_previous')
        )
        
        # Calculate differences
        comparison['diff'] = comparison['PAYEMS_current'] - comparison['PAYEMS_previous']
        
        # Summary statistics
        n_changed = (comparison['diff'] != 0).sum()
        max_change = comparison['diff'].abs().max()
        
        result = {
            "status": "compared",
            "total_common_records": len(comparison),
            "records_changed": n_changed,
            "max_absolute_change": max_change,
            "revision_dates": comparison[comparison['diff'] != 0]['DATE'].tolist()
        }
        
        if n_changed > 0:
            logger.warning(f"Found {n_changed} revised records with max change of {max_change}")
            for date in result["revision_dates"][:5]:  # Show first 5
                logger.warning(f"Revision detected for {date}")
        else:
            logger.info("No revisions detected compared to previous snapshot")
            
        return result


def main():
    """Main execution function"""
    try:
        downloader = FREDDataDownloader()
        
        # Download current data
        current_data = downloader.download_payems()
        
        # Compare with previous snapshot
        comparison_result = downloader.compare_with_previous(current_data)
        logger.info(f"Comparison result: {comparison_result}")
        
        # Save new snapshot
        snapshot_path = downloader.save_snapshot(current_data)
        
        # Print summary
        print(f"\n=== FRED PAYEMS Download Summary ===")
        print(f"Records downloaded: {len(current_data)}")
        print(f"Date range: {current_data['DATE'].min()} to {current_data['DATE'].max()}")
        print(f"Latest value: {current_data['PAYEMS'].iloc[-1]:,.0f}")
        print(f"Snapshot saved to: {snapshot_path}")
        
        if comparison_result["status"] == "compared":
            print(f"Revisions detected: {comparison_result['records_changed']}")
            if comparison_result['records_changed'] > 0:
                print(f"Max revision: {comparison_result['max_absolute_change']:,.0f}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())