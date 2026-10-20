# Ohio early-vote data extraction spec

Use the MCP tool `mcp__Google_Cloud_BigQuery__execute_sql_readonly` with projectId `coldspark-voterdata`,
timeoutMs 180000. Results are capped at 3,000 rows: if a query returns exactly 3000 rows, split its
county range further and re-run. Write output files as compact JSON (no pretty printing) into
/tmp/claude-0/-home-claude/56ba9409-63fb-5245-89b4-6688db412ff2/scratchpad/ohio/data/ .
Large tool results are saved by the harness to a file; convert those with a Python script (never retype).
After writing, re-read the file and spot-check 3 rows against the query output.

## Year parameters

| year | abev table | voter file table | Election Day |
|---|---|---|---|
| 2026 | `coldspark-voterdata.national_file.abev_2026` | `coldspark-voterdata.national_file.voters` | 2026-11-03 |
| 2024 | `coldspark-voterdata.national_file.abev_2024` | `coldspark-voterdata.national_file.voterfile_2024` | 2024-11-05 |
| 2022 | `coldspark-voterdata.national_file.abev_2022` | `coldspark-voterdata.national_file.voterfile_2022` | 2022-11-08 |

## Common CTE (substitute ABEV, VF, ED, YEAR)

```sql
WITH a AS (
  SELECT
    REGEXP_REPLACE(REPLACE(UPPER(a.Jurisname), 'LAWERENCE', 'LAWRENCE'), ' COUNTY$', '') AS county,
    a.RequestDate, a.ReturnDate, a.EarlyVoted, a.Rejected,
    CASE v.PartyRollUp WHEN 'Republican' THEN 'R' WHEN 'Democrat' THEN 'D' ELSE 'O' END AS party
  FROM `ABEV` a
  LEFT JOIN `VF` v ON v.DT_Regid = a.DT_Regid AND v.State = 'OH'
  WHERE a.State = 'OH'
),
u AS (
  SELECT county, 'req' AS m, DATE_DIFF(DATE 'ED', RequestDate, DAY) AS d, party FROM a
    WHERE Rejected = 0 AND RequestDate BETWEEN DATE 'YEAR-01-01' AND DATE 'YEAR-12-31'
  UNION ALL
  SELECT county, 'ret', DATE_DIFF(DATE 'ED', ReturnDate, DAY), party FROM a
    WHERE Rejected = 0 AND ReturnDate BETWEEN DATE 'YEAR-01-01' AND DATE 'YEAR-12-31'
  UNION ALL
  SELECT county, 'eip', DATE_DIFF(DATE 'ED', EarlyVoted, DAY), party FROM a
    WHERE EarlyVoted BETWEEN DATE 'YEAR-01-01' AND DATE 'YEAR-12-31'
)
```

## Query S — statewide daily (one per year)

```sql
<CTE>
SELECT d,
  COUNTIF(m='req' AND party='R') reqR, COUNTIF(m='req' AND party='D') reqD, COUNTIF(m='req' AND party='O') reqO,
  COUNTIF(m='ret' AND party='R') retR, COUNTIF(m='ret' AND party='D') retD, COUNTIF(m='ret' AND party='O') retO,
  COUNTIF(m='eip' AND party='R') eipR, COUNTIF(m='eip' AND party='D') eipD, COUNTIF(m='eip' AND party='O') eipO
FROM u WHERE d BETWEEN -14 AND 60 GROUP BY d ORDER BY d
```
Also, per year, run a totals query:
`SELECT COUNT(*) rows_total, COUNTIF(a.Rejected=1) rejected_rows, COUNTIF(v.DT_Regid IS NULL) unmatched_rows FROM ABEV a LEFT JOIN VF v ON v.DT_Regid = a.DT_Regid AND v.State='OH' WHERE a.State='OH'`.

Output `daily.json`:
```json
{"2026":{"rows":[[d,reqR,reqD,reqO,retR,retD,retO,eipR,eipD,eipO],...],"rows_total":N,"rejected_rows":N,"unmatched_rows":N},
 "2024":{...},"2022":{...}}
```

## Query C — county daily (one per year, chunked by county range)

```sql
<CTE>
SELECT county, d, <same 9 COUNTIF columns as Query S>
FROM u WHERE d BETWEEN -14 AND 60 AND county >= 'LO' AND county < 'S'   -- chunk
GROUP BY county, d ORDER BY county, d
```
Suggested chunks (county is the stripped upper-case name): `< 'F'`, `>= 'F' AND < 'LO'`, `>= 'LO' AND < 'S'`, `>= 'S'`.
Output `county_daily_YEAR.json`: `{"COUNTY":[[d,reqR,...,eipO],...], ...}` (88 counties).

## Query P — precinct level, 2026 only (chunked by county range)

```sql
SELECT UPPER(v.CountyName) county, v.PrecinctCode precinct,
  COUNTIF(party='R') regR, COUNTIF(party='D') regD, COUNTIF(party='O') regO,
  COUNTIF(a.Rejected=0 AND a.RequestDate IS NOT NULL AND party='R') reqR,
  COUNTIF(a.Rejected=0 AND a.RequestDate IS NOT NULL AND party='D') reqD,
  COUNTIF(a.Rejected=0 AND a.RequestDate IS NOT NULL AND party='O') reqO,
  COUNTIF(a.Rejected=0 AND a.ReturnDate IS NOT NULL AND party='R') retR,
  COUNTIF(a.Rejected=0 AND a.ReturnDate IS NOT NULL AND party='D') retD,
  COUNTIF(a.Rejected=0 AND a.ReturnDate IS NOT NULL AND party='O') retO,
  COUNTIF(a.EarlyVoted IS NOT NULL AND party='R') eipR,
  COUNTIF(a.EarlyVoted IS NOT NULL AND party='D') eipD,
  COUNTIF(a.EarlyVoted IS NOT NULL AND party='O') eipO
FROM (
  SELECT DT_Regid, CountyName, PrecinctCode,
    CASE PartyRollUp WHEN 'Republican' THEN 'R' WHEN 'Democrat' THEN 'D' ELSE 'O' END AS party
  FROM `coldspark-voterdata.national_file.voters`
  WHERE State='OH' AND UPPER(CountyName) >= 'CR' AND UPPER(CountyName) < 'G'   -- chunk
) v
LEFT JOIN `coldspark-voterdata.national_file.abev_2026` a ON a.DT_Regid = v.DT_Regid AND a.State='OH'
GROUP BY 1,2 ORDER BY 1,2
```
Suggested chunks: `< 'CR'`, `>= 'CR' AND < 'G'`, `>= 'G' AND < 'M'`, `>= 'M' AND < 'S'`, `>= 'S'`. Split further if any returns 3000 rows.
Output `precinct_2026.json`: `{"COUNTY":[["precinctCode",regR,regD,regO,reqR,reqD,reqO,retR,retD,retO,eipR,eipD,eipO],...],...}`.
Precinct code may be NULL → use "" .
