---
name: proxy-export
description: Turn a finished deck.txt into proxy-ready output — plain lists for MPCFill/print services, Moxfield import text, or a print-ready PDF of true-size 3x3 sheets. Use when the user wants to print, import, or share a list.
---

# Proxy export

```bash
./edh export decks/<slug>/<arch>/deck.txt --out decks/<slug>/<arch>/proxies.txt   # "1 Name" lines
./edh export decks/<slug>/<arch>/deck.txt --format moxfield                          # Commander/Deck sections
./edh export decks/<slug>/<arch>/deck.txt --format pdf [--paper a4]                   # print sheets
./edh export decks/<slug>/<arch>/deck.txt --format images --out /some/dir             # raw scans
```

- **plain** pastes into MPCFill, mtgprint.net, Printing Proxies, Moxfield and
  Archidekt bulk import. Commanders come first.
- **pdf** downloads Scryfall's large scans (cached in `data/cache/images`), lays
  them out 3×3 at 63×88 mm with cut guides, and adds back faces for double-faced
  cards as separate cards. Print at 100% scale ("actual size"), not
  "fit to page". A 100-card deck is ~12 pages and ~15–25 MB. PDFs are gitignored.
  Tell the user where the file is. Don't commit it.
- Basic lands print too. Mention that most people already own basics, and offer
  a version without them if asked (remove basics from a copy of the list first).
- Scryfall images are for personal use. Don't suggest selling proxies.
