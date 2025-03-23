import pandas as pd
import numpy as np
from xgboost import XGBRegressor
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import json
import time
import argparse

parser = argparse.ArgumentParser(description="Offline Transfer Learning", formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("source_machine",help="Name of source machine")
parser.add_argument("target_machine",help="Name of target machine")
parser.set_defaults(verbose=False)
args = parser.parse_args() 


def get_features():
    return ["thread__park","SetIntField","SetByteArrayRegion","NewStringUTF","gc","vmops","thread__sleep",
                 "GetStringLength","GetObjectClass","GetMethodID","method__compile","safepoint","GetObjectArrayElement",
                 "CallVoidMethod","compiled__method__load","NewString",
                 "IsInstanceOf","GetEnv","CallObjectMethod","ReleaseIntArrayElements",
                 "GetByteArrayElements","Throw","compiled__method__unload"]
def get_ratio(prediction, real):
    total_prediction_energy = prediction.sum()
    total_actual_energy = real.sum()
    return np.abs((total_actual_energy - total_prediction_energy) / total_actual_energy)
def get_model(path):
    vesta_model =  XGBRegressor()
    vesta_model.load_model(path)
    return vesta_model
def get_thresholds(path, band=0):
    thresholds = pd.read_csv(path).set_index("benchmark").sum(axis=1).round(3).to_dict()
    for b in thresholds:
        #if thresholds[b] < band:
        #    thresholds[b] = band
        thresholds[b] += band
    return thresholds
def get_clean_vesta_df(filename):
    df = pd.read_csv(filename).fillna(-1)
    df = df[df.power <= 10**5]
    df = df[df.power > 0]
    df = df.drop([col for col in df.columns if '__entry' in col], axis=1)
    df = df.drop([col for col in df.columns if '__return' in col], axis=1)
    df = df.drop([col for col in df.columns if '__begin' in col], axis=1)
    df = df.drop([col for col in df.columns if '__end' in col], axis=1)
    try:
        df["NewStringUTF"]
    except KeyError:
        df["NewStringUTF"] = -1
    try:
        df["NewString"]
    except KeyError:
        df["NewString"] = -1
    df["iteration"] = df.iteration - df.iteration.min()+1
    return df

source_machine = args.source_machine
target_machine = args.target_machine
config = ""
band = 0.02
vesta_model = get_model(f"../data/originals/models/dynamic-{source_machine}.json")
thresholds = get_thresholds(f"../data/originals/predictions/dynamic-{source_machine}.csv", band=band)

original_size = dict()
with open(f"../data/originals/sizes/dynamic-{source_machine}.json","r") as fp:
    original_size = json.load(fp)

from sklearn.linear_model import LinearRegression
def train_smaller_model_alt(large_df, features, original_model, sizes):
    smaller_df_train = pd.DataFrame()
    smaller_df_test = pd.DataFrame()
    for b in large_df.benchmark.unique():
        bench_df = large_df[large_df.benchmark == b]
        train_data = bench_df[bench_df["iteration"] <= sizes[b]]
        while len(train_data) < 2:
            sizes[b] += 1
            train_data = bench_df[bench_df["iteration"] <= sizes[b]]
        split_train, split_test = train_test_split(train_data, test_size=.5)
        smaller_df_train = pd.concat([smaller_df_train, split_train])
        smaller_df_test = pd.concat([smaller_df_test, split_test])
    events_df_train = smaller_df_train[features]
    power_df_train = smaller_df_train["power"]
    prediction_energy = original_model.predict(events_df_train)
    power_diff = pd.Series(prediction_energy, dtype=np.float64) - power_df_train.reset_index(drop=True)
    transfer_model = XGBRegressor()
    #transfer_model = LinearRegression()
    transfer_model.fit(events_df_train, power_diff)
    return (transfer_model, events_df_train.copy(), smaller_df_test.copy())
features = get_features()
df = get_clean_vesta_df(f"../data/aligned_traces/{target_machine}-aligned.csv").fillna(-1)
start = time.time()
benchmarks = df.benchmark.unique()
ratios = {}
sizes = {}
plotting_info = dict()
loop = True
num_loops = 0
for bench in benchmarks:
    ratios[bench] = []
    sizes[bench] = 1
    plotting_info[bench] = dict()
while loop:
    for bench in benchmarks:
        ratios[bench] = []
    transfer_model,df_train,df_test = train_smaller_model_alt(df, features, vesta_model, sizes)
    for bench in benchmarks:
        events_test = df_test[df_test.benchmark == bench]
        if len(events_test) == 0:
            continue
        events_test = events_test[features]
        #initial prediction
        prediction_energy = vesta_model.predict(events_test)
        #transformation
        transformed_energy = prediction_energy - transfer_model.predict(events_test)
        real_energy = df_test[df_test.benchmark == bench]["power"]
        ratio_val = get_ratio(transformed_energy, real_energy)
        ratios[bench].append(ratio_val)
        plotting_info[bench][sizes[bench]] = ratio_val
    ratio_mean = pd.DataFrame(ratios).mean()
    ratio_mean_df = pd.DataFrame(ratio_mean).rename(columns={0:"mean"})
    ratio_mean_df["std"] = pd.DataFrame(ratios).std()
    ratio_mean_df = ratio_mean_df.sort_index()
    ratio_mean_df = ratio_mean_df.reset_index(names=["benchmark"])
    loop = False
    for b in benchmarks:
        if len(ratio_mean_df[(ratio_mean_df["benchmark"] == b) & (ratio_mean_df["mean"] > thresholds[b])]):
            if sizes[b] < original_size[b]:
                loop = True
                sizes[b] = sizes[b] + 1
    num_loops += 1
end = time.time()
training_duration = end - start
data_duration = 0
for s in sizes:
    data_duration += len(df[(df.benchmark == s) & (df.iteration <= sizes[s])])
with open (f"../data/transfers/times/{source_machine}-to-{target_machine}{config}.csv", "w") as fp:
    fp.write("model,collection,training\n")
    fp.write(f"{source_machine}-to-{target_machine},{data_duration},{training_duration:.0f}\n")
transfer_size = sizes
with open(f"../data/transfers/sizes/{source_machine}-to-{target_machine}{config}.json", "w") as fp:
    json.dump(transfer_size, fp)
ratio_mean_df.to_csv(f"../data/transfers/predictions/{source_machine}-to-{target_machine}{config}.csv", index=False)
transfer_model.save_model(f"../data/transfers/models/{source_machine}-to-{target_machine}{config}.json")
df_train.to_csv(f"../data/transfers/splits/{source_machine}-to-{target_machine}{config}-training_shap.csv", index=False)
df_test.to_csv(f"../data/transfers/splits/{source_machine}-to-{target_machine}{config}-testing_shap.csv", index=False)
