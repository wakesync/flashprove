# FlashProve prover image for one H200 in a Tinfoil enclave. Untested on a GPU. All stages were built
# locally on 2026-11-12 (issue #140: `prover`, `final`, `runtime`; receipts in
# experiments/20261112-7-h200-dense-calibration/runs/; phase 1 had built `toolkit`, `source`,
# `verifier` only); nothing has been pushed or published, and nothing has run on a GPU.
#
# NOT REPRODUCIBLE YET: the Ubuntu apt packages below are neither version-pinned nor taken from a
# snapshot, so a later rebuild can install different versions. The base image, the CUDA wheels, the
# driver stub and the source commit are pinned. What apt installed is recorded in /opt/env/dpkg.txt
# (phase 1's copy: experiments/20261110-43-h200-bringup/runs/image-dpkg.txt). Pinning them (for
# example to snapshot.ubuntu.com at a fixed date) is open work; it changes the toolkit stage and so
# needs a rebuild and new receipts.
#
# Build context: this directory (research/gpu/tinfoil-h200/).
#   docker build --target final -t fp-h200-prover .      # the full image (toolkit + on-box build), about half an hour of compiling
#   docker build --target runtime -t fp-h200-runtime .    # binaries + redistributable runtime libraries only (README.md, "Licences")
#   docker build --target verifier -t fp-h200-verifier .  # toolkit + cp_verify only, a few minutes
# The last stage is `final`, so a build without --target builds the full image (moved there in PR #141
# review round 1; before that a build without --target gave `runtime`, which cannot do the on-box build).
# Stage <-> flag: final <-> FP_ONBOX_BUILD=1, runtime <-> FP_ONBOX_BUILD=0 (set in the runtime stage);
# run_job.sh refuses FP_ONBOX_BUILD=1 without nvcc before any GPU step.
# The config's healthcheck runs python3 (installed in both final and runtime; the runtime stage has no
# curl). image_contract_test.py checks these stage/config facts statically on every CI run.
# The driver stub (stubs/libcuda.so) is never copied into the runtime image: the driver's own
# libcuda.so.1 comes from the NVIDIA container runtime.
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
# valid. Their pipelines run without pipefail: nvcc --version | tail | tee and gcc --version | head |
# tee, whose outputs are checked by content on the next line; the driver stub's echo | sha256sum -c,
# whose last command is the check itself; and the verifier's sha256sum | tee. Phase 1's receipts establish only what those stages
# printed and produced, not that no earlier command in such a pipeline failed.)
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

# ---- runtime-picks: what the runtime-only image takes from the prover stage ------------------------
# The CUDA libraries that the built programs load, each checked against the list of files that the
# CUDA Toolkit EULA (Attachment A) names as redistributable; any other toolkit library ends the build.
FROM prover AS runtime-picks
RUN set -e; mkdir -p /picks/lib; \
    allow=' libcudart.so libcublas.so libcublasLt.so libnvrtc.so libnvrtc-builtins.so libnvJitLink.so '; \
    for b in /opt/flashprove/prover/build/hc/cp_commit /opt/flashprove/prover/build/hc/cp_prove \
             /opt/flashprove/prover/build/hc/cp_verify /opt/flashprove/prover/build/compiler_sample /opt/fp-h200/cc_probe; do \
      ldd "$b" | awk '/=> \/opt\/cuda-13.2.86\// && !/\/stubs\// {print $3}'; \
    done | sort -u >/picks/needed.txt; \
    while read -r lib; do \
      base=$(basename "$lib"); stem=${base%%.so*}.so; \
      case "$allow" in *" $stem "*) ;; *) echo "not redistributable by Attachment A: $lib" >&2; exit 1 ;; esac; \
      cp -L "$lib" /picks/lib/"$base"; \
    done </picks/needed.txt; \
    cat /picks/needed.txt; ls -l /picks/lib

# ---- runtime: binaries + redistributable runtime libraries only (no compiler, headers or static libs)
# For a PUBLIC image (README.md, "Licences"). It cannot rebuild on the box: run it with
# FP_ONBOX_BUILD=0, which is a deviation from the #43 PREREG that has to be registered first.
# The programs keep their run path to /opt/cuda-13.2.86/nvidia/cu13/lib, so the picked libraries go
# to the same place. The pinned checkout is copied whole, with its build directory (the three
# programs, their .build records and compiler_sample; no toolkit file is in it: the build links the
# toolkit's shared libraries, and cc_probe links cudart_static, which Attachment A lists as
# redistributable).
FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852 AS runtime
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 util-linux time git \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/env && dpkg-query -W -f '${Package} ${Version}\n' > /opt/env/dpkg.txt
COPY --from=runtime-picks /picks/lib/ /opt/cuda-13.2.86/nvidia/cu13/lib/
COPY --from=prover /opt/flashprove/ /opt/flashprove/
COPY --from=prover /opt/env/nvcc.txt /opt/env/gcc.txt /opt/env/flashprove-commit.txt /opt/env/cp_verify.sha256 /opt/env/programs.sha256 /opt/env/
COPY --from=prover /opt/fp-h200/cc_probe /opt/fp-h200/cc_probe
# (Copied files keep their modes, root-owned and not group/other-writable as in the prover stage; a
# chmod -R here would only copy ~0.8 GB into a second layer. The check below fails the build if not.)
RUN test -z "$(find /opt/cuda-13.2.86 /opt/flashprove /opt/fp-h200 \( -perm -g+w -o -perm -o+w \) ! -type l -print -quit)"
COPY run_job.sh serve.py stamp.sh calib_run.sh /opt/fp-h200/
COPY calib/ /opt/fp-h200/calib/
RUN chmod 0755 /opt/fp-h200/run_job.sh /opt/fp-h200/serve.py /opt/fp-h200/stamp.sh /opt/fp-h200/calib_run.sh \
    && chmod -R go-w /opt/fp-h200/calib \
    && useradd --uid 10001 --create-home --shell /bin/bash prover
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    FP_REPO=/opt/flashprove \
    FP_WORK=/work \
    FP_ONBOX_BUILD=0
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/opt/fp-h200/run_job.sh", "serve"]

# ---- final: job runner and results server ----------------------------------------------------------
# The LAST stage (since PR #141 review round 1), so a `docker build` without --target gives this one:
# the draft config's FP_ONBOX_BUILD "1" needs its compiler. Its content is unchanged by the move.
FROM prover AS final
COPY run_job.sh serve.py stamp.sh calib_run.sh /opt/fp-h200/
# The calibration configurations of issue #140 (make_calib_configs.py writes them; FP_CALIB selects them).
COPY calib/ /opt/fp-h200/calib/
RUN chmod 0755 /opt/fp-h200/run_job.sh /opt/fp-h200/serve.py /opt/fp-h200/stamp.sh /opt/fp-h200/calib_run.sh \
    && chmod -R go-w /opt/fp-h200/calib \
    && useradd --uid 10001 --create-home --shell /bin/bash prover
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    FP_REPO=/opt/flashprove \
    FP_WORK=/work
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/opt/fp-h200/run_job.sh", "serve"]
