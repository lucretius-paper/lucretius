CC = gcc
CFLAGS = -fPIC -g

SOURCES = src
RAPL_SOURCES = $(SOURCES)/arch_spec.o $(SOURCES)/msr.o $(SOURCES)/rapl.o
TARGET = bin

JAVA_HOME = $(shell readlink -f /usr/bin/javac | sed "s:bin/javac::")
JAVA_INCLUDE = $(JAVA_HOME)include
JAVA_LINUX_INCLUDE = $(JAVA_INCLUDE)/linux
JNI_INCLUDE = -I$(JAVA_INCLUDE) -I$(JAVA_LINUX_INCLUDE)

JAVAC=javac
JAVA_CLASSPATH = lib/dacapo.jar:lib/renaissance-gpl-0.11.0.jar

PYTHON_SERVER_DIR = ./server/
.PHONY: %.o %.class
%.o: %.c
	$(CC) -c -o $@ $^ $(CFLAGS) $(JNI_INCLUDE)

%.class: %.java
	$(JAVAC) -cp $(JAVA_CLASSPATH) $^ -d .


libMonotonic.so: $(SOURCES)/monotonic_timestamp.o
	mkdir -p $(TARGET)
	$(CC) -shared -Wl,-soname,$@ -o $(TARGET)/$@ $^ $(JNI_INCLUDE) -lc
	rm -f $^

libRapl.so: $(RAPL_SOURCES)
	mkdir -p $(TARGET)
	$(CC) -shared -Wl,-soname,$@ -o $(TARGET)/$@ $^ $(JNI_INCLUDE) -lc
	rm -f $^

native: libRapl.so libMonotonic.so
	@echo 'built native libraries'

proto:	server/lucretius_service.proto
	python3 -m grpc_tools.protoc -I$(PYTHON_SERVER_DIR) --python_out=$(PYTHON_SERVER_DIR) --pyi_out=$(PYTHON_SERVER_DIR) --grpc_python_out=$(PYTHON_SERVER_DIR) $(PYTHON_SERVER_DIR)lucretius_service.proto

clean:
	rm -r $(TARGET) ./server/lucretius_service*.py*

get_java_deps:
	mkdir -p lib
	wget https://sourceforge.net/projects/dacapobench/files/evaluation/dacapo-evaluation-git%2B309e1fa.jar/download
	mv download lib/dacapo.jar
	wget https://github.com/renaissance-benchmarks/renaissance/releases/download/v0.14.1/renaissance-gpl-0.14.1.jar
	mv renaissance-gpl-0.14.1.jar lib/renaissance-gpl-0.14.1.jar
