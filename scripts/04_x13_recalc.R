#!/usr/bin/env Rscript
# X-13-ARIMA-SEATS Seasonal Adjustment Script for Employment Statistics Re-analysis
# Performs seasonal adjustment using both X-11 and SEATS methods with diagnostic analysis

# Load required libraries
suppressPackageStartupMessages({
  library(seasonal)
  library(arrow)
  library(dplyr)
  library(lubridate)
  library(ggplot2)
  library(jsonlite)
})

# Configuration
INPUT_FILE <- "data_processed/nfp_revisions.feather"
OUTPUT_FILE <- "data_processed/nfp_revisions.feather"
LOG_LEVEL <- "INFO"

# Logging function
log_message <- function(level, message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(sprintf("[%s] %s - %s\n", timestamp, level, message))
}

# X-13-ARIMA-SEATS Seasonal Adjustment Class
X13SeasonalAdjuster <- function() {
  
  adjust_series <- function(ts_data, method = "x11", series_name = "NFP") {
    log_message("INFO", sprintf("Starting %s seasonal adjustment for %s", method, series_name))
    
    tryCatch({
      # Configure X-13 model based on method
      if (method == "x11") {
        model <- seas(ts_data, 
                     x11 = "",
                     automdl = TRUE,
                     outlier = TRUE,
                     transform.function = "none",
                     regression.aictest = NULL,
                     x11.mode = "mult")
      } else if (method == "seats") {
        model <- seas(ts_data,
                     seats = "",
                     automdl = TRUE,
                     outlier = TRUE,
                     transform.function = "none",
                     regression.aictest = NULL)
      } else {
        stop("Method must be 'x11' or 'seats'")
      }
      
      # Extract results
      adjusted_series <- final(model)
      seasonal_component <- seasonal(model)
      trend_component <- trend(model)
      irregular_component <- irregular(model)
      
      # Get diagnostic statistics
      diagnostics <- list()
      
      # Model fit statistics
      diagnostics$aicc <- model$model$aicc
      diagnostics$bic <- model$model$bic
      diagnostics$ljungbox <- model$udg$lbq
      diagnostics$ljungbox_pval <- model$udg$lbqpval
      
      # Seasonal diagnostics
      try({
        diagnostics$m_statistics <- model$udg[grepl("^m[0-9]", names(model$udg))]
        diagnostics$q_statistics <- model$udg[grepl("^q", names(model$udg))]
      }, silent = TRUE)
      
      # Sliding spans analysis (if available)
      try({
        ss_result <- summary(model)
        if ("slidingspans" %in% names(ss_result)) {
          diagnostics$sliding_spans_max <- max(ss_result$slidingspans, na.rm = TRUE)
          diagnostics$sliding_spans_mean <- mean(ss_result$slidingspans, na.rm = TRUE)
        }
      }, silent = TRUE)
      
      # Revision analysis (if history is available)
      try({
        if ("revisions" %in% names(summary(model))) {
          rev_stats <- summary(model)$revisions
          diagnostics$revision_variance <- var(rev_stats, na.rm = TRUE)
          diagnostics$revision_mean_abs <- mean(abs(rev_stats), na.rm = TRUE)
        }
      }, silent = TRUE)
      
      log_message("INFO", sprintf("%s adjustment completed successfully", method))
      
      return(list(
        adjusted = as.numeric(adjusted_series),
        seasonal = as.numeric(seasonal_component),
        trend = as.numeric(trend_component),
        irregular = as.numeric(irregular_component),
        diagnostics = diagnostics,
        model = model
      ))
      
    }, error = function(e) {
      log_message("ERROR", sprintf("Failed %s adjustment: %s", method, e$message))
      return(NULL)
    })
  }
  
  compare_methods <- function(ts_data, series_name = "NFP") {
    log_message("INFO", sprintf("Comparing X-11 vs SEATS for %s", series_name))
    
    # Adjust with both methods
    x11_result <- adjust_series(ts_data, "x11", series_name)
    seats_result <- adjust_series(ts_data, "seats", series_name)
    
    if (is.null(x11_result) || is.null(seats_result)) {
      log_message("WARNING", "One or both adjustment methods failed")
      return(list(x11 = x11_result, seats = seats_result))
    }
    
    # Compare adjusted series
    diff_adj <- x11_result$adjusted - seats_result$adjusted
    
    comparison <- list(
      mean_abs_diff = mean(abs(diff_adj), na.rm = TRUE),
      max_abs_diff = max(abs(diff_adj), na.rm = TRUE),
      correlation = cor(x11_result$adjusted, seats_result$adjusted, use = "complete.obs"),
      
      # Model fit comparison
      x11_aicc = x11_result$diagnostics$aicc,
      seats_aicc = seats_result$diagnostics$aicc,
      
      # Diagnostic comparison
      x11_ljungbox_pval = x11_result$diagnostics$ljungbox_pval,
      seats_ljungbox_pval = seats_result$diagnostics$ljungbox_pval
    )
    
    # Recommend method based on diagnostics
    if (!is.null(comparison$x11_aicc) && !is.null(comparison$seats_aicc)) {
      comparison$recommended_method <- ifelse(comparison$x11_aicc < comparison$seats_aicc, "x11", "seats")
    } else {
      comparison$recommended_method <- "x11"  # Default fallback
    }
    
    log_message("INFO", sprintf("Method comparison completed. Recommended: %s", comparison$recommended_method))
    
    return(list(
      x11 = x11_result,
      seats = seats_result,
      comparison = comparison
    ))
  }
  
  list(
    adjust_series = adjust_series,
    compare_methods = compare_methods
  )
}

