
# !/usr/bin/python

import pandas as pd
import numpy as np
import os
import argparse
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)


pd.options.mode.chained_assignment = None

# default values for the experiments run
WRAP_AROUND_VALUE = 262143
WARM_UP = 5
BUCKET_SIZE_MS = 4


def maybe_apply_wrap_around(value):
    ''' applies the rapl wrap around if a diff is negative '''
    if value < 0:
        return value + WRAP_AROUND_VALUE
    else:
        return value


def normalize_timestamps(timestamps, bucket_size_ms=BUCKET_SIZE_MS):
    ''' normalizes ns timestamps to ms-bucketed timestamps '''
    # TODO: this is producing strange behavior due to int division:
    #   2938450289096200 // 10**6 = 2938450288
    return timestamps // 10**6 // bucket_size_ms


def samples_to_power(samples, normalize_timestamps_fn=None):
    ''' computes the power of each ts bucket '''
    samples = samples.copy(deep=True)
    if normalize_timestamps_fn is not None:
        samples['ts'] = normalize_timestamps_fn(samples.timestamp)
    else:
        samples['ts'] = normalize_timestamps(samples.timestamp)
    # TODO: i've prefered interval beginning. is there a best practice?
    samples = samples.groupby(['ts', 'iteration']).min().sort_index()
    df = samples.groupby('iteration').diff().dropna()
    d_t = df.timestamp / 10 ** 9
    components = [col for col in samples.columns if 'energy_component' in col]
    d_e = df[components].apply(lambda s: s.map(maybe_apply_wrap_around))
    d_e = d_e.sum(axis=1)
    power = d_e / d_t
    power.name = 'power'
    return power


# Gross way to handle solo components without rocking the boat too much
def samples_to_power_single_component(samples, component_name, normalize_timestamps_fn=None):
    ''' computes the power of each ts bucket '''
    samples = samples.copy(deep=True)
    if normalize_timestamps_fn is not None:
        samples['ts'] = normalize_timestamps_fn(samples.timestamp)
    else:
        samples['ts'] = normalize_timestamps(samples.timestamp)
    # TODO: i've prefered interval beginning. is there a best practice?
    samples = samples.groupby(['ts', 'iteration']).min().sort_index()
    df = samples.groupby('iteration').diff().dropna()
    d_t = df.timestamp / 10 ** 9
    d_e = df[[component_name]].apply(lambda s: s.map(maybe_apply_wrap_around))
    d_e = d_e.sum(axis=1)
    power = d_e / d_t
    power.name = f'{component_name}_power'
    return power


def bucket_probes(probes, normalize_timestamps_fn=None):
    ''' sums the number of probe events for each probe into ts buckets '''
    probes = probes.copy(deep=True)
    if normalize_timestamps_fn is not None:
        probes['ts'] = normalize_timestamps_fn(probes.event_time)
    else:
        probes['ts'] = normalize_timestamps(probes.event_time)
    probes = probes.groupby(['ts', 'probe']).event_time.count()
    probes.name = 'events'

    return probes


PROBE_TOKEN = '__'


def to_probe_kinds(probes):
    return probes.str.split(PROBE_TOKEN).str[:-1].str.join(PROBE_TOKEN)


ENTRY_TOKENS = ['begin', 'entry']
EXIT_TOKENS = ['end', 'return']
SYNTHESIZABLE_TOKEN_PAIRS = list((ENTRY_TOKENS, EXIT_TOKENS))


def is_synthesizable(probes):
    is_synthesizable_pair = map(
        lambda x: any(t in x[0] for t in x[1]),
        zip(probes, SYNTHESIZABLE_TOKEN_PAIRS)
    )
    # print(probes, SYNTHESIZABLE_TOKEN_PAIRS)
    return len(probes) == 2 and all(is_synthesizable_pair)


