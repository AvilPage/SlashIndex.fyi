### SlashIndex

Find your people, fast — every personal blog on the planet, in one place.


### Adding a domain via pull request

1. Add one row beneath the header. `domain` is required; `author`, `topics`, `pages`,
   `country`, `state`, and `city` are optional.
2. Quote values that contain commas, such as `"about, now"` or
   `"design, programming"`.
3. Submit the change as a PR. After it is merged, the deployment workflow rebuilds
   the index automatically.

For example:

```csv
avilpage.com,Anand,"design, programming","about, now",🇮🇳 IN,Karnataka,Bangalore
```

### Slash Pages

- /about
- /friends
- /ideas
- /now
- /uses

### Local Setup

CLI tool generates a csv file.

```shell
slashindex sync --output slashindex.csv
slashindex build
```

### Adding a domain with the CLI

To enrich a personal site and add it to `index.csv`, run:

```shell
slashindex add https://example.com --csv index.csv
```

The command normalizes the domain, extracts available metadata, and sorts the CSV. Use
`--dry-run` to print the row without writing it.

### Reprocessing domain metadata

To fill blank `author`, `topics`, `pages`, `country`, `state`, and `city` fields from
each domain's public website, run:

```shell
slashindex reprocess --csv index.csv
```

By default, only rows with every metadata field blank are processed. Existing values are
always preserved. Use `--partial` to also process rows that have some metadata already
filled, `--dry-run` to inspect the result without writing the CSV, or `--limit N` to
process a smaller batch. Reprocessing also normalizes domains by removing `http://`,
`https://`, and `www.` before writing the CSV, then sorts rows by domain.

### Deployment
