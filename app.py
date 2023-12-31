from flask import Flask, render_template
import sqlite3
import tls_client
from tabulate import tabulate

app = Flask(__name__)

# Set up SQLite connection pool
conn = sqlite3.connect("fight_data.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA busy_timeout = 30000")

@app.route('/')
def index():
    # API Request using tls_client
    requests_session = tls_client.Session(client_identifier="chrome112")
    response1 = requests_session.get('https://api.prizepicks.com/projections')

    if response1.status_code == 200:
        prizepicks_data = response1.json()
    else:
        prizepicks_data = {}

    # Mapping between API stat types and corresponding column names in the database
    stat_type_mapping = {
        "Points": "PTS",
        "Rebounds": "REB",
        "Blocks": "BLK",
        "Turnovers": "TOV"
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
            # Assuming your table is named "your_table_name" and columns are named "Player", "Date", and the mapped column name
            table_name = "fight_data"
            player_column_name = "Player"
            date_column_name = "Date"

            # Check if the player is in the database
            query = f"SELECT {player_column_name}, {date_column_name}, {db_column_name} FROM {table_name} WHERE {player_column_name} = ? ORDER BY {date_column_name} ASC LIMIT 5"
            with conn, conn.cursor() as cursor:
                cursor.execute(query, (player_name,))
                db_data = cursor.fetchall()

            if db_data:
                # Extract the latest 5 dates and corresponding values for the player
                latest_data = [(date, value) for _, date, value in db_data]

                # Calculate the percentage of times the player went over the stat line in the last 5 dates
                over_stat_line_count = sum(value > line_score for _, value in latest_data)
                percentage_over_stat_line = (over_stat_line_count / len(latest_data)) * 100

                # Append data to the table
                table_data.append([player_name, stat_type, line_score, ", ".join(date for date, _ in latest_data),
                                   f"{percentage_over_stat_line:.2f}%"])

    # Display data in a tabulate table with the new "Last 5 Dates" and "L5%" columns
    headers = ["Player Name", "Stat Type", "Line Score", "Last 5 Dates", "L5%"]
    table = tabulate(table_data, headers=headers, tablefmt="html")

    return render_template('index.html', table=table)

if __name__ == '__main__':
    app.run(debug=True, port=5200, host='0.0.0.0', threaded=True)
