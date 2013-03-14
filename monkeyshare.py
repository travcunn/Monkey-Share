import collections, cPickle, hashlib, math, os, random, sqlite3, socket, sys, thread, threading, time
from PyQt4 import QtCore, QtGui
from PyQt4 import *
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from ui.AboutWindow import Ui_AboutWindow
from ui.AddPeerWindow import Ui_AddPeerWindow
from ui.DownloadWindow import Ui_DownloadWindow
from ui.SettingsWindow import Ui_SettingsWindow
from ui.MainWindow import Ui_MainWindow
from threading import Thread

class PeerClient(object):
	
	#This class contains all of the methods for connecting with remote peers
	#Threads downloading of files or file lists, checks status of other peers
	def __init__(self):
		object.__init__(self)
		self.database = FileDatabase()
				
	def getPeerName(self, remoteip):
		connection = socket.socket(socket.AF_INET)
		connection.settimeout(10)
		connection.connect((remoteip, 10050))
		connection.send("Info")
		while True:
			receivedData = connection.recv(1024)
			if(receivedData[0:3] == "End"): 
				break
			elif(receivedData[0:6] == "Denied"):
				print ("The peer is not accepting new connections")
				return False
			else:
				return receivedData
	
	def pingPeer(self, remoteip):
		connection = socket.socket(socket.AF_INET)
		connection.settimeout(5)
		try:
			connection.connect((remoteip, 10050))
		except:
			return False
		connection.send("Ping")
		while True:
			receivedData = connection.recv(1024)
			if(receivedData[0:1] == "1"): 
				return True
			else:
				return False
			break
	
	def startPeerCheck(self):
		thread.start_new_thread(self.peerStatusThread, ())
	
	def peerStatusThread(self):
		while(True):
			for i in range(len(self.database.getAllPeers())):
				if(self.pingPeer(self.database.getAllPeers()[i][0])):
					if(self.database.checkPeerStatus(self.database.getAllPeers()[i][0])[0] == "offline"):
						#thread.start_new_thread(self.getPeerListing, (self.database.getAllPeers()[i][0],))
						self.database.setPeerStatus(self.database.getAllPeers()[i][0], "online")
				else:
					if(self.database.checkPeerStatus(self.database.getAllPeers()[i][0])[0] == "online"):
						self.database.setPeerStatus(self.database.getAllPeers()[i][0], "offline")
			time.sleep(15)
		
