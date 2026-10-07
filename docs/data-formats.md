# Data Formats And Exports

This is a short reference page. The normal workflow is described in [user-guide.md](user-guide.md), and troubleshooting lives in [faq.md](faq.md).

## Inputs

The file-open dialog accepts `.txt`, `.csv`, `.log`, `.parquet`, and `.pq` files.

The parser tries to detect the field separator, decimal marker, and likely datetime-like columns. It works best when the file has a real header row and each row represents one sample or measurement step.

Example: if a file uses semicolons as separators and commas as decimal markers, the parser may still load it correctly, but badly formed files often need cleanup first.

Parquet is a compressed binary alternative for saving and reopening large datasets.
It preserves numeric and datetime types without CSV text parsing. Parquet loading
does not apply CSV separator detection or datetime guessing. PyArrow is a required
dependency and is included in the Windows packaging configuration.

## Prepared Datasets

Creating a prepared dataset makes a new in-app dataset entry. It copies the selected source dataset and can optionally keep only a chosen column subset. It does not automatically write a new file to disk.

If you need row-based separation, use `Preparation -> Split Into Subframes`.

## Exports

- merge saves a merged dataset to CSV or Parquet
- `Files -> Export Selected Clean Data` lets you choose CSV or Parquet, enter a custom filename prefix, and write `dropna()`-cleaned files named `<prefix>_<dataset>.csv` or `<prefix>_<dataset>.parquet`
- `Export Current View` in the analysis workspace writes the current working dataframe to CSV or Parquet without dropping missing rows

In single-file save dialogs, select CSV or Parquet. If the filename has no extension,
the selected format supplies it; an explicit extension takes precedence. `.parquet`
and `.pq` select Parquet (case-insensitive); other extensions retain the existing CSV
writer behavior. CSV remains semicolon-delimited by default and neither format
exports the DataFrame index.

EvalData Parquet exports also store assigned column roles in file metadata and
restore them when loaded. Ordinary Parquet files without those roles still load,
with roles inferred as for CSV. This saves the dataset, not a complete analysis
session or plotting configuration. CSV metadata behavior is unchanged.

Binary storage is intended to reduce repeated parsing and storage overhead; actual
speed depends on the dataset and disk. Loading still materializes a pandas DataFrame
in memory and does not introduce lazy or disk-backed analysis.

If you need a durable file from a prepared dataset, the practical path is to open it in the analysis workspace and export the current view.
