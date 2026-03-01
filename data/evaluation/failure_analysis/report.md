# Failure Mode Analysis Report

**3 scenarios** | **13 false negatives** | **27 false positives**

## False Negative Distribution

| Category | Count | % | Description |
|----------|-------|---|-------------|
| entity_extraction_gap | 0 | 0% | Entity not in index, can't route |
| routing_miss | 0 | 0% | Input should trigger regulation but didn't |
| retrieval_failure | 13 | 100% | Regulation routed, article not retrieved |
| extraction_failure | 0 | 0% | Article retrieved, requirement not extracted |
| cross_reference_miss | 0 | 0% | Referenced regulation not resolved |

## False Positive Distribution

| Category | Count | % | Description |
|----------|-------|---|-------------|
| tangential_cross_ref | 25 | 93% | Valid from cross-ref regulation, tangential |
| scope_error | 0 | 0% | Applies to different product domain |
| over_extraction | 2 | 7% | Valid requirement, not in ground truth |
| hallucination | 0 | 0% | References unrouted regulation |

## Scenario: fic_labelling_general

### False Negatives (4)

- **FIC-04** [32011R1169 Art 7 general_obligation] → **retrieval_failure**
  32011R1169 Art 7 not in retrieved articles; regulation has Arts [1, 9, 12, 16, 21, 22, 36, 49] retrieved
- **FIC-06** [32011R1169 Art 13 labelling] → **retrieval_failure**
  32011R1169 Art 13 not in retrieved articles; regulation has Arts [1, 9, 12, 16, 21, 22, 36, 49] retrieved
- **FIC-07** [32011R1169 Art 26 labelling] → **retrieval_failure**
  32011R1169 Art 26 not in retrieved articles; regulation has Arts [1, 9, 12, 16, 21, 22, 36, 49] retrieved
- **FIC-08** [32011R1169 Art 17 labelling] → **retrieval_failure**
  32011R1169 Art 17 not in retrieved articles; regulation has Arts [1, 9, 12, 16, 21, 22, 36, 49] retrieved

### False Positives (11)

- [32008R1332 Art 12 labelling] → **tangential_cross_ref** (conf=0.65)
  32008R1332 Art 12 added via cross-reference from 32011R1169, 32018R0848 — valid extraction but tangential to scenario
- [32006R1925 Art 7 labelling] → **tangential_cross_ref** (conf=0.80)
  32006R1925 Art 7 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario
- [32006R1925 Art 15 notification] → **tangential_cross_ref** (conf=0.70)
  32006R1925 Art 15 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario
- [32015R2283 Art 14 notification] → **tangential_cross_ref** (conf=0.60)
  32015R2283 Art 14 added via cross-reference from 32011R1169, 32018R0848 — valid extraction but tangential to scenario
- [32015R2283 Art 25 notification] → **tangential_cross_ref** (conf=0.75)
  32015R2283 Art 25 added via cross-reference from 32011R1169, 32018R0848 — valid extraction but tangential to scenario
- [32004R0853 Art 5 labelling] → **tangential_cross_ref** (conf=0.70)
  32004R0853 Art 5 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario
- [32004R0852 Art 10 hygiene] → **tangential_cross_ref** (conf=0.80)
  32004R0852 Art 10 added via cross-reference from 32011R1169, 32018R0848 — valid extraction but tangential to scenario
- [32003R1830 Art 5 traceability] → **tangential_cross_ref** (conf=0.70)
  32003R1830 Art 5 added via cross-reference from 32018R0848 — valid extraction but tangential to scenario
- [32003R1830 Art 4 labelling] → **tangential_cross_ref** (conf=0.70)
  32003R1830 Art 4 added via cross-reference from 32018R0848 — valid extraction but tangential to scenario
- [32004R0852 Art 11 hygiene] → **tangential_cross_ref** (conf=0.80)
  32004R0852 Art 11 added via cross-reference from 32011R1169, 32018R0848 — valid extraction but tangential to scenario
- [32004R0853 Art 3 hygiene] → **tangential_cross_ref** (conf=0.70)
  32004R0853 Art 3 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario

## Scenario: food_supplement_vitamin_d

### False Negatives (4)

- **FS-01** [32002L0046 Art 3 general_obligation] → **retrieval_failure**
  32002L0046 Art 3 not in retrieved articles; regulation has Arts [2, 5, 6, 7, 8] retrieved