class PeerServer(threading.Thread):
	def __init__(self, portNumber = 10050):
		threading.Thread.__init__(self)
		self.__port = portNumber
		self.s = socket.socket()
		##allows for reuse of a socket, since the system puts it in a state that cannot be reused
		###http://docs.python.org/2/library/socket.html
		self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		try:
			self.s.bind(('0.0.0.0', self.__port))
			self.s.listen(0)
			self.connectionsAlive = []
			#create an instance of the database
			self.database = FileDatabase()
			#create an instance of the settings
			self.settings = AppSettings()
			#start() the thread... dont call the run method. self.start() will start the thread correctly
			self.start()
		except:
			raise
        
	def run(self):
		while(True):
			self.acceptConnections()
		
	def acceptConnections(self):
		#waits for someone to connect, creates a thread for that connection, then waits other connections
		client, address = self.s.accept()
		##address is an array object, so address[0] will get the ip of the client connected
		print "[server]: Client connected: [%s] [Spawning a connection thread]" % str(address[0])
		#to allow for multiple connections, start a thread for each client
		if(int(self.allClientsConnectionCount()) <= int(self.settings.getMaxConnections())):
			if(int(self.clientConnectionCount(address[0])) <= int(self.settings.getMaxConnectionsPerPeer())):
				self.clientConnectionAdd(address[0])
				thread.start_new_thread(self.clientConnection, (client, address))
			else:
				thread.start_new_thread(self.clientConnection, (client, address, False))

	def clientConnectionAdd(self, ip):
		self.connectionsAlive.append(str(ip))
		print "[server]: Adding %s to the connections list" % str(ip)
		print "[server]: Here is a list of all the connected clients:"
		for i in range(len(self.connectionsAlive)):
			print self.connectionsAlive[i]
		
	def clientConnectionRemove(self, ip):
		self.connectionsAlive.remove(str(ip))
		print "[server]: Here is a list of all the connected clients:"
		for i in range(len(self.connectionsAlive)):
			print "[server]: %s" % self.connectionsAlive[i]
		if(len(self.connectionsAlive) == 0):
			print "[server]: ...no clients connected..."
		
	def clientConnectionCount(self, ip):
		connections = 0
		for i in range(len(self.connectionsAlive)):
			if (self.connectionsAlive[i] == str(ip)):
				connections = connections + 1
		return connections
		
	def allClientsConnectionCount(self):
		return len(self.connectionsAlive)
		
	def clientConnection(self, client, address, accept=True):
		if(accept):
			while True:
				receivedData = client.recv(1024)
				if receivedData:
					if(receivedData[0:5] == "Hash:"):
						#if the remote client requests a hash, set the request hash
						fileRequestHash = receivedData[5:37]
						print "[server]: The remote client has requested: %s" % fileRequestHash
						requestedFilePath = self.database.getPathLocal(fileRequestHash)
						if(requestedFilePath == None):
						#if the hash is invalid, do this
							print '[server]: Invalid hash requested'
							#if we dont use sleep, the client is unable to read the end command
							client.send("Invalid")
							client.close()
							self.clientConnectionRemove(address[0])
							print '[server]: Closed the connection'
						else:
						#if the hash is valid, do this
							print '[server]: Starting the upload of the file'
							try:
								fileToSend = open(requestedFilePath[0], "rb")
								dataToSend = fileToSend.read()
								fileToSend.close()
							except:
								print "[server]: Could not open the file requested"
							else:
								amountDataSent = 0
								print("[server]: Requested file is %s bytes") % os.path.getsize(requestedFilePath[0])
								datasent = client.send(dataToSend)
								amountDataSent = amountDataSent + datasent
								print ("[server]: Sent %s bytes") % amountDataSent
								#if we dont use sleep, the client is unable to read the end command
								time.sleep(1)
								client.send("End")
								client.close()
								self.clientConnectionRemove(address[0])
								print '[server]: Successfully sent the file and closed the connection'
					elif(receivedData[0:8] == "Filelist"):
						#if the remote client requests a file list, send them a file list
						print "Client requested a file list... Sending..."
						hashesDump = self.database.dumpHashesLocal()
						sharesDump = self.database.dumpSharesPathLocal()
						sizesDump = self.database.dumpSizeLocal()
						for i in range(len(hashesDump)):
							#For every row in the database, send it individually.
							#In case the connection is dropped, the client can still receive a partial list
							anotherRow = [hashesDump[i][0], sharesDump[i][0], sizesDump[i][0]]
							rowToSend = cPickle.dumps(anotherRow)
							client.send(rowToSend)
							#if we send too fast, the peer wont receive the messages...
							time.sleep(0.5)
						time.sleep(1)
						client.send("End")
						client.close()
						print '[server]: Closed the connection'
						self.clientConnectionRemove(address[0])
					elif(receivedData[0:4] == "Ping"):
						#responds to a ping request from client
						client.send("1")
						client.close()
						self.clientConnectionRemove(address[0])
						print '[server]: Closed the connection'
					elif(receivedData[0:4] == "Info"):
						#responds to the client with a username
						self.settings.readSettings("settings.ini")
						client.send(self.settings.getUsername())
						time.sleep(1)
						client.send("End")
						client.close()
						self.clientConnectionRemove(address[0])
						print '[server]: Closed the connection'
					
				else:
					break
				break
		else:
			#if told to drop connection, send client a status message, then close the connection
			#if we dont use sleep, the client is unable to read the end command
			client.send("Denied")
			client.close()
			self.clientConnectionRemove(address[0])
			print '[server]: Closed the connection'
			
	def stopServer(self):
		self.s.close()
		#using _Thread__stop() kills the thread, since socket.accept() is blocking
		#http://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python
		self._Thread__stop()

