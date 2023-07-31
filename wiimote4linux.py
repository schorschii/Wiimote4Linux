#!/usr/bin/env python3
# *-* coding: utf-8 *-*

import os
import sys
import time
import traceback

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from locale import getdefaultlocale

import wiimote


class SystemTrayIcon(QSystemTrayIcon):
	parentWidget = None

	def __init__(self, icon, parent):
		QSystemTrayIcon.__init__(self, icon, parent)
		self.parentWidget = parent
		menu = QMenu(parent)
		actionOpenMainWindow = menu.addAction('Control Window')
		actionOpenMainWindow.triggered.connect(self.openMainWindow)
		actionExit = menu.addAction('Exit')
		actionExit.triggered.connect(self.exit)
		self.setContextMenu(menu)
		self.activated.connect(self.showMenuOnTrigger)
		self.setToolTip('Wiimote4Linux')

	def showMenuOnTrigger(self, reason):
		if(reason == QSystemTrayIcon.Trigger):
			self.contextMenu().popup(QCursor.pos())

	def openMainWindow(self):
		self.parentWidget.show()

	def exit(self):
		QCoreApplication.exit()

class LaserPointerDot(QMainWindow):
	position = [0, 0]

	def __init__(self):
		super(LaserPointerDot, self).__init__()
		self.setWindowFlags(
			Qt.FramelessWindowHint # no border
			| Qt.WindowStaysOnTopHint # always on top
			| Qt.CustomizeWindowHint | Qt.Tool # no taskbar entry
		)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self.resize(23, 23)
		self.setWindowTitle('')

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setPen(QPen(Qt.white, 2, Qt.SolidLine))
		painter.setBrush(QBrush(Qt.red, Qt.SolidPattern))
		painter.drawEllipse(2, 2, 20, 20)

	def moveRel(self, x, y):
		self.position[0] += x
		self.position[1] += y
		self.move(self.position[0], self.position[1])

class CalibrationWindow(QDialog):
	DOT_SIZE = 10

	def __init__(self):
		super(CalibrationWindow, self).__init__()
		self.setWindowFlags(Qt.FramelessWindowHint | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)
		self.setWindowState(Qt.WindowFullScreen)
		self.setWindowTitle('Calibration Board')
		self.points = 0
		self.parentWidgetReference = None

	def paintEvent(self, event):
		marginHorizontal = int(self.width() * wiimote.Controller.CALIBRATION_MARGIN)
		marginVertical = int(self.height() * wiimote.Controller.CALIBRATION_MARGIN)

		painter = QPainter(self)
		painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
		if(self.points == 0):
			painter.drawEllipse(
				marginHorizontal, marginVertical,
				self.DOT_SIZE, self.DOT_SIZE
			)
		elif(self.points == 1):
			painter.drawEllipse(
				self.width()-self.DOT_SIZE-marginHorizontal, marginVertical,
				self.DOT_SIZE, self.DOT_SIZE
			)
		elif(self.points == 2):
			painter.drawEllipse(
				marginHorizontal, self.height()-self.DOT_SIZE-marginVertical,
				self.DOT_SIZE, self.DOT_SIZE
			)
		elif(self.points == 3):
			painter.drawEllipse(
				self.width()-self.DOT_SIZE-marginHorizontal, self.height()-self.DOT_SIZE-marginVertical,
				self.DOT_SIZE, self.DOT_SIZE
			)

	def drawPoint(self, points):
		self.points = points
		if(self.points > 3):
			self.hide()
			if(self.parentWidgetReference):
				self.parentWidgetReference.show()
		else:
			self.repaint()

