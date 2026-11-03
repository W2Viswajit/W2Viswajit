"""Render public GitHub contribution counts as a repository-owned SVG."""
import argparse
import datetime as dt
import html
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates, self.counts = {}, {}
        self.tip = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('data-date'):
            self.dates[a['id']] = a['data-date']
        if tag == 'tool-tip':
            self.tip = a.get('for')

    def handle_data(self, data):
        if self.tip and 'contribution' in data:
            match = re.match(r'\s*([\d,]+|No) contributions?\b', data)
            if match:
                self.counts[self.tip] = 0 if match[1] == 'No' else int(match[1].replace(',', ''))

    def handle_endtag(self, tag):
        if tag == 'tool-tip':
            self.tip = None


def get_days(calendar=None):
    if calendar:
        parser = Calendar()
        parser.feed(Path(calendar).read_text(encoding='utf-8'))
        if any(key not in parser.counts for key in parser.dates):
            raise ValueError('Incomplete contribution counts; keeping previous graph')
        return sorted((date, parser.counts[key]) for key, date in parser.dates.items())[-31:]
    token = os.environ['GH_TOKEN']
    owner = os.environ.get('GITHUB_REPOSITORY_OWNER', 'W2Viswajit')
    query = 'query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}'
    payload = json.dumps({'query': query, 'variables': {'login': owner}}).encode()
    request = Request('https://api.github.com/graphql', data=payload, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'W2-profile-activity'})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get('errors'):
        raise ValueError('GitHub could not return contribution data')
    weeks = result['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
    return sorted((day['date'], day['contributionCount']) for week in weeks for day in week['contributionDays'])[-31:]


def render(days):
    if len(days) != 31 or any(count < 0 for _, count in days):
        raise ValueError('Expected 31 days of nonnegative contribution counts')
    dates = [dt.date.fromisoformat(date) for date, _ in days]
    if any((b-a).days != 1 for a,b in zip(dates,dates[1:])):
        raise ValueError('Contribution dates must be consecutive')
    maximum = max(4, max(count for _, count in days))
    top = ((maximum+3)//4)*4
    points = [(62+i*29.2, 236-count/top*146) for i,(_,count) in enumerate(days)]
    total = sum(count for _,count in days)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 300" role="img" aria-labelledby="title desc">',
           '<title id="title">GitHub contribution activity</title>',
           f'<desc id="desc">{total} contributions over 31 days, {days[0][0]} to {days[-1][0]}.</desc>',
           '<rect x="1" y="1" width="998" height="298" rx="14" fill="#0d1117" stroke="#293640"/>',
           '<g font-family="Consolas,monospace">',
           '<text x="34" y="36" fill="#39d98a" font-size="17">$ git activity --last 31d</text>',
           f'<text x="34" y="61" fill="#8b949e" font-size="12">{days[0][0]} / {days[-1][0]} · {total} contributions</text>']
    for j in range(5):
        y = 236-j*36.5
        svg.append(f'<path d="M62 {y}H938" stroke="#212b35"/><text x="46" y="{y+4}" fill="#8b949e" font-size="11" text-anchor="end">{top*j//4}</text>')
    coords=' '.join(f'{x:.1f},{y:.1f}' for x,y in points)
    svg.append(f'<polygon points="62,236 {coords} 938,236" fill="#39d98a" opacity=".09"/>')
    svg.append(f'<polyline points="{coords}" fill="none" stroke="#39d98a" stroke-width="2.5" stroke-linejoin="round"/>')
    for (x,y),(date,count) in zip(points,days):
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#58d5e8"><title>{html.escape(date)}: {count} contributions</title></circle>')
    for i in [0,10,20,30]:
        svg.append(f'<text x="{points[i][0]:.1f}" y="265" fill="#8b949e" font-size="11" text-anchor="middle">{dates[i].strftime("%d %b")}</text>')
    svg.append('</g></svg>')
    return '\n'.join(svg)+'\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--calendar', help='Optional saved public GitHub calendar for initial generation')
    parser.add_argument('--output', default='assets/activity.svg')
    args = parser.parse_args()
    svg = render(get_days(args.calendar))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding='utf-8')
    print('Updated',path)
