load("@protobuf//bazel:java_proto_library.bzl", "java_proto_library")
load("@grpc-java//:java_grpc_library.bzl", "java_grpc_library")

proto_library(
    name = "lucretius_service_protos",
    visibility = ["//visibility:public"],
    srcs = ["lucretius_service.proto"],
)

java_proto_library(
    name = "lucretius_service_java_protos",
    visibility = ["//visibility:public"],
    deps = [":lucretius_service_protos"],
)

java_grpc_library(
    name = "lucretius_service_java_grpc",
    visibility = ["//visibility:public"],
    srcs = [":lucretius_service_protos"],
    deps = [":lucretius_service_java_protos"]
)
