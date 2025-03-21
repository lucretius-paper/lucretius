# `VESTA`

VESTA is a power modeling system that uses *language runtime events* for prediction. Below is the abstract for the publication.

```
Power modeling is an essential building block for computer systems in support of energy optimization,
energy profiling, and energy-aware application development. We introduce `VESTA`, a novel approach
to modeling the power consumption of applications with one key insight: *language runtime* events
are often correlated with a sustained level of power consumption. When compared with the established
approach of power modeling based on hardware performance counters (HPCs), `VESTA` has the benefit of not
requiring root privileges and enabling higher-levels of explainability, while achieving comparable or
even higher precision. Through experiments performed on 37 real-world applications on the
Java Virtual Machine (JVM), `VESTA` is capable of predicting energy consumption with a mean absolute
percentage error of 1.56\% while incurring a minimal performance and energy overhead.
```

# Table of Contents

- [Setup](#setup)
  - [RAPL](#rapl)
  - [bcc](#bcc)
  - [Java with DTrace](#java-with-dtrace)
- [Running with Docker](#running-with-docker)
- [Running from Source](#running-from-source)
- [Experiment Reproduction](#experiment-reproduction)
  - [Adding a custom benchmark](#adding-a-custom-benchmark)
- [Evaluation and Plots](#evaluation-and-plots)
  - [Modeling](#modeling)
  - [Accuracy Plot](#accuracy-plot)
  - [Overhead Plots](#overhead-plots)
  - [Line Graphs](#line-graphs)
  - [SHAP Plots](#shap-plots)
  - [Tree Visualizer](#tree-visualizer)

# Setup

In order to run the experiments (in a Docker image or otherwise), the host system must be Intel + Linux server and you must have `sudo` access in order to collect the data for the experiments. These steps **must** be done on the host system even if you are running through the Docker image. The experiments presented in the paper were run on the following system:

```
Dual socket Intel Xeon E5-3630 v4 2.20GHz (40 cores)
64GB DDR4 RAM
Debian 11
Linux kernel 5.17.0-3-amd64
```

Our experiments were evaluated on the [DaCapo](https://www.dacapobench.org) and [Renaissance](https://renaissance.dev) benchmark suites, which are collections of JVM applications tuned for server systems. All experiments took ~48 hours to run on the above system, which included both the baseline and the probing experiments that 256 iterations per benchmark each, the first 5 of which are discarded as warmup. To run the benchmarks effectively for this many iterations, we recommend having a CPU with at least 10 cores and at least 16GB or more of RAM. If your system's specifications are significantly less than this, or it is not a server class system, you may have some difficulty successfully running the experiments. In this case, we suggest reducing the number of iterations to 25 or 55 (this includes warmup iterations) to get sufficient data.

## RAPL

[RAPL](https://www.kernel.org/doc/html/next/power/powercap/powercap.html) is a feature for Intel CPUs that allows for sampling counters from the CPU that represent energy consumption since boot. RAPL requires the model-specific registers (`msr`s) to be enabled to allow sampling. For an Intel-Linux system, you will probably need to run `sudo modprobe msr` to enable it.

## bcc

[`bpf`](https://docs.kernel.org/bpf) and [`bcc`](https://github.com/iovisor/bcc) are a set of tools that allow for method profiling of applications. To use VESTA, they must be enabled on the host machine for `UDST` instrumentation even in the Docker image. You need to ensure that your kernel has the correct Linux headers enabled. In order to do this, check the contents of your system's `/proc/config.gz` for the flags that enable `bpf` (`CONFIG_BPF`, `CONFIG_BPF_SYSCALL`, `CONFIG_BPF_JIT`, `CONFIG_HAVE_EBPF_JIT`, `CONFIG_BPF_EVENTS`, `CONFIG_IKHEADERS`). These flags should be either set to `y` (for yes, meaning they have been included), `m` (for module, meaning they are available on demand), or are not explicitly present. If any of these flags are set to `n` (for no, meaning not included), then your kernel may need to be recompiled. The majority of Linux distributions have been compiled with all of necessary flags for `VESTA` included, so hopefully this will not be necessary.

Next, you need to modify the contents of your kernel configuration's boot file, which is found at `/boot/config` or `/boot/config-$(uname -r)` (where `$(uname -r)` will return the kernel version). This file determines which components are included in the kernel on system boot. You will need to modify the boot configuration by adding the `bpf` related flags set to `y` (or updating them to `y` if they are already present) so they will be included in the kernel. You can check the boot configuration with `cat /boot/config | grep -E "(BPF|IKHEADERS)"` or `cat /boot/config-$(uname -r) | grep -E "(BPF|IKHEADERS)"`. You should look for all of the following entries to be present and set to `y` (note that the order of the flags does not matter):

```
CONFIG_BPF=y
CONFIG_BPF_SYSCALL=y
CONFIG_BPF_JIT=y
CONFIG_HAVE_EBPF_JIT=y
CONFIG_BPF_EVENTS=y
CONFIG_IKHEADERS=y
```

If an entry is not present in the boot configuration, you should add it to `/boot/config` or `/boot/config-$(uname -r)` set to `y`.

Next, you will need to setup `bpf` and `bcc` for your distribution, which is listed in `bcc`'s [installation guide](https://github.com/iovisor/bcc/blob/master/INSTALL.md). For this process, you will need to install the kernel headers package, `bpf`, and `bcc` which is frequently available through your package manager. The specific packages will differ and can be found in the installation guide, but we provide the instructions here for ease:

```
# debian
echo deb http://cloudfront.debian.net/debian sid main >> /etc/apt/sources.list
sudo apt-get install -y bpfcc-tools libbpfcc libbpfcc-dev linux-headers-$(uname -r)

# ubuntu
sudo apt-get install bpfcc-tools linux-headers-$(uname -r)

# fedora 30 and higher
sudo dnf install bcc

# fedora 29 and lower
sudo dnf config-manager --add-repo=http://alt.fedoraproject.org/pub/alt/rawhide-kernel-nodebug/fedora-rawhide-kernel-nodebug.repo
sudo dnf update

# arch linux
pacman -S bcc bcc-tools python-bcc

# gentoo
emerge sys-kernel/gentoo-sources
emerge dev-util/bcc

# openSUSE
sudo zypper ref
sudo zypper in bcc-tools bcc-examples

# RHEL
yum install bcc-tools

# amazon linux 1
sudo yum update kernel
sudo yum install bcc
sudo reboot

# amazon linux 2
sudo amazon-linux-extras install BCC

# alpine
sudo apk add bcc-tools bcc-doc
```

Once you have done the two above steps, you will very likely need to reboot your system.

Finally, you may need to mount [`debugfs`](https://docs.kernel.org/filesystems/debugfs.html) which `bpf` uses to communicate between the user and kernel spaces. This is done using `mount -t debugfs none /sys/kernel/debug`. If you missed this step, you may see an error message like `open(/sys/kernel/debug/tracing/uprobe_events): No such file or directory` when running the experiments.

## Java with Dtrace

Finally, you will need a version of `java` with [`DTrace Probes`](https://docs.oracle.com/javase/8/docs/technotes/guides/vm/dtrace.html) enabled, which will expose the dtrace probes as `UDSTs` that can be instrumented with `bcc`. Our official repository contains a pre-built version of `openjdk-19` that was used to run our experiments. If you would like to use a different version or you are running this from the github repository, you need to re-compile from [source](https://github.com/openjdk/jdk/blob/master/doc/building.md) with the `--enable-dtrace` flag set.

# Running with Docker

We provide a Dockerfile in this repository that should correctly set up the environment to have access to both `msr` and `bpf` so you can run the experiments. You will need to run it with the following flags for everything to work:

```
sudo docker build . -t vesta
sudo docker run -it --rm  --privileged \
    -v /lib/modules:/lib/modules:ro \
    -v /sys/kernel/debug:/sys/kernel/debug:rw \
    -v /usr/src:/usr/src:ro \
    -v /etc/localtime:/etc/localtime:ro \
    vesta
```

NOTE: If you are trying to reproduce the experiments from the github repo, you will need to get the benchmark jars before building the Docker image, which can be done with `bash setup_benchmarks.sh`.

Once inside the image, you need to move to the `vesta` directory to set up and run the experiments.

# Running from Source

You can also reproduce our experiments directly from this repository. First you should install the following package on your system to support the experiments and modeling:

```
apt-get install -y git wget openjdk-11-jdk make \
    gcc maven bpftrace bpfcc-tools libbpfcc libbpfcc-dev \
    python3 python3-pip graphviz
pip3 install numpy pandas pytest numba xgboost scikit-learn shap
```
If you are not on Debian, your system's package manager likely has similar targets. Then you can download the repository, unpack it, and go into the repository's directory. Once in the directory, you can do the following steps to build the codebase:

1. run `bash setup_benchmarks.sh` to get the dependency benchmarks.

2. run `mvn clean install` to build a fat vesta `jar`.

3. run `make native` to build the native libraries used for runtime sampling.

# Experiment Reproduction

Once you've setup the codebase and are in the `vesta` root directory, you can use `bash scripts/my_fibonacci.sh` as a smoke test to confirm that you will be able to collect all the necessary data. This will run a very simple fibonacci workload with all profiling enabled, and process the energy and probing data into a single aligned timeline. After the program runs, you should see a dataframe printed to the console of the aligned data. In addition, a directory should be produced at `${PWD}/my-fibonacci` with the following files: `aligned.csv`, `energy.csv`, `probes.csv`, and `summary.csv`. Here is a snip of the expected output from `scripts/my_fibonacci.sh`:

```bash
/vesta# bash scripts/my_fibonacci.sh
bash scripts/my_fibonacci.sh
computed fib(45) in 7652 millis
ran fib(45) in 7671 +/- 56.4912 millis
aligning data for my-fibonacci
                       power  CallObjectMethod__entry  CallObjectMethod__return  SetByteArrayRegion__entry  SetByteArrayRegion__return
iteration ts                                                                                                                                                
6         1495958  24.859596                   1518.0                    1518.0                     1518.0                      1518.0
          1495959  25.174031                   1539.0                    1538.0                     1538.0                      1538.0
          1495960  25.597081                   1517.0                    1518.0                     1518.0                      1518.0
          1495961  25.490402                   1530.0                    1530.0                     1530.0                      1530.0
          1495962  25.577676                   1528.0                    1528.0                     1528.0                      1528.0
...                      ...                      ...                       ...                        ...                       ...
19        1496059  25.385899                   1546.0                    1546.0                     1546.0                      1546.0
          1496060  25.070887                   1560.0                    1560.0                     1560.0                      1560.0
          1496061  25.323372                   1534.0                    1534.0                     1534.0                      1534.0
          1496062  25.730467                   1538.0                    1538.0                     1538.0                      1538.0
          1496063  27.594447                   1546.0                    1546.0                     1546.0                      1546.0
```

Once the test completes successfully, you are ready to run the experiments.

## Experiment Definition

Our experiments are defined using a `json` file. The file should contain a list of dicts that define the parameters for the experiments:

```json
{
    "suite": "dacapo", // options: ["dacapo", "renaissance", "custom"]
    "benchmark": "avrora",
    "size": "default", // only necessary for "dacapo"
    "probes": "NewStringUTF__entry,NewStringUTF__return,SetByteArrayRegion__entry,SetByteArrayRegion__return,thread__park__begin,thread__park__end",
},
```

We provide some `json` files that contain the experiments used to produce our data. You can generate new experiment scripts by running `scripts/generate_experiments.py` with a `benchmarks.json`. This will create a directory containing the experiment driving code. The probes listed in `benchmark-configs/benchmarks.json` were selected during `VESTA`'s screening. You may add or remove probes from this list by consulting the full list of Java's [DTrace Probes](https://docs.oracle.com/javase/8/docs/technotes/guides/vm/dtrace.html); make sure that any instance of a hyphen (`-`) is replaced by two underscores (`__`) if you do add probes. There are two additional caveats regarding modifying the sampled probes:

1. As mentioned in the publication, unselected probes incurred significant overhead 
2. Language runtime events (LREs) are represented through a pair of probes with the same prefix but ending with `__entry`/`__return` and `__begin`/`__end`. If a given probe does not have its corresponding partner probe, then it will be modeled individually as a counter.

To do a full reproduction, first you'll need to build and run the baseline, i.e. executing the benchmarks with no probing:

```bash
python3 scripts/generate_experiments.py \
    --java_path=dtrace-jdk/bin/java \
    --iters=256 \
    --exp_path="${PWD}/baseline" \
    --benchmarks="${PWD}/benchmark-configs/baseline.json"
bash scripts/run_experiments.sh "${PWD}/baseline"
```

Then do the same with the probing enabled:

```bash
python3 scripts/generate_experiments.py \
    --java_path=dtrace-jdk/bin/java \
    --iters=256 \
    --exp_path="${PWD}/data" \
    --benchmarks="${PWD}/benchmark-configs/benchmarks.json"
bash scripts/run_experiments.sh "${PWD}/data"
```

NOTE: If you are running this from outside of the Docker image, make sure that you execute `scripts/run_experiments` as sudo (`sudo bash scripts/run_experiments.sh "${PWD}/data"`)

## Adding a custom benchmark

VESTA supports the addition of new Java benchmarks that can be run either standalone or as part of an experiment.

### Creating a Java Benchmark

You can add your Java program to this repository (preferably at `src/main/java/vesta`) and use the `vesta.SampleCollector` in your program to add energy data collection:

```java
package vesta;

final class MyFibonacci {
    int fib(int n) { ...}

    public static void main(String[] args) {
        int iterations = Integer.parseInt(args[0]);
        SampleCollector collector = new SampleCollector();
        for (int i = 0; i < iterations; i++) {
            collector.start();
            fib(42);
            collector.stop();
        }
        collector.dump();
    }
}
```

Next, recompile the tool with `mvn package`; if you have third-party dependencies, you should add them to the `pom.xml`. You should be able to directly run your benchmark from the newly built jar:

```bash
OUT_DIR="${PWD}/my-fibonacci"
dtrace-jdk/bin/java -cp "${PWD}/target/vesta-0.1.0-jar-with-dependencies.jar" \
    -Dvesta.output.directory="${OUT_DIR}" \
    -Dvesta.library.path="${PWD}/bin" \
    vesta.MyFibonacci 50
```

The above command will produce `${PWD}/my-fibonacci/summary.csv`, which contains end-to-end measurements of energy and runtime, and `${PWD}/my-fibonacci/energy.csv`, which contains timestamped measurements` of energy.

### BPF Probing

Next, you can do bpf probing by calling the `scripts/java_multi_probe.py` script on your executing Java program:

```bash
pid=$!
OUT_DIR="${PWD}/my-fibonacci"
PROBES=NewStringUTF__entry,NewStringUTF__return,SetByteArrayRegion__entry,SetByteArrayRegion__return,thread__park__begin,thread__park__end
python3 "${PWD}/scripts/java_multi_probe.py" --pid "${pid}" \
    --output_directory="${OUT_DIR}" \
    --probes="${PROBES}"
```

This will produce a `${PWD}/my-fibonacci/probes.csv` file containing the probing information.

### Including the custom benchmark in an experiment

Before adding your custom benchmark to an experiment, you may want to execute the benchmark as a sanity test with a small script:

```bash
OUT_DIR="${PWD}/my-fibonacci"
PROBES=NewStringUTF__entry,NewStringUTF__return,SetByteArrayRegion__entry,SetByteArrayRegion__return,thread__park__begin,thread__park__end
dtrace-jdk/bin/java -cp "${PWD}/target/vesta-0.1.0-jar-with-dependencies.jar" \
    -Dvesta.output.directory="${OUT_DIR}" \
    -Dvesta.library.path="${PWD}/bin" \
    vesta.MyFibonacci 50 &
pid=$! # retrieve last process pid
python3 "${PWD}/scripts/java_multi_probe.py" --pid "${pid}" \
    --output_directory="${OUT_DIR}" \
    --probes="${PROBES}"
```

The smoke testing script at `scripts/my_fibonacci.sh` can be used a template: you can copy and modify it to produce a new smoke test. If the three data files (`energy.csv`, `probes.csv`, `summary.csv`) are present and you can successfully run `scripts/single-alignment.py` on the new directory, then your benchmark has been integrated with `VESTA`'s driver. You can then add your benchmark to a `benchmarks.json` file as a `"custom"` suite:

```json
{
    "suite": "custom",  
    "benchmark": "my-fibonacci",
    "main_class": "vesta.MyFibonacci",
    "args": "42 {iters}",
    "probes": "NewStringUTF__entry,NewStringUTF__return,SetByteArrayRegion__entry,SetByteArrayRegion__return,thread__park__begin,thread__park__end",
}
````

Now you can follow the steps in the [experiment reproduction](#experiments-reproduction) to run your benchmark as part of an experiment.

# Evaluation and Plots

## Modeling

The data can be pre-processed into an aligned time-series with `scripts/alignment.py`:

```bash
python3 scripts/alignment.py \
    --out_file_name="${PWD}/data/aligned.csv" \
    --bucket=1000 \
    --warm_up=5 \
    data
```

Modeling is done with the `scripts/model_builder.py`:

```bash
python3 scripts/model_builder.py \
    --out_path="${PWD}/data" \
    --name=vesta-artifact \
    "${PWD}/data/aligned.csv"
```

The model, training, and testing data will all be used for producing plots which can be used to learn about how the tracked runtime events affect power consumption.


## Accuracy Plot

This script replicates Fig. 5 which shows the MAPE for a set of benchmarks.

The structure for calling the script is as follows: `python3 scripts/inference.py <model json> <testing data csv> --out_path=<location and name of pdf to create>`

The graph can be created with the following:

```bash
python3 scripts/inference.py \
    --out_path="${PWD}/data/vesta-artifact_inference.pdf" \
    "${PWD}/data/vesta-artifact.json" \
    "${PWD}/data/vesta-artifact_test.csv"
```

## Overhead Plots

This script replicates Figs. 8-9 which show the wall-clock time and energy overhead for VESTA, respectively. (Note: this does not create the ref-cycle overhead. As of right now it's a bit more involved to get that working in the general case.)

The structure for calling the script is as follows: `python3 scripts/overhead.py <path to directory that has the test data> <path to directory that has the baseline data> --output_directory=<location of where to put overhead pdfs>`

The graph can be created with the following:

```bash
python3 scripts/overhead.py \
    --output_directory="${PWD}/data" \
    "${PWD}/data" \
    "${PWD}/baseline"
```


## Line Graphs

This script replicates Figs. 6-7 which show the ground power truth alongside predicted power.

The structure for calling the script is as follows: `python3 scripts/xgboost_ground-truth_graphs.py <model json> <testing data csv> --output_directory=<path to directory where pdfs will be stored>`

The graphs can be created with the following:

```bash
python3 scripts/xgboost_ground-truth_graphs.py \
    --output_directory="${PWD}/data" \
    "${PWD}/data/vesta-artifact.json" \
    "${PWD}/data/vesta-artifact_test.csv"
```
It will create as many graphs as there are benchmarks in the testing data.

## SHAP Plots

This script will create Figs. 10a, 10b, 11

The structure for calling the script is as follows: `python3 scripts/shap_graphs.py <model json> <training data csv> --output_directory=<path to directory where pdfs will be stored>`

The graphs can be created with the following:

```bash
python3 scripts/shap_graphs.py \
    --output_directory="${PWD}/data" \
    "${PWD}/data/vesta-artifact.json" \
    "${PWD}/data/vesta-artifact_train.csv"
```

Currently, this will make 1 feature importance bar graph, 1 feature importance violin graph (with all features), and n number of SHAP scatter plots where n is the number of features.

## Tree Visualizer

This script will replicate the visualizer graph shown in Fig. 13.

The structure for calling the script is as follows: `python3 scripts/tree_visualizer.py <model json> <training data csv> <testing data csv> <index> --output_directory=<path to directory where pdfs will be stored>`

Assuming you would like to view the prediction path from the 1000th datapoint in the testing data, the graphs can be created with the following:

```bash
python3 scripts/tree_visualizer.py \
    --output_directory="${PWD}/data" \
    "${PWD}/data/vesta-artifact.json" \
    "${PWD}/data/vesta-artifact_train.csv" \
    "${PWD}/data/vesta-artifact_test.csv" \
    1000
```

This will create a svg (the only format supported by dtreeviz). If you would like a pdf you can use `rsvg-convert` to convert the output:
```bash
rsvg-convert -f pdf -o "${PWD}/data/prediction.pdf" "${PWD}/data/prediction.svg"
```