- **FS-04** [32006R1924 Art 3 general_obligation] → **retrieval_failure**
  32006R1924 Art 3 not in retrieved articles; regulation has Arts [7, 10] retrieved
- **FS-07** [32006R1925 Art 3 general_obligation] → **retrieval_failure**
  32006R1925 Art 3 not in retrieved articles; regulation has Arts [6, 7] retrieved
- **FS-08** [32002R0178 Art 18 traceability] → **retrieval_failure**
  32002R0178 Art 18 not in retrieved articles; regulation has Arts [14, 21] retrieved

### False Positives (4)

- [32011R1169 Art 50 labelling] → **over_extraction** (conf=0.85)
  32011R1169 Art 50 labelling: valid extraction not covered by ground truth (conf=0.85)
- [32008R0353 Art 6 documentation] → **over_extraction** (conf=0.80)
  32008R0353 Art 6 documentation: valid extraction not covered by ground truth (conf=0.80)
- [32015R2283 Art 7 authorisation] → **tangential_cross_ref** (conf=0.75)
  32015R2283 Art 7 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario
- [32008R1333 Art 24 labelling] → **tangential_cross_ref** (conf=0.70)
  32008R1333 Art 24 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario

## Scenario: novel_food_insect_protein

### False Negatives (5)

- **NF-01** [32015R2283 Art 6 authorisation] → **retrieval_failure**
  32015R2283 Art 6 not in retrieved articles; regulation has Arts [10, 25] retrieved
- **NF-02** [32015R2283 Art 7 safety_assessment] → **retrieval_failure**
  32015R2283 Art 7 not in retrieved articles; regulation has Arts [10, 25] retrieved
- **NF-04** [32015R2283 Art 9 labelling] → **retrieval_failure**
  32015R2283 Art 9 not in retrieved articles; regulation has Arts [10, 25] retrieved
- **NF-07** [32002R0178 Art 14 general_obligation] → **retrieval_failure**
  32002R0178 Art 14 not in retrieved articles; regulation has Arts [16, 18] retrieved
- **NF-08** [32011R1169 Art 9 labelling] → **retrieval_failure**
  32011R1169 Art 9 not in retrieved articles; regulation has Arts [1, 6] retrieved

### False Positives (12)

- [32008R1332 Art 11 labelling] → **tangential_cross_ref** (conf=0.35)
  32008R1332 Art 11 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario
- [32008R1332 Art 12 labelling] → **tangential_cross_ref** (conf=0.30)
  32008R1332 Art 12 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario
- [32003R1829 Art 13 labelling] → **tangential_cross_ref** (conf=0.45)
  32003R1829 Art 13 added via cross-reference from 32015R2283 — valid extraction but tangential to scenario
- [32003R1829 Art 25 labelling] → **tangential_cross_ref** (conf=0.15)
  32003R1829 Art 25 added via cross-reference from 32015R2283 — valid extraction but tangential to scenario
- [32008R1332 Art 10 labelling] → **tangential_cross_ref** (conf=0.30)
  32008R1332 Art 10 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario
- [32003R1829 Art 4 authorisation] → **tangential_cross_ref** (conf=0.40)
  32003R1829 Art 4 added via cross-reference from 32015R2283 — valid extraction but tangential to scenario
- [32008R1333 Art 24 labelling] → **tangential_cross_ref** (conf=0.55)
  32008R1333 Art 24 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario
- [32006R1924 Art 25 notification] → **tangential_cross_ref** (conf=0.55)
  32006R1924 Art 25 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario
- [32006R1925 Art 7 labelling] → **tangential_cross_ref** (conf=0.60)
  32006R1925 Art 7 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario
- [32004R0853 Art 5 labelling] → **tangential_cross_ref** (conf=0.45)
  32004R0853 Art 5 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario
- [32004R0853 Art 7 documentation] → **tangential_cross_ref** (conf=0.40)
  32004R0853 Art 7 added via cross-reference from 32011R1169 — valid extraction but tangential to scenario
- [32006R1925 Art 15 notification] → **tangential_cross_ref** (conf=0.50)
  32006R1925 Art 15 added via cross-reference from 32011R1169, 32015R2283 — valid extraction but tangential to scenario

## Key Findings

1. **Zero hallucinations.** The system never invents regulations or requirements outside the routed set.
2. **retrieval_failure is the primary FN cause** (13/13, 100%). 
3. **tangential_cross_ref is the primary FP cause** (25/27, 93%).