# Main processing function
process_employment_data <- function() {
  log_message("INFO", "Starting X-13-ARIMA-SEATS seasonal adjustment")
  
  # Check if input file exists
  if (!file.exists(INPUT_FILE)) {
    log_message("ERROR", sprintf("Input file not found: %s", INPUT_FILE))
    stop("Input file not found")
  }
  
  # Load data
  log_message("INFO", sprintf("Loading data from %s", INPUT_FILE))
  df <- read_feather(INPUT_FILE)
  
  # Validate data
  if (!"date" %in% names(df)) {
    log_message("ERROR", "Date column not found in data")
    stop("Date column not found")
  }
  
  # Convert date column and sort
  df$date <- as.Date(df$date)
  df <- df[order(df$date), ]
  
  log_message("INFO", sprintf("Loaded %d records from %s to %s", 
                             nrow(df), min(df$date), max(df$date)))
  
  # Initialize adjuster
  adjuster <- X13SeasonalAdjuster()
  
  # Process different series
  series_to_process <- c("release1", "final")
  
  for (series_col in series_to_process) {
    if (!series_col %in% names(df)) {
      log_message("WARNING", sprintf("Series %s not found in data", series_col))
      next
    }
    
    # Remove missing values and create time series
    valid_data <- !is.na(df[[series_col]])
    if (sum(valid_data) < 24) {
      log_message("WARNING", sprintf("Insufficient data for %s (need at least 24 observations)", series_col))
      next
    }
    
    # Create monthly time series
    # Assuming monthly data starting from first valid date
    first_date <- min(df$date[valid_data])
    start_year <- year(first_date)
    start_month <- month(first_date)
    
    ts_data <- ts(df[[series_col]][valid_data], 
                  start = c(start_year, start_month), 
                  frequency = 12)
    
    log_message("INFO", sprintf("Processing series: %s", series_col))
    
    # Compare methods
    results <- adjuster$compare_methods(ts_data, series_col)
    
    # Add results to dataframe
    if (!is.null(results$x11)) {
      # Align results with original dataframe
      x11_adj <- rep(NA, nrow(df))
      x11_adj[valid_data] <- results$x11$adjusted
      df[[paste0(series_col, "_x11_adj")]] <- x11_adj
      
      # Add sliding spans if available
      if (!is.null(results$x11$diagnostics$sliding_spans_max)) {
        df[[paste0(series_col, "_x11_ss_max")]] <- results$x11$diagnostics$sliding_spans_max
      }
    }
    
    if (!is.null(results$seats)) {
      # Align results with original dataframe
      seats_adj <- rep(NA, nrow(df))
      seats_adj[valid_data] <- results$seats$adjusted
      df[[paste0(series_col, "_seats_adj")]] <- seats_adj
      
      # Add sliding spans if available
      if (!is.null(results$seats$diagnostics$sliding_spans_max)) {
        df[[paste0(series_col, "_seats_ss_max")]] <- results$seats$diagnostics$sliding_spans_max
      }
    }
    
    # Add comparison metrics
    if (!is.null(results$comparison)) {
      df[[paste0(series_col, "_method_diff")]] <- results$comparison$mean_abs_diff
      df[[paste0(series_col, "_recommended_method")]] <- results$comparison$recommended_method
    }
    
    # Save model diagnostics
    diagnostics_file <- sprintf("data_processed/%s_x13_diagnostics.json", series_col)
    if (!is.null(results$comparison)) {
      writeLines(toJSON(results$comparison, auto_unbox = TRUE, pretty = TRUE), 
                diagnostics_file)
      log_message("INFO", sprintf("Saved diagnostics to %s", diagnostics_file))
    }
  }
  
  # Add overall seasonal adjustment quality metrics
  df$seasonal_adjustment_quality <- "good"
  
  # Mark poor quality adjustments
  for (series_col in series_to_process) {
    diff_col <- paste0(series_col, "_method_diff")
    if (diff_col %in% names(df)) {
      # If methods disagree significantly, mark as poor quality
      poor_quality <- !is.na(df[[diff_col]]) & df[[diff_col]] > 50  # 50k difference threshold
      df$seasonal_adjustment_quality[poor_quality] <- "poor"
    }
  }
  
  # Save updated dataset
  log_message("INFO", sprintf("Saving updated dataset to %s", OUTPUT_FILE))
  write_feather(df, OUTPUT_FILE)
  
  # Also save as CSV for inspection
  csv_file <- gsub("\\.feather$", ".csv", OUTPUT_FILE)
  write.csv(df, csv_file, row.names = FALSE)
  
  # Generate summary report
  generate_summary_report(df)
  
  log_message("INFO", "X-13-ARIMA-SEATS processing completed")
}

