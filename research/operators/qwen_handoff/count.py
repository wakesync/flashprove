#!/usr/bin/env python3
"""Exact columns/affine relations of handoff.cpp, not bytes or model-fit estimates."""
import json

def power2(n):
    return 1 << (n-1).bit_length()

def counts(D,C,F=12):
    T=2*C
    inherited_cols=T*((F+5)*D*D+(4*F+5)*D)
    inherited_rel=T*((2*F+9)*D*D+(8*F+7)*D)
    extra=150+36*D+3*T*D # two 75-cell descriptors, history and preconv input cells
    rc=T*(D*D+3*D)
    core=inherited_cols+extra
    size=16*power2((rc+15)//16)
    laid=((core-rc+size-1)//size)*size+size
    return dict(D=D,C=C,F=F,T=T,core_columns=core,aligned_columns=laid,
                relations=inherited_rel+extra,range_cells=rc,
                core_columns_per_token=core/T,relations_per_token=(inherited_rel+extra)/T,
                boundary_state_equalities=D*D,history_equalities=27*D,
                extra_columns=extra)

if __name__=='__main__':
    print(json.dumps({'kind':'counted, not memory or hardware measurements',
          'rows':[counts(D,C) for D,C in [(8,2),(32,2),(128,2),(128,64)]]},indent=2))
