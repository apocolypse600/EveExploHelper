# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'keyBindDialog.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_KeyBindDialog(object):
    def setupUi(self, KeyBindDialog):
        KeyBindDialog.setObjectName("KeyBindDialog")
        KeyBindDialog.resize(332, 96)
        self.verticalLayout = QtWidgets.QVBoxLayout(KeyBindDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayoutButtons = QtWidgets.QHBoxLayout()
        self.horizontalLayoutButtons.setObjectName("horizontalLayoutButtons")
        self.pushButtonAddAnother = QtWidgets.QPushButton(KeyBindDialog)
        self.pushButtonAddAnother.setObjectName("pushButtonAddAnother")
        self.horizontalLayoutButtons.addWidget(self.pushButtonAddAnother)
        self.verticalLayout.addLayout(self.horizontalLayoutButtons)
        self.buttonBox = QtWidgets.QDialogButtonBox(KeyBindDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(KeyBindDialog)
        self.buttonBox.accepted.connect(KeyBindDialog.accept)
        self.buttonBox.rejected.connect(KeyBindDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(KeyBindDialog)

    def retranslateUi(self, KeyBindDialog):
        _translate = QtCore.QCoreApplication.translate
        KeyBindDialog.setWindowTitle(_translate("KeyBindDialog", "Dialog"))
        self.pushButtonAddAnother.setText(_translate("KeyBindDialog", "Add Another"))
