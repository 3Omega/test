from flask import Flask, render_template
import json
import tls_client
from datetime import datetime
app = Flask(__name__)


@app.route('/')
def index():
    # Load data from JSON file
    with open('data.json', 'r') as json_file:
        data = json.load(json_file)

    matched_players = set(entry['Player'] for entry in data)

    # API Request
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    }

    # API Request using tls_client
    requests_session = tls_client.Session(client_identifier="chrome112")
    response1 = requests_session.get('https://api.prizepicks.com/projections')

    if response1.status_code == 200:
        prizepicks_data = response1.json()
    else:
        prizepicks_data = {}

    # Save data to JSON file
    file_path = "pp.json"
    with open(file_path, "w") as json_file:
        json.dump(prizepicks_data, json_file)

    data_by_league = {}
    previous_player_name = None

    # Add a dictionary to map stat types between API and JSON
    stat_mapping = {
        'Points': 'PTS',
        'FG Made': 'FGM',
        'FG Attempted': 'FGA',
        '3-PT Made': '3PM',
        '3-PT Attempted': '3PA',
        'Free Throws Made': 'FTM',
        'Free Throws Attempted': 'FTA',
        'Offensive Rebounds': 'ORB',
        'Defensive Rebounds': 'DRB',
        'Rebounds': 'REB',
        'Assists': 'AST',
        'Steals': 'STL',
        'Blocked Shots': 'BLK',
        'Turnovers': 'TOV',
        'Personal Fouls': 'PF',
        'Pts+Rebs+Asts': lambda row: row['PTS'] + row['REB'] + row['AST'],
        'Rebs+Asts': lambda row: row['REB'] + row['AST'],
        'Pts+Asts': lambda row: row['PTS'] + row['AST'],
        'Pts+Rebs': lambda row: row['PTS'] + row['REB'],
        'Blks+Stls': lambda row: row['BLK'] + row['STL'],
        # Add more mappings as needed
    }

    def determine_ai_decision(overall_percentage, over5_percentage):
        weights = {'overall': 2.50, 'over5': 0.2, 'over3': 0.3, 'over10': 0.4}
        weighted_avg = (
            weights['overall'] * overall_percentage +
            weights['over5'] * over5_percentage
        )

        if weighted_avg >= 50:
            return 'Over'
        elif weighted_avg <= 50:
            return 'Under'
        else:
            return 'Undecided'

    for projection in prizepicks_data.get("data", []):
        player_id = projection.get("relationships", {}).get(
            "new_player", {}).get("data", {}).get("id", "")
        league_id = projection.get("relationships", {}).get(
            "league", {}).get("data", {}).get("id", "")
        player_name = next((player["attributes"]["name"] for player in prizepicks_data.get("included", [])
                            if player.get("type") == "new_player" and player.get("id") == player_id), "")

        players = [p.strip() for p in player_name.split('+')]
        league = player_name.split(" - ")[0]
        projection_type = projection.get(
            "attributes", {}).get("projection_type", "")
        stat_type = projection.get("attributes", {}).get("stat_type", "")

        # Extract the team name for the player from the JSON data
        player_data = next(
            (entry for entry in data if entry['Player'] == player_name), None)
        if player_data:
            team = player_data['Team']

        line_score = projection.get("attributes", {}).get("line_score", 0.0)

        if all(player in matched_players for player in players):
            pass
        else:
            continue

        if league_id in ['80', '84', '192', '149']:
            continue

        if stat_type in ['Kicking Points', 'Receiving Yards', 'Receiving Yards in First 2 Receptions',
                         'Shots On Goal', 'Fantasy Score', 'Sacks', 'Shots', 'Completions in First 10 Pass Attempts',
                         'Points (Combo)', 'Assists (Combo)', 'Rebounds (Combo)', '3-PT Made (Combo)']:
            continue

        if player_name != previous_player_name:
            data_by_league.setdefault(league, []).append(
                ['', '', '', '', ''])  # Add an extra column for "over %"

        all_dates = [entry['Date']
                     for entry in data if entry['Player'] == player_name]
        all_dates.sort(key=lambda x: datetime.strptime(
            x, '%b %d, %Y'), reverse=True)

        last_5_dates = all_dates[:5]

        player_stat_data = [
            entry for entry in data if entry['Player'] == player_name]

        json_stat_type = stat_mapping.get(stat_type, stat_type)

        agg_stat = [
            stat_mapping[stat_type](entry) if callable(
                stat_mapping.get(stat_type)) else float(entry[json_stat_type])
            for entry in player_stat_data
        ]

        player_stat_data = [
            entry for entry in player_stat_data if entry['Date'] in last_5_dates and float(entry.get(json_stat_type, 0.0)) > line_score
        ]

        player_stat_data = [
            entry for entry in player_stat_data if entry['Date'] in last_5_dates and float(entry[json_stat_type]) > line_score
        ]

        over5_percentage = (len(player_stat_data) /
                            len(last_5_dates)) * 100 if last_5_dates else 0
        player_stat_data_all_dates = [
            entry for entry in player_stat_data if entry['Date'] in all_dates and float(entry[json_stat_type]) > line_score
        ]
        overall_percentage = (
            len(player_stat_data_all_dates) / len(all_dates)) * 100 if all_dates else 0

        ai_decision = determine_ai_decision(
            overall_percentage, over5_percentage
        )

        def format_dates(dates):
            formatted_dates = []
            unique_years = set()

            for date in dates:
                if len(date) == 0:
                    formatted_dates.append('')
                else:
                    date_obj = datetime.strptime(date, '%b %d, %Y')
                    formatted_date = date_obj.strftime('%b %d, %Y')
                    year = formatted_date[-4:]
                    if year not in unique_years:
                        unique_years.add(year)
                    else:
                        # Remove the year if it is the same as the previous date
                        formatted_date = formatted_date[:-6]
                    formatted_dates.append(formatted_date)

            return formatted_dates

        compact_last_5_dates = ', '.join(format_dates(last_5_dates))

        data_by_league.setdefault(league, []).append(
            [player_name, stat_type, team, f"{line_score:.1f}", ai_decision,
                f"{overall_percentage:.1f}%", compact_last_5_dates]
        )
        previous_player_name = player_name

    sorted_leagues = sorted(data_by_league.keys())

    table_data = []
    for league in sorted_leagues:
        if league:
            table_data.extend(data_by_league[league])

    if table_data:
        headers = ["Player", "Stat Type", "Team",
                   "PrizePicks Line", "AI", "L5%", "SZN", "Last 5 days"]
        return render_template('index.html', table_data=table_data, headers=headers)
    else:
        return "Failed to retrieve data from API"


if __name__ == '__main__':
    app.run(debug=True, port=5420, host='0.0.0.0', threaded=True)
