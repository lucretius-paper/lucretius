import argparse
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.ticker as mtick
from matplotlib.ticker import PercentFormatter
import pandas as pd

parser = argparse.ArgumentParser(description="Speedup Plot Generator", formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("original_sizes", help="Path to original sizes.csv")
parser.add_argument("comparison_sizes", help="Path to comparison sizes.csv")
parser.add_argument("-o","--out_path", type=str,help="Path to where the plot should be stored", default="./")
parser.set_defaults(verbose=False)

args = parser.parse_args() 
original_size_data = args.original_sizes
comparison_size_data = args.comparison_sizes


df_orig = pd.read_json(original_size_data, orient="index").rename(columns={0:"size"}).sort_index()
df_new = pd.read_json(comparison_size_data, orient="index").rename(columns={0:"size"}).sort_index()
df_speedup = df_orig / df_new

mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.rcParams['axes.labelsize'] = "x-large"
mpl.rcParams['axes.titlesize'] = 'x-large'
mpl.rcParams['xtick.labelsize'] = 'x-large'
mpl.rcParams['ytick.labelsize'] = 'x-large'
fig = plt.gcf()
fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(df_speedup.index, df_speedup["size"], capsize=2, color="tab:green", edgecolor="black")
ax.hlines(1, 0, len(df_speedup),color="tab:red", linestyles="--",linewidth=3)
ax.set_xlabel("Benchmarks")
ax.set_ylabel("Speedup")
plt.xticks(rotation=55, ha='right')
fig.tight_layout()
plt.savefig(f"{args.out_path}/SPEEDUP.pdf", format="pdf", bbox_inches="tight")
plt.close()