class FileDatabase(object):
	#This class stores/retrieves hash/path data about the locally and remotely shared files
	def __init__(self):
		object.__init__(self)
		#create an instance of the settings object
		self.settings = AppSettings()
		self.createDatabase()
		#self.indexFiles()
	
	#####################################################
	############ Database Connect/Disconnect ############
	#####################################################
	
	def dbConnect(self):
		self.dbconnection = sqlite3.connect("files.db")
		return self.dbconnection.cursor()
	
	def dbDisconnect(self):
		self.dbconnection.close()
		
	#####################################################
	##### Remote file listing in the local database #####
	#####################################################
	
	def addRemoteFile(self, sharepath, hash, peerip, size):
		#Adds files to the database. Specify a filepath and its hash
		try:
			cursor = self.dbConnect()
			cursor.execute("INSERT INTO remotefiles VALUES (?, ?, ?, ?)", (hash, sharepath, peerip, size))
			self.dbconnection.commit()
		except:
			raise
		finally:
			self.dbDisconnect()
	
	def clearFilesRemote(self, peerip):
		#clears the remote files table for a specific ip
		cursor = self.dbConnect()
		cursor.execute("DELETE FROM remotefiles WHERE peerip=?", (peerip,))
		self.dbconnection.commit()
	
	def getFileSize(self, sharepath): 
	##Returns the hash of a file in the database, based upon the shared path
		cursor = self.dbConnect()
		cursor.execute("SELECT size FROM remotefiles WHERE sharepath=?", (sharepath,))
		return cursor.fetchone()[0]
		
	def getHashRemote(self, sharepath): 
	##Returns the hash of a file in the database, based upon the shared path
		cursor = self.dbConnect()
		cursor.execute("SELECT hash FROM remotefiles WHERE sharepath=?", (sharepath,))
		return cursor.fetchone()[0]
	
	def getUserFiles(self, username): 
	##Returns all files under a specific user
		peerip = self.getPeerIP(username)[0]
		cursor = self.dbConnect()
		cursor.execute("SELECT sharepath FROM remotefiles WHERE peerip=?", (peerip,))
		return cursor.fetchall()
		
	def remoteFilesDump(self, peerip): 
	##Returns all files under a specific user
		cursor = self.dbConnect()
		cursor.execute("SELECT sharepath FROM remotefiles where peerip=?", (peerip,))
		return cursor.fetchall()
		
	#####################################################
	##### Local file listing in the local database ######
	#####################################################
			
	def addLocalFile(self, filepath, hash, sharepath, size):
		#Adds files to the database. Specify a filepath and its hash
		try:
			cursor = self.dbConnect()
			cursor.execute("INSERT INTO localfiles VALUES (?, ?, ?, ?)", (hash, filepath.decode('utf-8'), sharepath.decode('utf-8'), size))
			self.dbconnection.commit()
		except:
			raise
		finally:
			self.dbDisconnect()	
	
	def clearFilesLocal(self):
		#clears the local files table
		cursor = self.dbConnect()
		cursor.execute("DELETE FROM localfiles")
		self.dbconnection.commit()
	
	def getHashLocal(self, filepath): 	
	##Returns the hash of a file in the database, based upon the path
		cursor = self.dbConnect()
		cursor.execute("SELECT hash FROM localfiles WHERE path=?", (filepath,))	
		#return the first one, since queries return a 2d array (http://cs.iupui.edu/~aharris/230/python/data/data.html)
		return cursor.fetchone()
	
	def getPathLocal(self, hash):
	##Returns the hash of a local file in the database, based upon the path
		cursor = self.dbConnect()
		cursor.execute("SELECT path FROM localfiles WHERE hash=?", (hash,))
		return cursor.fetchone()
		
	#####################################################
	##### Local file info dump in the local database ####
	#####################################################
	
	def dumpHashesLocal(self):
		cursor = self.dbConnect()
		cursor.execute("SELECT hash FROM localfiles")
		return cursor.fetchall()

	def dumpFilesLocal(self):
		cursor = self.dbConnect()
		cursor.execute("SELECT path FROM localfiles")
		return cursor.fetchall()
		
	def dumpSharesPathLocal(self):
		cursor = self.dbConnect()
		cursor.execute("SELECT sharepath FROM localfiles")
		return cursor.fetchall()
		
	def dumpSizeLocal(self):
		cursor = self.dbConnect()
		cursor.execute("SELECT size FROM localfiles")
		return cursor.fetchall()
	
	#####################################################
	######## Local file discovery and indexing  #########
	#####################################################
	
	def indexFiles(self):
		print "[database]: Indexing all files in the shared folder..."
		##we must clear the existing table if there is request to index the files
		self.clearFilesLocal()
		self.settings.readSettings("settings.ini")
		for (paths, folders, files) in os.walk(self.settings.getShareDirectory()):
			#for each file it sees, we want the path and the file to we can store it
			for eachfile in files:
				#os.walk crawls in the "Shared" folder and it returns an array of great things (being the file path)!
				#print paths
				## os.path.join combines the real path with the filename, and it works cross platform, woot!
				discoveredFilePath = os.path.join(paths,eachfile)
				self.addLocalFile(discoveredFilePath, self.hashFile(discoveredFilePath), (os.path.join(paths,eachfile).replace(self.settings.getShareDirectory(),'')), os.path.getsize(discoveredFilePath))
				print  "[database-indexer]: %s %s" % (os.path.join(paths,eachfile).replace(self.settings.getShareDirectory(),''), os.path.getsize(discoveredFilePath))
		print "[database]: Indexing complete..."
			
	def hashFile(self, filepath):
	##Read files line by line instead of all at once (allows for large files to be hashes)
	##For each line in the file, update the hash, then when it reaches the end of the 
		fileToHash = open(filepath)
		md5 = hashlib.md5()
		while(True):
			currentLine = fileToHash.readline()
			if not currentLine:
				#when readline() returns false, it is at the end of the file, so break the loop
				break
			md5.update(currentLine)
		return md5.hexdigest()

	#####################################################
	################# Database creation #################
	#####################################################
	
	def createDatabase(self):
		#ensures the tables are in the database, and if they are, it moves on
		try:
			cursor = self.dbConnect()
			cursor.execute("""CREATE TABLE localfiles (hash text, path text, sharepath text, size int)""")
			cursor.execute("""CREATE TABLE remotefiles (hash text, sharepath text, peerip text, size int)""")
			cursor.execute("""CREATE TABLE peers (username text, peerip text, status text)""")
		except sqlite3.OperationalError:
			pass
		finally:
			self.dbDisconnect()
			
	#####################################################
	################## Peer Management ##################
	#####################################################

	def addPeer(self, username, peerip):
		#Adds peer to the database. Specify a username and peerip
		try:
			if(self.checkPeerStatus(peerip) != None):
				print "Peer already exists. Not adding."
			else:
				cursor = self.dbConnect()
				cursor.execute("INSERT INTO peers VALUES (?, ?, ?)", (username, peerip, "offline"))
				self.dbconnection.commit()
		except:
			raise
		finally:
			self.dbDisconnect()	
			
	def removePeer(self, peerip):
		#removes a peer by peerip
		cursor = self.dbConnect()
		cursor.execute("DELETE FROM peers WHERE peerip=?", (peerip,))
		self.dbconnection.commit()
		
	def checkPeerStatus(self, peerip):
		#checks the status of a peer
		cursor = self.dbConnect()
		cursor.execute("SELECT status FROM peers WHERE peerip=?", (peerip,))	
		return cursor.fetchone()
		
	def setPeerStatus(self, peerip, status):
		#checks the status of a peer
		cursor = self.dbConnect()
		cursor.execute("UPDATE peers SET status=? WHERE peerip=?", (status, peerip))	
		self.dbconnection.commit()
		
	def getPeerName(self, peerip):
		#gets the name of the peer in the db
		cursor = self.dbConnect()
		cursor.execute("SELECT username FROM peers WHERE peerip=?", (peerip,))
		return cursor.fetchone()
	
	def getPeerIP(self, peername):
		#gets the name of the peer in the db
		cursor = self.dbConnect()
		cursor.execute("SELECT peerip FROM peers WHERE username=?", (peername,))
		return cursor.fetchone()
	
	def getAllPeers(self):
		cursor = self.dbConnect()
		cursor.execute("SELECT peerip FROM peers")	
		return cursor.fetchall()

