from scholarly import scholarly
import requests

# Your Google Scholar Profile ID
USER_ID = "NsOqVtkAAAAJ"

# Get Google Scholar Profile
author = scholarly.search_author_id(USER_ID)
scholarly.fill(author)

# Extract BibTeX for each paper
bibtex_entries = []
for pub in author["publications"]:
    if "bib" in pub:
        scholarly.fill(pub)
        bibtex_entries.append(pub["bib"])

# Save to bibtex file
bibtex_content = "\n\n".join([entry["bibtex"] for entry in bibtex_entries])
with open("bibliography.bib", "w", encoding="utf-8") as f:
    f.write(bibtex_content)

print("Updated BibTeX file saved.")