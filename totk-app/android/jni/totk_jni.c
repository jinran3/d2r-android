// JNI 桥：只做转发，不放逻辑（逻辑在 core/）。
// JNI bridge: forwarding only, no logic here (the logic lives in core/).
#include <jni.h>
#include <stdlib.h>

extern char *totk_selfcheck(const char *dir);

JNIEXPORT jstring JNICALL
Java_org_totk_android_port_MainActivity_selfCheck(JNIEnv *env, jclass cls, jstring jdir) {
    (void)cls;
    const char *dir = (*env)->GetStringUTFChars(env, jdir, NULL);
    char *report = dir ? totk_selfcheck(dir) : NULL;
    if (dir) (*env)->ReleaseStringUTFChars(env, jdir, dir);
    jstring out = (*env)->NewStringUTF(env, report ? report : "selfcheck: no report");
    free(report);
    return out;
}