class AppSettings(object):
	def __init__(self):
		object.__init__(self)
		self.readSettings("settings.ini")
		
	def readSettings(self, path):
		try:
			settingsFile = open(path, 'r')
			settings = cPickle.load(settingsFile)
			settingsFile.close()
			#for each value in the array, set variables accordingly
			self.setServerPort(settings[0])
			self.setShareDirectory(settings[1])
			self.setUsername(settings[2])
			self.setMaxConnections(settings[3])
			self.setMaxConnectionsPerPeer(settings[4])
		except IOError:
			self.setDefaults()
			self.saveSettings(path)
			
	def saveSettings(self, path):
		try:
			settingsFile = open(path, 'w')
			cPickle.dump((self.getServerPort(), self.getShareDirectory(), self.getUsername(), self.getMaxConnections(), self.getMaxConnectionsPerPeer()), settingsFile)
			settingsFile.close()
			return True
		except IOError:
			return False
			
	def setDefaults(self):
		self.setServerPort(10050)
		self.setShareDirectory("")
		self.setUsername(self.setRandomName())
		self.setMaxConnections(20)
		self.setMaxConnectionsPerPeer(5)
		
	def getServerPort(self):
		return self.__serverPort
		
	def getShareDirectory(self):
		return self.__shareDirectory
	
	def getUsername(self):
		return self.__username
		
	def getMaxConnections(self):
		return self.__maxConnections
		
	def getMaxConnectionsPerPeer(self):
		return self.__maxConnectionsPerPeer
		
	def setServerPort(self, port):
		self.__serverPort = port
		
	def setShareDirectory(self, directory):
		self.__shareDirectory = directory
	
	def setUsername(self, username):
		self.__username = username
		
	def setRandomName(self):
		return("unnamed_user%d" % random.randint(0, 60000))
	
	def setMaxConnections(self, numberOfConnections):
		self.__maxConnections = numberOfConnections
	
	def setMaxConnectionsPerPeer(self, numberOfConnections):
		self.__maxConnectionsPerPeer = numberOfConnections

