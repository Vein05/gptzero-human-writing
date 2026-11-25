"""ClinicalTrials.gov detailed descriptions of studies last updated in 2020 or earlier (API v2), so the current text is
the pre-2021 text; each study's history page gives the dated version.

    python3 -m collect.clinical_trials OUT.jsonl

Keeps descriptions of 750-1,200 words. The API returns the text in Markdown (records were converted in 2023), so a
text should be compared with the dated version on the history page before it is used as dated evidence.
"""

import json
import sys
import urllib.parse

from collect.fetch import fetch

API = "https://clinicaltrials.gov/api/v2/studies?"
QUERY = {
    "filter.advanced": "AREA[LastUpdatePostDate]RANGE[MIN,2020-12-31]",
    "pageSize": "1000",
    "format": "json",
    "fields": "NCTId,BriefTitle,DetailedDescription,LastUpdatePostDate,StudyFirstPostDate,LeadSponsorName",
}
MIN_WORDS, MAX_WORDS = 750, 1200


def description(study):
    """One output row for a study whose description has 750-1,200 words, else None."""
    p = study.get("protocolSection", {})
    text = p.get("descriptionModule", {}).get("detailedDescription", "")
    if not MIN_WORDS <= len(text.split()) <= MAX_WORDS:
        return None
    nct = p["identificationModule"]["nctId"]
    status = p.get("statusModule", {})
    return {
        "nct": nct,
        "title": p["identificationModule"].get("briefTitle", ""),
        "sponsor": p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
        "first_posted": status.get("studyFirstPostDateStruct", {}).get("date", ""),
        "last_update": status.get("lastUpdatePostDateStruct", {}).get("date", ""),
        "source": f"https://clinicaltrials.gov/study/{nct}?tab=history",
        "text": text,
    }


def main():
    token, kept = None, 0
    with open(sys.argv[1], "w") as f:
        while True:
            page = json.loads(fetch(API + urllib.parse.urlencode(QUERY | ({"pageToken": token} if token else {}))))
            for row in filter(None, map(description, page.get("studies", []))):
                f.write(json.dumps(row) + "\n")
                kept += 1
            token = page.get("nextPageToken")
            print(kept, "kept", flush=True)
            if not token:
                break


if __name__ == "__main__":
    main()
