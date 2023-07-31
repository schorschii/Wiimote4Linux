#!/usr/bin/env python3
# *-* coding: utf-8 *-*

import threading
import hid
import struct
import pyautogui
import configparser
from pathlib import Path
import alsaaudio
import traceback

from warper import warper


IDs = [
	{'vid': 0x057e, 'pid': 0x0306}, # Wii Remote/old Wii Remote Plus
	{'vid': 0x057e, 'pid': 0x0330}, # new Wii Remote Plus
]

class OutputReport:
	Dummy       = 0x00
	LEDs        = 0x11
	Type        = 0x12
	IR          = 0x13
	Status      = 0x15
	WriteMemory = 0x16
	ReadMemory  = 0x17
	IR2         = 0x1A

class InputReport:
	FLAG_CONTINUOUS         = 0x04
	Status                  = 0x20
	ReadData                = 0x21
	AcknowledgeResult       = 0x22
	Buttons                 = 0x30
	ButtonsAccel            = 0x31
	ButtonsExtenion         = 0x32
	ButtonsAccelIr          = 0x33
	ButtonsExtension        = 0x34
	ButtonsAccelExtension   = 0x35
	ButtonsIrExtension      = 0x36
	ButtonsAccelIrExtension = 0x37

class Register:
	IR                    = 0x4B00030
	IR_SENSITIVITY_1      = 0x4B00000
	IR_SENSITIVITY_2      = 0x4B0001A
	IR_MODE               = 0x4B00033
	EXTENSION_INIT_1      = 0x4A400F0
	EXTENSION_INIT_2      = 0x4A400FB
	MOTIONPLUS_INIT_1     = 0x4A600F0
	MOTIONPLUS_INIT_2     = 0x4A600FE

	EXTENSION_INIT_1_VAL  = 0x55
	EXTENSION_INIT_2_VAL  = 0x00
	MOTIONPLUS_INIT_1_VAL = 0x55
	MOTIONPLUS_INIT_2_VAL = 0x04

class LEDs:
	Rumble  = 0x01
	Player1 = 0x10
	Player2 = 0x20
	Player3 = 0x40
	Player4 = 0x80

class IrValue:
	Max = 1023
	Min = 0

class IrState:
	Off = 0x00
	On  = 0x04

class IrMode:
	Basic    = 0x01 # just the position of the 4 dots
	Extended = 0x03 # position plus approx. object size
	Full     = 0x05 # even more, read the docs

class IrSensitivity:
	Lv1  = [b'\x02\x00\x00\x71\x01\x00\x64\x00\xfe', b'\xfd\x05']
	Lv2  = [b'\x02\x00\x00\x71\x01\x00\x96\x00\xb4', b'\xb3\x04']
	Lv3  = [b'\x02\x00\x00\x71\x01\x00\xaa\x00\x64', b'\x63\x03']
	Lv4  = [b'\x02\x00\x00\x71\x01\x00\xc8\x00\x36', b'\x35\x03']
	Lv5  = [b'\x07\x00\x00\x71\x01\x00\x72\x00\x20', b'\x1f\x03']
	Max  = [b'\x00\x00\x00\x00\x00\x00\x90\x00\x41', b'\x40\x00']

class State:
	btnLeft  = False
	btnRight = False
	btnDown  = False
	btnUp    = False
	btnPlus  = False
	btnTwo   = False
	btnOne   = False
	btnB     = False
	btnA     = False
	btnMinus = False
	btnHome  = False
	x        = 0x80
	y        = 0x80
	z        = 0x80
	ir1      = [0,0]
	ir2      = [0,0]
	ir3      = [0,0]
	ir4      = [0,0]
	found1   = False
	found2   = False
	found3   = False
	found4   = False
	yaw      = 0x1f7f
	roll     = 0x1f7f
	pitch    = 0x1f7f

def parseButtons(d, s=State()):
	s.btnLeft  = d[1] & 0x01
	s.btnRight = d[1] & 0x02
	s.btnDown  = d[1] & 0x04
	s.btnUp    = d[1] & 0x08
	s.btnPlus  = d[1] & 0x10
	s.btnTwo   = d[2] & 0x01
	s.btnOne   = d[2] & 0x02
	s.btnB     = d[2] & 0x04
	s.btnA     = d[2] & 0x08
	s.btnMinus = d[2] & 0x10
	s.btnHome  = d[2] & 0x80
	return s

def parseAccel(d, s=State()):
	s.x        = d[3]
	s.y        = d[4]
	s.z        = d[5]
	return s

