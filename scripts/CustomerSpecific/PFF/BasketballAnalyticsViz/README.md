# Basketball Analytics Visualization Prototype

This is a rapid prototype for visualizing basketball tracking data with player statistics. The visualization displays:

- Player positions with IDs and markers
- Speed and distance metrics for each player
- Ball movement tracking
- Team scores and statistics
- Possession percentages
- Event markers on the court

## Requirements

- Python 3.7+
- Flask

## Installation

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000/
   ```

## Features

- **Player Tracking**: Shows player positions with unique IDs and team colors
- **Metrics Display**: Shows speed (km/h) and distance (m) for each tracked player
- **Team Statistics**: Displays team scores, passes, interceptions, and possession percentages
- **Court Visualization**: Basketball court with visual markers for events
- **Minimap**: Small court diagram in the corner showing player positions

## Future Enhancements

- Add frame-by-frame playback controls
- Implement player tracking from video input
- Add heatmap visualization for player movement
- Support for multiple camera angles
- Advanced statistics and event detection