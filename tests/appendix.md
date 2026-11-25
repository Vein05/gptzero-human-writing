### Table A1. What we scanned, and what GPTZero said

Human text written 1902-2020, unchanged. Many Lehman rows are overlapping cuts of the same few releases.

| Kind of text | Scans | Words | Called AI | 75% AI or more | Highest AI probability |
|---|---|---|---|---|---|
| Lehman Brothers releases and filings (1998-2008) | 185 | 78,086 | 11 | 4 | 1.0 |
| Other companies' financial releases: earnings, dividends, reports | 58 | 27,313 | 2 | 0 | 0.59 |
| Science, statistics and government writing | 42 | 23,387 | 0 | 0 | 0.0013 |
| Plain web genres: help pages, self-help, content farms, sample essays, Google Answers, a sports recap | 33 | 23,320 | 0 | 0 | 0.00089 |
| South Asian English: newspapers, government releases, court judgments, journals, books (1902-2019) | 48 | 40,778 | 0 | 0 | 0.00046 |
| Corporate web pages | 24 | 16,117 | 0 | 0 | 0.00018 |
| Student and ESL essays | 110 | 44,097 | 0 | 0 | 0.00015 |
| **All** | **500** | **253,098** | **13** | **4** | |

### Table A2. Same release, different starting sentence (Lehman Q2 2008, unchanged text)

| Text starts at | Words | AI probability |
|---|---|---|
| "Capital Markets reported net ..." | 302 | 0.00021 |
| "Fixed Income Capital Markets ..." | 300 | 0.00015 |
| "Excluding mark to market ..." | 311 | 0.00086 |
| "Equities Capital Markets reported ..." | 324 | 0.11 |
| "Investment Banking reported net ..." | 301 | 1.0 |
| "Debt underwriting revenues were ..." | 312 | 0.59 |
| "Equity underwriting revenues were ..." | 307 | 0.14 |
| "Merger and acquisition advisory ..." | 323 | 0.072 |
| "Investment Management reported net ..." | 313 | 0.00064 |
| "Asset Management revenues were ..." | 305 | 0.00072 |
| "The Firm reported assets ..." | 315 | 0.00091 |
| "Private Investment Management reported ..." | 301 | 0.0015 |
| "Chairman and Chief Executive ..." (750+ words, to the end) | 840 | 0.056 |
| "With these actions and ..." (750+ words, to the end) | 751 | 0.056 |

### Table A3. Is it the words or the numbers? (Lehman Q2 2007; edited copies are tests only)

| Text | AI probability | Mean sentence score |
|---|---|---|
| As published (322 words) | 1.0 | 0.98 |
| Wording: "compared with" changed to "compared to" twice | 1.0 | 0.96 |
| Wording: the previous quarter's reason clause | 1.0 | 0.97 |
| Wording: the previous quarter's word order in the company paragraph | 1.0 | 0.98 |
| Figures: the previous quarter's expense figures | 0.61 | 0.91 |
| Figures: the previous quarter's ratio figures | 1.0 | 0.93 |
| Figures: the previous quarter's capital figures | 1.0 | 0.96 |
| Figures: all of the previous quarter's figures | 0.22 | 0.69 |
| Figures: small random changes to every figure, try 1 | 0.24 | 0.71 |
| Figures: small random changes to every figure, try 2 | 0.1 | 0.50 |
| Figures: small random changes to every figure, try 3 | 0.55 | 0.89 |
| The previous quarter's release, as published | 0.045 | 0.31 |
| The previous quarter's release with this quarter's figures | 0.32 | 0.79 |

### Table A4. Free detectors from Hugging Face on the same human texts

| Detector | Flags as AI (of 388 human texts) | Finds the ones GPTZero calls AI (AUROC) |
|---|---|---|
| tropa-mini | 13% | 0.69 |
| tabularisai | 5% | 0.76 |
| tmr | 95% | 0.66 |
| vanguard | 42% | 0.69 |

GPTZero itself calls 12 of these 388 texts AI (cuts of the Lehman Q2 2007 and Q2 2008 releases, and one Bear Stearns dividend release). AUROC 0.5 is chance.
