# Which Human Writing Does GPTZero Call AI?

Code for the post [post]. It recomputes every number, table and figure in the post from the dataset [dataset], and
holds the scripts I used to collect the texts, scan them and run the comparisons.

## Recompute the post

Put the dataset's `data/` folder at `dataset/data` (or pass its path, or set `GPTZERO_HUMAN_DATA`). Then, with
Python 3.11 or later and nothing else installed:

```
python3 recompute.py dataset/data     # every number in the post
python3 tables.py dataset/data        # Tables A1-A4 of the appendix, as Markdown
```

Two numbers about Liang et al.'s essays in 2023 need their scores: pass `GPTZero.json` from
[their repository](https://github.com/Weixin-Liang/ChatGPT-Detector-Bias) (`Data_and_Results/Human_Data/TOEFL_real_91`)
as the second argument of `recompute.py`.

The figures need Pillow (for text widths) and the Source Serif 4 font (`FIGURE_FONT` can point to the .ttf):

```
uv run --extra figures python -m figures.make_figures out/ --data dataset/data --liang GPTZero.json
```

Tests: `uv run pytest`. They check that `recompute.py` and `tables.py` give the post's numbers and tables, that the text
helpers work, and that the collectors give back the dataset's texts from the download cache. Tests skip what is
missing (the dataset, Liang et al.'s file, the cache).

## Folders

| Folder | What it does | Needs |
| --- | --- | --- |
| `recompute.py`, `tables.py`, `dataset.py` | numbers and tables of the post | the dataset |
| `figures/` | the post's figures as SVG | Pillow, Source Serif 4 |
| `scan/` | sends texts to GPTZero and saves each full response | `GPTZERO_API_KEY` (paid) |
| `controls/` | the 118 AI texts written by Qwen3-14B, and the detector comparison on the 118 pairs | GPU |
| `free_detectors/` | the four free Hugging Face detectors behind Table A4 | GPU or Apple MPS (CPU works, slowly) |
| `collect/` | downloading and cutting the human texts, and a check against the dataset | network once |
| `tests/` | pytest | |

`controls/detectors.py` runs Binoculars, Fast-DetectGPT, RADAR, Desklib, Fakespot and OpenAI's RoBERTa detector, each
with its own code or model-card recipe (`BINOCULARS_REPO` and `FAST_DETECT_GPT_REPO` point to clones of the two
repositories). `controls/editlens.py` runs Pangram's EditLens models (`EDITLENS_REPO`, gated models on Hugging Face).
`controls/compare.py` reads their outputs and prints false positives, detections and AUROC for each detector. The
dataset holds GPTZero's scores on the 118 pairs, but not the other detectors' scores, so these numbers need a GPU run.
The AUROC numbers of the free detectors (Table A4) are computed from the dataset.

## How the texts were collected

Each module in `collect/` covers one kind of source and uses the same download helper (`collect/fetch.py`): an on-disk
cache named by the SHA-1 of the address, a pause between requests, and a User-Agent from `COLLECT_USER_AGENT`. SEC
EDGAR asks for a name and an email address in the User-Agent, so `sec.gov` requests use `SEC_USER_AGENT`.

| Module | Source |
| --- | --- |
| `lehman.py` | Lehman Brothers' earnings releases (1998-2008) on the Wayback Machine, and the unchanged cuts of them |
| `edgar.py` | SEC 8-K exhibits: earnings releases of about 70 companies, Lehman's four peers, whole short releases, regional banks |
| `essays.py` | student essays from two dead sites (2002-2003), and the two batches that were scanned |
| `web_genres.py` | seven web genres guessed to be plain writing (trafilatura 2.3.1) |
| `google_answers.py` | Google Answers researchers' answers (2002-2006) |
| `results_prose.py` | BLS, NOAA, USDA WASDE and ESPN results prose (2019) |
| `dead_sites.py` | pages of company websites that went offline around 2008-2015 |
| `clinical_trials.py` | ClinicalTrials.gov detailed descriptions last updated in 2020 or earlier |

`python3 -m collect.check dataset/data [PAGE_TEXTS.jsonl]` rebuilds the texts from the cached raw pages, with no
network, and compares them with the dataset's `text_sha256` (withheld texts included). With my cache it gave:

| Source | Texts rebuilt exactly |
| --- | --- |
| Lehman release cuts, from my saved page texts of every quarter | 93 of 93 |
| Lehman release cuts, from the ten release pages I fetched again | 44 of 44 |
| SEC filings (Lehman's peers, short releases and cuts of them) | 77 of 77 |
| Student essays | 110 of 110 |
| BLS, NOAA, WASDE, ESPN, Google Answers, web genres, dead company sites (the pages I fetched again to check) | 11 of 11 |

Ten Lehman release pages fetched again from the Wayback Machine gave the same page text as my first download.

Some texts had no script; I collected them by hand:

- NSF award abstracts from 2015-2019, picked with a word list, and three passages of US federal strategy documents.
- Pre-2008 corporate pages on the Wayback Machine, sampled with a loose content filter (at most three per site),
  including whole Lehman release pages and one cleaned copy of the Q2 2007 release.
- Earnings releases and explainer pages from before 2009.
- Nepali English-language newspapers on the Wayback Machine.
- India's Press Information Bureau releases, Indian Kanoon judgments and IOSR journal papers on the Wayback Machine,
  and OCR text of Digital Library of India books from 1902-1945.
- Stretches of earnings releases from EDGAR that resembled the Lehman text, cuts of Huntington 8-K releases, stretches
  of Lehman's Q2 2007 10-Q, and the 306-word passage of Lehman's 8-K.
- Choices made by reading: the three Bear Stearns dividend releases out of five, the four paragraph ranges of peer
  releases (picked from GPTZero's sentence scores), the four regional bank sections, the Merrill Lynch article, and the
  three ClinicalTrials.gov descriptions (the top three by OpenAI's RoBERTa detector score).

## What the dataset does not reproduce

- The post's 628 windows include withheld texts. From the released texts the count is 384, and the 27 hot windows are
  all in released texts.
- Fakespot, Desklib and Fast-DetectGPT's false positives on the 118 human texts, and EditLens on the 118 pairs, are
  not in the dataset; `controls/` recomputes them with a GPU.
- "32 regional banks" and "a few hundred" sections describe the collection, not the scans; `collect/edgar.py regional`
  rebuilds that list.

## Data and licence

The code is MIT licensed. The dataset is CC BY 4.0; each text keeps its source's terms. Some texts are withheld in the
dataset: for those it gives the address, snapshot date, first and last words and SHA-256, so they can be taken again
with `collect/` and checked against the hash.