class MainWindow(QtGui.QMainWindow, Ui_MainWindow):
	def __init__(self, parent=None):
		QtGui.QMainWindow.__init__(self)
		self.setupUi(self)
		self.setWindowTitle('Monkey Share')
		self.database = FileDatabase()
		self.peerclient = PeerClient()
		self.downloadButton.clicked.connect(self.downloadButtonClicked)
		self.filesView.itemSelectionChanged.connect(self.selectedFile)
		self.peersView.itemSelectionChanged.connect(self.fileListingUpdate)
		self.actionAdd_Peer_2.triggered.connect(self.addpeer)
		self.actionRemove_Peer_2.triggered.connect(self.deleteselected)
		self.actionRefresh_Peers_2.triggered.connect(self.refreshpeerfilescurrent)
		self.actionSettings_2.triggered.connect(self.showsettings)
		self.actionSettings.triggered.connect(self.showsettings)
		self.actionExit.triggered.connect(self.close)
		self.actionAdd_Peer.triggered.connect(self.addpeer)
		self.actionRemove_Peer.triggered.connect(self.deleteselected)
		self.actionRefresh_Peers.triggered.connect(self.refreshpeerfilesthread)
		self.actionAbout_2.triggered.connect(self.showabout)
		self.filesView.itemDoubleClicked.connect(self.downloadButtonClicked)
		self.searchButton.clicked.connect(self.searchFiles)
		self.downloadSearchButton.clicked.connect(self.downloadSearchButtonClicked)
		self.searchResultsView.itemDoubleClicked.connect(self.downloadSearchButtonClicked)
		self.filesListing = []
		self.peersList = []
		self.fileslist = []
		self.sizeslist = []
		self.checksumslist = []
		self.searchresults = []
		self.thefiles = {'1':self.fileslist, '0':self.sizeslist, '3':self.checksumslist}
		self.selectedPeer = ""
		
		self.refreshpeersthread()
		
		self.show()
	
	def searchFiles(self):
		try:	
			thepeer = self.database.getPeerIP(self.selectedPeer)[0]
		except:
			QtGui.QMessageBox.information(self, "Select a peer", "Please select a peer, then continue your search.")
		else:
			self.searchResultsView.clear()
			self.searchresults = []
			searchterms = str(self.searchInput.text()).lower().split()
			for term in searchterms:
				for i in range(len(self.database.remoteFilesDump(thepeer))):
					try:
						theindex = (self.database.remoteFilesDump(thepeer)[i][0]).lower().index(term)
						self.searchresults.append(self.database.remoteFilesDump(thepeer)[i][0])
					except:
						pass
			resultcount = collections.Counter(self.searchresults)
			for i in range(len(resultcount.most_common(len(resultcount)))):
				self.searchResultsView.insertItem(i, resultcount.most_common(len(resultcount))[i][0])
			if(len(self.searchresults) == 0):
				QtGui.QMessageBox.information(self, "No Results Found", "No results found on your search.")
		
	def downloadSearchButtonClicked(self):
		try:
			self.window = DownloadWindow(self, self.selectedPeer, (self.searchResultsView.selectedItems()[0].text()))
			self.window.show()
		except:
			#if no files are selected, just pass... its not able to download selected, so it moves on
			pass
        
	def downloadButtonClicked(self):
		try:
			selectedrow=[] 
			for selected in self.filesView.selectedIndexes():
				selectedrow.append(selected.row())
			for i in selectedrow:
				self.window = DownloadWindow(self, self.selectedPeer, (self.filesView.item(selectedrow[0], 0).text()))
				self.window.show()
		except:
			#if no files are selected, just pass... its not able to download selected, so it moves on
			pass
			
	
	def addpeer(self, parent):
		self.newpeer = ""
		try:
			self.window = AddPeerWindow(self)
			self.window.show()
		except:
			pass
	
	def deleteselected(self):
		try:
			if(self.selectedPeer != ""):
				self.peersView.takeItem(self.peersList.index(self.selectedPeer))
				self.database.removePeer(self.database.getPeerIP(self.selectedPeer)[0])
				self.fileslist = []
				self.peerslist = []
				self.filesListing = []
				self.filesView.setRowCount(0)
				self.peersList.remove(self.selectedPeer)
		except:
			raise
	
	def refreshpeerfilesthread(self):
		#spawns a thread to refreshpeerfiles
		thread.start_new_thread(self.refreshpeerfiles, ())
	
	def refreshpeerfiles(self):
		#for each peer in the database, get the file listing, which stores in db. When done, update screen.
		for i in range(len(self.database.getAllPeers())):
			thread.start_new_thread(self.getPeerListing, (self.database.getAllPeers()[i][0],))
	
	def refreshpeerfilescurrent(self):
		#for each peer in the database, get the file listing, which stores in db. When done, update screen.
		try:
			self.getPeerListing(self.database.getPeerIP(self.selectedPeer)[0])
			self.refreshCurrent()
		except:
			pass
	
	def refreshpeerfilesloop(self):
		#spawns a thread to refreshpeerfilesdef getPeerListing(self, remoteip):
		self.database.clearFilesRemote(remoteip)
		connection = socket.socket(socket.AF_INET)
		try:
			connection.connect((remoteip, 10050))
		except:
			pass
		else:
			connection.send("Filelist")
			while True:
				receivedData = connection.recv(1024)
				if(receivedData[0:3] == "End"): 
					break
				elif (receivedData[0:7] == "Invalid"):
					print ("[client]: The requested file was invalid.") 
					break
				elif(receivedData[0:6] == "Denied"):
					print ("[client]: The peer is not accepting new connections")
					break
				else:
					theReceivedArray = cPickle.loads(receivedData)
					self.database.addRemoteFile(theReceivedArray[1], theReceivedArray[0], remoteip, theReceivedArray[2])
					print "[client]: " + theReceivedArray[0] + " " + theReceivedArray[1] + " Size:" + str(theReceivedArray[2])
		thread.start_new_thread(self.refreshpeerfileslooper, ())
	
	def refreshpeerfileslooper(self):
		while(True):
			#for each peer in the database, get the file listing, which stores in db. When done, update screen.
			for i in range(len(self.database.getAllPeers())):
				thread = Thread(target=self.peerclient.getPeerListing, args=(self.database.getAllPeers()[i][0],))
				thread.start()
			try:
				thread.join()
			except:
				pass
			self.refreshCurrent()
			time.sleep(15)
		
	def refreshpeersthread(self):
		#starts the thread for refreshpeersListing
		thread.start_new_thread(self.refreshpeersListing, ())
		
	def refreshpeersListing(self):
		#adds peers to the list when found in the database, ignore adding duplicates
		#also, this changes the color of the peers depending on the result of a ping
		for i in range(len(self.database.getAllPeers())):
			try:
				#Try converting the index of where the peer is in the list
				#self.peersListbox.itemconfig([i], bg='red', fg='white')
				theusername = self.database.getPeerName(self.database.getAllPeers()[i][0])[0]
				int(self.peersList.index(theusername))
			except:
				#If it's not in the list, insert it into the listbox and the list
				self.peersView.addItem(self.database.getPeerName(self.database.getAllPeers()[i][0])[0])
				self.peersList.append(self.database.getPeerName(self.database.getAllPeers()[i][0])[0])
				print "peer went online"
				print self.database.getPeerName(self.database.getAllPeers()[i][0])[0]
			finally:
				if(self.peerclient.pingPeer(self.database.getAllPeers()[i][0]) != True):
					self.peersView.takeItem(i)
					print "peer went offline"
					print self.database.getPeerName(self.database.getAllPeers()[i][0])[0]
		
	
	def refreshSinglePeerListing(self, peername):
		try:
			#Try converting the index of where the peer is in the list
			#self.peersListbox.itemconfig([i], bg='red', fg='white')
			listnumber = int(self.peersList.index(peername))
			if(self.peerclient.pingPeer(self.database.getPeerIP(peername)) != True):
				self.peersView.takeItem(self.peersView.row(username))
		except:
			#If it's not in the list, insert it into the listbox and the list
			self.peersView.addItem(str(peername))
			self.peersList.append(peername)
			listnumber = int(self.peersList.index(peername))
			self.refreshpeerfilesthread()

	def refreshCurrent(self):
		#refreshes the file listbox of the selected peer
		try:
			self.changeFilesList(self.selectedPeer)
		except:
			pass
	
	def selectedFile(self):
		#when the user selects a file, this is the event
		try:
			self.selectedfile = self.filesView.currentItem().text()
		except:
			pass
	
	def changeFilesList(self, username):
		#show the files of the selected user in the file listbox
		#self.filesView.takeItem(0, (self.filesView.count() - 1))
		print "changing file listing for"
		print username
		for i in range(len(self.database.getUserFiles((username)))):
			try:
				theuserfiles = (self.database.getUserFiles(username)[i][0])
				#print theuserfiles
				int(self.fileslist.index(self.fileslist[i]))
				print "not in the db"
			except:
				self.sizeslisting = []
				self.checksumlist = []
		
				self.filesView.clear()
				self.filesView.clearContents()
				columns = QStringList()
				self.filesView.setEditTriggers(QTableWidget.NoEditTriggers)
				columns.append(QString("File Name"))
				columns.append(QString("Size"))
				columns.append(QString("Checksum"))
				self.filesView.setHorizontalHeaderLabels(columns)
				#If it's not in the list, insert it into the listbox and the list
				thisfilename = self.database.getUserFiles(username)[i][0]
				self.fileslist.append(thisfilename)
				thissize = float(self.database.getFileSize(thisfilename))
				if(thissize < 1024):
					measurement = "bytes"
				elif(thissize < int(math.pow(1024, 2))):
					thissize = thissize/1024
					measurement = "kB"
				elif(thissize < int(math.pow(1024, 3))):
					thissize = thissize/int(math.pow(1024, 2))
					measurement = "mB"
				else:
					thissize = thissize/int(math.pow(1024, 3))
					measurement = "gb"
				self.sizeslist.append(str("%.2f" % thissize) + " " + measurement)
				self.checksumslist.append(self.database.getHashRemote(thisfilename))
				self.filesListing.append(thisfilename)
				self.filesView.setRowCount(len(self.fileslist))
				i = 0
				for files in self.thefiles:
					x = 0
					for item in self.thefiles[files]:
						newrow = QTableWidgetItem(item)
						self.filesView.setItem(x, i, newrow)
						x = x + 1
					i = i + 1
				self.filesView.resizeColumnsToContents()
		if(len(self.database.getUserFiles((username))) == 0):
			print "User doesn't have any files"
			self.sizeslisting = []
			self.checksumlist = []
	
			self.filesView.clear()
			self.filesView.clearContents()
			self.filesListing = []
			self.fileslist = []
			columns = QStringList()
			self.filesView.setEditTriggers(QTableWidget.NoEditTriggers)
			columns.append(QString("File Name"))
			columns.append(QString("Size"))
			columns.append(QString("Checksum"))
			self.filesView.setHorizontalHeaderLabels(columns)
			self.filesView.setRowCount(0)
	def fileListingUpdate(self):
		#when the user selects a peer, this is the event
		try:
			theusername = str(self.peersView.currentItem().text())
			self.selectedPeer = theusername
		except:
			pass
		else:
			self.changeFilesList(theusername)
		
	def getPeerListing(self, remoteip):
		self.database.clearFilesRemote(remoteip)
		connection = socket.socket(socket.AF_INET)
		try:
			connection.connect((remoteip, 10050))
		except:
			pass
		else:
			connection.send("Filelist")
			while True:
				receivedData = connection.recv(1024)
				if(receivedData[0:3] == "End"): 
					break
				elif (receivedData[0:7] == "Invalid"):
					print ("[client]: The requested file was invalid.") 
					break
				elif(receivedData[0:6] == "Denied"):
					print ("[client]: The peer is not accepting new connections")
					break
				else:
					theReceivedArray = cPickle.loads(receivedData)
					self.database.addRemoteFile(theReceivedArray[1], theReceivedArray[0], remoteip, theReceivedArray[2])
					print "[client]: " + theReceivedArray[0] + " " + theReceivedArray[1] + " Size:" + str(theReceivedArray[2])
					
	def showsettings(self):
		try:
			self.window = SettingsWindow(self)
			self.window.show()
		except:
			pass
			
	def showabout(self):
		try:
			self.window = AboutWindow(self)
			self.window.show()
		except:
			pass
	
	def close(self):
		self.destroy()

