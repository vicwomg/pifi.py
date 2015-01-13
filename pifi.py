import sys
import os
import subprocess
import socket
import time
import pygame
import signal
from wifi import Cell, Scheme
from virtualKeyboard import VirtualKeyboard

class PiFi:

  def __init__(self, interface='wlan0'):
    self.interface = interface
    self.aps = None

    # Templates for the interface files
    self.wpa_supplicant_path = '/etc/wpa_supplicant/wpa_supplicant.conf'
    self.wpa_supplicant_template = """
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
        ssid="%s"
        %s
}
"""
    self.etc_interfaces_path = '/etc/network/interfaces'
    self.etc_interfaces_template = """
auto lo

iface lo inet loopback
iface eth0 inet dhcp

allow-hotplug wlan0
iface wlan0 inet manual
wpa-roam %s
iface default inet dhcp
""" % self.wpa_supplicant_path

    # Vars for the selected AP, set by prompts
    self.selected_ap = None
    self.selected_ap_name = None
    self.selected_ap_password = None
    self.selected_ap_encrypted = None

    # IP address set by self.getIP()
    self.ip = None
  
  def getWifiAPs(self):
    print "Scanning for WiFi APs...\n"
    aps = Cell.all('wlan0')
    aps_by_signal_strength = sorted(aps, key=lambda ap: ap.signal, reverse=True)
    self.aps = aps_by_signal_strength

  def printAPs(self):
    print "Available networks:"
    index = 0
    for ap in self.aps:
      print "[%d] SSID:%s  Strength:%d  Protected:%s" % (index, ap.ssid, ap.signal, str(ap.encrypted))
      index = index + 1
  
  def promptForSSID(self):
    ap_count = len(self.aps)
    while (True):
      prompt = "Select wifi AP (0-%d): " % (ap_count - 1)
      ap_index = raw_input(prompt)
      if ap_index.isdigit():
        ap_index_int = int(ap_index)
        if (ap_index_int >= ap_count or ap_index_int < 0):
          pass
        else:  
          print "Selected wifi AP: " + self.aps[ap_index_int].ssid
          break

      print "'%s' is not a valid selection. %s" % (ap_index, prompt) 
      continue
    self.setAPFromIndex(ap_index_int)

  def setAPFromIndex(self, ap_index):
    self.selected_ap = self.aps[ap_index]
    self.selected_ap_ssid = self.selected_ap.ssid
    self.selected_ap_encrypted = self.selected_ap.encrypted

  def promptForPassword(self):
    if (self.selected_ap_encrypted):
      password = raw_input("Enter password for '%s': " % self.selected_ap_ssid)
      self.selected_ap_password = password
    else:
      print "'%s' is not encrypted. No password necessary." % self.selected_ap_ssid

  def generateWPASupplicant(self):
    print "Generating '%s'..." % self.wpa_supplicant_path
    if (self.selected_ap_encrypted):
      encryption_string = 'psk="%s"' % self.selected_ap_password
    else:
      encryption_string = "key_mgmt=None"
    wpa_supplicant = self.wpa_supplicant_template % (self.selected_ap_ssid, encryption_string)

    file = open(self.wpa_supplicant_path, 'w')
    file.write(wpa_supplicant)
    file.close()

  def generateEtcInterfaces(self):
    print "Generating '%s'..." % self.etc_interfaces_path
    file = open(self.etc_interfaces_path, 'w')
    file.write(self.etc_interfaces_template)
    file.close()

  def getIP(self):
    proc = subprocess.Popen(['hostname', '-I'], stdout=subprocess.PIPE)
    proc.wait()
    out = proc.stdout.readline()
    self.ip = out.strip()
    return self.ip

  def isConnected(self):
    self.getIP()
    #print 'Your IP address is: %s' % ip
    try:
      socket.inet_aton(self.ip)
      return True
    except socket.error:
      return False

  def reconnect(self):
    print 'Re-connecting wifi...'
    proc = subprocess.Popen(['sudo', 'ifdown', self.interface], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.wait()
    proc2 = subprocess.Popen(['sudo', 'ifup', self.interface], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc2.wait()
    time.sleep(3) #allow some time to get IP

  def run(self):
    self.getWifiAPs()
    while (True): 
      self.printAPs()
      print
      self.promptForSSID()
      print
      self.promptForPassword()
      self.generateEtcInterfaces()
      self.generateWPASupplicant()
      self.reconnect()
      if(self.isConnected()):
        break
      else:
        print
        print "[ERROR] Failed to connect to '%s'!" % self.selected_ap_ssid
        print "[ERROR] Please try again, and double-check your password."
        print

    print "SUCCESS! IP: %s" % self.ip


class PiFiGUI(PiFi):
  def __init__(self):
    PiFi.__init__(self)

    print "Initializing PiTFT screen..."
    os.putenv('SDL_VIDEODRIVER', 'fbcon')
    os.putenv('SDL_FBDEV'      , '/dev/fb1')
    os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
    os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')
    os.putenv('DISPLAY'   , ':0')

    # Init pygame and screen
    pygame.display.init()
    pygame.font.init()
    pygame.mouse.set_visible(False)
    self.width = pygame.display.Info().current_w
    self.height = pygame.display.Info().current_h
    self.size = (self.width, self.height)
    self.screen = pygame.display.set_mode(self.size)
    self.display = pygame.display
    # Color definitions
    self.white = (255,255,255)
    self.yellow = (255,255,0)
    self.black = (0,0,0)
    # Background settings
    self.bgColor = self.black
    # Font settings
    self.txtColor = self.yellow
    self.txtFont = pygame.font.SysFont("Arial", 20, bold=True)
    self.txtFontSmall = pygame.font.SysFont("Arial", 16)
    # Max rows to display in lists
    self.rowsPerScreen = 7
    self.rowHeight = self.height / self.rowsPerScreen

  def resetBackground(self):
    self.bg  = pygame.transform.scale(self.image, self.size)
  
  def clearScreen(self):
    self.screen.fill(self.bgColor)  

  def renderCenteredText(self, text):
    self.clearScreen()
    txt = self.txtFont.render(text , 1, self.txtColor)
    self.screen.blit(txt, (15, self.height / 2 - 20))
    self.display.update()

  def addHeader(self, text):
    txt = self.txtFont.render(text, 1, self.txtColor)
    self.screen.blit(txt, (15, 5))

  def showSplashScreen(self):
    self.renderCenteredText('PiFi: WiFi Setup Wizard');

  def showAPs(self):
    self.renderCenteredText('Scanning for WiFi networks...');
    self.getWifiAPs()
    self.clearScreen()
    self.addHeader('Tap to select a WiFi network...')
    y = self.rowHeight
    for each in self.aps:
      line = "[ %s ] (%d)" % (each.ssid, each.signal) 
      txt = self.txtFontSmall.render(line, 1, self.white)
      self.screen.blit(txt, (15, y))
      y = y + self.rowHeight
    self.display.update()

  def getMousePress(self):
    running = True
    while running:
      try: 
        #event = pygame.event.poll()
        for event in pygame.event.get():
          if event.type == pygame.QUIT:
            running = False
          elif event.type == pygame.MOUSEBUTTONDOWN:
            return event.pos
            running = False
      except KeyboardInterrupt:
        running = False
        self.quit()

  def getSelectionIndex(self):
    pos = self.getMousePress()
    y = pos[1]
    segment = y / self.rowHeight
    selectionIndex = segment - 1
    if (selectionIndex == -1):
      selectionIndex = 0
    return selectionIndex

  def confirmSelectedAP(self):
    self.clearScreen()
    self.addHeader("Connect to: '%s'?" % self.selected_ap_ssid)
    yes = self.txtFont.render("Yes", 1, self.white)
    no = self.txtFont.render("No", 1, self.white)
    self.screen.blit(yes, (50, self.height / 2 ))
    self.screen.blit(no, (self.width - 120, self.height / 2))
    self.display.update()

  def getConfirmation(self):
    self.confirmSelectedAP()
    pos = self.getMousePress()
    x = pos[0]
    if (x < (self.width / 2)):
      return True
    else:
      return False

  def promptForPassword(self):
    self.renderCenteredText("Enter the WiFi password...")
    time.sleep(2)
    if (self.selected_ap_encrypted):
      vkey = VirtualKeyboard(self.screen)
      self.selected_ap_password = vkey.run("")
    
  def run(self):
    self.showSplashScreen()
    time.sleep(3)

    while True:
      ap_confirmed = False
      while (ap_confirmed == False):
        self.showAPs()
        index = self.getSelectionIndex()
        self.setAPFromIndex(index)
        ap_confirmed = self.getConfirmation()
    
      self.promptForPassword()
      self.renderCenteredText("Connecting to '%s'..." % self.selected_ap_ssid)
      self.generateEtcInterfaces()
      self.generateWPASupplicant()
      self.reconnect()
      if(self.isConnected()):
        break
      else:
        self.renderCenteredText("Failed! Check WiFi password")
        time.sleep(3)
    
    self.renderCenteredText("Success! IP: %s" % self.ip)
    time.sleep(2)
    self.quit()    

  def quit(self):
    print("Exiting...")
    sys.exit(0)

def usageExit():
  usage = '''%s : Wizard for setting up a WiFi connection 

usage:	  %s [OPTION]
options:  --help  : shows help
          --gui   : configure using a touchscreen graphical user interface
          default : Runs command line interface
''' % (sys.argv[0], sys.argv[0])
  print usage
  sys.exit(0)  

def main():
  if (len(sys.argv) == 2):
    arg = sys.argv[1]
    if (arg in ('--help', '-h')):
      usageExit()
    elif (arg == '--gui'):
      pifi = PiFiGUI()
    else:
      usageExit()
  else:
    pifi = PiFi()
  pifi.run()

if __name__ == "__main__":
  main()

