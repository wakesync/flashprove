// Minimal unprivileged sampling profiler for cp_verify (perf is unavailable: perf_event_paranoid=4,
// no perf/valgrind installed; gprof's timer is not inherited by cp_verify's forked stage children).
// LD_PRELOAD this library. In every process (also after fork) it arms ITIMER_PROF at 1 kHz of process
// CPU time; each SIGPROF records the interrupted PC and up to 24 frame-pointer return addresses
// (meaningful only for a -fno-omit-frame-pointer build), as offsets from the main executable's load
// base. At exit each process writes $SAMPLER_DIR/samples.<pid>.txt: one line per sample, hex offsets,
// leaf first. Addresses outside the executable are written as 0. It reads nothing of the verifier's data.
#define _GNU_SOURCE
#include <link.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <ucontext.h>
#include <unistd.h>
#include <pthread.h>

#define MAXS 200000
#define DEPTH 24
static uintptr_t lo, hi;
static uintptr_t buf[MAXS][DEPTH];
static unsigned char nfr[MAXS];
static volatile int n;
static int me;

static int phdr_cb(struct dl_phdr_info *info, size_t size, void *data) {
  (void)size; (void)data;
  if (info->dlpi_name && info->dlpi_name[0]) return 0;  // the main program has an empty name
  lo = info->dlpi_addr; hi = 0;
  for (int i = 0; i < info->dlpi_phnum; i++)
    if (info->dlpi_phdr[i].p_type == PT_LOAD) {
      uintptr_t e = info->dlpi_addr + info->dlpi_phdr[i].p_vaddr + info->dlpi_phdr[i].p_memsz;
      if (e > hi) hi = e;
    }
  return 1;
}
static uintptr_t off(uintptr_t a) { return (a >= lo && a < hi) ? a - lo : 0; }

static void on_prof(int sig, siginfo_t *si, void *uc_) {
  (void)sig; (void)si;
  int i = n;
  if (i >= MAXS) return;
  ucontext_t *uc = uc_;
  uintptr_t pc = uc->uc_mcontext.gregs[REG_RIP];
  uintptr_t *fp = (uintptr_t *)uc->uc_mcontext.gregs[REG_RBP];
  uintptr_t sp = uc->uc_mcontext.gregs[REG_RSP];
  int d = 0;
  buf[i][d++] = off(pc);
  while (d < DEPTH && fp && (uintptr_t)fp > sp && (uintptr_t)fp - sp < (64u << 20) && ((uintptr_t)fp & 7) == 0) {
    uintptr_t ret = fp[1];
    if (!ret) break;
    buf[i][d++] = off(ret);
    uintptr_t *nx = (uintptr_t *)fp[0];
    if (nx <= fp) break;
    fp = nx;
  }
  nfr[i] = (unsigned char)d;
  n = i + 1;
}
static void arm(void) {
  me = getpid();
  n = 0;
  struct itimerval t = {{0, 1000}, {0, 1000}};
  setitimer(ITIMER_PROF, &t, 0);
}
static void dump(void) {
  struct itimerval z = {{0, 0}, {0, 0}};
  setitimer(ITIMER_PROF, &z, 0);
  if (getpid() != me) return;
  const char *dir = getenv("SAMPLER_DIR");
  if (!dir) return;
  char p[4096];
  snprintf(p, sizeof p, "%s/samples.%d.txt", dir, (int)getpid());
  FILE *f = fopen(p, "w");
  if (!f) return;
  for (int i = 0; i < n; i++) {
    for (int d = 0; d < nfr[i]; d++) fprintf(f, d ? " %lx" : "%lx", (unsigned long)buf[i][d]);
    fputc('\n', f);
  }
  fclose(f);
}
__attribute__((constructor)) static void init(void) {
  // Only profile cp_verify itself: an armed timer survives exec() while the handler does not, so a
  // wrapper such as taskset must never arm it.
  char exe[4096];
  ssize_t k = readlink("/proc/self/exe", exe, sizeof exe - 1);
  if (k <= 0) return;
  exe[k] = 0;
  const char *base = strrchr(exe, '/');
  if (!base || strcmp(base + 1, "cp_verify")) return;
  dl_iterate_phdr(phdr_cb, 0);
  struct sigaction sa;
  memset(&sa, 0, sizeof sa);
  sa.sa_sigaction = on_prof;
  sa.sa_flags = SA_SIGINFO | SA_RESTART;
  sigaction(SIGPROF, &sa, 0);
  pthread_atfork(0, 0, arm);
  atexit(dump);
  arm();
}
