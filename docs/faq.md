# FAQ And Troubleshooting

## The app says I must select exactly one dataset

Some actions work only when one dataset is selected, especially preview, preparation, and opening the analysis workspace.

Fix:

- click one dataset in the dataset list
- clear any multi-selection before retrying

## I created a prepared dataset but cannot find a new file on disk

Prepared datasets are created inside the application as new dataset entries. They are not automatically saved to disk.

Fix:

- select the prepared dataset
- open the analysis workspace if needed
- use export when you want a physical CSV file

## The wrong column is used as time

Automatic role inference is only a starting point.

Fix:

- open the `Roles` tab
- assign the correct column to `time`
- reopen or refresh analysis views if needed

## The plot or spectrum looks wrong

Common causes are wrong column roles, wrong active column, wrong x-axis reference, or an output range that is too short.

Fix:

- confirm the active analysis column
- confirm the time or reference column
- widen the selected output range
- try the demo datasets to verify expected behavior

## FFT and Welch PSD give different-looking results

That is normal. They answer related but not identical questions.

Fix:

- use FFT amplitude for a direct frequency-content view
- use Welch PSD for a smoother estimate in noisy data

## My file loads but the columns look strange

This often means the delimiter or decimal marker was not interpreted as you expected.

Fix:

- inspect the raw source file manually
- check whether commas or semicolons are used as separators
- check whether commas or dots are used as decimal markers

## Exported data is not what I expected

Different export actions export different things.

Check:

- `Export Clean Data` exports cleaned versions of loaded datasets
- merge saves a merged CSV
- `Export Current View` exports the analysis workspace working dataframe

## I am not sure which part of the app to use

Start with `which-tool-when.md`.

Short version:

- use the main window for structural preparation
- use the analysis workspace for detailed analysis and exports
