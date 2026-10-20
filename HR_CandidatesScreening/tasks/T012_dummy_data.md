# T012 - Generate dummy data package for local demo

## Goal
Produce a fictional test data package for the Candidate Screening agent, so it can be run on a laptop against Vertex AI.

## Inputs
- ~/candidates_screening/screening_agent/create_dummy_data.py (already on this server)

## Steps (work only inside ~/candidates_screening)
1. cd ~/candidates_screening/screening_agent
2. Run: .venv/bin/python create_dummy_data.py
   (it writes data/job_advert.docx and three fictional candidate folders under data/applications/)
3. Create ~/candidates_screening/demo/ and zip the data folder into ~/candidates_screening/demo/dummy_data.zip
   Include only data/ (job_advert.docx and applications/). Do NOT include .env, .venv, output/ or any key file.
4. Write ~/candidates_screening/demo/MANIFEST.txt listing every file in the zip with its size and sha256.

## Rules
- All data is fictional. No real names, contacts or personal information.
- Never write API keys, tokens or client secrets into any file.
- Do not touch any folder outside ~/candidates_screening.

## Done means
- demo/dummy_data.zip exists and contains job_advert.docx plus exactly 3 candidate folders.
- demo/MANIFEST.txt exists and matches the zip contents.
- Final summary gives the zip path and the file list.
