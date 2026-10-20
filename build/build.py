#!/usr/bin/env python3
"""Assemble the Ohio Early Vote dashboard: template.html + data/*.json -> dashboard.html (+ index.html)

Usage: python3 build.py [data_dir] [out_file]
Expects in data_dir: daily.json, county_daily_2026.json, county_daily_2024.json,
county_daily_2022.json, precinct_2026.json (formats in SPEC.md) and ohio_counties.json.
Writes dashboard.html (body-only, for the Artifact tool, which adds the page skeleton) and
index.html (the same content wrapped in a full HTML document, for GitHub Pages).
"""
import json, sys, os, datetime

here = os.path.dirname(os.path.abspath(__file__))
data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'data')
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, 'dashboard.html')

ED = {'2026': '2026-11-03', '2024': '2024-11-05', '2022': '2022-11-08'}

def load(name):
    with open(os.path.join(data_dir, name)) as f:
        return json.load(f)

daily = load('daily.json')
county = {y: load(f'county_daily_{y}.json') for y in ('2026', '2024', '2022')}
precinct = load('precinct_2026.json')
geo = load('ohio_counties.json')  # static: Ohio county outlines as SVG paths (made by geo/make_geo.py)

# As-of = last complete day in 2026: smallest d whose returns+EIP exceed 500.
rows26 = sorted(daily['2026']['rows'])
asof_d = None
for r in rows26:
    if sum(r[4:10]) > 500:
        asof_d = r[0]; break
if asof_d is None:
    raise SystemExit('could not determine as-of day')
ed26 = datetime.date.fromisoformat(ED['2026'])
asof_date = ed26 - datetime.timedelta(days=asof_d)

# Partial-day rows dropped from headline figures (d < asof_d)
partial = [r for r in rows26 if r[0] < asof_d]
partial_tot = [sum(r[i] for r in partial) for i in range(1, 10)]

# Sanity: county sums should match statewide
for y in county:
    s = [0]*9
    for rows in county[y].values():
        for r in rows:
            for i in range(9): s[i] += r[i+1]
    t = [sum(r[i+1] for r in daily[y]['rows']) for i in range(9)]
    if s != t:
        print(f'WARNING {y}: county sums {s} != statewide {t}', file=sys.stderr)
assert len(precinct) == 88 and all(len(county[y]) == 88 for y in county)

payload = {
    'ed': ED,
    'asof': {'d': asof_d, 'date': asof_date.isoformat()},
    'partial': partial_tot,
    'meta': {y: {k: v for k, v in daily[y].items() if k != 'rows'} for y in daily},
    'daily': {y: sorted(daily[y]['rows']) for y in daily},
    'county': county,
    'precinct': precinct,
    'geo': geo,
    'built': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
}

with open(os.path.join(here, 'template.html')) as f:
    tpl = f.read()
js = json.dumps(payload, separators=(',', ':')).replace('</', '<\\/')
assert '/*__DATA__*/' in tpl and '/*__JS__*/' in tpl
with open(os.path.join(here, 'app.js')) as f:
    appjs = f.read()
html = tpl.replace('/*__DATA__*/', js).replace('/*__JS__*/', appjs)
with open(out, 'w') as f:
    f.write(html)

# Standalone copy for GitHub Pages (ohio.coldspark.com)
index = os.path.join(os.path.dirname(out), 'index.html')
with open(index, 'w') as f:
    f.write('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '</head>\n<body>\n' + html + '\n</body>\n</html>\n')
print(f'wrote {out} ({len(html)/1e6:.2f} MB) and {index}; as of {asof_date} (d={asof_d}); partial-day rows dropped: {partial_tot}')
