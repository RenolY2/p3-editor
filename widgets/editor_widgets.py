import traceback

from PyQt5.QtGui import QMouseEvent, QWheelEvent, QPainter, QColor, QFont, QFontMetrics, QPolygon, QImage, QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QDialog, QMenu, QLineEdit,
                            QMdiSubWindow, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTextEdit, QAction, QShortcut)
import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as QtCore
from PyQt5.QtCore import QSize, pyqtSignal, QPoint, QRect
from PyQt5.QtCore import Qt
import PyQt5.QtGui as QtGui


def catch_exception(func):
    def handle(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            traceback.print_exc()
            #raise
    return handle


def catch_exception_with_dialog(func):
    def handle(*args, **kwargs):
        try:
            print(args, kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            print("hey")
            open_error_dialog(str(e), None)
    return handle


def catch_exception_with_dialog_nokw(func):
    def handle(*args, **kwargs):
        try:
            print(args, kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), None)
    return handle


def open_error_dialog(errormsg, self):
    errorbox = QtWidgets.QMessageBox()
    errorbox.critical(self, "Error", errormsg)
    errorbox.setFixedSize(500, 200)


class PikObjectEditor(QMdiSubWindow):
    triggered = pyqtSignal(object)
    closing = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window_name = "Edit Pikmin Object"
        self.resize(900, 500)
        self.setMinimumSize(QSize(300, 300))

        self.centralwidget = QWidget(self)
        self.setWidget(self.centralwidget)
        self.entity = None

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)

        self.dummywidget = QWidget(self)
        self.dummywidget.setMaximumSize(0,0)

        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.addWidget(self.dummywidget)


        # self.goto_id_action = ActionWithOwner("Go To ID", self, action_owner=self)

        #self.addAction(self.goto_id_action)

        #self.goto_shortcut = QKeySequence(Qt.CTRL+Qt.Key_G)


        #self.goto_id_action.setShortcut(self.goto_shortcut)
        #self.goto_id_action.setShortcutContext(Qt.WidgetShortcut)
        #self.goto_id_action.setAutoRepeat(False)

        #self.goto_id_action.triggered_owner.connect(self.open_new_window)

        self.textbox_xml = QTextEdit(self.centralwidget)
        self.button_savetext = QPushButton(self.centralwidget)
        self.button_savetext.setText("Save Object Data")
        self.button_savetext.setMaximumWidth(400)
        self.textbox_xml.setLineWrapMode(QTextEdit.NoWrap)
        self.textbox_xml.setContextMenuPolicy(Qt.CustomContextMenu)
        #self.textbox_xml.customContextMenuRequested.connect(self.my_context_menu)

        metrics = QFontMetrics(font)
        self.textbox_xml.setTabStopWidth(4 * metrics.width(' '))
        self.textbox_xml.setFont(font)

        self.verticalLayout.addWidget(self.textbox_xml)
        self.verticalLayout.addWidget(self.button_savetext)
        self.setWindowTitle(self.window_name)

        QtWidgets.QShortcut(Qt.CTRL + Qt.Key_S, self).activated.connect(self.emit_save_object)
        self.button_savetext.setToolTip("Hotkey: Ctrl+S")

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.CTRL + Qt.Key_W:
            self.shortcut_closewindow()
        else:
            super().keyPressEvent(event)

    def emit_save_object(self):
        self.button_savetext.pressed.emit()

    @catch_exception
    def shortcut_closewindow(self):
        self.close()

    def closeEvent(self, event):
        self.closing.emit()

    def set_content(self, pikminobject):
        try:
            text = StringIO()
            for comment in pikminobject.preceeding_comment:
                assert comment.startswith("#")
                text.write(comment.strip())
                text.write("\n")
            node = pikminobject.to_textnode()
            piktxt = PikminTxt()
            piktxt.write(text, node=[node])
            self.textbox_xml.setText(text.getvalue())
            self.entity = pikminobject
            self.set_title(pikminobject.get_useful_object_name())
        except:
            traceback.print_exc()

    def open_new_window(self, owner):
        #print("It was pressed!", owner)
        #print("selected:", owner.textbox_xml.textCursor().selectedText())

        self.triggered.emit(self)

    def get_content(self):
        try:
            content = self.textbox_xml.toPlainText()
            obj = PikminObject()
            obj.from_text(content)
            obj.get_rotation()
            self.set_title(obj.get_useful_object_name())
            return obj
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)
            return None

    def set_title(self, objectname):
        self.setWindowTitle("{0} - {1}".format(self.window_name, objectname))

    def reset(self):
        pass


