PARK PATROL

[Probabilistic Crowdsourced Parking Predictor & Spatial Management System]


Live site: https://parkpatrol.onrender.com/

Park Patrol is a web app that shows which parking spots are free in a simulated parking lot, so drivers can check before they drive in. A camera detects spots that are taken, updates the dashboard every few seconds, and flags double-parked cars to campus security. Signing in requires a DLSL Google account and can subscribe to Telegram alerts for when a spot opens.


Leader: Lindain, Domnick Jullien
Members: Jumarang, Kyer Jairus
       : Silva, Jan Kerby 
       : Zotomayor, Aaron Simon Luis



OVERVIEW

1. A camera is mounted over the lot and streams frames to the backend.
2. A detection model marks each spot as occupied or free and checks the lines between spots for cars straddling two spots.
3. The backend updates spot status every few seconds.
4. The web dashboard shows the latest status to signed-in users.
5. On a double-parking event, the backend saves one encrypted picture and sends an alert to the security Telegram group. When the violation clears, a "Cleared" message reports how long it lasted.
6. Subscribed users get a Telegram message when a spot opens in a full lot.



USAGE

[Students]
1. Open the site and sign in with your DLSL Google account.
2. Check the Overview for free spots or open the Lot map.
3. If the lot is full, tap **Notify me** and subscribe on Telegram.

[Security & Admins]
1. Use Admin sign in on the login page.
2. Review double-parking alerts and the live camera.

TELEGRAM COMMANDS
- /stop - unsubscribe from spot alerts.



LIMITATIONS

- Detection can mistake people, bags, or other objects for cars.
- The detection model needs more training data (lighting, weather, camera angles, car sizes and colors, partly blocked views, cars outside lines).
- Tested only on a miniature model, not a full-size lot.
- Covers cars only; motorcycles, bicycles, and trucks are not supported.
- Covers a single lot (Lot A, six spots).
- The proposal's crowdsourced prediction features (Quadtree zone indexing, Poisson vacancy model, reputation scoring) describe the planned design; update this section to say which parts are implemented.



DISCLAIMER: 
"This is an academic project by Team 3, De La Salle Lipa, made for educational purposes only and provided as is without warranty. All rights reserved by the Park Patrol team."
