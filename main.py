#!/usr/bin/python3
# much of the pong physics is copied from here:
# https://robots.thoughtbot.com/pong-clone-in-javascript

from subprocess import check_output, run, Popen, CalledProcessError
import re
from random import random
import Xlib
from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import record
from Xlib.protocol import rq
from threading import Thread

SCREEN_REGEX = r'^\s+dimensions:\s+(\d+)x(\d+)'

# balls
def detect_collision(rect1, rect2):
	return rect1.x < rect2.x + rect2.width and \
	   rect1.x + rect1.width > rect2.x and \
	   rect1.y < rect2.y + rect2.height and \
	   rect1.height + rect1.y > rect2.y

class Ball(object):
	
	def __init__(self, x, y, window_id):
		self.x = x
		self.y = y
		self.default_x = x
		self.default_y = y
		self.x_speed = 3
		self.y_speed = 0
		self.width = 10
		self.height = 10
		self.window_id = window_id 
		
		self.player_did_it = False
	
	def reset(self):
		self.x = self.default_x
		self.y = self.default_y
		self.x_speed = 3
		self.y_speed = 0
	
	def update(self, paddle1, paddle2):
		global screen_width, screen_height
		self.x += self.x_speed
		self.y += self.y_speed
		
		if self.y - 5 < 0: # hit the top wall
			self.y = 5
			self.y_speed = -self.y_speed
		elif self.y + 5 > screen_height: # hit the bottom wall
			self.y = screen_height - 5
			self.y_speed = -self.y_speed
		
		if self.x < 0 or self.x > screen_width:
			# lost
			print('rip')
			reset()
		
		# change number for difficulty
		if detect_collision(self, paddle1): # player
			self.x_speed = 3
			self.y_speed = min(self.y_speed + paddle1.y_speed // 2, 4)
			self.x += self.x_speed
			self.player_did_it = True
		elif detect_collision(self,paddle2): # computer
			self.x_speed = -3
			self.y_speed = min(self.y_speed + paddle2.y_speed // 2, 6)
			self.x += self.x_speed
			self.player_did_it = False
	
	def draw(self):
		run([ 'wmctrl', '-F', '-r', self.window_id, '-e', ','.join([ '0', str(self.x), str(self.y), str(self.width), str(self.height) ]) ])

class Paddle(object):
	
	def __init__(self, x, y, width, height, window_id):
		self.x = x
		self.y = y
		self.default_x = x
		self.default_y = y
		self.width = width
		self.height = height
		self.x_speed = 0
		self.y_speed = 0
		self.window_id = window_id
	
	def reset(self):
		self.x = self.default_x
		self.y = self.default_y
	
	def move(self, x, y):
		last_x, last_y = self.x, self.y
		self.x = x
		self.y = y
		self.x_speed = x
		self.y_speed = y
		if self.y < 0:
			self.y = 0
			self.y_speed = 0
		elif self.y + self.height > screen_height:
			self.y = screen_height - self.height - 20 # window decoration
			self.y_speed = 0
	
	def move_(self, x, y):
		self.x += x
		self.y += y
		self.x_speed = x
		self.y_speed = y
		if self.y < 0:
			self.y = 0
			self.y_speed = 0
		elif self.y + self.height > screen_height:
			self.y = screen_height - self.height - 20 # window decoration
			self.y_speed = 0
	
	def draw(self):
		run([ 'wmctrl', '-F', '-r', self.window_id, '-e', ','.join([ '0', str(self.x), str(self.y), str(self.width), str(self.height) ]) ])

# screen shit
def get_screen_size():
	lines = check_output(['xdpyinfo']).decode('utf-8').split('\n')
	line = next(filter(lambda line: 'dimensions' in line, lines))
	matches = re.match(SCREEN_REGEX, line)
	print(matches.group(1), matches.group(2))
	return (int(matches.group(1)), int(matches.group(2)))

# keyboard
local_display = Display()
record_display = Display()
def mousemove(event):
	player.move(0, event.root_y)

def callback(reply):
	if is_kill:
		exit()
	if reply.category != record.FromServer:
		return
	if reply.client_swapped:
		print("* received swapped protocol data, cowardly ignored")
		return
	if not len(reply.data) or reply.data[0] < 2: # not an event
		return
	
	data = reply.data
	while len(data):
		event, data = rq.EventField(None).parse_binary_value(data, record_display.display, None, None)
		if event.type == X.MotionNotify:
			mousemove(event)

def init_events():
	ctx = record_display.record_create_context(
		0,
		[record.CurrentClients],
		[{
				'core_requests': (0, 0),
				'core_replies': (0, 0),
				'ext_requests': (0, 0, 0, 0),
				'ext_replies': (0, 0, 0, 0),
				'delivered_events': (0, 0),
				'device_events': (X.KeyPress, X.MotionNotify),
				'errors': (0, 0),
				'client_started': False,
				'client_died': False,
		}]
	)
	record_display.record_enable_context(ctx, callback)
	record_display.record_free_context(ctx)

# main
ball = None
player = None
computer = None

screen_width = 0
screen_height = 0

def computer_update():
	global screen_height, computer
	y_pos = ball.y
	diff = -(computer.y + computer.height // 2 - y_pos - 20)
	diff = min(max(diff, -5), 5)
	computer.move_(0, diff)
	if computer.y < 0:
		computer.y = 0
	elif computer.y + computer.height > screen_height:
		computer.y = screen_height - computer.height

def update():
	computer_update()
	ball.update(player, computer)
	
	ball.draw()
	player.draw()
	computer.draw()

is_kill = False
process=[]
def kill():
	global is_kill
	is_kill = True
	for p in process:
		p.kill()
	exit()

def reset():
	ball.reset()
	player.reset()
	computer.reset()

def main():
	global screen_width, screen_height, ball, player, computer
	global process
	screen_width, screen_height = get_screen_size()
	ball_id, player_id, computer_id = str(random()), str(random()), str(random())
	process=[ # replace this with appropriate terminal of your choice
		Popen(['lxterminal', '--title=' + ball_id]),
		Popen(['lxterminal', '--title=' + player_id]),
		Popen(['lxterminal', '--title=' + computer_id])
	]
	
	Thread(target=init_events).start()
	
	ball = Ball(100, 100, ball_id)
	player = Paddle(0, screen_height // 2 - 50, 50, 175, player_id)
	computer = Paddle(screen_width - 70, screen_height // 2 - 50, 50, 175, computer_id)
	
	while True:
		update()

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		kill()
