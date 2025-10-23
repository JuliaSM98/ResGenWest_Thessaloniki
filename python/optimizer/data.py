import os
import re
from typing import Dict, List, Tuple

try:
    import fiona  # type: ignore
except Exception as e:  # pragma: no cover
    fiona = None


def list_block_shapefiles(uncovered_dir: str) -> List[str]:
    """Return sorted list of shapefile paths matching Block_*.shp in a directory."""
    files = []
    if not os.path.isdir(uncovered_dir):
        raise FileNotFoundError(f"Uncovered dir not found: {uncovered_dir}")
    for name in os.listdir(uncovered_dir):
        if name.lower().endswith('.shp') and name.startswith('Block_'):
            files.append(os.path.join(uncovered_dir, name))
    # sort by numeric block number if possible
    def keyfn(p: str) -> Tuple[int, str]:
        bname = os.path.basename(p)
        m = re.match(r"Block_(\d+)\.shp\Z", bname)
        return (int(m.group(1)) if m else 10**9, bname)
    return sorted(files, key=keyfn)


def extract_block_number_from_filename(path: str) -> int:
    bname = os.path.basename(path)
    m = re.match(r"Block_(\d+)\.shp\Z", bname)
    if not m:
        raise ValueError(f"Cannot parse block number from filename: {bname}")
    return int(m.group(1))


def load_uncovered_blocks(uncovered_path: str) -> List[Dict]:
    """Load total uncovered area per block.

    Accepts either:
    - a directory containing multiple Block_*.shp files (expects `Area_Uncov` in each), or
    - a single shapefile path (expects unified schema with `Id`, `B_Number`, and `Area_U_m2`).

    Returns a list of dicts: { 'block': str|int, 'area_m2': float, 'path': str }.
    """
    if fiona is None:
        raise RuntimeError(
            "Fiona is required to read shapefiles. Install dependencies with `pip install -r python/requirements.txt`."
        )
    # Case 1: unified shapefile provided
    if os.path.isfile(uncovered_path) and uncovered_path.lower().endswith('.shp'):
        results: List[Dict] = []
        # Aggregate uncovered area per (Id, B_Number) pair using Area_U_m2
        accum: Dict[str, float] = {}
        with fiona.open(uncovered_path, 'r') as src:
            for feat in src:
                props = feat.get('properties') or {}
                pid = props.get('Id')
                bno = props.get('B_Number')
                # accept numeric or string values; ignore missing
                val_U = props.get('Area_U_m2')
                Val_R = props.get('Area_R_m2')
                v = None
                if val_U is not None and val_U != '':
                    val = val_U
                    cell_type = 'ground'
                elif Val_R is not None and Val_R != '':
                    val = Val_R
                    cell_type = 'roof'
                if isinstance(val, (int, float)):
                    v = float(val)
                else:
                    try:
                        if val is not None:
                            v = float(str(val))
                    except Exception:
                        v = None
                if v is None:
                    continue
                key = f"{pid}.{bno}:{cell_type}"
                accum[key] = accum.get(key, 0.0) + v
        for key, total_area in sorted(accum.items(), key=lambda kv: kv[0]):
            pid_bno, cell_type_b = key.rsplit(':', 1)
            results.append({'block': key, 'area_m2': total_area, 'cell_type': cell_type_b})
        return results

    # Case 2: directory of Block_*.shp files (legacy mode)
    results: List[Dict] = []
    for shp in list_block_shapefiles(uncovered_path):
        block = extract_block_number_from_filename(shp)
        total_area = 0.0
        with fiona.open(shp, 'r') as src:
            for feat in src:
                props = feat.get('properties') or {}
                val = props.get('Area_Uncov')
                if isinstance(val, (int, float)):
                    total_area += float(val)
                else:
                    # try parsing string numeric values
                    try:
                        if val is not None:
                            total_area += float(str(val))
                    except Exception:
                        pass
        results.append({'block': block, 'area_m2': total_area, 'path': shp})
    # sort by block number
    results.sort(key=lambda r: r['block'])
    return results

