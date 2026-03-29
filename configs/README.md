# Configs

`configs/shared_decks.json` drives automatic `.apkg` downloads.

Schema:

```json
{
  "output_dir": "raw",
  "decks": [
    {
      "shared_id": 2090856176,
      "url": "https://ankiweb.net/shared/info/2090856176",
      "filename": "2090856176-IELTS-Writing-Part-1.apkg"
    }
  ]
}
```

Notes:

- `output_dir` is optional and defaults to `raw`.
- Each deck can provide either `shared_id` or `url`.
- `filename` is optional. If omitted, the fetcher derives one from the deck title.
