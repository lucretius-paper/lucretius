import pandas as pd
import numpy as np
from xgboost import XGBRegressor
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import argparse
import os
import matplotlib as mpl
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.rcParams['axes.labelsize'] = "x-large"
mpl.rcParams['axes.titlesize'] = 'x-large'
mpl.rcParams['xtick.labelsize'] = 'x-large'
mpl.rcParams['ytick.labelsize'] = 'x-large'


def parse_args():
    parser = argparse.ArgumentParser(description='XGBoost vs Ground graph creator')
    parser.add_argument('model', type=str, help='path to XGBoost json model')
    parser.add_argument('testing', type=str, help='path to testing data')
    parser.add_argument(
        '--output_directory',
        default=None,
        help='location to write the line graphs'
    )

    args = parser.parse_args()
    if args.output_directory is None:
        args.output_directory = "."

    return args

args = parse_args()




#Faithful McCullough Method
df = pd.read_csv(args.testing).fillna(-1)
df = df[df.power <= 10**5]
df = df.drop([col for col in df.columns if '__entry' in col], axis=1)
df = df.drop([col for col in df.columns if '__return' in col], axis=1)
df = df.drop([col for col in df.columns if '__begin' in col], axis=1)
df = df.drop([col for col in df.columns if '__end' in col], axis=1)
train_bench = "combined-benchmarks"
benchmarks = df.benchmark.unique()
dt_model = XGBRegressor(tree_method='gpu_hist', gpu_id=0)
dt_model.load_model(args.model)    

for bench in benchmarks:
    df_bench = df[df.benchmark == bench]
    events_bench_test = df_bench.drop(["iteration","ts","benchmark","power"], axis=1)
    events_bench_test = events_bench_test.drop([col for col in events_bench_test.columns if 'energy_component' in col], axis=1)
    predictions = dt_model.predict(events_bench_test).tolist()
    real = df_bench.power.tolist()
    fig = plt.gcf()
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(range(0, len(real)), real, label="ground truth", color="black")
    ax.plot(range(0, len(predictions)), predictions, label="XGBoost", linestyle="--", color="tab:blue")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (W)")
    plt.savefig(f"{args.output_directory}/{bench}.pdf", format="pdf", bbox_inches="tight")
    plt.clf()
    plt.close()
