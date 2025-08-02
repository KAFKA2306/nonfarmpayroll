#!/usr/bin/env python3
"""
Merge Revisions Script for Employment Statistics Re-analysis
Combines FRED final data with BLS release data to calculate revision errors
"""

import pandas as pd
import numpy as np
import glob
import pathlib
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RevisionMerger:
    """Merges FRED final data with BLS release data to calculate revisions"""
    
    def __init__(self, 
                 fred_dir: str = "data_raw/fred_snapshots",
                 bls_dir: str = "data_processed",
                 output_dir: str = "data_processed"):
        self.fred_dir = pathlib.Path(fred_dir)
        self.bls_dir = pathlib.Path(bls_dir)
        self.output_dir = pathlib.Path(output_dir)
        
        # BLS published standard error (±85,000 for 90% CI of ±136,000)
        self.standard_error = 85000
        self.confidence_interval_90 = 136000
        
    def load_latest_fred_data(self) -> pd.DataFrame:
        """
        Load the most recent FRED snapshot
        
        Returns:
            DataFrame with DATE and PAYEMS columns
        """
        fred_files = list(self.fred_dir.glob("PAYEMS_*.csv"))
        
        if not fred_files:
            raise FileNotFoundError(f"No FRED snapshots found in {self.fred_dir}")
            
        # Get the most recent file
        latest_file = sorted(fred_files)[-1]
        logger.info(f"Loading FRED data from {latest_file}")
        
        df = pd.read_csv(latest_file, parse_dates=['DATE'])
        df.rename(columns={'PAYEMS': 'final'}, inplace=True)
        
        # Convert to thousands (FRED is in thousands, BLS releases often in levels)
        # FRED PAYEMS is already in thousands of persons
        
        logger.info(f"Loaded {len(df)} FRED records from {df['DATE'].min()} to {df['DATE'].max()}")
        
        return df
    
    def load_bls_releases(self) -> pd.DataFrame:
        """
        Load BLS release data
        
        Returns:
            DataFrame with release data
        """
        # Try parquet first, then CSV
        parquet_path = self.bls_dir / "bls_releases.parquet"
        csv_path = self.bls_dir / "bls_releases.csv"
        
        if parquet_path.exists():
            logger.info(f"Loading BLS releases from {parquet_path}")
            df = pd.read_parquet(parquet_path)
        elif csv_path.exists():
            logger.info(f"Loading BLS releases from {csv_path}")
            df = pd.read_csv(csv_path, parse_dates=['date'])
        else:
            raise FileNotFoundError(f"No BLS release data found in {self.bls_dir}")
            
        # Ensure date column is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        elif 'DATE' in df.columns:
            df.rename(columns={'DATE': 'date'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            
        # Convert values to thousands if they appear to be in levels
        for col in ['release1', 'release2', 'release3']:
            if col in df.columns:
                # If values are > 10000, assume they're in levels, convert to thousands
                if df[col].max() > 10000:
                    df[col] = df[col] / 1000
                    
        logger.info(f"Loaded {len(df)} BLS release records")
        
        return df
    
    def merge_datasets(self, fred_df: pd.DataFrame, bls_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge FRED and BLS datasets
        
        Args:
            fred_df: FRED final data
            bls_df: BLS release data
            
        Returns:
            Merged DataFrame
        """
        # Merge on date
        merged = pd.merge(
            fred_df, 
            bls_df, 
            left_on='DATE', 
            right_on='date', 
            how='outer',
            suffixes=('_fred', '_bls')
        )
        
        # Use the common date column
        merged['date'] = merged['DATE'].fillna(merged['date'])
        merged.drop(['DATE', 'date_bls'], axis=1, errors='ignore', inplace=True)
        
        # Sort by date
        merged = merged.sort_values('date').reset_index(drop=True)
        
        logger.info(f"Merged dataset has {len(merged)} records")
        
        return merged
    
    def calculate_revisions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate revision errors between releases
        
        Args:
            df: Merged dataset
            
        Returns:
            DataFrame with revision calculations
        """
        df = df.copy()
        
        # Ensure we have the required columns
        release_cols = ['release1', 'release2', 'release3']
        available_releases = [col for col in release_cols if col in df.columns]
        
        if not available_releases:
            logger.warning("No release columns found, creating placeholder data")
            # If no BLS data available, use final values as proxy
            df['release1'] = df['final']
            available_releases = ['release1']
        
        # Calculate revisions between consecutive releases
        if 'release2' in df.columns and 'release1' in df.columns:
            df['rev_2to1'] = df['release2'] - df['release1']  # 2nd release vs 1st release
        else:
            df['rev_2to1'] = np.nan
            
        if 'release3' in df.columns and 'release2' in df.columns:
            df['rev_3to2'] = df['release3'] - df['release2']  # 3rd release vs 2nd release
        elif 'release3' in df.columns and 'release1' in df.columns:
            df['rev_3to1'] = df['release3'] - df['release1']  # 3rd release vs 1st release
        else:
            df['rev_3to2'] = np.nan
            
        # Final benchmark revision (most important)
        if 'final' in df.columns and 'release1' in df.columns:
            df['rev_final'] = df['final'] - df['release1']  # Final vs 1st release
        else:
            df['rev_final'] = np.nan
            
        if 'final' in df.columns and 'release3' in df.columns:
            df['rev_final_to3'] = df['final'] - df['release3']  # Final vs 3rd release
        else:
            df['rev_final_to3'] = np.nan
        
        # Add standard errors and confidence intervals
        df['se'] = self.standard_error
        df['ci90_lower'] = df['release1'] - self.confidence_interval_90
        df['ci90_upper'] = df['release1'] + self.confidence_interval_90
        
        # Flag outlier periods (COVID, financial crisis, etc.)
        df['is_outlier'] = False
        
        # COVID period (March 2020 - June 2020)
        covid_mask = (df['date'] >= '2020-03-01') & (df['date'] <= '2020-06-01')
        df.loc[covid_mask, 'is_outlier'] = True
        
        # Financial crisis (September 2008 - March 2009)
        crisis_mask = (df['date'] >= '2008-09-01') & (df['date'] <= '2009-03-01')
        df.loc[crisis_mask, 'is_outlier'] = True
        
        # Flag extreme revisions (>3 standard deviations)
        if 'rev_final' in df.columns:
            extreme_revision_threshold = 3 * self.standard_error
            extreme_mask = np.abs(df['rev_final']) > extreme_revision_threshold
            df.loc[extreme_mask, 'is_outlier'] = True
        
        logger.info(f"Marked {df['is_outlier'].sum()} records as outliers")
        
        return df
    
    def add_summary_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add summary statistics and quality metrics
        
        Args:
            df: DataFrame with revisions
            
        Returns:
            DataFrame with additional statistics
        """
        df = df.copy()
        
        # Rolling statistics for revision patterns
        for col in ['rev_2to1', 'rev_3to2', 'rev_final']:
            if col in df.columns:
                # 12-month rolling standard deviation
                df[f'{col}_rolling_std'] = df[col].rolling(window=12, min_periods=6).std()
                
                # 12-month rolling mean
                df[f'{col}_rolling_mean'] = df[col].rolling(window=12, min_periods=6).mean()
        
        # Revision direction consistency
        if 'rev_2to1' in df.columns and 'rev_final' in df.columns:
            df['revision_direction_consistent'] = (
                np.sign(df['rev_2to1']) == np.sign(df['rev_final'])
            )
        
        # Absolute revision size categories
        if 'rev_final' in df.columns:
            df['revision_magnitude'] = pd.cut(
                np.abs(df['rev_final']),
                bins=[0, 50, 100, 200, np.inf],
                labels=['Small', 'Medium', 'Large', 'Extreme'],
                include_lowest=True
            )
        
        return df
    
    def save_final_dataset(self, df: pd.DataFrame) -> pathlib.Path:
        """
        Save the final merged dataset
        
        Args:
            df: Final DataFrame to save
            
        Returns:
            Path to saved file
        """
        # Save as Feather (fast, preserves dtypes)
        feather_path = self.output_dir / "nfp_revisions.feather"
        df.to_feather(feather_path)
        
        # Save as CSV for human inspection
        csv_path = self.output_dir / "nfp_revisions.csv"
        df.to_csv(csv_path, index=False)
        
        # Save as Parquet (compressed, good for ML)
        parquet_path = self.output_dir / "nfp_revisions.parquet"
        df.to_parquet(parquet_path, index=False)
        
        logger.info(f"Saved final dataset to {feather_path}, {csv_path}, and {parquet_path}")
        
        return feather_path
    
    def generate_summary_report(self, df: pd.DataFrame) -> Dict:
        """
        Generate summary statistics for the dataset
        
        Args:
            df: Final dataset
            
        Returns:
            Dictionary with summary statistics
        """
        report = {
            'dataset_info': {
                'total_records': len(df),
                'date_range': {
                    'start': str(df['date'].min()),
                    'end': str(df['date'].max())
                },
                'missing_data': {
                    'release1': df['release1'].isna().sum(),
                    'release2': df['release2'].isna().sum() if 'release2' in df.columns else 'N/A',
                    'release3': df['release3'].isna().sum() if 'release3' in df.columns else 'N/A',
                    'final': df['final'].isna().sum()
                }
            }
        }
        
        # Revision statistics
        if 'rev_final' in df.columns:
            rev_final_clean = df['rev_final'].dropna()
            if len(rev_final_clean) > 0:
                report['revision_statistics'] = {
                    'mean_revision': float(rev_final_clean.mean()),
                    'median_revision': float(rev_final_clean.median()),
                    'std_revision': float(rev_final_clean.std()),
                    'max_positive_revision': float(rev_final_clean.max()),
                    'max_negative_revision': float(rev_final_clean.min()),
                    'revision_frequency': {
                        'positive': int((rev_final_clean > 0).sum()),
                        'negative': int((rev_final_clean < 0).sum()),
                        'zero': int((rev_final_clean == 0).sum())
                    }
                }
        
        # Outlier information
        report['outliers'] = {
            'total_outliers': int(df['is_outlier'].sum()),
            'outlier_percentage': float(df['is_outlier'].mean() * 100)
        }
        
        return report


def main():
    """Main execution function"""
    try:
        merger = RevisionMerger()
        
        # Load datasets
        logger.info("Loading FRED data...")
        fred_df = merger.load_latest_fred_data()
        
        logger.info("Loading BLS release data...")
        try:
            bls_df = merger.load_bls_releases()
        except FileNotFoundError:
            logger.warning("No BLS release data found. Creating minimal dataset with FRED data only.")
            bls_df = pd.DataFrame()
        
        # Merge datasets
        if not bls_df.empty:
            merged_df = merger.merge_datasets(fred_df, bls_df)
        else:
            merged_df = fred_df.copy()
            merged_df.rename(columns={'DATE': 'date'}, inplace=True)
        
        # Calculate revisions
        logger.info("Calculating revisions...")
        final_df = merger.calculate_revisions(merged_df)
        
        # Add summary statistics
        logger.info("Adding summary statistics...")
        final_df = merger.add_summary_statistics(final_df)
        
        # Save final dataset
        output_path = merger.save_final_dataset(final_df)
        
        # Generate summary report
        summary = merger.generate_summary_report(final_df)
        
        # Print summary
        print(f"\n=== Employment Statistics Revision Analysis Summary ===")
        print(f"Total records: {summary['dataset_info']['total_records']}")
        print(f"Date range: {summary['dataset_info']['date_range']['start']} to {summary['dataset_info']['date_range']['end']}")
        print(f"Outliers: {summary['outliers']['total_outliers']} ({summary['outliers']['outlier_percentage']:.1f}%)")
        
        if 'revision_statistics' in summary:
            rev_stats = summary['revision_statistics']
            print(f"\nRevision Statistics:")
            print(f"  Mean revision: {rev_stats['mean_revision']:+.1f}k")
            print(f"  Median revision: {rev_stats['median_revision']:+.1f}k")
            print(f"  Std deviation: {rev_stats['std_revision']:.1f}k")
            print(f"  Max positive: {rev_stats['max_positive_revision']:+.1f}k")
            print(f"  Max negative: {rev_stats['max_negative_revision']:+.1f}k")
        
        print(f"\nOutput saved to: {output_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())