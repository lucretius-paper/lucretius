#!/usr/bin/env python3
from concurrent import futures
import logging
import time
import threading
import grpc
import lucretius_service_pb2
import lucretius_service_pb2_grpc
import argparse
import warnings
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from xgboost import XGBRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from vesta import Vesta
from alignment import align_benchmark_iter,synthesize_probes
warnings.simplefilter(action='ignore', category=FutureWarning)

class LucretiusState():

    def __init__(self, probes, output_directory, target_directory, transfer):
        self.applications = dict() #pid to str (app name) map
        self.thresholds = dict() #str (app name) to target ratio
        self.iter_bound = dict() #str (app name) to int (bound iterations) map
        self.iter_count = dict() #pid to int (iteration count) map
        self.application_client_locks = dict() #pid to conditional lock map
        self.vestas = dict() # pid to vesta instance map
        self.run_again = dict() #pid to bool map
        self.arrivals_lock = threading.Lock()
        self.arrivals_count = 0
        self.shutdown_clients = False
        self.app_is_running = False
        self.transfer = transfer #Indicates if transfer or dynamic original training is desired
        self.probes = probes #String of probes separated by ','
        self.output_directory = output_directory #Path to top level directory
        self.target_directory = target_directory #Path to target directory
        self.aligned_data = pd.DataFrame()
        self.original_model = None #The original model if performing a transfer
        self.model = None #The model storage to eventually return
        self.df_train = None
        self.df_test = None
        self.ratios = None
        if transfer:
            self.original_model = get_model(f"{target_directory}/model.json")
            with open(f"{target_directory}/sizes.json","r") as size_fp:
                self.iter_bound = json.load(size_fp)

    def arrivals_atomic_add(self):
        with self.arrivals_lock:
            self.arrivals_count += 1

    def arrivals_atomic_subtract(self):
        with self.arrivals_lock:
            self.arrivals_count -= 1

    def finished_iter(self):
        self.app_is_running = False

    def started_iter(self):
        self.app_is_running = True

    def is_running(self):
        return self.app_is_running
            
    def is_shutdown(self):
        return self.shutdown_clients
        
    def shutdown(self):
        self.shutdown_clients = True
        
    def add_app(self, application, pid):
        self.applications[pid] = application
        self.application_client_locks[pid] = threading.Condition()
        self.vestas[pid] = Vesta(pid, self.probes, f"{self.output_directory}/{application}/")
        self.run_again[pid] = True
        self.iter_count[pid] = 0
        
class LucretiusServiceServicer(lucretius_service_pb2_grpc.LucretiusServiceServicer):

    def __init__(self, glob_state):
        self.state = glob_state
    
    def connect(self, request, context): #Receives a ConnectionRequest
        app_name = request.application_name
        pid = request.pid
        self.state.add_app(app_name, pid) #Add pid:application info to global state
        #print(f"{app_name} CONNECTED!")
        return lucretius_service_pb2.ConnectionResponse(is_available=True) #Notify that client is connected

    def start(self, request, context): #Receives a StartRequest
        pid = request.pid
        with self.state.application_client_locks[pid]:
            self.state.arrivals_atomic_add()
            #print(f"{pid}:{self.state.applications[pid]} IS WAITING")
            self.state.application_client_locks[pid].wait() #Wait for main thread to let application run
        self.state.arrivals_atomic_subtract()
        run_app = not(self.state.shutdown_clients)
        #print(f"Telling {pid}:{self.state.applications[pid]} TO RUN")
        return lucretius_service_pb2.StartResponse(can_run=run_app) #Tell JVM to run the app
    
    def finished(self, request, context): #Receives a FinishedNotification
        pid = request.pid
        self.state.finished_iter()
        return lucretius_service_pb2.Empty() #Let the JVM get back to a starting state
        
    def check_shutdown(self):
        return self.state.is_shutdown()

