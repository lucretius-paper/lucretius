#include <jni.h>

#ifndef _Included_vesta_MonotonicTimestamp
#define _Included_vesta_MonotonicTimestamp
#ifdef __cplusplus
extern "C" {
#endif

JNIEXPORT jlong JNICALL Java_vesta_MonotonicTimestamp_getMonotonicTimestamp
  (JNIEnv *, jclass);

#ifdef __cplusplus
}
#endif
#endif
