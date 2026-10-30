# Historical source binding before benchmark scores

The three original workbooks were captured once after protocol commit `eb549dfe750318ad0526ab0422a2d5bf70410b5e`. Their bytes remain private and unchanged. This is a post-capture, pre-score binding, not an untouched schema preregistration.

## What was inspected

The first inspection read names, dimensions and the first 12 rows of each sheet in the 2022–2023 file. It therefore exposed 11 example data rows as well as headers, including some unrelated futures values. Those values remain private and are excluded from the projection. No benchmark scores or target-pair selection were computed. Primary-source searches also exposed May/July 2024 and August 16, 2024 report excerpts, including some later-cohort prices. There is no analyst-blindness claim; the deterministic rules and thresholds will not be selected or tuned.

The older headline sheet already has `31-3-35` as well as `41-4-34`. The October 2024 announcement specifies `31/3/36` in the August 2025 format. It does not establish that the older report had only one quality. The authored one-row-to-two-row expansion tests an ingestion failure mechanism; it is not a reconstruction of the actual format transition or evidence of actual transition incidents.

## Exact columns and meaning

Read only the `C-L-S` sheet for the planned quotations. Columns A–I are `Source.Name`, `Date`, `Type`, `Market`, `Color`, `Leaf`, `Staple`, `Difference`, `Physical Price`. Keep the exact source tokens, original row and cell references, native types and formula/cache states. Match only `Type=Upland` and exact color/leaf/staple strings `41/4/34` or `31/3/36`. Do not split grouped tokens or substitute headline `31/3/35` for planned `31/3/36`.

Use the supplied `Physical Price` in cents per pound, not `Difference`, basis or ICE futures. The archived USDA May 10, 2024 report identifies the physical spot quotations in cents per pound and distinguishes the futures settlement section. Its common spot quotation convention is net weight in mixed lots, FOB car/truck including compression and brokerage. Its base has mike 3.5, 3.6 and 4.3–4.9, strength 27.0–28.9 grams per tex and uniformity 81.0–81.9. The C-L-S comparison uses that report's base convention for other factors; it is a comparison of quoted grid definitions, not physical-bale equivalence or a claim that all these attributes are recorded per transaction. Retain this convention identifier in the quote identity. Cross-check the 41/4/34 grid quotations against the separate `Basis and Bales` base-price column before analysis; do not reconstruct them from futures or differences.

Only seven exact native market labels qualify: Southeast, North Delta, South Delta, East TX-OK, West Texas, Desert SW and SJ Valley. Report any unexpected labels without inventing a crosswalk. The historical names are retained and are not silently renamed to current region labels.

## Reader precision and checks

Native XLSX numeric tokens can contain more digits than a displayed monetary value. To retain those exact decimal tokens, the projection streams raw OOXML cells; Openpyxl independently checks every selected original row, cell type, date interpretation and numeric conversion. This reverses the originally proposed reader order before any projection or score. No monetary rounding or favorable tolerance enters the benchmark: its fractions use native decimal tokens. Formula cells are unavailable, even if cached. Dates use the workbook's recorded epoch, with raw serials retained. Missing and error cells remain explicit.

The original row universe is scanned for the two exact grade definitions. Keep all matches and exclusion reasons; preserve identical and conflicting copies. Source gates and the fixed earlier/later split remain as written in the protocol. No held metric may run before a committed dependency freeze.

## Rights evidence

The USDA digital-rights page was readable through the web source tool; a separate direct HTTP capture returned 403 and is retained without retry. Its public-domain rule includes marked third-party exceptions. Only attributed USDA-produced spot-quotation facts and new calculations may be projected. No complete source workbook, report PDF, website body, futures value, source logo or contact is published.

Sources: [October 2024 announcement](https://content.govdelivery.com/accounts/USDAAMS/bulletins/3bd797d), [historical workbook directory](https://apps.ams.usda.gov/Cotton/HistoricalUplandPrices/), [May 10, 2024 USDA report](https://downloads.usda.library.cornell.edu/usda-esmis/files/gb19f580q/t722jz84c/3t947d25s/CNDDSQ.PDF), [USDA rights policy](https://www.usda.gov/about-usda/policies-and-links).
