# Data Formats And Exports

## Supported Input Types

The file-open dialog accepts:

- `.txt`
- `.csv`
- `.log`

The parser tries to detect:

- field separator
- decimal marker
- datetime-like columns based on names such as time, date, or timestamp

## What The App Expects

The app works best when:

- the first real header row contains column names
- each row represents one sample or measurement step
- one column can act as time or sample index if needed
- numeric signal columns are stored consistently

## Notes About Delimiters

The parser supports different separators and decimal markers by detection rather than by a fixed import wizard.

That is useful for mixed logging formats, but it also means badly formed files may need cleanup before loading.

## Prepared Datasets

When you create a prepared dataset:

- the app slices the selected source dataset by the current overview range
- it optionally keeps only the chosen columns
- it creates a new dataset entry inside the application
- it does not automatically write a new file to disk

## Exported Files

### Merge Output

The merge workflow saves a merged dataset to a CSV file.

### Export Clean Data

`Files -> Export Clean Data` exports cleaned versions of all loaded datasets to a selected directory.

These cleaned versions are based on dropping missing values.

### Export Current View

Inside the analysis workspace, `Export Current View` writes the current working dataframe to a CSV file.

## Practical Advice

- If you need a durable file from a prepared dataset, open it in the analysis workspace and export the current view.
- If your file does not import correctly, first inspect delimiter and decimal-marker conventions in the source file.
- If time is not recognized automatically, assign the time role manually in the main window.