def parseIr(d, s=State()):
	s.ir1 = [
		d[6]  | ((d[8]  >> 4) & 0x03) << 8,
		d[7]  | ((d[8]  >> 6) & 0x03) << 8
	]
	s.ir2 = [
		d[9]  | ((d[8]  >> 0) & 0x03) << 8,
		d[10] | ((d[8]  >> 2) & 0x03) << 8
	]
	s.ir3 = [
		d[11] | ((d[13] >> 4) & 0x03) << 8,
		d[12] | ((d[13] >> 6) & 0x03) << 8
	]
	s.ir4 = [
		d[14] | ((d[13] >> 0) & 0x03) << 8,
		d[15] | ((d[13] >> 2) & 0x03) << 8
	]
	s.found1 = LEDs.Player1 if s.ir1[0] != IrValue.Max and s.ir1[1] != IrValue.Max else 0x00
	s.found2 = LEDs.Player2 if s.ir2[0] != IrValue.Max and s.ir2[1] != IrValue.Max else 0x00
	s.found3 = LEDs.Player3 if s.ir3[0] != IrValue.Max and s.ir3[1] != IrValue.Max else 0x00
	s.found4 = LEDs.Player4 if s.ir4[0] != IrValue.Max and s.ir4[1] != IrValue.Max else 0x00
	return s

def parseButtonsAccelIrState(d):
	s = State()
	s = parseButtons(d, s)
	s = parseAccel(d, s)
	s = parseIr(d, s)
	return s

def parseButtonsAccelIrExtensionState(d):
	s = State()
	s = parseButtons(d, s)
	s = parseAccel(d, s)
	s = parseIr(d, s)
	s.yaw   = d[16] | ((d[19] >> 2) & 0x3f) << 8
	s.roll  = d[17] | ((d[20] >> 2) & 0x3f) << 8
	s.pitch = d[18] | ((d[21] >> 2) & 0x3f) << 8
	return s

class ControllerOperationMode:
	OFF         = 0
	CALIBRATION = 1
	DRAWING     = 2

class ControllerMouseState:
	x = None
	y = None
	pressed = False

class ControllerPointerState:
	def __init__(self, calibX=None, calibY=None, factor=None):
		if(calibX): self.calibX = calibX
		if(calibY): self.calibY = calibY
		if(factor): self.factor = factor

	x = None
	y = None
	calibX = 8175
	calibY = 8140
	factor = 0.02
	visible = False

