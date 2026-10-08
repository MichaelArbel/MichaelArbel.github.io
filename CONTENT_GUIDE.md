# Updating the site

This website is a Jekyll site. The main editable content is Markdown; Jekyll
turns it into the website when it builds.

## Home page

Edit `index.md`. The biography is normal Markdown below the front matter; the
same file contains the profile photo, CV, address, social links, and contact
note used by the homepage layout.

## Opportunities

Edit `opportunities/index.md` to describe PhD and postdoctoral opportunities,
funding, application material, and the preferred contact process.

## Teaching

Edit `teaching/index.md` to maintain the list of courses and their links. Each
course is a normal Markdown section, so it is easy to add a term, a concise
description, and a link to its dedicated course website.

## Blog

Each published blog post is a Markdown file in `blog/`. Copy
`blog/blog-post-template.md` to `blog/your-post.md`, then fill in its `title`,
`date`, `summary`, and Markdown body. Keep `blog_post: true`; the Blog page
automatically turns all such files into linked cards, newest first. The
template itself is excluded from the built website. The Blog link is hidden
from the main navigation until at least one published post exists.

## Talks and slides

1. Put a PDF in `assets/pdf/`.
2. Open `talks/README.md` and copy one of the items in the `talks:` list.
3. Fill in the title, date, event, location, and `slides` PDF path. `topic`,
   `video`, `paper`, and `event_url` are optional.

The talks page is automatically ordered newest first, with upcoming talks
shown before the archive. A talk moves to the archive automatically after its
date has passed.

## Software

Edit `software/README.md`. Each entry has a title, short description, image,
and optional Code and ArXiv links. The Software page is generated automatically
from this file. Set `projects: [anr]`, `projects: [erc]`, or
`projects: [anr, erc]` on an entry to also show it on the corresponding project
page.

## News

Edit `news/README.md` and add new entries at the top of its `items:` list.
Set a date and write the announcement in `content`; standard Markdown links
are supported. The homepage formats the date and displays the list
automatically.

## Publications

`assets/bibliography/bibliography.bib` is the authoritative, curated record of
your publications. The weekly `.github/workflows/update-publications.yml`
workflow queries the official arXiv API for Michael Arbel's records. It never
replaces or removes curated entries: it adds missing arXiv identifiers to
matching entries and appends only new arXiv preprints. It then regenerates
`_data/publications.json`, which Jekyll uses to render the publication list
without browser JavaScript. The workflow commits both files and can also be run
from the **Actions** tab with **Run workflow**.

To run the same update locally, use `python scripts/update_publications.py`.
To regenerate only the display data after editing BibTeX by hand, use
`python scripts/update_publications.py --from-bib`. If arXiv cannot be reached,
the workflow fails without changing the published bibliography.

The Publications page starts with the `featured_work` entries in
`publications/index.html`; update those deliberately when a contribution should
be highlighted. The complete bibliography is then grouped automatically into
peer-reviewed publications, preprints, and other research outputs based on the
BibTeX entry type and venue.

## Curriculum vitae

The homepage links to `cv/CV.pdf`. Its editable source is `cv/CV.tex`, which
reads the same `assets/bibliography/bibliography.bib` as the website. Keep the
research profile, supervision, selected software, courses, and talks in sync
with the corresponding Markdown pages. Upcoming talks must remain labelled as
upcoming until they have taken place. Changes to the bibliography appear in
the PDF only after recompiling it.

This CV uses the existing multi-file ModernCV project and BibLaTeX/Biber. With
a TeX installation that provides `latexmk` and `biber`, rebuild from `cv/`:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=.build CV.tex
cp .build/CV.pdf CV.pdf
```

Check the generated PDF before publishing. Older packages are deliberately
omitted from the selected software section; this is not a complete software
archive.

## Project pages

The ANR JCJC project is in `projects/bonsai/`; the ERC placeholders are in
`projects/erc/`. Each project has four Markdown pages:

- `index.md` — overview and abstract
- `publications.md`
- `software.md`
- `jobs.md`

The shared project navigation is added automatically. BONSAI publications are
currently a clearly labelled time-window view, while project software is
selected by the optional `projects` field in `software/README.md`.

## Preview and build

Use Ruby 3.0 or newer. On macOS, the system Ruby is too old; select the
Homebrew Ruby before running Bundler:

```bash
export PATH="$(brew --prefix ruby)/bin:$PATH"
BUNDLE_PATH=vendor/bundle bundle install
BUNDLE_PATH=vendor/bundle bundle exec jekyll serve --livereload
```

Run `BUNDLE_PATH=vendor/bundle bundle exec jekyll build` for the production
build check.

After building, run `python3 scripts/check_site.py` to check the primary pages,
local links and assets, shared project headings, publication dates, and the
copied CV.
