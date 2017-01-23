EveExploHelper 1.0.0
====================

A small program to help explorers of New Eden (Eve Online).

Features
--------

- Reminder to bookmark the wormhole when jumping to / from a wormhole system
- Keybindings to easily lookup wormhole classifications (e.g. typing C248 will tell you the wormhole leads to nullsec)
- A keybinding to send the current clipboard to [evepraisal](http://evepraisal.com/) for a price estimate at Jita (useful when trying to assess which cans to hack at data / relic sites)

CREST Setup
-----------

To use the bookmark reminder function of this application, you'll need to register a new application on [CCP's developer website](https://developers.eveonline.com/applications). This is unfortunately only available to accounts that have paid money for gametime. Hopefully CCP adjusts this policy sometime soon.

1. Go to  [CCP's developer website](https://developers.eveonline.com/applications)
2. Go to manage applications, then create new application
3. Give a name and description for your installation
4. Ensure the characterLocationRead permission is enabled
5. Set the callback url to http://localhost:4173/ (if you want to use a different port, choose that port after the colon instead of 4173)
6. Click create
7. Add the Client ID and Secret Key on the next page to respective locations in the settings.ini in this folder, in the [CREST] section. Also update the port in the [network] section if you chose a different port.

License
-------

EveExploHelper is copyrighted free software made available under the terms of the GPLv3

bookmarkTheHole.wav was created by me using [eSpeak](http://espeak.sourceforge.net/) and is licenced under [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/).  

Copyright: (C) 2017 by apocolypse600. All Rights Reserved.