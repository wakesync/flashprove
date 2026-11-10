# FlashProve prover image for one H200 in a Tinfoil enclave. Untested draft: partly built (stages
# `toolkit`, `source` and `verifier`, see README.md); the `prover` and `final` stages have NOT been
# built, and nothing has been published.
#
# NOT REPRODUCIBLE YET: the Ubuntu apt packages below are neither version-pinned nor taken from a
# snapshot, so a later rebuild can install different versions. The base image, the CUDA wheels, the
# driver stub and the source commit are pinned. What apt installed is recorded in /opt/env/dpkg.txt
# (phase 1's copy: experiments/20261110-43-h200-bringup/runs/image-dpkg.txt). Pinning them (for
# example to snapshot.ubuntu.com at a fixed date) is open work; it changes the toolkit stage and so
# needs a rebuild and new receipts.
#
# Build context: this directory (research/gpu/tinfoil-h200/).
#   docker build -t fp-h200-prover .                     # whole image, about half an hour of compiling
#   docker build --target verifier -t fp-h200-verifier .  # toolkit + cp_verify only, a few minutes
#
# The prover is built from the same pinned commit as the H100 receipts (research/gpu/README.md), with
# the same toolkit wheels (requirements-cuda.txt), so that the H200 numbers are comparable. The build
# needs no GPU: without one, prover/build.sh checks the compiler's version only, and the GPU check by
# value (compiler_sample) is run on the H200 by run_job.sh before any proof.

# ---- stage toolkit: OS packages and CUDA 13.2 Update 2 (nvcc 13.2.86) -----------------------------
FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852 AS toolkit
ARG DEBIAN_FRONTEND=noninteractive
# gcc/g++ 13 (Ubuntu 24.04's default, 13.3), python3, binutils, flock (util-linux), GNU time, git.
# OS package versions are not pinned (see the header: not reproducible yet); recorded in /opt/env/dpkg.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential gcc-13 g++-13 binutils python3 python3-pip \
      util-linux time bc xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/env && dpkg-query -W -f '${Package} ${Version}\n' > /opt/env/dpkg.txt
# The toolkit, as prover/docs/build.md installs it, into a root-owned directory (so build.sh gives
# the programs a run path to it, and only root can change the code that they load).
# Link-time stand-in for the driver's library: build.md links stubs/libcuda.so to the machine's own
# libcuda.so.1, which an image build does not have. NVIDIA's stub (same CUDA 13.2.86 release, from
# NVIDIA's apt repository, pinned by sha256) has the soname libcuda.so.1, so at run time the loader
# takes the driver's library, which the NVIDIA container runtime puts in the loader's configuration.
# One RUN, so that chmod does not copy the toolkit into a second layer.
COPY requirements-cuda.txt /opt/env/requirements-cuda.txt
RUN mkdir /opt/cuda-13.2.86 \
    && python3 -m pip install --no-cache-dir --no-deps --require-hashes --break-system-packages \
         --target /opt/cuda-13.2.86 -r /opt/env/requirements-cuda.txt \
    && cd /opt/cuda-13.2.86/nvidia/cu13/lib \
    && for n in cublasLt cublas cudart; do ln -s lib$n.so.13 lib$n.so; done \
    && mkdir stubs \
    && curl -fsSLo /tmp/drv.deb \
      https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-driver-dev-13-2_13.2.86-1_amd64.deb \
    && echo "ba113b074282ba57132a7dd44d3d454dc43d0b069cdfef992f3bd4f910b76711  /tmp/drv.deb" | sha256sum -c - \
    && dpkg-deb -x /tmp/drv.deb /tmp/drv \
    && cp /tmp/drv/usr/local/cuda-13.2/targets/x86_64-linux/lib/stubs/libcuda.so /opt/cuda-13.2.86/nvidia/cu13/lib/stubs/ \
    && rm -rf /tmp/drv /tmp/drv.deb \
    && chmod -R go-w /opt/cuda-13.2.86
ENV PATH=/opt/cuda-13.2.86/nvidia/cu13/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN nvcc --version | tail -n 2 | tee /opt/env/nvcc.txt && gcc --version | head -n 1 | tee /opt/env/gcc.txt

# ---- stage source: the pinned commit, without the Lean tree (not needed to build or run) ----------
FROM toolkit AS source
ARG FLASHPROVE_REPO=https://github.com/wakesync/flashprove.git
ARG FLASHPROVE_COMMIT=9e2bdd8ff5bf9c62f18263d7dac189b0400b260c
RUN git init -q /opt/flashprove && cd /opt/flashprove \
    && git remote add origin "$FLASHPROVE_REPO" \
    && git config core.sparseCheckout true && git sparse-checkout set --no-cone '/*' '!/lean/' \
    && git fetch -q --depth 1 --filter=blob:none origin "$FLASHPROVE_COMMIT" \
    && git checkout -q FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "$FLASHPROVE_COMMIT" \
    && git rev-parse HEAD > /opt/env/flashprove-commit.txt \
    && chmod -R go-w /opt/flashprove

# ---- stage verifier: cp_verify alone (validated locally in phase 1) -------------------------------
FROM source AS verifier
RUN cd /opt/flashprove && verifier/build.sh && sha256sum bin/cp_verify | tee /opt/env/cp_verify.sha256

# ---- stage prover: the default (serving) build, cp_commit + cp_prove + copy of cp_verify ----------
FROM verifier AS prover
# From here on every RUN is bash with pipefail, so a failing build is not hidden by `| tail`.
# (The toolkit/source/verifier stages are left unchanged so that phase 1's build receipts stay
# valid; their one pipeline, nvcc --version | tail | tee, is checked by content here.)
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN grep -q 'V13.2.86' /opt/env/nvcc.txt && grep -q '^gcc' /opt/env/gcc.txt
# No GPU here: CUDA_VISIBLE_DEVICES= keeps the compiler sample off any GPU (version check only).
RUN cd /opt/flashprove/prover && CUDA_VISIBLE_DEVICES= ./build.sh 2>&1 | tail -n 20 \
    && test -x build/hc/cp_commit && test -x build/hc/cp_prove && test -x build/hc/cp_verify \
    && sha256sum build/hc/cp_commit build/hc/cp_prove build/hc/cp_verify | tee /opt/env/programs.sha256
# The compiler sample, kept so that run_job.sh can run the check by value on the H200.
RUN cd /opt/flashprove/prover && CUDA_VISIBLE_DEVICES= ./build.sh compiler_sample 2>&1 | tail -n 3 \
    && test -x build/compiler_sample
# A one-call probe of host memory registration under confidential computing (cc_probe.cu).
COPY cc_probe.cu /opt/fp-h200/cc_probe.cu
RUN nvcc -std=c++17 --gpu-architecture=sm_90a --cudart=static -o /opt/fp-h200/cc_probe /opt/fp-h200/cc_probe.cu

# ---- final: job runner and results server ----------------------------------------------------------
FROM prover AS final
COPY run_job.sh serve.py /opt/fp-h200/
RUN chmod 0755 /opt/fp-h200/run_job.sh /opt/fp-h200/serve.py \
    && useradd --uid 10001 --create-home --shell /bin/bash prover
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    FP_REPO=/opt/flashprove \
    FP_WORK=/work
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/opt/fp-h200/run_job.sh", "serve"]
