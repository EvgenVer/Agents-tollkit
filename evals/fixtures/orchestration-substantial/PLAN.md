# PLAN — Independent ingestion pipelines

Implement the CSV, JSON Lines, and key-value pipelines independently. Each task owns two
production modules and one test module, has a stable contract, and shares no production
files with another task. Run the complete suite after integrating the three tasks.