class Controller:
	CALIBRATION_MARGIN = 0.05

	evtControllerDisconnected = None
	evtStatusReport = None
	evtLaserPointer = None
	evtCalibrationChanged = None

	def __init__(self):
		self.configParser = None
		self.configPath = str(Path.home())+'/.config/wiimote4linux.ini'

		self.dev = None
		self.mouseState = ControllerMouseState()
		self.pointerState = ControllerPointerState()

		self.smoothingBuffer = []
		self.maxSmoothingBufferSize = 4

		self.calibrationPoints = []

		pyautogui.PAUSE = 0

	def start(self, screenWidth, screenHeight):
		self.screenWidth = screenWidth
		self.screenHeight = screenHeight

		self.__connect()

		# choose input report format
		self.__initMotionPlus()
		self.__initIr()
		self.__sendOutputReport(OutputReport.Type,
			struct.pack('B', InputReport.FLAG_CONTINUOUS) + struct.pack('B', InputReport.ButtonsAccelIrExtension)
		)

		# software setup
		self.__initWarpMatrix()
		self.operationMode = ControllerOperationMode.OFF
		self.__readConfig()

		# start reading input reports
		self.inputLoop = threading.Thread(target=self.__inputLoop, daemon=True)
		self.inputLoop.start()

	def __connect(self):
		#for d in hid.enumerate(): print(d)
		# connect to HID device
		for id in IDs:
			try:
				self.dev = hid.Device(id['vid'], id['pid'])
				print(f'Connected to: {self.dev.product}, Serial: {self.dev.serial}')
				break
			except Exception as e: pass
		if(not self.dev):
			raise Exception('Unable to find a Wiimote HID device')

	def __writeRegister(self, register, payload):
		self.__sendOutputReport(OutputReport.WriteMemory,
			struct.pack('>I', register) + struct.pack('B', len(payload)) + payload.ljust(16, b'\x00')
		)

	def __sendOutputReport(self, report, payload):
		packet = struct.pack('B', report) + payload
		#print('<==', packet.hex())
		self.dev.write(packet)

	def __initMotionPlus(self):
		self.__writeRegister(Register.MOTIONPLUS_INIT_1, bytes([Register.MOTIONPLUS_INIT_1_VAL]))
		self.__writeRegister(Register.MOTIONPLUS_INIT_2, bytes([Register.MOTIONPLUS_INIT_2_VAL]))

	def __initIr(self):
		# IR init procedure
		self.__sendOutputReport(OutputReport.IR, bytes([IrState.On]))
		self.__sendOutputReport(OutputReport.IR2, bytes([IrState.On]))
		self.__writeRegister(Register.IR, bytes([0x08]))
		self.__writeRegister(Register.IR_SENSITIVITY_1, IrSensitivity.Max[0])
		self.__writeRegister(Register.IR_SENSITIVITY_2, IrSensitivity.Max[1])
		self.__writeRegister(Register.IR_MODE, bytes([IrMode.Basic]))
		self.__writeRegister(Register.IR, bytes([0x08]))

	def __initWarpMatrix(self):
		self.warpMatrix = warper()
		self.warpMatrix.setDestination(
			self.screenWidth  * self.CALIBRATION_MARGIN,
			self.screenHeight * self.CALIBRATION_MARGIN,
			self.screenWidth  * (1.0 - self.CALIBRATION_MARGIN),
			self.screenHeight * self.CALIBRATION_MARGIN,
			self.screenWidth  * self.CALIBRATION_MARGIN,
			self.screenHeight * (1.0 - self.CALIBRATION_MARGIN),
			self.screenWidth  * (1.0 - self.CALIBRATION_MARGIN),
			self.screenHeight * (1.0 - self.CALIBRATION_MARGIN)
		)

	def __readConfig(self):
		self.configParser = configparser.ConfigParser()
		self.configParser.read(self.configPath)

		if(self.configParser.has_section('activeboard')):
			config = dict(self.configParser.items('activeboard'))
			self.maxSmoothingBufferSize = int(config.get('smoothing', self.maxSmoothingBufferSize))
			topleft = config.get('calibration-topleft', '0,0').split(',')
			topright = config.get('calibration-topright', '0,0').split(',')
			bottomleft = config.get('calibration-bottomleft', '0,0').split(',')
			bottomright = config.get('calibration-bottomright', '0,0').split(',')
			self.warpMatrix.setSource(
				int(topleft[0]), int(topleft[1]),
				int(topright[0]), int(topright[1]),
				int(bottomleft[0]), int(bottomleft[1]),
				int(bottomright[0]), int(bottomright[1])
			)
			self.warpMatrix.computeWarp()
			self.operationMode = ControllerOperationMode.DRAWING

		if(self.configParser.has_section('laserpointer')):
			config = dict(self.configParser.items('laserpointer'))
			self.pointerState = ControllerPointerState(
				int(config.get('yaw', self.pointerState.calibX)),
				int(config.get('pitch', self.pointerState.calibY)),
				float(config.get('factor', self.pointerState.factor)),
			)

	def __saveConfig(self, topleftx, toplefty, toprightx, toprighty, bottomleftx, bottomlefty, bottomrightx, bottomrighty):
		if(not self.configParser.has_section('activeboard')):
			self.configParser.add_section('activeboard')
		self.configParser['activeboard']['calibration-topleft'] = str(topleftx)+','+str(toplefty)
		self.configParser['activeboard']['calibration-topright'] = str(toprightx)+','+str(toprighty)
		self.configParser['activeboard']['calibration-bottomleft'] = str(bottomleftx)+','+str(bottomlefty)
		self.configParser['activeboard']['calibration-bottomright'] = str(bottomrightx)+','+str(bottomrighty)

		with open(self.configPath, 'w') as f:
			self.configParser.write(f)

	def __smooth(self, x, y):
		smoothingBufferSize = 1
		for sb in self.smoothingBuffer:
			x += sb[0]; y += sb[1]
			smoothingBufferSize += 1
		x = x / smoothingBufferSize
		y = y / smoothingBufferSize
		self.smoothingBuffer.insert(0, [x, y])
		self.smoothingBuffer = self.smoothingBuffer[:self.maxSmoothingBufferSize]
		return x, y

	def __inputLoop(self):
		previousState = State()

		while True:
			try:
				d = self.dev.read(64)
			except Exception as e:
				self.evtControllerDisconnected.emit()
				break
			currentState = State()

			if(d[0] == InputReport.Status):
				# parse status report
				batteryCritical = d[3] & 0b00000001
				batteryLevelPercent = int(d[6] * 100 / 255)
				self.evtStatusReport.emit(batteryLevelPercent)
				if(batteryCritical):
					print('!!! BATTERY CRITICAL', str(batteryLevelPercent)+'%')
				# re-enable to desired input report
				self.__sendOutputReport(OutputReport.Type,
					struct.pack('B', InputReport.FLAG_CONTINUOUS) + struct.pack('B', InputReport.ButtonsAccelIrExtension)
				)

			elif(d[0] == InputReport.ReadData):
				# todo: reactive MotionPlus (only when inactive; gets inactive sometimes)
				self.__writeRegister(Register.MOTIONPLUS_INIT_2, bytes([Register.MOTIONPLUS_INIT_2_VAL]))
				continue

			# parse data from supported reports
			elif(d[0] == InputReport.ButtonsAccelIr):
				currentState = parseButtonsAccelIrState(d)
			elif(d[0] == InputReport.ButtonsAccelIrExtension):
				currentState = parseButtonsAccelIrExtensionState(d)
			else:
				#print('Unsupported report:', d.hex())
				continue


			# set LEDs corresponding to recognized IR points
			if(currentState.found1 != previousState.found1 or currentState.found2 != previousState.found2
			or currentState.found3 != previousState.found3 or currentState.found4 != previousState.found4):
				self.__sendOutputReport(OutputReport.LEDs, bytes([
					0xff-(currentState.found1 + currentState.found2 + currentState.found3 + currentState.found4 + LEDs.Rumble)
				]))

			# presenter mode - press keys
			if(currentState.btnUp and not previousState.btnUp):
				pyautogui.press('up')
			elif(currentState.btnDown and not previousState.btnDown):
				pyautogui.press('down')
			elif(currentState.btnLeft and not previousState.btnLeft):
				pyautogui.press('left')
			elif(currentState.btnRight and not previousState.btnRight):
				pyautogui.press('right')
			elif(currentState.btnPlus and not previousState.btnPlus):
				#pyautogui.press('volumeup') # does not work under Linux
				m = alsaaudio.Mixer()
				m.setvolume(m.getvolume()[0] + 2)
			elif(currentState.btnMinus and not previousState.btnMinus):
				#pyautogui.press('volumedown') # does not work under Linux
				m = alsaaudio.Mixer()
				m.setvolume(m.getvolume()[0] - 2)

			# laserpointer mode - show dot on screen
			elif(currentState.btnA or currentState.btnB):
				self.pointerState.x = int( (currentState.yaw - self.pointerState.calibX) * self.pointerState.factor )
				self.pointerState.y = int( (currentState.pitch - self.pointerState.calibY) * -self.pointerState.factor )
				self.evtLaserPointer.emit(True, self.pointerState.x, self.pointerState.y)
			elif((not currentState.btnA and not currentState.btnB)
			and (previousState.btnA or previousState.btnB)):
				self.pointerState.x = None
				self.pointerState.y = None
				self.evtLaserPointer.emit(False, 0, 0)

			# whiteboard mode - calibration
			elif(currentState.btnHome and not previousState.btnHome):
				self.operationMode = ControllerOperationMode.CALIBRATION
				self.calibrationPoints.clear()
				self.evtCalibrationChanged.emit(len(self.calibrationPoints))
				print('Calibration initiated via home button')

			# whiteboard mode - move mouse
			elif(currentState.found1):
				if(self.operationMode == ControllerOperationMode.DRAWING):
					# translate coordinates
					x, y = self.warpMatrix.warp(currentState.ir1[0], currentState.ir1[1])
					# apply smoothing and move mouse
					self.mouseState.x, self.mouseState.y = self.__smooth(x, y)
					pyautogui.moveTo(
						min(self.screenWidth-2, max(0, self.mouseState.x)),
						min(self.screenHeight-2, max(0, self.mouseState.y))
					)
					if(not self.mouseState.pressed):
						pyautogui.mouseDown()
						self.mouseState.pressed = True

				elif(self.operationMode == ControllerOperationMode.CALIBRATION
				and not previousState.found1):
					if(len(self.calibrationPoints) < 4):
						self.calibrationPoints.append([currentState.ir1[0], currentState.ir1[1]])
						print('Calibration point {}: {},{}'.format(len(self.calibrationPoints), currentState.ir1[0], currentState.ir1[1]))
						self.evtCalibrationChanged.emit(len(self.calibrationPoints))
					if(len(self.calibrationPoints) == 4):
						self.warpMatrix.setSource(
							int(self.calibrationPoints[0][0]), int(self.calibrationPoints[0][1]),
							int(self.calibrationPoints[1][0]), int(self.calibrationPoints[1][1]),
							int(self.calibrationPoints[2][0]), int(self.calibrationPoints[2][1]),
							int(self.calibrationPoints[3][0]), int(self.calibrationPoints[3][1])
						)
						try:
							self.warpMatrix.computeWarp()
							self.__saveConfig(
								self.calibrationPoints[0][0], self.calibrationPoints[0][1],
								self.calibrationPoints[1][0], self.calibrationPoints[1][1],
								self.calibrationPoints[2][0], self.calibrationPoints[2][1],
								self.calibrationPoints[3][0], self.calibrationPoints[3][1]
							)
							self.operationMode = ControllerOperationMode.DRAWING
							print('Calibration done, switch to operation mode')
						except ZeroDivisionError:
							# invalid calibration data (e.g. points too close)
							print(traceback.format_exc())

			else: # mouse up
				self.smoothingBuffer.clear()
				self.mouseState.x = None
				self.mouseState.y = None
				if(self.mouseState.pressed):
					pyautogui.mouseUp()
					self.mouseState.pressed = False

			previousState = currentState
