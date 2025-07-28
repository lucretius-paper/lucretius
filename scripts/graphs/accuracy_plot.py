import argparse
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.ticker as mtick
from matplotlib.ticker import PercentFormatter
import pandas as pd

parser = argparse.ArgumentParser(description="Accuracy Plot Generator", formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("ratio_data", help="Path to ratios.csv")
parser.add_argument("-o","--out_path", type=str,help="Path to where the plot should be stored", default="./")
parser.set_defaults(verbose=False)

args = parser.parse_args() 
ratio_data = args.ratio_data

ratio_mean_df = pd.read_csv(ratio_data).fillna(0)
ratio_mean_df = ratio_mean_df.sort_values("benchmark")

std_val = ratio_mean_df['mean'].std()
std_val = 0 if pd.isna(std_val) else std_val

mpl.rcParams['axes.labelsize'] = "x-large"
mpl.rcParams['axes.titlesize'] = 'x-large'
mpl.rcParams['xtick.labelsize'] = 'x-large'
mpl.rcParams['ytick.labelsize'] = 'x-large'
fig = plt.gcf()
fig, ax = plt.subplots(figsize=(10, 3))
ax.bar(ratio_mean_df.index, ratio_mean_df["mean"]*100, yerr=ratio_mean_df["std"]*100, capsize=2, color="tab:purple", edgecolor="black")
print(f"\nAvg Error = {(ratio_mean_df['mean'].mean() * 100):.2f}%\nMedian Error = {(ratio_mean_df['mean'].median() * 100):.2f}%")
plt.ylim(0,100 * (ratio_mean_df['mean'].max() + 2 * std_val))
plt.xlabel("Benchmark")
plt.ylabel("Percent Error")
fmt = '%.0f%%' # Format you want the ticks, e.g. '40%'
yticks = mtick.FormatStrFormatter(fmt)
ax.yaxis.set_major_formatter(yticks)
ax.set_xlim(0.5, len(ratio_mean_df))
ax.set_xlim(-1, len(ratio_mean_df))
ax.set_xticklabels(ratio_mean_df.benchmark)
plt.xticks(list(range(len(ratio_mean_df))), rotation=55, ha='right')
plt.savefig(f"{args.out_path}/MAPE.pdf", format="pdf", bbox_inches="tight")
plt.close()
