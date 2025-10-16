import os
import re
from typing import Dict, List, Tuple

try:
    import fiona  # type: ignore
except Exception as e:  # pragma: no cover
    fiona = None


def list_block_shapefiles(uncovered_dir: str) -> List[str]:
    """Return sorted list of shapefile paths matching Block_*.shp."""
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


def load_uncovered_blocks(uncovered_dir: str) -> List[Dict]:
    """Load total uncovered area per block from multiple Block_*.shp files.

    Expects attribute `Area_Uncov` per geometry. Ignores `Id`.
    Returns a list of dicts: { 'block': int, 'area_m2': float, 'path': str }.
    """
    if fiona is None:
        raise RuntimeError(
            "Fiona is required to read shapefiles. Install dependencies with `pip install -r python/requirements.txt`."
        )
    results: List[Dict] = []
    for shp in list_block_shapefiles(uncovered_dir):
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

