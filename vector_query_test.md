# Vector Query Test

## Test Question
**Question:**
Which insurance plan has the lowest monthly premium?

**Expected Answer:**
Bronze HMO (Plan ID: P103) has the lowest monthly premium of 150.

---

## Silver Plan Scope

**Question:**
Show details of the Silver HMO plan.

**Expected Result:**
- Plan ID: P102
- Plan Name: Silver HMO
- Monthly Premium: 300
- Annual Deductible: 1500
- Coverage Type: HMO
- Network Tier: Silver

---

## Collection Count Check

Expected collection count:

6 documents

---

## Metadata Filtering

Example metadata fields:

- source_file
- source_type
- plan_type
- section

Metadata can be used to filter documents during vector search.

---

## Result

The vector database was successfully created using ChromaDB.

Embeddings were generated successfully.

All 6 documents were indexed successfully.