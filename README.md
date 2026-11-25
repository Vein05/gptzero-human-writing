# Which Human Writing Does GPTZero Call AI?

Code for my post [Which Human Writing Does GPTZero Call AI?][post]. I ran 500 scans of old human writing (1902-2020)
through GPTZero 5.0b, looking for text it calls AI. Almost all of it came back human. The exception was two unchanged
~300-word cuts of Lehman Brothers earnings releases, which scored 100% AI.

The scores are on [Hugging Face][dataset]. This repo recomputes the post from that dataset, and has the scripts I used
to collect the texts, scan them and compare detectors.

## Quick start

All you need is Python 3.11+ and the dataset's `data/` folder:

```
python3 recompute.py path/to/data    # every number in the post
python3 tables.py path/to/data       # Tables A1-A4
```

The figures need Pillow and the Source Serif 4 font (set `FIGURE_FONT` to the .ttf if it isn't found):

```
uv run --extra figures python -m figures.make_figures out/ --data path/to/data --liang GPTZero.json
```

`GPTZero.json` is Liang et al.'s file with GPTZero's 2023 scores on their 91 TOEFL essays, from
[their repo](https://github.com/Weixin-Liang/ChatGPT-Detector-Bias) (`Data_and_Results/Human_Data/TOEFL_real_91`).
`recompute.py` takes it as an optional second argument for the two 2023 numbers.

Tests: `GPTZERO_HUMAN_DATA=path/to/data uv run pytest`. Tests that need a missing file are skipped.

## What's here

- `scan/` sends texts to the GPTZero API and saves each raw response. Needs `GPTZERO_API_KEY`, and it spends credits.
- `collect/` downloads the human texts (Wayback Machine, SEC EDGAR and a few other sites) and cuts them into whole
  sentences. `python3 -m collect.check path/to/data` rebuilds texts from the download cache and checks them against the
  dataset's hashes.
- `controls/` has the 118 AI texts I had Qwen3-14B write to match human ones, and the comparison with other detectors
  (Binoculars, Fast-DetectGPT, RADAR, Desklib, Fakespot, OpenAI's RoBERTa, EditLens). Needs a GPU.
- `free_detectors/` scores the four Hugging Face detectors in Table A4.
- `figures/` draws the post's figures.

## Notes

- Not every text came from a script. I collected some of the early ones by hand: the NSF abstracts, the federal
  strategy documents, the Nepali newspapers, the Indian sources and the first Wayback corporate pages. For those, the
  source URL in the dataset is the record. Every scripted text I could check (335 of them) rebuilds exactly.
- A few picks were made by reading, not by a rule, such as which Bear Stearns releases to scan. The collectors list
  those explicitly.
- The other detectors' scores on the 118 pairs aren't in the dataset, so those numbers need a GPU rerun.
- The post's count of 628 windows includes withheld texts. From the released texts you get 384, and all 27 hot windows
  are among them.
- SEC EDGAR wants a name and an email in the User-Agent. Set `SEC_USER_AGENT`.

## Licence

The code is MIT. The dataset is CC BY 4.0, and the texts in it keep their sources' terms. Texts I couldn't release are
listed with their source, first and last words and a hash, so you can fetch them again with `collect/` and check them.

[post]: https://spanthi.com/blog/gptzero-human-writing/
[dataset]: https://huggingface.co/datasets/vein05/gptzero-human-writing
