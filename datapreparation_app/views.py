import pandas as pd
from .preview import get_preview_plot_columns
from .datasets import format_source_paths, parse_split_ranges

def get_preview_plot_columns_view(dataframe: pd.DataFrame) -> list[str]:
	return get_preview_plot_columns(dataframe)

def format_source_paths_view(source_paths: list[str]) -> str:
	return format_source_paths(source_paths)

def parse_split_ranges_view(raw_text: str) -> list[tuple[int, int]]:
	return parse_split_ranges(raw_text)
"""Reusable rendering and preview helpers for datapreparation_app."""
# (Intentionally left blank for harmonization; move or add view helpers here as needed.)