def get_features(lucretius_state):
    return sorted(set([p[:p.rfind("__")].strip() if "begin" in p or "end" in p or "entry" in p or "return" in p else p for p in lucretius_state.probes.split(',')]))
    # return ["thread__park","SetIntField","SetByteArrayRegion","NewStringUTF","gc","vmops","thread__sleep",
    #              "GetStringLength","GetObjectClass","GetMethodID","method__compile","safepoint","GetObjectArrayElement",
    #              "CallVoidMethod","compiled__method__load","NewString",
    #              "IsInstanceOf","GetEnv","CallObjectMethod","ReleaseIntArrayElements",
    #              "GetByteArrayElements","Throw","compiled__method__unload"]

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
        thresholds[b] += band
    return thresholds

def get_clean_vesta_df(lucretius_state, aligned_trace):
    df = aligned_trace.fillna(-1)
    df = df[df.power <= 10**5]
    df = df[df.power > 0]
    df = df.drop([col for col in df.columns if '__entry' in col], axis=1)
    df = df.drop([col for col in df.columns if '__return' in col], axis=1)
    df = df.drop([col for col in df.columns if '__begin' in col], axis=1)
    df = df.drop([col for col in df.columns if '__end' in col], axis=1)
    for feature in get_features(lucretius_state):
        #Sometimes the benchmarks you want to track don't fire...
        try:
            df[feature]
        except KeyError:
            df[feature] = -1
    df["iteration"] = df.iteration - df.iteration.min()+1
    return df

def train_smaller_model_original(large_df, features):
    smaller_df_train = pd.DataFrame()
    smaller_df_test = pd.DataFrame()
    for b in large_df.benchmark.unique():
        bench_df = large_df[large_df.benchmark == b]
        train_data = bench_df
        if len(train_data) < 2:
            print(f"{b} did not have enough data for training!")
            continue            
        split_train, split_test = train_test_split(train_data, test_size=.5)
        smaller_df_train = pd.concat([smaller_df_train, split_train])
        smaller_df_test = pd.concat([smaller_df_test, split_test])
    events_df_train = smaller_df_train[features]
    power_df_train = smaller_df_train["power"]
    transfer_model = XGBRegressor()
    transfer_model.fit(events_df_train, power_df_train)
    return (transfer_model, smaller_df_train.copy(), smaller_df_test.copy())

def train_smaller_model_transfer(large_df, features, original_model):
    smaller_df_train = pd.DataFrame()
    smaller_df_test = pd.DataFrame()
    for b in large_df.benchmark.unique():
        bench_df = large_df[large_df.benchmark == b]
        train_data = bench_df
        if len(train_data) < 2:
            print(f"{b} did not have enough data for training!")
            continue
        split_train, split_test = train_test_split(train_data, test_size=.5)
        smaller_df_train = pd.concat([smaller_df_train, split_train])
        smaller_df_test = pd.concat([smaller_df_test, split_test])
    events_df_train = smaller_df_train[features]
    power_df_train = smaller_df_train["power"]
    prediction_energy = original_model.predict(events_df_train)
    power_diff = pd.Series(prediction_energy, dtype=np.float64) - power_df_train.reset_index(drop=True)
    transfer_model = XGBRegressor()
    transfer_model.fit(events_df_train, power_diff)
    return (transfer_model, events_df_train.copy(), smaller_df_test.copy())


def get_diff(prediction, real):    
    return np.abs(real - prediction).mean()

def dynamic_original_training(lucretius_state):
    features = get_features(lucretius_state)
    df = get_clean_vesta_df(lucretius_state, lucretius_state.aligned_data).fillna(-1)
    benchmarks = df.benchmark.unique()
    ratios = dict()
    diffs = dict()
    for bench in benchmarks:
        ratios[bench] = []
        diffs[bench] = []
    model,df_train,df_test = train_smaller_model_original(df, features)
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
    for b in ratios:
        if len(ratios[b]) == 0:
            ratios[b].append(100000) #Indicates there was not enough data to train that benchmark
    ratio_mean = pd.DataFrame(ratios).mean()
    ratio_mean_df = pd.DataFrame(ratio_mean).rename(columns={0:"mean"})
    ratio_mean_df["std"] = pd.DataFrame(ratios).std()
    ratio_mean_df = ratio_mean_df.sort_index()
    ratio_mean_df = ratio_mean_df.reset_index(names=["benchmark"])
    #Set the state to the most recent training run
    lucretius_state.model = model
    lucretius_state.df_train = df_train
    lucretius_state.df_test = df_test
    lucretius_state.ratios = ratio_mean_df
    return

