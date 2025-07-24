FROM debian:bullseye-slim

# setup
RUN apt-get update && apt-get install -y --fix-missing git wget openjdk-11-jdk make gcc graphviz librsvg2-bin screen && apt-get -y upgrade
RUN wget https://github.com/bazelbuild/bazelisk/releases/download/v1.26.0/bazelisk-amd64.deb && apt-get install ./bazelisk-amd64.deb && rm ./bazelisk-amd64.deb


# setup bpf probing
RUN apt-get install -y python3 python3-pip
RUN apt-get install -y bpftrace bpfcc-tools libbpfcc libbpfcc-dev
RUN pip3 install numpy pandas pytest numba xgboost sklearn matplotlib shap dtreeviz grpcio grpcio-tools


RUN git clone https://github.com/lucretius-paper/lucretius.git
COPY dtrace-jdk.tar.gz lucretius/.
RUN cd lucretius && tar -xzvf dtrace-jdk.tar.gz && rm dtrace-jdk.tar.gz

# setup java code
COPY lib lucretius/lib
RUN cd lucretius && bash setup_benchmarks.sh
RUN cd lucretius && make native && make proto -d

RUN useradd -ms /bin/bash epicurus
RUN chmod 777 /lucretius/
USER epicurus
RUN cd lucretius && bazel build lucretius_deploy.jar
User root

ENTRYPOINT cd lucretius && /bin/bash
