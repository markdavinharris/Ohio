# Ohio — projected final electorate (gated panel)

Same model as Texas, North Carolina, Georgia and Florida (full write-up in `claude/texas-ev-dashboard/PROJECTION.md`).
Cells = ModeledParty x habit (E/D/N from the last two generals' vote method) x general-election frequency (0-3) x
primary (R/D/N). For each cell the share of the final vote still to come after day d is learned from a past year
(shrunk toward parent cells, 500-voter prior) and scaled by k = (2026 cell early rate / training-year rate)^alpha.
Central: train 2022 on current-file labels (voters, RegistrationYear <= 2022), alpha 0.5. Range: train {2022, 2024} x
alpha {0.25, 0.5, 0.75}. Shown as GOP-Dem points (HardGOP+SoftGOP minus HardDem+SoftDem; Swing in the base).

## Daily step
Run the three queries below with ASOF replaced by the page's as-of day number (the d build.py reports; it must match),
each result saved to a file by the harness (the pad column makes sure), then
`python3 make_proj.py data/proj.json OH ASOF bq/M_2022.json bq/M_2024.json bq/M_2026.json`.
build.py shows the panel only when proj.json's day equals the page's day; otherwise it hides it.
Then record the day in the Electorate projection tracker: `claude/projection-tracker/RECORD.md`, "Daily step".

First build: Ohio: early voting opened 2026-10-06; on 2026-10-24 (data through Oct 22, ASOF 12) early D+7.0 -> projected R+11.0 (R+6.7 to R+12.2). Backtest at d=12: train 2022 -> test 2024 model off by 2.0 (raw early vote off by 2.6); 2024 -> 2022 off by 7.2 (raw 17.2).

### Query M, 2022 (training year; current voters file, registered by 2022)
```sql
WITH a AS (
  SELECT DT_Regid, MAX(DATE_DIFF(DATE '2022-11-08', LEAST(IFNULL(EarlyVoted, DATE '2099-01-01'), IFNULL(IF(Rejected=0, ReturnDate, NULL), DATE '2099-01-01')), DAY)) dbe
  FROM `coldspark-voterdata.national_file.abev_2022`
  WHERE State='OH' AND (EarlyVoted IS NOT NULL OR (ReturnDate IS NOT NULL AND Rejected=0)) AND DT_Regid<>''
  GROUP BY 1 HAVING dbe BETWEEN 0 AND 60
), v AS (
  SELECT f.State st, f.ModeledParty party,
   CASE WHEN VH20G IN ('2','7') THEN 'E' WHEN VH20G='1' THEN 'D' WHEN VH18G IN ('2','7') THEN 'E' WHEN VH18G='1' THEN 'D' ELSE 'N' END habit,
   IF(VH20G IS NOT NULL,1,0)+IF(VH18G IS NOT NULL,1,0)+IF(VH16G IS NOT NULL,1,0) freq,
   CASE WHEN COALESCE(VH22P,VH20P) IN ('3','4','8') THEN 'R' WHEN COALESCE(VH22P,VH20P) IN ('5','6','9') THEN 'D' ELSE 'N' END prim,
   VH22G IS NOT NULL OR a.dbe IS NOT NULL fin, a.dbe
  FROM `coldspark-voterdata.national_file.voters` f LEFT JOIN a USING (DT_Regid)
  WHERE f.State='OH' AND (f.RegistrationYear IS NULL OR f.RegistrationYear<=2022))
SELECT st,party,habit,freq,prim, COUNT(*) n, COUNTIF(fin) fin, COUNTIF(dbe>=ASOF) eASOF, REPEAT('x',300) pad
FROM v GROUP BY 1,2,3,4,5
```

### Query M, 2024 (training year; voterfile_2024)
```sql
WITH a AS (
  SELECT DT_Regid, MAX(DATE_DIFF(DATE '2024-11-05', LEAST(IFNULL(EarlyVoted, DATE '2099-01-01'), IFNULL(IF(Rejected=0, ReturnDate, NULL), DATE '2099-01-01')), DAY)) dbe
  FROM `coldspark-voterdata.national_file.abev_2024`
  WHERE State='OH' AND (EarlyVoted IS NOT NULL OR (ReturnDate IS NOT NULL AND Rejected=0)) AND DT_Regid<>''
  GROUP BY 1 HAVING dbe BETWEEN 0 AND 60
), v AS (
  SELECT f.State st, f.ModeledParty party,
   CASE WHEN VH22G IN ('2','7') THEN 'E' WHEN VH22G='1' THEN 'D' WHEN VH20G IN ('2','7') THEN 'E' WHEN VH20G='1' THEN 'D' ELSE 'N' END habit,
   IF(VH22G IS NOT NULL,1,0)+IF(VH20G IS NOT NULL,1,0)+IF(VH18G IS NOT NULL,1,0) freq,
   CASE WHEN COALESCE(VH24P,VH22P) IN ('3','4','8') THEN 'R' WHEN COALESCE(VH24P,VH22P) IN ('5','6','9') THEN 'D' ELSE 'N' END prim,
   VH24G IS NOT NULL OR a.dbe IS NOT NULL fin, a.dbe
  FROM `coldspark-voterdata.national_file.voterfile_2024` f LEFT JOIN a USING (DT_Regid)
  WHERE f.State='OH')
SELECT st,party,habit,freq,prim, COUNT(*) n, COUNTIF(fin) fin, COUNTIF(dbe>=ASOF) eASOF, REPEAT('x',300) pad
FROM v GROUP BY 1,2,3,4,5
```

### Query M, 2026 (this year)
```sql
WITH a AS (
  SELECT DT_Regid, MAX(DATE_DIFF(DATE '2026-11-03', LEAST(IFNULL(EarlyVoted, DATE '2099-01-01'), IFNULL(IF(Rejected=0, ReturnDate, NULL), DATE '2099-01-01')), DAY)) dbe
  FROM `coldspark-voterdata.national_file.abev_2026`
  WHERE State='OH' AND (EarlyVoted IS NOT NULL OR (ReturnDate IS NOT NULL AND Rejected=0)) AND DT_Regid<>''
  GROUP BY 1 HAVING dbe BETWEEN ASOF AND 60
), v AS (
  SELECT f.State st, f.ModeledParty party,
   CASE WHEN VH24G IN ('2','7') THEN 'E' WHEN VH24G='1' THEN 'D' WHEN VH22G IN ('2','7') THEN 'E' WHEN VH22G='1' THEN 'D' ELSE 'N' END habit,
   IF(VH24G IS NOT NULL,1,0)+IF(VH22G IS NOT NULL,1,0)+IF(VH20G IS NOT NULL,1,0) freq,
   CASE WHEN COALESCE(VH26P,VH24P) IN ('3','4','8') THEN 'R' WHEN COALESCE(VH26P,VH24P) IN ('5','6','9') THEN 'D' ELSE 'N' END prim,
   FALSE fin, a.dbe
  FROM `coldspark-voterdata.national_file.voters` f LEFT JOIN a USING (DT_Regid)
  WHERE f.State='OH')
SELECT st,party,habit,freq,prim, COUNT(*) n, COUNTIF(fin) fin, COUNTIF(dbe>=ASOF) eASOF, REPEAT('x',300) pad
FROM v GROUP BY 1,2,3,4,5
```
