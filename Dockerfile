FROM debian:bullseye-slim

# setup
RUN apt-get update && apt-get install -y --fix-missing git wget openjdk-11-jdk make gcc bazel graphviz librsvg2-bin && apt-get -y upgrade
RUN git clone https://github.com/lucretius-paper/lucretius.git

# setup java code
COPY lib lucretius/lib
RUN cd lucretius && bash setup_benchmarks.sh
RUN cd lucretius && bazel build lucretius_deploy.jar
RUN cd lucretius && make native

# setup bpf probing
COPY dtrace-jdk.tar.gz lucretius/.
RUN cd lucretius && tar -xzvf dtrace-jdk.tar.gz
RUN apt-get install -y bpftrace bpfcc-tools libbpfcc libbpfcc-dev
RUN apt-get install -y python3 python3-pip
RUN cd lucretius && pip3 install numpy pandas pytest numba xgboost sklearn matplotlib shap dtreeviz

