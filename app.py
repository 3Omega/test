from flask import Flask, render_template
import json
import sqlite3
import tls_client
from tabulate import tabulate

app = Flask(__name__)

@app.route('/')
def index():
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
    response1 = requests_session.get('https://api.prizepicks.com/projections',headers=headers)

    if response1.status_code == 200:
        prizepicks_data = response1.json()
    else:
        prizepicks_data = {}

    # Save data to JSON file
    file_path = "pp.json"
    with open(file_path, "w") as json_file:
        json.dump(prizepicks_data, json_file)

    # Mapping between API stat types and corresponding column names in the database
    stat_type_mapping = {
        "Points": "PTS",
        "Rebounds": "REB",
        "Blocks" : "BLK",
        "Turnovers" :"TOV"
        # Add more mappings as needed
    }

    # Extract player information from the API response
    table_data = []
    for projection in prizepicks_data.get("data", []):
        player_id = projection.get("relationships", {}).get(
            "new_player", {}).get("data", {}).get("id", "")
        player_name = next((player["attributes"]["name"] for player in prizepicks_data.get("included", [])
                            if player.get("type") == "new_player" and player.get("id") == player_id), "")

        # Additional information from the API
        stat_type = projection.get("attributes", {}).get("stat_type", "")
        line_score = projection.get("attributes", {}).get("line_score", 0.0)

        # Map API stat type to database column name
        db_column_name = stat_type_mapping.get(stat_type, "")

        if db_column_name:
            # Connect to the SQLite database
            db_path = "fight_data.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Assuming your table is named "your_table_name" and columns are named "Player", "Date", and the mapped column name
            table_name = "fight_data"
            player_column_name = "Player"
            date_column_name = "Date"

            # Check if the player is in the database
            query = f"SELECT {player_column_name}, {date_column_name}, {db_column_name} FROM {table_name} WHERE {player_column_name} = ? ORDER BY {date_column_name} ASC LIMIT 5"
            cursor.execute(query, (player_name,))
            db_data = cursor.fetchall()

            if db_data:
                # Extract the latest 5 dates and corresponding values for the player
                latest_data = [(date, value) for _, date, value in db_data]

                # Calculate the percentage of times the player went over the stat line in the last 5 dates
                over_stat_line_count = sum(value > line_score for _, value in latest_data)
                percentage_over_stat_line = (over_stat_line_count / len(latest_data)) * 100

                # Append data to the table
                table_data.append([player_name, stat_type, line_score, ", ".join(date for date, _ in latest_data), f"{percentage_over_stat_line:.2f}%"])

            # Close the database connection
            conn.close()

    # Display data in a tabulate table with the new "Last 5 Dates" and "L5%" columns
    headers = ["Player Name", "Stat Type", "Line Score", "Last 5 Dates", "L5%"]
    table = tabulate(table_data, headers=headers, tablefmt="html")

    return render_template('index.html', table=table)

if __name__ == '__main__':
    app.run(debug=True, threaded=True )
