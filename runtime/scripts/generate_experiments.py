#!/usr/bin/python
# The idea here is to generate scripts that can be run later on in the pipeline
# Some things are still hard-coded for convenience, but should be changed later
#       i.e. library_path, script_path, dacapo_path, renaissance_path, renaissance_jar, when calling the renaissance jar, & the references to the vesta jar
import argparse
import shutil
import os
import json


def parse_args():
    parser = argparse.ArgumentParser(
        description="Probes Parser", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-iters", "--iters", type=int,
                        help="Number of iterations")
    parser.add_argument("-exp_path", "--exp_path", type=str,
                        help="Path where you want to generate the experiments")
    parser.add_argument("-java_path", "--java_path", type=str,
                        help="Path to specified java version", default="java")
    parser.add_argument("-benchmarks", "--benchmarks", type=str,
                        help="Path to benchmarks file")
    parser.set_defaults(verbose=False)

    return parser.parse_args()


def create_dir(str_dir):
    try:
        os.makedirs(str_dir, exist_ok=True)
    except FileExistsError:
        print("Directory already exists...skipping creation")
    except:
        print("OS error! Could not create %s" % (str_dir))
        quit()


def main():
    args = parse_args()
    exp_path = args.exp_path
    java_path = args.java_path
    benchmarks = args.benchmarks
    iters = args.iters
    launch_path = exp_path + "/launch"
    library_extra_papi = f"LD_LIBRARY_PATH={os.getcwd()}/bin/.:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
    library_path = f"{os.getcwd()}/bin"
    vesta_jar = f"{os.getcwd()}/target/vesta-0.1.0-jar-with-dependencies.jar"
    dacapo_path = f"{os.getcwd()}/lib/dacapo.jar:{vesta_jar}"
    renaissance_path = f"{os.getcwd()}/lib/renaissance-gpl-0.14.1.jar:{vesta_jar}"
    renaissance_jar = f"{os.getcwd()}/lib/renaissance-gpl-0.14.1.jar"
    script_path = f"{os.getcwd()}/scripts"
    gc = ""

    os.makedirs(launch_path, exist_ok=True)
    shutil.copyfile(benchmarks, os.path.join(exp_path, "benchmarks.json"))
    with open(benchmarks) as fp:
        cluster_count = 0
        tests = json.load(fp)

    for test in tests:
        benchmark = test["benchmark"]
        suite = test["suite"]
        output_directory = f'{exp_path}/{cluster_count}_{benchmark}'

        command = []
        command.extend([
            f'{library_extra_papi} {java_path} {gc}',
            '-XX:+ExtendedDTraceProbes',
            f'-Dvesta.library.path={library_path}',
            f'-Dvesta.output.directory={output_directory}'])

        do_filter = "filter" in test and test["filter"] == "yes"
        if do_filter:
            window = test["window"]
            variance = test["variance"]
            baseline_path = test["baseline_path"]
            command.append(f'-Dvesta.baseline.path={baseline_path}')

        if suite == "dacapo":
            callback = 'FilteringVestaDacapoCallback' if do_filter else 'VestaDacapoCallback'
            size = test["size"]
            command.extend([
                f'-cp {dacapo_path}',
                f'Harness {benchmark} -s {size} -c vesta.{callback}',
                f'--no-validation --iterations {iters}'])
            if do_filter:
                command.append(f'--window {window} --variance {variance}')
        elif suite == "renaissance":
            plugin = 'FilteringVestaRenaissancePlugin' if do_filter else 'VestaRenaissancePlugin'
            if do_filter:
                command.append(
                    f'-Dvesta.renaissance.args={iters},{window},{variance}')
            command.extend(
                [f'-cp {renaissance_path}', f'-jar {renaissance_jar}'])
            if do_filter:
                command.append(f'--policy {vesta_jar}!vesta.{plugin}')
            command.append(
                f'-r {iters} --plugin {vesta_jar}!vesta.{plugin} {benchmark}')
        elif suite == "custom":
            main_class = test["main_class"]
            bench_args = test["args"].format(iters=iters)
            command.append(f'-cp {vesta_jar} {main_class} {bench_args}')
        else:
            print(f'unrecognized suite {suite}! continuing...')
            continue

        probes = test["probes"] if "probes" in test else ""
        if probes != "":
            command[-1] += '&'
            command = [' \\\n    '.join(command)]

            command.append('pid=$!')
            command.append('')
            command.append(
                f'python3 {script_path}/java_multi_probe.py --pid $! --probes={probes} --output_directory={output_directory}')
            command.append('tail --pid="${pid}" -f /dev/null')
        else:
            command = [' \\\n    '.join(command)]

        os.makedirs(output_directory, exist_ok=True)
        with open(f'{launch_path}/cluster_{cluster_count}.sh', "w") as output_file:
            output_file.write('\n'.join(command))

        cluster_count = cluster_count + 1


if __name__ == '__main__':
    main()
