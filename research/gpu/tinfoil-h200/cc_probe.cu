// cc_probe: one look at what the GPU allows for host memory before any proof runs.
// Prints one JSON object. Under NVIDIA confidential computing (CC-On), NVIDIA's Trusted Computing
// release notes (r580, "Limitations in the SPT CC and PPCIe Modes") list cudaHostRegister as not
// allowed; cudaHostAlloc is expected to work through the encrypted bounce buffer. The default build's
// cp_commit and cp_prove use cudaHostRegister, so this probe predicts whether they can start.
// It also times one 1 GiB host-to-device copy from cudaHostAlloc memory (descriptive, n = 3).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <cuda_runtime.h>

static double copy_gibps(void *host, void *dev, size_t bytes) {
  cudaDeviceSynchronize();
  auto t0 = std::chrono::steady_clock::now();
  if (cudaMemcpy(dev, host, bytes, cudaMemcpyHostToDevice) != cudaSuccess) return -1;
  cudaDeviceSynchronize();
  double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  return bytes / s / (1024.0 * 1024 * 1024);
}

int main() {
  const size_t small = (size_t)64 << 20, big = (size_t)1 << 30;
  cudaDeviceProp p{};
  cudaError_t e = cudaGetDeviceProperties(&p, 0);
  if (e != cudaSuccess) {
    printf("{\"error\": \"%s\"}\n", cudaGetErrorString(e));
    return 2;
  }
  int reg_supported = -1;
  cudaDeviceGetAttribute(&reg_supported, cudaDevAttrHostRegisterSupported, 0);

  void *plain = aligned_alloc(2 << 20, small);
  memset(plain, 0, small);
  cudaError_t reg = cudaHostRegister(plain, small, cudaHostRegisterDefault);
  if (reg == cudaSuccess) cudaHostUnregister(plain);
  cudaGetLastError(); // a refused registration is not sticky (reported); clear it anyway
  free(plain);

  void *pinned = nullptr, *dev = nullptr;
  cudaError_t alloc = cudaHostAlloc(&pinned, big, cudaHostAllocDefault);
  double rates[3] = {-1, -1, -1};
  if (alloc == cudaSuccess && cudaMalloc(&dev, big) == cudaSuccess) {
    memset(pinned, 1, big);
    for (double &r : rates) r = copy_gibps(pinned, dev, big);
  }
  if (dev) cudaFree(dev);
  if (pinned) cudaFreeHost(pinned);

  printf("{\"device\": \"%s\", \"cc\": \"%d.%d\", \"total_mem_bytes\": %zu, "
         "\"attr_host_register_supported\": %d, "
         "\"cudaHostRegister\": {\"code\": %d, \"name\": \"%s\"}, "
         "\"cudaHostAlloc\": {\"code\": %d, \"name\": \"%s\"}, "
         "\"h2d_gibps_from_hostalloc_1GiB\": [%.3f, %.3f, %.3f]}\n",
         p.name, p.major, p.minor, (size_t)p.totalGlobalMem, reg_supported, (int)reg, cudaGetErrorName(reg),
         (int)alloc, cudaGetErrorName(alloc), rates[0], rates[1], rates[2]);
  return 0;
}
