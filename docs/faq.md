# FAQ And Troubleshooting

Use this page for practical problems. For the normal workflow, start with [user-guide.md](user-guide.md).

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

Common causes are wrong column roles, the wrong active column, or the wrong x-axis/reference column.

Fix:

- confirm the active analysis column
- confirm the time or reference column
- try the built-in spectral demo as a control case
- compare against the demo datasets as a sanity check, not as proof that the app is generally correct

## FFT and Welch PSD give different-looking results

That is normal. They answer related but not identical questions.

Fix:

- use FFT amplitude for a direct frequency-content view
- use Welch PSD for a smoother estimate in noisy data

If you want the formal explanation instead of the short practical distinction, see [docs/latex/fft_welch_example.pdf](latex/fft_welch_example.pdf).

## My file loads but the columns look strange

This often means the delimiter or decimal marker was not interpreted as you expected.

Fix:

- inspect the raw source file manually
- check whether commas or semicolons are used as separators
- check whether commas or dots are used as decimal markers

Example: if one row appears as a single long text field, the separator was probably not interpreted the way you expected.

## Exported data is not what I expected

Different export actions export different things.

Check:

- `Export Clean Data` exports cleaned versions of loaded datasets
- merge saves a merged CSV
- `Export Current View` exports the analysis workspace working dataframe

If the result looks wrong, first check whether you exported from the main window or from the analysis workspace. Those actions do not export the same thing.

## I am not sure which part of the app to use

Start with `which-tool-when.md`.

Short version:

- use the main window for structural preparation
- use the analysis workspace for detailed analysis and exports
