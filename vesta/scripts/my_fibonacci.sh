OUT_DIR="${PWD}/my-fibonacci"
mkdir "${OUT_DIR}"

PROBES=CallObjectMethod__entry,CallObjectMethod__return,CallVoidMethod__entry,CallVoidMethod__return,DestroyJavaVM__entry,DestroyJavaVM__return,GetByteArrayElements__entry,GetByteArrayElements__return,GetEnv__entry,GetEnv__return,GetFloatField__entry,GetFloatField__return,GetLongField__entry,GetLongField__return,GetMethodID__entry,GetMethodID__return,GetObjectArrayElement__entry,GetObjectArrayElement__return,GetObjectClass__entry,GetObjectClass__return,GetStringLength__entry,GetStringLength__return,IsInstanceOf__entry,IsInstanceOf__return,NewDirectByteBuffer__entry,NewDirectByteBuffer__return,NewLongArray__entry,NewLongArray__return,NewString__entry,NewString__return,NewStringUTF__entry,NewStringUTF__return,ReleaseIntArrayElements__entry,ReleaseIntArrayElements__return,ReleaseShortArrayElements__entry,ReleaseShortArrayElements__return,SetByteArrayRegion__entry,SetByteArrayRegion__return,SetIntField__entry,SetIntField__return,Throw__entry,Throw__return,class__initialization__concurrent,class__initialization__error,class__unloaded,compiled__method__load,compiled__method__unload,gc__begin,gc__end,method__compile__begin,method__compile__end,safepoint__begin,safepoint__end,thread__park__begin,thread__park__end,thread__sleep__begin,thread__sleep__end,vmops__begin,vmops__end

dtrace-jdk/bin/java -cp "${PWD}/target/vesta-0.1.0-jar-with-dependencies.jar" \
    -Dvesta.output.directory="${OUT_DIR}" \
    -Dvesta.library.path="${PWD}/bin" \
    vesta.MyFibonacci 45 20 &
pid=$!
python3 "${PWD}/scripts/java_multi_probe.py" --pid "${pid}" \
    --output_directory="${OUT_DIR}" \
    --probes="${PROBES}"

python3 "${PWD}/scripts/single-alignment.py" \
    --out_file_name="${OUT_DIR}/aligned.csv" \
    --bucket=1000 \
    --warm_up=5 \
    "${OUT_DIR}"