class DownloadWindow(QtGui.QWidget, Ui_DownloadWindow):
	def __init__(self, parent, theuser, requesteddownload):
		QtGui.QMainWindow.__init__(self)
		self.setupUi(self)
		self.parent = parent
		self.requesteddownload = requesteddownload
		self.theuser = theuser
		self.setWindowTitle('Download File')
		self.settings = AppSettings()
		self.database = FileDatabase()
		self.requestedFileLabel.setText(self.requesteddownload)
		self.sumLabel.setText(self.database.getHashRemote(str(requesteddownload)))
		self.sizeLabel.setText(str(self.database.getFileSize(str(requesteddownload))/1024) + " kb")
		self.userLabel.setText(theuser + " (" + self.database.getPeerIP(self.theuser)[0] + ")")
		self.browseButton.clicked.connect(self.editDestination)
		self.cancelButton.clicked.connect(self.close)
		self.downloadButton.clicked.connect(self.download)
		
		self.fileDestinationInput.setText(self.settings.getShareDirectory() + requesteddownload)
		self.fileDestinationInput.setText

	
	def editDestination(self):
		newfile = QtGui.QFileDialog.getSaveFileName(self, 'Save File', '.')
		if (len(newfile) > 0):
			self.fileDestinationInput.setText(newfile)
	
	def download(self):
		if(len(str(self.fileDestinationInput)) > 0):
			try:
				self.downloadFile(self.database.getPeerIP(self.theuser)[0], self.requesteddownload, self.fileDestinationInput.text())
			except:
				self.error()
	
	def downloadFile(self, remoteip, sharepath, destination):
		connection = socket.socket(socket.AF_INET)
		connection.connect((remoteip, 10050))
		requestedFileHash = self.database.getHashRemote(str(sharepath))
		connection.send("Hash:" + requestedFileHash)
		receivedFile = open(destination, "wb")
		receivedamount = 0
		startdltimer = time.time()
		while True:
			receivedData = connection.recv(1024)
			if(receivedData[0:3] == "End"): 
				break
			elif(receivedData[0:7] == "Invalid"):
				print ("[client]: The requested file was invalid.") 
				break
			elif(receivedData[0:6] == "Denied"):
				print ("[client]: The peer is not accepting new connections")
				break
			else:
				receivedamount = receivedamount + len(receivedData)
				self.progressBar.setValue(int(float(receivedamount / float(self.database.getFileSize(str(sharepath)))) * 100))
				dlspeed = float((receivedamount * 1024 /(time.time() - startdltimer))/(1024*1024))
				if(dlspeed <1024):
					measurement = "bytes/second"
				elif(dlspeed < 1024^2):
					dlspeed = dlspeed/1024
					measurement = "kB/s"
				else:
					dlspeed = dlspeed/(1024^2)
					measurement = "mB/s"
					
				self.speedLabel.setText(str("%.2f" % dlspeed) + " " + measurement)
				receivedFile.write(receivedData)
		print "[client]: Received the file with the hash " + requestedFileHash
		receivedFile.close()
		print "[client]: closing file..."
		print self.database.hashFile(destination)
		print requestedFileHash
		if(self.database.hashFile(destination) == requestedFileHash):
			self.complete()
		else:
			self.error()
	
	def complete(self):
		QtGui.QMessageBox.information(self, "Complete", "File transfer complete and hash verified.")
		self.close()
		
	def error(self):
		QtGui.QMessageBox.critical(self, "Error", "There was an error downloading the file.")
			
	def close(self, event=None):
		self.deleteLater()

