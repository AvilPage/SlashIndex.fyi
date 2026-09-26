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

### SlashIndex CLI

CLI tool generates a csv file.

```shell
slashindex sync

slashindex build

slashindex add https://avilpage.com 
```
slashindex reprocess
slashindex reprocess --partial
slashindex reprocess --column topics
```