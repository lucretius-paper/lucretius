import dtreeviz
import pandas as pd
from xgboost import XGBRegressor
import numpy as np
import shap
import matplotlib as mpl
from matplotlib.ticker import PercentFormatter
import matplotlib.ticker as mtick
import matplotlib.pyplot as plt
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='SHAP graph creator')
    parser.add_argument('model', type=str, help='path to XGBoost json model')
    parser.add_argument('training', type=str, help='path to training data')
    parser.add_argument(
        '--output_directory',
        default=None,
        help='location to write the SHAP graphs'
    )

    args = parser.parse_args()
    if args.output_directory is None:
        args.output_directory = "."

    return args

args = parse_args()



df_train = pd.read_csv(args.training)
events_df_train = df_train
events_df_train = events_df_train.drop(["iteration","ts","benchmark","power"], axis=1)
events_df_train = events_df_train.drop([col for col in events_df_train.columns if 'energy_component' in col], axis=1)
power_df_train = df_train["power"]

model = XGBRegressor(tree_method='gpu_hist', gpu_id=0)
model.load_model(args.model)
explainer = shap.explainers.TreeExplainer(model, events_df_train)
shap_values = explainer(events_df_train)
shap_values = shap_values

#Making SHAP scatter plots
mpl.rcParams['axes.labelsize'] = "x-large"
mpl.rcParams['axes.titlesize'] = 'x-large'
mpl.rcParams['xtick.labelsize'] = 'x-large'
mpl.rcParams['ytick.labelsize'] = 'x-large'
features = events_df_train.columns
for f in features:
    fig, ax = plt.subplots(figsize=(10, 3))
    shaps = shap_values[:, [f]].values
    feature = shap_values[:, [f]].data
    s_arr = []
    f_arr = []
    p_arr = []
    for i in range(len(shaps)):
        if feature[i][0] == -1 or feature[i][0] == 0: 
                continue
        s_arr.append(shaps[i][0])
        f_arr.append(feature[i][0])
        if power_df_train[i] > 150:
            p_arr.append(150)
        else:
            p_arr.append(power_df_train[i])
    plot = ax.scatter(f_arr, s_arr, c=p_arr, cmap="bwr", alpha=.33)
    plt.title(f"{f} SHAP Values")
    plt.xlabel("Depth")
    plt.ylabel("SHAP value")
    fig.colorbar(plot, label="power")
    plt.axhline(y = 0.0, color = 'r', linestyle = '--') 
    ax.set_xlim(1)
    plt.xticks(rotation=15, ha='center')
    plt.savefig(f"{args.output_directory}/SHAP_{f}_scatter.pdf", format="pdf", bbox_inches="tight")
    plt.clf()

#Making Violin Plot
violin_plot_format = []
for f in features:
    shaps = shap_values[:, [f]].values.tolist()
    shaps_f = shap_values[:, [f]].data.tolist()
    arr = []
    for i in range(len(shaps)):
        if shaps_f[i][0] == -1 or shaps_f[i][0] == 0: 
                continue
        arr.append(shaps[i][0])
    violin_plot_format.append(arr)
fig, ax = plt.subplots(figsize=(10, 5))
ax.violinplot(violin_plot_format, vert=False,showmeans=True)
ax.set_yticks([y + 1 for y in range(len(violin_plot_format))],
                  labels=features)
plt.axvline(x = 0.0, color = 'r', linestyle = '--')
plt.xlabel("SHAP value")
plt.ylabel("Runtime Events")
plt.savefig(f"{args.output_directory}/SHAP_feature_importance.pdf", format="pdf", bbox_inches="tight")


#Making SHAP feature importance bar graphs
importance = []
stds = []
for f in features:
    #print(f)
    shaps = shap_values[:, [f]].values.tolist()
    importance.append(np.absolute(shaps).mean())
    stds.append(np.absolute(shaps).std())
mpl.rcParams['axes.labelsize'] = "x-large"
mpl.rcParams['axes.titlesize'] = 'x-large'
mpl.rcParams['xtick.labelsize'] = 'x-large'
mpl.rcParams['ytick.labelsize'] = 'x-large'

fig = plt.gcf()
fig, ax = plt.subplots(figsize=(10, 3))
ax.bar(features, importance, yerr=stds,capsize=2, color="tab:pink", edgecolor="black")
plt.ylim(0,)
plt.xlabel("Runtime Event")
plt.ylabel("Avg Abs SHAP Value")
plt.xticks(rotation=55, ha='right')
plt.savefig(f"{args.output_directory}/SHAP-ranked-importance.pdf", format="pdf", bbox_inches="tight")
plt.clf()
