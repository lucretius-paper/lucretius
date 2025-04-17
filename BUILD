java_import(
    name = "benchmarks",
    jars = [
        "lib/renaissance-gpl-0.14.1.jar",
        "lib/dacapo.jar",
    ],
)

java_binary(
    name = "lucretius",
    srcs = glob(["src/main/java/lucretius/*.java"]),
    main_class = "lucretius.Lucretius",
    runtime_deps = ["@grpc-java//netty"],
    deps = ["//:benchmarks","//src/main/proto/lucretius:lucretius_service_java_protos", "@grpc-java//api", "//src/main/proto/lucretius:lucretius_service_java_grpc"],
)
