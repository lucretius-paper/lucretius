FROM debian:bullseye-slim

# setup system dependencies
RUN apt-get update && apt-get install -y --fix-missing git wget openjdk-11-jdk make gcc graphviz librsvg2-bin screen && apt-get -y upgrade
RUN wget https://github.com/bazelbuild/bazelisk/releases/download/v1.26.0/bazelisk-amd64.deb && apt-get install ./bazelisk-amd64.deb && rm ./bazelisk-amd64.deb


# setup bpf probing
RUN apt-get install -y python3 python3-pip
RUN apt-get install -y bpftrace bpfcc-tools libbpfcc libbpfcc-dev
RUN pip3 install numpy pandas pytest numba xgboost sklearn matplotlib shap dtreeviz grpcio grpcio-tools


# setup dtrace java
RUN git clone https://github.com/lucretius-paper/lucretius.git
COPY dtrace-jdk.tar.gz lucretius/.
RUN cd lucretius && tar -xzvf dtrace-jdk.tar.gz && rm dtrace-jdk.tar.gz
ENV DTRACE_JAVA=/lucretius/dtrace-jdk/bin/java

# setup java code
COPY lib lucretius/lib
RUN cd lucretius && bash setup_benchmarks.sh
RUN cd lucretius && make native && make proto -d
RUN useradd -ms /bin/bash epicurus
RUN chmod 777 /lucretius/
    # bazel requires a non-root user to build
USER epicurus
RUN cd lucretius && bazel build lucretius_deploy.jar
User root

# setup screen environment aliases
RUN echo 'alias create_client="screen -dmS client -s bash"' >> /etc/bash.bashrc 
RUN echo 'alias create_server="screen -dmS server -s bash"' >> /etc/bash.bashrc 
RUN echo 'alias join_client="screen -r client"' >> /etc/bash.bashrc
RUN echo 'alias join_server="screen -r server"' >> /etc/bash.bashrc

ENTRYPOINT cd lucretius && /bin/bash && screen -dmS client && screen -dmS server
