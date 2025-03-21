
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
import argparse

parser = argparse.ArgumentParser(description="Model Builder Parser", formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("aligned_filename",help="Path to file created by alignment.py")
parser.add_argument("-n", "--name", type=str, help="Name of model being built; i.e., -n \"model\" creates model.json, model_test.csv, and model_train.csv", default="model")
parser.add_argument("-o","--out_path", type=str,help="Path where model is stored; i.e, -o \".\" stores model.json in the current directory", default=".")
parser.add_argument("-t","--xgb_tree", type=str,help="The xgboost tree method to use.", default="hist")
parser.set_defaults(verbose=False)
args = parser.parse_args() 
aligned_path = args.aligned_filename
model_name = args.name
out_path = args.out_path

df = pd.read_csv(aligned_path).fillna(-1)
df = df[df.power <= 10**5]
df = df.drop([col for col in df.columns if '__entry' in col], axis=1)
df = df.drop([col for col in df.columns if '__return' in col], axis=1)
df = df.drop([col for col in df.columns if '__begin' in col], axis=1)
df = df.drop([col for col in df.columns if '__end' in col], axis=1)
benchmarks = df.benchmark.unique()
ratios = {}

for bench in benchmarks:
    ratios[bench] = []
    
model = XGBRegressor(tree_method=args.xgb_tree)
df_train, df_test = train_test_split(df, test_size=.5)
events_df_train = df_train
power_df_train = df_train["power"]
events_df_train = events_df_train.drop(["iteration","ts","benchmark","power"], axis=1)
events_df_train = events_df_train.drop([col for col in events_df_train.columns if 'energy_component' in col], axis=1)
model.fit(events_df_train, power_df_train)
model.save_model(f"{out_path}/{model_name}.json")
df_train.to_csv(f"{out_path}/{model_name}_train.csv", index=False)
df_test.to_csv(f"{out_path}/{model_name}_test.csv", index=False)


