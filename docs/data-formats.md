# Data Formats And Exports

This is a short reference page. The normal workflow is described in [user-guide.md](user-guide.md), and troubleshooting lives in [faq.md](faq.md).

## Inputs

The file-open dialog accepts `.txt`, `.csv`, and `.log` files.

The parser tries to detect the field separator, decimal marker, and likely datetime-like columns. It works best when the file has a real header row and each row represents one sample or measurement step.

Example: if a file uses semicolons as separators and commas as decimal markers, the parser may still load it correctly, but badly formed files often need cleanup first.

## Prepared Datasets

Creating a prepared dataset makes a new in-app dataset entry. It copies the selected source dataset and can optionally keep only a chosen column subset. It does not automatically write a new file to disk.

If you need row-based separation, use `Preparation -> Split Into Subframes`.

## Exports

- merge saves a merged dataset to CSV
- `Files -> Export Clean Data` writes cleaned versions of all loaded datasets
- `Export Current View` in the analysis workspace writes the current working dataframe to CSV

If you need a durable file from a prepared dataset, the practical path is to open it in the analysis workspace and export the current view.
