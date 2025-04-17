#include <jni.h>

#ifndef _Included_lucretius_MonotonicTimestamp
#define _Included_lucretius_MonotonicTimestamp
#ifdef __cplusplus
extern "C" {
#endif

JNIEXPORT jlong JNICALL Java_lucretius_MonotonicTimestamp_getMonotonicTimestamp
  (JNIEnv *, jclass);

#ifdef __cplusplus
}
#endif
#endif
