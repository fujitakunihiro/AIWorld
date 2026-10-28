# Paris Métro line 4 prototype

Cité and Saint-Michel stations and one entrance at each station are located from OpenStreetMap; their IDs, WGS84 coordinates and API URL are in `unreal/AIWorld/Content/Data/paris-metro.json` (© OpenStreetMap contributors, ODbL). [RATP confirms Cité is the nearest station to Notre-Dame and is on line 4](https://www.ratp.fr/visiter-paris/lieux/notre-dame); [its line map](https://www.ratp.fr/informer/picts/plans/pdf/reseaux/m4.pdf) shows Cité and Saint-Michel adjacent.

The underground platforms, the 300 m stage depth, the straight line between stations, train design and journey time are inferred gameplay prototypes. They are not a surveyed reconstruction, the station entrances are simplified above-ground markers, and moving from street to platform is a teleport, not a stairway. There is no timetable, actual RATP branding, live service or real vehicle model. RATP service changes are deliberately not simulated.

Run `Paris-Metro.cmd` or `unreal/scripts/Start-ParisDigitalTwin.ps1 -MetroView -Quality Medium`. K enters the nearest station from the street or exits the station to the street; L boards and automatically starts the train, and L again after arrival leaves the train onto the destination platform. WASD and the mouse are available when walking on the platform; F2 returns to the city overview. K is blocked during a train ride so the player cannot be dropped into the tunnel.

`unreal/scripts/Test-ParisDigitalTwin.ps1 -Photoreal` includes the MetroTravel Unreal test for platform collision, boarding, bounded travel, arrival, leaving the train, and returning to the street. This prototype reuses built-in materials and procedural meshes; no paid or external 3D assets are required.
