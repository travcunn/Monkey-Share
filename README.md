Monkey-Share
============
Sometimes, us monkies like to share files.

A lightweight and naive P2P file sharing application using sockets written in Python, using PyQT as the GUI.
Originally used to learn about Python and sockets. Someday, I'll rewrite this with cleaner and more elegant code. When I gave a demo in a programming class, I stripped off the UI and used my iPhone as a peer.
    
__Run it__:

    python monkeyshare.py

__Caution:__
Since entire files are loaded into memory before they are transferred, it's probably not a good idea to send large files. In the future, it will be better to read each line of the file individually.

Screenshots
-----------

#####File Listing
![Monkey Share](https://raw.githubusercontent.com/travcunn/Monkey-Share/master/screenshots/monkeyshare.png)

#####File Download
![File Download](https://raw.githubusercontent.com/travcunn/Monkey-Share/master/screenshots/download.png)

#####User Settings
![File Download](https://raw.githubusercontent.com/travcunn/Monkey-Share/master/screenshots/settings.png)

#####Add Peer
![File Download](https://raw.githubusercontent.com/travcunn/Monkey-Share/master/screenshots/addpeer.png)
