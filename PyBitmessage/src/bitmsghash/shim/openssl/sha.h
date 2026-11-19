/*
 * Minimal OpenSSL-compatible SHA-512 surface, sufficient for bitmsghash.cpp.
 * Used on Android (and any platform without libcrypto headers) so the PoW
 * module can be built with the NDK alone.
 */
#ifndef BITMESSAGE_SHIM_SHA512_H
#define BITMESSAGE_SHIM_SHA512_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SHA512_DIGEST_LENGTH 64

typedef struct {
    uint64_t h[8];
    uint64_t total;          /* bytes processed so far */
    unsigned char buf[128];
    size_t buflen;
} SHA512_CTX;

int SHA512_Init(SHA512_CTX *ctx);
int SHA512_Update(SHA512_CTX *ctx, const void *data, size_t len);
int SHA512_Final(unsigned char *md, SHA512_CTX *ctx);

#ifdef __cplusplus
}
#endif

#endif
