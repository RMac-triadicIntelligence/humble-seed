"""ADAPTER, not a kernel: v0.8.6 candidate (file named candidate_v0_8_2.py by the adapter) placed in the 'v0.7 merge' slot.
The lineage probes call OwnerTool.attest(seed, cp) (v0.7 interface). v0.8.2's
attest builds its own request at signing time, so the passed request is ignored."""
import importlib.util as _u, sys as _s
from pathlib import Path as _P
_spec = _u.spec_from_file_location("candidate_v0_8_2", _P(__file__).with_name("candidate_v0_8_2.py"))
_m = _u.module_from_spec(_spec); _s.modules["candidate_v0_8_2"] = _m; _spec.loader.exec_module(_m)
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})

class OwnerTool(_m.OwnerTool):
    def attest(self, seed, cp=None):
        return super().attest(seed)