class ControlWindow(QMainWindow):
	evtControllerDisconnected = pyqtSignal()
	evtStatusReport = pyqtSignal(int)
	evtLaserPointer = pyqtSignal(bool, int, int)
	evtCalibrationChanged = pyqtSignal(int)

	def __init__(self):
		super(ControlWindow, self).__init__()
		self.setWindowTitle('Wiimote4Linux Control')
		self.setWindowFlags(Qt.Drawer)

		# init other windows
		self.laserPointerDot = LaserPointerDot()
		self.calibrationWindow = CalibrationWindow()

		# connect events
		self.evtControllerDisconnected.connect(self.evtControllerDisconnectedHandler)
		self.evtStatusReport.connect(self.evtStatusReportHandler)
		self.evtLaserPointer.connect(self.evtLaserPointerHandler)
		self.evtCalibrationChanged.connect(self.evtCalibrationChangedHandler)

		# main window layout
		self.mainLayout = QGridLayout()

		self.sltScreen = QComboBox()
		for screen in QApplication.instance().screens():
			self.sltScreen.addItem(
				screen.name()+': '
				+str(screen.geometry().x())+','+str(screen.geometry().y())
				+' '+str(screen.geometry().width())+'x'+str(screen.geometry().height())
			)
		self.mainLayout.addWidget(self.sltScreen, 0, 0, 1, 4)

		self.btnConnect = QPushButton('Connect')
		self.btnConnect.clicked.connect(self.onClickConnect)
		self.mainLayout.addWidget(self.btnConnect, 1, 0)
		self.btnCalibrate = QPushButton('Calibrate')
		self.btnCalibrate.clicked.connect(self.onClickCalibrate)
		self.mainLayout.addWidget(self.btnCalibrate, 1, 1)
		self.btnMouseControl = QPushButton('Mouse Control')
		self.btnMouseControl.setCheckable(True)
		self.btnMouseControl.setChecked(True)
		self.btnMouseControl.clicked.connect(self.onClickMouseControl)
		self.mainLayout.addWidget(self.btnMouseControl, 1, 2)
		self.btnDraw = QPushButton('Draw')
		self.btnDraw.clicked.connect(self.onClickDraw)
		self.mainLayout.addWidget(self.btnDraw, 1, 3)

		self.lblStatus = QLabel('Initializing...')
		self.mainLayout.addWidget(self.lblStatus, 2, 0, 1, 3)

		centralWidget = QWidget()
		centralWidget.setLayout(self.mainLayout)
		self.setCentralWidget(centralWidget)

		# load icons
		self.icon = QIcon(os.path.dirname(os.path.realpath(__file__))+'/icon.svg')
		self.iconError = QIcon(os.path.dirname(os.path.realpath(__file__))+'/icon-error.svg')

		# init tray icon
		self.trayIcon = SystemTrayIcon(self.icon, self)
		self.trayIcon.show()

		# start controller
		self.wiimoteController = wiimote.Controller()
		self.wiimoteController.evtControllerDisconnected = self.evtControllerDisconnected
		self.wiimoteController.evtStatusReport = self.evtStatusReport
		self.wiimoteController.evtLaserPointer = self.evtLaserPointer
		self.wiimoteController.evtCalibrationChanged = self.evtCalibrationChanged
		self.tryInitController(False)

	def tryInitController(self, reportError=True):
		try:
			targetScreen = QApplication.instance().screens()[self.sltScreen.currentIndex()]
			self.wiimoteController.start(
				targetScreen.geometry().width(),
				targetScreen.geometry().height()
			)
			self.lblStatus.setText('Wiimote connected.')
			self.setActiveboardEnabled(True)
		except Exception as e:
			print(traceback.format_exc())
			if(reportError):
				self.showDialog('Wiimote4Linux', 'Unable to initialize controller.', str(e))
			self.lblStatus.setText(str(e))
			self.setActiveboardEnabled(False)

	def setActiveboardEnabled(self, state):
		if(state):
			self.trayIcon.setIcon(self.icon)
		else:
			self.trayIcon.setIcon(self.iconError)
		self.btnConnect.setEnabled(not state)
		self.btnCalibrate.setEnabled(state)
		self.btnMouseControl.setEnabled(state)
		self.btnDraw.setEnabled(state)

	def showDialog(self, title, text, additionalText='', icon=QMessageBox.Critical):
		msg = QMessageBox()
		msg.setIcon(icon)
		msg.setWindowTitle(title)
		msg.setText(text)
		msg.setDetailedText(additionalText)
		msg.setStandardButtons(QMessageBox.Ok)
		msg.exec()

	def evtControllerDisconnectedHandler(self):
		self.lblStatus.setText('Wiimote disconnected!')
		self.setActiveboardEnabled(False)

	def evtStatusReportHandler(self, batteryLevel):
		self.lblStatus.setText('Wiimote connected (battery '+str(batteryLevel)+'%)')

	def evtLaserPointerHandler(self, visible, x, y):
		if(visible):
			self.laserPointerDot.show()
			self.laserPointerDot.moveRel(x, y)
		else:
			self.laserPointerDot.hide()

	def evtCalibrationChangedHandler(self, pointsRecognized):
		self.showCalibrationWindow(pointsRecognized)

	def showCalibrationWindow(self, points=0):
		self.hide()
		self.parentWidgetReference = self
		targetScreen = QApplication.instance().screens()[self.sltScreen.currentIndex()]
		self.calibrationWindow.resize(20, 20)
		self.calibrationWindow.move(targetScreen.geometry().x(), targetScreen.geometry().y())
		time.sleep(0.1)
		self.calibrationWindow.resize(targetScreen.geometry().width(), targetScreen.geometry().height())
		self.calibrationWindow.showFullScreen()
		self.calibrationWindow.drawPoint(points)

	def onClickConnect(self, e):
		self.tryInitController()

	def onClickCalibrate(self, e):
		self.wiimoteController.operationMode = wiimote.ControllerOperationMode.CALIBRATION
		self.wiimoteController.calibrationPoints.clear()
		self.showCalibrationWindow()

	def onClickMouseControl(self, e):
		if(self.btnMouseControl.isChecked()):
			self.wiimoteController.operationMode = wiimote.ControllerOperationMode.DRAWING
		else:
			self.wiimoteController.operationMode = wiimote.ControllerOperationMode.OFF

	def onClickDraw(self, e):
		self.showDialog('Wiimote4Linux', 'Coming soon!', '(maybe)', QMessageBox.Information)


# initialize QT app
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
controlWindow = ControlWindow()
sys.exit(app.exec_())