def dynamic_transfer_training(lucretius_state):
    features = get_features(lucretius_state)
    df = get_clean_vesta_df(lucretius_state, lucretius_state.aligned_data).fillna(-1)
    benchmarks = df.benchmark.unique()
    ratios = dict()
    diffs = dict()
    for bench in benchmarks:
        ratios[bench] = []
        diffs[bench] = []
    transfer_model,df_train,df_test = train_smaller_model_transfer(df, features, lucretius_state.original_model)
    for bench in benchmarks:
        events_test = df_test[df_test.benchmark == bench]
        if len(events_test) == 0:
            continue
        events_test = events_test[features]
        #initial prediction
        prediction_energy = lucretius_state.original_model.predict(events_test)
        #transformation
        transformed_energy = prediction_energy - transfer_model.predict(events_test)
        real_energy = df_test[df_test.benchmark == bench]["power"]
        ratio_val = get_ratio(transformed_energy, real_energy)
        ratios[bench].append(ratio_val)
        diffs[bench].append(get_diff(prediction_energy, real_energy))
    for b in ratios:
        if len(ratios[b]) == 0:
            ratios[b].append(100000) #Indicates there was not enough data to train that benchmark
    ratio_mean = pd.DataFrame(ratios).mean()
    ratio_mean_df = pd.DataFrame(ratio_mean).rename(columns={0:"mean"})
    ratio_mean_df["std"] = pd.DataFrame(ratios).std()
    ratio_mean_df = ratio_mean_df.sort_index()
    ratio_mean_df = ratio_mean_df.reset_index(names=["benchmark"])
    #Set the state to the most recent training run
    lucretius_state.model = transfer_model
    lucretius_state.df_train = df_train
    lucretius_state.df_test = df_test
    lucretius_state.ratios = ratio_mean_df
    return


def dump(lucretius_state):
    #num_loops += 1
    #end = time.time()
    #training_duration = end - start
    # data_duration = 0
    # for s in sizes:
    #     data_duration += len(df[(df.benchmark == s) & (df.iteration <= sizes[s])])
    # with open (f"../data/originals/times/dynamic-{machine}{config}.csv", "w") as fp:
    #     fp.write("model,collection,training\n")
    #     fp.write(f"dynamic-{machine},{data_duration},{training_duration:.0f}\n")
    # diff_mean = pd.DataFrame(diffs).mean()
    # diff_mean_df = pd.DataFrame(diff_mean).rename(columns={0:"mean"})
    # diff_mean_df["std"] = pd.DataFrame(diffs).std()
    # diff_mean_df = diff_mean_df.sort_index()
    # diff_mean_df = diff_mean_df.reset_index(names=["benchmark"])
    # diff_mean_df.to_csv(f"../data/originals/predictions/{machine}{config}.csv", index=False)
    formatted_counts = dict()
    for pid in lucretius_state.iter_count:
        formatted_counts[lucretius_state.applications[pid]] = lucretius_state.iter_count[pid]
    with open(f"{lucretius_state.output_directory}/sizes.json", "w") as fp:
        json.dump(formatted_counts, fp)
    lucretius_state.ratios.to_csv(f"{lucretius_state.output_directory}/ratios.csv", index=False)
    lucretius_state.model.save_model(f"{lucretius_state.output_directory}/model.json")
    lucretius_state.df_train.to_csv(f"{lucretius_state.output_directory}/training.csv", index=False)
    lucretius_state.df_test.to_csv(f"{lucretius_state.output_directory}/testing.csv", index=False)

    
def run_iters(lucretius_state):
    while(lucretius_state.arrivals_count != len(lucretius_state.applications)):
        #Stall until all of the clients are waiting
        time.sleep(1)
    for pid in lucretius_state.applications:
        pid_client_lock = lucretius_state.application_client_locks[pid] #Grab lock for application
        lucretius_state.started_iter() #Started iteration
        if(not(lucretius_state.is_shutdown())):
            if lucretius_state.run_again[pid]:
                with pid_client_lock:
                    print(f"NOTIFYING {pid}:{lucretius_state.applications[pid]}")
                    pid_client_lock.notify()
                lucretius_state.vestas[pid].start()
                while(lucretius_state.is_running()):
                    lucretius_state.vestas[pid].poll()
                    #put a wait?
                lucretius_state.iter_count[pid] += 1
                lucretius_state.vestas[pid].dump()
        else:
            with pid_client_lock:
                print(f"(SHUTDOWN) NOTIFYING {pid}:{lucretius_state.applications[pid]}")
                pid_client_lock.notify()
            while(lucretius_state.is_running()):
                time.sleep(1)            
            #lucretius_state.vestas[pid].dump()
        
