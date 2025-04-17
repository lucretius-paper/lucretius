# `LucRETius`

LucRETius is a power modeling system that uses *language runtime events* for prediction. Below is the abstract for the publication.

```

Developing energy-aware applications is an important approach to promoting sustainable computing. This paper addresses a fundamental and challenging problem faced by developers and deployers: how to port a power model built for one machine to another? We present LucRETius, a novel approach toward portable power modeling through transfer learning, where a pre-trained power model on one machine can serve as a teacher to help construct a student model on another machine rapidly. The key insight that enables transfer learning is that the layer of application runtimes can abstract away the machine-specific details, so that two machines—despite different hardware and software system configurations—are unified with a common set of runtime events that can serve as features for transfer learning. We evaluate LucRETius through bi-directional transfers across 4 machines, and we show the power models built by LucRETius have a median percentage error of 1.01%-1.75% when used for predicting the energy consumption of 36 real-world JVM-based applications. Compared with training from scratch, LucRETius can lead to a speed up of 8.07×.

```

# Table of Contents

- [Setup](#setup)
  - [RAPL](#rapl)
  - [PowerCap](#powercap)
  - [bcc](#bcc)
  - [Java with DTrace](#java-with-dtrace)
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

In order to run the experiments (in a Docker image or otherwise), the host system must be an Intel + Linux or AMD + Linux server and you must have `sudo` access in order to collect the data for the experiments. These steps **must** be done on the host system even if you are running through the Docker image. The experiments presented in the paper were run on the following system:

```
Machine A

&
Machine B
Dual socket Intel Xeon E5-3630 v4 2.20GHz (40 cores)
64GB DDR4 RAM
Debian 11
Linux kernel 5.17.0-3-amd64

&
Machine C

&
Machine D

```

Our experiments were evaluated on the [DaCapo](https://www.dacapobench.org) and [Renaissance](https://renaissance.dev) benchmark suites, which are collections of JVM applications tuned for server systems. All experiments took ~X hours to run on the above system, although the time varies considering the dynamic nature of the training. To run the benchmarks effectively, we recommend having a CPU with at least 10 cores and at least 16GB or more of RAM. If your system's specifications are significantly less than this, or it is not a server class system, you may have some difficulty successfully running the experiments.

## RAPL

[RAPL](https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/advisory-guidance/running-average-power-limit-energy-reporting.html) is a feature for Intel CPUs that allows for sampling counters from the CPU that represent energy consumption since boot. RAPL requires the model-specific registers (`msr`s) to be enabled to allow sampling. For an Intel-Linux system, you will probably need to run `sudo modprobe msr` to enable it.

## PowerCap
[PowerCap](https://www.kernel.org/doc/html/next/power/powercap/powercap.html) is a framework that provides a user-space interface for communicating with the kernel and its access to power capping drivers. PowerCap relies on the system's ability to report energy consumption and will require the `msr`s to be enabled.

## bcc

[`bpf`](https://docs.kernel.org/bpf) and [`bcc`](https://github.com/iovisor/bcc) are a set of tools that allow for method profiling of applications. To use `LucRETius`, they must be enabled on the host machine for `UDST` instrumentation even in the Docker image. You need to ensure that your kernel has the correct Linux headers enabled. In order to do this, check the contents of your system's `/proc/config.gz` for the flags that enable `bpf` (`CONFIG_BPF`, `CONFIG_BPF_SYSCALL`, `CONFIG_BPF_JIT`, `CONFIG_HAVE_EBPF_JIT`, `CONFIG_BPF_EVENTS`, `CONFIG_IKHEADERS`). These flags should be either set to `y` (for yes, meaning they have been included), `m` (for module, meaning they are available on demand), or are not explicitly present. If any of these flags are set to `n` (for no, meaning not included), then your kernel may need to be recompiled. The majority of Linux distributions have been compiled with all of necessary flags for `LucRETius` included, so hopefully this will not be necessary.

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

# Running from Source

You can also reproduce our experiments directly from this repository. First you should install the following package on your system to support the experiments and modeling:

```
apt-get install -y git wget openjdk-11-jdk make \
    gcc maven bpftrace bpfcc-tools libbpfcc libbpfcc-dev \
    python3 python3-pip graphviz
pip3 install numpy pandas pytest numba xgboost scikit-learn shap protobuf grpcio
```
If you are not on Debian, your system's package manager likely has similar targets. Then you can download the repository, unpack it, and go into the repository's directory. Once in the directory, you can do the following steps to build the codebase:

1. run `bash setup_benchmarks.sh` to get the dependency benchmarks.

2. run `bazel build lucretius_deploy.jar` to build a fat lucretius `jar`.

3. run `make native` to build the native libraries used for runtime sampling.

# Experiment Reproduction

Once you've setup the codebase and are in the `lucretius` root directory, you can use `bash scripts/my_fibonacci.sh /path/to/DTrace/java` (as a reminder, you must have sudo privileges to run bcc) as a smoke test to confirm that you will be able to collect all the necessary data. This will set up a very simple fibonacci workload with all profiling enabled, and process the energy and probing data into a single aligned timeline. After the script runs, you'll find a folder `${PWD}/my-fibonacci` which will contain a `start_server.sh` and `start_clients.sh`. (You'll need to run the server and client in two different windows.) After doing so, you should see the following files in `${PWD}/my-fibonacci`: `ratios.csv`, `sizes.json`, `model.json`, `testing.csv`, and `training.csv`. You will also find a folder `${PWD}/my-fibonacci/fibonacci` with the following files: `energy_*.csv`, `probes_*.csv`, and `summary.csv` (the number of energy and probes file will vary based on the dynamic learning results).

```bash
#In one window
bash ./start_server.sh

#In another window
bash ./start_clients.sh
```

Once the test completes successfully, you are ready to run the experiments.

## Experiment Definition

Our experiments are defined using a `json` file. The file should contain a json object representing server configs and a list of dicts that define the parameters for the client connections:

```json
{
    "server": 
		{"probes": "thread__park__begin,thread__park__end,vmops__begin,vmops__end",
	     "transfer": "Y", // only needed if performing a transfer...for dynamic original training it should be omitted
		 "jrapl": "Y" // only needed if using jRAPL...for PowerCap system it should be omitted
	    },
    "client":
    [
		{
			"suite": "dacapo", // options: ["dacapo", "renaissance", "custom"]
			"benchmark": "sunflow",
			"size": "default" // only necessary for "dacapo"
		},
		{
			"suite": "renaissance",
			"benchmark": "dec-tree"
		},
		{
			"suite": "custom",
			"benchmark": "my-fibonacci",
			"main_class": "lucretius.MyFibonacci",
			"args": "42 {iters}"
		}
	]
}
```

We provide some `json` files that contain the experiments used to produce our data. You can generate new experiment scripts by running `scripts/generate_experiments.py` with a `server-config.json`. This will create a directory containing the experiment driving code. The probes listed in `server-configs/lucretius_all_benchmarks.json` were used in the `VESTA` paper. You may add or remove probes from this list by consulting the full list of Java's [DTrace Probes](https://docs.oracle.com/javase/8/docs/technotes/guides/vm/dtrace.html); make sure that any instance of a hyphen (`-`) is replaced by two underscores (`__`) if you do add probes. There are two additional caveats regarding modifying the sampled probes:

1. As mentioned in the publication, unselected probes incurred significant overhead 
2. Language runtime events (LREs) are represented through a pair of probes with the same prefix but ending with `__entry`/`__return` and `__begin`/`__end`. If a given probe does not have its corresponding partner probe, then it will be modeled individually as a counter.

To do a full reproduction, first you'll need to build and run the baseline, i.e. executing the benchmarks with no probing:

```bash
python3 scripts/generate_experiments.py \
    -java_path /path/to/the/USDT-enabled/java \ 
	-server_config server-configs/server-config.json \
	-exp_path $PWD/path/to/experiment/dir/ \
	-target $PWD/path/to/original/data/dir/
```

The `target` folder needs to contain a `ratios.csv` file which will need to contain data for all of the benchmarks you plan on running. For example, if you wanted to run `LuCREtius` with the `server-configs/lucretius_dynamic_original_example.json` file:
```
	benchmark,mean
	my-fibonacci,0.10
	sunflow,0.10
	dec-tree,0.10
```
Each benchmark will run until all three meet the 10% threshold. If you want to run a transfer then you'll also need a `sizes.json` file and a `model.json` file (which will be generated for you if you train a dynamic original model).

You can then navigate to the folder given for `exp_path` and you'll find a directory which contains a folder for each application given with `server_config` and two bash scripts for running `LucRETius`: `run_server.sh` and `run_clients.sh`. You'll need to run these in two separate bash instances, so we recommend using a window management system like ![screen](https://www.gnu.org/software/screen/manual/screen.htmlhttps://www.gnu.org/software/screen/manual/screen.html). Once you have a screen (or a separate bash instance) running for the `server` and the `clients` you can run the system with:

```bash
	bash run_server.sh
```
and
```bash
	bash run_clients.sh
```

`run_server.sh` will spin up the `LucRETius` server and `run_clients.sh` will start each application one by one and connect them to the server. Once all clients have been connected you can start `LucRETius` by hitting enter while on the server window.

NOTE: If you are running this from outside of a Docker image, make sure that you execute `scripts/run_experiments` as sudo (`sudo bash scripts/run_experiments.sh "${PWD}/data"`)

## Adding a custom benchmark

`LucRETius` supports the addition of new Java benchmarks that can be run either standalone or as part of an experiment.

### Creating a Java Benchmark

You can add your Java program to this repository (preferably at `src/main/java/lucretius`) and use the `lucretius.RaplSampleCollector` or `lucretius.PowercapSampleCollector` in your program to add energy data collection. You'll also need to use the static class lucretius.Lucretius to connect to and communicate with the server:

```java
package lucretius;

final class MyFibonacci {
    int fib(int n) { ...}

    public static void main(String[] args) {
		Lucretius.connect("my-fibonacci"); //Connects to the server
        int iterations = Integer.parseInt(args[0]);
		SampleCollector collector = new RaplSampleCollector();
        while(Lucretius.startRequest()){ //Waits to hear from the server to start
            collector.start();
            fib(42);
            collector.stop();
			collector.write_iter();
			Lucretius.finishedNotification(); //Notifies the server it has completed an iteration
        }
        collector.dump();
		Lucretius.finishedNotification(); //Notifies the server that it has finished shutting down
    }
}
```

Next, recompile the tool with `bazel build lucretius_deploy.jar`; if you have third-party dependencies, you should add them to the relevant `MODULE` and `BUILD` files. You should be able to directly run your benchmark from the newly built jar. Once you've done so you can add another `custom` client to your `server-config.json` file and generate experiments as outlined [here](#experiment-reproduction).

# Evaluation and Plots

## Modeling

A full run of `LucRETius` will produce
	- a trained `XGBoost` model in the experiment directory: `model.json`
	- a list of model accuracies per application: `ratios.csv`
	- a list of iterations per application: `sizes.json`
	- aligned data used for training: `training.csv`
	- aligned data used for testing: `testing.csv`

## Accuracy Plot

## Overhead Plots


## Line Graphs


## SHAP Plots

## Tree Visualizer
