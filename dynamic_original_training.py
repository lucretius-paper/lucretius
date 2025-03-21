import pandas as pd
import numpy as np
from xgboost import XGBRegressor
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import json
import time
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
machine = "A"
config = ""
vesta_model = get_model(f"./models/full-iter-{machine}.json")
thresholds = get_thresholds(f"./model_ratios/predictions/full-iter-{machine}.csv", band=0.00)
def train_smaller_model_alt(large_df, features, sizes):
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
    transfer_model = XGBRegressor()
    transfer_model.fit(events_df_train, power_df_train)
    return (transfer_model, smaller_df_train.copy(), smaller_df_test.copy())
features = get_features()
df = get_clean_vesta_df(f"./aligned_traces/{machine}-aligned.csv").fillna(-1)
def get_diff(prediction, real):                                                                                                                               
    #total_prediction_energy = prediction.sum() / len(prediction)
    #total_actual_energy = real.sum() / len(real)
    return np.abs(real - prediction).mean()
    #return np.abs(total_actual_energy - total_prediction_energy)
start = time.time()
benchmarks = df.benchmark.unique()
ratios = {}
sizes = {}
diffs = {}
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
        diffs[bench] = []
    model,df_train,df_test = train_smaller_model_alt(df, features, sizes)
    for bench in benchmarks:
        events_test = df_test[df_test.benchmark == bench]
        if len(events_test) == 0:
            continue
        events_test = events_test[features]
        #initial prediction
        prediction_energy = model.predict(events_test)
        real_energy = df_test[df_test.benchmark == bench]["power"]
        ratio_val = get_ratio(prediction_energy, real_energy)
        ratios[bench].append(ratio_val)
        diffs[bench].append(get_diff(prediction_energy, real_energy))
        plotting_info[bench][sizes[bench]] = ratio_val
    ratio_mean = pd.DataFrame(ratios).mean()
    ratio_mean_df = pd.DataFrame(ratio_mean).rename(columns={0:"mean"})
    ratio_mean_df["std"] = pd.DataFrame(ratios).std()
    ratio_mean_df = ratio_mean_df.sort_index()
    ratio_mean_df = ratio_mean_df.reset_index(names=["benchmark"])
#     over_threshold = ratio_mean_df[ratio_mean_df["mean"] > .1]
#     if len(over_threshold) > 0:
#         loop = True
#         num_loops += 1
#         for b in over_threshold["benchmark"]:
#             sizes[b] = sizes[b] + 1
#     else:
#         loop = False
    loop = False
    for b in benchmarks:
        if len(ratio_mean_df[(ratio_mean_df["benchmark"] == b) & (ratio_mean_df["mean"] > thresholds[b])]):
            if sizes[b] < 256:
                loop = True
                sizes[b] = sizes[b] + 1
    num_loops += 1
end = time.time()
training_duration = end - start
data_duration = 0
for s in sizes:
    data_duration += len(df[(df.benchmark == s) & (df.iteration <= sizes[s])])
with open (f"./core/model_ratios/time/dynamic-{machine}{config}.csv", "w") as fp:
    fp.write("model,collection,training\n")
    fp.write(f"dynamic-{machine},{data_duration},{training_duration:.0f}\n")
diff_mean = pd.DataFrame(diffs).mean()                                                                                                                
diff_mean_df = pd.DataFrame(diff_mean).rename(columns={0:"mean"})
diff_mean_df["std"] = pd.DataFrame(diffs).std()
diff_mean_df = diff_mean_df.sort_index()
diff_mean_df = diff_mean_df.reset_index(names=["benchmark"])
diff_mean_df.to_csv(f"./model_ratios/predictions/{machine}{config}.csv", index=False)
original_sizes = sizes
with open(f"./model_ratios/sizes/dynamic-{machine}{config}.json", "w") as fp:
    json.dump(original_sizes, fp)
ratio_mean_df.to_csv(f"./model_ratios/predictions/dynamic-{machine}{config}.csv", index=False)
model.save_model(f"./models/dynamic-{machine}{config}.json")
df_train.to_csv(f"./shap/dynamic-{machine}{config}-training_shap.csv", index=False)
df_test.to_csv(f"./shap/dynamic-{machine}{config}-testing_shap.csv", index=False)
