import time, sys
from cleo.io.buffered_io import BufferedIO
from cleo.ui.table import Table
from cleo.ui.table_cell import TableCell
from cleo.ui.table_cell_style import TableCellStyle
for n in range(14, 25, 2):
    t = Table(BufferedIO())
    t.set_rows([[TableCell("<a=" + "aaa=" * n + "!", style=TableCellStyle(cell_format="{}"))]])
    s = time.time(); t.render(); print(n, round(time.time() - s, 3), flush=True)