class AddPeerWindow(QtGui.QWidget, Ui_AddPeerWindow):
	def __init__(self, parent):
		QtGui.QMainWindow.__init__(self)
		self.setupUi(self)
		self.parent = parent
		self.setWindowTitle('Add Peer')
		self.settings = AppSettings()
		self.database = FileDatabase()
		self.cancelButton.clicked.connect(self.close)
		self.saveButton.clicked.connect(self.save)

		self.show()
	
	def save(self, event=None):
		#do some validation here... maybe even start up an indexer when the settings change...
		self.database = FileDatabase()
		self.peerclient = PeerClient()
		if(len(self.peerAddressInput.text()) > 0):
			try:
				if(self.database.checkPeerStatus(str(self.peerAddressInput.text())) != None):
					self.peerExistsError()
				else:
					newpeerinput = self.peerclient.getPeerName(str(self.peerAddressInput.text()))
					self.database.addPeer(newpeerinput, str(self.peerAddressInput.text()))
					if(len(newpeerinput) > 0):
						self.parent.newpeer = newpeerinput
					if(self.parent.newpeer != ""):
						self.parent.refreshSinglePeerListing(self.parent.newpeer)
						#self.refreshpeersListing()
					self.close()
			except:
				self.addPeerError()
		else:
			self.validationError("Not a valid entry")
		
	def close(self, event=None):
		self.destroy()
	
	def addPeerError(self):
		QtGui.QMessageBox.critical(self, "Could not connect", "The peer was offline or does not exist")
	
	def peerExistsError(self):
		QtGui.QMessageBox.information(self, "Peer Exists", "The specified peer already exists.")

	def validationError(self, message):
		QtGui.QMessageBox.critical(self, "Error", message)
			
	def close(self, event=None):
		self.deleteLater()

