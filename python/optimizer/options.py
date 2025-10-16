from dataclasses import dataclass
from typing import List
import csv


@dataclass(frozen=True)
class GroundOption:
    mix_id: str
    res_pct: float  # 0..1
    nbs_pct: float  # 0..1
    label: str


def _normalize_pct(v: str) -> float:
    try:
        x = float(v)
    except Exception:
        x = 0.0
    # options may be in 0..1 or 0..100
    return x / 100.0 if x > 1.0 else x


def load_ground_options(path: str, max_pct_res: float = 1.0, max_pct_nbs: float = 1.0) -> List[GroundOption]:
    """Load ground options from options.csv; apply maximum percentage filters (0..1)."""
    out: List[GroundOption] = []
    with open(path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get('cell_type') or '').strip().lower() != 'ground':
                continue
            res_pct = _normalize_pct(row.get('res_pct', '0'))
            nbs_pct = _normalize_pct(row.get('nbs_pct', '0'))
            if res_pct <= max_pct_res and nbs_pct <= max_pct_nbs:
                out.append(
                    GroundOption(
                        mix_id=(row.get('mix_id') or '').strip(),
                        res_pct=res_pct,
                        nbs_pct=nbs_pct,
                        label=(row.get('label') or '').strip(),
                    )
                )
    if not out:
        raise ValueError("No ground options available after applying max percentage filters.")
    return out