# Generate summary report
generate_summary_report <- function(df) {
  log_message("INFO", "Generating seasonal adjustment summary report")
  
  report <- list()
  
  # Overall statistics
  report$summary <- list(
    total_records = nrow(df),
    date_range = list(
      start = as.character(min(df$date, na.rm = TRUE)),
      end = as.character(max(df$date, na.rm = TRUE))
    ),
    quality_distribution = table(df$seasonal_adjustment_quality)
  )
  
  # Seasonal adjustment statistics
  adj_cols <- names(df)[grepl("_(x11|seats)_adj$", names(df))]
  
  for (col in adj_cols) {
    if (col %in% names(df)) {
      series_name <- gsub("_(x11|seats)_adj$", "", col)
      method <- ifelse(grepl("_x11_", col), "x11", "seats")
      
      valid_data <- !is.na(df[[col]])
      if (sum(valid_data) > 0) {
        report[[paste(series_name, method, sep = "_")]] <- list(
          valid_observations = sum(valid_data),
          mean_value = mean(df[[col]], na.rm = TRUE),
          std_dev = sd(df[[col]], na.rm = TRUE),
          range = range(df[[col]], na.rm = TRUE)
        )
      }
    }
  }
  
  # Save report
  report_file <- "data_processed/x13_summary_report.json"
  writeLines(toJSON(report, auto_unbox = TRUE, pretty = TRUE), report_file)
  
  # Print summary to console
  cat("\n=== X-13-ARIMA-SEATS Summary Report ===\n")
  cat(sprintf("Total records: %d\n", report$summary$total_records))
  cat(sprintf("Date range: %s to %s\n", report$summary$date_range$start, report$summary$date_range$end))
  cat("Quality distribution:\n")
  print(report$summary$quality_distribution)
  cat(sprintf("Summary saved to: %s\n", report_file))
}

# Main execution
if (!interactive()) {
  tryCatch({
    process_employment_data()
    cat("X-13-ARIMA-SEATS processing completed successfully.\n")
  }, error = function(e) {
    log_message("ERROR", sprintf("Script failed: %s", e$message))
    quit(status = 1)
  })
}