class SettingsWindow(QtGui.QWidget, Ui_SettingsWindow):
	def __init__(self, parent):
		QtGui.QMainWindow.__init__(self)
		self.setupUi(self)
		self.parent = parent
		self.setWindowTitle('Settings')
		self.appsettings = AppSettings()
		self.cancelButton.clicked.connect(self.close)
		self.saveButton.clicked.connect(self.save)
		self.browseButton.clicked.connect(self.editShareDir)
		self.usernameInput.setText(self.appsettings.getUsername())
		self.sharedDirInput.setText(self.appsettings.getShareDirectory())
		self.maxConnections.setValue(int(self.appsettings.getMaxConnections()))
		self.maxPeers.setValue(int(self.appsettings.getMaxConnectionsPerPeer()))

		self.show()
	
	def save(self):
		#do some validation here... maybe even start up an indexer when the settings change...
		self.database = FileDatabase()
		if(int(self.maxConnections.text()) >= int(self.maxPeers.text())):
			self.appsettings.setMaxConnections(str(self.maxConnections.text()))
			self.appsettings.setMaxConnectionsPerPeer(str(self.maxPeers.text()))
			if(len(self.usernameInput.text()) != 0):
				self.appsettings.setUsername(str(self.usernameInput.text()))
				if(os.path.isdir(self.sharedDirInput.text())):
					if(self.appsettings.getShareDirectory() != str(self.sharedDirInput.text())):
						self.appsettings.setShareDirectory(str(self.sharedDirInput.text()))
						self.appsettings.saveSettings("settings.ini")
						QtGui.QMessageBox.information(self, "Files Indexing", "Files will be indexed in the background")
						thread.start_new_thread(self.database.indexFiles, ())
					else:
						self.appsettings.setShareDirectory(str(self.sharedDirInput.text()))
						self.appsettings.saveSettings("settings.ini")
					self.close()
				else:
					self.validationError("Invalid share directory")
			else:
				self.validationError("Invalid Username")
		else:
			self.validationError("Max peer connections must be less than max connections")
	
	def editShareDir(self):
		newdirectory = QtGui.QFileDialog.getExistingDirectory(self, "Select Share Directory")
		if (len(str(newdirectory)) > 0):
			self.sharedDirInput.setText(newdirectory)

	def validationError(self, message):
		QtGui.QMessageBox.critical(self, "Error", message)
			
	def close(self, event=None):
		self.deleteLater()

class AboutWindow(QtGui.QWidget, Ui_AboutWindow):
	def __init__(self, parent):
		QtGui.QMainWindow.__init__(self)
		self.setupUi(self)
		self.setWindowTitle('About Monkey Share')
		self.closeButton.clicked.connect(self.close)

		self.show()
			
	def close(self, event=None):
		self.deleteLater()
		
def main():		
	try:	
		app = QtGui.QApplication(sys.argv)
		peerserver = PeerServer()
		mainwindow = MainWindow()
		app.exec_()
	except:
		peerserver._Thread__stop()
		
if __name__ == "__main__":
	main()
	
