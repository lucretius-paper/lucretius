import dtreeviz
import pandas as pd
from xgboost import XGBRegressor
import matplotlib.pyplot as plt
import matplotlib as mpl
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Tree Visualizer')
    parser.add_argument('model', type=str, help='path to XGBoost json model')
    parser.add_argument('training', type=str, help='path to training data')
    parser.add_argument('testing', type=str, help='path to testing data')
    parser.add_argument("index", type=int, help="index to trace")
    parser.add_argument(
        '--output_directory',
        default=None,
        help='location to write the visualizer'
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
df_test = pd.read_csv(args.testing)
model = XGBRegressor(tree_method='gpu_hist', gpu_id=0)
model.load_model(args.model)
features = events_df_train.columns
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
viz_rmodel = dtreeviz.model(model=model, tree_index=1, 
                            X_train=events_df_train[features], 
                            y_train=power_df_train, 
                            feature_names=list(events_df_train.columns),
                            target_name="power")
v = viz_rmodel.view(fontname="monospace", fancy=True, x=df_test.loc[args.index][features],show_just_path=False)
v.save(f"{args.output_directory}/prediction.svg")
