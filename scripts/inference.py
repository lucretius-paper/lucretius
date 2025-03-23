import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
import argparse

parser = argparse.ArgumentParser(description="Inference Stage Parser", formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("model", help="Path to model created by model_builder.py")
parser.add_argument("test_data", help="Path to aligned testing data for prediction")
parser.add_argument("-o","--out_path", type=str,help="Path where the plot for the inference is stored", default="./")
parser.add_argument("-t","--xgb_tree", type=str,help="The xgboost tree method to use.", default="hist")
parser.set_defaults(verbose=False)
args = parser.parse_args() 
model_path = args.model
test_data = args.test_data

model = XGBRegressor(tree_method=args.xgb_tree)
model.load_model(model_path)

df_test = pd.read_csv(test_data)

benchmarks = df_test.benchmark.unique()
ratios = {}
for bench in benchmarks:
    ratios[bench] = []


df_test = pd.read_csv(test_data)
for bench in benchmarks:
    events_test = df_test[df_test.benchmark == bench]
    if len(events_test) == 0:
        continue
    events_test = events_test.drop(["iteration","ts","benchmark","power"], axis=1)
    events_test = events_test.drop([col for col in events_test.columns if 'energy_component' in col], axis=1)
    prediction_energy = model.predict(events_test)
    real_energy = df_test[df_test.benchmark == bench]["power"]
    total_prediction_energy = prediction_energy.sum()
    total_actual_energy = real_energy.sum()

    ratio =  np.abs((total_actual_energy - total_prediction_energy) / total_actual_energy)
    ratios[bench].append(ratio)


ratio_mean = pd.DataFrame(ratios).mean()
ratio_mean_df = pd.DataFrame(ratio_mean).rename(columns={0:"mean"})
ratio_mean_df["std"] = pd.DataFrame(ratios).std()
ratio_mean_df = ratio_mean_df.sort_index()
ratio_mean_df = ratio_mean_df.reset_index(names=["benchmark"])


import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.rcParams['axes.labelsize'] = "x-large"
mpl.rcParams['axes.titlesize'] = 'x-large'
mpl.rcParams['xtick.labelsize'] = 'x-large'
mpl.rcParams['ytick.labelsize'] = 'x-large'
from matplotlib.ticker import PercentFormatter
import matplotlib.ticker as mtick
fig = plt.gcf()
fig, ax = plt.subplots(figsize=(10, 3))
ax.bar(ratio_mean_df.index, ratio_mean_df["mean"]*100, yerr=ratio_mean_df["std"]*100, capsize=2, color="tab:purple", edgecolor="black")
print(f"\nAvg Error = {(ratio_mean_df['mean'].mean() * 100):.2f}%\nMedian Error = {(ratio_mean_df['mean'].median() * 100):.2f}%")
plt.ylim(0,100 * (ratio_mean_df['mean'].max() + 2 * ratio_mean_df['mean'].std()))
plt.xlabel("Benchmark")
plt.ylabel("Percent Error")
fmt = '%.0f%%' # Format you want the ticks, e.g. '40%'
yticks = mtick.FormatStrFormatter(fmt)
ax.yaxis.set_major_formatter(yticks)
ax.set_xlim(0.5, len(ratio_mean_df))
ax.set_xlim(-1, len(ratio_mean_df))
ax.set_xticklabels(ratio_mean_df.benchmark)
plt.xticks(list(range(len(ratio_mean_df))), rotation=55, ha='right')
plt.savefig(args.out_path, format="pdf", bbox_inches="tight")
plt.close()