# TODO: the synthesis and metric computations are a little crude
def synthesize_probes(probes):
    # invalid data rules:
    #  - no synthesizable columns
    #  -
    # print(probes)
    # if len(probes.unstack().dropna()) == 0:
    #     return pd.DataFrame()

    probe_kind = probes.reset_index().probe
    probe_kind = pd.concat([
        to_probe_kinds(probe_kind),
        probe_kind
    ], axis=1)
    probe_kind.columns = ['probe_kind', 'probe']
    probe_kind = probe_kind.groupby('probe_kind').probe.unique().to_dict()
    probe_kind = {kind: probe_names for kind,
                  probe_names in probe_kind.items() if is_synthesizable(probe_names)}

    if len(probe_kind) == 0:
        return pd.DataFrame()

    probes = probes.unstack(fill_value=0)

    arr = []
    for kind, probe_names in probe_kind.items():
        probe_names = np.sort(probe_names)
        if is_synthesizable(probe_names):
            df = probes[probe_names]
            # diff will do begin - end, so we have to flip things a little bit
            synthesized = df.min(axis=1) - df.diff(axis=1).iloc[:, -1].cumsum()
            synthesized.name = kind
            arr.append(synthesized)

    synthesized = pd.concat(arr, axis=1).reset_index()
    synthesized = synthesized.set_index(
        'ts')[[kind for kind in probe_kind.keys() if kind != '']].stack()
    synthesized.name = 'events'
    return synthesized.unstack()


def norm_with_buckets(bucket_size_ms=BUCKET_SIZE_MS):
    return lambda timestamps: normalize_timestamps(timestamps, bucket_size_ms)


def parse_args():
    parser = argparse.ArgumentParser(description='jvm probe tracer')
    parser.add_argument('data', type=str, help='path to probing data')
    parser.add_argument(
        '--warm_up',
        type=int,
        default=WARM_UP,
        help='number of warm ups',
    )
    parser.add_argument(
        '--bucket',
        type=int,
        default=BUCKET_SIZE_MS,
        help='size of the ms timestamp buckets',
    )
    parser.add_argument(
        '--output_directory',
        default=None,
        help='location to write the summary and metrics'
    )
    parser.add_argument(
        "--out_file_name",
        default="aligned_data.csv",
        help="filename for alignment"
    )
    args = parser.parse_args()
    if args.output_directory is None:
        args.output_directory = os.path.join(args.data)

    return args


