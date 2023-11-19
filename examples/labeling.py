import sys
from pathlib import Path

import numpy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from volumina.api import Viewer
from volumina.colortables import create_random_16bit
from volumina.layer import ColortableLayer, GrayscaleLayer
from volumina.pixelpipeline.datasources import ArraySinkSource, ArraySource
from volumina.utility import ShortcutManager

COLORTABLE = [QColor(0, 0, 0, 0).rgba()] + create_random_16bit()


class ColorIndicator(QDialog):
    drawNumberChanged = pyqtSignal(int)
    drawColorChanged = pyqtSignal("quint64")
    size_changed = pyqtSignal(int)

    def __init__(self, colors, max_label, parent=None):
        super().__init__(parent)
        self.colors = colors
        self.number = 1
        self.size = 1
        self.max_label = max_label

        self.layout = QVBoxLayout()
        hbox_color = QHBoxLayout()
        self.decrement_paint_value_btn = QPushButton("-")
        self.decrement_paint_value_btn.clicked.connect(self.decrement_color)
        self.increment_paint_value_btn = QPushButton("+")
        self.new_paint_value_btn = QPushButton("*")
        self.increment_paint_value_btn.clicked.connect(self.increment_color)
        self.new_paint_value_btn.clicked.connect(self.new_color)
        self.edit_color = QLineEdit(str(self.number))
        self.edit_color.setAlignment(Qt.AlignCenter)
        self.edit_color.textChanged.connect(self.update_color_edit)
        hbox_color.addWidget(self.decrement_paint_value_btn)
        hbox_color.addWidget(self.edit_color)
        hbox_color.addWidget(self.increment_paint_value_btn)
        self.layout.addLayout(hbox_color)

        hbox_size = QHBoxLayout()
        self.number = 10
        self.decrement_brush_size_btn = QPushButton("-")
        self.decrement_brush_size_btn.clicked.connect(self.decrement_size)
        self.increment_brush_size_btn = QPushButton("+")
        self.increment_brush_size_btn.clicked.connect(self.increment_size)
        self.edit_size = QLineEdit(str(self.number))
        self.edit_size.setAlignment(Qt.AlignCenter)
        self.edit_size.textChanged.connect(self.update_size_edit)
        hbox_size.addWidget(self.decrement_brush_size_btn)
        hbox_size.addWidget(self.edit_size)
        hbox_size.addWidget(self.increment_brush_size_btn)
        self.layout.addLayout(hbox_size)

        self.setLayout(self.layout)
        self.update_color_edit()

        mgr = ShortcutManager()
        ActionInfo = ShortcutManager.ActionInfo

        mgr.register(
            "n",
            ActionInfo("Labeling", "new color", "get next new color", self.new_color, self, self.new_paint_value_btn),
        )

    def _color_step(self, step: int):
        number = self.number + step
        if 1 < number < len(self.colors) - 1:
            self.edit_color.setText(str(number))

    def increment_color(self):
        self._color_step(step=1)

    def decrement_color(self):
        self._color_step(step=-1)

    def new_color(self):
        self.max_label += 1
        self.edit_color.setText(str(self.max_label))

    def update_color_edit(self):
        self.number = int(self.edit_color.text())
        color = self.colors[self.number]
        x = QPalette()
        x.setColor(QPalette.Base, QColor(color))
        x.setColor(QPalette.Text, Qt.white)
        self.edit_color.setPalette(x)
        self.drawNumberChanged.emit(self.number)
        self.drawColorChanged.emit(color)

    def _size_step(self, step: int):
        new = self.size + step
        if 1 < new < 62:
            self.edit_size.setText(str(new))

    def increment_size(self):
        self._size_step(step=1)

    def decrement_size(self):
        self._size_step(step=-1)

    def update_size_edit(self):
        self.size = int(self.edit_size.text())
        self.size_changed.emit(self.size)


# data = Path("/Users/kutra/scratch") / "raw.npy"
# seg = Path("/Users/kutra/scratch") / "mc-seg.npy"

data = Path("/home/kutra/scratch") / "cremi-raw-xyzc.npy"

# data_arr = numpy.load(data)[numpy.newaxis, :, :, numpy.newaxis]
# label_arr = numpy.load(seg)[numpy.newaxis, :, :, numpy.newaxis]
data_arr = numpy.load(data)[numpy.newaxis, :, :, :, :]
label_arr = numpy.zeros_like(data_arr, dtype="uint32")

##-----
app = QApplication(sys.argv)
v = Viewer()


data_src = ArraySource(data_arr)
data_layer = GrayscaleLayer(data_src)
data_layer.name = "Raw"
data_layer.numberOfChannels = 1

label_src = ArraySinkSource(label_arr)
label_layer = ColortableLayer(label_src, colorTable=COLORTABLE, direct=False)
label_layer.name = "Labels"
label_layer.ref_object = None

# assert SHAPE == label_arr.shape == data_arr.shape
v.dataShape = data_arr.shape

v.layerstack.append(data_layer)
v.layerstack.append(label_layer)

v.editor.setLabelSink(label_src)
v.editor.setInteractionMode("brushing")

v.setWindowTitle("labeling")
v.showMaximized()
c = ColorIndicator(COLORTABLE, max_label=label_arr.max(), parent=v)
c.drawNumberChanged.connect(v.editor.brushingModel.setDrawnNumber)
c.drawColorChanged.connect(v.editor.brushingModel.setBrushColor)
c.size_changed.connect(v.editor.brushingModel.setBrushSize)
v.editor.brushingModel.drawnNumberChanged.connect(lambda x: c.edit_color.setText(str(x)))


c.show()

app.exec_()
