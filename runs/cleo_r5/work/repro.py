from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle
t = Table(BufferedIO())
t.set_rows([[TableCell("x", style=TableCellStyle())]])
t.render()