def shutdown(lucretius_state):
    print("SHUTTING DOWN APPS")
    while(lucretius_state.arrivals_count != len(lucretius_state.applications)):
        #Stall until all of the clients are waiting
        time.sleep(1)
    lucretius_state.shutdown() #Set the shutdown flag
    #Wake up threads to shutdown
    run_iters(lucretius_state)

def check_loop(lucretius_state):
    ratios = None
    
    if lucretius_state.transfer:
        thresholds = get_thresholds(f"{lucretius_state.target_directory}/ratios.csv", band=0.02)
        dynamic_transfer_training(lucretius_state)
    else:
        thresholds = get_thresholds(f"{lucretius_state.target_directory}/ratios.csv", band=0.00)
        dynamic_original_training(lucretius_state)
    ratios = lucretius_state.ratios
    for pid in lucretius_state.run_again:
        b = lucretius_state.applications[pid]
        if len(ratios[(ratios["benchmark"] == b) & (ratios["mean"] > thresholds[b])]):
            if lucretius_state.transfer:
                if lucretius_state.iter_count[pid] < lucretius_state.iter_bound[lucretius_state.applications[pid]]:
                    lucretius_state.run_again[pid] = True
                else:
                    lucretius_state.run_again[pid] = False
            else:
                if lucretius_state.iter_count[pid] < 256:
                    lucretius_state.run_again[pid] = True
                else:
                    lucretius_state.run_again[pid] = False
        else:
            lucretius_state.run_again[pid] = False
    return any([lucretius_state.run_again[k] for k in lucretius_state.run_again])

def align(lucretius_state):
    for pid in lucretius_state.run_again:
        if lucretius_state.run_again[pid]:
            #If we an an iteration we must align that data and store it in memory, i.e. append it to our df
            align_df = align_benchmark_iter(lucretius_state.output_directory, lucretius_state.applications[pid], lucretius_state.iter_count[pid], 0, 1000)
            lucretius_state.aligned_data = pd.concat([lucretius_state.aligned_data, align_df.reset_index()])
            
def lucretius_loop(lucretius_state):
    response = "FILLER"
    while response != "":
        response = input("\rPLEASE TYPE ENTER WHEN YOU'VE FINISHED CONNECTING YOUR APPLICATIONS ")
    #Each app should be run at least once
    for i in range(5):
        run_iters(lucretius_state)
        align(lucretius_state)
    while check_loop(lucretius_state):
        run_iters(lucretius_state)
        align(lucretius_state)
    shutdown(lucretius_state)

def parse_args():
    parser = argparse.ArgumentParser(description='lucretius server')
    parser.add_argument(
        '-t',
        '--transfer',
        default=False,
        action="store_true",
        help="Flag for performing transfer (default is dynamic original training)"
    )
    parser.add_argument(
        '--target',
        default=None,
        type=str,
        help="path to target data"
    )
    parser.add_argument(
        '--probes',
        default='monitor__wait',
        type=str,
        help='jvm probes to trace'
    )
    parser.add_argument(
        '--output_directory',
        default='.',
        type=str,
        help='top level directory containing experiment folders'
    )
    return parser.parse_args()

    
def main():
    args = parse_args()
    state = LucretiusState(args.probes, args.output_directory, args.target, args.transfer)
    server = grpc.server(futures.ThreadPoolExecutor()) #Not setting max_workers
    lucretius_service_pb2_grpc.add_LucretiusServiceServicer_to_server(
        LucretiusServiceServicer(state), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Started up LucRETius server")
    lucretius_loop(state)
    print("ALL APPS DISCONNECTED")
    dump(state)
    server.stop(5)    

if __name__ == "__main__":
    main()
