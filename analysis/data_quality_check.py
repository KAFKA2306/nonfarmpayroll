#!/usr/bin/env python3
"""
Data Quality Check Script for Employment Statistics Re-analysis
Validates data integrity, consistency, and identifies potential issues
"""

import pandas as pd
import numpy as np
import pathlib
import logging
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import warnings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataQualityChecker:
    """Comprehensive data quality validation for employment statistics"""
    
    def __init__(self, data_file: str = "data_processed/nfp_revisions.feather"):
        self.data_file = pathlib.Path(data_file)
        self.quality_report = {}
        
    def load_data(self) -> pd.DataFrame:
        """Load the dataset for quality checking"""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_file}")
            
        try:
            if self.data_file.suffix == '.feather':
                df = pd.read_feather(self.data_file)
            elif self.data_file.suffix == '.parquet':
                df = pd.read_parquet(self.data_file)
            elif self.data_file.suffix == '.csv':
                df = pd.read_csv(self.data_file, parse_dates=['date'])
            else:
                raise ValueError(f"Unsupported file format: {self.data_file.suffix}")
                
            logger.info(f"Loaded {len(df)} records from {self.data_file}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def check_data_structure(self, df: pd.DataFrame) -> Dict:
        """Check basic data structure and schema"""
        logger.info("Checking data structure...")
        
        structure_check = {
            'total_records': len(df),
            'total_columns': len(df.columns),
            'column_names': list(df.columns),
            'data_types': df.dtypes.to_dict(),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024
        }
        
        # Expected columns
        expected_cols = ['date', 'release1', 'final', 'se', 'ci90_lower', 'ci90_upper']
        missing_cols = [col for col in expected_cols if col not in df.columns]
        unexpected_cols = [col for col in df.columns if col not in expected_cols + 
                          ['release2', 'release3', 'rev_2to1', 'rev_3to2', 'rev_final', 
                           'is_outlier', 'revision_magnitude']]
        
        structure_check.update({
            'missing_expected_columns': missing_cols,
            'unexpected_columns': unexpected_cols,
            'has_all_required_columns': len(missing_cols) == 0
        })
        
        return structure_check
    
    def check_missing_data(self, df: pd.DataFrame) -> Dict:
        """Analyze missing data patterns"""
        logger.info("Checking missing data patterns...")
        
        missing_stats = {}
        
        for col in df.columns:
            missing_count = df[col].isna().sum()
            missing_pct = (missing_count / len(df)) * 100
            
            missing_stats[col] = {
                'missing_count': int(missing_count),
                'missing_percentage': float(missing_pct),
                'first_valid_index': int(df[col].first_valid_index()) if df[col].first_valid_index() is not None else None,
                'last_valid_index': int(df[col].last_valid_index()) if df[col].last_valid_index() is not None else None
            }
        
        # Identify problematic columns (>50% missing)
        high_missing = {col: stats for col, stats in missing_stats.items() 
                       if stats['missing_percentage'] > 50}
        
        return {
            'by_column': missing_stats,
            'high_missing_columns': high_missing,
            'total_complete_records': int(df.dropna().shape[0])
        }
    
    def check_date_consistency(self, df: pd.DataFrame) -> Dict:
        """Check date column consistency and continuity"""
        logger.info("Checking date consistency...")
        
        if 'date' not in df.columns:
            return {'error': 'Date column not found'}
        
        date_check = {}
        
        # Convert to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            try:
                df['date'] = pd.to_datetime(df['date'])
            except Exception as e:
                return {'error': f'Cannot convert date column: {e}'}
        
        # Basic date statistics
        date_check.update({
            'date_range': {
                'start': str(df['date'].min()),
                'end': str(df['date'].max()),
                'span_years': float((df['date'].max() - df['date'].min()).days / 365.25)
            },
            'unique_dates': int(df['date'].nunique()),
            'duplicate_dates': int(df['date'].duplicated().sum())
        })
        
        # Check for monthly frequency (expected pattern)
        if len(df) > 1:
            df_sorted = df.sort_values('date')
            date_diffs = df_sorted['date'].diff().dt.days
            
            # Expected monthly differences (28-31 days)
            expected_monthly = (date_diffs >= 28) & (date_diffs <= 31)
            irregular_gaps = (~expected_monthly & date_diffs.notna()).sum()
            
            date_check.update({
                'irregular_time_gaps': int(irregular_gaps),
                'median_gap_days': float(date_diffs.median()),
                'max_gap_days': float(date_diffs.max()),
                'min_gap_days': float(date_diffs.min())
            })
        
        return date_check
    
    def check_value_ranges(self, df: pd.DataFrame) -> Dict:
        """Check if values are within reasonable ranges"""
        logger.info("Checking value ranges...")
        
        range_checks = {}
        
        # Employment level checks (thousands of people)
        employment_cols = [col for col in df.columns if any(x in col.lower() 
                          for x in ['release', 'final', 'nonfarm', 'payroll'])]
        
        for col in employment_cols:
            if col in df.columns and df[col].dtype in ['int64', 'float64']:
                values = df[col].dropna()
                if len(values) > 0:
                    range_checks[col] = {
                        'min': float(values.min()),
                        'max': float(values.max()),
                        'mean': float(values.mean()),
                        'std': float(values.std()),
                        'outliers_iqr': int(self._count_iqr_outliers(values)),
                        'negative_values': int((values < 0).sum()),
                        'zero_values': int((values == 0).sum()),
                        'reasonable_range': bool(values.min() >= 100000 and values.max() <= 200000)  # 100M to 200M jobs
                    }
        
        # Revision checks
        revision_cols = [col for col in df.columns if 'rev_' in col]
        for col in revision_cols:
            if col in df.columns and df[col].dtype in ['int64', 'float64']:
                values = df[col].dropna()
                if len(values) > 0:
                    range_checks[col] = {
                        'min': float(values.min()),
                        'max': float(values.max()),
                        'mean': float(values.mean()),
                        'std': float(values.std()),
                        'outliers_iqr': int(self._count_iqr_outliers(values)),
                        'extreme_revisions': int((np.abs(values) > 1000).sum())  # >1M revision
                    }
        
        return range_checks
    
    def check_revision_consistency(self, df: pd.DataFrame) -> Dict:
        """Check revision calculation consistency"""
        logger.info("Checking revision consistency...")
        
        consistency_check = {}
        
        # Check if revision calculations are correct
        if all(col in df.columns for col in ['release1', 'release2', 'rev_2to1']):
            calculated_rev = df['release2'] - df['release1']
            stored_rev = df['rev_2to1']
            
            # Allow for small floating point differences
            inconsistent = np.abs(calculated_rev - stored_rev) > 0.01
            inconsistent_count = inconsistent.sum()
            
            consistency_check['rev_2to1'] = {
                'inconsistent_count': int(inconsistent_count),
                'max_difference': float(np.abs(calculated_rev - stored_rev).max()) if len(df) > 0 else 0
            }
        
        # Similar check for other revisions
        if all(col in df.columns for col in ['final', 'release1', 'rev_final']):
            calculated_rev = df['final'] - df['release1']
            stored_rev = df['rev_final']
            
            inconsistent = np.abs(calculated_rev - stored_rev) > 0.01
            inconsistent_count = inconsistent.sum()
            
            consistency_check['rev_final'] = {
                'inconsistent_count': int(inconsistent_count),
                'max_difference': float(np.abs(calculated_rev - stored_rev).max()) if len(df) > 0 else 0
            }
        
        return consistency_check
    
    def check_seasonal_patterns(self, df: pd.DataFrame) -> Dict:
        """Check for expected seasonal patterns"""
        logger.info("Checking seasonal patterns...")
        
        if 'date' not in df.columns:
            return {'error': 'Date column required for seasonal analysis'}
        
        seasonal_check = {}
        
        # Add month column if not exists
        df_temp = df.copy()
        df_temp['month'] = pd.to_datetime(df_temp['date']).dt.month
        
        # Check employment series for seasonal patterns
        employment_cols = [col for col in df.columns if any(x in col.lower() 
                          for x in ['release1', 'final']) and df[col].dtype in ['int64', 'float64']]
        
        for col in employment_cols:
            if col in df.columns:
                monthly_stats = df_temp.groupby('month')[col].agg(['mean', 'std', 'count']).reset_index()
                
                seasonal_check[col] = {
                    'monthly_means': monthly_stats['mean'].to_dict(),
                    'monthly_stds': monthly_stats['std'].to_dict(),
                    'seasonal_variation_coeff': float(monthly_stats['mean'].std() / monthly_stats['mean'].mean())
                }
        
        return seasonal_check
    
    def _count_iqr_outliers(self, series: pd.Series) -> int:
        """Count outliers using IQR method"""
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        return ((series < lower_bound) | (series > upper_bound)).sum()
    
    def run_all_checks(self) -> Dict:
        """Run all quality checks and compile report"""
        logger.info("Starting comprehensive data quality check...")
        
        try:
            df = self.load_data()
            
            # Run all checks
            self.quality_report = {
                'metadata': {
                    'check_timestamp': datetime.now().isoformat(),
                    'data_file': str(self.data_file),
                    'checker_version': '1.0'
                },
                'structure': self.check_data_structure(df),
                'missing_data': self.check_missing_data(df),
                'date_consistency': self.check_date_consistency(df),
                'value_ranges': self.check_value_ranges(df),
                'revision_consistency': self.check_revision_consistency(df),
                'seasonal_patterns': self.check_seasonal_patterns(df)
            }
            
            # Add overall quality score
            self.quality_report['overall_score'] = self._calculate_quality_score()
            
            logger.info("Data quality check completed")
            return self.quality_report
            
        except Exception as e:
            logger.error(f"Quality check failed: {e}")
            raise
    
    def _calculate_quality_score(self) -> Dict:
        """Calculate overall quality score (0-100)"""
        score = 100
        issues = []
        
        # Deduct points for structural issues
        if not self.quality_report['structure']['has_all_required_columns']:
            score -= 20
            issues.append("Missing required columns")
        
        # Deduct points for high missing data
        high_missing = len(self.quality_report['missing_data']['high_missing_columns'])
        if high_missing > 0:
            score -= min(high_missing * 10, 30)
            issues.append(f"{high_missing} columns with high missing data")
        
        # Deduct points for date issues
        if self.quality_report['date_consistency'].get('duplicate_dates', 0) > 0:
            score -= 10
            issues.append("Duplicate dates found")
        
        # Deduct points for revision inconsistencies
        for rev_type, rev_data in self.quality_report['revision_consistency'].items():
            if rev_data.get('inconsistent_count', 0) > 0:
                score -= 5
                issues.append(f"Revision calculation inconsistencies in {rev_type}")
        
        return {
            'score': max(score, 0),
            'grade': 'A' if score >= 90 else 'B' if score >= 80 else 'C' if score >= 70 else 'D' if score >= 60 else 'F',
            'issues': issues
        }
    
    def save_report(self, output_path: str = "data_processed/quality_report.json"):
        """Save quality report to file"""
        output_file = pathlib.Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(self.quality_report, f, indent=2, default=str)
        
        logger.info(f"Quality report saved to {output_file}")
        return output_file
    
    def print_summary(self):
        """Print summary of quality check results"""
        if not self.quality_report:
            print("No quality report available. Run checks first.")
            return
        
        print("\n=== Data Quality Check Summary ===")
        print(f"Overall Score: {self.quality_report['overall_score']['score']}/100 (Grade: {self.quality_report['overall_score']['grade']})")
        
        structure = self.quality_report['structure']
        print(f"Records: {structure['total_records']:,}")
        print(f"Columns: {structure['total_columns']}")
        print(f"Memory Usage: {structure['memory_usage_mb']:.1f} MB")
        
        missing = self.quality_report['missing_data']
        print(f"Complete Records: {missing['total_complete_records']:,}")
        print(f"High Missing Columns: {len(missing['high_missing_columns'])}")
        
        dates = self.quality_report['date_consistency']
        if 'date_range' in dates:
            print(f"Date Range: {dates['date_range']['start']} to {dates['date_range']['end']}")
            print(f"Duplicate Dates: {dates.get('duplicate_dates', 0)}")
        
        if self.quality_report['overall_score']['issues']:
            print("\nIssues Found:")
            for issue in self.quality_report['overall_score']['issues']:
                print(f"  - {issue}")
        else:
            print("\nNo significant issues found.")


def main():
    """Main execution function"""
    try:
        checker = DataQualityChecker()
        
        # Run all quality checks
        report = checker.run_all_checks()
        
        # Save report
        report_file = checker.save_report()
        
        # Print summary
        checker.print_summary()
        
        print(f"\nDetailed report saved to: {report_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())