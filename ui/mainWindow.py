# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'mainWindow.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(512, 241)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.labelMain = QtWidgets.QLabel(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.labelMain.sizePolicy().hasHeightForWidth())
        self.labelMain.setSizePolicy(sizePolicy)
        self.labelMain.setMinimumSize(QtCore.QSize(100, 50))
        self.labelMain.setFrameShape(QtWidgets.QFrame.Box)
        self.labelMain.setLineWidth(1)
        self.labelMain.setAlignment(QtCore.Qt.AlignCenter)
        self.labelMain.setIndent(0)
        self.labelMain.setObjectName("label_priceEstimate")
        self.horizontalLayout.addWidget(self.labelMain)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menuBar = QtWidgets.QMenuBar(MainWindow)
        self.menuBar.setGeometry(QtCore.QRect(0, 0, 512, 21))
        self.menuBar.setObjectName("menuBar")
        self.menuOptions = QtWidgets.QMenu(self.menuBar)
        self.menuOptions.setObjectName("menuOptions")
        MainWindow.setMenuBar(self.menuBar)
        self.actionKey_Binding = QtWidgets.QAction(MainWindow)
        self.actionKey_Binding.setObjectName("actionKey_Binding")
        self.actionCREST = QtWidgets.QAction(MainWindow)
        self.actionCREST.setObjectName("actionCREST")
        self.actionFeatures = QtWidgets.QAction(MainWindow)
        self.actionFeatures.setObjectName("actionFeatures")
        self.menuOptions.addAction(self.actionKey_Binding)
        self.menuOptions.addAction(self.actionCREST)
        self.menuOptions.addAction(self.actionFeatures)
        self.menuBar.addAction(self.menuOptions.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.labelMain.setText(_translate("MainWindow", "Waiting for input"))
        self.menuOptions.setTitle(_translate("MainWindow", "Options"))
        self.actionKey_Binding.setText(_translate("MainWindow", "Key Binding"))
        self.actionCREST.setText(_translate("MainWindow", "CREST"))
        self.actionFeatures.setText(_translate("MainWindow", "Features"))
