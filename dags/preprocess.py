import pandas as pd
import numpy as np
import os
import logging
from s3_utils import read_csv_from_s3, write_csv_to_s3

def load_data(csv_path):
    """
    Load the Bangalore house prices dataset
    """
    logging.info(f"Loading data from {csv_path}")
    return read_csv_from_s3(csv_path)

def convert_sqft_to_num(x):
    """
    Convert total_sqft to numeric value
    """
    tokens = str(x).split('-')
    if len(tokens) == 2:
        return (float(tokens[0]) + float(tokens[1])) / 2
    try:
        return float(x)
    except:
        return None

def clean_data(df):
    """
    Clean the dataset by handling missing values and outliers
    """
    logging.info("Cleaning data...")
    # Drop rows with NA values
    df.dropna(inplace=True)
    
    # Add BHK column
    df['bhk'] = df['size'].apply(lambda x: int(x.split(' ')[0]))
    
    # Convert total_sqft to numeric
    df['total_sqft'] = df['total_sqft'].apply(convert_sqft_to_num)
    
    # Drop rows where total_sqft is None
    df = df[df.total_sqft.notnull()]
    
    # Add new feature: price per square feet
    df['price_per_sqft'] = df['price'] * 100000 / df['total_sqft']
    
    # Keep only 2+ bedroom houses
    df = df[df.bhk >= 2]
    
    # Remove outliers based on price_per_sqft
    df = remove_price_outliers(df)
    
    # Remove bhk outliers
    df = remove_bhk_outliers(df)
    
    # Keep only relevant columns
    df = df[['location', 'total_sqft', 'bath', 'price', 'bhk']]
    
    # Handle locations with fewer data points
    df.location = df.location.apply(lambda x: x.strip())
    location_stats = df.groupby('location')['location'].count()
    locations_less_than_10 = location_stats[location_stats <= 10]
    df.location = df.location.apply(lambda x: 'other' if x in locations_less_than_10 else x)
    
    return df

def remove_price_outliers(df):
    """
    Remove price outliers based on standard deviation (using 1 std dev like notebook)
    """
    logging.info("Removing price outliers...")
    df_out = pd.DataFrame()
    for key, subdf in df.groupby('location'):
        m = np.mean(subdf.price_per_sqft)
        sd = np.std(subdf.price_per_sqft)
        # Use 1 standard deviation like in notebook for more aggressive outlier removal
        reduced_df = subdf[(subdf.price_per_sqft > (m - sd)) & (subdf.price_per_sqft <= (m + sd))]
        df_out = pd.concat([df_out, reduced_df], ignore_index=True)
    return df_out

def remove_bhk_outliers(df):
    """
    Remove BHK outliers where 2 BHK costs more than 3 BHK in same location
    """
    logging.info("Removing BHK outliers...")
    exclude_indices = []
    for location, location_df in df.groupby('location'):
        bhk_stats = {}
        for bhk, bhk_df in location_df.groupby('bhk'):
            bhk_stats[bhk] = {
                'mean': np.mean(bhk_df.price_per_sqft),
                'std': np.std(bhk_df.price_per_sqft),
                'count': bhk_df.shape[0]
            }
        
        for bhk, bhk_df in location_df.groupby('bhk'):
            stats = bhk_stats.get(bhk-1)
            if stats and stats['count'] > 5:
                exclude_indices = exclude_indices + list(bhk_df[bhk_df.price_per_sqft < stats['mean']].index)
    
    return df.drop(exclude_indices)

def preprocess_data(input_path, output_path):
    """
    Main function to preprocess the data
    """
    logging.info("Starting data preprocessing...")
    
    # Load data
    df = load_data(input_path)
    
    # Clean data
    df_cleaned = clean_data(df)
    
    # Save processed data
    write_csv_to_s3(df_cleaned, output_path)
    logging.info(f"Preprocessed data saved to {output_path}")
    logging.info(f"Final dataset shape: {df_cleaned.shape}")
    
    return None

if __name__ == "__main__":
    # For testing
    input_file = "../../data/raw/train.csv"
    output_file = "../../data/processed/preprocessed_data.csv"
    preprocess_data(input_file, output_file)