class AddPikObjectWindow(PikObjectEditor):
    @catch_exception
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "windowtype" in kwargs:
            self.window_name = kwargs["windowtype"]
            del kwargs["windowtype"]
        else:
            self.window_name = "Add Pikmin Object"

        self.resize(900, 500)
        self.setMinimumSize(QSize(300, 300))

        self.centralwidget = QWidget(self)
        self.setWidget(self.centralwidget)
        self.entity = None

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)

        self.dummywidget = QWidget(self)
        self.dummywidget.setMaximumSize(0,0)


        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.addWidget(self.dummywidget)

        self.setup_dropdown_menu()
        self.verticalLayout.addWidget(self.template_menu)

        self.textbox_xml = QTextEdit(self.centralwidget)
        self.button_savetext = QPushButton(self.centralwidget)
        self.button_savetext.setText("Add Object")
        self.button_savetext.setToolTip("Hotkey: Ctrl+S")
        self.button_savetext.setMaximumWidth(400)
        self.textbox_xml.setLineWrapMode(QTextEdit.NoWrap)
        self.textbox_xml.setContextMenuPolicy(Qt.CustomContextMenu)
        #self.textbox_xml.customContextMenuRequested.connect(self.my_context_menu)

        metrics = QFontMetrics(font)
        self.textbox_xml.setTabStopWidth(4 * metrics.width(' '))
        self.textbox_xml.setFont(font)

        self.verticalLayout.addWidget(self.textbox_xml)
        self.verticalLayout.addWidget(self.button_savetext)
        self.setWindowTitle(self.window_name)

        #QtWidgets.QShortcut(Qt.CTRL + Qt.Key_S, self).activated.connect(self.emit_add_object)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.CTRL + Qt.Key_S:
            self.emit_add_object()
        else:
            super().keyPressEvent(event)

    def emit_add_object(self):
        self.button_savetext.pressed.emit()

    def get_content(self):
        try:
            content = self.textbox_xml.toPlainText()
            obj = PikminObject()
            obj.from_text(content)
            obj.get_rotation()
            return obj
        except Exception as e:
            traceback.print_exc()
            open_error_dialog(str(e), self)
            return None

    def setup_dropdown_menu(self):
        self.template_menu = QtWidgets.QComboBox(self)
        self.template_menu.addItem("-- select object template --")
        self.template_menu.addItem("[None]")

        for filename in os.listdir("./object_templates"):
            if filename.endswith(".txt"):
                self.template_menu.addItem(filename)

        self.template_menu.currentIndexChanged.connect(self.read_template_file_into_window)

    @catch_exception_with_dialog
    def read_template_file_into_window(self, index):
        if index == 1:
            self.textbox_xml.setText("")
        elif index > 1:
            filename = self.template_menu.currentText()

            with open(os.path.join("./object_templates", filename), "r", encoding="utf-8") as f:
                self.textbox_xml.setText(f.read())


class SpawnpointEditor(QMdiSubWindow):
    triggered = pyqtSignal(object)
    closing = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.centralwidget = QWidget(self)
        self.setWidget(self.centralwidget)
        self.entity = None
        self.resize(400, 200)

        font = QFont()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.verticalLayout = QVBoxLayout(self.centralwidget)

        self.position = QLineEdit(self.centralwidget)
        self.rotation = QLineEdit(self.centralwidget)

        self.button_savetext = QPushButton(self.centralwidget)
        self.button_savetext.setText("Set Data")
        self.button_savetext.setMaximumWidth(400)

        self.verticalLayout.addWidget(QLabel("startPos"))
        self.verticalLayout.addWidget(self.position)
        self.verticalLayout.addWidget(QLabel("startDir"))
        self.verticalLayout.addWidget(self.rotation)
        self.verticalLayout.addWidget(self.button_savetext)
        self.setWindowTitle("Edit startPos/Dir")

    def closeEvent(self, event):
        self.closing.emit()

    def get_pos_dir(self):
        pos = self.position.text().strip()
        direction = float(self.rotation.text().strip())

        if "," in pos:
            pos = [float(x.strip()) for x in pos.split(",")]
        else:
            pos = [float(x.strip()) for x in pos.split(" ")]

        assert len(pos) == 3

        return pos, direction