def main():
    args = parse_args()

    # probes = list(filter(lambda f: os.path.isdir(os.path.join(args.data, f)), os.listdir(args.data)))
    # probes = [args.output_directory]

    # print('processing experiments:')
    # print(probes)

    aligned = []
    probe = args.data
    # for probe in probes:
    print('aligning data for {}'.format(probe))
    for benchmark in os.listdir(os.path.join(args.data)):
        if '_' not in benchmark or '.' in benchmark:
            continue
        bench = benchmark.split('_')[-1]
        print(f'aligning {bench}')
        data_dir = os.path.join(args.data, benchmark)

        # TODO: we should be able handle all the potential failures but
        #       i got frustrated
        try:
            energy = pd.read_csv(os.path.join(data_dir, 'energy.csv'))
            energy = energy[energy.iteration > args.warm_up]
            iteration_times = energy.groupby(
                'iteration').timestamp.agg(('min', 'max'))

            probes = []
            for chunk in pd.read_csv(os.path.join(data_dir, 'probes.csv'), chunksize=10**6):
                mask = None
                for iteration_time in iteration_times.values:
                    # print(iteration_time)
                    time_range = (iteration_time[0] <= chunk.event_time) & (
                        chunk.event_time <= iteration_time[1])
                    if mask is None:
                        mask = time_range
                    else:
                        mask = mask | time_range
                # print(len(chunk))
                chunk = chunk[mask]
                # print(chunk)
                # print(chunk[mask])
                # ts_first = chunk.event_time.iloc[0]
                # ts_last = chunk.event_time.iloc[-1]
                # df = pd.read_csv(os.path.join(data_dir, 'probes.csv'))
                probe_kind = chunk.probe
                probe_kind.loc[probe_kind.str.contains('sys_enter')] = probe_kind.loc[probe_kind.str.contains(
                    'sys_enter')].str.replace('sys_enter_', '') + '__entry'
                probe_kind.loc[probe_kind.str.contains('sys_exit')] = probe_kind.loc[probe_kind.str.contains(
                    'sys_exit')].str.replace('sys_exit_', '') + '__return'
                chunk["probe"] = probe_kind
                chunk = bucket_probes(
                    chunk,
                    norm_with_buckets(args.bucket),
                )
                # print(len(chunk))
                probes.append(chunk)

            probes = pd.concat(probes).groupby(['ts', 'probe']).sum()
            # print(len(probes))
            # print(probes)
            # return

            ts_first = probes.reset_index().ts.min() * 10**6 * args.bucket
            ts_last = probes.reset_index().ts.max() * 10**6 * args.bucket
            if probes.sum() > 0:
                # df = pd.read_csv(os.path.join(data_dir, 'energy.csv'))
                # df = df[df.iteration > args.warm_up]
                df = energy
                df = df[(df.timestamp >= ts_first) &
                        (df.timestamp <= ts_last)]
                if len(df) == 0:
                    continue
                power = df.groupby('iteration').apply(lambda s: samples_to_power(
                    s, norm_with_buckets(args.bucket)).reset_index('iteration', drop=True))
                # merge the power and probes along the timestamp and drop
                # all records that have no power
                components = [
                    col for col in df.columns if 'energy_component' in col]
                df_energy = pd.read_csv(
                    os.path.join(data_dir, 'energy.csv'))
                df_energy = df_energy[df_energy.iteration > args.warm_up]
                df_energy = df_energy[(df_energy.timestamp >= ts_first) & (
                    df_energy.timestamp <= ts_last)]
                df = pd.merge(
                    power.reset_index(),
                    probes.unstack(),
                    on='ts',
                    how='left'
                ).set_index(['iteration', 'ts']).sort_index()
                # Goofy nonsense to shove the individual components into
                for component in components:
                    comp_power = df_energy.groupby('iteration').apply(lambda s: samples_to_power_single_component(
                        s, component, norm_with_buckets(args.bucket)).reset_index('iteration', drop=True))
                    df = pd.merge(
                        df,
                        comp_power.reset_index(),
                        on='ts',
                        how='left'
                    ).set_index(['iteration', 'ts']).sort_index()
                df.columns.name = 'probe'
                df = df.stack()
                df.name = 'events'

                try:
                    synth = df.groupby('iteration').apply(
                        synthesize_probes).stack()
                    df = pd.concat([df, synth]).unstack().assign(
                        benchmark=bench).set_index('benchmark', append=True)
                    # df = pd.concat([df.unstack()[[col for col in df.unstack() if not any(token in col for token in ENTRY_TOKENS + EXIT_TOKENS)]].stack(), synth]).unstack().assign(benchmark=bench).set_index('benchmark', append=True)
                except Exception as e:
                    print(f'error synthesizing {bench}')
                    print(e)
                    df = df.unstack().assign(benchmark=bench).set_index('benchmark', append=True)
                aligned.append(df)
                # print("writing to csv...")
                # df.to_csv("{}/{}/{}/aligned.csv".format(args.data, probe, benchmark))
                # print("wrote to csv!")
            else:
                print('no probe events for {}!'.format(benchmark))
        except KeyboardInterrupt:
            return
        except Exception as e:
            print('error handling data for {}!'.format(benchmark))
            print(e)

    aligned = pd.concat(aligned)
    probes = list(aligned.columns)
    probes.remove('power')
    aligned = aligned[['power'] + probes]
    aligned.to_csv(args.out_file_name)
    print(aligned)


if __name__ == '__main__':
    main()
