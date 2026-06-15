"""
Runtime hook for PyInstaller: redirect matplotlib's config/cache directory to a
persistent user-level folder so the font cache is built once and reused on
every subsequent startup instead of being rebuilt from scratch each time.
"""
import os

_cache_dir = os.path.join(os.path.expanduser("~"), ".evaldata_cache", "matplotlib")
os.makedirs(_cache_dir, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", _cache_dir)
