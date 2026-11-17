// Experiment 20261117-212-moe-at-layer-ne (issue #212). Host only: g++, no CUDA.
// Enumerates prof in {1, 2, 3, 20}, layer l in 0..7, NE in {0, 1, 16} and counts where each arm
// disagrees with the reference rule ref(prof, l, NE) = prof >= 3 && (l & 1) && NE > 0.
// It includes main's unmodified prover/prover/layout.h, so arm A tests main's own moe_at_layer().
// Usage: enumerate <output file>. Deterministic: no randomness, no timing.
#include "prover/layout.h"
#include <cstdio>

static bool ref(int prof, int l, int NE) { return prof >= 3 && (l & 1) && NE > 0; }

// Arm B: the LayerShape::prof that main assigns before either caller of moe_at_layer() runs.
// Both assignments use the same expression, with mo = NE > 0 (prover/prover/inputs.cuh line 237):
//   prover/prover/layer_setup.cuh line 70 (LayerShape S -> make_layer_layout -> ForwardPass::L.s,
//     read as pf = L.s.prof at prover/prover/forward.cuh line 1480, used at line 1558);
//   prover/prover/inputs.cuh line 293 (LayerShape s -> layer_words_fit, forward.cuh line 108).
// The parameter file's own prof (prover/common/parameter_file.h line 176: must be 20) is not
// assigned to LayerShape::prof anywhere on main.
static int shape_prof_on_main(int NE) {
  const bool mo = NE > 0;
  return mo ? 3 : 2;
}

int main(int argc, char **argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: enumerate <output file>\n");
    return 1;
  }
  FILE *o = fopen(argv[1], "w");
  if (!o) {
    fprintf(stderr, "cannot open %s\n", argv[1]);
    return 1;
  }
  const int profs[] = {1, 2, 3, 20}, nes[] = {0, 1, 16};
  int casesAB = 0, disA = 0, disA_ne0_odd_hi = 0, disB = 0, casesB_ne0 = 0, disB_ne0 = 0, casesB_p20 = 0, disB_p20 = 0,
      casesC = 0, disC = 0, casesC_main = 0, disC_main = 0;
  fprintf(o, "# prof l NE ref armA armB armC armC_main\n");
  for (int prof : profs)
    for (int l = 0; l < 8; l++)
      for (int NE : nes) {
        const bool r = ref(prof, l, NE);
        // Arm A: main's function, given the enumerated prof directly.
        const bool a = moe_at_layer(prof, l);
        // Arm B: main's function, given the prof that main's callers actually see for this NE.
        LayerShape sb;
        sb.prof = shape_prof_on_main(NE);
        sb.NE = NE > 0 ? NE : 0; // layer_setup.cuh line 64: mo ? NE : 0
        const bool b = moe_at_layer(sb.prof, l);
        // Arm C: the prior-art rule prof >= 3 && (l & 1) && NE > 0 fed with the LayerShape that
        // inputs.cuh lines 292-295 builds for layer_words_fit(): it sets prof, xl and the digit
        // forms, never NE, so NE keeps its default (layout.h line 21).
        LayerShape sc; // as at inputs.cuh line 292: NE not assigned
        sc.prof = prof;
        const bool c = sc.prof >= 3 && (l & 1) && sc.NE > 0;
        // Arm C as main would actually call it (prof = mo ? 3 : 2).
        LayerShape scm;
        scm.prof = shape_prof_on_main(NE);
        const bool cm = scm.prof >= 3 && (l & 1) && scm.NE > 0;
        casesAB++;
        disA += a != r;
        disA_ne0_odd_hi += (a != r) && NE == 0 && (l & 1) && prof >= 3;
        disB += b != r;
        if (NE == 0) casesB_ne0++, disB_ne0 += b != r;
        if (prof == 20) casesB_p20++, disB_p20 += b != r;
        if (NE > 0) {
          casesC++;
          disC += r && !c;
          casesC_main++;
          disC_main += r && !cm;
        }
        fprintf(o, "%d %d %d %d %d %d %d %d\n", prof, l, NE, (int)r, (int)a, (int)b, (int)c, (int)cm);
      }
  // Arm B with the reference evaluated at main's own shape prof (the prof the prover runs with).
  int disB_own = 0;
  for (int l = 0; l < 8; l++)
    for (int NE : nes) disB_own += moe_at_layer(shape_prof_on_main(NE), l) != ref(shape_prof_on_main(NE), l, NE);
  fprintf(o, "armA_disagree %d of %d\n", disA, casesAB);
  fprintf(o, "armA_disagree_ne0_odd_prof_ge3 %d\n", disA_ne0_odd_hi);
  fprintf(o, "armB_disagree %d of %d\n", disB, casesAB);
  fprintf(o, "armB_disagree_ne0 %d of %d\n", disB_ne0, casesB_ne0);
  fprintf(o, "armB_disagree_prof20 %d of %d\n", disB_p20, casesB_p20);
  fprintf(o, "armB_own_prof_disagree %d of %d\n", disB_own, 8 * 3);
  fprintf(o, "armC_missed_moe %d of %d\n", disC, casesC);
  fprintf(o, "armC_main_prof_missed_moe %d of %d\n", disC_main, casesC_main);
  fclose(o);
  return 0;
}
